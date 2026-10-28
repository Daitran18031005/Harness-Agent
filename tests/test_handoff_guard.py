"""Chốt CẤU TRÚC cho `handoff.transfer`: chỉ chạy khi khách (lời nguyên văn đã kiểm chứng) yêu cầu hoặc chấp nhận đề nghị chuyển máy.
LLM giả: kiểm chứng phần CODE (chặn, kiểm chứng trích dẫn, một lần/lượt, không chốt cuộc gọi khi bị chặn)."""
import unittest

from src.harness.reply_reader import authorize_handoff
from tests.test_order_gate import GateBase, NEW_PHONE
from tests.test_reply_reader import ReaderLLM

BRIEF = {"customer_phone": "CURRENT_CUSTOMER", "customer_name": "Đại", "escalation_reason": "xin giảm giá", "conversation_summary": "Khách mặc cả máy lọc nước",
         "product_advised": "SKU-WP-RO10", "price_quoted_vnd": 6900000, "open_questions": ["giảm thêm"], "next_action": "nhân viên gọi lại",
         "generated_at": "2026-10-15T10:00:00"}
HANDOFF = ("handoff.transfer", {"brief": BRIEF})


def verdict(authorized=True, basis="asked", quote="cho gặp nhân viên"):
    return lambda t: {"category": "other", "authorized": authorized, "basis": basis, "quote": quote}


def safety(quote="uống thuốc", **kw):
    return lambda t: {"category": "scope_safety", "category_quote": quote, "authorized": False, **kw}


class AuthorizeTest(unittest.TestCase):
    TEXT = "mắc quá, cho gặp nhân viên đi"

    def test_requires_verbatim_quote_and_valid_basis(self):
        ok = authorize_handoff(ReaderLLM(verdict()), self.TEXT)
        self.assertEqual((ok["authorized"], ok["basis"], ok["quote"]), (True, "asked", "cho gặp nhân viên"))
        for bad in (verdict(quote="tôi muốn chuyển máy"),            # trích dẫn bịa
                    verdict(basis=None), verdict(basis="complained"), verdict(authorized=False), lambda t: {}, lambda t: "x", lambda t: RuntimeError("mạng")):
            self.assertFalse(authorize_handoff(ReaderLLM(bad), self.TEXT)["authorized"])

    def test_scope_safety_needs_no_request_but_needs_a_verbatim_quote(self):
        text = "máy lọc không khí này dùng khi bé đang uống thuốc được không"
        ok = authorize_handoff(ReaderLLM(safety()), text)
        self.assertEqual((ok["authorized"], ok["basis"], ok["category"], ok["quote"]), (True, "scope_safety", "scope_safety", "uống thuốc"))
        self.assertFalse(authorize_handoff(ReaderLLM(safety(quote="bé bị hen suyễn")), text)["authorized"])      # trích dẫn bịa → rơi về ca cần khách cho phép
        self.assertFalse(authorize_handoff(ReaderLLM(lambda t: {"category": "scope_safety"}), text)["authorized"])  # thiếu trích dẫn
        self.assertTrue(authorize_handoff(ReaderLLM(lambda t: {**safety()(t), "category_quote": "bịa", "authorized": True, "basis": "asked", "quote": "uống thuốc"}), text)["authorized"])   # ca B vẫn qua nếu khách thật sự yêu cầu

    def test_no_llm_means_no_handoff(self):
        self.assertFalse(authorize_handoff(None, self.TEXT)["authorized"])
        self.assertFalse(authorize_handoff(object(), self.TEXT)["authorized"])


class HandoffToolTest(GateBase):
    def setUp(self):
        super().setUp()
        self.checks = 0
        self.llm = self.orch.llm_client = ReaderLLM(self.reader(verdict(False, None, "")))

    def reader(self, inner):
        """Bộ đọc giả; đếm riêng số lần CHỐT chuyển máy (phân biệt với lần đọc lời khách khác)."""
        def run(t):
            self.checks += "Câu cuối của nhân viên" in t and "Đang chờ" not in t
            return inner(t)
        return run

    def handoffs(self, tc):
        return [c for c in tc if c["name"] == "handoff.transfer"]

    def test_blocked_without_customer_request(self):
        txt, tc, meta = self.turn(NEW_PHONE, "mắc quá vậy? 6tr8 lấy luôn", [HANDOFF, HANDOFF], "Em sẽ chuyển máy cho nhân viên ạ.")
        self.assertEqual(self.handoffs(tc), [])                               # không có lời gọi nào chạy, cũng không vào trace
        self.assertIsNone(meta["memory_extraction"])                          # không chốt episode giữa cuộc
        self.assertFalse(meta["handoff_check"]["authorized"])
        self.assertEqual(self.checks, 1)                                      # hai lần LLM thử gọi → chỉ một lần chốt trong lượt

    def test_allowed_when_customer_asked(self):
        self.llm.reader = self.reader(verdict())
        _, tc, meta = self.turn(NEW_PHONE, "cho gặp nhân viên đi", [HANDOFF])
        self.assertEqual(len(self.handoffs(tc)), 1)
        self.assertEqual((meta["handoff_check"]["basis"], meta["handoff_check"]["quote"]), ("asked", "cho gặp nhân viên"))
        self.assertEqual(meta["memory_extraction"]["trigger"], "handoff")

    def test_scope_safety_goes_through_without_the_customer_asking(self):
        self.llm.reader = self.reader(safety())
        _, tc, meta = self.turn(NEW_PHONE, "máy này dùng khi bé đang uống thuốc được không", [HANDOFF], "Dạ em chuyển máy cho dược sĩ ạ.")
        self.assertEqual(len(self.handoffs(tc)), 1)
        self.assertEqual((meta["handoff_check"]["category"], meta["handoff_check"]["basis"]), ("scope_safety", "scope_safety"))
        self.assertEqual(meta["memory_extraction"]["trigger"], "handoff")

    def test_price_haggling_labelled_as_scope_safety_without_a_real_quote_is_blocked(self):
        self.llm.reader = self.reader(safety(quote="giảm thêm 90k"))
        _, tc, _ = self.turn(NEW_PHONE, "mắc quá, tôi muốn giảm thêm 90k", [HANDOFF])
        self.assertEqual(self.handoffs(tc), [])

    def test_missing_brief_fields_are_filled_by_code_so_the_transfer_succeeds(self):
        self.llm.reader = self.reader(safety())
        _, tc, meta = self.turn(NEW_PHONE, "máy này dùng khi bé đang uống thuốc được không", [("handoff.transfer", {"brief": {"escalation_reason": "y tế"}})])
        res = self.handoffs(tc)[0]["result"]
        self.assertNotIn("error", res)
        self.assertEqual(res["status"], "queued")
        args = self.handoffs(tc)[0]["args"]["brief"]
        self.assertEqual(args["escalation_reason"], "y tế")                       # trường LLM đã điền được giữ
        self.assertIn("uống thuốc", args["conversation_summary"])                 # trường thiếu lấy từ lời khách đã kiểm chứng

    def test_invented_quote_is_still_blocked(self):
        self.llm.reader = self.reader(verdict(quote="tôi đồng ý chuyển máy"))
        _, tc, _ = self.turn(NEW_PHONE, "ừ để xem đã", [HANDOFF])
        self.assertEqual(self.handoffs(tc), [])

    def test_no_check_when_llm_does_not_try_to_transfer(self):
        _, _, meta = self.turn(NEW_PHONE, "alo", [])
        self.assertIsNone(meta["handoff_check"])


class BriefAfterMidCallHandoffTest(GateBase):
    def test_own_episode_is_not_a_previous_call(self):
        self.llm = self.orch.llm_client = ReaderLLM(verdict())
        self.turn(NEW_PHONE, "cho gặp nhân viên đi", [HANDOFF])
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("tôi tên Đại", InputChannel.HOTLINE, NEW_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")
        self.assertEqual(brief.previous_calls_count, 0)
        later = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-17")      # ngày khác = cuộc gọi MỚI → episode đó là cuộc trước
        self.assertEqual(later.previous_calls_count, 1)


if __name__ == "__main__":
    unittest.main()
