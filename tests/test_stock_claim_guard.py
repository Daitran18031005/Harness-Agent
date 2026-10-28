"""Guardrail 2b: lời báo hết hàng phải khớp kết quả `inventory.check` của cuộc gọi (lỗi UI: "38 đen không có sẵn" trong khi tool ghi còn hàng)."""
import unittest

from src.harness.guardrail import GuardrailAndFallback


def inv(sku, in_stock):
    return {"name": "inventory.check", "args": {"sku": sku}, "result": {"sku": sku, "in_stock": in_stock, "qty": 5 if in_stock else 0}}


class StockClaimGuardTest(unittest.TestCase):
    def check(self, text, calls):
        return GuardrailAndFallback().check({"proposed_text": text, "action_type": "speak"}, {}, {"tool_calls": calls, "call_tool_calls": calls})

    def test_out_of_stock_claim_contradicting_the_tool_is_replaced(self):
        d = self.check("Dạ size 38 màu đen hiện không có sẵn ạ. Anh cho em xin địa chỉ nhận hàng nhé.", [inv("SKU-SN-RUN2-38-DEN", True)])
        self.assertFalse(d.approved)
        self.assertEqual(d.violation_type, "stock_claim_mismatch")
        self.assertIn("Giày chạy bộ RunLite 2 Pro size 38 màu đen hiện còn hàng", d.sanitized_text)
        self.assertNotIn("không có sẵn", d.sanitized_text)
        self.assertIn("xin địa chỉ nhận hàng", d.sanitized_text)                    # phần còn lại của câu trả lời được giữ

    def test_claims_consistent_with_the_tool_are_left_alone(self):
        d = self.check("Dạ size 38 màu xám hiện hết hàng ạ.", [inv("SKU-SN-RUN2-38-XAM", False)])
        self.assertTrue(d.approved)
        self.assertEqual(d.sanitized_text, "Dạ size 38 màu xám hiện hết hàng ạ.")

    def test_no_inventory_evidence_means_no_intervention(self):
        self.assertTrue(self.check("Dạ mẫu này hiện hết hàng ạ.", []).approved)

    def test_mixed_evidence_means_no_intervention(self):
        calls = [inv("SKU-JK-DWN-M-DEN", False), inv("SKU-JK-DWN-M-BE", True)]
        d = self.check("Dạ size M màu đen hết hàng, còn màu be ạ.", calls)
        self.assertTrue(d.approved)
        self.assertIn("hết hàng", d.sanitized_text)

    def test_latest_result_per_variant_wins(self):
        calls = [inv("SKU-SN-RUN2-38-DEN", False), inv("SKU-SN-RUN2-38-DEN", True)]
        self.assertFalse(self.check("Dạ mẫu này hết hàng rồi ạ.", calls).approved)

    def test_expiry_negation_and_other_wording_do_not_trigger(self):
        calls = [inv("SKU-SN-RUN2-38-DEN", True)]
        for ok in ("Dạ khuyến mãi đã hết hạn từ ngày 7/10 ạ.", "Dạ mẫu này chưa hết hàng đâu ạ.", "Dạ size 38 màu đen còn hàng ạ."):
            d = self.check(ok, calls)
            self.assertTrue(d.approved, ok)
            self.assertEqual(d.sanitized_text, ok)

    def test_parent_level_evidence_is_not_evidence_about_a_size_or_color(self):
        # ui_replay 2026-10-27: inventory.check trên SKU cha "còn hàng", agent đúng khi nói 38 xám hết → guard từng sửa nhầm thành "còn hàng"
        d = self.check("Dạ size 38 màu xám hiện đã hết hàng ạ.", [inv("SKU-SN-RUN2", True)])
        self.assertTrue(d.approved)
        self.assertIn("hết hàng", d.sanitized_text)
        self.assertTrue(self.check("Dạ hiện hết hàng rồi ạ.", [inv("SKU-AP-Y", True)]).approved)      # sản phẩm không biến thể: không đủ bằng chứng theo size/màu

    def test_two_variants_checked_each_sentence_judged_on_its_own(self):
        # ui_replay 2026-10-27: 38 xám hết thật, 38 đen còn — bằng chứng hỗn hợp trước đây khiến guard bỏ qua cả câu sai
        calls = [inv("SKU-SN-RUN2-38-XAM", False), inv("SKU-SN-RUN2-38-DEN", True)]
        d = self.check("Dạ size 38 màu xám hết hàng ạ. Dạ size 38 màu đen không có sẵn ạ.", calls)
        self.assertEqual(d.violation_type, "stock_claim_mismatch")
        self.assertIn("màu xám hết hàng", d.sanitized_text)
        self.assertIn("size 38 màu đen hiện còn hàng", d.sanitized_text)
        self.assertTrue(self.check("Dạ size 38 màu xám hết hàng ạ.", calls).approved)
        self.assertTrue(self.check("Dạ size 38 hết hàng ạ.", calls).approved)                # không rõ nói biến thể nào: không can thiệp

    def test_sentence_about_another_size_or_color_is_not_touched(self):
        calls = [inv("SKU-SN-RUN2-38-DEN", True)]
        self.assertTrue(self.check("Dạ size 38 màu xám hiện hết hàng ạ.", calls).approved)       # xám ≠ đen đã tra
        self.assertTrue(self.check("Dạ size 37 hiện hết hàng ạ.", calls).approved)               # 37 ≠ 38
        self.assertFalse(self.check("Dạ size 38 màu đen hiện hết hàng ạ.", calls).approved)      # đúng biến thể đã tra → sửa


if __name__ == "__main__":
    unittest.main()
