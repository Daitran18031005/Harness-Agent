"""Giá báo == giá đơn khi mua nhiều máy (KM 'máy thứ 2'): `price_basket` (pricing.quote_order), order.create(lines), hạn mức COD trên tổng của giỏ.
Mọi con số đối chiếu với mock_tools.py của BTC (bản 11/2026) ngày 2026-10-15 (AirPure Pro: AIR-OCT −300.000, AIR-2ND-50 −50% cho MỘT máy mỗi đơn)."""
import unittest
from tests._helpers import build_components
from tests.test_orchestrator import FakeLLM
from src.channels.normalizer import InputChannel
from src.harness.basket import price_basket, order_args, cod_exceeds, cod_needs_confirmation, replace_amount, correct_basket_totals

ON = "2026-10-15"
PRO, AP_X, AP_Y, SHOE, RUN2 = "SKU-AP-PRO", "SKU-AP-X", "SKU-AP-Y", "SKU-SN-CAS-39-DEN", "SKU-SN-RUN2-40-DEN"


def mock_call(tool, args):
    import mock_tools
    return (mock_tools.pricing_quote_order if tool == "pricing.quote_order" else mock_tools.pricing_get_quote)(**args)


def basket(*lines):
    return price_basket(mock_call, [{"sku": s, "qty": q} for s, q in lines], ON)


class PriceBasketTest(unittest.TestCase):
    def setUp(self):
        build_components()                     # reset trạng thái mock

    def test_two_same_machines_apply_second_item_to_one_unit(self):
        pb = basket((PRO, 2))
        self.assertEqual(pb["lines"][0]["unit_prices_vnd"], [7690000, 3995000])
        self.assertEqual(pb["total_vnd"], 11685000)
        self.assertEqual([a["promo_code"] for a in pb["lines"][0]["second_unit_promos"]], ["AIR-2ND-50"])

    def test_single_unit_unchanged(self):
        self.assertEqual(basket((AP_Y, 1))["total_vnd"], 5200000)

    def test_product_without_second_item_promo_is_price_times_qty(self):
        self.assertEqual(basket((SHOE, 2))["total_vnd"], 1780000)

    def test_three_same_machines_only_one_gets_second_item_discount(self):
        pb = basket((PRO, 3))                  # luật BTC 11/2026: đúng MỘT máy mỗi đơn được giảm 50%
        self.assertEqual(pb["lines"][0]["unit_prices_vnd"], [7690000, 7690000, 3995000])
        self.assertEqual(pb["total_vnd"], 19375000)

    def test_two_different_machines_cheaper_one_gets_discount(self):
        pb = basket((AP_X, 1), (AP_Y, 1))
        self.assertEqual([l["line_total_vnd"] for l in pb["lines"]], [2445000, 5200000])
        self.assertEqual(pb["total_vnd"], 7645000)

    def test_two_different_products_without_basket_promo(self):
        self.assertEqual(basket((SHOE, 1), (RUN2, 1))["total_vnd"], 2411000)

    def test_order_args_uniform_keeps_old_form_and_mixed_uses_lines(self):
        base = {"customer_phone": "0900000001", "sku": PRO, "qty": 3, "price_vnd": 1, "basket_skus": [AP_Y]}
        self.assertEqual(order_args({**base, "sku": SHOE, "qty": 2}, basket((SHOE, 2))), {"customer_phone": "0900000001", "sku": SHOE, "qty": 2, "price_vnd": 1})
        out = order_args(base, basket((PRO, 3)))
        self.assertEqual(out["lines"], [{"sku": PRO, "qty": 1, "price_vnd": v} for v in (7690000, 7690000, 3995000)])
        self.assertFalse({"qty", "price_vnd", "basket_skus"} & set(out))

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

    def test_quote_for_two_machines_reports_basket_total(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": PRO, "qty": 2})])
        r = tc[0]["result"]
        self.assertEqual((r["total_vnd"], r["unit_prices_vnd"], r["final_price_vnd"]), (11685000, [7690000, 3995000], 7690000))

    def test_two_machines_create_one_order_with_per_unit_lines(self):
        self._setup()
        _, tc, _ = self._run([self._create(PRO, 2, price_vnd=7690000)])
        m = self._mock()
        self.assertEqual([o["total_vnd"] for o in m._ORDERS.values()], [11685000])      # tổng báo == tổng backend ghi
        oc = next(c for c in tc if c["name"] == "order.create")
        self.assertEqual(oc["args"]["lines"], [{"sku": PRO, "qty": 1, "price_vnd": 7690000}, {"sku": PRO, "qty": 1, "price_vnd": 3995000}])
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 0)
        self._run([self._create(PRO, 2, price_vnd=7690000)])                 # khách nhắc lại: không tạo đơn thứ hai
        self.assertEqual(len(m._ORDERS), 1)

    def test_single_unit_still_creates_order(self):
        self._setup()
        _, tc, _ = self._run([self._create(AP_Y, 1, price_vnd=5200000)])
        self.assertEqual(len(self._mock()._ORDERS), 1)
        self.assertEqual(tc[-1]["result"]["total_vnd"], 5200000)

    def test_two_shoes_create_order_with_price_times_two(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": SHOE, "qty": 2}), self._create(SHOE, 2, price_vnd=890000)])
        self.assertEqual(tc[0]["result"]["total_vnd"], 1780000)
        self.assertEqual(tc[1]["result"]["total_vnd"], 1780000)              # tổng báo == tổng đơn
        self.assertEqual(len(self._mock()._ORDERS), 1)

    def test_three_machines_quote_equals_order_total(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": PRO, "qty": 3}), self._create(PRO, 3, price_vnd=7690000)])
        self.assertEqual(tc[0]["result"]["total_vnd"], 19375000)
        self.assertEqual(tc[1]["result"]["total_vnd"], 19375000)
        self.assertEqual(len(self._mock()._ORDERS), 1)

    def test_two_different_machines_create_one_order_with_basket_total(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": AP_X, "qty": 1, "basket_skus": [AP_Y]}),
                              self._create(AP_X, 1, price_vnd=2445000, basket_skus=[AP_Y])])
        self.assertEqual(next(c for c in tc if c["name"] == "pricing.get_quote")["result"]["total_vnd"], 7645000)
        m = self._mock()
        self.assertEqual([(o["total_vnd"], [l["sku"] for l in o["lines"]]) for o in m._ORDERS.values()], [(7645000, [AP_X, AP_Y])])
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 0)

    def test_two_different_products_are_one_order_even_if_llm_calls_twice(self):
        self._setup()
        _, tc, _ = self._run([("pricing.get_quote", {"sku": SHOE, "qty": 1, "basket_skus": [RUN2]}),
                              self._create(SHOE, 1, price_vnd=890000, basket_skus=[RUN2]),
                              self._create(RUN2, 1, price_vnd=1521000, basket_skus=[SHOE])])
        self.assertEqual(tc[0]["result"]["total_vnd"], 2411000)
        self.assertEqual([o["total_vnd"] for o in self._mock()._ORDERS.values()], [2411000])
        self.assertTrue(tc[2]["result"].get("already_done"))

    def test_cod_blocks_correct_total_over_limit(self):
        self._setup(order_gate=True)
        final, tc, _ = self._run([self._create(PRO, 2, payment="COD", price_vnd=7690000)])
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertIn("hạn mức", final)
        self.assertIn("11.685.000", final)                                   # hạn mức tính trên tổng ĐÚNG, không phải 15.380.000
        self.assertNotIn("15.380.000", final)

    def test_cod_not_blocked_when_basket_total_is_under_limit(self):
        """AP-Y x2: tổng đúng 7.800.000 ≤ 10.000.000 (nhân giá × 2 ra 10.400.000 > hạn mức) → không được nói 'vượt hạn mức COD', không chuyển nhân viên; order gate hỏi phần còn thiếu."""
        self._setup(order_gate=True)
        final, tc, _ = self._run([self._create(AP_Y, 2, payment="COD", price_vnd=5200000)])
        m = self._mock()
        self.assertNotIn("hạn mức", final)
        self.assertEqual(len([t for t in m._TICKETS if t["action"] == "handoff"]), 0)
        self.assertEqual(len(m._ORDERS), 0)                                  # gate chưa đủ thông tin giao hàng

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
