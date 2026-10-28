"""Chốt CẤU TRÚC cho hai lỗi ui_replay (không dựa vào việc LLM làm theo chỉ dẫn):
C — khách nói đã từng liên hệ mà hệ thống chưa có lịch sử: lời agent PHẢI có câu xin SĐT/tài khoản cũ (bộ đọc LLM + trích dẫn; code nối câu nếu LLM quên).
D — shortlist `no_basis` (khách nêu thông tin nhưng không tiêu chí nào áp dụng): CODE dựng câu từ dữ liệu tool, không để LLM khẳng định "phù hợp/an toàn".
LLM giả: kiểm chứng phần CODE."""
import unittest

from tests.test_order_gate import GateBase, NEW_PHONE, KNOWN_PHONE
from tests.test_reply_reader import ReaderLLM, CHECK39

CLAIM = {"claims_prior_contact": True, "prior_contact_quote": "hôm trước tôi có gọi"}
TEXT = "tôi là Đại, hôm trước tôi có gọi để tư vấn máy lọc nước, giờ hỏi còn hàng không"
ASK = "Để em tra lại lịch sử"


class PriorContactTest(GateBase):
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: CLAIM)

    def test_question_is_appended_when_the_llm_forgot_it(self):
        txt, _, meta = self.turn(NEW_PHONE, TEXT, [], "Dạ máy lọc nước RO10 còn hàng ạ.")
        self.assertIn("còn hàng", txt)                                       # câu trả lời của LLM vẫn còn
        self.assertIn(ASK, txt)
        self.assertTrue(meta["reply_reading"]["prior_contact"])
        txt2, _, _ = self.turn(NEW_PHONE, "ừ", [], "Dạ vâng ạ.")             # chỉ hỏi MỘT lần/cuộc
        self.assertNotIn(ASK, txt2)

    def test_llm_already_asking_for_the_phone_is_not_duplicated(self):
        txt, _, _ = self.turn(NEW_PHONE, TEXT, [], "Dạ anh cho em xin số điện thoại đã dùng lần trước để tra lại ạ?")
        self.assertNotIn(ASK, txt)
        self.assertEqual(txt.count("số điện thoại"), 1)

    def test_unverifiable_claim_changes_nothing(self):
        self.llm.reader = lambda t: {"claims_prior_contact": True, "prior_contact_quote": "tuần trước em ghé cửa hàng"}      # trích dẫn bịa
        txt, _, meta = self.turn(NEW_PHONE, TEXT, [], "Dạ còn hàng ạ.")
        self.assertEqual((txt, meta["reply_reading"]["prior_contact"]), ("Dạ còn hàng ạ.", False))

    def test_customer_with_history_is_never_asked(self):
        class B:
            previous_calls_count, honorific = 2, "anh"
        from src.harness.reply_reader import verify
        r = verify(CLAIM, TEXT)
        self.assertTrue(r.prior_contact)
        self.assertEqual(self.orch._ensure_prior_contact_question("s", "Dạ ạ.", r, B()), "Dạ ạ.")

    def test_customer_known_from_crm_is_never_asked_for_the_old_phone(self):
        """Khách gọi từ SĐT có hồ sơ CRM (tên/đơn) nhưng chưa có episode: đã biết là ai → không xin lại SĐT, và không tốn lần đọc "đã liên hệ trước"."""
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize(TEXT, InputChannel.HOTLINE, KNOWN_PHONE)
        known = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")
        self.assertEqual((known.previous_calls_count, known.crm_known), (0, True))
        txt, _, meta = self.turn(KNOWN_PHONE, TEXT, [], "Dạ còn hàng ạ.")
        self.assertEqual((txt, meta["reply_reading"]), ("Dạ còn hàng ạ.", {"source": "skipped"}))
        self.assertEqual(self.llm.read_calls, 0)
        from src.harness.reply_reader import verify
        self.assertEqual(self.orch._ensure_prior_contact_question("s", "Dạ ạ.", verify(CLAIM, TEXT), known), "Dạ ạ.")      # cả lớp nối câu cũng chặn

    def test_name_heard_in_the_call_does_not_count_as_crm(self):
        txt, _, _ = self.turn(NEW_PHONE, "tôi là Đại, hôm trước tôi có gọi, máy lọc nước còn hàng không", [], "Dạ còn hàng ạ.")
        self.assertIn(ASK, txt)

    def test_reader_runs_only_in_the_first_two_turns_of_a_new_customer(self):
        self.llm.reader = lambda t: {}
        for _ in range(3):
            self.turn(NEW_PHONE, "alo", [])
        self.assertEqual(self.llm.read_calls, 2)


class NoBasisTest(GateBase):
    TEXT = "phòng nhà tôi hai mươi mét vuông, có bé ba tuổi"
    LIE = "Dạ Máy lọc nước UF Sunhouse phù hợp phòng 20m² và an toàn cho trẻ nhỏ ạ."

    def test_code_renders_the_reply_from_tool_data(self):
        txt, _, meta = self.turn(NEW_PHONE, self.TEXT, [("product.shortlist", {"category": "máy lọc nước"})], self.LIE)
        self.assertNotIn("phù hợp phòng", txt)
        self.assertNotIn("an toàn cho trẻ", txt)
        self.assertIn("chưa có tiêu chí nào", txt)
        for name in ("Máy lọc nước UF Sunhouse", "Máy lọc nước RO Kangaroo 10 lõi"):
            self.assertIn(name, txt)
        self.assertIn("3.290.000đ", txt)                                      # giá niêm yết lấy từ kết quả tool
        self.assertIn("loại sản phẩm nào", txt)

    def test_reply_kept_when_rules_do_apply(self):
        txt, _, _ = self.turn(NEW_PHONE, self.TEXT, [("product.shortlist", {"category": "máy lọc không khí"})], "Dạ em gợi ý AirPure Y ạ.")
        self.assertEqual(txt, "Dạ em gợi ý AirPure Y ạ.")

    def test_reply_kept_when_other_tools_ran_in_the_same_turn(self):
        txt, _, _ = self.turn(NEW_PHONE, self.TEXT, [("product.shortlist", {"category": "máy lọc nước"}), CHECK39], "Dạ giày còn hàng ạ.")
        self.assertEqual(txt, "Dạ giày còn hàng ạ.")


if __name__ == "__main__":
    unittest.main()
