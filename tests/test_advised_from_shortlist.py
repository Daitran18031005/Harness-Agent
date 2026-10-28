"""ui_replay_10/13 hội thoại E: LLM chỉ gọi product.shortlist (không pricing.get_quote) rồi nêu tên + giá một sản phẩm → product_advised không được lưu
→ cuộc gọi sau (Call Brief) mất sản phẩm đã tư vấn. Ghi từ kết quả shortlist chỉ khi lời agent nêu tên ĐÚNG MỘT sản phẩm trong danh sách."""
import unittest

from tests.test_order_gate import GateBase, NEW_PHONE

SHORTLIST = ("product.shortlist", {"category": "máy lọc không khí", "room_area_m2": 20})


class AdvisedFromShortlistTest(GateBase):
    def advised(self):
        facts = self.c["memory"].as_caller("EvalRunner").get_profile_facts(self.c["resolver"].resolve(
            self.c["normalizer"].normalize("alo", __import__("src.channels.normalizer", fromlist=["InputChannel"]).InputChannel.HOTLINE, NEW_PHONE)).customer_id)
        return facts.get("product_advised")

    def names(self):
        _, tc, _ = self.turn(NEW_PHONE, "chị hỏi máy lọc không khí cho phòng 20m2", [SHORTLIST], "x")
        res = next(c for c in tc if c["name"] == "product.shortlist")["result"]
        return [i["name"] for i in res["items"]], [i["sku"] for i in res["items"]]

    def test_single_product_named_in_the_reply_is_remembered(self):
        names, skus = self.names()
        self.llm.script.clear()
        self.turn(NEW_PHONE, "chị hỏi máy lọc không khí cho phòng 20m2", [SHORTLIST], f"Dạ em gợi ý {names[0]} ạ.")
        self.assertEqual(self.advised(), skus[0])

    def test_several_products_named_or_none_named_is_not_remembered(self):
        names, skus = self.names()
        self.assertIsNone(self.advised())                                                    # lời agent không nêu tên sản phẩm nào
        self.turn(NEW_PHONE, "cho chị xem thêm", [SHORTLIST], f"Dạ có {names[0]} và {names[1]} ạ.")
        self.assertIsNone(self.advised())                                                    # nêu nhiều sản phẩm: không biết chốt cái nào


if __name__ == "__main__":
    unittest.main()
