"""Tầng đầu ra: bỏ markdown + không lặp y nguyên câu hỏi cùng slot (ui_replay hội thoại A lượt 1 và B lượt 5–6)."""
import unittest

from src.harness.reask import rewrite_reasks, strip_markdown
from src.harness.extractor import extract_questions
from tests._helpers import build_components


class StripMarkdownTest(unittest.TestCase):
    def test_real_llm_output_from_ui_replay(self):
        raw = ("Dạ, em đã tìm thấy sản phẩm giày. Đây là một số thông tin:\n- **Tên sản phẩm**: Giày chạy bộ RunLite 2 Pro\n- **Giá**: 1.690.000 VNĐ\n"
               "- **Thời gian đổi trả**: 7 ngày\nSản phẩm có nhiều kích cỡ ạ.")
        out = strip_markdown(raw)
        self.assertNotIn("*", out)
        self.assertNotIn("\n-", out)
        self.assertIn("Tên sản phẩm: Giày chạy bộ RunLite 2 Pro; Giá: 1.690.000 VNĐ; Thời gian đổi trả: 7 ngày.", out)
        self.assertTrue(out.endswith("Sản phẩm có nhiều kích cỡ ạ."))

    def test_headings_numbered_lists_italics_and_code(self):
        self.assertEqual(strip_markdown("# Báo giá\n1. Máy A\n2. Máy B"), "Báo giá Máy A; Máy B.")
        self.assertEqual(strip_markdown("Dạ *rất* vui ạ, mã `OD1`"), "Dạ rất vui ạ, mã OD1")

    def test_plain_text_is_untouched(self):
        for t in ("Dạ giá 1.521.000đ - đã gồm khuyến mãi ạ.", "Dạ em chào anh 2*3 ạ?", ""):
            self.assertEqual(strip_markdown(t), t)


class RewriteReaskTest(unittest.TestCase):
    ASK = "Em cũng xin phép hỏi số điện thoại của anh/chị để lưu hồ sơ ạ?"

    def run_turn(self, counts, answered=frozenset(), name=None):
        return rewrite_reasks("Dạ em hiểu ạ. " + self.ASK, extract_questions("Dạ em hiểu ạ. " + self.ASK), counts, set(answered), name, "anh/chị")

    def test_first_ask_is_kept_second_is_rephrased_third_dropped(self):
        t1, c1, e1 = self.run_turn({})
        self.assertIn(self.ASK, t1)
        self.assertEqual((c1, e1), ({"phone": 1}, []))
        t2, c2, e2 = self.run_turn(c1, name="Đại")
        self.assertNotIn("hỏi số điện thoại", t2)
        self.assertNotIn("?", t2)                                               # không còn là câu hỏi lặp
        self.assertIn("Dạ em đã ghi nhận tên Đại.", t2)                         # xác nhận điều đã nghe
        self.assertIn("vẫn hỗ trợ anh/chị bình thường", t2)
        self.assertEqual((c2, e2[0]["action"]), ({"phone": 2}, "rephrased"))
        t3, c3, e3 = self.run_turn(c2, name="Đại")
        self.assertEqual(t3, "Dạ em hiểu ạ.")
        self.assertEqual(e3[0]["action"], "dropped")

    def test_answered_slot_resets_the_counter(self):
        t, c, e = self.run_turn({"phone": 2}, answered={"phone"})
        self.assertIn(self.ASK, t)
        self.assertEqual((c, e), ({"phone": 1}, []))

    def test_slots_not_asked_this_turn_are_forgotten(self):
        t, c, e = rewrite_reasks("Dạ em hiểu ạ.", [], {"phone": 1}, set(), None, "chị")
        self.assertEqual((t, c, e), ("Dạ em hiểu ạ.", {}, []))

    def test_confirm_questions_and_other_slots_are_not_touched(self):
        txt = "Số điện thoại của chị là 0911 đúng không ạ? Chị chọn màu gì ạ?"
        t, c, e = rewrite_reasks(txt, extract_questions(txt), {"phone": 1, "color": 1}, set(), None, "chị")
        self.assertEqual((t, e), (txt, []))


class FakeLLM:
    available = True

    def __init__(self, text):
        self.text = text

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        return self.text, [], {"prompt_tokens": 0, "completion_tokens": 0}


class OrchestratorOutputTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()

    def say(self, customer, llm_text, phone="0911111111", date="2026-10-17"):
        from src.channels.normalizer import InputChannel
        orch = self.c["orchestrator"]
        orch.llm_client = FakeLLM(llm_text)
        t = self.c["normalizer"].normalize(customer, InputChannel.HOTLINE, phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t), date)
        return orch.process_turn(t, b, current_date=date)[0]

    def test_markdown_never_reaches_the_customer(self):
        out = self.say("cho hỏi giày", "Dạ đây là thông tin:\n- **Tên**: Giày A\n- **Giá**: 1.000.000đ ạ")
        self.assertNotIn("*", out)
        self.assertNotIn("\n", out)

    def test_same_slot_is_not_asked_three_times_in_a_row(self):
        ask = "Dạ em hiểu ạ. Em xin phép hỏi số điện thoại của anh/chị để lưu hồ sơ ạ?"
        o1 = self.say("hiện tại chưa cần", ask)
        o2 = self.say("tôi tên Đại", ask)
        o3 = self.say("ừ", ask)
        self.assertIn("số điện thoại", o1)
        self.assertNotEqual(o2, o1)
        self.assertNotIn("?", o2)
        self.assertNotIn("số điện thoại", o3)

    def test_giving_the_phone_resets_the_counter(self):
        ask = "Dạ em hiểu ạ. Em xin phép hỏi số điện thoại của anh/chị để lưu hồ sơ ạ?"
        self.say("chưa cần", ask)
        o2 = self.say("số em là 0987654321", ask)  # khách đã đưa SĐT -> lần hỏi này tính là lần ĐẦU, không bị đổi cách
        self.assertIn("hỏi số điện thoại", o2)
        o3 = self.say("ừ", ask)                     # hỏi lại ngay sau đó mới bị đổi cách
        self.assertNotIn("hỏi số điện thoại", o3)


if __name__ == "__main__":
    unittest.main()
