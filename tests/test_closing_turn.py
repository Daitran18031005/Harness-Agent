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
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))  # không chốt lần hai

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
