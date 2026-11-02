"""Khách đổi sang SẢN PHẨM KHÁC giữa cuộc gọi (CHECKING § 11.102): ui trace `call_3` — áo phao Warmly đã tư vấn, khách chuyển sang áo khoác gió Windbreak.
Lỗi gốc: enum SKU khóa theo sản phẩm lúc đầu cuộc, `order.update` cho "đổi sang…" khi chưa có đơn, giá sản phẩm A gắn tên sản phẩm B, size/màu cũ áp sang món mới."""
import unittest
from unittest import mock

from tests.test_order_gate import GateBase, NEW_PHONE
from src.llm.client import LLMClient

DWN, WND = "SKU-JK-DWN", "SKU-JK-WND"                 # áo phao Warmly 1.490.000đ · áo khoác gió Windbreak 690.000đ
SEARCH_WND = {"name": "catalog.search", "args": {"query": "áo windbreak"}, "result": {"items": [{"sku": WND, "name": "Áo khoác gió Windbreak"}]}}
SEARCH_DWN = {"name": "catalog.search", "args": {"sku": DWN}, "result": {"items": [{"sku": DWN, "name": "Áo phao lông vũ Warmly"}]}}


class FocusProductTest(GateBase):
    def test_most_recent_product_comes_first_then_the_advised_one(self):
        self.assertEqual(self.orch._discussed_parents(DWN, [SEARCH_DWN, SEARCH_WND]), [WND, DWN])
        self.assertEqual(self.orch._discussed_parents(DWN, []), [DWN])                      # chưa tra gì: sản phẩm đã tư vấn
        self.assertEqual(self.orch._discussed_parents(None, [SEARCH_WND]), [WND])

    def test_enum_covers_every_product_in_play_so_the_new_one_can_be_quoted(self):
        from src.llm.client import build_openai_tools
        llm = mock.Mock(get_base_tools=build_openai_tools)
        tools = self.orch._build_dynamic_tools(llm, [WND, DWN])
        enum = next(t["function"]["parameters"]["properties"]["sku"]["enum"] for t in tools if t["function"]["name"] == "pricing__get_quote")
        self.assertTrue({"SKU-JK-WND-L-BE", "SKU-JK-DWN-L-BE"} <= set(enum))
        only_old = next(t["function"]["parameters"]["properties"]["sku"]["enum"]
                        for t in self.orch._build_dynamic_tools(llm, DWN) if t["function"]["name"] == "pricing__get_quote")
        self.assertFalse(any(x.startswith(WND) for x in only_old))                           # hành vi cũ (một sản phẩm) vẫn dùng được

    def test_named_variant_is_checked_on_the_product_just_searched(self):
        calls = self.orch._check_named_variants(["cỡ L màu be"], DWN, [SEARCH_DWN, SEARCH_WND], [], "2026-10-30")
        self.assertEqual([c["args"]["sku"] for c in calls], ["SKU-JK-WND-L-BE"])
        calls = self.orch._check_named_variants(["cỡ L màu be"], DWN, [], [], "2026-10-30")      # chưa chuyển sản phẩm: vẫn là sản phẩm đã tư vấn
        self.assertEqual([c["args"]["sku"] for c in calls], ["SKU-JK-DWN-L-BE"])


class PerRoundToolsTest(unittest.TestCase):
    def test_tools_can_be_rebuilt_every_round(self):
        c = LLMClient()
        c.available, c._tools = True, []
        seen, rounds = [], iter([("", [{"id": "1", "name": "catalog__search", "arguments": '{"query": "x"}'}], None, None), ("Dạ ạ.", [], None, None)])

        def fake_round(messages, tools):
            seen.append(tools)
            return next(rounds)
        c._stream_round = fake_round
        n = iter(range(10))
        text, _, _ = c.chat_with_tools([{"role": "user", "content": "x"}], lambda name, args: ({"items": []}, args), tools_override=lambda: [next(n)])
        self.assertEqual((text, seen), ("Dạ ạ.", [[0], [1]]))


class ExchangeIntentTest(GateBase):
    def test_exchange_without_an_order_gets_a_hint_to_search_instead(self):
        _, tc, _ = self.turn(NEW_PHONE, "hiện tại tôi muốn đổi sang áo khoác windbreaker",
                             [("order.update", {"order_id": "OD-KHONG-CO", "action": "exchange_product", "new_variant_sku": "SKU-JK-DWN-L-BE"})], "Dạ ạ.")
        res = next(c["result"] for c in tc if c["name"] == "order.update")
        self.assertEqual(res["error"], "order_not_found")
        self.assertIn("KHÔNG phải đổi đơn", res["hint"])

    def test_prompt_separates_changing_an_order_from_choosing_another_product(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-30")
        sys_msg = " ".join(m["content"] for m in self.orch._build_llm_messages(t, brief, [], "2026-10-30", None))
        for needle in ("CỦA MỘT ĐƠN ĐÃ ĐẶT", "CHƯA có đơn nào", "KHÔNG gọi order.update", "MỘT sản phẩm", "CHỈ là lựa chọn cho SẢN PHẨM ĐÃ TƯ VẤN",
                       "ĐÍCH DANH", "KHÔNG dùng product.shortlist"):
            self.assertIn(needle, sys_msg)


class PriceBoundToProductTest(GateBase):
    QUOTE_DWN = ("pricing.get_quote", {"sku": "SKU-JK-DWN-L-BE"})

    def test_price_of_another_product_is_replaced_by_the_named_products_own_quote(self):
        txt, tc, _ = self.turn(NEW_PHONE, "cho tôi xem giá của áo khoác windbreaker", [self.QUOTE_DWN],
                               "Dạ em đã kiểm tra, giá của sản phẩm Áo khoác gió Windbreak cỡ L màu be là 1.490.000đ ạ.")
        self.assertIn("690.000", txt)
        self.assertNotIn("1.490.000", txt)
        quoted = [c["args"]["sku"] for c in tc if c["name"] == "pricing.get_quote"]
        self.assertEqual(quoted, ["SKU-JK-DWN-L-BE", WND])                                   # lời gọi sửa nằm trong trace làm bằng chứng

    def test_consistent_answer_is_left_alone(self):
        txt, tc, _ = self.turn(NEW_PHONE, "áo phao giá bao nhiêu", [self.QUOTE_DWN], "Dạ Áo phao lông vũ Warmly giá 1.490.000đ ạ.")
        self.assertIn("1.490.000", txt)
        self.assertEqual([c["args"]["sku"] for c in tc if c["name"] == "pricing.get_quote"], ["SKU-JK-DWN-L-BE"])

    def test_gift_name_alone_does_not_trigger_a_requote(self):
        txt, tc, _ = self.turn(NEW_PHONE, "máy lọc X giá sao", [("pricing.get_quote", {"sku": "SKU-AP-X"})],
                               "Dạ giá 4.890.000đ, có tặng Màng lọc thay thế AirPure X/Y ạ.")
        self.assertIn("4.890.000", txt)
        self.assertEqual(len([c for c in tc if c["name"] == "pricing.get_quote"]), 1)


class SizeColorBelongToTheProductTest(GateBase):
    def messages(self, focus):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("cho tôi xem giá", InputChannel.HOTLINE, NEW_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-30")
        brief.product_advised = DWN
        brief.profile_facts = {"product_advised": DWN, "size": "L", "color": "be", "variant_sku": "SKU-JK-DWN-L-BE"}
        return " ".join(m["content"] for m in self.orch._build_llm_messages(t, brief, [], "2026-10-30", None, focus_parent=focus))

    def test_old_size_and_color_are_hidden_once_another_product_is_in_play(self):
        msg = self.messages(WND)
        self.assertNotIn("'size': 'L'", msg)
        self.assertNotIn("SKU-JK-DWN-L-BE", msg)
        self.assertIn("ĐANG xem sản phẩm khác", msg)

    def test_size_and_color_stay_while_the_advised_product_is_in_play(self):
        msg = self.messages(DWN)
        self.assertIn("'size': 'L'", msg)
        self.assertNotIn("ĐANG xem sản phẩm khác", msg)


if __name__ == "__main__":
    unittest.main()
