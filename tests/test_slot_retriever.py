"""Bước 12: schema slot → thuộc tính (luật dữ liệu), ProductRetriever, ClarificationPolicy và tích hợp vào orchestrator.
Kiểm bằng NHIỀU sản phẩm/ngành và catalog thử — không có test nào gắn vào tên AirPure/SAMPLE-01."""
import copy
import json
import os
import random
import re
import unittest

from src.catalog import ClarificationPolicy, ProductRetriever, load_rules, parse_rules, validate_against_catalog
from src.catalog.slot_schema import RuleError
from tests._helpers import build_components
from tests.test_orchestrator import FakeLLM

CATALOG = json.load(open(os.path.join(os.path.dirname(__file__), "..", "BTC-Data-Vong1-TEAMS", "catalog", "products.json"), encoding="utf-8"))["products"]


def prod(sku, price, category="x/loai-a", name=None, **attrs):
    return {"sku": sku, "name": name or f"San pham {sku}", "brand": "B", "category": category, "list_price_vnd": price,
            "attributes": attrs, "stock": 5, "variants": []}


class RulesAsDataTest(unittest.TestCase):
    def test_rules_load_and_every_rule_points_to_a_real_catalog_attribute(self):
        rules = load_rules()
        self.assertEqual(validate_against_catalog(rules, CATALOG), [])            # không có luật chết
        self.assertGreaterEqual(len(rules.rules), 8)

    def test_no_product_names_or_skus_inside_rules_or_retriever_source(self):
        text = open(os.path.join(os.path.dirname(__file__), "..", "config", "slot_rules.json"), encoding="utf-8").read()
        src = open(os.path.join(os.path.dirname(__file__), "..", "src", "catalog", "retriever.py"), encoding="utf-8").read()
        for token in ("AirPure", "SKU-AP", "SAMPLE-01", "Karofi", "RunLite"):
            self.assertNotIn(token, text)
            self.assertNotIn(token, src)

    def test_invalid_rules_are_rejected(self):
        with self.assertRaises(RuleError):
            parse_rules({"rules": [{"id": "a", "slot": "s", "attribute": "x", "op": "nope", "weight": 1, "reason": "r"}]})
        with self.assertRaises(RuleError):
            parse_rules({"rules": [{"id": "a", "slot": "s", "attribute": "x", "op": "eq", "weight": 1, "reason": "r"}]})   # eq thiếu value
        with self.assertRaises(RuleError):
            parse_rules({"rules": [{"id": "a", "slot": "s", "attribute": "x", "op": "gte", "weight": 0, "reason": "r"}]})
        ok = {"id": "a", "slot": "s", "attribute": "x", "op": "gte", "weight": 1, "reason": "r"}
        with self.assertRaises(RuleError):
            parse_rules({"rules": [ok, ok]})                                          # trùng id

    def test_dead_rule_detected(self):
        rules = parse_rules({"rules": [{"id": "ghost", "slot": "s", "attribute": "khong_ton_tai", "op": "gte", "weight": 1, "reason": "r"}]})
        self.assertTrue(validate_against_catalog(rules, CATALOG))


class RealCatalogMultiCategoryTest(unittest.TestCase):
    """≥ 8 sản phẩm thuộc ≥ 3 danh mục; mỗi luật có ca dương và ca âm."""

    @classmethod
    def setUpClass(cls):
        cls.r = ProductRetriever()

    def top(self, slots, category):
        return self.r.shortlist(slots, category=category).top

    def test_child_lock_preferred_over_cheaper_even_if_slightly_over_budget(self):
        t = self.r.shortlist({"room_area_m2": 25, "has_children": True, "budget_vnd": 5000000}, category="máy lọc không khí")
        self.assertEqual(t.top.sku, "SKU-AP-Y")
        self.assertEqual([v["rule"] for v in t.top.violated], ["budget"])           # vượt ngân sách được nêu rõ, không bị loại
        self.assertIn("child_safety", [m["rule"] for m in t.top.matched])

    def test_without_children_cheaper_in_budget_product_wins(self):
        t = self.r.shortlist({"room_area_m2": 25, "budget_vnd": 5000000}, category="máy lọc không khí")
        self.assertEqual(t.top.sku, "SKU-AP-X")

    def test_room_too_big_ranks_small_purifiers_last(self):
        t = self.r.shortlist({"room_area_m2": 55}, category="máy lọc không khí", top_k=10)
        order = [i.sku for i in t.items]
        self.assertEqual(t.top.sku, "SKU-XM-4P")                                   # phủ 60 m², sát nhu cầu nhất
        self.assertGreater(order.index("SKU-AP-MINI"), order.index("SKU-AP-PRO"))

    def test_stroller_weight_limit_picks_the_one_that_carries_the_child(self):
        self.assertEqual(self.top({"child_weight_kg": 18}, "xe đẩy").sku, "SKU-MB-STR1")     # tải 22 kg
        self.assertEqual(self.top({"child_weight_kg": 12}, "xe đẩy").sku in ("SKU-MB-STR1", "SKU-MB-STR2"), True)   # cả hai đủ tải → theo luật khác

    def test_water_filter_stage_rule(self):
        self.assertEqual(self.top({"min_stages": 8}, "máy lọc nước").sku, "SKU-WF-RO9")
        t = self.r.shortlist({"min_stages": 8}, category="máy lọc nước", top_k=5)
        self.assertIn("water_stages", [v["rule"] for v in t.items[-1].violated])

    def test_shoes_material_contains_rule_and_budget(self):
        t = self.r.shortlist({"budget_vnd": 1000000, "material": "EVA"}, category="giày", top_k=5)
        self.assertEqual(t.top.sku, "SKU-SN-CAS")                                  # duy nhất ≤ 1 triệu
        t2 = self.r.shortlist({"material": "da thật"}, category="giày", top_k=5)
        self.assertTrue(all(any(v["rule"] == "material" for v in i.violated) for i in t2.items))

    def test_warranty_rule_across_categories(self):
        t = self.r.shortlist({"min_warranty_months": 30}, category="máy lọc nước", top_k=5)
        self.assertTrue(all(any(m["rule"] == "warranty" for m in i.matched) for i in t.items))   # cả 3 máy đều 36 tháng
        t = self.r.shortlist({"min_warranty_months": 24}, category="quạt", top_k=5)
        self.assertTrue(all(any(v["rule"] == "warranty" for v in i.violated) for i in t.items))  # quạt bảo hành 12 tháng

    def test_rule_is_neutral_where_attribute_does_not_exist(self):
        t = self.r.shortlist({"has_children": True}, category="quạt", top_k=5)       # quạt không có child_safe_lock
        self.assertTrue(all(i.score == 0 and "child_safety" in i.unknown for i in t.items))
        self.assertEqual([i.list_price_vnd for i in t.items], sorted(i.list_price_vnd for i in t.items))   # hòa điểm → rẻ trước

    def test_discontinued_and_accessories_excluded(self):
        skus = {i.sku for i in self.r.shortlist({}, category="máy lọc không khí", top_k=50).items}
        self.assertNotIn("SKU-AP-X-2024", skus)                                    # ngừng bán
        self.assertFalse(skus & {"SKU-AP-FLT-X", "SKU-BDL-AIR", "SKU-XM-FLT"})     # phụ kiện/combo không lẫn vào tư vấn
        acc = {i.sku for i in self.r.shortlist({}, query="màng lọc", top_k=50).items}
        self.assertIn("SKU-AP-FLT-X", acc)                                         # nhưng tìm đích danh thì có

    def test_out_of_stock_demotes_but_does_not_remove(self):
        base = self.r.shortlist({"room_area_m2": 42}, category="máy lọc không khí", top_k=5)
        self.assertEqual(base.top.sku, "SKU-XM-4L")                                # phủ 43 m², sát nhu cầu nhất
        t = self.r.shortlist({"room_area_m2": 42}, category="máy lọc không khí", top_k=5, in_stock_fn=lambda sku: sku != "SKU-XM-4L")
        self.assertIn("SKU-XM-4L", [i.sku for i in t.items])                       # không bị loại
        self.assertNotEqual(t.top.sku, "SKU-XM-4L")                                # nhưng bị hạ hạng
        xm = next(i for i in t.items if i.sku == "SKU-XM-4L")
        self.assertIn("out_of_stock", [v["rule"] for v in xm.violated])

    def test_string_slots_from_llm_are_coerced_and_junk_ignored(self):
        t = self.r.shortlist({"room_area_m2": "25", "has_children": "true", "budget_vnd": "5000000", "mau_sac": "đỏ", "x": None},
                             category="máy lọc không khí")
        self.assertEqual(t.slots_used, {"room_area_m2": 25, "has_children": True, "budget_vnd": 5000000})
        self.assertEqual(t.top.sku, "SKU-AP-Y")

    def test_over_budget_penalty_grows_with_overage_but_never_excludes(self):
        r = ProductRetriever(products=[prod("A", 1_000_000), prod("B", 1_100_000), prod("C", 2_000_000)])
        scores = {i.sku: i.score for i in r.shortlist({"budget_vnd": 1_000_000}, top_k=5).items}
        self.assertGreater(scores["A"], scores["B"])
        self.assertGreater(scores["B"], scores["C"])
        self.assertEqual(len(r.shortlist({"budget_vnd": 10}, top_k=5).items), 3)     # ngân sách phi lý vẫn không loại ai

    def test_always_valid_skus_for_random_slot_combinations(self):
        """Mọi SKU shortlist trả về tồn tại thật và tool tham chiếu của BTC chấp nhận (không `unknown_sku`)."""
        import mock_tools
        rng = random.Random(7)
        cats = ["máy lọc không khí", "máy lọc nước", "quạt", "nồi chiên", "giày", "áo khoác", "xe đẩy", "máy hút sữa", "bình sữa", None]
        valid = {p["sku"] for p in CATALOG}
        for _ in range(300):
            slots = {k: v for k, v in {"room_area_m2": rng.choice([None, 10, 25, 50, 80]), "has_children": rng.choice([None, True, False]),
                                       "budget_vnd": rng.choice([None, 500_000, 3_000_000, 8_000_000]),
                                       "child_weight_kg": rng.choice([None, 9, 20]), "min_stages": rng.choice([None, 5, 9]),
                                       "material": rng.choice([None, "EVA"])}.items() if v is not None}
            res = self.r.shortlist(slots, category=rng.choice(cats), top_k=rng.choice([1, 3, 5]))
            for item in res.items:
                self.assertIn(item.sku, valid)
                self.assertNotIn("error", mock_tools.catalog_search(sku=item.sku))
                self.assertNotEqual(mock_tools.pricing_get_quote(item.sku, "2026-10-15").get("error"), "unknown_sku")


class SwapAndSyntheticCatalogTest(unittest.TestCase):
    """Kết quả phải đổi đúng theo THUỘC TÍNH, không theo tên/thứ tự sản phẩm."""

    def make(self, order=None, names=None):
        ps = [prod("P1", 4_000_000, child_safe_lock=False, room_area_m2=30), prod("P2", 4_500_000, child_safe_lock=True, room_area_m2=30),
              prod("P3", 3_000_000, child_safe_lock=False, room_area_m2=20)]
        if names:
            for p, n in zip(ps, names):
                p["name"] = n
        if order:
            ps = [ps[i] for i in order]
        return ProductRetriever(products=ps)

    def test_ranking_independent_of_names_and_catalog_order(self):
        slots = {"has_children": True, "room_area_m2": 25, "budget_vnd": 4_200_000}
        base = [i.sku for i in self.make().shortlist(slots, top_k=3).items]
        for order in ([2, 1, 0], [1, 0, 2], [0, 2, 1]):
            self.assertEqual([i.sku for i in self.make(order).shortlist(slots, top_k=3).items], base)
        self.assertEqual([i.sku for i in self.make(names=["Zeta", "Alpha", "Omega"]).shortlist(slots, top_k=3).items], base)
        self.assertEqual(base[0], "P2")

    def test_adding_a_better_product_changes_the_result(self):
        r = self.make()
        r.products.append(prod("P4", 4_100_000, child_safe_lock=True, room_area_m2=28))
        self.assertEqual(r.shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 4_200_000}).top.sku, "P4")

    def test_when_no_product_has_the_safety_attribute_choice_falls_back_to_other_rules(self):
        ps = [prod("Q1", 4_000_000, room_area_m2=30), prod("Q2", 3_000_000, room_area_m2=30)]
        t = ProductRetriever(products=ps).shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 3_500_000})
        self.assertEqual(t.top.sku, "Q2")                                          # luật trẻ em trung tính → theo giá/ngân sách

    def test_sole_safe_product_is_kept_even_far_over_budget(self):
        ps = [prod("S1", 9_000_000, child_safe_lock=True), prod("S2", 1_000_000, child_safe_lock=False), prod("S3", 1_200_000, child_safe_lock=False)]
        t = ProductRetriever(products=ps).shortlist({"has_children": True, "budget_vnd": 2_000_000})
        self.assertEqual(t.top.sku, "S1")
        self.assertIn("budget", [v["rule"] for v in t.top.violated])

    def test_new_category_attribute_needs_only_a_json_rule(self):
        rules = parse_rules({"rules": [{"id": "battery", "slot": "min_battery_h", "attribute": "battery_h", "op": "gte", "weight": 3, "reason": "pin", "question": "Cần pin bao lâu?"}]})
        ps = [prod("T1", 1_000_000, "dien-thoai/a", battery_h=10), prod("T2", 900_000, "dien-thoai/a", battery_h=24)]
        self.assertEqual(ProductRetriever(products=ps, rules=rules).shortlist({"min_battery_h": 20}).top.sku, "T2")


class BudgetDecisionTest(unittest.TestCase):
    """≤ 20% vượt ngân sách → vẫn chốt sản phẩm đứng đầu + nêu mức vượt; > 20% → 2 lựa chọn (đứng đầu + tốt nhất trong ngân sách)."""

    def retr(self):
        return ProductRetriever(products=[
            prod("SAFE", 5_200_000, child_safe_lock=True, room_area_m2=30),
            prod("CHEAP_A", 4_000_000, child_safe_lock=False, room_area_m2=30),
            prod("CHEAP_B", 3_000_000, child_safe_lock=False, room_area_m2=20),
            prod("PRICY", 9_000_000, child_safe_lock=True, room_area_m2=50)])

    def test_within_20_percent_keeps_single_choice_and_states_overage(self):
        res = self.retr().shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 5_000_000})
        self.assertEqual(res.top.sku, "SAFE")
        self.assertEqual(res.decision["mode"], "single")
        self.assertEqual(res.decision["overage_pct"], 4.0)
        self.assertIsNone(res.alternative)
        self.assertNotIn("alternative", res.to_dict())

    def test_exactly_20_percent_is_still_single(self):
        r = ProductRetriever(products=[prod("A", 6_000_000, child_safe_lock=True), prod("B", 3_000_000, child_safe_lock=False)])
        self.assertEqual(r.shortlist({"has_children": True, "budget_vnd": 5_000_000}).decision["mode"], "single")        # đúng 20,0%
        self.assertEqual(r.shortlist({"has_children": True, "budget_vnd": 4_999_000}).decision["mode"], "two_options")   # vừa quá 20%

    def test_over_20_percent_offers_two_options(self):
        res = self.retr().shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 4_000_000})
        self.assertEqual(res.top.sku, "SAFE")                                         # vẫn là sản phẩm đứng đầu (an toàn)
        self.assertEqual(res.decision["mode"], "two_options")
        self.assertEqual(res.decision["primary"], "SAFE")
        self.assertEqual(res.decision["alternative"], "CHEAP_A")                      # tốt nhất TRONG ngân sách (phủ đủ 25 m²)
        self.assertEqual(res.decision["overage_pct"], 30.0)
        self.assertLessEqual(res.alternative.list_price_vnd, 4_000_000)
        out = res.to_dict()
        self.assertEqual(out["alternative"]["sku"], "CHEAP_A")
        self.assertEqual(out["recommendation"], "SAFE")

    def test_over_20_percent_without_any_in_budget_product_stays_single_with_flag(self):
        res = self.retr().shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 1_000_000})
        self.assertEqual(res.decision["mode"], "single")
        self.assertTrue(res.decision.get("no_in_budget_alternative"))

    def test_no_budget_or_in_budget_is_single_without_overage(self):
        self.assertEqual(self.retr().shortlist({"has_children": True}).decision["mode"], "single")
        res = self.retr().shortlist({"room_area_m2": 25, "budget_vnd": 4_500_000})
        self.assertEqual(res.decision.get("overage_pct", 0.0), 0.0)

    def test_tolerance_is_a_setting_not_code(self):
        rules = load_rules()
        self.assertEqual(rules.settings["budget_tolerance"], 0.20)
        rules.settings["budget_tolerance"] = 0.50
        r = ProductRetriever(products=self.retr().products, rules=rules)
        self.assertEqual(r.shortlist({"has_children": True, "room_area_m2": 25, "budget_vnd": 4_000_000}).decision["mode"], "single")

    def test_real_catalog_over_budget_gives_alternative_in_budget(self):
        r = ProductRetriever()
        res = r.shortlist({"room_area_m2": 25, "has_children": True, "budget_vnd": 4_000_000}, category="máy lọc không khí")
        self.assertEqual(res.decision["mode"], "two_options")
        self.assertEqual(res.top.sku, "SKU-AP-Y")
        self.assertLessEqual(res.alternative.list_price_vnd, 4_000_000)
        same = r.shortlist({"room_area_m2": 25, "has_children": True, "budget_vnd": 5_000_000}, category="máy lọc không khí")
        self.assertEqual((same.top.sku, same.decision["mode"], same.decision["overage_pct"]), ("SKU-AP-Y", "single", 4.0))


class ConfirmationRewriteTest(unittest.TestCase):
    def setUp(self):
        self.policy = ClarificationPolicy(load_rules())

    def rewrite(self, text, banned, known, confirmed=()):
        from src.harness.extractor import extract_questions
        return self.policy.rewrite_repeated_questions(text, extract_questions(text), set(banned), known, set(confirmed))

    def test_templates_for_each_known_slot(self):
        cases = [("Phòng nhà mình rộng bao nhiêu mét vuông ạ?", "room_area_m2", {"room_area_m2": 25.0}, "Phòng nhà mình vẫn khoảng 25m² đúng không ạ?"),
                 ("Nhà mình có bé nhỏ không ạ?", "has_children", {"has_children": True}, "Nhà mình vẫn có bé nhỏ đúng không ạ?"),
                 ("Ngân sách của mình khoảng bao nhiêu ạ?", "budget_vnd", {"budget_vnd": 5000000}, "Ngân sách của mình vẫn khoảng 5.000.000đ đúng không ạ?"),
                 ("Mình lấy màu gì ạ?", "color", {"color": "den"}, "Mình vẫn lấy màu đen đúng không ạ?")]
        for q, slot, known, expected in cases:
            new, rewritten, dropped, kept = self.rewrite(q, {slot}, known)
            self.assertEqual(new, expected, slot)
            self.assertEqual((len(rewritten), dropped, kept), (1, [], []))

    def test_confirmation_keeps_the_rest_of_the_reply(self):
        text = "Dạ em gợi ý mẫu này ạ. Phòng nhà mình rộng bao nhiêu mét vuông ạ? Mình cần em báo giá luôn không ạ?"
        new, rewritten, _, _ = self.rewrite(text, {"room_area_m2"}, {"room_area_m2": 25})
        self.assertTrue(new.startswith("Dạ em gợi ý mẫu này ạ."))
        self.assertIn("vẫn khoảng 25m² đúng không ạ?", new)
        self.assertTrue(new.endswith("báo giá luôn không ạ?"))

    def test_only_one_confirmation_per_slot_then_drop(self):
        text = "Dạ em ghi nhận rồi ạ. Phòng nhà mình rộng bao nhiêu mét vuông ạ?"
        new, rewritten, dropped, _ = self.rewrite(text, {"room_area_m2"}, {"room_area_m2": 25}, confirmed={"room_area_m2"})
        self.assertEqual(rewritten, [])
        self.assertEqual(len(dropped), 1)
        self.assertNotIn("rộng bao nhiêu", new)
        self.assertNotIn("đúng không", new)

    def test_never_empties_the_reply_when_dropping(self):
        text = "Phòng nhà mình rộng bao nhiêu mét vuông ạ?"
        new, _, dropped, kept = self.rewrite(text, {"room_area_m2"}, {"room_area_m2": 25}, confirmed={"room_area_m2"})
        self.assertEqual(new, text)
        self.assertEqual(dropped, [])
        self.assertEqual(kept[0]["slot"], "room_area_m2")

    def test_blocker_questions_and_unbanned_slots_untouched(self):
        text = "Chị đã trao đổi với gia đình chưa ạ? Phòng nhà mình rộng bao nhiêu mét vuông ạ?"
        new, rewritten, _, _ = self.rewrite(text, {"blocker"}, {"room_area_m2": 25})
        self.assertEqual(new, text)
        self.assertEqual(rewritten, [])

    def test_unknown_value_is_kept_with_reason(self):
        text = "Nhà mình có bé nhỏ không ạ?"
        new, rewritten, _, kept = self.rewrite(text, {"has_children"}, {})
        self.assertEqual((new, rewritten), (text, []))
        self.assertIn("chưa biết giá trị", kept[0]["why"])


class MissingSlotsAndPolicyTest(unittest.TestCase):
    def setUp(self):
        self.r = ProductRetriever()
        self.policy = ClarificationPolicy(self.r.rules)

    def test_asks_only_slots_that_change_the_outcome(self):
        res = self.r.shortlist({}, category="máy lọc không khí")
        asks = [m["slot"] for m in res.missing_slots]
        self.assertIn("has_children", asks)
        self.assertEqual(asks[0], "has_children")                                  # đúng thứ tự ưu tiên
        fans = self.r.shortlist({}, category="quạt")
        self.assertNotIn("has_children", [m["slot"] for m in fans.missing_slots])  # quạt không có khóa trẻ em → hỏi cũng vô ích
        self.assertNotIn("room_area_m2", [m["slot"] for m in fans.missing_slots])

    def test_policy_picks_one_question_and_skips_known_asked_forbidden(self):
        missing = self.r.shortlist({}, category="máy lọc không khí").missing_slots
        first = self.policy.next_questions(missing, known=[], asked=[], must_not_ask=[])
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["slot"], "has_children")
        nxt = self.policy.next_questions(missing, known=["has_children"], asked=[], must_not_ask=[])
        self.assertEqual(nxt[0]["slot"], "room_area_m2")
        nxt = self.policy.next_questions(missing, known=["has_children"], asked=["room_area_m2"], must_not_ask=[])
        self.assertEqual(nxt[0]["slot"], "budget_vnd")
        none = self.policy.next_questions(missing, known=["has_children", "room_area_m2", "budget_vnd"], asked=[], must_not_ask=[])
        self.assertEqual(none, [])
        banned = self.policy.next_questions(missing, known=[], asked=[], must_not_ask=["has_children", "room_area_m2", "budget_vnd"])
        self.assertEqual(banned, [])

    def test_strip_repeated_open_questions_keeps_blocker_and_confirm(self):
        from src.harness.extractor import extract_questions
        text = "Dạ em gợi ý mẫu này giá 5.200.000đ ạ. Phòng nhà mình rộng bao nhiêu mét vuông ạ? Chị đã trao đổi với gia đình chưa ạ?"
        qs = extract_questions(text)
        new, removed = self.policy.strip_repeated_questions(text, qs, {"room_area_m2", "blocker"})
        self.assertNotIn("rộng bao nhiêu", new)
        self.assertIn("trao đổi với gia đình", new)                                 # blocker luôn được hỏi tiếp
        self.assertEqual([q["slot"] for q in removed], ["room_area_m2"])

    def test_strip_never_leaves_empty_reply(self):
        text = "Phòng nhà mình rộng bao nhiêu mét vuông ạ?"
        from src.harness.extractor import extract_questions
        new, removed = self.policy.strip_repeated_questions(text, extract_questions(text), {"room_area_m2"})
        self.assertEqual(new, text)
        self.assertEqual(removed, [])


class OrchestratorIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _turn(self, text, phone="0984726714", date="2026-10-17"):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        return t, self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)

    def test_shortlist_tool_runs_inside_orchestrator_with_remembered_and_turn_slots(self):
        t, b = self._turn("phòng chị 25 mét vuông, nhà có bé nhỏ, ngân sách 5 triệu thôi em")
        self.orch.llm_client = FakeLLM({"calls": [("product.shortlist", {"category": "máy lọc không khí"})], "text": "Dạ em gợi ý mẫu này ạ."})
        _, calls, _ = self.orch.process_turn(t, b, current_date="2026-10-17")
        res = next(c["result"] for c in calls if c["name"] == "product.shortlist")
        self.assertEqual(res["recommendation"], "SKU-AP-Y")
        self.assertEqual(res["slots_used"]["has_children"], True)
        self.assertEqual(res["slots_used"]["room_area_m2"], 25)
        self.assertNotIn("ask_next", res)                                           # đủ slot → không hỏi thêm
        self.assertIn("has_children", res["do_not_ask"])

    def test_shortlist_asks_at_most_one_question_and_never_a_known_slot(self):
        t, b = self._turn("chị muốn mua máy lọc không khí cho nhà")
        self.orch.llm_client = FakeLLM({"calls": [("product.shortlist", {"category": "máy lọc không khí", "has_children": True})], "text": "Dạ ạ."})
        _, calls, _ = self.orch.process_turn(t, b, current_date="2026-10-17")
        res = next(c["result"] for c in calls if c["name"] == "product.shortlist")
        self.assertEqual(len(res["ask_next"]), 1)
        self.assertEqual(res["ask_next"][0]["slot"], "room_area_m2")                # has_children đã biết (LLM truyền) → không hỏi lại

    def test_repeated_question_about_known_slot_becomes_a_confirmation_not_removed(self):
        t, b = self._turn("phòng chị 25 mét vuông, nhà có bé nhỏ")
        self.orch.llm_client = FakeLLM({"calls": [], "text": "Dạ em đã ghi nhận ạ. Phòng nhà mình rộng bao nhiêu mét vuông ạ? Em sẽ gợi ý mẫu phù hợp cho mình nhé."})
        final, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertNotIn("rộng bao nhiêu", final)
        self.assertIn("Phòng nhà mình vẫn khoảng 25m² đúng không ạ?", final)       # đổi thành xác nhận, vẫn còn trong lời agent
        self.assertIn("gợi ý mẫu phù hợp", final)
        self.assertEqual([q["slot"] for q in meta["repeat_questions_rewritten"]], ["room_area_m2"])
        self.assertEqual(meta["repeat_questions_dropped"], [])
        qs = {q["slot"]: q["type"] for q in meta["questions"]}
        self.assertEqual(qs.get("room_area_m2"), "confirm")                          # không còn là câu hỏi mở (không tính lặp)

    def test_second_repeat_in_same_call_is_dropped_because_already_confirmed_once(self):
        ask = "Dạ em đã ghi nhận ạ. Phòng nhà mình rộng bao nhiêu mét vuông ạ? Em sẽ gợi ý mẫu phù hợp cho mình nhé."
        t, b = self._turn("phòng chị 25 mét vuông, nhà có bé nhỏ")
        self.orch.llm_client = FakeLLM({"calls": [], "text": ask})
        first, _, m1 = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertTrue(m1["repeat_questions_rewritten"])
        t2, b2 = self._turn("ừ vậy em tư vấn đi")
        self.orch.llm_client = FakeLLM({"calls": [], "text": ask})
        second, _, m2 = self.orch.process_turn(t2, b2, current_date="2026-10-17")
        self.assertNotIn("rộng bao nhiêu", second)
        self.assertNotIn("đúng không ạ", second)                                      # không xác nhận lần hai
        self.assertEqual([q["slot"] for q in m2["repeat_questions_dropped"]], ["room_area_m2"])
        self.assertIn("gợi ý mẫu phù hợp", second)

    def test_unknown_value_question_is_left_untouched(self):
        t, b = self._turn("alo chị muốn mua máy lọc không khí")
        self.orch.llm_client = FakeLLM({"calls": [], "text": "Dạ em chào chị ạ. Nhà mình có bé nhỏ không ạ?"})
        self.orch.process_turn(t, b, current_date="2026-10-17")                      # lần đầu hỏi: hợp lệ (slot chưa biết)
        t2, b2 = self._turn("chưa biết nữa em")
        self.orch.llm_client = FakeLLM({"calls": [], "text": "Dạ vâng ạ. Nhà mình có bé nhỏ không ạ?"})
        final, _, meta = self.orch.process_turn(t2, b2, current_date="2026-10-17")   # hỏi lại khi khách chưa trả lời: chưa có giá trị để xác nhận
        self.assertIn("có bé nhỏ không", final)
        self.assertEqual(meta["repeat_questions_rewritten"], [])

    def test_system_prompt_has_no_product_specific_rule_and_mentions_shortlist(self):
        t, b = self._turn("alo")
        msgs = self.orch._build_llm_messages(t, b, [], "2026-10-17", None)
        sys_prompt = msgs[0]["content"]
        self.assertIn("product.shortlist", sys_prompt)
        self.assertNotIn("child_safe_lock", sys_prompt)

    def test_tool_schema_exposes_shortlist_with_all_rule_slots(self):
        from src.llm.client import build_openai_tools
        tools = {t["function"]["name"]: t["function"] for t in build_openai_tools()}
        props = set(tools["product__shortlist"]["parameters"]["properties"])
        self.assertTrue(set(self.orch.retriever.rules.slots()) <= props)


if __name__ == "__main__":
    unittest.main()
