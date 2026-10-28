"""Bước 7 — Normalizer & PII (V1–V4). Các ca lấy từ CHECKING Phụ lục B."""
import unittest
from tests import _helpers  # noqa: F401
from src.channels.normalizer import RequestNormalizer, InputChannel


def norm(text):
    return RequestNormalizer().normalize(text, InputChannel.HOTLINE, "0900000000")


class NormalizerTest(unittest.TestCase):
    def test_itn_fixed_cases_still_work(self):
        self.assertIn("249.000", norm("hai trăm bốn chín k").normalized_text)
        self.assertIn("4.890.000", norm("bốn triệu tám trăm chín mươi").normalized_text)

    def test_itn_general(self):  # V3
        self.assertIn("3.900.000", norm("ba triệu chín trăm nghìn").normalized_text)
        self.assertIn("5.500.000", norm("tầm năm triệu rưỡi thôi").normalized_text)
        self.assertIn("5.200.000", norm("giá năm triệu hai đúng không").normalized_text)

    def test_itn_digit_units(self):
        self.assertIn("249.000", norm("249k").normalized_text)
        self.assertIn("5.000.000", norm("5tr").normalized_text)
        self.assertIn("1.521.000", norm("giá 1521k đúng không").normalized_text)

    def test_teencode_k_means_khong(self):  # V1
        t = norm("sp nay co ship cod k a").normalized_text
        self.assertNotIn("nghìn", t)
        self.assertIn("không", t)

    def test_sai_is_not_size(self):  # V2
        self.assertIn("sai rồi", norm("chị nói sai rồi em").normalized_text)

    def test_single_letter_not_replaced_in_product_names(self):
        t = norm("máy lọc y giá bao nhiêu").normalized_text
        self.assertIn("lọc y", t)
        self.assertIn("chị có hỏi", norm("hôm trc c có hỏi máy lọc y").normalized_text)

    def test_asr_fixes(self):
        self.assertIn("size L", norm("sai z eo màu đen").normalized_text)
        self.assertIn("Xiaomi", norm("xiao mi 4 pro").normalized_text)

    def test_entities(self):
        t = norm("phòng 25m2 nhà có bé nhỏ")
        self.assertEqual(t.extracted_entities.get("room_area_m2"), 25.0)
        self.assertTrue(t.extracted_entities.get("has_children"))

    def test_phone_entity(self):
        t = norm("sdt minh 0994893949 de minh goi hotline sau nhe")
        self.assertEqual(t.extracted_entities.get("phone"), "0994893949")

    def test_pii_masked_in_normalized_text(self):  # V4
        t = norm("CCCD em 012345678901 stk 1903456789012")
        self.assertNotIn("012345678901", t.normalized_text)
        self.assertNotIn("1903456789012", t.normalized_text)

    def test_phone_kept_in_text(self):
        self.assertIn("0912345678", norm("số chị 0912345678 nhé").normalized_text)


class ITNLiteralZeroAndCountNounTest(unittest.TestCase):
    """Sửa ITN v2 (lỗi chung của tiếng Việt, không chỉnh theo tập test): 'lẻ/không' sau hàng nghìn là chữ số đơn vị; số đếm trước danh từ đơn vị
    (đơn, chiếc, cái, máy, bộ, đôi…) không thuộc số tiền."""

    def f(self, text):
        from src.channels.normalizer import itn_number_words
        return itn_number_words(text)

    def test_le_after_thousand_is_units(self):
        self.assertEqual(self.f("sáu trăm nghìn lẻ một"), "600.001")
        self.assertEqual(self.f("sáu trăm nghìn không trăm lẻ một"), "600.001")
        self.assertEqual(self.f("hai triệu không trăm lẻ năm nghìn"), "2.005.000")
        self.assertEqual(self.f("một triệu lẻ năm"), "1.000.005")

    def test_le_inside_the_group_still_means_that_group(self):
        self.assertEqual(self.f("sáu trăm lẻ một nghìn"), "601.000")
        self.assertEqual(self.f("hai triệu lẻ một nghìn"), "2.001.000")

    def test_count_before_unit_noun_is_not_money(self):
        for noun in ("đơn", "chiếc", "cái", "máy", "bộ", "đôi", "tháng"):
            self.assertEqual(self.f(f"mười triệu một {noun}"), f"10.000.000 một {noun}", noun)
        self.assertEqual(self.f("tám triệu một chiếc áo"), "8.000.000 một chiếc áo")
        self.assertEqual(self.f("ba triệu hai trăm nghìn một chiếc"), "3.200.000 một chiếc")
        self.assertEqual(self.f("năm triệu hai đôi giày"), "5.000.000 hai đôi giày")

    def test_shorthand_and_plain_amounts_unchanged(self):
        for spoken, written in (("năm triệu hai", "5.200.000"), ("năm triệu hai trăm nghìn", "5.200.000"),
                                ("bốn triệu tám trăm chín mươi nghìn", "4.890.000"), ("hai triệu rưỡi", "2.500.000"),
                                ("một triệu một trăm nghìn", "1.100.000"), ("mười triệu một", "10.100.000"), ("hai trăm bốn chín k", "249.000"),
                                ("mười triệu", "10.000.000"), ("bốn triệu tám trăm chín mươi", "4.890.000")):
            self.assertEqual(self.f(spoken), written, spoken)

    def test_noun_rule_needs_a_money_magnitude_and_exactly_one_trailing_digit_word(self):
        self.assertEqual(self.f("một đơn"), "một đơn")                       # không có bậc nghìn/triệu → không đổi
        self.assertEqual(self.f("năm triệu hai trăm máy"), "5.200.000 máy")  # nhiều từ số sau triệu: là số tiền, không phải số đếm
        self.assertEqual(self.f("mười triệu hai mươi máy"), "10.020.000 máy")

    def test_digit_form_follows_the_same_rule(self):
        from src.channels.normalizer import itn_digit_units
        self.assertEqual(itn_digit_units("10tr 1 đơn"), "10.000.000 1 đơn")
        self.assertEqual(itn_digit_units("5tr2 máy"), "5.000.000 2 máy")
        self.assertEqual(itn_digit_units("5tr2"), "5.200.000")
        self.assertEqual(itn_digit_units("2,5 triệu"), "2.500.000")

    def test_full_normalizer_gives_money_in_a_sentence(self):
        from src.channels.normalizer import InputChannel, RequestNormalizer
        out = RequestNormalizer().normalize("hạn mức mười triệu một đơn thôi", InputChannel.HOTLINE, "0900000000").normalized_text
        self.assertIn("10.000.000", out)
        self.assertNotIn("10.100.000", out)
        out = RequestNormalizer().normalize("mã sáu trăm nghìn lẻ một", InputChannel.HOTLINE, "0900000000").normalized_text
        self.assertIn("600.001", out)


if __name__ == "__main__":
    unittest.main()
