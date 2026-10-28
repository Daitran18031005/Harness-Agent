"""Nhánh dự phòng khi mất LLM: không nói mã SKU thô với khách, không gắn cứng thông số/quà tặng không có căn cứ."""
import unittest

from tests._helpers import build_components, advisor_suggests


class FallbackHonestyTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()
        advisor_suggests(self)

    def turn(self, text, phone, date):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t), date)
        text_out, _, _ = self.c["orchestrator"].process_turn(t, b, current_date=date)
        return text_out

    def test_catalog_helpers_resolve_variants_and_never_invent_names(self):
        from src.agents.specialists import catalog_product, product_name
        self.assertEqual(product_name("SKU-SN-CAS-39-DEN"), "Giày sneaker Urban Classic")
        self.assertEqual(catalog_product("SKU-SN-CAS-39-DEN")["sku"], "SKU-SN-CAS")
        self.assertEqual(product_name("SKU-KHONG-CO"), "SKU-KHONG-CO")        # không có trong catalog: giữ nguyên mã, không bịa tên
        self.assertEqual(product_name(None), "")

    def test_sales_advice_only_states_catalog_facts(self):
        from src.agents.specialists import SalesAdvisorAgent
        adv = SalesAdvisorAgent(None)
        kids = adv.advise({"profile": {"room_area_m2": 20, "has_children": True}, "call_brief": {"product_advised": "SKU-AP-Y"}})["talking_point"]
        self.assertIn("khóa an toàn cho trẻ nhỏ", kids)                          # AirPure Y có child_safe_lock = True
        self.assertIn("20m²", kids)                                              # phòng 20m² ≤ 30m² của sản phẩm
        no_kids = adv.advise({"profile": {"room_area_m2": 20}, "call_brief": {"product_advised": "SKU-AP-Y"}})["talking_point"]
        self.assertNotIn("trẻ", no_kids)
        too_big = adv.advise({"profile": {"room_area_m2": 80}, "call_brief": {"product_advised": "SKU-AP-Y"}})["talking_point"]
        self.assertNotIn("80m²", too_big)                                        # sản phẩm chỉ phủ 30m²: không nói "phù hợp phòng 80m²"
        shoes = adv.advise({"profile": {"room_area_m2": 20, "has_children": True}, "call_brief": {"product_advised": "SKU-SN-CAS"}})["talking_point"]
        self.assertEqual(shoes, "")                                              # giày không có thuộc tính máy lọc: không bịa HEPA/khóa trẻ em

    def test_greeting_names_the_product_not_the_sku(self):
        out = self.turn("alo em", "0911111111", "2026-10-17")
        self.assertNotIn("SKU-", out)
        self.assertIn("Máy lọc không khí AirPure Y", out)

    def test_gift_is_mentioned_only_while_the_promotion_applies(self):
        active = self.turn("giá vẫn như hôm trước đúng không em", "0984726714", "2026-10-17")
        self.assertIn("quà tặng kèm", active)
        self.assertNotIn("SKU-", active)
        expired = self.turn("giá vẫn như hôm trước đúng không em", "0984726714", "2026-10-25")
        self.assertNotIn("quà tặng", expired)                                    # GIFT-FILTER hết hạn 22/10: không hứa quà


if __name__ == "__main__":
    unittest.main()
