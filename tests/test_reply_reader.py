"""Hiểu lời khách bằng LLM kèm trích dẫn nguyên văn (reply_reader) nối vào order gate.
LLM ở đây là GIẢ (kịch bản JSON) → test kiểm chứng phần CODE: kiểm chứng trích dẫn, đi dây vào gate, dự phòng khi LLM lỗi.
Việc LLM thật có hiểu đúng lời khách đa dạng hay không do `scripts/eval_reply_reader.py` đo (tốn tiền, cần duyệt)."""
import unittest

from src.harness.reply_reader import read_reply, verify
from tests.test_order_gate import GateBase, NEW_PHONE, TurnLLM, order


CHECK39 = ("inventory.check", {"sku": "SKU-SN-CAS-39-DEN"})


def burn_early(case):
    """Khách MỚI được đọc ở 2 lượt đầu (xem họ có nói đã liên hệ trước không); các test về "ngữ cảnh mua" cần cửa sổ đó đóng, nên đốt 2 lượt chào rồi đặt lại bộ đếm."""
    case.llm.reader = lambda t: {}
    for _ in range(2):
        case.turn(NEW_PHONE, "alo", [])
    case.llm.read_calls = 0


class ReaderLLM(TurnLLM):
    """TurnLLM + complete_json trả JSON do `reader(text)` quyết định (mô phỏng bộ đọc)."""
    def __init__(self, reader):
        super().__init__()
        self.reader, self.read_calls = reader, 0

    def complete_json(self, messages):
        self.read_calls += 1
        out = self.reader(messages[-1]["content"])
        if isinstance(out, Exception):
            raise out
        return out, {}


class VerifyTest(unittest.TestCase):
    def test_claims_without_verbatim_evidence_are_dropped(self):
        text = "ừ số em đang gọi đây, giao cho Đại nhé"
        r = verify({"stance": "agree", "stance_quote": "tôi đồng ý đặt", "affirmed": ["recipient_phone"], "affirmed_quote": "số em đang gọi",
                    "recipient_name": "Đại", "name_quote": "giao cho Đại", "payment": "COD", "payment_quote": "thanh toán khi nhận"}, text)
        self.assertEqual(r.stance, "other")                       # trích dẫn bịa → không tính là đồng ý
        self.assertEqual(r.affirmed, ["recipient_phone"])         # trích dẫn thật
        self.assertEqual(r.recipient_name, "Đại")
        self.assertIsNone(r.payment)                              # trích dẫn bịa

    def test_invalid_values_are_dropped(self):
        r = verify({"payment": "bitcoin", "payment_quote": "bitcoin", "affirmed": ["blood_type"], "affirmed_quote": "ok",
                    "recipient_name": "Lan", "name_quote": "ok"}, "ok bitcoin")
        self.assertIsNone(r.payment)
        self.assertEqual(r.affirmed, [])
        self.assertIsNone(r.recipient_name)                       # tên không nằm trong đoạn trích

    def test_no_llm_or_llm_error_returns_none(self):
        self.assertIsNone(read_reply(None, "ok", ""))
        self.assertIsNone(read_reply(TurnLLM(), "ok", ""))        # không có complete_json
        self.assertIsNone(read_reply(ReaderLLM(lambda t: RuntimeError("mạng")), "ok", ""))


class GuardLLM:
    """complete_json giả: lớp một trả `first`, lớp hai (chốt độc lập) trả `second` (hoặc ném lỗi nếu là Exception)."""
    available = True

    def __init__(self, first, second):
        self.first, self.second, self.calls = first, second, []

    def complete_json(self, messages):
        from src.harness.reply_reader import VERIFY_PROMPT
        kind = "second" if messages[0]["content"] == VERIFY_PROMPT else "first"
        self.calls.append(kind)
        out = getattr(self, kind)
        if isinstance(out, Exception):
            raise out
        return out, {}


class ConsentGuardTest(unittest.TestCase):
    TEXT, WAIT = "cứ thế đi em", {"stage": "readback"}
    AGREE = {"stance": "agree", "stance_quote": "cứ thế đi", "confidence": 0.9}

    def read(self, llm, guard, waiting=None):
        return read_reply(llm, self.TEXT, "Anh xác nhận đặt đơn giúp em nhé?", waiting or self.WAIT, guard=guard)

    def test_verify_needs_both_layers(self):
        yes = {"authorizes": True, "quote": "cứ thế đi"}
        self.assertTrue(self.read(GuardLLM(self.AGREE, yes), "verify").agrees)
        for no in ({"authorizes": False, "quote": ""}, {"authorizes": True, "quote": "tôi cho phép"}, {}, RuntimeError("mạng")):   # từ chối / trích bịa / thiếu / lỗi
            r = self.read(GuardLLM(self.AGREE, no), "verify")
            self.assertEqual(r.stance, "other", no)
            self.assertFalse(r.guard["passed"])

    def test_second_layer_is_independent_of_the_first_answer(self):
        llm = GuardLLM(self.AGREE, {"authorizes": True, "quote": "cứ thế đi"})
        seen = []
        orig = llm.complete_json
        llm.complete_json = lambda m: (seen.append(str(m)), orig(m))[1]
        self.read(llm, "verify")
        self.assertNotIn("agree", seen[1])                          # lớp hai không thấy kết luận lớp một

    def test_confidence_mode_uses_no_extra_call(self):
        hi, lo = GuardLLM(self.AGREE, None), GuardLLM({**self.AGREE, "confidence": 0.5}, None)
        self.assertTrue(self.read(hi, "confidence").agrees)
        self.assertEqual(self.read(lo, "confidence").stance, "other")
        self.assertEqual(hi.calls, ["first"])
        self.assertEqual(self.read(GuardLLM({"stance": "agree", "stance_quote": "cứ thế đi"}, None), "confidence").stance, "other")   # thiếu confidence = thấp

    def test_guard_only_at_the_step_right_after_readback(self):
        llm = GuardLLM(self.AGREE, {"authorizes": False})
        self.assertTrue(self.read(llm, "verify", {"stage": "collect"}).agrees)
        self.assertEqual(llm.calls, ["first"])
        self.assertTrue(self.read(GuardLLM(self.AGREE, {"authorizes": False}), "none").agrees)       # chế độ đo


class GateUsesReadingTest(GateBase):
    def setUp(self):
        super().setUp()
        self.llm = self.orch.llm_client = ReaderLLM(lambda t: {})
        burn_early(self)

    def test_phone_confirmed_in_words_no_regex_would_catch(self):
        text = "ừa cái số em đang gọi đây nè, giao về 45/1 đường 10 phường linh đông, tên Đại"
        self.llm.reader = lambda t: {"stance": "other", "only_answers": True, "affirmed": ["recipient_phone"], "affirmed_quote": "cái số em đang gọi đây nè"}
        self.turn(NEW_PHONE, "ok lấy 39 đen", [CHECK39])
        _, _, meta = self.turn(NEW_PHONE, text, [order()])
        rt = meta["reply_reading"]
        self.assertEqual((rt["source"], rt["affirmed"], rt["evidence"]["affirmed"]), ("llm", ["recipient_phone"], "cái số em đang gọi đây nè"))
        self.assertEqual(rt["llm_calls"], 1)
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_phone"]["status"], "confirmed")
        self.assertEqual(ev["to_confirm"], [])
        self.assertEqual(self.llm.read_calls, 1)                   # lượt 1 (chưa có biến thể được tra) bỏ qua, lượt 2 mới đọc

    def test_agreement_with_invented_quote_does_not_create_an_order(self):
        self.llm.reader = lambda t: {"stance": "agree", "stance_quote": "tôi đồng ý chốt đơn", "only_answers": True}
        self.turn(NEW_PHONE, "ok lấy 39 đen", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
        _, tc, meta = self.turn(NEW_PHONE, "hmm để xem đã", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
        self.assertEqual(self.created(tc), [])

    def test_reader_is_skipped_until_a_concrete_variant_is_in_play(self):
        """Máy trạng thái tiết kiệm lần gọi: lượt khám phá sản phẩm (chưa tra/báo giá/đặt biến thể nào) không cần đọc ý đồng ý/xác nhận."""
        self.llm.reader = lambda t: {"only_answers": True}
        _, _, meta = self.turn(NEW_PHONE, "cho mình hỏi giày sneaker", [])
        self.assertEqual(meta["reply_reading"], {"source": "skipped"})
        self.assertEqual(self.llm.read_calls, 0)
        self.turn(NEW_PHONE, "lấy 39 đen", [CHECK39])
        self.assertEqual(self.llm.read_calls, 0)                   # lượt đầu nhắc biến thể: lúc đọc chưa có tra cứu nào
        self.turn(NEW_PHONE, "ừ", [])
        self.assertEqual(self.llm.read_calls, 1)                   # từ đây đã là ngữ cảnh mua

    def test_llm_failure_falls_back_to_regex(self):
        self.llm.reader = lambda t: RuntimeError("hết hạn mức")
        self.turn(NEW_PHONE, "ok lấy 39 đen", [CHECK39])
        _, _, meta = self.turn(NEW_PHONE, "đúng sdt, 45/1 đường 10 phường linh đông hồ chí minh, Đại", [order()])
        self.assertEqual(meta["reply_reading"], {"source": "regex_fallback"})
        self.assertEqual(meta["order_gate"][-1]["fields"]["recipient_phone"]["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()


class AddressReadingTest(unittest.TestCase):
    def test_address_without_keywords_is_kept_with_verbatim_quote(self):          # B1
        r = verify({"address": "14 Trần Phú, Hà Đông", "address_quote": "giao 14 Trần Phú, Hà Đông"}, "giao 14 Trần Phú, Hà Đông, COD nhé")
        self.assertEqual(r.address, "14 Trần Phú, Hà Đông")
        t = "gui ve so 129 khu nam viet a ngu hanh son da nang"
        self.assertEqual(verify({"address": "so 129 khu nam viet a ngu hanh son da nang", "address_quote": t}, t).address, "so 129 khu nam viet a ngu hanh son da nang")

    def test_invented_or_token_address_is_dropped(self):
        self.assertIsNone(verify({"address": "1 Lê Lợi", "address_quote": "1 Lê Lợi"}, "giao về địa chỉ cũ nhé").address)
        self.assertIsNone(verify({"address": "<ADDR_1>", "address_quote": "<ADDR_1>"}, "giao <ADDR_1>").address)


class OldAddressGateTest(unittest.TestCase):
    def test_old_address_reference_without_saved_address_says_so(self):           # B2
        from types import SimpleNamespace
        from src.harness.order_gate import OrderGate, OrderDraft, OrderKnown, ProductInfo
        g = OrderGate()
        g.begin_turn("S", 1, "giao về địa chỉ cũ nhé", reading=SimpleNamespace(agrees=False, declines=False, affirmed=["address"]))
        d = g.evaluate("S", OrderDraft(sku="SKU-X", payment="COD"), OrderKnown(caller_phone="0911265844"), ProductInfo(name="Máy X", unit_price=100000))
        self.assertIn("chưa có địa chỉ đã lưu", d["say"])


class TransferRequestTest(unittest.TestCase):
    def test_transfer_request_needs_verbatim_quote(self):                         # C3
        t = "lấy 3 máy xuất hóa đơn đỏ, nối máy thầy gặp bên khách hàng tổ chức B2B"
        self.assertTrue(verify({"asks_transfer": True, "transfer_quote": "nối máy thầy gặp bên khách hàng tổ chức B2B"}, t).asks_transfer)
        self.assertFalse(verify({"asks_transfer": True, "transfer_quote": "cho gặp quản lý"}, t).asks_transfer)


class QtyReadingTest(unittest.TestCase):
    def test_qty_needs_number_in_verbatim_quote(self):                           # TEST-64/80
        t = "Duy chốt thành 5 món Túi trữ sữa Sunmum 50 túi"
        self.assertEqual(verify({"qty": 5, "qty_quote": "5 món"}, t).qty, 5)
        self.assertIsNone(verify({"qty": 3, "qty_quote": "5 món"}, t).qty)             # số không nằm trong trích dẫn
        self.assertEqual(verify({"qty": 3, "qty_quote": "lấy ba bộ"}, "ok lấy ba bộ nhé").qty, 3)
