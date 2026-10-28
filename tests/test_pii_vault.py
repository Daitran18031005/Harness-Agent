"""Bước 7 — PiiVault: token CURRENT_CUSTOMER/<PHONE_n>/<ADDR_n>/<ID_n>, mở có kiểm soát, che kết quả tool (N13)."""
import json
import pickle
import copy
import unittest
from tests._helpers import build_components
from src.channels.normalizer import InputChannel
from src.privacy.pii_vault import PiiVault, detect_addresses, CALLER_TOKEN

CALLER = "0984726714"
OTHER = "0912345678"
OTHER2 = "0933111222"
ADDRESS = "25 Nguyễn Trãi, quận 1, TP HCM"


class VaultUnitTest(unittest.TestCase):
    def test_caller_vs_other_phone_tokens(self):
        v = PiiVault()
        out = v.mask_text(f"số em {CALLER}, giao cho em gái số {OTHER}, hoặc {OTHER2}, lại {OTHER}", CALLER)
        self.assertIn(CALLER_TOKEN, out)
        self.assertEqual(out.count("<PHONE_1>"), 2)       # cùng số -> cùng token
        self.assertIn("<PHONE_2>", out)
        for real in (CALLER, OTHER, OTHER2):
            self.assertNotIn(real, out)

    def test_current_customer_only_for_caller(self):
        v = PiiVault()
        self.assertEqual(v.phone_token(OTHER, CALLER), "<PHONE_1>")
        self.assertEqual(v.phone_token(CALLER, CALLER), CALLER_TOKEN)

    def test_address_stops_before_the_payment_phrase(self):
        from src.privacy.pii_vault import detect_addresses
        for text, want in (("Đúng rồi, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, thanh toán COD.", "số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội"),
                           ("giao về số 3 phố Huế, quận Hai Bà Trưng, Hà Nội, COD nhé", "số 3 phố Huế, quận Hai Bà Trưng, Hà Nội"),
                           ("giao về số 9 đường Lê Lợi, quận 1, TP.HCM, chuyển khoản nha", "số 9 đường Lê Lợi, quận 1, TP.HCM")):
            self.assertEqual([text[a:b] for a, b in detect_addresses(text)], [want])

    def test_address_without_street_or_district_words(self):
        """Câu demo thật (CHECKING § 11.99): không có đường/phường/quận và không có 'giao về' đứng trước → trước đây không nhận ra."""
        for text, want in (("Giao về số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội", "số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội"),
                           ("Giao cho Lan, số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội, thanh toán COD", "số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội"),
                           ("số 12 nguyễn trãi, thanh xuân, hà nội nhé", "số 12 nguyễn trãi, thanh xuân, hà nội"),
                           ("Giao cho Lan, 12 Nguyễn Trãi, Thanh Xuân, Hà Nội", "12 Nguyễn Trãi, Thanh Xuân, Hà Nội"),
                           ("Giao cho Lan, số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội, SĐT 0912345678", "số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội"),
                           ("số 9 Lê Lợi, TP.HCM", "số 9 Lê Lợi, TP.HCM")):
            self.assertEqual([text[a:b] for a, b in detect_addresses(text)], [want], text)
        masked = PiiVault().mask_text("Giao cho Lan, số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội, thanh toán COD", CALLER)
        self.assertEqual(masked, "Giao cho Lan, <ADDR_1>, thanh toán COD")

    def test_province_rule_has_no_false_positives(self):
        for text in ("máy này giá 5.200.000đ giao trong 2 ngày", "lấy 2 cái ở Hà Nội", "chị 25 tuổi, phòng 25m2 ở Hà Nội",
                     "em lấy 2 máy, giao Hà Nội", "số 5 trong Hà Nội", "phòng 25 mét vuông, nhà ở Hà Nội", "5 triệu rưỡi, Hà Nội"):
            self.assertEqual(detect_addresses(text), [], text)

    def test_address_detection_and_masking(self):
        v = PiiVault()
        text = f"Ok lên đơn, giao về {ADDRESS} nhé."
        out = v.mask_text(text, CALLER)
        self.assertIn("<ADDR_1>", out)
        self.assertNotIn("Nguyễn Trãi", out)
        self.assertTrue(out.endswith("nhé."))

    def test_street_pattern_without_trigger_and_no_false_positive(self):
        self.assertTrue(detect_addresses("nhà em ở số 12 ngõ 5 Cầu Giấy Hà Nội"))
        self.assertEqual(detect_addresses("giao về nhà luôn nhé"), [])        # không có dấu hiệu địa chỉ
        self.assertEqual(detect_addresses("máy này giá 5.200.000đ giao trong 2 ngày"), [])

    def test_unmask_only_allowed_tool_fields(self):
        v = PiiVault()
        v.mask_text(f"sdt {OTHER} giao về {ADDRESS}", CALLER)
        args = {"customer_phone": "<PHONE_1>", "address": "<ADDR_1>", "note": "gọi <PHONE_1>", "sku": "SKU-AP-Y"}
        out = v.unmask_args("order.create", args, CALLER)
        self.assertEqual(out["customer_phone"], OTHER)
        self.assertEqual(out["address"], ADDRESS)
        self.assertEqual(out["note"], "gọi <PHONE_1>")                         # field không nằm trong danh sách: giữ token
        self.assertEqual(args["customer_phone"], "<PHONE_1>")                  # không sửa bản gốc
        # tool không nằm trong danh sách cho phép -> không mở gì
        self.assertEqual(v.unmask_args("catalog.search", {"query": "<PHONE_1>"}, CALLER), {"query": "<PHONE_1>"})
        # CURRENT_CUSTOMER -> số người gọi
        self.assertEqual(v.unmask_args("order.create", {"customer_phone": CALLER_TOKEN}, CALLER)["customer_phone"], CALLER)

    def test_id_token_never_opened(self):
        v = PiiVault()
        self.assertEqual(v.unmask_args("order.create", {"customer_phone": "<ID_1>"}, CALLER)["customer_phone"], "<ID_1>")
        self.assertNotIn("<ID_1>", v.unmask_text("CCCD của chị là <ID_1> ạ", CALLER))

    def test_handoff_brief_nested_phone_unmasked(self):
        v = PiiVault()
        v.mask_text(f"số {OTHER}", CALLER)
        out = v.unmask_args("handoff.transfer", {"brief": {"customer_phone": "<PHONE_1>", "conversation_summary": "x <PHONE_1>"}}, CALLER)
        self.assertEqual(out["brief"]["customer_phone"], OTHER)
        self.assertEqual(out["brief"]["conversation_summary"], "x <PHONE_1>")

    def test_mask_value_hides_phones_and_addresses_in_results(self):
        v = PiiVault()
        v.mask_text(f"sdt {OTHER}", CALLER)
        result = {"orders": [{"order_id": "OD600001", "customer_phone": OTHER, "address": ADDRESS, "total_vnd": 5200000},
                             {"order_id": "OD600002", "customer_phone": CALLER}], "note": f"gọi {OTHER2} nhé"}
        masked = v.mask_value(result, CALLER)
        s = json.dumps(masked, ensure_ascii=False)
        for real in (OTHER, OTHER2, CALLER, "Nguyễn Trãi"):
            self.assertNotIn(real, s)
        self.assertEqual(masked["orders"][0]["total_vnd"], 5200000)
        self.assertEqual(masked["orders"][0]["order_id"], "OD600001")
        self.assertEqual(masked["orders"][1]["customer_phone"], CALLER_TOKEN)

    def test_redact_args_for_trace_keeps_phone_hides_address(self):
        v = PiiVault()
        v.mask_text(f"giao về {ADDRESS}", CALLER)
        out = v.redact_args_for_trace({"customer_phone": OTHER, "address": ADDRESS})
        self.assertEqual(out["customer_phone"], OTHER)
        self.assertEqual(out["address"], "<ADDR_1>")

    def test_vault_cannot_leave_the_process(self):
        v = PiiVault()
        v.mask_text(f"sdt {OTHER}", CALLER)
        self.assertNotIn(OTHER, repr(v))
        with self.assertRaises(TypeError):
            pickle.dumps(v)
        with self.assertRaises(TypeError):
            copy.deepcopy(v)
        with self.assertRaises(TypeError):
            json.dumps(v)


class RecordingLLM:
    """LLM giả: ghi lại MỌI thứ nó nhìn thấy (messages + kết quả tool) rồi thực hiện các tool call kịch bản."""
    available = True

    def __init__(self, calls, text):
        self.calls, self.text = calls, text
        self.seen_messages, self.seen_results = [], []

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        self.seen_messages.extend(messages)
        log = []
        for name, args in self.calls:
            result, executed = tool_executor(name, args)
            self.seen_results.append(result)
            log.append({"name": name, "tool": name, "args": executed, "result": result})
        return self.text, log, {"prompt_tokens": 0, "completion_tokens": 0}


class DeliverToSomeoneElseTest(unittest.TestCase):
    """Ca 'giao cho người khác, số khác': số/địa chỉ khác người gọi không bao giờ tới LLM dưới dạng thật."""

    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _turn(self, text, phone=CALLER, date="2026-10-17"):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone, reference_date=date)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)
        return t, b

    def test_other_phone_and_address_masked_for_llm_but_real_for_tool(self):
        text = f"Ok lên đơn, giao cho em gái số {OTHER}, giao về {ADDRESS} nhé. CCCD chị 012345678901."
        llm = RecordingLLM([("order.create", {"customer_phone": "<PHONE_1>", "address": "<ADDR_1>", "sku": "SKU-AP-Y",
                                               "price_vnd": 5200000, "payment": "COD"})],
                           "Dạ em đã lên đơn giao về <ADDR_1>, gọi số <PHONE_1> ạ.")
        self.orch.llm_client = llm
        t, b = self._turn(text)
        final, tool_calls, meta = self.orch.process_turn(t, b, current_date="2026-10-17")

        # 1. LLM không thấy số thật / địa chỉ thật / CCCD thật ở bất kỳ message nào
        blob = json.dumps(llm.seen_messages, ensure_ascii=False)
        for real in (CALLER, OTHER, "Nguyễn Trãi", "012345678901"):
            self.assertNotIn(real, blob)
        self.assertIn("<PHONE_1>", blob)
        self.assertIn("<ADDR_1>", blob)
        self.assertIn("<ID_1>", blob)
        # 2. tool nhận giá trị THẬT (số của người nhận, địa chỉ thật)
        audit = [a for a in self.c["mcp"].audit_log if a["tool"] == "order.create"][-1]
        self.assertEqual(audit["args"]["customer_phone"], OTHER)
        self.assertEqual(audit["args"]["address"], ADDRESS)
        self.assertNotEqual(audit["args"]["customer_phone"], CALLER)     # CURRENT_CUSTOMER không bị dùng cho số khác
        # 3. trace: giữ SĐT (BTC cho phép), địa chỉ bị che
        self.assertEqual(tool_calls[0]["args"]["customer_phone"], OTHER)
        self.assertEqual(tool_calls[0]["args"]["address"], "<ADDR_1>")
        self.assertEqual(tool_calls[0]["result"]["status"], "created")
        # 4. lời nói với khách được mở token (không còn token nào)
        self.assertIn(ADDRESS, final)
        self.assertIn(OTHER, final)
        self.assertNotIn("<", final)

    def test_tool_results_are_masked_before_reaching_llm(self):
        llm = RecordingLLM([
            ("order.create", {"customer_phone": "<PHONE_1>", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"}),
            ("order.status", {"customer_phone": "<PHONE_1>"}),
            ("order.status", {"customer_phone": CALLER_TOKEN}),
        ], "Dạ em đã kiểm tra ạ.")
        self.orch.llm_client = llm
        t, b = self._turn(f"lên đơn cho em gái số {OTHER} nhé")
        _, tool_calls, _ = self.orch.process_turn(t, b, current_date="2026-10-17")
        seen = json.dumps(llm.seen_results, ensure_ascii=False)
        self.assertNotIn(OTHER, seen)
        self.assertNotIn(CALLER, seen)
        self.assertIn("<PHONE_1>", seen)                                  # số người nhận -> token riêng
        self.assertNotIn(OTHER, json.dumps(tool_calls[1]["result"], ensure_ascii=False))

    def test_llm_cannot_make_tool_use_id_token(self):
        llm = RecordingLLM([("order.create", {"customer_phone": "<ID_1>", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"})], "ok")
        self.orch.llm_client = llm
        t, b = self._turn("lên đơn nhé, CCCD chị 012345678901")
        self.orch.process_turn(t, b, current_date="2026-10-17")
        audit = [a for a in self.c["mcp"].audit_log if a["tool"] == "order.create"][-1]
        self.assertEqual(audit["args"]["customer_phone"], "<ID_1>")       # không bao giờ được thay bằng số thật

    def test_profile_facts_whitelisted_in_prompt(self):
        llm = RecordingLLM([], "Dạ vâng ạ.")
        self.orch.llm_client = llm
        self.c["memory"].set_profile_fact("C001", "phone_provided", OTHER)
        self.c["memory"].set_profile_fact("C001", "room_area_m2", 25.0)
        t, b = self._turn("alo")
        self.orch.process_turn(t, b, current_date="2026-10-17")
        blob = json.dumps(llm.seen_messages, ensure_ascii=False)
        self.assertNotIn(OTHER, blob)
        self.assertNotIn("phone_provided", blob)
        self.assertIn("room_area_m2", blob)


if __name__ == "__main__":
    unittest.main()
