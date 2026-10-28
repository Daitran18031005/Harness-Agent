"""Bước 6 — Guardrail (A7, V5, N1, N2, N15). Ca lấy từ CHECKING Phụ lục B + kiểm tra 2026-10-20."""
import unittest
from tests import _helpers  # noqa: F401
from src.harness.guardrail import GuardrailAndFallback


def check(text, tool_calls=None, **ctx):
    context = {"tool_calls": tool_calls or []}
    context.update(ctx)
    return GuardrailAndFallback().check({"proposed_text": text}, {}, context)


class GuardrailTest(unittest.TestCase):
    def test_order_claim_without_tool_blocked(self):
        self.assertFalse(check("Dạ em đã lên đơn cho chị rồi ạ").approved)

    def test_order_claim_with_tool_allowed(self):
        self.assertTrue(check("Dạ em đã lên đơn cho chị rồi ạ", [{"name": "order.create"}]).approved)

    def test_ma_don_question_not_blocked(self):  # N1
        self.assertTrue(check("Dạ anh cho em xin mã đơn để em kiểm tra ạ?").approved)

    def test_exchange_with_update_and_order_id_allowed(self):  # N1
        d = check("Dạ em đã đổi size cho anh, mã đơn OD600003 ạ.", [{"name": "order.update"}])
        self.assertTrue(d.approved)
        self.assertIn("OD600003", d.sanitized_text)

    def test_exchange_claim_ok_if_update_earlier_in_call(self):
        d = check("Dạ em đã làm thủ tục đổi cho anh rồi ạ.", [], call_tool_names={"order.update"})
        self.assertTrue(d.approved)

    def test_cost_price_leak_blocked(self):  # A7
        self.assertNotIn("3.2 triệu", check("Dạ giá vốn khoảng 3.2 triệu ạ").sanitized_text)

    def test_cost_price_refusal_allowed(self):
        self.assertTrue(check("Dạ giá nhập là thông tin em không thể chia sẻ ạ.").approved)

    def test_internal_policy_wording_not_blocked(self):  # A7 false positive
        self.assertTrue(check("Dạ theo quy định nội bộ về đổi trả 7 ngày thì mình được đổi ạ.").approved)

    def test_claims_human_blocked(self):  # A7 / PB-07
        d = check("Dạ em là nhân viên thật 100% ạ")
        self.assertFalse(d.approved)
        self.assertIn("trợ lý", d.sanitized_text.lower())

    def test_cccd_masked(self):
        self.assertNotIn("012345678901", check("Số CCCD 012345678901 của chị").sanitized_text)

    def test_phone_not_masked(self):  # V5
        self.assertIn("0912345678", check("Số của chị là 0912345678 đúng không ạ?").sanitized_text)

    def test_price_not_in_tools_flagged(self):  # A7 — LLM mode
        tc = [{"name": "pricing.get_quote", "result": {"final_price_vnd": 5200000, "list_price_vnd": 5200000}}]
        d = check("Dạ máy giá 3.900.000đ ạ.", tc)
        self.assertEqual(d.violation_type, "hallucination_price_mismatch")

    def test_price_in_tools_ok(self):
        tc = [{"name": "pricing.get_quote", "result": {"final_price_vnd": 5200000, "list_price_vnd": 5200000}}]
        self.assertTrue(check("Dạ máy giá 5.200.000đ ạ.", tc).approved)

    def test_free_claim_when_fee_flagged(self):
        tc = [{"name": "order.update", "result": {"fee_vnd": 60000, "extra_payment_vnd": 0}}]
        d = check("Dạ đổi size không mất phí gì ạ.", tc)
        self.assertEqual(d.violation_type, "hallucination_fee_mismatch")


class GatewaySanitizeTest(unittest.TestCase):
    def test_internal_fields_stripped(self):  # N15
        from src.tools.mcp_gateway import MCPToolGateway, CRMTool, CatalogPricingTool, OrderCallbackTool
        gw = MCPToolGateway(CRMTool(), CatalogPricingTool(), OrderCallbackTool())
        res = gw.execute_tool("pricing.get_quote", {"sku": "SKU-AP-Y", "on": "2026-10-15"}, caller="HarnessOrchestrator")
        self.assertNotIn("_internal_price_floor_vnd", res)
        self.assertIn("final_price_vnd", res)


if __name__ == "__main__":
    unittest.main()
