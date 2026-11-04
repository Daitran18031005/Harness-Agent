"""Giá báo == giá đơn khi mua nhiều máy (KM 'máy thứ 2'): `price_basket`, chốt trước order.create, hạn mức COD trên tổng đúng của giỏ.
Mọi con số đối chiếu với mock_tools.py của BTC ngày 2026-10-15 (AirPure Pro: AIR-OCT −300.000 máy 1, AIR-2ND-50 −50% máy 2)."""
import unittest
from tests._helpers import build_components
from tests.test_orchestrator import FakeLLM
from src.channels.normalizer import InputChannel
from src.harness.basket import price_basket, cod_exceeds, cod_needs_confirmation, replace_amount, correct_basket_totals

ON = "2026-10-15"
PRO, AP_X, AP_Y, SHOE, RUN2 = "SKU-AP-PRO", "SKU-AP-X", "SKU-AP-Y", "SKU-SN-CAS-39-DEN", "SKU-SN-RUN2-40-DEN"


def mock_quote(args):
    import mock_tools
    a = {k: v for k, v in args.items() if k in ("sku", "on", "qty", "customer_phone", "address", "basket_skus")}
    return mock_tools.pricing_get_quote(**a)


def basket(*lines):
    return price_basket(mock_quote, [{"sku": s, "qty": q} for s, q in lines], ON)


class PriceBasketTest(unittest.TestCase):
    def setUp(self):
        build_components()                     # reset trạng thái mock

    def test_two_same_machines_apply_second_item_and_are_unsynced(self):
        pb = basket((PRO, 2))
        self.assertEqual(pb["lines"][0]["unit_prices_vnd"], [7690000, 3995000])
        self.assertEqual((pb["total_vnd"], pb["order_total_vnd"], pb["synced"]), (11685000, 15380000, False))

    def test_single_unit_unchanged(self):
        pb = basket((AP_Y, 1))
        self.assertEqual((pb["total_vnd"], pb["order_total_vnd"], pb["synced"]), (5200000, 5200000, True))

    def test_product_without_second_item_promo_is_price_times_qty(self):
        pb = basket((SHOE, 2))
        self.assertEqual((pb["total_vnd"], pb["synced"]), (1780000, True))

    def test_three_same_machines_get_no_extra_discount(self):
        pb = basket((PRO, 3))
        self.assertEqual(pb["lines"][0]["unit_prices_vnd"], [7690000] * 3)
        self.assertEqual((pb["total_vnd"], pb["order_total_vnd"], pb["synced"]), (23070000, 23070000, True))

    def test_two_different_machines_policy_total_but_order_create_cannot_carry_basket(self):
        pb = basket((AP_X, 1), (AP_Y, 1))
        self.assertEqual([l["line_total_vnd"] for l in pb["lines"]], [2445000, 5200000])      # máy rẻ hơn (AP-X) được giảm 50% theo giỏ
        self.assertEqual([l["order_line_total_vnd"] for l in pb["lines"]], [4890000, 5200000])  # order.create không nhận giỏ → ghi giá không KM
        self.assertEqual((pb["total_vnd"], pb["order_total_vnd"], pb["synced"]), (7645000, 10090000, False))

    def test_two_different_products_without_basket_promo_are_synced(self):
        pb = basket((SHOE, 1), (RUN2, 1))
        self.assertEqual((pb["total_vnd"], pb["order_total_vnd"], pb["synced"]), (2411000, 2411000, True))

    def test_unknown_sku_returns_error(self):
        self.assertIn("error", basket(("SKU-KHONG-CO", 1)))

    def test_cod_thresholds(self):
        self.assertTrue(cod_exceeds(10000001)); self.assertFalse(cod_exceeds(10000000))
        self.assertTrue(cod_needs_confirmation(2000001)); self.assertFalse(cod_needs_confirmation(2000000))


class CorrectTotalsTest(unittest.TestCase):
    CALL = {"name": "pricing.get_quote", "args": {"qty": 2}, "result": {"final_price_vnd": 7690000, "total_vnd": 11685000, "order_total_vnd": 15380000}}

    def test_replace_amount_handles_formats_and_not_longer_numbers(self):
        out = replace_amount("15.380.000 VNĐ | 15,380,000đ | 15380000 đồng | 115.380.000 | 15.380.0001", 15380000, 11685000)
        self.assertEqual(out, "11.685.000 VNĐ | 11.685.000đ | 11.685.000 đồng | 115.380.000 | 15.380.0001")

    def test_llm_multiplication_is_replaced_by_policy_total(self):
        out = correct_basket_totals("giá sau KM cho 2 máy là 15.380.000 VNĐ, máy thứ hai giảm 3.995.000đ", [self.CALL])
        self.assertIn("11.685.000", out)
        self.assertNotIn("15.380.000", out)
        self.assertIn("3.995.000", out)                       # số đúng khác không bị đụng

    def test_unit_price_of_another_sku_in_a_basket_is_untouched(self):
        call = {**self.CALL, "args": {"qty": 2, "basket_skus": ["SKU-X"]}}
        self.assertEqual(correct_basket_totals("giá 15.380.000", [call]), "giá 15.380.000")
        self.assertEqual(correct_basket_totals("giá 7.690.000", [self.CALL]), "giá 7.690.000")      # giá một máy là số đúng

    def test_orchestrator_corrects_reply_end_to_end(self):
        c = build_components(); orch = c["orchestrator"]
        t = c["normalizer"].normalize("anh muốn mua 2 máy AirPure Pro", InputChannel.HOTLINE, "0911265844")
        b = c["brief"].build(c["resolver"].resolve(t, memory=c["memory"]), ON)
        orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": PRO, "qty": 2})], "text": "Dạ giá sau khuyến mãi cho 2 máy là 15.380.000 VNĐ ạ."})
        final, _, _ = orch.process_turn(t, b, current_date=ON)
        self.assertIn("11.685.000", final)
        self.assertNotIn("15.380.000", final)


class OrderSyncTest(unittest.TestCase):
    def _setup(self, order_gate=False):
        self.c = build_components(order_gate=order_gate)
        self.orch = self.c["orchestrator"]

    def _run(self, calls, phone="0911265844"):
        t = self.c["normalizer"].normalize("ok lên đơn cho anh", InputChannel.HOTLINE, phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), ON)
        self.orch.llm_client = FakeLLM({"calls": calls, "text": "Dạ em đã lên đơn ạ."})
        return self.orch.process_turn(t, b, current_date=ON)

    @staticmethod
    def _mock():
        import mock_tools
        return mock_tools

    @staticmethod
    def _create(sku, qty=1, payment="CK", **kw):
        return ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": sku, "qty": qty, "payment": payment, **kw})

    def test_quote_for_two_machines_reports_policy_total_and_flags_mismatch(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": PRO, "qty": 2})])
        r = tc[0]["result"]
        self.assertEqual((r["total_vnd"], r["order_total_vnd"], r["price_synced"]), (11685000, 15380000, False))
        self.assertEqual(r["final_price_vnd"], 7690000)                      # order.create vẫn kiểm giá theo đơn vị 1

    def test_unsynced_two_machines_never_create_order_and_hand_off_once(self):
        self._setup()
        final, tc, _ = self._run([self._create(PRO, 2, price_vnd=7690000)])
        m = self._mock()
        self.assertEqual(len(m._ORDERS), 0)                                  # backend sẽ ghi 15.380.000 ≠ 11.685.000 → không tạo
        self.assertFalse([c for c in tc if c["name"] == "order.create" and "order_id" in (c.get("result") or {})])
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 1)
        self.assertIn("11.685.000", final)
        self.assertNotIn("15.380.000", final)                                # một con số duy nhất
        self._run([self._create(PRO, 2, price_vnd=7690000)])                 # khách nhắc lại: không tạo phiếu thứ hai
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 1)
        self.assertEqual(len(m._ORDERS), 0)

    def test_single_unit_still_creates_order(self):
        self._setup()
        _, tc, _ = self._run([self._create(AP_Y, 1, price_vnd=5200000)])
        self.assertEqual(len(self._mock()._ORDERS), 1)
        self.assertEqual(tc[-1]["result"]["total_vnd"], 5200000)

    def test_two_shoes_create_order_with_price_times_two(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": SHOE, "qty": 2}), self._create(SHOE, 2, price_vnd=890000)])
        self.assertEqual(tc[0]["result"]["total_vnd"], 1780000)
        self.assertTrue(tc[0]["result"]["price_synced"])
        self.assertEqual(tc[1]["result"]["total_vnd"], 1780000)              # tổng báo == tổng đơn
        self.assertEqual(len(self._mock()._ORDERS), 1)

    def test_three_machines_quote_equals_order_total(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": PRO, "qty": 3}), self._create(PRO, 3, price_vnd=7690000)])
        self.assertEqual(tc[0]["result"]["total_vnd"], 23070000)
        self.assertEqual(tc[1]["result"]["total_vnd"], 23070000)
        self.assertEqual(len(self._mock()._ORDERS), 1)

    def test_two_different_machines_total_is_reported_but_orders_are_not_created(self):
        """Tổng giỏ 2 máy khác SKU do price_basket tính (7.645.000); order.create không nhận giỏ nên sẽ ghi 10.090.000 → không tạo đơn nào, chuyển nhân viên."""
        self._setup()
        final, tc, _ = self._run([("pricing.get_quote", {"sku": AP_X, "qty": 1, "basket_skus": [AP_Y]}),
                                  self._create(AP_X, 1, price_vnd=2445000, basket_skus=[AP_Y])])
        q = next(c for c in tc if c["name"] == "pricing.get_quote")["result"]     # lời gọi của cổng/handoff đứng trước trong trace
        self.assertEqual((q["total_vnd"], q["order_total_vnd"], q["price_synced"]), (7645000, 10090000, False))
        m = self._mock()
        self.assertEqual(len(m._ORDERS), 0)
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 1)
        self.assertIn("7.645.000", final)

    def test_two_different_products_quote_equals_sum_of_orders(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": SHOE, "qty": 1, "basket_skus": [RUN2]}),
                              self._create(SHOE, 1, price_vnd=890000, basket_skus=[RUN2]),
                              self._create(RUN2, 1, price_vnd=1521000, basket_skus=[SHOE])])
        self.assertEqual(tc[0]["result"]["total_vnd"], 2411000)
        self.assertEqual(tc[1]["result"]["total_vnd"] + tc[2]["result"]["total_vnd"], 2411000)
        self.assertEqual(len(self._mock()._ORDERS), 2)

    def test_cod_blocks_correct_total_over_limit(self):
        self._setup(order_gate=True)
        final, tc, _ = self._run([self._create(PRO, 2, payment="COD", price_vnd=7690000)])
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertIn("hạn mức", final)
        self.assertIn("11.685.000", final)                                   # hạn mức tính trên tổng ĐÚNG, không phải 15.380.000
        self.assertNotIn("15.380.000", final)

    def test_cod_not_blocked_by_wrong_old_total(self):
        """AP-Y x2: tổng đúng 7.800.000 ≤ 10.000.000 (cách cũ ra 10.400.000 > hạn mức) → không được nói 'vượt hạn mức COD'; đơn không tạo vì lệch giá, chuyển nhân viên."""
        self._setup(order_gate=True)
        final, tc, _ = self._run([self._create(AP_Y, 2, payment="COD", price_vnd=5200000)])
        m = self._mock()
        self.assertEqual(len(m._ORDERS), 0)
        self.assertNotIn("hạn mức", final)
        self.assertIn("7.800.000", final)
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 1)

    def test_cod_limit_applies_to_whole_basket_not_each_line(self):
        """PRO (7.690.000) + AP-Y (2.600.000 nhờ KM máy thứ 2) = 10.290.000: từng dòng ≤ 10.000.000 nhưng cả giỏ vượt → không COD, không tách đơn để lách."""
        self._setup(order_gate=True)
        final, _, _ = self._run([self._create(PRO, 1, payment="COD", price_vnd=7690000, basket_skus=[AP_Y])])
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertIn("hạn mức", final)
        self.assertIn("10.290.000", final)

    def test_confirmation_call_threshold_uses_basket_total(self):
        """Hai dòng COD, mỗi dòng ≤ 2.000.000 (backend không đòi gọi xác nhận) nhưng cả giỏ 2.411.000 > 2.000.000 → cờ xác nhận bật."""
        self._setup()
        _, tc, _ = self._run([self._create(RUN2, 1, payment="COD", price_vnd=1521000, basket_skus=[SHOE])])
        r = tc[-1]["result"]
        self.assertEqual(r["status"], "created")
        self.assertTrue(r["needs_confirmation_call"])

    def test_sanitize_basket_still_strips_own_sku(self):
        from src.harness.orchestrator import HarnessOrchestrator
        out = HarnessOrchestrator._sanitize_basket("order.create", {"sku": PRO, "basket_skus": [PRO]})
        self.assertNotIn("basket_skus", out)


if __name__ == "__main__":
    unittest.main()
