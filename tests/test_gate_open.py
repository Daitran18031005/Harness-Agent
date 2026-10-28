"""Mở order gate BẰNG CODE khi khách cam kết mua (lỗi ui_replay_9 lượt 6: gate chỉ chạy nếu LLM chính tình cờ gọi order.create).
Các lớp: ý định (bộ đọc, GIẢ ở đây) · đối tượng (code) · loại trừ. LLM giả → chỉ kiểm chứng phần CODE; độ chính xác của bộ đọc đo ở scripts/."""
import unittest

from src.harness.order_gate import OrderGate, DRAFT_TTL_TURNS
from tests.test_order_gate import GateBase, NEW_PHONE
from tests.test_reply_reader import ReaderLLM, CHECK39, burn_early

COMMIT = {"order_intent": "commit", "intent_quote": "lấy", "only_answers": True}


class GateOpenTest(GateBase):
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})

    def explore(self):
        """Lượt 1: biến thể đã được tra → vào ngữ cảnh mua (bộ đọc chạy từ lượt sau)."""
        self.llm.reader = lambda t: {}
        self.turn(NEW_PHONE, "cho mình xem giày sneaker 39 đen", [CHECK39])

    def say(self, text, reading):
        self.llm.reader = lambda t: reading
        before = self.llm.calls
        txt, tc, meta = self.turn(NEW_PHONE, text, [])
        return txt, tc, meta, self.llm.calls - before

    def test_commit_on_one_in_stock_variant_opens_the_gate_without_the_main_llm(self):
        self.explore()
        txt, tc, meta, main_calls = self.say("ok lấy 39 đen", COMMIT)
        go = meta["gate_open"]
        self.assertTrue(go["opened"])
        self.assertEqual(go["object"]["checked"], {"SKU-SN-CAS-39-DEN": True})
        self.assertEqual(main_calls, 0)                                        # code trả lời, LLM chính không chạy
        self.assertEqual(meta["order_gate"][-1]["action"], "ask_confirm")      # gate hỏi tên/địa chỉ/thanh toán, xác nhận SĐT
        self.assertIn("địa chỉ", txt)
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])    # tuyệt đối chưa tạo đơn

    def test_no_commit_means_no_opening(self):
        self.explore()
        _, _, meta, main_calls = self.say("39 đen giá bao nhiêu", {"order_intent": "other"})
        self.assertEqual((meta["gate_open"]["opened"], meta["gate_open"]["reason"], main_calls), (False, "intent_not_commit", 1))

    def test_contradicting_signals_exclude_opening(self):
        self.explore()
        _, _, meta, _ = self.say("ok lấy 39 đen", {**COMMIT, "stance": "decline", "stance_quote": "lấy"})
        self.assertEqual((meta["gate_open"]["opened"], meta["gate_open"]["exclusions"]), (False, ["decline"]))

    def test_commit_with_open_question_opens_after_the_answer(self):
        """Chỉ có `open_question` (khách vừa hỏi vừa chốt): không còn bị loại — LLM chính trả lời, code nối bước gate (tests/test_gd2_fixes.py)."""
        self.explore()
        _, _, meta, main_calls = self.say("ok lấy 39 đen", {**COMMIT, "asks_question": True})
        self.assertEqual((meta["gate_open"]["opened"], meta["gate_open"]["reason"], main_calls), (True, "opened_after_answer", 1))

    def test_unverifiable_commit_is_ignored(self):
        self.explore()
        _, _, meta, _ = self.say("ok lấy 39 đen", {"order_intent": "commit", "intent_quote": "tôi quyết định mua"})   # trích dẫn bịa
        self.assertEqual(meta["gate_open"]["reason"], "intent_not_commit")

    def test_two_variants_open_at_the_ask_variant_step(self):
        self.explore()
        txt, _, meta, _ = self.say("39 đen hay 40 đen thì lấy", {**COMMIT, "intent_quote": "lấy"})
        go = meta["gate_open"]
        self.assertEqual((go["opened"], go["object"].get("fallback")), (True, "ask_variant"))
        self.assertEqual(set(go["object"]["checked"]), {"SKU-SN-CAS-39-DEN", "SKU-SN-CAS-40-DEN"})

    def test_no_second_opening_while_a_draft_is_open(self):
        self.explore()
        self.say("ok lấy 39 đen", COMMIT)
        _, _, meta, _ = self.say("ok lấy 39 đen", COMMIT)
        self.assertNotEqual(meta["gate_open"].get("reason"), "opened")


SEARCH = ("catalog.search", {"query": "giày sneaker Urban Classic"})


class LateReadTest(GateBase):
    """Lượt ĐẦU nhắc biến thể + cam kết ngay: lúc đầu lượt bộ đọc bị `skipped`; tín hiệu (code thấy biến thể cụ thể được nêu) → đọc muộn rồi mới quyết định mở gate."""
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)
        self.llm.reader = lambda t: {}
        self.turn(NEW_PHONE, "cho mình xem giày sneaker Urban Classic", [SEARCH])       # biết sản phẩm, CHƯA có biến thể nào được tra
        self.reads0 = self.llm.read_calls

    def test_first_mention_and_commit_in_one_turn_opens_the_gate(self):
        self.assertEqual(self.reads0, 0)                                                # lượt 1: không đọc
        self.llm.reader = lambda t: COMMIT
        before = self.llm.calls
        _, _, meta = self.turn(NEW_PHONE, "ok lấy 39 đen", [])
        self.assertEqual(self.llm.read_calls, 1)                                        # đọc muộn đúng 1 lần
        self.assertTrue(meta["reply_reading"]["late"])
        self.assertTrue(meta["gate_open"]["opened"])
        self.assertEqual(self.llm.calls - before, 0)

    def test_no_variant_named_means_no_late_read(self):
        self.llm.reader = lambda t: COMMIT
        _, _, meta = self.turn(NEW_PHONE, "ok em lấy luôn", [])
        self.assertEqual((self.llm.read_calls, meta["reply_reading"]), (0, {"source": "skipped"}))

    def test_variant_named_but_only_asking_is_read_once_and_not_opened(self):
        self.llm.reader = lambda t: {"order_intent": "other", "asks_question": True}
        before = self.llm.calls
        _, _, meta = self.turn(NEW_PHONE, "39 đen giá bao nhiêu", [])
        self.assertEqual((self.llm.read_calls, meta["gate_open"]["opened"], self.llm.calls - before), (1, False, 1))


QUOTE_RO10 = ("pricing.get_quote", {"sku": "SKU-WF-RO10", "on": "2026-10-15"})


class SimpleProductTest(GateBase):
    """Sản phẩm KHÔNG có biến thể (máy lọc nước RO10): đã được báo giá thì vào ngữ cảnh mua; cam kết → code tra kho đúng SKU đó rồi mở gate."""
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)

    def test_quoted_simple_sku_enters_buying_context_and_opens_the_gate(self):
        _, _, meta = self.turn(NEW_PHONE, "máy lọc nước 10 lõi giá như nào?", [QUOTE_RO10])
        self.assertEqual((meta["reply_reading"], self.llm.read_calls), ({"source": "skipped"}, 0))        # chưa có sản phẩm trước lượt này
        self.llm.reader = lambda t: COMMIT
        before = self.llm.calls
        _, tc, meta = self.turn(NEW_PHONE, "ok lấy luôn", [])
        go = meta["gate_open"]
        self.assertEqual((meta["reply_reading"]["order_intent"], go["opened"], go["object"]["checked"]), ("commit", True, {"SKU-WF-RO10": True}))
        self.assertEqual(self.llm.calls - before, 0)
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])

    def test_simple_product_not_committed_is_read_but_not_opened(self):
        self.turn(NEW_PHONE, "máy lọc nước 10 lõi giá như nào?", [QUOTE_RO10])
        self.llm.reader = lambda t: {"order_intent": "other", "stance": "decline", "stance_quote": "mắc quá"}
        _, _, meta = self.turn(NEW_PHONE, "mắc quá", [])
        self.assertEqual((self.llm.read_calls, meta["gate_open"]["opened"], meta["gate_open"]["reason"]), (1, False, "intent_not_commit"))

    def test_product_with_variants_does_not_count_until_a_variant_is_named(self):
        self.turn(NEW_PHONE, "cho mình xem giày sneaker Urban Classic", [SEARCH])
        _, _, meta = self.turn(NEW_PHONE, "ok em lấy luôn", [])
        self.assertEqual((self.llm.read_calls, meta["reply_reading"]), (0, {"source": "skipped"}))


QUOTE_APX = ("pricing.get_quote", {"sku": "SKU-AP-X", "on": "2026-10-15"})
LIST = ("catalog.search", {"query": "máy lọc"})


class AmbiguousProductTest(GateBase):
    """Nhiều sản phẩm đang bàn → 'ok lấy' không đủ để biết lấy cái nào: không mở gate (LLM chính hỏi lại), ghi lý do vào trace."""
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})

    def commit(self, *prior):
        self.llm.reader = lambda t: {}
        for calls in prior:
            self.turn(NEW_PHONE, "xem sản phẩm", list(calls))
        self.llm.reader = lambda t: COMMIT
        _, tc, meta = self.turn(NEW_PHONE, "ok em lấy", [])
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])
        return meta["gate_open"]

    def test_two_quoted_products(self):
        go = self.commit([QUOTE_RO10, QUOTE_APX])
        self.assertEqual((go["opened"], go["reason"], set(go["object"]["products"])), (False, "ambiguous_product", {"SKU-WF-RO10", "SKU-AP-X"}))

    def test_list_of_results_not_yet_narrowed_down(self):
        go = self.commit([QUOTE_RO10], [LIST])
        self.assertEqual((go["opened"], go["reason"], go["object"]["listing"]), (False, "ambiguous_product", True))

    def test_quote_after_the_list_resolves_the_ambiguity(self):
        go = self.commit([LIST], [QUOTE_RO10])
        self.assertEqual((go["opened"], go["object"]["checked"]), (True, {"SKU-WF-RO10": True}))

    def test_a_named_variant_is_never_ambiguous(self):
        self.llm.reader = lambda t: {}
        self.turn(NEW_PHONE, "xem", [QUOTE_RO10, SEARCH])
        self.llm.reader = lambda t: COMMIT
        _, _, meta = self.turn(NEW_PHONE, "lấy 39 đen", [])
        self.assertEqual((meta["gate_open"]["opened"], meta["gate_open"]["sku"]), (True, "SKU-SN-CAS-39-DEN"))


class DraftExpiryTest(unittest.TestCase):
    def test_idle_draft_withdraws_itself(self):
        g = OrderGate()
        st = g.state("s")
        g.begin_turn("s", 1, "ok lấy")
        st.stage, st.last_decision = "collect", {"turn": 1, "allow": False, "action": "ask"}
        g.begin_turn("s", 1 + DRAFT_TTL_TURNS, "alo")
        self.assertIsNotNone(st.last_decision)                                  # chưa quá hạn
        g.begin_turn("s", 2 + DRAFT_TTL_TURNS, "alo")
        self.assertIsNone(st.last_decision)
        self.assertEqual(st.abandoned_turn, 2 + DRAFT_TTL_TURNS)


if __name__ == "__main__":
    unittest.main()
