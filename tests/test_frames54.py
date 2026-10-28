"""Khung 54 kịch bản còn lại (src/dataset/frames54.py): đúng cơ cấu, ràng buộc người duyệt đặt ra, và đáp án khớp mock/bộ chọn sản phẩm."""
import unittest

from src.dataset import truth as T
from src.dataset.rules import is_order_call
from src.dataset.validate import SUCCESS_FIELDS


class Frames54Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.dataset.frames54 import build_frames54
        cls.frames = build_frames54()
        cls.calls = [(f["scenario"], c) for f in cls.frames for c in f["calls"]]

    def test_structure_matches_the_approved_plan(self):
        self.assertEqual(len(self.frames), 54)
        groups = [f["scenario"]["group"] for f in self.frames]
        self.assertEqual((groups.count("A"), groups.count("B"), groups.count("C")), (13, 10, 31))
        self.assertEqual(sorted({len(f["calls"]) for f in self.frames}), [1, 2, 3])
        self.assertEqual(len(self.calls), 87)                               # 87 + 17 (10 mẫu) + 31 (22 kịch bản hiện có) = 135 cuộc

    def test_ids_and_phones_are_unique_and_do_not_collide_with_existing_data(self):
        from src.dataset.specs import build_sample10
        ids = [f["scenario"]["scenario_id"] for f in self.frames]
        phones = [f["scenario"]["customer_phone"] for f in self.frames]
        self.assertEqual(len(set(ids)), 54)
        self.assertEqual(len(set(phones)), 54)
        self.assertFalse(set(phones) & {f["scenario"]["customer_phone"] for f in build_sample10()})
        self.assertTrue(all(p.startswith("09000200") for p in phones))      # dải SĐT giả của dự án, không gắn người thật

    def test_at_least_three_over_budget_two_option_cases_and_truth_comes_from_the_retriever(self):
        from src.catalog import ProductRetriever
        over = [f for f in self.frames if f["scenario"]["hard_case"] == "vuot_ngan_sach_2_lua_chon"]
        self.assertGreaterEqual(len(over), 3)
        r = ProductRetriever()
        for f in over:
            slots = {x["key"]: x["value"] for x in f["calls"][0]["customer_facts"] if x["key"] in ("room_area_m2", "has_children", "budget_vnd")}
            res = r.shortlist(slots, category="máy lọc không khí")
            self.assertEqual(res.decision["mode"], "two_options", f["scenario"]["scenario_id"])
            self.assertGreater(res.decision["overage_pct"], 20)
            names = {T.product_name(res.items[0].sku), T.product_name(res.alternative.sku)}
            vars_text = " ".join(v["text"] for v in f["calls"][0]["agent_vars"].values())
            self.assertTrue(all(n in vars_text for n in names))              # lời agent có đủ CẢ HAI lựa chọn qua ô trống
            self.assertLessEqual(res.alternative.list_price_vnd, slots["budget_vnd"])

    def test_at_least_two_returning_customers_with_saved_address_where_the_gate_only_confirms(self):
        saved = [(s, c) for s, c in self.calls if c.get("saved_address")]
        self.assertGreaterEqual(len(saved), 2)
        for s, c in saved:
            self.assertEqual(c["name"], "call_2")
            self.assertTrue(c["order_flow"])
            keys = {x["key"] for x in c["customer_facts"]}
            self.assertFalse(keys & {"address", "payment", "recipient_name", "phone_provided"})        # khách KHÔNG nói lại, chỉ xác nhận
            self.assertIsNone(c["agent_vars"]["address"].get("after"))
            self.assertIsNone(c["agent_vars"]["recipient_name"].get("after"))
            first = next(f for f in self.frames if f["scenario"]["scenario_id"] == s["scenario_id"])["calls"][0]
            self.assertTrue(is_order_call(first))                            # địa chỉ lưu có nguồn: đơn thật ở cuộc 1
            self.assertEqual(c["saved_address"], next(x["value"] for x in first["customer_facts"] if x["key"] == "address"))

    def test_order_calls_go_through_the_gate_and_others_do_not(self):
        n = 0
        for s, c in self.calls:
            if is_order_call(c):
                n += 1
                self.assertTrue(c["order_flow"], (s["scenario_id"], c["name"]))
                for k in ("readback_total", "payment_label", "recipient_name", "caller_phone", "address", "order_id"):
                    self.assertIn(k, c["agent_vars"], (s["scenario_id"], c["name"], k))
            else:
                self.assertNotIn("order_flow", c, (s["scenario_id"], c["name"]))
        self.assertGreaterEqual(n, 40)

    def test_expected_blocks_use_only_btc_fields_and_prices_match_the_mock(self):
        for s, c in self.calls:
            si = (c["expected"].get("success_if") or {})
            self.assertFalse(set(si) - SUCCESS_FIELDS, (s["scenario_id"], c["name"], set(si) - SUCCESS_FIELDS))
            am = si.get("args_match") or {}
            if is_order_call(c) and am.get("price_vnd") and am.get("sku") and am.get("qty") is None:
                self.assertEqual(am["price_vnd"], T.quote(am["sku"], c["abs_date"], s["customer_phone"])["final_price_vnd"], (s["scenario_id"], c["name"]))
                self.assertTrue(T.stock(am["sku"], c["abs_date"])["in_stock"], (s["scenario_id"], c["name"], "đặt hàng hết hàng"))

    def test_promo_expiry_cases_have_promo_active_on_call1_and_expired_on_call2(self):
        n = 0
        for f in self.frames:
            if f["scenario"]["hard_case"] == "khuyen_mai_het_han":
                n += 1
                gt = f["calls"][1]["expected"]["ground_truth_facts"]
                code = next(k for k in gt if k.startswith("promo_")).split("_")[1] if "promo_" in "".join(gt) else None
                self.assertTrue(code and gt[next(k for k in gt if k.startswith("promo_"))] is False)
                self.assertTrue(T.promo_active(code, f["calls"][0]["abs_date"]))
                self.assertFalse(T.promo_active(code, f["calls"][1]["abs_date"]))
        self.assertEqual(n, 3)

    def test_sizes_colors_exist_and_exchange_prices_come_from_order_update(self):
        for f in self.frames:
            if f["scenario"]["archetype"] == "exchange":
                gt = f["calls"][2]["expected"]["ground_truth_facts"]
                self.assertIn("extra_payment_vnd", gt)
                v2 = f["calls"][2]["expected"]["success_if"]["args_match"]["new_variant_sku"]
                self.assertTrue(T.stock(v2, f["calls"][2]["abs_date"])["in_stock"])
        surcharged = [f for f in self.frames if f["scenario"]["archetype"] == "exchange" and f["calls"][2]["expected"]["ground_truth_facts"]["extra_payment_vnd"] > 0]
        free = [f for f in self.frames if f["scenario"]["archetype"] == "exchange" and f["calls"][2]["expected"]["ground_truth_facts"]["extra_payment_vnd"] == 0]
        self.assertTrue(surcharged and free)                                  # có cả ca phụ thu lẫn không phụ thu

    def test_cod_limit_cases_really_exceed_the_limit(self):
        for f in self.frames:
            if f["scenario"]["hard_case"] == "cod_vuot_han_muc":
                gt = f["calls"][0]["expected"]["ground_truth_facts"]
                self.assertGreater(gt["total_vnd"], gt["cod_limit_vnd"])

    def test_teencode_only_on_chat_channels(self):
        for s, c in self.calls:
            if c["style"] == "teencode":
                self.assertIn(c["channel"], {"chat_fanpage", "zalo_oa"})


if __name__ == "__main__":
    unittest.main()
