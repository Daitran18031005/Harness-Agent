"""Bước 17 — backend FastAPI (api/): phiên, call_name/turn_num do API cấp, hai phiên đồng thời không lẫn dữ liệu, không lộ PII, mọi endpoint.
Pipeline thật (bộ nhớ cục bộ + DB tạm, cổng MCP cùng tiến trình), KHÔNG có LLM (OPENAI_API_KEY rỗng) — không gọi mạng."""
import json
import threading
import unittest
from unittest import mock

from tests._helpers import advisor_suggests
from tests import _helpers  # noqa: F401  (đặt OPENAI_API_KEY="" trước khi import phần còn lại)
from tests.test_pipeline_lifecycle import make_pipeline

from fastapi.testclient import TestClient

from api.app import create_app
from api.scrub import MASK, scrub

LAN, HUNG = "0901111111", "0902222222"
DATE = "2026-10-15"


class ApiCase(unittest.TestCase):
    def setUp(self):
        self.pipeline = make_pipeline(self)
        self.client = TestClient(create_app(self.pipeline))

    def chat(self, message, **kw):
        r = self.client.post("/chat", json={"message": message, "call_date": DATE, **kw})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def open_session(self, phone, channel="hotline"):
        r = self.client.post("/sessions", json={"contact_id": phone, "channel": channel, "call_date": DATE})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["session_id"]

    def get(self, path, sid, **params):
        r = self.client.get(path, params={"session_id": sid, **params})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class SessionAndCounterTest(ApiCase):
    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual((r.status_code, r.json()), (200, {"status": "ok", "llm": False, "spent_vnd": 0.0, "cap_vnd": None}))

    def test_call_name_and_turn_num_are_assigned_by_the_api(self):
        """UI cũ gửi call_1 cố định và turn_num = số tin nhắn (cả tin của agent). API: mỗi lượt khách +1, mỗi phiên mới của cùng liên hệ → call_2."""
        sid = self.open_session(LAN)
        first, second = self.chat("Chị tên Lan, hỏi máy lọc không khí cho phòng 20m2", session_id=sid), self.chat("giá bao nhiêu em", session_id=sid)
        self.assertEqual((first["call_name"], first["turn_num"], second["turn_num"]), ("call_1", 1, 2))
        self.assertEqual(second["trace"]["call"], "call_1")
        self.assertEqual(second["trace"]["turn"], 2)

        sid2 = self.open_session(LAN)                                   # cuộc gọi thứ hai của cùng khách
        again = self.chat("alo chị Lan đây", session_id=sid2)
        self.assertEqual((again["call_name"], again["turn_num"]), ("call_2", 1))
        self.assertTrue(self.client.get(f"/sessions/{sid}").json()["ended"])    # mở phiên mới chốt phiên cũ
        r = self.client.post("/chat", json={"session_id": sid, "message": "alo"})
        self.assertEqual(r.status_code, 409)

    def test_chat_without_session_id_opens_one(self):
        out = self.chat("Chị tên Lan, hỏi máy lọc không khí", contact_id=LAN)
        self.assertEqual((out["call_name"], out["turn_num"]), ("call_1", 1))
        info = self.client.get(f"/sessions/{out['session_id']}").json()
        self.assertEqual((info["turn_num"], info["ended"], info["channel"]), (1, False, "hotline"))

    def test_anonymous_sessions_do_not_share_a_customer(self):
        a, b = self.chat("Chị tên Lan, hỏi máy lọc không khí"), self.chat("Anh tên Hùng, hỏi máy lọc không khí")
        self.assertNotEqual(a["customer_id"], b["customer_id"])
        self.assertNotEqual(a["session_id"], b["session_id"])

    def test_validation_and_unknown_session(self):
        self.assertEqual(self.client.get("/call-brief", params={"session_id": "nope"}).status_code, 404)
        self.assertEqual(self.client.post("/chat", json={"session_id": "nope", "message": "alo"}).status_code, 404)
        self.assertEqual(self.client.post("/sessions", json={"channel": "telegram"}).status_code, 422)
        self.assertEqual(self.client.post("/sessions", json={"call_date": "2026-15-10"}).status_code, 422)
        self.assertEqual(self.client.post("/chat", json={"message": ""}).status_code, 422)

    def test_failed_turn_returns_500_without_pii_and_does_not_advance_the_counter(self):
        sid = self.open_session(LAN)
        real = self.pipeline.handle_incoming_request
        with mock.patch.object(self.pipeline, "handle_incoming_request", side_effect=ValueError(f"boom {LAN}")):
            r = self.client.post("/chat", json={"session_id": sid, "message": "alo"})
        self.assertEqual(r.status_code, 500)
        self.assertNotIn(LAN, r.text)
        with mock.patch.object(self.pipeline, "handle_incoming_request", side_effect=real):
            self.assertEqual(self.chat("alo", session_id=sid)["turn_num"], 1)

    def test_end_session(self):
        sid = self.chat("Chị tên Lan, hỏi máy lọc không khí cho phòng 20m2", contact_id=LAN)["session_id"]
        first = self.client.post(f"/sessions/{sid}/end").json()
        self.assertTrue(first["finalized"])
        self.assertTrue(all(set(w) == {"key", "op", "source"} for w in first["memory_writes"]))   # chỉ khóa, không giá trị
        second = self.client.post(f"/sessions/{sid}/end").json()
        self.assertEqual((second["finalized"], second["reason"]), (False, "phiên đã kết thúc"))


class TwoSessionsTest(ApiCase):
    def test_two_concurrent_sessions_never_mix_name_cart_or_memory(self):
        sid_a, sid_b = self.open_session(LAN), self.open_session(HUNG)
        script = {sid_a: ["Chị tên Lan, chị hỏi máy lọc không khí cho phòng 20m2", "giá cao quá để chị hỏi chồng đã", "chị hỏi thêm về bảo hành"],
                  sid_b: ["Anh tên Hùng, anh hỏi giày chạy bộ size 42", "anh thích màu đen", "anh hỏi thêm về đổi trả"]}
        barrier, errors = threading.Barrier(2), []

        def run(sid):
            try:
                barrier.wait()
                for i, msg in enumerate(script[sid], 1):
                    out = self.chat(msg, session_id=sid)
                    self.assertEqual(out["turn_num"], i)
            except BaseException as e:                                  # noqa: BLE001 — đưa lỗi của luồng về luồng test
                errors.append(e)

        threads = [threading.Thread(target=run, args=(s,)) for s in script]
        [t.start() for t in threads]
        [t.join(timeout=120) for t in threads]
        self.assertEqual(errors, [])

        brief_a, brief_b = (self.get("/call-brief", s)["call_brief"] for s in (sid_a, sid_b))
        self.assertEqual((brief_a["customer_name"], brief_b["customer_name"]), ("Lan", "Hùng"))
        self.assertEqual((brief_a["honorific"], brief_b["honorific"]), ("chị", "anh"))
        tl_a, tl_b = self.get("/memory/timeline", sid_a), self.get("/memory/timeline", sid_b)
        self.assertNotEqual(tl_a["customer_id"], tl_b["customer_id"])
        names = lambda tl: [f["value"] for f in tl["versions"]["customer_name"]]   # noqa: E731
        self.assertEqual((names(tl_a), names(tl_b)), (["Lan"], ["Hùng"]))
        self.assertNotIn("size", tl_a["versions"])                                   # fact của khách B không nằm ở A
        self.assertNotIn("room_area_m2", tl_b["versions"])
        for tl, other in ((tl_a, "Hùng"), (tl_b, "Lan")):
            self.assertNotIn(other, json.dumps(tl, ensure_ascii=False))
        # nhật ký tool: mỗi phiên chỉ giữ lời gọi của lượt MÌNH, không trùng call_id, và hợp lại nằm trong nhật ký của cổng
        log_a, log_b = (self.get("/tools/log", s)["entries"] for s in (sid_a, sid_b))
        ids_a, ids_b = {e["call_id"] for e in log_a}, {e["call_id"] for e in log_b}
        self.assertTrue(ids_a and ids_b)
        self.assertFalse(ids_a & ids_b)
        self.assertLessEqual(ids_a | ids_b, {a["call_id"] for a in self.pipeline.mcp_gateway.audit_log})
        # mỗi lượt của phiên mình có đúng call_name của mình trong provenance bộ nhớ
        for tl in (tl_a, tl_b):
            self.assertEqual({f["source_call"] for fs in tl["versions"].values() for f in fs}, {"call_1"})


class NoPiiTest(ApiCase):
    def test_no_raw_phone_or_address_in_any_json_endpoint(self):
        address = "12 Nguyễn Trãi, Quận 5"
        out = self.chat(f"Chị tên Lan, số chị {LAN}, địa chỉ: {address}, chị hỏi máy lọc không khí cho phòng 20m2", contact_id=LAN)
        sid = out["session_id"]
        for path in ("/call-brief", "/memory/timeline", "/tools/log", "/orders"):
            body = self.client.get(path, params={"session_id": sid}).text
            self.assertNotIn(LAN, body, path)
            self.assertNotIn("Nguyễn Trãi", body, path)
        trace = json.dumps(out["trace"], ensure_ascii=False)
        self.assertNotIn(LAN, trace)
        self.assertNotIn("Nguyễn Trãi", trace)
        self.assertNotIn("customer_text", out["trace"])                              # trace rút gọn: không có lời khách/agent
        self.assertNotIn("agent_text", out["trace"])
        self.assertTrue(all(set(c) == {"tool", "error"} for c in out["trace"]["tool_calls"]))

    def test_scrub(self):
        self.assertEqual(scrub({"customer_phone": LAN, "note": f"gọi {LAN} nhé", "order_id": "OD123456", "price": 5200000, "n": None, "ok": True,
                                "shipping_address": "12 Nguyễn Trãi", "items": [{"phone": 901111111}]}),
                         {"customer_phone": MASK, "note": f"gọi {MASK} nhé", "order_id": "OD123456", "price": 5200000, "n": None, "ok": True,
                          "shipping_address": MASK, "items": [{"phone": MASK}]})
        self.assertEqual(scrub({"key": "address", "value": "12 Nguyễn Trãi", "superseded": False}), {"key": "address", "value": MASK, "superseded": False})
        self.assertEqual(scrub({"key": "size", "value": "42"}), {"key": "size", "value": "42"})


class OrdersAndToolLogTest(ApiCase):
    def test_orders_come_from_the_session_tool_log_only(self):
        sid_a, sid_b = self.open_session(LAN), self.open_session(HUNG)
        real = self.pipeline.handle_incoming_request

        def with_order(*args, **kwargs):                                 # mô phỏng lõi tạo đơn trong lượt (không có LLM nên không tự đặt đơn được)
            self.pipeline.mcp_gateway.execute_tool("order.create", {"customer_phone": LAN, "sku": "SKU-AP-Y", "qty": 1, "address": "12 Nguyễn Trãi",
                                                                   "payment": "COD", "on": DATE}, caller="HarnessOrchestrator")
            return real(*args, **kwargs)

        self.assertEqual(self.get("/orders", sid_a), {"session_id": sid_a, "orders": [], "latest": None})
        with mock.patch.object(self.pipeline, "handle_incoming_request", side_effect=with_order):
            self.chat("Chị tên Lan, hỏi máy lọc không khí", session_id=sid_a)
        orders = self.get("/orders", sid_a)
        self.assertEqual([o["tool"] for o in orders["orders"]], ["order.create"])
        self.assertEqual(orders["latest"], orders["orders"][-1])
        self.assertEqual(orders["latest"]["args"]["customer_phone"], MASK)
        self.assertEqual(orders["latest"]["args"]["address"], MASK)
        self.assertTrue(orders["latest"]["result"].get("order_id"))
        self.chat("Anh tên Hùng, hỏi máy lọc không khí", session_id=sid_b)
        self.assertEqual(self.get("/orders", sid_b)["orders"], [])       # đơn của phiên A không hiện ở phiên B

    def test_tools_log_limit_returns_the_latest_entries(self):
        advisor_suggests(self)
        sid = self.open_session(LAN)
        self.chat("Chị tên Lan, hỏi máy lọc không khí cho phòng 20m2", session_id=sid)
        full = self.get("/tools/log", sid)["entries"]
        self.assertGreaterEqual(len(full), 2)
        self.assertEqual(self.get("/tools/log", sid, limit=1)["entries"], full[-1:])
        self.assertTrue(all({"call_id", "tool", "caller", "args", "duration_ms"} <= set(e) for e in full))
        self.assertEqual(self.client.get("/tools/log", params={"session_id": sid, "limit": 0}).status_code, 422)


class BudgetTest(ApiCase):
    def test_health_reports_spend_and_cap(self):
        h = self.client.get("/health").json()
        self.assertIn("spent_vnd", h)
        self.assertIn("cap_vnd", h)

    def test_budget_cap_returns_402_not_a_crash(self):
        from src.llm.cost_tracker import BudgetExceeded
        sid = self.open_session(LAN)
        with mock.patch.object(self.pipeline, "handle_incoming_request", side_effect=BudgetExceeded(600, 500)):
            r = self.client.post("/chat", json={"message": "alo", "session_id": sid, "call_date": DATE})
        self.assertEqual(r.status_code, 402)
        self.assertEqual(self.client.get("/sessions/" + sid).json()["turn_num"], 0)   # lượt không được tính


class UiTest(ApiCase):
    """Giao diện bước 18 do chính API phục vụ (cùng origin, không cần CORS)."""
    def test_root_redirects_to_the_ui_and_the_page_loads(self):
        r = self.client.get("/", follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (307, "/ui/"))
        page = self.client.get("/ui/")
        self.assertEqual(page.status_code, 200)
        for needle in ("Harness Agent", "Call Brief", "Dòng thời gian bộ nhớ", "/call-brief", "/memory/timeline", "/asr", "/chat", "/sessions"):
            self.assertIn(needle, page.text)

    def test_page_never_writes_server_text_with_innerhtml(self):
        self.assertNotIn("innerHTML", self.client.get("/ui/").text)


class ASRTest(ApiCase):
    def upload(self, name="a.wav", data=b"RIFFxxxx"):
        return self.client.post("/asr", files={"file": (name, data, "audio/wav")})

    def test_missing_model_is_a_clear_error_and_nothing_is_transcribed(self):
        with mock.patch("src.channels.offline_asr.is_available", return_value=False), \
                mock.patch("src.channels.offline_asr.transcribe_audio") as transcribe:
            r = self.upload()
        self.assertEqual(r.status_code, 503)
        self.assertIn("không tự tải model", r.json()["detail"])
        transcribe.assert_not_called()

    def test_transcribes_and_removes_the_temp_file(self):
        seen = {}

        def fake(path):
            import os
            seen["path"], seen["exists"] = path, os.path.exists(path)
            return "chị muốn mua máy lọc không khí"

        with mock.patch("src.channels.offline_asr.is_available", return_value=True), mock.patch("src.channels.offline_asr.transcribe_audio", side_effect=fake):
            r = self.upload("goi.mp3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "chị muốn mua máy lọc không khí")
        self.assertTrue(seen["exists"] and seen["path"].endswith(".mp3"))
        import os
        self.assertFalse(os.path.exists(seen["path"]))

    def test_rejects_other_types_empty_transcripts_and_big_files(self):
        self.assertEqual(self.upload("a.txt").status_code, 415)
        with mock.patch("src.channels.offline_asr.is_available", return_value=True), mock.patch("src.channels.offline_asr.transcribe_audio", return_value=""):
            self.assertEqual(self.upload().status_code, 422)
        with mock.patch("api.routes.ASR_MAX_BYTES", 4):
            self.assertEqual(self.upload().status_code, 413)


class LifespanTest(unittest.TestCase):
    def test_app_builds_and_closes_its_own_pipeline(self):
        stub = mock.MagicMock()
        stub.llm_client.available = False
        with mock.patch("api.app._build_pipeline", return_value=stub):
            with TestClient(create_app()) as client:
                self.assertEqual(client.get("/health").json()["status"], "ok")
            stub.close.assert_called_once()

    def test_injected_pipeline_is_not_closed_by_the_app(self):
        stub = mock.MagicMock()
        stub.llm_client.available = False
        with TestClient(create_app(stub)) as client:
            client.get("/health")
        stub.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
