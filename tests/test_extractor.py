"""Bước 10 — trích claims/questions từ lời agent (B6, B7, N10)."""
import unittest
from tests import _helpers  # noqa: F401
from src.harness.extractor import extract_claims, extract_questions


def fields(claims):
    return {(c["field"], c["value"]) for c in claims}


class ClaimsTest(unittest.TestCase):
    def test_price_claim_from_text(self):
        cl = fields(extract_claims("Dạ mẫu AirPure Y giá 5.200.000đ, còn hàng ạ.", []))
        self.assertIn(("price_vnd", 5200000), cl)
        self.assertIn(("in_stock", True), cl)

    def test_free_exchange_claim(self):  # SAMPLE-03 lỗi "không mất phí"
        cl = fields(extract_claims("Dạ đổi size không mất phí gì anh nhé.", []))
        self.assertIn(("exchange_fee_vnd", 0), cl)

    def test_fee_amount(self):
        cl = fields(extract_claims("Dạ lần này phí đổi là 60.000đ ạ.", []))
        self.assertIn(("exchange_fee_vnd", 60000), cl)

    def test_list_price(self):
        cl = fields(extract_claims("Giá gốc 1.690.000đ, sau giảm còn 1.521.000đ ạ.", []))
        self.assertIn(("list_price_vnd", 1690000), cl)
        self.assertIn(("price_vnd", 1521000), cl)

    def test_out_of_stock_and_restock(self):
        cl = fields(extract_claims("Dạ mẫu này đang hết hàng, dự kiến về ngày 19/10 ạ.", [], call_date="2026-10-15"))
        self.assertIn(("in_stock", False), cl)
        self.assertIn(("restock_date", "2026-10-19"), cl)

    def test_ai_identity(self):
        self.assertIn(("is_human", False), fields(extract_claims("Dạ em là trợ lý ảo AI của shop ạ.", [])))

    def test_warranty_and_return(self):
        cl = fields(extract_claims("Máy bảo hành 24 tháng, đổi trả trong 7 ngày ạ.", []))
        self.assertIn(("warranty_months", 24), cl)
        self.assertIn(("return_days", 7), cl)


class QuestionsTest(unittest.TestCase):
    def test_open_area(self):
        q = extract_questions("Dạ phòng mình rộng bao nhiêu mét vuông ạ?")
        self.assertEqual([(x["slot"], x["type"]) for x in q], [("room_area_m2", "open")])

    def test_confirm_area(self):
        q = extract_questions("Vẫn là phòng 25m² đúng không ạ?")
        self.assertEqual([(x["slot"], x["type"]) for x in q], [("room_area_m2", "confirm")])

    def test_unlabeled_question_counted(self):
        q = extract_questions("Mình muốn giao vào buổi nào ạ?")
        self.assertEqual(len(q), 1)

    def test_not_a_question(self):
        self.assertEqual(extract_questions("Dạ em cảm ơn chị ạ."), [])


class ClaimsRegressionTest(unittest.TestCase):
    """Ca rút từ lời agent thật trong runs/*.jsonl (bộ trích từng gán nhầm)."""

    def test_expired_promo_is_not_out_of_stock(self):
        cl = fields(extract_claims("Tuy nhiên chương trình khuyến mãi RUN2-SALE đã hết hạn ạ.", []))
        self.assertIn(("promo_active", False), cl)
        self.assertIn(("promo_RUN2-SALE_active", False), cl)
        self.assertFalse([c for c in cl if c[0] == "in_stock"])

    def test_discount_amount_is_not_the_price(self):
        cl = fields(extract_claims("Em xin lỗi vì không còn khuyến mãi giảm giá 500.000đ như chị hỏi, giá hiện tại là 4.890.000đ ạ.", []))
        self.assertIn(("discount_vnd", 500000), cl)
        self.assertIn(("price_vnd", 4890000), cl)
        self.assertNotIn(("price_vnd", 500000), cl)

    def test_gift_value_is_not_a_claim(self):
        cl = fields(extract_claims("Máy giá 5.200.000đ, tặng kèm màng lọc trị giá 690.000đ ạ.", []))
        self.assertIn(("price_vnd", 5200000), cl)
        self.assertFalse([c for c in cl if c[1] == 690000])

    def test_tool_result_assigns_role_without_keyword(self):
        tc = [{"name": "pricing.get_quote", "args": {}, "result": {"final_price_vnd": 1521000, "list_price_vnd": 1690000}}]
        cl = fields(extract_claims("Dạ 1.521.000đ ạ, còn 1.690.000đ nếu mua lẻ.", tc))
        self.assertIn(("price_vnd", 1521000), cl)
        self.assertIn(("list_price_vnd", 1690000), cl)

    def test_contradictory_stock_statements_skipped(self):
        cl = fields(extract_claims("Size 40 hết hàng nhưng size 41 còn hàng ạ.", []))
        self.assertFalse([c for c in cl if c[0] == "in_stock"])

    def test_delivery_days_single_and_range(self):
        self.assertIn(("delivery_days", 2), fields(extract_claims("Bên em giao hàng trong 2 ngày ạ.", [])))
        self.assertFalse([c for c in fields(extract_claims("Giao hàng trong 2-3 ngày ạ.", [])) if c[0] == "delivery_days"])

    def test_restock_date_rolls_to_next_year(self):
        cl = fields(extract_claims("Mẫu này hết hàng, dự kiến về ngày 5/1 ạ.", [], call_date="2026-12-30"))
        self.assertIn(("restock_date", "2027-01-05"), cl)

    def test_freeship_and_exchange_window(self):
        cl = fields(extract_claims("Đơn này được miễn phí vận chuyển, và đổi size trong 7 ngày ạ.", []))
        self.assertIn(("freeship", True), cl)
        self.assertIn(("exchange_window_days", 7), cl)
        self.assertFalse([c for c in cl if c[0] == "exchange_fee_vnd"])      # "miễn phí" ở đây là ship, không phải phí đổi

    def test_claims_human(self):
        self.assertIn(("is_human", True), fields(extract_claims("Dạ em là nhân viên thật 100% ạ.", [])))

    def test_warranty_in_years(self):
        self.assertIn(("warranty_months", 24), fields(extract_claims("Máy bảo hành chính hãng 2 năm ạ.", [])))

    def test_thousands_dots_do_not_split_clause(self):
        cl = fields(extract_claims("Giá gốc 1.690.000đ.", []))
        self.assertIn(("list_price_vnd", 1690000), cl)

    def test_claims_have_text_snippet(self):
        c = extract_claims("Dạ máy giá 5.200.000đ ạ.", [])[0]
        self.assertEqual(set(c), {"field", "value", "text"})
        self.assertIn("5.200.000", c["text"])


class QuestionsRegressionTest(unittest.TestCase):
    def test_multiple_questions_counted(self):
        q = extract_questions("Dạ phòng mình rộng bao nhiêu mét vuông ạ? Nhà có trẻ nhỏ không ạ? Ngân sách mình tầm bao nhiêu ạ?")
        self.assertEqual([x["slot"] for x in q], ["room_area_m2", "has_children", "budget_vnd"])

    def test_question_without_question_mark(self):
        q = extract_questions("Mình muốn giao hàng về địa chỉ cũ đúng không ạ")
        self.assertEqual([(x["slot"], x["type"]) for x in q], [("delivery_address", "confirm")])

    def test_price_with_dots_does_not_break_sentences(self):
        q = extract_questions("Máy giá 5.200.000đ ạ. Mình chốt đơn luôn nhé? Địa chỉ giao hàng của mình là gì ạ?")
        self.assertEqual(len(q), 2)

    def test_statement_is_not_question(self):
        self.assertEqual(extract_questions("Dạ em xin phép chuyển máy cho nhân viên nhé."), [])

    def test_open_vs_confirm_with_order_id(self):
        q = extract_questions("Anh cho em xin mã đơn để em kiểm tra ạ? Đơn OD600001 đúng không ạ?")
        self.assertEqual([(x["slot"], x["type"]) for x in q], [("order_id", "open"), ("order_id", "confirm")])


class PromoCodeFalsePositiveTest(unittest.TestCase):
    """Lời agent thật ở bước 15 giai đoạn A: tên sản phẩm rút gọn ('AP-Y', 'SN-RUN2') bị gán nhầm thành promo_code."""

    def test_short_product_names_are_not_promo_codes(self):
        for text in ("Dạ em chào chị Hoa, hôm 15/10 bên em có tư vấn mẫu AP-Y giá ưu đãi 5.200.000đ ạ.",
                     "Dạ chị Hoa, em đã tạo đơn với sản phẩm AP-Y. Đơn hàng của chị có mã số là OD600001.",
                     "Dạ đúng rồi ạ, giá ưu đãi cho mẫu SN-RUN2 là 1.521.000đ, đã bao gồm khuyến mãi rồi ạ."):
            self.assertFalse([c for c in extract_claims(text, []) if c["field"].startswith("promo")], text)

    def test_real_promo_code_still_extracted(self):
        cl = fields(extract_claims("Dạ chị được áp dụng mã RUN2-SALE giảm 10% ạ.", []))
        self.assertIn(("promo_code", "RUN2-SALE"), cl)
        cl2 = fields(extract_claims("Dạ khuyến mãi AP-SEP đã hết hạn rồi ạ.", []))
        self.assertIn(("promo_AP-SEP_active", False), cl2)


class PriceDeltaTest(unittest.TestCase):
    """Bước 15 giai đoạn B (SAMPLE-03): 'size 43 giá sẽ nhích lên 50.000đ' bị trích nhầm thành price_vnd=50000."""

    def test_variant_delta_is_not_the_price(self):
        cl = fields(extract_claims("Nếu anh chọn size 43, giá sẽ nhích lên 50.000đ so với size 39.", []))
        self.assertIn(("variant_price_delta_vnd", 50000), cl)
        self.assertFalse([c for c in cl if c[0] == "price_vnd"])

    def test_price_and_delta_in_one_text(self):
        cl = fields(extract_claims("Giày size 39 giá 890.000đ, size 43 chênh lệch 50.000đ ạ.", []))
        self.assertIn(("price_vnd", 890000), cl)
        self.assertIn(("variant_price_delta_vnd", 50000), cl)


if __name__ == "__main__":
    unittest.main()
