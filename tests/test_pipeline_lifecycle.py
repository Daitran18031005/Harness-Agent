"""Vòng đời pipeline (audit #5, #6): đóng cổng MCP khi đóng pipeline, MỘT pipeline dùng chung cho UI (và các lượt được tuần tự hóa), cuộc gọi bị bỏ dở được chốt
bằng bộ quét nền thay vì nằm mãi trong bộ nhớ."""
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

from tests import _helpers  # noqa: F401  (đặt OPENAI_API_KEY="" ... trước khi import phần còn lại)

PHONE = "0984726714"


def make_pipeline(case, mcp_transport="inproc"):
    """Pipeline thật, bộ nhớ cục bộ + DB tạm; cổng MCP theo `mcp_transport`."""
    d = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, d, ignore_errors=True)
    patcher = mock.patch.dict(os.environ, {"MCP_TRANSPORT": mcp_transport, "MEMORY_TRANSPORT": "local", "OPENAI_API_KEY": ""})
    patcher.start()
    case.addCleanup(patcher.stop)
    from pipeline import CallCenterHarnessPipeline
    p = CallCenterHarnessPipeline(trace_file=os.path.join(d, "t.jsonl"), db_path=os.path.join(d, "t.db"))
    case.addCleanup(p.close)
    return p


def mcp_server_processes():
    import psutil
    out = []
    for child in psutil.Process().children(recursive=True):
        try:
            if any("mcp_servers." in part for part in child.cmdline()):
                out.append(child)
        except psutil.Error:
            pass
    return out


class CloseTest(unittest.TestCase):
    def test_close_closes_the_mcp_gateway(self):
        p = make_pipeline(self)
        self.assertFalse(p.mcp_gateway._closed)
        p.close()
        self.assertTrue(p.mcp_gateway._closed)
        p.close()                                                           # đóng hai lần không lỗi

    def test_close_ends_the_mcp_server_processes(self):
        before = {c.pid for c in mcp_server_processes()}
        p = make_pipeline(self, mcp_transport="stdio")
        started = [c for c in mcp_server_processes() if c.pid not in before]
        self.assertGreaterEqual(len(started), 2)                            # mcp-catalog và mcp-crm là tiến trình riêng
        p.close()
        deadline = time.time() + 15
        while time.time() < deadline and any(c.is_running() for c in started):
            time.sleep(0.2)
        self.assertEqual([c.pid for c in started if c.is_running()], [])    # không để tiến trình mồ côi sau khi đóng pipeline


class SerializedTurnsTest(unittest.TestCase):
    def test_turns_from_different_threads_never_overlap(self):
        """Một pipeline dùng chung cho nhiều phiên UI: lượt của phiên này không được xen vào giao dịch của phiên kia (begin_turn/commit dùng chung)."""
        p = make_pipeline(self)
        state = {"now": 0, "max": 0}
        guard = threading.Lock()

        def slow_process(*args, **kwargs):
            with guard:
                state["now"] += 1
                state["max"] = max(state["max"], state["now"])
            time.sleep(0.05)
            with guard:
                state["now"] -= 1
            return {"customer_id": "C1"}

        with mock.patch.object(p, "_process", side_effect=slow_process):
            threads = [threading.Thread(target=p.handle_incoming_request, args=("alo", PHONE), kwargs={"turn_num": i + 1}) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertEqual(state["max"], 1)


class IdleSweeperTest(unittest.TestCase):
    def _open_call(self, p):
        return p.handle_incoming_request("alo cho chị hỏi máy lọc", PHONE, call_date="2026-10-17", call_name="call_1", turn_num=1)

    def test_background_sweeper_finalizes_an_abandoned_call(self):
        """Khách đóng tab giữa chừng: không còn ai gọi gì nữa, nên chỉ một bộ quét nền mới chốt được cuộc gọi (episode `ngat_cuoc`, giải phóng bảng token PII)."""
        p = make_pipeline(self)
        r = self._open_call(p)
        cid = r["customer_id"]
        self.assertIn(PHONE, p._open_calls)
        p.start_idle_sweeper(idle_seconds=0.2, interval_s=0.05)
        deadline = time.time() + 10
        while time.time() < deadline and PHONE in p._open_calls:
            time.sleep(0.05)
        self.assertNotIn(PHONE, p._open_calls)
        episodes = p.memory.get_episodes(cid)
        self.assertEqual([e.outcome for e in episodes], ["ngat_cuoc"])
        self.assertEqual(p.orchestrator._vaults, {})                         # bảng token PII (SĐT/địa chỉ thật) đã được giải phóng

    def test_an_active_call_is_not_swept(self):
        p = make_pipeline(self)
        self._open_call(p)
        p.start_idle_sweeper(idle_seconds=3600, interval_s=0.05)
        time.sleep(0.4)
        self.assertIn(PHONE, p._open_calls)

    def test_sweeper_is_idempotent_and_stops_on_close(self):
        p = make_pipeline(self)
        t1 = p.start_idle_sweeper(idle_seconds=3600, interval_s=0.05)
        t2 = p.start_idle_sweeper(idle_seconds=3600, interval_s=0.05)
        self.assertIs(t1, t2)
        self.assertTrue(t1.is_alive())
        p.close()
        t1.join(5)
        self.assertFalse(t1.is_alive())

    def test_timeout_finalization_runs_inside_its_own_turn_transaction(self):
        """Chốt timeout phải có `begin_turn` riêng (provenance đúng cuộc gọi, ghi theo giao dịch) như `end_call` — không ghi tự do ngoài giao dịch."""
        p = make_pipeline(self)
        self._open_call(p)
        with mock.patch.object(p.memory, "begin_turn", wraps=p.memory.begin_turn) as spy:
            self.assertEqual(p.sweep_idle(idle_seconds=0), 1)
        self.assertEqual([c.args[0] for c in spy.call_args_list], ["call_1#timeout"])
        self.assertEqual(p.sweep_idle(idle_seconds=0), 0)                    # không chốt lần hai


class UiWiringTest(unittest.TestCase):
    def test_ui_shares_one_pipeline_across_sessions_and_starts_the_sweeper(self):
        """Mỗi lần mở/làm mới trang là một phiên Streamlit mới; trước đây mỗi phiên dựng pipeline riêng (+2 tiến trình MCP) và không bao giờ đóng."""
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        fake_class = mock.MagicMock(name="CallCenterHarnessPipeline")
        with mock.patch("pipeline.CallCenterHarnessPipeline", fake_class):
            for _ in range(2):                                              # hai phiên trình duyệt
                at = AppTest.from_file(os.path.join(_helpers.CODE_DIR, "ui_app.py"), default_timeout=60)
                at.run()
        self.assertEqual(fake_class.call_count, 1)
        fake_class.return_value.start_idle_sweeper.assert_called()


if __name__ == "__main__":
    unittest.main()
