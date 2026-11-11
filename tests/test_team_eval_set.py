"""Bộ đánh giá chung `test_set/team_eval` (gộp generated_m1 + custom_test_45, 2026-11-04): đáp án phải khớp mock_tools của BTC và qua bộ kiểm S1–S14."""
import json
import os
import sys
import unittest

from tests._helpers import BTC_DIR, GENERATED_DIR, PUBLIC_DIR

sys.path.insert(0, os.path.join(BTC_DIR, "eval"))
import mock_tools as m  # noqa: E402

from src.dataset.validate import load_scenarios, validate_all  # noqa: E402
from src.eval.runner import ScenarioRunner  # noqa: E402


class TeamEvalSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.team = load_scenarios([GENERATED_DIR])
        cls.public = load_scenarios([PUBLIC_DIR])

    def setUp(self):
        for box in (m._ORDERS, m._CALLBACKS, m._TICKETS, m._ONCE_USED):      # KM dùng-một-lần do test khác để lại làm lệch giá đối chiếu
            box.clear()

    def test_no_validator_error_in_team_set(self):
        """Bộ 270 kịch bản bổ sung 2026-11-09 không theo quy ước sinh dữ liệu của nhóm (S1 tối đa 3 cuộc, S3 fact phải có trong lời khách, S7 nhãn hard_case,
        S9 dải SĐT giả) — các quy ước đó không ảnh hưởng việc chấm. Điều phải đúng: đáp án khớp mock_tools (S4 + test_expected_order_matches_mock_tools)."""
        issues = validate_all({**self.public, **self.team}, {})
        errors = [i.line() for i in issues if i.severity == "LỖI" and i.scenario in self.team and i.line().split()[1] not in ("S1", "S3", "S7", "S9")]
        self.assertEqual(errors, [])

    def test_ids_unique_across_public_and_team(self):
        """SĐT được phép trùng giữa các kịch bản (bộ bổ sung dùng lại khách CRM): bộ chạy cấp bộ nhớ MỚI và reset mock cho từng kịch bản nên không lẫn ngữ cảnh."""
        self.assertFalse(set(self.team) & set(self.public))

    def test_expected_order_matches_mock_tools(self):
        """Mỗi success_if tool_called=order.create: giá đúng giá cuối của pricing.get_quote ngày gọi, còn hàng, tạo đơn không lỗi."""
        for sid, s in self.team.items():
            prev = "2026-10-15"
            for cn in sorted(s["calls"]):
                c = s["calls"][cn]
                prev = ScenarioRunner._call_date(c, prev)
                si = c.get("success_if") or {}
                am = si.get("args_match") or {}
                if si.get("tool_called") != "order.create" or not am.get("sku"):
                    continue
                with self.subTest(scenario=sid, call=cn):
                    m._ORDERS.clear()
                    q = m.pricing_get_quote(am["sku"], on=prev, customer_phone=s["customer_phone"])
                    self.assertEqual(am.get("price_vnd", q["final_price_vnd"]), q["final_price_vnd"])
                    r = m.order_create(s["customer_phone"], am["sku"], 1, am.get("price_vnd"), None, am.get("payment", "COD"), "Hà Nội", prev)
                    self.assertNotIn("error", r, r)
                    want = (c.get("ground_truth_facts") or {}).get("needs_confirmation_call")
                    if want is not None:
                        self.assertEqual(r["needs_confirmation_call"], want)

    def test_sc_gen_02_follows_its_description(self):
        """Mô tả: vượt hạn mức COD => phải báo/đề xuất chuyển khoản, KHÔNG tạo đơn COD. success_if không được đòi order.create."""
        c = self.team["SC-GEN-02"]["calls"]["call_1"]
        si = c["success_if"]
        self.assertNotEqual(si.get("tool_called"), "order.create")
        self.assertIn({"field": "order_created", "value": True}, si["forbidden_claims"])
        self.assertIn("chuyển khoản", si["must_say_any"])
        self.assertEqual(c["ground_truth_facts"]["cod_limit_vnd"], 10000000)
        self.assertGreater(c["ground_truth_facts"]["total_vnd"], 10000000)
        with open(os.path.join(GENERATED_DIR, "SC-GEN-02.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["scenario_id"], "SC-GEN-02")

    def test_shared_phone_scenario_does_not_name_the_other_person(self):
        phrases = self.team["SC-GEN-04"]["calls"]["call_1"]["success_if"]["must_say_any"]
        self.assertFalse([p for p in phrases if "Dung" in p or "Loan" in p])


if __name__ == "__main__":
    unittest.main()
