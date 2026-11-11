"""Sửa sau phân tích GĐ2 (CHECKING §11.88), mục 1–5. Không gọi LLM thật."""
import unittest

from src.harness.extractor import extract_claims
from tests.test_order_gate import GateBase, NEW_PHONE, KNOWN_PHONE, order, SKU39
from tests.test_reply_reader import ReaderLLM, burn_early
from tests.test_gate_open import COMMIT, QUOTE_RO10

AMBIGUOUS_PHONE = "0958421083"       # dùng chung giữa C034 và C035 (crm_seed.json)
QUOTE_APX = ("pricing.get_quote", {"sku": "SKU-AP-X", "on": "2026-10-15"})


def phone_args(tc, name):
    return [c["args"] for c in tc if c["name"] == name]


class OrderArgsTest(GateBase):
    """Mục 1: order.create luôn mang price_vnd (giá sau KM của MỘT sản phẩm), kể cả khi LLM bỏ trường này."""

    def full_flow(self, args):
        self.turn(NEW_PHONE, "Anh muốn lấy giày Casual size 39 màu đen", [order(**args)], "Dạ em lên đơn ngay ạ.")
        self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD", **args)])
        self.turn(NEW_PHONE, "ok số này, COD nhé", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD", **args)])
        return self.turn(NEW_PHONE, "ok chốt đi em", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD", **args)], "Dạ em đã lên đơn rồi ạ.")

    def test_missing_price_is_filled_from_the_quote(self):
        _, tc, _ = self.full_flow({})
        made = [c for c in tc if c["name"] == "order.create"]
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["args"]["price_vnd"], 890000)

    def test_price_given_by_llm_is_kept(self):
        _, tc, _ = self.full_flow({"price_vnd": 890000})
        self.assertEqual([c["args"]["price_vnd"] for c in tc if c["name"] == "order.create"], [890000])


class QuotePhoneTest(GateBase):
    """Mục 1: pricing.get_quote không có SĐT → code chèn SĐT người gọi (KM theo hồ sơ cần SĐT); không chèn khi SĐT dùng chung."""

    def test_phone_is_injected_when_llm_omits_it(self):
        _, tc, _ = self.turn(KNOWN_PHONE, "giá AirPure X sao em", [QUOTE_APX], "Dạ ạ.")
        args = phone_args(tc, "pricing.get_quote")
        self.assertEqual([a.get("customer_phone") for a in args], [KNOWN_PHONE])

    def test_given_phone_is_not_overwritten(self):
        _, tc, _ = self.turn(KNOWN_PHONE, "giá", [("pricing.get_quote", {**QUOTE_APX[1], "customer_phone": "CURRENT_CUSTOMER"})], "Dạ ạ.")
        self.assertEqual([a["customer_phone"] for a in phone_args(tc, "pricing.get_quote")], [KNOWN_PHONE])

    def test_shared_phone_gets_no_injection(self):
        _, tc, _ = self.turn(AMBIGUOUS_PHONE, "giá AirPure X", [QUOTE_APX], "Dạ ạ.")
        self.assertTrue(all(not a.get("customer_phone") for a in phone_args(tc, "pricing.get_quote")))


class QtyCarryTest(GateBase):
    """Mục 1: khách mua nhiều máy — gate do code mở không được rơi về qty 1."""

    def test_gate_opened_by_code_keeps_the_quoted_qty(self):
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        self.turn(NEW_PHONE, "anh muốn mua 2 máy AirPure X", [("pricing.get_quote", {"sku": "SKU-AP-X", "qty": 2, "on": "2026-10-15"})], "Dạ ạ.")
        self.llm.reader = lambda t: COMMIT
        _, tc, meta = self.turn(NEW_PHONE, "ok lấy luôn", [])
        self.assertTrue(meta["gate_open"]["opened"], meta["gate_open"])
        quote = phone_args(tc, "pricing.quote_order")[-1]            # từ 2 máy: giá từng máy lấy bằng pricing.quote_order (BTC 11/2026)
        self.assertEqual(quote["lines"], [{"sku": "SKU-AP-X", "qty": 2}])

    def test_basket_comes_from_latest_quote_order(self):
        sid = "SESS-B"
        self.orch._call_log[sid] = [{"name": "pricing.get_quote", "args": {"sku": "SKU-AP-X"}, "result": {}},
                                    {"name": "pricing.quote_order", "args": {"lines": [{"sku": "SKU-AP-MINI", "qty": 1}, {"sku": "SKU-AP-X", "qty": 2}]}, "result": {"units": []}}]
        self.assertEqual(self.orch._basket_in_play(sid, "SKU-AP-X"), [{"sku": "SKU-AP-X", "qty": 2}, {"sku": "SKU-AP-MINI", "qty": 1}])
        self.assertEqual(self.orch._qty_in_play(sid, "SKU-AP-X"), 2)

    def test_default_is_one(self):
        sid = "SESS-X"
        self.orch._call_log[sid] = [{"name": "pricing.get_quote", "args": {"sku": "SKU-AP-X"}, "result": {}}]
        self.assertEqual(self.orch._qty_in_play(sid, "SKU-AP-X"), 1)
        self.assertEqual(self.orch._qty_in_play(sid, "SKU-AP-PRO"), 1)
        self.orch._call_log[sid].append({"name": "order.create", "args": {"sku": "SKU-AP-X", "qty": 3}, "result": {}})
        self.assertEqual(self.orch._qty_in_play(sid, "SKU-AP-X"), 3)


class IdentityQuestionTest(GateBase):
    """Mục 2: SĐT dùng chung — khách mở đầu bằng câu hỏi giá vẫn được hỏi xác nhận tên (một lần/cuộc)."""

    def test_question_is_appended_once(self):
        txt, _, meta = self.turn(AMBIGUOUS_PHONE, "cho hỏi máy lọc nước Karofi 9 lõi giá bao nhiêu?", [("pricing.get_quote", {"sku": "SKU-WF-RO9", "on": "2026-10-15"})],
                                 "Dạ máy giá 5.990.000đ ạ. Anh/chị cần thêm gì không ạ?")
        self.assertIn("5.990.000", txt)                                        # vẫn trả lời thông tin công khai
        self.assertIn("xác nhận tên", txt)
        self.assertNotIn("cần thêm gì", txt)                                   # chỉ một câu hỏi cuối lượt
        txt2, _, _ = self.turn(AMBIGUOUS_PHONE, "ok", [], "Dạ vâng ạ.")
        self.assertNotIn("xác nhận tên", txt2)

    def test_llm_already_asked_keeps_text(self):
        reply = "Dạ máy giá 5.990.000đ ạ. Cho em xin phép xác nhận tên mình để hỗ trợ đúng thông tin ạ?"
        txt, _, _ = self.turn(AMBIGUOUS_PHONE, "giá Karofi 9 lõi?", [("pricing.get_quote", {"sku": "SKU-WF-RO9", "on": "2026-10-15"})], reply)
        self.assertEqual(txt.count("xác nhận tên"), 1)

    def test_known_customer_not_asked(self):
        txt, _, _ = self.turn(KNOWN_PHONE, "alo", [], "Dạ em nghe ạ.")
        self.assertNotIn("xác nhận tên", txt)


class OpenQuestionGateTest(GateBase):
    """Mục 3: khách vừa hỏi vừa chốt mua → LLM trả lời, code nối bước kế tiếp của gate (không để LLM tự hỏi thông tin giao hàng)."""

    def test_commit_with_question_opens_the_gate_after_the_answer(self):
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)
        self.turn(NEW_PHONE, "máy lọc nước 10 lõi giá như nào?", [QUOTE_RO10], "Dạ giá 6.900.000đ ạ.")
        self.llm.reader = lambda t: {**COMMIT, "intent_quote": "lên đơn", "asks_question": True}
        before = self.llm.calls
        txt, tc, meta = self.turn(NEW_PHONE, "có freeship không em, lên đơn cho anh", [], "Dạ có freeship ạ. Anh cho em xin tên người nhận và thanh toán ạ?")
        go = meta["gate_open"]
        self.assertEqual((go["opened"], go["reason"]), (True, "opened_after_answer"))
        self.assertEqual(self.llm.calls - before, 1)                           # LLM chính trả lời câu hỏi
        self.assertIn("freeship", txt)
        self.assertFalse(meta["order_gate"][-1]["allow"])                      # gate đã vào
        self.assertIn("địa chỉ", txt)                                          # câu hỏi của gate được nối
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])

    def test_decline_with_question_still_excluded(self):
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)
        self.turn(NEW_PHONE, "máy lọc nước 10 lõi giá như nào?", [QUOTE_RO10], "Dạ ạ.")
        self.llm.reader = lambda t: {**COMMIT, "asks_question": True, "stance": "decline", "stance_quote": "lấy"}
        _, _, meta = self.turn(NEW_PHONE, "mắc quá, lấy được không?", [], "Dạ ạ.")
        self.assertFalse(meta["gate_open"]["opened"])


class PriceTopicGateTest(GateBase):
    """Khách vừa chốt mua vừa hỏi/chất vấn về giá hoặc khuyến mãi → KHÔNG mở gate sớm (SAMPLE-05: câu hỏi của gate đã thay mất câu trả lời về mức giảm)."""

    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)
        self.turn(NEW_PHONE, "máy lọc nước 10 lõi giá như nào?", [QUOTE_RO10], "Dạ giá 6.900.000đ ạ.")

    def say(self, reading, text="lấy máy lọc nước giảm 500.000 hôm trước nhé"):
        self.llm.reader = lambda t: reading
        return self.turn(NEW_PHONE, text, [QUOTE_RO10], "Dạ hiện bên em không còn khuyến mãi đó ạ.")

    def test_verify_keeps_only_quoted_price_topic(self):
        from src.harness.reply_reader import verify
        text = "lấy máy lọc nước giảm 500.000 hôm trước nhé"
        self.assertTrue(verify({"asks_price_promo": True, "price_promo_quote": "giảm 500.000 hôm trước"}, text).price_topic)
        self.assertFalse(verify({"asks_price_promo": True, "price_promo_quote": "giảm 300.000"}, text).price_topic)      # trích dẫn bịa
        self.assertFalse(verify({"asks_price_promo": True}, text).price_topic)                                           # thiếu trích dẫn
        self.assertFalse(verify({"price_promo_quote": "giảm 500.000"}, text).price_topic)

    def test_price_question_with_commit_does_not_open_the_gate(self):
        txt, tc, meta = self.say({**COMMIT, "asks_question": True, "asks_price_promo": True, "price_promo_quote": "giảm 500.000 hôm trước"})
        go = meta["gate_open"]
        self.assertFalse(go["opened"])
        self.assertIn("price_topic", go["exclusions"])
        self.assertIn("không còn khuyến mãi", txt)                               # câu trả lời của LLM về giá còn nguyên, không bị gate thay
        self.assertFalse(meta.get("order_gate"))
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])

    def test_non_price_question_still_opens_after_the_answer(self):
        _, _, meta = self.say({**COMMIT, "intent_quote": "lấy", "asks_question": True}, "có freeship không em, lấy luôn")
        self.assertEqual((meta["gate_open"]["opened"], meta["gate_open"]["reason"]), (True, "opened_after_answer"))


class ScopeNoticeTest(GateBase):
    """GEN-08: chuyển máy ca ngoài phạm vi/an toàn thành công → lời agent luôn có cụm thừa nhận chưa có thông tin chuyên môn."""
    BRIEF = {"escalation_reason": "y tế"}
    TEXT = "máy hút sữa dùng khi mẹ đang uống kháng sinh có ảnh hưởng gì không"

    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {"category": "scope_safety", "category_quote": "uống kháng sinh", "authorized": False})

    def test_notice_added_and_matches_btc_abstain_keywords(self):
        from tests.test_gd2_fixes import ABSTAIN_KW
        txt, tc, _ = self.turn(NEW_PHONE, self.TEXT, [("handoff.transfer", {"brief": self.BRIEF})], "Dạ, em đã chuyển máy cho nhân viên phụ trách ạ.")
        self.assertTrue(any(c["name"] == "handoff.transfer" and "error" not in c["result"] for c in tc))
        self.assertTrue(txt.startswith("Dạ phần này em chưa có thông tin chuyên môn"), txt)
        self.assertIn("Em đã chuyển máy", txt)
        self.assertEqual(txt.count("Dạ"), 1)
        self.assertTrue(any(k in txt.lower() for k in ABSTAIN_KW))

    def test_not_duplicated_when_llm_already_said_it(self):
        reply = "Dạ em chưa có thông tin chuyên môn về việc này, em chuyển nhân viên ạ."
        txt, _, _ = self.turn(NEW_PHONE, self.TEXT, [("handoff.transfer", {"brief": self.BRIEF})], reply)
        self.assertEqual(txt.lower().count("chưa có thông tin"), 1)

    def test_no_notice_when_transfer_was_blocked_or_not_scope_safety(self):
        self.llm.reader = lambda t: {"category": "other", "authorized": False}
        txt, tc, _ = self.turn(NEW_PHONE, "mắc quá vậy?", [("handoff.transfer", {"brief": self.BRIEF})], "Dạ em xin lỗi ạ.")
        self.assertFalse([c for c in tc if c["name"] == "handoff.transfer"])
        self.assertNotIn("chuyên môn", txt)
        self.llm.reader = lambda t: {"category": "other", "authorized": True, "basis": "asked", "quote": "gặp nhân viên"}
        txt, _, _ = self.turn(NEW_PHONE, "cho gặp nhân viên đi", [("handoff.transfer", {"brief": self.BRIEF})], "Dạ em chuyển máy ạ.")
        self.assertNotIn("chuyên môn", txt)

    def test_helper_skips_order_incident_calls(self):
        H = type(self.orch)
        calls = [{"name": "order.status", "result": {"orders": [{}]}}, {"name": "handoff.transfer", "result": {"status": "queued"}}]
        v = {"authorized": True, "category": "scope_safety"}
        self.assertEqual(H._ensure_scope_notice("Dạ em chuyển ạ.", calls, v), "Dạ em chuyển ạ.")
        self.assertEqual(H._ensure_scope_notice("Dạ em chuyển ạ.", calls[1:], None), "Dạ em chuyển ạ.")


ABSTAIN_KW = ("không có thông tin", "chưa có thông tin", "em chưa rõ", "em không chắc", "em sẽ kiểm tra", "chưa nắm được")   # reference_eval.ABSTAIN_KW


class ConfirmationCallTest(GateBase):
    """Đơn có needs_confirmation_call (AirPure X 4.890.000đ > 2 triệu): câu chốt đơn do code dựng phải báo sẽ có người gọi xác nhận."""
    def test_created_reply_mentions_the_confirmation_call(self):
        o = lambda **kw: order(sku="SKU-AP-X", price_vnd=4890000, recipient_name="Lan", address="<ADDR_1>", payment="COD", **kw)
        self.turn(NEW_PHONE, "Anh muốn lấy máy lọc AirPure X", [order(sku="SKU-AP-X", price_vnd=4890000)], "Dạ ạ.")
        self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội", [o()])
        self.turn(NEW_PHONE, "ok số này, COD nhé", [o()])
        txt, tc, _ = self.turn(NEW_PHONE, "ok chốt đi em", [o()], "Dạ em đã lên đơn rồi ạ.")
        self.assertEqual(len(self.created(tc)), 1)
        self.assertTrue(self.created(tc)[0]["result"].get("needs_confirmation_call"))
        self.assertIn("gọi", txt)
        self.assertIn("xác nhận đơn", txt)


class AltPriceClaimTest(unittest.TestCase):
    """Mục 5: giá của mẫu khác trong danh sách không phải claim `price_vnd` về sản phẩm chủ đề."""
    SHORTLIST = {"name": "product.shortlist", "args": {}, "result": {"items": [
        {"sku": "SKU-SS-AX40", "name": "Máy lọc không khí Samsung AX40", "list_price_vnd": 6490000},
        {"sku": "SKU-AP-PRO", "name": "Máy lọc không khí AirPure Pro", "list_price_vnd": 7990000},
        {"sku": "SKU-AP-Y", "name": "Máy lọc không khí AirPure Y", "list_price_vnd": 5200000}]}}
    TEXT = ("Em xin liệt kê: Máy lọc không khí Samsung AX40 - Giá: 6.490.000 VNĐ; Máy lọc không khí AirPure Pro - Giá: 7.990.000 VNĐ; "
            "Máy lọc không khí AirPure Y - Giá: 5.200.000 VNĐ ạ.")

    def fields(self, text, tc):
        return {(c["field"], c["value"]) for c in extract_claims(text, tc)}

    def test_other_products_become_alt_price(self):
        f = self.fields(self.TEXT, [self.SHORTLIST])
        self.assertIn(("price_vnd", 6490000), f)
        self.assertNotIn(("price_vnd", 7990000), f)
        self.assertIn(("alt_price_vnd", 7990000), f)
        self.assertIn(("alt_price_vnd", 5200000), f)

    def test_quote_subject_wins_over_shortlist_order(self):
        quote = {"name": "pricing.get_quote", "args": {"sku": "SKU-AP-Y"}, "result": {"sku": "SKU-AP-Y", "final_price_vnd": 5200000, "list_price_vnd": 5200000}}
        f = self.fields(self.TEXT, [self.SHORTLIST, quote])
        self.assertIn(("price_vnd", 5200000), f)
        self.assertIn(("alt_price_vnd", 6490000), f)

    def test_without_tool_results_nothing_changes(self):
        f = self.fields("Dạ mẫu AirPure Y giá 5.200.000đ ạ.", [])
        self.assertIn(("price_vnd", 5200000), f)

    def test_single_product_quote_is_untouched(self):
        quote = {"name": "pricing.get_quote", "args": {"sku": "SKU-AP-Y"}, "result": {"sku": "SKU-AP-Y", "final_price_vnd": 4800000, "list_price_vnd": 5200000,
                                                                                   "items": [{"sku": "SKU-AP-Y", "name": "Máy lọc không khí AirPure Y"}]}}
        f = self.fields("Máy lọc không khí AirPure Y giá gốc 5.200.000đ, còn 4.800.000đ ạ.", [quote])
        self.assertEqual({("list_price_vnd", 5200000), ("price_vnd", 4800000)} - f, set())


class PromptTest(GateBase):
    """Mục 4: các luật mới có trong system prompt."""
    def test_rules_present(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")
        sys_msg = self.orch._build_llm_messages(t, brief, [], "2026-10-15", None)[0]["content"]
        for needle in ("chưa có thông tin chuyên môn", "CẢ về bảo hành LẪN về đổi trả", "giá MỘT sản phẩm", "needs_confirmation_call=true"):
            self.assertIn(needle, sys_msg)


class NoLLMFallbackTest(GateBase):
    """Nhánh dự phòng mất LLM: chưa biết sản phẩm thì KHÔNG báo giá / lên đơn sản phẩm tự chọn (trước đây mặc định cứng SKU-AP-Y; CHECKING §11.92)."""

    def setUp(self):
        super().setUp()
        self.orch.llm_client = None

    def test_unknown_product_asks_instead_of_quoting(self):
        txt, tc, _ = self.turn(NEW_PHONE, "shop ơi máy hút sữa Spectra S1 giá bao nhiêu ạ", [])
        self.assertEqual(tc, [])
        self.assertNotIn("AirPure", txt)
        self.assertNotIn("5.200.000", txt)
        self.assertIn("sản phẩm nào", txt)

    def test_unknown_product_never_creates_an_order(self):
        _, tc, _ = self.turn(NEW_PHONE, "lên đơn cho anh nhé", [])
        self.assertEqual([c for c in tc if c["name"].startswith(("order.", "pricing."))], [])

    def test_advisor_returns_no_sku_without_a_known_product(self):
        from src.agents.specialists import SalesAdvisorAgent
        self.assertIsNone(SalesAdvisorAgent(None).advise({"call_brief": {}})["suggested_sku"])
        self.assertEqual(SalesAdvisorAgent(None).advise({"call_brief": {"product_advised": "SKU-AP-X"}})["suggested_sku"], "SKU-AP-X")


if __name__ == "__main__":
    unittest.main()
