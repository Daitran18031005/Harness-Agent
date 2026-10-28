"""spoken_form (ITN ngược) — số bằng chữ đúng quy ước BTC và ITN(spoken_form(x)) trả lại đúng các số trong x."""
import re
import unittest

from src.channels.asr_postprocess import normalize_transcript, spoken_small_numbers
from src.dataset.spoken import number_to_words, spoken_form


def numbers_back(spoken: str) -> set:
    """Các số tìm lại được sau ITN của dự án (cùng đường như hypotheses): số tiền, SĐT, số nhỏ trước đơn vị."""
    norm = spoken_small_numbers(normalize_transcript(spoken).normalized_text)
    return {int(re.sub(r"[.,]", "", m)) for m in re.findall(r"\d[\d.,]*\d|\d", norm)}


class NumberWordsTest(unittest.TestCase):
    def test_btc_ground_truth_phrases(self):
        self.assertEqual(number_to_words(5_200_000), "năm triệu hai trăm nghìn")
        self.assertEqual(number_to_words(4_890_000), "bốn triệu tám trăm chín mươi nghìn")
        self.assertEqual(number_to_words(25), "hai mươi lăm")
        self.assertEqual(number_to_words(41), "bốn mươi mốt")
        self.assertEqual(number_to_words(36), "ba mươi sáu")
        self.assertEqual(number_to_words(312_456), "ba trăm mười hai nghìn bốn trăm năm mươi sáu")
        self.assertEqual(number_to_words(521_338), "năm trăm hai mươi mốt nghìn ba trăm ba mươi tám")

    def test_edge_numbers(self):
        self.assertEqual(number_to_words(0), "không")
        self.assertEqual(number_to_words(10), "mười")
        self.assertEqual(number_to_words(15), "mười lăm")
        self.assertEqual(number_to_words(105), "một trăm lẻ năm")
        self.assertEqual(number_to_words(600_001), "sáu trăm nghìn không trăm lẻ một")
        self.assertEqual(number_to_words(1_000), "một nghìn")
        self.assertEqual(number_to_words(2_000_000), "hai triệu")
        self.assertEqual(number_to_words(1_521_000), "một triệu năm trăm hai mươi mốt nghìn")
        self.assertEqual(number_to_words(2_001_000), "hai triệu không trăm lẻ một nghìn")


class SpokenFormTest(unittest.TestCase):
    def test_no_digits_or_punctuation_left_and_lowercase(self):
        out = spoken_form("Dạ, giá 5.200.000đ ạ! Phòng 25m², size 41, giao 2 ngày; gọi 0982345678 nhé (OD600001) — 15/10, hết 22/10.")
        self.assertFalse(re.search(r"\d", out), out)
        self.assertFalse(re.search(r"[^\w\s]", out), out)
        self.assertEqual(out, out.lower())

    def test_matches_btc_style(self):
        self.assertEqual(spoken_form("giá 5.200.000đ"), "giá năm triệu hai trăm nghìn")
        self.assertEqual(spoken_form("phòng 25m²"), "phòng hai mươi lăm mét vuông")
        self.assertEqual(spoken_form("đến hết ngày 22/10"), "đến hết ngày hai mươi hai tháng mười")
        self.assertEqual(spoken_form("hôm 15/10"), "hôm mười lăm tháng mười")
        self.assertEqual(spoken_form("mẫu AirPure Y"), "mẫu e pia y")
        self.assertEqual(spoken_form("thanh toán COD"), "thanh toán cê ô đê")
        self.assertEqual(spoken_form("size 41 màu đen"), "size bốn mươi mốt màu đen")
        self.assertEqual(spoken_form("RunLite 2 Pro"), "run lai hai pro")
        self.assertEqual(spoken_form("Karofi 9 lõi"), "ka rô phi chín lõi")

    def test_alphanumeric_model_codes(self):
        self.assertEqual(spoken_form("Spectra S1"), "xpec tra ét một")
        self.assertEqual(spoken_form("Quạt đứng Senko TS16"), "quạt đứng sen cô ti ét mười sáu")
        self.assertEqual(spoken_form("Samsung AX40"), "sam sung ây ích bốn mươi")
        self.assertEqual(spoken_form("mã đơn OD600001"), "mã đơn ô đê sáu không không không không một")      # OD… vẫn là mã đơn

    def test_phone_and_order_id(self):
        self.assertEqual(spoken_form("0982345678"), "không chín tám hai ba bốn năm sáu bảy tám")
        # mã đơn đọc TỪNG CHỮ SỐ: đọc như một con số bị ITN của normalizer hiểu sai ("sáu trăm nghìn lẻ một" → 600.100)
        self.assertEqual(spoken_form("mã đơn OD312456"), "mã đơn ô đê ba một hai bốn năm sáu")
        from src.channels.asr_postprocess import extract_hypothesis_entities
        self.assertEqual(extract_hypothesis_entities(spoken_form("mã đơn của chị là OD600001 ạ"))["order_id"], "OD600001")

    def test_customer_style_amounts(self):
        self.assertEqual(spoken_form("ngân sách tầm 5 triệu"), "ngân sách tầm năm triệu")
        self.assertEqual(spoken_form("khoảng 2,5 triệu"), "khoảng hai triệu năm trăm nghìn")
        self.assertEqual(spoken_form("bên kia bán 4590k"), "bên kia bán bốn triệu năm trăm chín mươi nghìn")    # 4590k = 4.590.000
        self.assertEqual(spoken_form("áo 249k"), "áo hai trăm bốn mươi chín nghìn")
        self.assertEqual(spoken_form("giảm 10%"), "giảm mười phần trăm")

    def test_round_trip_through_project_itn(self):
        cases = {
            "Dạ giá 5.200.000đ ạ": {5_200_000},
            "giá 4.890.000đ còn hàng": {4_890_000},
            "phòng 25m² nhà có bé 2 tuổi": {25},                                  # "2 tuổi": ITN đã KHÓA không có đơn vị "tuổi" → không đòi hỏi
            "số của anh 0917223456 nhé": {917223456},                       # SĐT: ITN trả lại chuỗi 10 số (bỏ 0 đầu khi so số)
            "gói 1.521.000đ miễn phí ship đơn từ 2.000.000đ": {1_521_000, 2_000_000},
            "phụ thu 219.000đ": {219_000},
            "bảo hành 36 tháng đổi trả 7 ngày": {36, 7},
            "khuyến mãi hết ngày 22/10": {22},                                     # tháng được kiểm bằng extract_promo_expiry (test riêng)
            "ngân sách tầm 5 triệu": {5_000_000},
        }
        for written, expected in cases.items():
            back = numbers_back(spoken_form(written))
            missing = {e for e in expected if e not in back}
            self.assertFalse(missing, f"{written!r} → {spoken_form(written)!r}: thiếu {missing} (tìm lại được {back})")

    def test_dates_round_trip_through_promo_expiry_extractor(self):
        from src.channels.asr_entities import extract_promo_expiry
        spoken = spoken_form("Khuyến mãi đến hết ngày 22/10 ạ")
        self.assertEqual(extract_promo_expiry(spoken, "2026-10-15"), "2026-10-22")

    def test_large_batch_of_amounts_round_trips(self):
        for v in (289_000, 490_000, 590_000, 1_290_000, 1_690_000, 2_190_000, 2_445_000, 3_990_000, 4_290_000, 6_490_000, 7_690_000, 12_980_000):
            written = f"{v:,}đ".replace(",", ".")
            self.assertIn(v, numbers_back(spoken_form(written)), written)


if __name__ == "__main__":
    unittest.main()
