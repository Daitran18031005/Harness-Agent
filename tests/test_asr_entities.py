"""Trích thực thể phi số từ giả thuyết ASR (sku, color, promo_expiry, payment, in_stock, blocker, size) + vai trò số tiền theo cụm từ.
Văn bản mẫu viết theo cách BTC viết ground truth/ASR nghe ra; D01–D04 là mẫu trong-tập nên có thêm test trên chuỗi tự viết."""
import json
import os
import unittest

from src.channels.asr_entities import (extract_blocker, extract_color, extract_payment, extract_promo_expiry,
                                       extract_sizes, product_mentions)
from src.channels.asr_postprocess import extract_hypothesis_entities

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GT = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr", "ground_truth.json")


def skus(text):
    return [s for _, s, _ in product_mentions(text)]


class ProductMentionTest(unittest.TestCase):
    def test_btc_style_readings(self):
        self.assertEqual(skus("mẫu e pia y có khóa trẻ em"), ["SKU-AP-Y"])
        self.assertEqual(skus("máy lọc nước ka rô phi chín lõi bên em giá bao nhiêu"), ["SKU-WF-RO9"])
        self.assertEqual(skus("giày run lai hai pro size bốn mươi"), ["SKU-SN-RUN2"])

    def test_asr_variants_seen_on_samples(self):
        self.assertEqual(skus("hai mẫu phù hợp là epx và epi ạ"), ["SKU-AP-X", "SKU-AP-Y"])
        self.assertEqual(skus("máy caro phi chín lõi"), ["SKU-WF-RO9"])
        self.assertEqual(skus("giày rung lai hai pro"), ["SKU-SN-RUN2"])

    def test_letter_after_mau_resolves_to_sibling_of_previous_product(self):
        self.assertEqual(skus("hai mẫu là epx và epi ạ còn mẫu ít thì bao nhiêu")[-1], "SKU-AP-X")

    def test_different_categories_not_confused(self):
        self.assertEqual(skus("xiao mi smart bốn pờ rô"), ["SKU-XM-4P"])
        self.assertEqual(skus("nồi chiên phi líp sáu lít"), ["SKU-AF-6L"])

    def test_common_words_do_not_match(self):
        self.assertEqual(skus("dạ chị chờ em chút nhé em kiểm tra tồn kho giúp chị"), [])
        self.assertEqual(skus("dạ vâng em ghi nhận mai hoặc ngày kia em gọi lại chị được không ạ"), [])

    def test_last_mention_wins_for_sku_entity(self):
        e = extract_hypothesis_entities("mẫu e pia y giá năm triệu hai trăm nghìn còn mẫu e pia x thì rẻ hơn")
        self.assertEqual(e["sku"], "SKU-AP-X")


class SmallFieldsTest(unittest.TestCase):
    def test_color_slug_without_diacritics(self):
        self.assertEqual(extract_color("giày size bốn mươi màu đen chị muốn đổi"), "den")
        self.assertEqual(extract_color("áo màu trắng ạ"), "trang")
        self.assertIsNone(extract_color("trời tối đen như mực"))                 # không có "màu"

    def test_payment_variants(self):
        self.assertEqual(extract_payment("thanh toán khi nhận hàng"), "COD")
        self.assertEqual(extract_payment("thanh toán cê ô đê đúng không ạ"), "COD")
        self.assertEqual(extract_payment("thanh toán k ôd đúng không"), "COD")
        self.assertEqual(extract_payment("em chuyển khoản trước nhé"), "bank")
        self.assertIsNone(extract_payment("chị cần thêm thời gian"))

    def test_blocker_vocabulary(self):
        self.assertEqual(extract_blocker("ừ để chị hỏi ông xã rồi gọi lại em nhé"), "can hoi chong")
        self.assertEqual(extract_blocker("để anh hỏi bà xã đã"), "can hoi vo")
        self.assertEqual(extract_blocker("bên kia anh thấy bán rẻ hơn mà"), "so sanh gia")
        self.assertIsNone(extract_blocker("rồi bà xã anh ok rồi giá vẫn vậy đúng không em"))   # đã được đồng ý → không còn rào cản

    def test_promo_expiry_iso(self):
        self.assertEqual(extract_promo_expiry("đang có khuyến mãi tặng một màng lọc đến hết ngày hai mươi hai tháng mười ạ", "2026-10-15"), "2026-10-22")
        self.assertEqual(extract_promo_expiry("khuyến mãi hết ngày 30 tháng 9", "2026-09-25"), "2026-09-30")
        self.assertIsNone(extract_promo_expiry("em gọi lại ngày hai mươi hai tháng mười nhé", "2026-10-15"))   # không có từ "hết/đến/hạn"

    def test_sizes_old_and_new(self):
        out = extract_sizes("chị mới nhận giày mà sai rơ bốn mươi hơi chật chị muốn đổi lên sai rơ bốn mươi mốt")
        self.assertEqual(out, {"size_old": 40, "size_new": 41})
        self.assertEqual(extract_sizes("em ơi còn size 39 không"), {"size_old": 39})
        self.assertEqual(extract_sizes("đổi lên bốn mươi mốt có mất phí gì không"), {"size_new": 41})

    def test_in_stock_comes_from_claims(self):
        self.assertIs(extract_hypothesis_entities("dạ còn hàng ạ bên vận chuyển sẽ qua lấy").get("in_stock"), True)


class MoneyRoleTest(unittest.TestCase):
    def test_role_phrases(self):
        e = extract_hypothesis_entities("bên kia anh thấy bán có năm triệu bảy thôi sao bên em đắt hơn")
        self.assertEqual(e.get("competitor_price_vnd"), 5700000)
        e = extract_hypothesis_entities("đơn từ hai triệu được miễn phí vận chuyển hàng cồng kềnh ngoài nội thành phụ thu ba mươi nghìn thôi ạ")
        self.assertEqual(e.get("min_free_ship_vnd"), 2000000)
        self.assertEqual(e.get("bulky_fee_vnd"), 30000)
        self.assertNotIn("exchange_fee_vnd", e)

    def test_model_is_price_when_said_after_price_keyword(self):
        e = extract_hypothesis_entities("mẫu epi giá năm triệu hai trăm nghìn còn mẫu x là bốn triệu tám trăm chín mươi nghìn")
        self.assertEqual(e.get("price_vnd"), 4890000)           # lần báo giá CUỐI

    def test_room_area_without_square(self):
        self.assertEqual(extract_hypothesis_entities("cho phòng hai mươi lăm mét giá năm triệu").get("room_area_m2"), 25)


class SampleDialoguesTest(unittest.TestCase):
    """Trên CHÍNH văn bản ground truth của D01–D04 (không qua ASR) mọi khóa dialogue-level phải trích đúng — chặn hồi quy.
    Đây là mẫu trong-tập: luật được viết khi đã thấy các hội thoại này."""

    def test_ground_truth_text_gives_ground_truth_entities(self):
        gt = json.load(open(GT, encoding="utf-8"))["dialogues"]
        for d in gt:
            got = extract_hypothesis_entities(d["full_text"], "2026-10-15")
            for k, v in d["entities"].items():
                self.assertEqual(str(got.get(k)), str(v), f"{d['id']}.{k}")


if __name__ == "__main__":
    unittest.main()
