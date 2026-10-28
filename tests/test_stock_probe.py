"""Code tự tra `inventory.check` cho biến thể khách nêu (size+màu) trước khi trả lời — lỗi ui_replay: LLM chỉ gọi catalog.search rồi nói "38 đen không có sẵn" dù còn 5."""
import unittest

from src.channels.normalizer import InputChannel
from tests._helpers import build_components

DATE = "2026-10-17"          # 38 đen còn 5, 38 xám hết (mock BTC)
SEARCH = ("catalog.search", {"query": "giày chạy bộ RunLite 2 Pro"})


class ScriptedLLM:
    available = True

    def __init__(self, calls, text):
        self.calls, self.text, self.seen_messages = calls, text, []

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        self.seen_messages = messages
        log = []
        for name, args in self.calls:
            result, executed = tool_executor(name, args)
            log.append({"name": name, "tool": name, "args": executed, "result": result})
        return self.text, log, {"prompt_tokens": 0, "completion_tokens": 0}


class StockProbeTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def say(self, customer, calls, reply, phone="0911111111"):
        llm = self.orch.llm_client = ScriptedLLM(calls, reply)
        t = self.c["normalizer"].normalize(customer, InputChannel.HOTLINE, phone, reference_date=DATE)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), DATE)
        final, tool_calls, _ = self.orch.process_turn(t, b, current_date=DATE)
        return final, tool_calls, llm

    @staticmethod
    def checked(tool_calls):
        return {tc["args"]["sku"]: tc["result"]["in_stock"] for tc in tool_calls if tc["name"] == "inventory.check"}

    def test_product_only_learned_this_turn_is_still_checked_and_wrong_claim_replaced(self):
        # LLM chỉ gọi catalog.search (không inventory.check) rồi nói sai
        final, calls, _ = self.say("thế 38 đen có không?", [SEARCH], "Dạ, em xin lỗi nhưng màu đen size 38 không có sẵn trong kho ạ.")
        self.assertEqual(self.checked(calls), {"SKU-SN-RUN2-38-DEN": True})
        self.assertIn("size 38 màu đen hiện còn hàng", final)
        self.assertNotIn("không có sẵn", final)

    def test_known_product_is_checked_before_the_llm_and_the_llm_is_told(self):
        self.say("cho mình hỏi giày chạy bộ RunLite 2 Pro", [SEARCH], "Dạ giá 1.690.000đ ạ.")
        final, calls, llm = self.say("có 38 đen ko?", [], "Dạ còn hàng ạ.")           # LLM không gọi tool nào
        self.assertEqual(self.checked(calls), {"SKU-SN-RUN2-38-DEN": True})
        sys_ctx = " ".join(m["content"] for m in llm.seen_messages if m["role"] == "system")
        self.assertIn("SKU-SN-RUN2-38-DEN: CÒN HÀNG (qty=5)", sys_ctx)

    def test_genuinely_out_of_stock_variant_is_left_alone(self):
        final, calls, _ = self.say("cho mình 38 xám", [SEARCH], "Dạ size 38 màu xám hiện hết hàng ạ.")
        self.assertEqual(self.checked(calls), {"SKU-SN-RUN2-38-XAM": False})
        self.assertIn("hết hàng", final)

    def test_two_variants_in_one_turn_each_claim_judged_on_its_own(self):
        final, calls, _ = self.say("38 xám hay 38 đen còn?", [SEARCH],
                                   "Dạ size 38 màu xám hết hàng ạ. Dạ size 38 màu đen không có sẵn ạ.")
        self.assertEqual(self.checked(calls), {"SKU-SN-RUN2-38-XAM": False, "SKU-SN-RUN2-38-DEN": True})
        self.assertIn("màu xám hết hàng", final)                 # đúng sự thật: giữ
        self.assertIn("size 38 màu đen hiện còn hàng", final)    # sai: sửa
        self.assertNotIn("không có sẵn", final)

    def test_variant_already_checked_by_the_llm_is_not_checked_twice(self):
        inv = ("inventory.check", {"sku": "SKU-SN-RUN2-38-DEN"})
        _, calls, _ = self.say("38 đen còn không", [SEARCH, inv], "Dạ còn ạ.")
        self.assertEqual(len([c for c in calls if c["name"] == "inventory.check"]), 1)

    def test_no_check_when_customer_names_only_size_or_color_or_a_nonexistent_size(self):
        for text in ("giày màu đen có không", "có size 38 không", "có xám 37 ko?"):
            _, calls, _ = self.say(text, [SEARCH], "Dạ để em kiểm tra ạ.")
            self.assertEqual(self.checked(calls), {}, text)

    def test_latest_mention_wins_in_a_follow_up_turn(self):
        self.say("38 xám có không?", [SEARCH], "Dạ hết ạ.")
        _, calls, _ = self.say("thế 38 đen thì sao?", [], "Dạ ạ.")
        self.assertEqual(self.checked(calls), {"SKU-SN-RUN2-38-DEN": True})

    def test_single_letter_sizes_need_a_whole_word(self):
        # "m" trong "mình" không được tính là size M
        variants = [{"variant_sku": "SKU-X-M-DEN", "size": "M", "color": "den"}]
        f = self.orch._variants_named_in
        self.assertEqual(f(variants, "mình muốn áo đen"), [])
        self.assertEqual(f(variants, "áo size M màu đen"), ["SKU-X-M-DEN"])


if __name__ == "__main__":
    unittest.main()
