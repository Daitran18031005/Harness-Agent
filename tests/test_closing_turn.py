"""Lượt chốt của cuộc gọi (luật chấm BTC 11/2026): sau lượt khách cuối, agent được một lượt không có lời khách để đọc lại đơn và gọi order.create."""
import unittest
from tests.test_basket_sync import OrderSyncTest, ON, AP_Y

RUN2 = "SKU-SN-RUN2"          # sản phẩm có biến thể size/màu


class ClosingTurnTest(unittest.TestCase):
    _setup, _run, _mock, _create = OrderSyncTest._setup, OrderSyncTest._run, staticmethod(OrderSyncTest._mock), staticmethod(OrderSyncTest._create)

    def _close(self, phone="0911265844", orders_now=True):
        t = self.c["normalizer"].normalize("", self._channel(), phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), ON)
        self.orch.llm_client.complete_json = lambda msgs: ({"orders_now": orders_now, "quote": "lên đơn cho anh" if orders_now else ""}, {})   # chốt độc lập của lượt chốt
        return b, (lambda: self.orch.process_turn(t, b, current_date=ON, closing=True))

    @staticmethod
    def _channel():
        from src.channels.normalizer import InputChannel
        return InputChannel.HOTLINE

    def test_open_draft_is_created_with_cod_default(self):
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])              # gate hỏi địa chỉ/thanh toán, chưa tạo đơn
        m = self._mock()
        self.assertEqual(len(m._ORDERS), 0)
        b, close = self._close()
        self.assertTrue(self.orch.has_open_order(b.customer_id, ON))
        reply, tc, _ = close()
        oc = [c for c in tc if c["name"] == "order.create"]
        self.assertEqual((oc[0]["args"]["sku"], oc[0]["args"]["price_vnd"], oc[0]["args"]["payment"]), (AP_Y, 5200000, "COD"))
        self.assertEqual(oc[0]["result"]["status"], "created")
        self.assertEqual(len(m._ORDERS), 1)
        self.assertIn("đọc lại đơn", reply)
        self.assertIn("một sản phẩm", reply)                           # A2: đọc cả giá một sản phẩm, SĐT
        self.assertIn("số điện thoại", reply)
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))  # không chốt lần hai

    def test_no_closing_order_after_handoff(self):
        """A1: đã chuyển máy thành công thì lượt chốt không tạo đơn."""
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])
        b, close = self._close()
        sid = f"SESS-{b.customer_id}-{ON}"
        self.orch._call_log.setdefault(sid, []).append({"name": "handoff.transfer", "args": {}, "result": {"ticket_id": "T-1"}})
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))
        _, tc, _ = close()
        self.assertFalse([c for c in tc if c["name"] == "order.create"])

    def test_unknown_sku_is_not_read_back(self):
        """A3: SKU tự đặt → không đọc lại mã thô, không tạo đơn."""
        self._setup(order_gate=True)
        self._run([self._create("SPECTRA-S1", 1, payment=None)])
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse(self.orch.has_open_order(self._close()[0].customer_id, ON))

    def test_independent_check_blocks_when_customer_did_not_order(self):
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])
        _, close = self._close(orders_now=False)                       # "khoan chốt vội": chốt độc lập không thấy yêu cầu đặt đơn
        reply, tc, _ = close()
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse([c for c in tc if c["name"] == "order.create"])
        self.assertNotIn("?", reply)

    def test_callback_in_the_past_rolls_to_next_occurrence(self):
        from src.harness.orchestrator import HarnessOrchestrator as H
        f = lambda at: H._future_callback({"callback_at": at}, "2026-10-15")["callback_at"]
        self.assertEqual(f("2026-01-01T09:00:00"), "2027-01-01T09:00:00")     # "Tết Dương lịch 01/01" nói ngày 15/10 → năm sau
        self.assertEqual(f("2025-12-20T09:00"), "2026-12-20T09:00")
        self.assertEqual(f("2026-10-27T09:00:00"), "2026-10-27T09:00:00")     # tương lai: giữ nguyên

    def test_second_call_on_the_same_day_sees_the_first_one(self):
        """Hai cuộc cùng khách CÙNG NGÀY: cuộc đầu đã kết thúc phải được tính là cuộc trước (không bị coi là cuộc hiện tại, không bị cuộc sau ghi đè)."""
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        t = self.c["normalizer"].normalize("alo", self._channel(), "0911265844")
        ident = self.c["resolver"].resolve(t, memory=self.c["memory"])
        self.orch.finalize_call(ident.customer_id, ON, "call_1", "hotline")
        b = self.c["brief"].build(ident, ON)
        self.assertEqual((b.previous_calls_count, b.product_advised), (1, AP_Y))
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])                # cuộc thứ hai, cùng ngày
        self.orch.finalize_call(ident.customer_id, ON, "call_2", "hotline", trigger="handoff", clear=False)
        self.orch.finalize_call(ident.customer_id, ON, "call_2", "hotline")
        ids = [e.session_id for e in self.c["memory"].get_episodes(ident.customer_id)]
        self.assertEqual([i.split("#")[1] for i in ids], ["1", "2"])                 # hai cuộc, mỗi cuộc đếm một lần (episode giữa cuộc bị ẩn)

    def test_speculative_quote_is_remembered_only_when_the_agent_used_it(self):
        """Báo giá do code CHẠY TRƯỚC (đoán) không được thành "sản phẩm đã tư vấn" nếu agent không nói tới nó (từng ghi nhầm ghế ô tô cho khách hỏi máy lọc)."""
        self._setup()
        guess = {"name": "pricing.get_quote", "args": {"sku": "SKU-MB-CAR"}, "result": {"sku": "SKU-MB-CAR", "final_price_vnd": 4990000, "applied_promos": []}, "speculative": True}
        mem = self.c["memory"]
        self.orch._persist_tool_grounded_facts("C-SPEC", [guess], "Dạ nhà mình có bé nhỏ thì em gợi ý máy có khóa trẻ em ạ.")
        self.assertNotIn("product_advised", mem.get_profile_facts("C-SPEC"))
        self.orch._persist_tool_grounded_facts("C-SPEC", [guess], "Dạ ghế đó giá 4.990.000đ ạ.")
        self.assertEqual(mem.get_profile_facts("C-SPEC").get("product_advised"), "SKU-MB-CAR")

    def test_speculative_targets_need_the_real_product_name(self):
        self._setup()
        t = self.c["normalizer"].normalize("alo", self._channel(), "0911265844")
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), ON)
        from src.privacy.pii_vault import PiiVault
        look = lambda text: {c["args"]["sku"] for c in self.orch._speculative_lookups(text, None, [], None, b, None, ON, PiiVault())}
        self.assertEqual(look("Nhà chị có bé nhỏ, ngân sách tầm 5.000.000 thôi em."), set())          # "có bé" không phải tên sản phẩm
        self.assertEqual(look("Em ơi Máy lọc không khí AirPure X bên em giá bao nhiêu?"), {"SKU-AP-X"})

    def test_no_draft_means_no_closing_turn(self):
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        b, _ = self._close()
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))

    def test_unknown_variant_is_not_ordered(self):
        self._setup(order_gate=True)
        self._run([self._create(RUN2, 1, payment="COD")])             # khách chưa chọn size/màu
        _, close = self._close()
        reply, tc, _ = close()
        self.assertNotIn("?", reply)                                   # không còn ai trả lời: không hỏi
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse([c for c in tc if c["name"] == "order.create"])

    def test_focus_product_keeps_shortlist_top_from_being_main_price(self):
        from src.harness.extractor import extract_claims
        calls = [{"name": "product.shortlist", "args": {}, "result": {"items": [{"sku": "SKU-SS-AX40", "name": "Máy lọc không khí Samsung AX40", "list_price_vnd": 6490000}]}}]
        text = "Ngoài ra còn Máy lọc không khí Samsung AX40 - Giá: 6.490.000 VNĐ."
        self.assertEqual([c["field"] for c in extract_claims(text, calls)], ["price_vnd"])                       # chưa bàn gì: đầu shortlist là chủ đề
        self.assertEqual([c["field"] for c in extract_claims(text, calls, focus_sku="SKU-XM-4P")], ["alt_price_vnd"])


del OrderSyncTest       # không để unittest nạp lại các test của lớp đó từ file này

if __name__ == "__main__":
    unittest.main()


class InventedSkuRepairTest(unittest.TestCase):
    _setup, _run, _mock, _create = ClosingTurnTest._setup, ClosingTurnTest._run, ClosingTurnTest._mock, ClosingTurnTest.__dict__["_create"]

    def test_invented_code_maps_to_last_looked_up_simple_product(self):          # A3: sửa trước rồi mới chặn
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        self._run([self._create("MADE-UP-1", 1, payment=None)])
        self.assertTrue(all(a.get("sku") == AP_Y for a in self.orch._gate_retry_args.values()))
        self.assertTrue(self.orch._gate_retry_args)                                # đơn nháp mở với SKU thật, không bị chặn


class NamedProductTest(unittest.TestCase):
    def test_accessory_name_is_not_read_as_the_main_unit(self):                 # TEST-200
        from types import SimpleNamespace
        from src.harness.orchestrator import HarnessOrchestrator as H
        o = H.__new__(H)
        names = {"SKU-AP-X": "Máy lọc không khí AirPure X", "SKU-AP-FLT-X": "Màng lọc thay thế AirPure X/Y"}
        o._call_log = {"S": [{"name": "catalog.search", "args": {}, "result": {"items": [{"sku": "SKU-AP-X"}, {"sku": "SKU-AP-FLT-X"}]}}]}
        o._product_info = lambda s: {"name": names.get(s, "")}
        o._parent_sku = lambda s: s
        self.assertEqual(o._named_in_call("S", "giao Màng lọc thay thế AirPure X/Y tới Cần Thơ"), "SKU-AP-FLT-X")
        self.assertIsNone(o._named_in_call("S", "giao cái máy hôm trước"))


class MovedCallbackTest(unittest.TestCase):
    def test_moved_callback_date_is_told(self):                                  # TEST-29
        from src.harness.orchestrator import HarnessOrchestrator as H
        calls = [{"name": "schedule.callback", "result": {"callback_at": "2026-10-27T08:00", "moved_from": "2026-10-26T08:00:00"}}]
        t = H._say_moved_callback("Dạ em đã ghi nhận lịch gọi lại thứ 2 ngày 26/10 ạ.", calls)
        self.assertIn("27/10", t)
        self.assertIn("nghỉ", t)
        self.assertEqual(H._say_moved_callback("Dạ em hẹn 8:00 ngày 27/10 ạ.", calls), "Dạ em hẹn 8:00 ngày 27/10 ạ.")
