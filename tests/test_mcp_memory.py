"""`mcp-memory` — MCP server THẬT thứ 3, nơi ghi duy nhất của bộ nhớ khách hàng (bước 19).

Hai tầng tool:
  - 6 TOOL CAO cho các thành phần: get_call_brief · search · timeline · commit_turn · commit_episode · delete_customer
  - TOOL THẤP (open/close/begin_turn/drain_writes/abort_turn/working_*/profile_*/facts_by_channel/episode*/merge_customer/query_policy/identity_link*) chỉ cho LÕI
Kiểm: mỗi tool cao chạy đúng; caller khác bị từ chối; kết quả qua MCP y hệt MemoryService cục bộ (cả đường tool cao lẫn đường tool thấp); một file DB chỉ có MỘT
người ghi; giao dịch theo lượt nằm trong server; xóa khách xóa sạch và chỉ Operator xóa được; kiểm toán phía server không chứa tham số; đường stdio = tiến trình riêng."""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest

from tests import _helpers  # noqa: F401  (đặt OPENAI_API_KEY="" ... trước khi import phần còn lại)
from src.identity.identity_map import IdentityLinkMap
from src.memory.episodic import EpisodeRecord
from src.memory.remote import (MemoryAccessDenied, MemoryLink, MemoryServerError, RemoteBackend, RemoteMemoryService, create_memory_service)
from src.memory.service import MemoryService

HIGH_TOOLS = {"memory.get_call_brief", "memory.search", "memory.timeline", "memory.commit_turn", "memory.commit_episode", "memory.delete_customer"}
LOW_TOOLS = {"memory.open", "memory.close", "memory.begin_turn", "memory.drain_writes", "memory.abort_turn", "memory.working_get", "memory.working_set",
             "memory.profile_set", "memory.profile_get", "memory.facts_by_channel", "memory.profile_versions", "memory.episode_add", "memory.episodes_get",
             "memory.merge_customer", "memory.query_policy", "memory.identity_links_load", "memory.identity_link_save"}
EXPECTED_TOOLS = HIGH_TOOLS | LOW_TOOLS | {"memory.admin_audit"}
ORCH, BRIEF, UI, OPERATOR, IDENT, CORE = "HarnessOrchestrator", "CallBriefBuilder", "StreamlitUI", "Operator", "IdentityResolver", "HarnessCore"
VALID_ARGS = {"memory.begin_turn": {"source": "x#turn1"}, "memory.working_get": {"session_id": "S"}, "memory.working_set": {"session_id": "S", "fields": {}},
              "memory.profile_set": {"customer_id": "Z", "key": "k", "value": 1}, "memory.profile_get": {"customer_id": "C1"},
              "memory.facts_by_channel": {"customer_id": "C1"}, "memory.profile_versions": {"customer_id": "C1"},
              "memory.episode_add": {"customer_id": "Z", "episode": {}}, "memory.episodes_get": {"customer_id": "C1"},
              "memory.merge_customer": {"src_id": "A", "dst_id": "A"}, "memory.query_policy": {"query": "đổi trả"},
              "memory.identity_link_save": {"contact_hash": "h", "master_id": "m"}, "memory.get_call_brief": {"customer_id": "C1"},
              "memory.search": {"query": "đổi trả"}, "memory.timeline": {"customer_id": "C1"}, "memory.commit_turn": {"ops": []},
              "memory.commit_episode": {"customer_id": "Z", "episode": {}}, "memory.delete_customer": {"customer_id": "NOBODY"}}
EVERYONE = {ORCH, BRIEF, UI, OPERATOR, IDENT, CORE, "EvalRunner", "TestHarness", "SeedScript"}


def episode(session="SESS-C1-2026-10-15", call_date="2026-10-15", **kw):
    return EpisodeRecord(session_id=session, call_index=1, call_date=call_date, channel="hotline", customer_goal="hỏi máy lọc",
                         product_advised="SKU-AP-Y", price_quoted_vnd=5200000, blocker="hỏi ý chồng", outcome="hen_goi_lai", **kw)


def script(orch, core=None, operator=None):
    """Cùng một chuỗi thao tác trên MemoryService cục bộ và RemoteMemoryService; trả về mọi thứ quan sát được.
    `core` mở/hủy lượt (tool thấp), `orch` đọc/ghi bộ nhớ cuộc gọi và CHỐT lượt, `operator` xóa khách và xem dòng thời gian."""
    core, operator = core or orch, operator or orch
    out = {}
    core.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
    orch.set_profile_fact("C1", "product_advised", "SKU-AP-Y")
    orch.set_profile_fact("C1", "budget_vnd", 5000000, ttl_days=30)
    orch.set_profile_fact("C1", "channels_seen", ["hotline"])
    orch.set_profile_fact("C1", "blocker", "hỏi ý chồng", ttl_days=0)          # ttl 0 -> hết hiệu lực ngay
    orch.set_profile_fact("C1", "budget_vnd", 5700000, ttl_days=30)            # supersede
    orch.set_profile_fact("C1", "budget_vnd", 5700000, ttl_days=30)            # cùng giá trị: không thêm phiên bản
    orch.add_episode("C1", episode())
    orch.set_working("SESS-C1-2026-10-15", current_turn=2, intent="buy", pending_slots={"size": "39"},
                     messages_in_session=[{"role": "user", "content": "alo"}])
    out["writes_t1"] = orch.drain_writes()
    core.begin_turn("call_2#turn1", call_date="2026-10-17", channel="zalo")
    orch.set_profile_fact("C1", "color", "đen")
    out["writes_t2"] = orch.drain_writes()
    out["facts"] = orch.get_profile_facts("C1")
    out["facts_on_date"] = orch.get_profile_facts("C1", on_date="2026-10-17")
    out["facts_expired"] = orch.get_profile_facts("C1", on_date="2026-12-31")
    out["by_channel"] = orch.facts_by_channel("C1", on_date="2026-10-17")
    out["episodes"] = [vars(e) for e in orch.get_episodes("C1")]
    out["last_episode"] = vars(orch.get_last_episode("C1"))
    out["no_episode"] = orch.get_last_episode("NOBODY")
    out["working"] = vars(orch.get_working("SESS-C1-2026-10-15"))
    tl = operator.timeline("C1")
    out["timeline_episodes"] = [vars(e) for e in tl["episodes"]]
    out["versions"] = {k: [(f.value, f.superseded, f.superseded_by, f.source_call, f.source_turn, f.source_channel, f.observed_on, f.ttl_days)
                           for f in fs] for k, fs in tl["versions"].items()}
    out["policy"] = orch.query_policy("đổi size trong bao lâu", on_date="2026-10-15")
    orch.merge_customer("ANON", "C1")                                          # nguồn rỗng: không lỗi
    orch.set_profile_fact("ANON", "size", "39")
    orch.add_episode("ANON", episode(session="SESS-ANON-1"))
    orch.merge_customer("ANON", "C1")
    out["after_merge"] = (orch.get_profile_facts("C1").get("size"), orch.get_profile_facts("ANON"), [e.session_id for e in orch.get_episodes("ANON")],
                          sorted(e.session_id for e in orch.get_episodes("C1")))
    deleted = []
    operator.register_delete_listener(deleted.append)
    operator.delete_customer_data("C1")
    out["after_delete"] = (orch.get_profile_facts("C1"), orch.get_episodes("C1"), orch.get_working("SESS-C1-2026-10-15").current_turn, deleted)
    return out


class InprocParityTest(unittest.TestCase):
    """Qua MCP (inproc) cho kết quả Y HỆT bộ nhớ cục bộ — cả đường tool cao lẫn đường tool thấp."""

    @classmethod
    def setUpClass(cls):
        cls.link = MemoryLink("inproc")

    @classmethod
    def tearDownClass(cls):
        cls.link.close()

    def new_remote(self, caller="TestHarness", **kw):
        m = RemoteMemoryService(enable_persistence=kw.pop("enable_persistence", False), transport="inproc", link=self.link, caller=caller, **kw)
        self.addCleanup(m.close)
        return m

    def test_server_exposes_every_memory_tool(self):
        import asyncio
        from mcp import Client
        from mcp_servers import memory_server
        server, _, _ = memory_server.build_server()

        async def go():
            async with Client(server) as c:
                return {t.name for t in (await c.list_tools()).tools}
        self.assertEqual(asyncio.run(go()), EXPECTED_TOOLS)
        self.assertEqual(len(HIGH_TOOLS), 6)

    def test_high_level_path_identical_to_local_service(self):
        base = self.new_remote()
        remote = script(base.as_caller(ORCH), core=base, operator=base.as_caller(OPERATOR))
        local = script(MemoryService(enable_persistence=False))
        self.assertEqual(local.keys(), remote.keys())
        for key in local:
            self.assertEqual(local[key], remote[key], key)

    def test_low_level_path_identical_to_local_service(self):
        base = self.new_remote()
        remote = script(base, core=base, operator=base.as_caller(OPERATOR))          # TestHarness thay lõi: toàn bộ đọc/ghi qua tool thấp
        local = script(MemoryService(enable_persistence=False))
        for key in local:
            self.assertEqual(local[key], remote[key], key)

    def test_each_component_uses_the_tool_tier_it_is_allowed(self):
        base = self.new_remote()
        base.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        orch = base.as_caller(ORCH)
        orch.set_profile_fact("C1", "color", "đen")
        orch.add_episode("C1", episode())
        orch.get_profile_facts("C1")
        orch.query_policy("đổi trả")
        orch.drain_writes()
        base.as_caller(BRIEF).get_profile_facts("C1")
        base.as_caller(OPERATOR).timeline("C1")
        base.as_caller(OPERATOR).delete_customer_data("C1")
        used = {a["tool"] for a in self.link.call("memory.admin_audit", {}, "TestHarness")["audit"] if a["caller"] in (ORCH, BRIEF, OPERATOR)}
        self.assertEqual(used, {"memory.commit_turn", "memory.commit_episode", "memory.get_call_brief", "memory.search", "memory.timeline", "memory.delete_customer"})

    def test_returns_copies_so_changes_must_go_through_set_working(self):
        m = self.new_remote().as_caller(ORCH)
        m.set_working("S1", messages_in_session=[{"role": "user", "content": "a"}])
        state = m.get_working("S1")
        state.messages_in_session.append({"role": "user", "content": "b"})
        self.assertEqual(len(m.get_working("S1").messages_in_session), 1)                 # chưa ghi
        m.set_working("S1", messages_in_session=state.messages_in_session)
        self.assertEqual(len(m.get_working("S1").messages_in_session), 2)

    def test_none_is_a_valid_fact_value(self):
        base = self.new_remote()
        base.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        for m in (base.as_caller(ORCH), base):
            m.set_profile_fact("C1", "blocker", None)
            self.assertIn("blocker", m.get_profile_facts("C1"))
            self.assertIsNone(m.get_profile_facts("C1")["blocker"])

    def test_keys_starting_with_underscore_are_data_not_stripped(self):
        for m in (self.new_remote().as_caller(ORCH), self.new_remote()):
            m.set_working("S1", pending_slots={"_draft": 1, "size": "39"})
            self.assertEqual(m.get_working("S1").pending_slots, {"_draft": 1, "size": "39"})

    def test_errors_are_structured_not_silent(self):
        base = self.new_remote()
        for m in (base, base.as_caller(ORCH)):
            with self.assertRaises(MemoryServerError):
                m.set_working("S1", khong_co_truong_nay=1)                                # tên trường lạ là lỗi lập trình (như bản cục bộ)
        with self.assertRaises(MemoryServerError):
            base.as_caller(ORCH)._call("memory.commit_turn", ops=[{"op": "xoa_het"}])      # thao tác lạ
        with self.assertRaises(MemoryServerError):
            base.as_caller(BRIEF)._call("memory.get_call_brief", customer_id="C1", include=["bí_mật"])
        with self.assertRaises(MemoryServerError):
            base.as_caller(BRIEF)._call("memory.get_call_brief", include=["working"])      # thiếu session_id
        base.close()
        self.assertEqual(self.link.call("memory.profile_get", {"store_id": "mem:khong-ton-tai", "customer_id": "C1"}, "TestHarness")["error"],
                         "tool_execution_failed")

    def test_commit_turn_applies_ops_in_order_and_finalizes_only_on_request(self):
        base = self.new_remote()
        orch = base.as_caller(ORCH)
        base.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        res = orch._call("memory.commit_turn", ops=[{"op": "set_fact", "customer_id": "C1", "key": "size", "value": "38"},
                                                    {"op": "set_fact", "customer_id": "C1", "key": "size", "value": "39"},
                                                    {"op": "set_working", "session_id": "S1", "fields": {"current_turn": 3}}])
        self.assertEqual(len(res["results"]), 3)
        self.assertNotIn("writes", res)                                                    # chưa chốt lượt
        self.assertEqual(orch.get_profile_facts("C1"), {"size": "39"})                      # nhưng đọc thấy ngay
        done = orch._call("memory.commit_turn", finalize=True)
        self.assertEqual([w["op"] for w in done["writes"]], ["set", "supersede"])
        self.assertEqual(orch._call("memory.commit_turn", finalize=True)["writes"], [])     # nhật ký đã rút

    def test_get_call_brief_returns_exactly_the_requested_parts(self):
        base = self.new_remote()
        orch = base.as_caller(ORCH)
        orch.set_profile_fact("C1", "color", "đen")
        orch.add_episode("C1", episode())
        orch.set_working("S1", current_turn=4)
        full = orch._call("memory.get_call_brief", customer_id="C1", on_date="2026-10-15")
        self.assertEqual(set(full), {"facts", "by_channel", "episodes"})                    # mặc định: không kèm working
        self.assertEqual(set(orch._call("memory.get_call_brief", customer_id="C1", include=["facts"])), {"facts"})
        self.assertEqual(orch._call("memory.get_call_brief", include=["working"], session_id="S1")["working"]["current_turn"], 4)

    def test_memory_backed_resolver_links_persist_through_the_server(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        db = os.path.join(d, "m.db")
        m = self.new_remote(enable_persistence=True, db_path=db)
        backend = m.backend                                                                # liên kết định danh = tool thấp, do lõi giữ
        self.assertIsInstance(backend, RemoteBackend)
        self.assertTrue(backend.available)
        master = IdentityLinkMap(backend).resolve_master_id("0900111222")
        self.assertEqual(IdentityLinkMap(backend).resolve_master_id("0900111222"), master)   # bản đồ mới nạp lại từ server
        self.assertIsNone(self.new_remote().backend)                                      # kho không bền vững: không có backend (như cục bộ)
        with self.assertRaises(MemoryAccessDenied):
            m.as_caller(IDENT).backend.load_identity_links()                               # thành phần khác không đọc/ghi thẳng bảng liên kết

    def test_factory_picks_transport(self):
        self.assertIsInstance(create_memory_service(enable_persistence=False, transport="local"), MemoryService)
        with self.assertRaises(ValueError):
            create_memory_service(enable_persistence=False, transport="bồ-câu-đưa-thư")


class PermissionsTest(unittest.TestCase):
    """Phân quyền theo caller, kiểm ở PHÍA SERVER, mặc định từ chối. Tool thấp chỉ lõi; commit_* chỉ HarnessOrchestrator; delete_customer chỉ Operator."""

    @classmethod
    def setUpClass(cls):
        cls.link = MemoryLink("inproc")
        cls.admin = RemoteMemoryService(enable_persistence=False, transport="inproc", link=cls.link, caller="TestHarness")
        cls.sid = cls.admin.store_id
        cls.admin.set_profile_fact("C1", "product_advised", "SKU-AP-Y")
        cls.admin.add_episode("C1", episode())

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()
        cls.link.close()

    def status(self, tool, caller, **args):
        """'forbidden' nếu bị từ chối; 'allowed' nếu không (kể cả khi tham số sai — quyền được kiểm TRƯỚC khi chạy)."""
        res = self.link.call(tool, {"store_id": self.sid, **args}, caller)
        return "forbidden" if res.get("error") == "forbidden" else "allowed"

    def test_low_level_tools_are_core_only(self):
        core = {CORE, "EvalRunner", "TestHarness"}
        args = {"memory.begin_turn": {"source": "x#turn1"}, "memory.working_get": {"session_id": "S"}, "memory.working_set": {"session_id": "S", "fields": {}},
                "memory.profile_set": {"customer_id": "Z", "key": "k", "value": 1}, "memory.profile_get": {"customer_id": "C1"},
                "memory.facts_by_channel": {"customer_id": "C1"}, "memory.profile_versions": {"customer_id": "C1"},
                "memory.episode_add": {"customer_id": "Z", "episode": {}}, "memory.episodes_get": {"customer_id": "C1"},
                "memory.merge_customer": {"src_id": "A", "dst_id": "A"}, "memory.query_policy": {"query": "đổi trả"},
                "memory.identity_link_save": {"contact_hash": "h", "master_id": "m"}}
        for tool in sorted(set(args)):
            for caller in sorted(EVERYONE):
                expect = "allowed" if caller in core else "forbidden"
                self.assertEqual(self.status(tool, caller, **args[tool]), expect, f"{tool} <- {caller}")
        for tool in ("memory.drain_writes", "memory.abort_turn", "memory.identity_links_load"):
            for caller in sorted(EVERYONE - core):
                self.assertEqual(self.status(tool, caller), "forbidden", f"{tool} <- {caller}")
        for caller in sorted(EVERYONE - core):
            self.assertEqual(self.link.call("memory.open", {"enable_persistence": False}, caller)["error"], "forbidden")
            self.assertEqual(self.status("memory.close", caller), "forbidden")
        self.assertEqual(len(self.link.registry), 1)                                  # không kho nào được mở/đóng trái phép
        self.assertEqual(self.status("memory.admin_audit", CORE), "forbidden")        # kiểm toán chỉ cho bộ chạy đánh giá/test

    def test_high_level_caller_matrix(self):
        allowed = {"memory.get_call_brief": {BRIEF, ORCH}, "memory.search": {ORCH}, "memory.timeline": {UI, OPERATOR},
                   "memory.commit_turn": {ORCH}, "memory.commit_episode": {ORCH}, "memory.delete_customer": {OPERATOR}}
        args = {"memory.get_call_brief": {"customer_id": "C1"}, "memory.search": {"query": "đổi trả"}, "memory.timeline": {"customer_id": "C1"},
                "memory.commit_turn": {"ops": []}, "memory.commit_episode": {"customer_id": "Z", "episode": vars(episode(session="X"))},
                "memory.delete_customer": {"customer_id": "NOBODY"}}
        self.assertEqual(set(allowed), HIGH_TOOLS)
        for tool, who in allowed.items():
            for caller in sorted(EVERYONE):
                self.assertEqual(self.status(tool, caller, **args[tool]), "allowed" if caller in who else "forbidden", f"{tool} <- {caller}")

    def test_call_brief_and_ui_cannot_write_anything(self):
        m = self.admin.as_caller(BRIEF)
        self.assertEqual(m.get_profile_facts("C1"), {"product_advised": "SKU-AP-Y"})
        self.assertEqual(len(m.get_episodes("C1")), 1)
        ui = self.admin.as_caller(UI)
        self.assertEqual(len(ui.timeline("C1")["episodes"]), 1)
        for who in (m, ui):
            for write in (lambda: who.set_profile_fact("C1", "hack", 1), lambda: who.add_episode("C1", episode(session="X")),
                          lambda: who.set_working("S", intent="x"), lambda: who.delete_customer_data("C1"), lambda: who.merge_customer("C1", "C2"),
                          lambda: who.begin_turn("call_1#turn1"), lambda: who.drain_writes(), lambda: who.close()):
                with self.assertRaises(MemoryAccessDenied, msg=who.caller):
                    write()
        with self.assertRaises(MemoryAccessDenied):
            ui.get_profile_facts("C1")                                                # UI chỉ có timeline, không có get_call_brief
        self.assertEqual(self.admin.get_profile_facts("C1"), {"product_advised": "SKU-AP-Y"})        # không có gì bị ghi
        self.assertEqual(len(self.admin.get_episodes("C1")), 1)

    def test_orchestrator_cannot_delete_or_manage_stores_or_turns(self):
        m = self.admin.as_caller(ORCH)
        m.set_profile_fact("C1", "color", "den")                                      # ghi bộ nhớ cuộc gọi thì được
        for bad in (lambda: m.delete_customer_data("C1"), lambda: m.close(), lambda: m.begin_turn("call_1#turn1"), lambda: m.abort_turn(),
                    lambda: m.profile_versions("C1"), lambda: m._call("memory.identity_links_load")):
            with self.assertRaises(MemoryAccessDenied):
                bad()

    def test_only_operator_can_delete_and_other_customers_are_untouched(self):
        self.admin.set_profile_fact("C77", "color", "den")
        self.admin.add_episode("C77", episode(session="SESS-C77-1"))
        self.admin.set_profile_fact("C78", "color", "trang")
        self.admin.add_episode("C78", episode(session="SESS-C78-1"))
        for caller in (CORE, "TestHarness", "EvalRunner", ORCH, IDENT, BRIEF, UI, "SeedScript"):
            with self.assertRaises(MemoryAccessDenied, msg=caller):
                self.admin.as_caller(caller).delete_customer_data("C77")
        self.assertEqual(self.admin.get_profile_facts("C77"), {"color": "den"})
        self.admin.as_caller(OPERATOR).delete_customer_data("C77")
        self.assertEqual((self.admin.get_profile_facts("C77"), self.admin.get_episodes("C77")), ({}, []))
        self.assertEqual(self.admin.get_profile_facts("C78"), {"color": "trang"})              # khách khác không bị đụng
        self.assertEqual([e.session_id for e in self.admin.get_episodes("C78")], ["SESS-C78-1"])

    def test_unknown_or_missing_caller_denied_everywhere(self):
        for caller in ("Intruder", ""):
            for tool in sorted(EXPECTED_TOOLS - {"memory.open", "memory.admin_audit"}):
                self.assertEqual(self.status(tool, caller, **VALID_ARGS.get(tool, {})), "forbidden", f"{tool} <- {caller!r}")
            self.assertEqual(self.link.call("memory.open", {"enable_persistence": False}, caller)["error"], "forbidden")
        self.assertEqual(len(self.link.registry), 1)                                  # kho lạ không được mở

    def test_server_audit_has_no_arguments_and_records_denials(self):
        self.admin.set_profile_fact("C9", "recipient_phone", "0987654321")
        with self.assertRaises(MemoryAccessDenied):
            self.admin.as_caller(BRIEF).set_profile_fact("C9", "shipping_address", "12 Nguyễn Trãi, Hà Nội")
        audit = self.link.call("memory.admin_audit", {}, "TestHarness")["audit"]
        blob = json.dumps(audit, ensure_ascii=False)
        self.assertNotIn("0987654321", blob)
        self.assertNotIn("Nguyễn Trãi", blob)
        denied = [a for a in audit if a["caller"] == BRIEF and not a["ok"]]
        self.assertTrue(denied and denied[-1]["error"] == "forbidden" and denied[-1]["tool"] == "memory.commit_turn")
        self.assertEqual(self.link.call("memory.admin_audit", {}, BRIEF)["error"], "forbidden")


class SingleWriterTest(unittest.TestCase):
    """Một file DB chỉ có MỘT người ghi (MemoryService trong server); giao dịch theo lượt nằm trong server."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.db = os.path.join(self.dir, "mem.db")
        self.link = MemoryLink("inproc")
        self.addCleanup(self.link.close)

    def remote(self, caller="TestHarness"):
        return RemoteMemoryService(enable_persistence=True, db_path=self.db, transport="inproc", link=self.link, caller=caller)

    def test_two_clients_on_the_same_db_share_one_writer(self):
        a, b = self.remote(), self.remote("HarnessCore")
        self.assertEqual(a.store_id, b.store_id)
        self.assertEqual(len(self.link.registry), 1)
        svc = self.link.registry.get(a.store_id)
        self.assertIs(svc, self.link.registry.get(b.store_id))
        a.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        a.set_profile_fact("C1", "color", "đen")
        a.drain_writes()
        self.assertEqual(b.as_caller(ORCH).get_profile_facts("C1"), {"color": "đen"})  # không có bản cache lệch giữa hai "người ghi"
        b.close()
        self.assertEqual(len(self.link.registry), 1)                                   # còn một tham chiếu: DB vẫn mở
        a.set_profile_fact("C1", "size", "39")
        a.close()
        self.assertEqual(len(self.link.registry), 0)

    def test_client_never_touches_the_db_file(self):
        m = self.remote()
        self.assertFalse(hasattr(m, "profile") or hasattr(m, "working") or hasattr(m, "episodic"))   # không có tầng lưu trữ cục bộ nào để ghi
        self.assertIsInstance(m.backend, RemoteBackend)
        m.begin_turn("call_1#turn1")
        m.set_profile_fact("C1", "color", "đen")
        m.drain_writes()
        m.close()
        con = sqlite3.connect(self.db)
        self.addCleanup(con.close)
        self.assertEqual(con.execute("select count(*) from customer_profiles").fetchone()[0], 1)

    def test_turn_commit_and_rollback_live_in_the_server(self):
        core = self.remote("HarnessCore")
        orch = core.as_caller(ORCH)
        core.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        orch.set_profile_fact("C1", "color", "đen")
        orch.drain_writes()                                                           # orchestrator.commit_turn: chốt
        core.begin_turn("call_1#turn2", call_date="2026-10-15", channel="hotline")
        orch.set_profile_fact("C1", "size", "39")
        orch.add_episode("C1", episode())
        core.abort_turn()                                                             # lõi hủy các ghi DB của lượt 2
        core.close()
        con = sqlite3.connect(self.db)
        self.addCleanup(con.close)
        self.assertEqual([r[0] for r in con.execute("select key from customer_profiles")], ["color"])
        self.assertEqual(con.execute("select count(*) from episodic_records").fetchone()[0], 0)

    def test_data_survives_reopen_and_wal_is_checkpointed_on_close(self):
        core = self.remote("HarnessCore")
        orch = core.as_caller(ORCH)
        core.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        orch.set_profile_fact("C1", "product_advised", "SKU-AP-Y")
        orch.add_episode("C1", episode())
        orch.drain_writes()
        core.close()
        wal = self.db + "-wal"
        self.assertFalse(os.path.exists(wal) and os.path.getsize(wal) > 0)            # chỉ copy file .db vẫn đủ dữ liệu
        again = self.remote()
        self.assertEqual(again.get_profile_facts("C1"), {"product_advised": "SKU-AP-Y"})
        self.assertEqual([e.session_id for e in again.get_episodes("C1")], ["SESS-C1-2026-10-15"])

    def test_delete_customer_removes_every_table_and_runs_listeners(self):
        m = self.remote()
        m.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        m.set_profile_fact("C1", "shipping_address", "12 Nguyễn Trãi")
        m.add_episode("C1", episode())
        m.set_working("SESS-C1-2026-10-15", messages_in_session=[{"role": "user", "content": "0987654321"}])
        m.drain_writes()
        seen = []
        m.register_delete_listener(seen.append)
        m.as_caller(OPERATOR).delete_customer_data("C1")
        self.assertEqual(seen, ["C1"])
        m.close()
        con = sqlite3.connect(self.db)
        self.addCleanup(con.close)
        for table in ("customer_profiles", "episodic_records", "working_sessions"):
            n = con.execute(f"select count(*) from {table}").fetchone()[0]
            self.assertEqual(n, 0, table)


class StdioProcessTest(unittest.TestCase):
    """Đường chạy thật: mcp-memory là TIẾN TRÌNH RIÊNG; chỉ tiến trình đó mở file DB."""

    @classmethod
    def setUpClass(cls):
        cls.link = MemoryLink("stdio", timeout_s=90)
        cls.dir = tempfile.mkdtemp()
        cls.db = os.path.join(cls.dir, "stdio.db")

    @classmethod
    def tearDownClass(cls):
        cls.link.close()
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_server_is_a_separate_process_and_results_match_local(self):
        base = RemoteMemoryService(enable_persistence=False, transport="stdio", link=self.link, caller="TestHarness")
        try:
            remote = script(base.as_caller(ORCH), core=base, operator=base.as_caller(OPERATOR))
            self.assertEqual(remote, script(MemoryService(enable_persistence=False)))
            pid = self.link.call("memory.admin_audit", {}, "TestHarness")["pid"]
            self.assertNotEqual(pid, os.getpid())
        finally:
            base.close()

    def test_persistent_store_written_only_by_the_server_process(self):
        m = RemoteMemoryService(enable_persistence=True, db_path=self.db, transport="stdio", link=self.link, caller=CORE)
        orch = m.as_caller(ORCH)
        m.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
        orch.set_profile_fact("C1", "color", "đen")
        orch.drain_writes()
        m.close()
        con = sqlite3.connect(self.db)
        try:
            self.assertEqual(con.execute("select value from customer_profiles where key='color'").fetchone()[0], json.dumps("đen", ensure_ascii=False))
        finally:
            con.close()

    def test_forbidden_is_enforced_in_the_server_process(self):
        m = RemoteMemoryService(enable_persistence=False, transport="stdio", link=self.link, caller="TestHarness")
        try:
            with self.assertRaises(MemoryAccessDenied):
                m.as_caller(BRIEF).set_profile_fact("C1", "x", 1)
            with self.assertRaises(MemoryAccessDenied):
                m.as_caller(ORCH).delete_customer_data("C1")
        finally:
            m.close()

    def test_closing_the_link_stops_the_server_process(self):
        link = MemoryLink("stdio", timeout_s=90)
        link.close()
        self.assertEqual(link.call("memory.admin_audit", {}, "TestHarness")["error"], "link_closed")


class RunnerOverMemoryMCPTest(unittest.TestCase):
    """Chạy kịch bản BTC thật qua ScenarioRunner với bộ nhớ qua MCP: trace giống hệt bộ nhớ cục bộ (nhánh không-LLM, tất định)."""

    def _run(self, transport, only=("SAMPLE-01", "SAMPLE-04"), config="full"):
        from unittest import mock
        from src.eval.runner import ScenarioRunner
        from tests._helpers import PUBLIC_DIR
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "t.jsonl")
        with mock.patch.dict(os.environ, {"MEMORY_TRANSPORT": transport}):
            ScenarioRunner(PUBLIC_DIR).run_all(config=config, output_trace_file=out, only=list(only))
        with open(out, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        for r in rows:
            r.pop("latency", None)
        return rows

    def test_trace_identical_between_local_and_inproc_memory(self):
        local, remote = self._run("local"), self._run("inproc")
        self.assertEqual(len(local), len(remote))
        for a, b in zip(local, remote):
            for key in ("scenario_id", "call", "turn", "agent_text", "memory_writes", "facts_used", "claims", "questions"):
                self.assertEqual(a.get(key), b.get(key), f"{a['scenario_id']} {a['call']}#{a['turn']} {key}")
            self.assertEqual(a.get("_brief_facts"), b.get("_brief_facts"))
            self.assertEqual(a.get("_brief_must_carry_over"), b.get("_brief_must_carry_over"))

    def test_components_stay_inside_their_permissions_while_running_real_scenarios(self):
        """Chạy thật runner: không có lời gọi nào bị từ chối; mỗi thành phần chỉ dùng đúng tool của nó."""
        from src.memory.remote import shared_link
        self._run("inproc", only=("SAMPLE-01", "SAMPLE-04", "SAMPLE-06"))
        audit = shared_link("inproc").server_guard.audit
        self.assertTrue(audit)
        self.assertEqual([a for a in audit if a["error"] == "forbidden"], [])
        used = {}
        for a in audit:
            used.setdefault(a["caller"], set()).add(a["tool"])
        self.assertLessEqual(used[ORCH], {"memory.get_call_brief", "memory.search", "memory.commit_turn", "memory.commit_episode"})
        self.assertLessEqual(used[BRIEF], {"memory.get_call_brief"})
        self.assertIn("memory.commit_turn", used[ORCH])
        self.assertIn("memory.commit_episode", used[ORCH])
        self.assertLessEqual(used["EvalRunner"], {"memory.open", "memory.close", "memory.begin_turn", "memory.profile_set", "memory.episode_add",
                                                   "memory.profile_get", "memory.working_get"})
        self.assertNotIn(IDENT, used)                                                  # ghi bối cảnh định danh đi qua view HarnessOrchestrator

    def test_every_scenario_stack_releases_its_server_store(self):
        from unittest import mock
        from src.eval.runner import ScenarioRunner
        from src.memory.remote import shared_link
        from tests._helpers import PUBLIC_DIR
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        with mock.patch.dict(os.environ, {"MEMORY_TRANSPORT": "inproc"}):
            link = shared_link("inproc")
            before = len(link.registry)
            ScenarioRunner(PUBLIC_DIR).run_all(config="baseline_no_memory", output_trace_file=os.path.join(d, "b.jsonl"), only=["SAMPLE-01"])
        self.assertEqual(len(link.registry), before)                                  # baseline tạo kho mới mỗi call mà không để rò


if __name__ == "__main__":
    unittest.main()
