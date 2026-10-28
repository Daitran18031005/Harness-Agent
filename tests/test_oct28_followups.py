"""Các sửa còn lại sau ui_replay 18–22: (1B) code ép chuyển máy khi khiếu nại đơn đã đặt, C chỉ còn MỘT câu hỏi cuối lượt + xưng hô nhất quán đầu câu, bỏ inventory.check trùng."""
import unittest

from tests.test_handoff_guard import safety, verdict
from tests.test_order_gate import GateBase, NEW_PHONE
from tests.test_reply_reader import ReaderLLM
from tests.test_stock_probe import StockProbeTest, SEARCH

TAM = "0965384535"          # C032 Tâm — CRM có đơn OD301177 đang shipping
STATUS = ("order.status", {"order_id": "OD301177"})
COMPLAINT = "đơn OD301177 của tôi đặt từ hôm 3/10 mà tới giờ vẫn chưa nhận được hàng, sao vậy?"


class OrderComplaintEscalationTest(GateBase):
    def setUp(self):
        super().setUp()
        self.seen = []

    def use(self, classifier):
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: (self.seen.append(t), classifier(t))[1])

    def test_code_transfers_when_the_classifier_sees_a_complaint_about_a_placed_order(self):
        self.use(safety(quote="vẫn chưa nhận được hàng"))
        txt, tc, meta = self.turn(TAM, COMPLAINT, [STATUS], "Dạ đơn đang giao ạ.")
        hand = [c for c in tc if c["name"] == "handoff.transfer"]
        self.assertEqual(len(hand), 1)
        self.assertEqual(hand[0]["result"]["status"], "queued")
        self.assertIn("Em đã chuyển thông tin đơn", txt)
        self.assertIn("Dạ đơn đang giao ạ.", txt)                              # câu trả lời của LLM vẫn còn
        self.assertEqual(meta["handoff_check"]["category"], "scope_safety")
        self.assertEqual(meta["memory_extraction"]["trigger"], "handoff")
        self.assertTrue(any("OD301177" in t and "shipping" in t and "hôm nay" in t for t in self.seen))   # chốt thấy dữ kiện đơn

    def test_plain_status_question_is_not_transferred(self):
        self.use(verdict(False, None, ""))
        txt, tc, meta = self.turn(TAM, "đơn OD301177 giao tới đâu rồi em?", [STATUS], "Dạ đơn đang giao ạ.")
        self.assertEqual([c for c in tc if c["name"] == "handoff.transfer"], [])
        self.assertEqual(txt, "Dạ đơn đang giao ạ.")
        self.assertFalse(meta["handoff_check"]["authorized"])

    def test_invented_quote_does_not_transfer(self):
        self.use(safety(quote="đơn bị mất"))
        _, tc, _ = self.turn(TAM, COMPLAINT, [STATUS], "Dạ đơn đang giao ạ.")
        self.assertEqual([c for c in tc if c["name"] == "handoff.transfer"], [])

    def test_no_extra_check_when_the_llm_already_handled_it_or_no_order_was_looked_up(self):
        self.use(safety(quote="vẫn chưa nhận được hàng"))
        self.turn(TAM, "alo", [])
        self.assertEqual([t for t in self.seen if "Dữ kiện hệ thống" in t], [])


class SingleQuestionAndAddressingTest(GateBase):
    def test_prior_contact_question_replaces_the_llm_closing_question(self):
        from src.harness.reply_reader import verify
        claim = verify({"claims_prior_contact": True, "prior_contact_quote": "hôm trước tôi có gọi"}, "hôm trước tôi có gọi")
        class B:
            previous_calls_count, honorific, crm_known = 0, "anh/chị", False
        out = self.orch._ensure_prior_contact_question("s", "Dạ còn hàng 12 chiếc ạ. Anh có muốn biết thêm thông tin gì không ạ?", claim, B())
        self.assertEqual(out.count("?"), 1)
        self.assertIn("còn hàng 12 chiếc", out)
        self.assertNotIn("muốn biết thêm", out)
        self.assertIn("số điện thoại", out)

    def test_sentence_initial_bare_honorific_is_unified_when_unknown(self):
        class B:
            customer_name, honorific = "Đại", "anh/chị"
            def addressing(self): return "anh/chị Đại"
        self.assertEqual(self.orch._fix_addressing("Dạ em chào anh. Anh cần gì ạ? Chị xem giúp em.", B()), "Dạ em chào anh/chị. Anh/chị cần gì ạ? Anh/chị xem giúp em.")


class DuplicateStockCheckTest(StockProbeTest):
    def test_llm_repeating_the_code_pre_check_is_served_from_it(self):
        self.say("cho mình hỏi giày chạy bộ RunLite 2 Pro", [SEARCH], "Dạ giá 1.690.000đ ạ.")
        inv = ("inventory.check", {"sku": "SKU-SN-RUN2-38-DEN"})
        final, calls, _ = self.say("có 38 đen ko?", [inv], "Dạ còn hàng ạ.")
        self.assertEqual([c["args"]["sku"] for c in calls if c["name"] == "inventory.check"], ["SKU-SN-RUN2-38-DEN"])   # một lần, không hai


for name in [n for n in dir(StockProbeTest) if n.startswith("test_")]:
    setattr(DuplicateStockCheckTest, name, None)                                  # chỉ chạy test mới, không chạy lại các test của lớp cha
DuplicateStockCheckTest.test_llm_repeating_the_code_pre_check_is_served_from_it = DuplicateStockCheckTest.__dict__["test_llm_repeating_the_code_pre_check_is_served_from_it"]


del StockProbeTest      # chỉ để kế thừa; tránh bị unittest thu thập lại
if __name__ == "__main__":
    unittest.main()
