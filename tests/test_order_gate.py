"""Order gate (src/harness/order_gate.py): checklist → hỏi/xác nhận → đọc lại đơn 1 lần → chỉ tạo đơn khi khách đồng ý RÕ RÀNG ở lượt sau."""
import unittest

from tests._helpers import build_components, advisor_suggests

SKU39, SKU40 = "SKU-SN-CAS-39-DEN", "SKU-SN-CAS-40-DEN"
NEW_PHONE = "0911222333"           # không có trong CRM → khách mới
KNOWN_PHONE = "0984726714"         # C001 Hoa (chị) trong crm_seed


class TurnLLM:
    """LLM giả: mỗi lượt chạy các tool call trong kịch bản rồi trả text (không gọi mạng)."""
    available = True

    def __init__(self):
        self.script = []
        self.calls = 0                      # số lần LLM THỰC SỰ được gọi (order gate tự xử lý lượt trả lời gate → không gọi LLM)

    def get_base_tools(self):
        return []

    def add(self, calls, text):
        self.script.append((calls, text))

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        self.calls += 1
        calls, text = self.script.pop(0)
        log = []
        for name, args in calls:
            result, executed = tool_executor(name, args)
            log.append({"name": name, "tool": name, "args": executed, "result": result})
        return text, log, {"prompt_tokens": 0, "completion_tokens": 0}


def order(sku=SKU39, **kw):
    args = {"customer_phone": "CURRENT_CUSTOMER", "sku": sku, "qty": 1, "price_vnd": 890000}
    args.update(kw)
    return ("order.create", args)


class GateBase(unittest.TestCase):
    def setUp(self):
        self.c = build_components(order_gate=True)
        self.orch = self.c["orchestrator"]
        self.llm = TurnLLM()
        self.orch.llm_client = self.llm

    def turn(self, phone, text, calls, reply="Dạ em nghe ạ.", date="2026-10-15"):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), date)
        self.llm.script.clear()             # kịch bản của lượt trước mà LLM không được gọi (code xử lý) không được dồn sang lượt sau
        self.llm.add(calls, reply)
        return self.orch.process_turn(t, brief, current_date=date, call_name="call_1")

    def created(self, tool_calls):
        return [c for c in tool_calls if c["name"] == "order.create" and (c.get("result") or {}).get("status") == "created"]


class ConsentTest(unittest.TestCase):
    def test_explicit_consent(self):
        from src.harness.order_gate import is_explicit_consent as c
        for ok in ("ok em", "Đúng rồi", "Vâng", "đồng ý", "ok đúng rồi em", "chốt luôn", "ok lên đơn cho anh, COD nhé."):
            self.assertTrue(c(ok), ok)
        for no in ("ừ để chị hỏi chồng đã", "được, nhưng giao sau 5h nhé", "không, đổi địa chỉ khác", "giao mấy ngày?", "khoan đã", "ừm",
                   "ok nhưng cho anh đổi size", "sai rồi, số nhà 14 chứ", "Em ơi cái này bảo hành bao lâu?"):
            self.assertFalse(c(no), no)

    def test_complaints_with_a_polite_particle_are_not_consent(self):
        """Audit #2: "dạ"/"vâng"/"ừ" chỉ là lời đáp lại; kèm một câu than phiền/ý khác thì KHÔNG phải đồng ý chốt đơn."""
        from src.harness.order_gate import is_explicit_consent as c
        for no in ("Dạ đắt thật đấy", "Dạ nhiều tiền thế", "Dạ chị đang bận lắm", "Vâng, đắt thật", "Ừ, giá cũng cao", "Dạ em nghe không rõ lắm",
                   "Có, hơi đắt so với chỗ khác", "Dạ mắc ghê"):
            self.assertFalse(c(no), no)

    def test_plain_acknowledgements_and_strong_phrases_are_still_consent(self):
        from src.harness.order_gate import is_explicit_consent as c
        for ok in ("Dạ", "Dạ vâng ạ", "Vâng ạ", "Ừ", "Có", "Dạ cũng được", "Dạ được ạ", "Dạ đúng rồi ạ", "Ok em", "Dạ ok em nhé", "ừ được", "Dạ chốt đi em"):
            self.assertTrue(c(ok), ok)

    def test_confirming_stored_info_may_carry_new_info_but_order_consent_may_not(self):
        """Xác nhận THÔNG TIN ĐÃ LƯU được kèm thông tin mới ("đúng sdt, giao về …"); còn chốt đơn sau khi đọc lại thì phải là lời đồng ý trơn."""
        from src.harness.order_gate import is_explicit_consent as c
        text = "đúng sdt, giao về 45/1 đường 10 phường Linh Đông, Đại"
        self.assertTrue(c(text, max_words=40, lenient=True))
        self.assertFalse(c(text, max_words=40))
        self.assertFalse(c("Dạ đắt thật đấy", max_words=40))

    def test_payment_detection(self):
        from src.harness.order_gate import detect_payment as d
        self.assertEqual(d("COD nhé"), "COD")
        self.assertEqual(d("nhận hàng rồi trả tiền"), "COD")
        self.assertEqual(d("chuyển khoản đi"), "bank")
        self.assertEqual(d("cod thôi, à thôi chuyển khoản"), "bank")           # đổi ý: lấy lần nhắc cuối
        self.assertIsNone(d("giao nhanh giúp anh"))


class NewCustomerTest(GateBase):
    def test_new_customer_full_flow(self):
        # lượt 1: khách muốn mua, chưa nói gì → hỏi (không tạo đơn)
        _, tc, meta = self.turn(NEW_PHONE, "Anh muốn lấy giày Casual size 39 màu đen", [order(payment="COD")], "Dạ em lên đơn ngay ạ.")
        self.assertEqual(self.created(tc), [])
        self.assertFalse(any(c["name"] == "order.create" for c in tc), "lời gọi bị chặn không được nằm trong tool_calls của trace")
        ev = meta["order_gate"][-1]
        self.assertFalse(ev["allow"])
        self.assertIn("address", ev["missing"])
        self.assertEqual(ev["fields"]["payment"]["status"], "missing")          # LLM tự điền COD nhưng khách chưa nói → không tính
        # lượt 2: khách nêu tên + địa chỉ + SĐT nhận là số đang gọi cần xác nhận
        txt, tc, meta = self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội",
                                  [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
        self.assertEqual(self.created(tc), [])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_name"]["status"], "stated")
        self.assertEqual(ev["fields"]["address"]["status"], "stated")
        self.assertIn("payment", ev["missing"])
        self.assertIn("thanh toán", txt.lower())                                 # câu hỏi do code ép vào lời agent
        # lượt 3: khách trả lời thanh toán + đồng ý số đang gọi → đủ checklist → ĐỌC LẠI đơn, chưa tạo
        txt, tc, meta = self.turn(NEW_PHONE, "ok số này, COD nhé", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
        self.assertEqual(self.created(tc), [])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["action"], "readback")
        self.assertIn("xác nhận", txt)
        self.assertIn("12 đường Nguyễn Trãi", txt)                               # token địa chỉ đã được mở khi nói với khách
        self.assertNotIn("<ADDR_", txt)
        self.assertIn("890.000đ", txt)
        # lượt 4: khách đồng ý rõ ràng → LLM gọi lại đúng tham số → đơn được tạo
        _, tc, meta = self.turn(NEW_PHONE, "ok chốt đi em", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")], "Dạ em đã lên đơn rồi ạ.")
        self.assertEqual(len(self.created(tc)), 1)
        self.assertEqual(meta["order_gate"][-1]["action"], "allow")
        made = self.created(tc)[0]
        self.assertTrue(made["result"]["order_id"].startswith("OD"))
        self.assertEqual(self.llm.calls, 1, "chỉ lượt đầu (khách nói ý định mua) cần LLM; các lượt trả lời gate do code xử lý")

    def test_ok_before_readback_does_not_create(self):
        """Khách nói 'ok lên đơn COD nhé' + đủ thông tin trong CÙNG lượt: vẫn phải đọc lại đơn trước, không tạo ngay."""
        _, tc, meta = self.turn(NEW_PHONE, "ok lên đơn giày Casual 39 đen, COD nhé, giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, số này",
                                [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
        self.assertEqual(self.created(tc), [])
        evs = meta["order_gate"]
        self.assertFalse(evs[-1]["allow"])
        self.assertIn(evs[-1]["action"], ("confirm", "readback"))               # SĐT nhận = số đang gọi: cần xác nhận hoặc đọc lại
        if evs[-1]["action"] == "confirm":
            _, tc, meta = self.turn(NEW_PHONE, "đúng rồi", [order(recipient_name="Lan", address="<ADDR_1>", payment="COD")])
            self.assertEqual(meta["order_gate"][-1]["action"], "readback")
            self.assertEqual(self.created(tc), [])

    def test_llm_invented_values_are_not_counted(self):
        """LLM điền tên/địa chỉ mà khách CHƯA nói → coi như thiếu (không tạo đơn bằng dữ liệu bịa)."""
        _, tc, meta = self.turn(NEW_PHONE, "anh muốn mua giày Casual 39 đen",
                                [order(recipient_name="Nguyễn Văn A", address="1 phố Bịa, Hà Nội", payment="COD")])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_name"]["status"], "missing")
        self.assertEqual(ev["fields"]["address"]["status"], "missing")
        self.assertEqual(self.created(tc), [])

    def test_parent_sku_needs_variant(self):
        _, tc, meta = self.turn(NEW_PHONE, "anh muốn mua giày Casual", [order(sku="SKU-SN-CAS")])
        self.assertEqual(meta["order_gate"][-1]["fields"]["item"]["status"], "missing")

    def test_false_claim_when_blocked_is_replaced(self):
        txt, tc, meta = self.turn(NEW_PHONE, "lên đơn cho anh", [order()], "Dạ em đã lên đơn thành công rồi ạ.")
        self.assertEqual(self.created(tc), [])
        self.assertNotIn("thành công", txt.lower())                       # lời "đã lên đơn thành công" bị guardrail thay vì đơn chưa tạo
        self.assertTrue(any(w in txt.lower() for w in ("địa chỉ", "thanh toán", "tên")))     # và câu hỏi của gate vẫn được nói


class ReturningCustomerTest(GateBase):
    def _save(self):
        m = self.c["memory"]
        m.set_profile_fact("C001", "shipping_address", "số 8 phố Hoàng Hoa Thám, quận Ba Đình, Hà Nội")
        m.set_profile_fact("C001", "payment_method", "COD")
        m.set_profile_fact("C001", "recipient_name", "Hoa")

    def test_saved_address_is_only_confirmed(self):
        self._save()
        # lượt 1: khách cũ muốn mua → KHÔNG hỏi địa chỉ từ đầu, chỉ XÁC NHẬN
        txt, tc, meta = self.turn(KNOWN_PHONE, "chị lấy giày Casual 39 đen nhé", [order()], "Dạ em lên đơn ạ.")
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["action"], "confirm")
        self.assertEqual(ev["missing"], [])
        self.assertIn("address", ev["to_confirm"])
        self.assertIn("Hoàng Hoa Thám", txt)
        self.assertIn("đúng không", txt)
        self.assertEqual(self.created(tc), [])
        # lượt 2: khách xác nhận → đọc lại đơn
        txt, tc, meta = self.turn(KNOWN_PHONE, "đúng rồi em", [order()])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        self.assertEqual(self.created(tc), [])
        # lượt 3: đồng ý → tạo
        _, tc, meta = self.turn(KNOWN_PHONE, "ok", [order()], "Dạ em đã lên đơn ạ.")
        self.assertEqual(len(self.created(tc)), 1)

    def test_customer_changes_saved_address(self):
        self._save()
        self.turn(KNOWN_PHONE, "chị lấy giày Casual 39 đen", [order()])
        txt, tc, meta = self.turn(KNOWN_PHONE, "không, giao về số 5 đường Lê Lợi, quận 1, TP.HCM",
                                  [order(address="<ADDR_2>")])                       # <ADDR_1> là địa chỉ đã lưu (hệ thống đăng ký), địa chỉ khách vừa nói là <ADDR_2>
        self.assertEqual(meta["order_gate"][-1]["fields"]["address"]["status"], "stated")
        self.assertEqual(self.created(tc), [])


class OtherRecipientTest(GateBase):
    def test_deliver_to_someone_else_reads_back_their_phone(self):
        script = dict(recipient_name="Hùng", recipient_phone="<PHONE_1>", address="<ADDR_1>", payment="COD")
        txt, tc, meta = self.turn(NEW_PHONE, "anh lấy giày Casual 39 đen, giao cho bác Hùng, số 0988777666, giao về số 3 phố Huế, quận Hai Bà Trưng, Hà Nội, thanh toán COD", [order(**script)])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_phone"]["status"], "stated")
        self.assertEqual(ev["action"], "readback")                                # đủ checklist ngay lượt đầu → đọc lại, không tạo
        self.assertIn("0988777666", txt)
        self.assertEqual(self.created(tc), [])
        _, tc, meta = self.turn(NEW_PHONE, "ok đúng rồi", [order(**script)], "Dạ em đã lên đơn ạ.")
        self.assertEqual(len(self.created(tc)), 1)
        args = [c for c in tc if c["name"] == "order.create"][0]["args"]
        self.assertNotIn("recipient_name", args)                                   # tham số chỉ dành cho gate, không vào trace/MCP
        self.assertNotIn("recipient_phone", args)
        facts = self.c["memory"].get_profile_facts(self.c["resolver"].resolve(
            self.c["normalizer"].normalize("alo", __import__("src.channels.normalizer", fromlist=["InputChannel"]).InputChannel.HOTLINE, NEW_PHONE)).customer_id)
        self.assertEqual(facts.get("recipient_phone"), "0988777666")


class ChangeOfMindTest(GateBase):
    def _to_readback(self):
        a = dict(recipient_name="Lan", address="<ADDR_1>", payment="COD")
        self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, COD, giày Casual 39 đen", [order(**a)])
        _, tc, meta = self.turn(NEW_PHONE, "ok số này", [order(**a)])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        return a

    def test_changes_size_after_readback_needs_new_readback(self):
        a = self._to_readback()
        _, tc, meta = self.turn(NEW_PHONE, "khoan, đổi sang size 40 nhé", [order(sku=SKU40, **a)])
        self.assertEqual(self.created(tc), [])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")           # đơn đổi → đọc lại lần nữa
        _, tc, meta = self.turn(NEW_PHONE, "ok đúng rồi", [order(sku=SKU40, **a)], "Dạ em đã lên đơn ạ.")
        made = self.created(tc)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["args"]["sku"], SKU40)

    def test_walks_away_after_readback_creates_nothing(self):
        self._to_readback()
        _, tc, meta = self.turn(NEW_PHONE, "thôi anh không mua nữa", [])
        self.assertEqual(self.created(tc), [])
        self.assertEqual(self.orch.order_gate.state(f"SESS-{self._cid()}-2026-10-15").stage, "collect")

    def _cid(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        return self.c["resolver"].resolve(t).customer_id

    def test_consent_only_counts_on_the_very_next_turn(self):
        a = self._to_readback()
        _, tc, meta = self.turn(NEW_PHONE, "à cho hỏi bảo hành bao lâu?", [])                       # không đồng ý → bản đọc lại hết hiệu lực
        self.assertEqual(self.created(tc), [])
        _, tc, meta = self.turn(NEW_PHONE, "ok", [order(**a)])                                      # 'ok' muộn: phải đọc lại lần nữa
        self.assertEqual(self.created(tc), [])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        _, tc, meta = self.turn(NEW_PHONE, "ok chốt", [order(**a)], "Dạ em đã lên đơn ạ.")
        self.assertEqual(len(self.created(tc)), 1)

    def test_consent_with_a_change_is_not_clear_consent(self):
        a = self._to_readback()
        _, tc, meta = self.turn(NEW_PHONE, "được, nhưng giao sau 5 giờ chiều nhé", [order(**a)])
        self.assertEqual(self.created(tc), [])


class RuleBasedPathTest(GateBase):
    def test_rule_based_fallback_cannot_bypass_the_gate(self):
        advisor_suggests(self)
        self.orch.llm_client = None
        t, b = self.turn_inputs(KNOWN_PHONE, "chị muốn lên đơn luôn")
        txt, tc, meta = self.orch.process_turn(t, b, current_date="2026-10-15")
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])
        self.assertTrue(meta["order_gate"])

    def turn_inputs(self, phone, text):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        return t, self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")


class ToolSchemaTest(unittest.TestCase):
    def test_llm_sees_recipient_params_on_order_create_only(self):
        from src.harness.order_gate import with_order_gate_params
        from src.llm.client import build_openai_tools
        base = build_openai_tools()
        patched = with_order_gate_params(base)
        by = {t["function"]["name"].replace("__", "."): t["function"]["parameters"]["properties"] for t in patched}
        self.assertIn("recipient_name", by["order.create"])
        self.assertIn("recipient_phone", by["order.create"])
        self.assertNotIn("recipient_name", by["order.update"])
        orig = {t["function"]["name"].replace("__", "."): t["function"]["parameters"]["properties"] for t in base}
        self.assertNotIn("recipient_name", orig["order.create"])                       # bản gốc (schema BTC) không bị sửa tại chỗ


class DriverTest(GateBase):
    """Bộ điều khiển đơn: khách trả lời câu hỏi/xác nhận/đọc lại của gate → CODE cập nhật đơn nháp, chạy lại gate, tạo đơn khi khách đồng ý — không gọi LLM."""

    def test_gate_replies_do_not_need_the_llm_even_if_it_would_forget_to_call_order_create(self):
        self.turn(NEW_PHONE, "anh muốn lấy giày Casual size 39 màu đen", [order()], "Dạ em lên đơn ạ.")          # LLM gọi order.create (bị chặn: hỏi)
        calls_after_first = self.llm.calls
        txt, tc, meta = self.turn(NEW_PHONE, "Tên người nhận là Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, thanh toán COD", [])
        self.assertEqual(self.llm.calls, calls_after_first)                      # code tự xử lý (LLM script rỗng sẽ nổ nếu bị gọi)
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_name"]["status"], "stated")
        self.assertEqual(ev["fields"]["address"]["status"], "stated")
        self.assertEqual(ev["fields"]["payment"]["status"], "stated")
        self.assertIn("recipient_phone", ev["to_confirm"])                       # SĐT nhận = số đang gọi: còn cần xác nhận
        self.assertIn("đúng không", txt)

    def test_full_flow_with_the_llm_called_only_once(self):
        self.turn(NEW_PHONE, "anh lấy giày Casual size 39 màu đen", [order()])
        self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, COD", [])
        txt, tc, meta = self.turn(NEW_PHONE, "đúng rồi, số này", [])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        self.assertIn("xác nhận", txt)
        self.assertEqual(self.created(tc), [])
        txt, tc, meta = self.turn(NEW_PHONE, "ok chốt", [])
        made = self.created(tc)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["args"]["sku"], SKU39)
        self.assertIn(made[0]["result"]["order_id"], txt)
        self.assertEqual(self.llm.calls, 1)
        self.assertNotIn("recipient_name", made[0]["args"])

    def test_question_in_the_middle_goes_to_the_llm_and_the_gate_question_is_still_asked(self):
        self.turn(NEW_PHONE, "anh lấy giày Casual size 39 màu đen", [order()])
        txt, tc, meta = self.turn(NEW_PHONE, "mà giày này bảo hành bao lâu em?", [], "Dạ giày bên em đổi trả trong 7 ngày ạ.")
        self.assertEqual(self.llm.calls, 2)                                      # câu hỏi chen ngang → LLM trả lời
        self.assertIn("7 ngày", txt)
        self.assertTrue(any(w in txt.lower() for w in ("địa chỉ", "tên người nhận", "thanh toán")))      # …và bước kế tiếp của gate vẫn được nối vào

    def test_change_of_product_goes_to_the_llm(self):
        self.turn(NEW_PHONE, "anh lấy giày Casual size 39 màu đen", [order()])
        self.turn(NEW_PHONE, "thôi đổi sang size 40 nhé", [], "Dạ vâng ạ.")
        self.assertEqual(self.llm.calls, 2)

    def test_cod_limit_error_is_explained_and_bank_transfer_completes_the_order(self):
        sku, args = "SKU-SS-AX40", dict(qty=2, price_vnd=6490000, recipient_name="Lan", address="<ADDR_1>", payment="COD")
        o = lambda **kw: ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": sku, **{**args, **kw}})
        self.turn(NEW_PHONE, "anh lấy hai máy lọc không khí Samsung AX40, tên người nhận là Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, COD", [o()])
        self.turn(NEW_PHONE, "đúng rồi, số này", [])                              # xác nhận SĐT → đọc lại đơn COD
        txt, tc, meta = self.turn(NEW_PHONE, "ok", [])                           # đồng ý → code tạo đơn → hệ thống báo vượt hạn mức COD
        self.assertEqual(self.created(tc), [])
        self.assertIn("hạn mức", txt)
        self.assertIn("chuyển khoản", txt)
        txt, tc, meta = self.turn(NEW_PHONE, "ừ chuyển khoản nhé", [])            # đọc lại đơn với chuyển khoản
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        self.assertIn("chuyển khoản", txt)
        txt, tc, meta = self.turn(NEW_PHONE, "ok đồng ý", [])
        made = self.created(tc)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["args"]["payment"], "bank")
        self.assertEqual(self.llm.calls, 1)

    def test_extract_name_helpers(self):
        from src.harness.order_gate import extract_recipient_name as n, is_pure_gate_reply as p
        self.assertEqual(n("Tên người nhận là Thu, giao về số 12"), "Thu")
        self.assertEqual(n("Giao cho chị Hoa nhé"), "Hoa")
        self.assertEqual(n("Nguyễn Thu ạ", name_pending=True), "Nguyễn Thu")
        self.assertIsNone(n("Nguyễn Thu ạ"))
        self.assertIsNone(n("đúng rồi", name_pending=True))
        self.assertTrue(p("Đúng rồi, giao về số 12 đường Nguyễn Trãi, thanh toán COD."))
        self.assertFalse(p("bảo hành bao lâu em?"))
        self.assertFalse(p("đổi sang size 40"))


class CanonicalSkuTest(GateBase):
    def test_product_name_passed_as_sku_is_resolved_before_the_gate_stores_the_draft(self):
        """LLM truyền tên sản phẩm thay vì SKU: đơn nháp phải giữ SKU chuẩn để code tạo đơn được ở lượt sau (lỗi gặp ở run G / SAMPLE-01)."""
        self.assertEqual(self.orch._canonical_sku("AirPure Y", "", None), "SKU-AP-Y")
        self.assertEqual(self.orch._canonical_sku("SKU-AP-Y", "", None), "SKU-AP-Y")
        self.assertEqual(self.orch._canonical_sku(SKU39, "", None), SKU39)

    def test_flow_completes_when_the_llm_used_a_product_name(self):
        args = dict(sku="AirPure Y", price_vnd=5200000)
        o = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "qty": 1, **args})
        self.turn(NEW_PHONE, "anh lấy máy lọc không khí AirPure Y", [o])
        self.turn(NEW_PHONE, "Giao cho Lan, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, COD", [])
        self.turn(NEW_PHONE, "đúng rồi, số này", [])
        txt, tc, meta = self.turn(NEW_PHONE, "ok", [])
        made = self.created(tc)
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["args"]["sku"], "SKU-AP-Y")


class QuoteWithProductNameTest(GateBase):
    def test_quote_with_a_product_name_is_resolved_to_the_real_sku(self):
        """LLM truyền tên sản phẩm cho pricing.get_quote/inventory.check → code chuẩn hóa sang SKU thật (báo giá có căn cứ để ghi nhớ)."""
        _, tc, meta = self.turn(NEW_PHONE, "máy lọc không khí AirPure Y giá bao nhiêu", [("pricing.get_quote", {"sku": "AirPure Y"}), ("inventory.check", {"sku": "Máy lọc không khí AirPure Y"})], "Dạ ạ.")
        quote = next(c for c in tc if c["name"] == "pricing.get_quote")
        self.assertEqual(quote["args"]["sku"], "SKU-AP-Y")
        self.assertIn("final_price_vnd", quote["result"])
        inv = next(c for c in tc if c["name"] == "inventory.check")
        self.assertEqual(inv["args"]["sku"], "SKU-AP-Y")
        self.assertNotIn("error", inv["result"])


class GateAssistTest(unittest.TestCase):
    def test_assist_answers_what_the_gate_asks(self):
        from src.eval.gate_assist import assist_reply
        self.assertIsNone(assist_reply(None))
        self.assertIsNone(assist_reply({"allow": True, "action": "allow"}))
        self.assertEqual(assist_reply({"allow": False, "action": "readback"}), "Ok em, đồng ý nhé.")
        self.assertEqual(assist_reply({"allow": False, "action": "confirm", "missing": [], "to_confirm": ["address"]}), "Đúng rồi em.")
        r = assist_reply({"allow": False, "action": "ask_confirm", "missing": ["address", "payment"], "to_confirm": ["recipient_phone"]}, "Hoa")
        self.assertTrue(r.startswith("Đúng rồi, ") and "Nguyễn Trãi" in r and "COD" in r)
        self.assertIn("Hoa", assist_reply({"allow": False, "action": "ask", "missing": ["recipient_name"], "to_confirm": []}, "Hoa"))
        self.assertIsNone(assist_reply({"allow": False, "action": "ask", "missing": ["item"], "to_confirm": []}, "Hoa"))     # không có dữ liệu mẫu → dừng chèn

    def test_assist_text_is_understood_by_the_gate(self):
        """Lời khách mô phỏng phải thật sự làm gate tiến lên (đồng ý rõ ràng; địa chỉ/thanh toán nhận ra được)."""
        from src.eval.gate_assist import assist_reply
        from src.harness.order_gate import detect_payment, is_explicit_consent
        self.assertTrue(is_explicit_consent(assist_reply({"allow": False, "action": "readback"})))
        self.assertTrue(is_explicit_consent("Đúng rồi em."))
        self.assertEqual(detect_payment(assist_reply({"allow": False, "action": "ask", "missing": ["payment"], "to_confirm": []})), "COD")


class GateAlwaysOnTest(unittest.TestCase):
    """Quyết định của người dùng: KHÔNG tắt gate — luôn bật ở demo, UI, eval."""

    def test_every_entrypoint_builds_an_orchestrator_with_the_gate_enabled(self):
        import tempfile, os
        from src.eval.runner import ScenarioRunner
        self.assertTrue(ScenarioRunner._new_stack(None)["orchestrator"].order_gate.enabled)                 # run_eval / eval
        from pipeline import CallCenterHarnessPipeline                                                      # main.py / ui_app.py dùng pipeline này
        d = tempfile.mkdtemp()
        pipe = CallCenterHarnessPipeline(trace_file=os.path.join(d, "t.jsonl"), db_path=os.path.join(d, "t.db"))
        self.assertTrue(pipe.orchestrator.order_gate.enabled)

    def test_there_is_no_switch_to_turn_the_gate_off_outside_unit_tests(self):
        import glob, os
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        files = [f for pat in ("*.py", "src/**/*.py", "scripts/*.py", "mcp_servers/*.py") for f in glob.glob(os.path.join(root, pat), recursive=True)]
        offenders = []
        for f in files:
            text = open(f, encoding="utf-8", errors="ignore").read()
            if "disable_for_unit_tests" in text and not f.endswith("order_gate.py"):
                offenders.append(f)
            for bad in ("--no-gate", "--gate-off", "ORDER_GATE_OFF", "ORDER_GATE_ENABLED", "order_gate.enabled ="):
                if bad in text and not f.endswith(os.path.join("tests", "test_order_gate.py")):
                    offenders.append((f, bad))
        self.assertEqual(offenders, [])
        from src.harness.order_gate import OrderGate
        with self.assertRaises(AttributeError):
            OrderGate().enabled = False                                                                     # `enabled` chỉ đọc


class NoDirectOrderCreateTest(unittest.TestCase):
    def test_orchestrator_has_a_single_order_create_call_site_behind_the_gate(self):
        import inspect
        from src.harness import orchestrator
        src = inspect.getsource(orchestrator)
        # chỉ còn: (1) executor của LLM (sau _gate_order_create), (2) nhánh rule-based (sau cổng, gate_say None)
        self.assertEqual(src.count('execute_tool(name, exec_args, caller="LLMOrchestrator")'), 1)
        self.assertEqual(src.count('tool_name="order.create"'), 1)
        self.assertIn("_gate_order_create(working_session_id", src)


class HonorificAndCompetitorTest(GateBase):
    def test_honorific_follows_how_the_customer_refers_to_themself(self):
        # CRM ghi C001 là "chị" nhưng khách tự xưng "anh" → dùng "anh" và nhớ lại
        _, _, _ = self.turn(KNOWN_PHONE, "Anh muốn hỏi máy lọc không khí", [], "Dạ em nghe anh ạ.")
        self.assertEqual(self.c["memory"].get_profile_facts("C001").get("honorific"), "anh")
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, KNOWN_PHONE)
        self.assertEqual(self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-16").honorific, "anh")

    def test_em_is_addressed_as_ban(self):
        self.turn(KNOWN_PHONE, "em muốn mua giày", [])
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, KNOWN_PHONE)
        self.assertEqual(self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-16").honorific, "bạn")

    def test_competitor_price_recorded_as_slot(self):
        self.turn(KNOWN_PHONE, "bên shop kia có 300k thôi em", [], "Dạ em hiểu ạ.")
        self.assertEqual(self.c["memory"].get_profile_facts("C001").get("competitor_price_vnd"), 300000)

    def test_competitor_difference_is_not_a_price(self):
        from src.memory.memory_extractor import extract_competitor_price as c, detect_self_honorific as h
        self.assertIsNone(c("bên khác rẻ hơn 500k"))
        self.assertEqual(c("Chỗ khác báo 4.500.000 thôi"), 4500000)
        self.assertIsNone(h("em có thể tư vấn giúp chị không"))                  # "em" ở đây là gọi nhân viên
        self.assertIsNone(h("hôm trước em tư vấn cho chị cái máy"))
        self.assertEqual(h("cho chị hỏi giá"), "chị")


if __name__ == "__main__":
    unittest.main()
