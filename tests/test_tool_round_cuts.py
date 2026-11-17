"""17/11: hai cờ cắt vòng LLM cho model hay gọi tool (gpt-5.4-mini): shortlist gắn sẵn KM/quà; mô tả search_policy chuyển câu KM của một sản phẩm sang pricing.get_quote."""
import os
import unittest
from unittest import mock

from tests.test_order_gate import GateBase, NEW_PHONE

SHORTLIST = ("product.shortlist", {"category": "máy lọc không khí", "room_area_m2": 20})


class ShortlistFullQuoteTest(GateBase):
    def items(self, on):
        import src.harness.orchestrator as O
        with mock.patch.object(O, "SHORTLIST_FULL_QUOTE", on):
            _, tc, _ = self.turn(NEW_PHONE, "chị hỏi máy lọc không khí cho phòng 20m2", [SHORTLIST], "x")
        res = next(c for c in tc if c["name"] == "product.shortlist")["result"]
        return res["items"], res.get("price_note", "")

    def test_flag_on_attaches_promos_and_says_no_requote(self):
        items, note = self.items(True)
        self.assertTrue(any("applied_promos" in (i.get("today") or {}) for i in items), items)
        self.assertIn("KHÔNG gọi lại pricing.get_quote", note)

    def test_flag_off_unchanged(self):
        items, note = self.items(False)
        self.assertFalse(any("today" in i for i in items))
        self.assertNotIn("KHÔNG gọi lại", note)


class PolicyToolNoPromoTest(unittest.TestCase):
    def desc(self, flag):
        from src.llm.client import build_openai_tools
        with mock.patch.dict(os.environ, {"POLICY_TOOL_NO_PROMO": flag}):
            return next(t for t in build_openai_tools() if t["function"]["name"] == "search_policy")["function"]["description"]

    def test_flag_routes_product_promo_to_quote(self):
        self.assertIn("pricing.get_quote", self.desc("on"))
        self.assertNotIn("pricing.get_quote", self.desc(""))


if __name__ == "__main__":
    unittest.main()
