"""Test bổ sung cho cụm bước 4–8: tool ghi an toàn, tóm tắt tool, guardrail trong luồng, tiền, ITN, định danh/kênh."""
import unittest
from tests._helpers import build_components, advisor_suggests
from tests.test_orchestrator import FakeLLM
from src.channels.normalizer import InputChannel, RequestNormalizer
from src.llm.client import LLMRoundLimit
from src.harness.money import extract_amounts, numbers_in, derived_numbers

NORM = RequestNormalizer()


def norm(text, ref=None):
    return NORM.normalize(text, InputChannel.HOTLINE, "0900000000", reference_date=ref)


class ExplodingLLM:
    """Thực hiện các tool call rồi ném lỗi (mô phỏng vượt số vòng / mất mạng sau khi đã ghi)."""
    available = True

    def __init__(self, calls, error):
        self.calls, self.error = calls, error

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        for name, args in self.calls:
            tool_executor(name, args)
        raise self.error


class SafeWriteTest(unittest.TestCase):  # bước 4
    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _turn(self, phone="0984726714", date="2026-10-17", text="alo"):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        return t, self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)

    def _orders(self):
        import mock_tools
        return len(mock_tools._ORDERS)

    def test_round_limit_after_order_create_does_not_run_rule_based_branch(self):
        create = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"})
        self.orch.llm_client = ExplodingLLM([create], LLMRoundLimit("loop"))
        t, b = self._turn(text="ok lên đơn cho chị")
        final, tool_calls, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        creates = [tc for tc in tool_calls if tc["name"] == "order.create"]
        self.assertEqual(len(creates), 1)                      # KHÔNG có order.create thứ hai
        self.assertEqual(self._orders(), 1)
        self.assertEqual(meta["violation"], "llm_round_limit")
        self.assertIn(creates[0]["result"]["order_id"], final)  # trả lời an toàn dựa trên đơn đã tạo
        self.assertTrue(meta["guardrail_approved"])

    def test_error_after_write_keeps_trace_and_no_duplicate(self):
        create = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"})
        self.orch.llm_client = ExplodingLLM([create], RuntimeError("network down"))
        t, b = self._turn(text="lên đơn cho chị nhé")
        _, tool_calls, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(self._orders(), 1)
        self.assertEqual(meta["violation"], "llm_error_after_write")
        self.assertEqual([tc["name"] for tc in tool_calls], ["order.create"])

    def test_error_before_any_write_falls_back_to_rule_based(self):
        advisor_suggests(self)
        self.orch.llm_client = ExplodingLLM([("inventory.check", {"sku": "SKU-AP-Y"})], RuntimeError("boom"))
        t, b = self._turn(text="alo")
        _, tool_calls, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        names = [tc["name"] for tc in tool_calls]
        self.assertEqual(names[0], "inventory.check")           # tool đã chạy vẫn nằm trong trace
        self.assertIn("pricing.get_quote", names)               # nhánh rule-based (chỉ đọc) đã chạy
        self.assertIsNone(meta["violation"])

    def test_basket_with_own_sku_does_not_trigger_second_item_promo(self):
        """SAMPLE-05 (chạy C): LLM nhét chính SKU vào basket_skus → KM 'máy thứ 2' áp sai. Phải bị bỏ."""
        t, b = self._turn("0976158464", "2026-10-15")
        quote = {"sku": "SKU-AP-X", "qty": 1, "customer_phone": "CURRENT_CUSTOMER", "basket_skus": ["SKU-AP-X"]}
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", quote)], "text": "Dạ giá 4.890.000đ ạ."})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        res = tc[0]["result"]
        self.assertEqual(res["final_price_vnd"], res["list_price_vnd"])
        self.assertNotIn("basket_skus", tc[0]["args"])

    def test_two_units_same_sku_quote_includes_second_item_promo(self):
        """GEN-02: 2 máy AirPure Pro ngày 15/10 — máy 1 AIR-OCT 7.690.000 + máy 2 AIR-2ND-50 3.995.000 = 11.685.000 (không phải 15.380.000)."""
        t, b = self._turn("0911265844", "2026-10-15")
        quote = {"sku": "SKU-AP-PRO", "qty": 2}
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", quote)], "text": "Dạ tổng 11.685.000đ ạ."})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        res = tc[0]["result"]
        self.assertEqual(res["unit_prices_vnd"], [7690000, 3995000])
        self.assertEqual(res["total_vnd"], 11685000)
        self.assertEqual(res["final_price_vnd"], 7690000)       # order.create vẫn kiểm giá theo đơn vị 1
        self.assertNotIn("basket_skus", tc[0]["args"])          # LLM không bị ép truyền giỏ; không đụng order.create

    def test_quote_total_added_only_for_multi_unit_or_basket(self):
        t, b = self._turn("0911265844", "2026-10-15")
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": "SKU-AP-PRO", "qty": 1})], "text": "Dạ ạ."})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        self.assertNotIn("total_vnd", tc[0]["result"])           # 1 máy, không giỏ: kết quả như cũ
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": "SKU-SN-CAS-39-DEN", "qty": 2})], "text": "Dạ ạ."})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        self.assertEqual(tc[0]["result"]["total_vnd"], 2 * tc[0]["result"]["final_price_vnd"])   # không có KM 'máy thứ 2': giá × 2

    def test_sanitize_basket_keeps_genuine_other_items(self):
        f = type(self.orch)._sanitize_basket
        out = f("pricing.get_quote", {"sku": "SKU-AP-X", "basket_skus": ["sku-ap-x", "SKU-SS-AX40", "SKU-SS-AX40"]})
        self.assertEqual(out["basket_skus"], ["SKU-SS-AX40"])
        self.assertEqual(f("catalog.search", {"basket_skus": ["A"]}), {"basket_skus": ["A"]})   # tool khác: không đụng
        self.assertNotIn("basket_skus", f("order.create", {"sku": "S1", "basket_skus": ["S1"]}))

    def test_dedup_returns_original_result_flagged(self):
        t, b = self._turn("0922264686", "2026-10-15")
        self.orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "payment": "COD"})], "text": "Dạ em đã lên đơn ạ."})
        _, tc1, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        oid = tc1[0]["result"]["order_id"]
        t2, b2 = self._turn("0922264686", "2026-10-19")
        upd = ("order.update", {"order_id": oid, "action": "exchange_size", "new_variant_sku": "SKU-SN-CAS-40-DEN"})
        self.orch.llm_client = FakeLLM({"calls": [upd], "text": "Dạ em đã làm thủ tục đổi size ạ."})
        _, first, _ = self.orch.process_turn(t2, b2, current_date="2026-10-19")
        _, second, _ = self.orch.process_turn(t2, b2, current_date="2026-10-19")
        self.assertNotIn("already_done", first[0]["result"])
        self.assertTrue(second[0]["result"].get("already_done"))
        self.assertEqual(second[0]["result"]["fee_vnd"], first[0]["result"]["fee_vnd"])
        import mock_tools
        self.assertEqual(len([x for x in mock_tools._TICKETS if x.get("action", "").startswith("exchange")]), 1)

    def test_same_order_requested_twice_is_still_deduplicated(self):
        """Đối chứng cho audit #3: lặp đúng yêu cầu tạo đơn (LLM lặp vòng) vẫn KHÔNG tạo đơn thứ hai."""
        import mock_tools
        t, b = self._turn("0922264686", "2026-10-15")
        create = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "payment": "COD"})
        self.orch.llm_client = FakeLLM({"calls": [create], "text": "ok"})
        _, first, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        _, second, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        self.assertTrue(second[0]["result"].get("already_done"))
        self.assertEqual(second[0]["result"]["order_id"], first[0]["result"]["order_id"])
        self.assertEqual(len(mock_tools._ORDERS), 1)

    def test_new_order_after_the_first_was_returned_is_not_swallowed_by_dedup(self):
        """Audit #3: đơn đã được trả hàng (order.update action=return) thì mục chống-lặp trỏ tới nó là cũ — đặt lại đúng sản phẩm đó phải TẠO đơn mới,
        không được trả "đơn này em đã lên rồi, mã X" với mã của đơn đã trả. (Hợp đồng tool KHÔNG có action huỷ đơn; trả hàng là thao tác duy nhất làm đơn hết hiệu lực.)"""
        import mock_tools
        t, b = self._turn("0922264686", "2026-10-15")
        create = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "payment": "COD"})
        self.orch.llm_client = FakeLLM({"calls": [create], "text": "ok"})
        _, first, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        oid = first[0]["result"]["order_id"]
        self.orch.llm_client = FakeLLM({"calls": [("order.update", {"order_id": oid, "action": "return", "reason": "không vừa"})], "text": "ok"})
        _, ret, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        self.assertEqual(ret[0]["result"]["status"], "pickup_scheduled")
        self.orch.llm_client = FakeLLM({"calls": [create], "text": "ok"})
        _, again, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        res = again[0]["result"]
        self.assertNotIn("already_done", res)
        self.assertEqual(res["status"], "created")
        self.assertNotEqual(res["order_id"], oid)
        self.assertEqual(len(mock_tools._ORDERS), 2)

    def test_new_call_new_day_allows_second_exchange_with_fee(self):
        t, b = self._turn("0922264686", "2026-10-15")
        self.orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "payment": "COD"})], "text": "ok"})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        oid = tc[0]["result"]["order_id"]
        fees = []
        for date, variant in (("2026-10-19", "SKU-SN-CAS-40-DEN"), ("2026-10-21", "SKU-SN-CAS-41-DEN")):
            t2, b2 = self._turn("0922264686", date)
            self.orch.llm_client = FakeLLM({"calls": [("order.update", {"order_id": oid, "action": "exchange_size", "new_variant_sku": variant})], "text": "ok"})
            _, tc2, _ = self.orch.process_turn(t2, b2, current_date=date)
            fees.append(tc2[0]["result"].get("fee_vnd"))
        self.assertEqual(fees, [0, 60000])                      # đổi khác biến thể ở cuộc gọi khác vẫn tính phí đúng

    def test_tool_summary_saved_in_working_memory_for_next_turn(self):
        t, b = self._turn("0922264686", "2026-10-15")
        self.orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "payment": "COD"})], "text": "ok"})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        oid = tc[0]["result"]["order_id"]
        t2, b2 = self._turn("0922264686", "2026-10-19")
        self.orch.llm_client = FakeLLM({"calls": [("order.update", {"order_id": oid, "action": "exchange_size", "new_variant_sku": "SKU-SN-CAS-40-DEN"})], "text": "Dạ ok ạ."})
        self.orch.process_turn(t2, b2, current_date="2026-10-19")
        st = self.c["memory"].get_working(f"SESS-{b2.customer_id}-2026-10-19")
        systems = [m["content"] for m in st.messages_in_session if m["role"] == "system"]
        self.assertTrue(systems and "fee_vnd=0" in systems[0] and oid in systems[0])

    def test_history_trimmed_to_budget(self):
        hist = [{"role": "user", "content": "x" * 5000} for _ in range(6)]
        trimmed = self.orch._trim_history(hist)
        self.assertLessEqual(sum(len(m["content"]) for m in trimmed), self.orch.MAX_HISTORY_CHARS)
        self.assertGreaterEqual(len(trimmed), 2)


class FactsUsedDetectionTest(unittest.TestCase):
    """Bước 15 GĐ B (SAMPLE-03): CCR thấp giả vì facts_used không nhận order_id/size/màu và so khớp có dấu.
    Quy tắc CÔNG BẰNG chi tiết nằm ở tests/test_fact_usage.py."""

    def setUp(self):
        self.c = build_components()

    def _brief_after_order(self):
        import mock_tools
        mem = self.c["memory"]
        mock_tools.order_create("0922264686", "SKU-SN-CAS-39-DEN", payment="COD", on="2026-10-15")
        for k, v in (("product_advised", "SKU-SN-CAS"), ("order_id", "OD600001"), ("variant_sku", "SKU-SN-CAS-39-DEN"),
                     ("size", "39"), ("color", "den"), ("price_quoted_vnd", 890000)):
            mem.set_profile_fact("C012", k, v)
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0922264686")
        return self.c["brief"].build(self.c["resolver"].resolve(t, memory=mem), "2026-10-19")

    def test_brief_carries_order_and_variant_facts(self):
        b = self._brief_after_order()
        for k in ("order_id", "variant_sku", "size", "color"):
            self.assertIn(k, b.must_carry_over)

    def test_accent_insensitive_and_args_detection(self):
        b = self._brief_after_order()
        orch = self.c["orchestrator"]
        calls = [{"name": "order.update", "args": {"order_id": "OD600001", "action": "exchange_size", "new_variant_sku": "SKU-SN-CAS-40-DEN"}}]
        used = orch._carried_facts(list(b.must_carry_over), b.profile_facts, "Dạ anh đang dùng size 39 màu đen đúng không ạ?",
                                   calls, "anh mới nhận giày hôm qua", set())
        self.assertEqual({"order_id", "size", "color"} <= set(used), True)
        self.assertNotIn("variant_sku", used)

    def test_unused_facts_not_reported(self):
        b = self._brief_after_order()
        self.assertEqual(self.c["orchestrator"]._carried_facts(list(b.must_carry_over), b.profile_facts, "Dạ em chào anh ạ.", [], "alo", set()), [])


class PromptCachePrefixTest(unittest.TestCase):
    """3(b): phần TĨNH của prompt phải ở đầu và giống hệt giữa các khách/lượt; lịch sử chỉ được nối thêm ở cuối."""

    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _msgs(self, phone, date, text, history):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)
        t.llm_text = text
        return self.orch._build_llm_messages(t, b, history, date, phone)

    def test_first_message_is_static_and_identical_across_customers_and_days(self):
        a = self._msgs("0984726714", "2026-10-15", "alo", [])
        b = self._msgs("0922264686", "2026-10-19", "xin chào", [])
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[0]["role"], "system")
        for dynamic in ("2026-10", "0984726714", "0922264686", "Hoa", "Khoa", "CURRENT_CUSTOMER:"):
            self.assertNotIn(dynamic, a[0]["content"])

    def test_dynamic_context_sits_after_history_just_before_the_user_turn(self):
        hist = [{"role": "user", "content": "lượt 1"}, {"role": "assistant", "content": "trả lời 1"}]
        m = self._msgs("0984726714", "2026-10-15", "lượt 2", hist)
        self.assertEqual([x["role"] for x in m], ["system", "user", "assistant", "system", "user"])
        self.assertIn("Call Brief", m[3]["content"])
        self.assertEqual(m[4]["content"], "lượt 2")

    def test_history_prefix_is_stable_across_turns_even_when_context_changes(self):
        h1 = [{"role": "user", "content": "lượt 1"}, {"role": "assistant", "content": "trả lời 1"}]
        turn_a = self._msgs("0984726714", "2026-10-15", "lượt 2", h1)
        self.c["memory"].set_profile_fact("C001", "room_area_m2", 25.0)          # ngữ cảnh Call Brief đổi giữa 2 lượt
        h2 = h1 + [{"role": "user", "content": "lượt 2"}, {"role": "assistant", "content": "trả lời 2"}]
        turn_b = self._msgs("0984726714", "2026-10-15", "lượt 3", h2)
        stable_a, stable_b = turn_a[:-2], turn_b[:-2]                            # bỏ [ngữ cảnh động + lời khách]
        self.assertEqual(stable_b[:len(stable_a)], stable_a)                     # tiền tố của lượt sau chứa nguyên tiền tố lượt trước
        self.assertNotEqual(turn_a[-2], turn_b[-2])                              # còn ngữ cảnh động thì đã đổi

    def test_static_prompt_is_long_enough_for_openai_prefix_caching(self):
        m = self._msgs("0984726714", "2026-10-15", "alo", [])
        # Ước lượng thô: tiếng Việt ~2,5 ký tự/token => ≥ 3.000 ký tự ≈ 1.200 token; chưa kể schema tool đứng TRƯỚC trong tiền tố.
        # Việc cache có thật sự xảy ra phải kiểm bằng `cached_tokens` trong trace khi chạy LLM thật.
        self.assertGreater(len(m[0]["content"]), 3000)


class GuardrailInFlowTest(unittest.TestCase):  # bước 6 trong luồng orchestrator
    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _turn(self, text="alo", date="2026-10-17"):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, "0984726714")
        return t, self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)

    def test_invented_price_is_replaced(self):
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": "SKU-AP-Y"})], "text": "Dạ máy giá 3.900.000đ thôi ạ."})
        t, b = self._turn()
        final, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(meta["violation"], "hallucination_price_mismatch")
        self.assertNotIn("3.900.000", final)

    def test_real_price_passes(self):
        self.orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": "SKU-AP-Y"})], "text": "Dạ máy giá 5.200.000đ ạ."})
        t, b = self._turn()
        final, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertTrue(meta["guardrail_approved"])
        self.assertIn("5.200.000", final)

    def test_customer_quoted_price_may_be_repeated(self):
        self.orch.llm_client = FakeLLM({"calls": [], "text": "Dạ bên em hiểu giá 4.590.000đ ở nơi khác ạ."})
        t, b = self._turn("bên kia bán 4590k thôi")
        _, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertTrue(meta["guardrail_approved"])

    def test_fee_claim_corrected_across_turns_in_same_call(self):
        t, b = self._turn("alo", "2026-10-15")
        self.orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "payment": "COD"})], "text": "ok"})
        _, tc, _ = self.orch.process_turn(t, b, current_date="2026-10-15")
        oid = tc[0]["result"]["order_id"]
        t2, b2 = self._turn("đổi size", "2026-10-19")
        upd = lambda v: FakeLLM({"calls": [("order.update", {"order_id": oid, "action": "exchange_size", "new_variant_sku": v})], "text": "Dạ em đã đổi size ạ."})
        self.orch.llm_client = upd("SKU-SN-CAS-40-DEN")
        self.orch.process_turn(t2, b2, current_date="2026-10-19")
        # lượt sau (không gọi tool) khẳng định "không mất phí" sau khi lần đổi thứ 2 có phí 60.000đ
        self.orch.llm_client = upd("SKU-SN-CAS-41-DEN")
        self.orch.process_turn(t2, b2, current_date="2026-10-19")
        self.orch.llm_client = FakeLLM({"calls": [], "text": "Dạ đổi size không mất phí gì ạ."})
        final, _, meta = self.orch.process_turn(t2, b2, current_date="2026-10-19")
        self.assertEqual(meta["violation"], "hallucination_fee_mismatch")
        self.assertIn("60.000", final)


class MoneyTest(unittest.TestCase):
    def test_extract_amounts(self):
        self.assertEqual([v for v, _ in extract_amounts("giá 5.200.000đ, tặng quà 690.000đ")], [5200000, 690000])
        self.assertEqual([v for v, _ in extract_amounts("tầm 5 triệu 2 nhé")], [5200000])
        self.assertEqual([v for v, _ in extract_amounts("giảm 500k")], [500000])
        self.assertEqual([v for v, _ in extract_amounts("5200000đ")], [5200000])
        self.assertEqual(extract_amounts("giao trong 2 ngày, bảo hành 24 tháng, mã đơn OD600003, phòng 25m²"), [])
        self.assertTrue(extract_amounts("khoảng 5 triệu")[0][1])               # ước chừng

    def test_numbers_in_results_include_strings_and_derived(self):
        nums = numbers_in({"a": 5200000, "chunks": [{"text": "phụ thu 60.000đ"}], "flag": True, "small": 5})
        self.assertEqual(nums, {5200000, 60000})
        self.assertIn(5260000, derived_numbers(nums))


class ITNExtraTest(unittest.TestCase):  # bước 7
    def test_spoken_phone(self):
        self.assertIn("0994893949", norm("số em không chín chín bốn tám chín ba chín bốn chín").normalized_text)

    def test_number_words_variants(self):
        self.assertIn("15.000.000", norm("giá mười lăm triệu").normalized_text)
        self.assertIn("2.350.000", norm("hai triệu ba trăm năm mươi nghìn").normalized_text)
        self.assertIn("2.500.000", norm("hai triệu rưỡi").normalized_text)
        self.assertIn("35 mét vuông", norm("phòng ba mươi lăm mét vuông").normalized_text)

    def test_digits_before_unit_not_double_converted(self):
        self.assertIn("ngân sách 6.000.000,", norm("ngân sách 6 triệu, có bé nhỏ").normalized_text)
        self.assertIn("5.200.000", norm("5tr2 nhé").normalized_text)
        self.assertNotIn("1.000.000", norm("giá 20 nghìn thôi").normalized_text)

    def test_ordinary_words_not_converted(self):
        self.assertEqual(norm("năm nay em muốn mua một cái").normalized_text, "năm nay em muốn mua một cái")

    def test_pronoun_context(self):
        self.assertIn("anh ok", norm("a ok r").normalized_text)
        self.assertIn("không ạ", norm("co ship k a").normalized_text)
        self.assertIn("cho chị nhé", norm("lên đơn cho c nhé").normalized_text)

    def test_relative_date_hint(self):
        e = norm("gọi lại ngày mai lúc 3 giờ chiều nhé", "2026-10-15").extracted_entities
        self.assertEqual(e["callback_hint"], {"date": "2026-10-16", "time": "15:00"})
        self.assertNotIn("callback_hint", norm("giảm 500k hôm trước, phòng q7 hcm", "2026-10-15").extracted_entities)

    def test_id_numbers_become_tokens(self):
        t = norm("CCCD em 012345678901 stk 1903456789012 sdt 0912345678").normalized_text
        self.assertIn("<ID_1>", t)
        self.assertIn("<ID_2>", t)
        self.assertIn("0912345678", t)          # SĐT giữ nguyên trong normalized_text (vault che trước khi vào LLM)


class IdentityChannelTest(unittest.TestCase):  # bước 8
    def setUp(self):
        self.c = build_components()

    def turn(self, text, channel, contact):
        return self.c["normalizer"].normalize(text, channel, contact)

    def test_zalo_and_fb_ids_resolve_to_c001(self):
        r = self.c["resolver"]
        self.assertEqual(r.resolve(self.turn("hi", InputChannel.ZALO, "zalo_hoa73")).customer_id, "C001")
        self.assertEqual(r.resolve(self.turn("hi", InputChannel.FANPAGE, "fb.hoa.479")).customer_id, "C001")

    def test_zalo_channel_with_phone_contact(self):   # SAMPLE-06 call_2: kênh Zalo nhưng contact là SĐT
        ident = self.c["resolver"].resolve(self.turn("hi", InputChannel.ZALO, "0984726714"))
        self.assertEqual(ident.customer_id, "C001")

    def test_shared_phone_choice_sticks_within_session_and_brief_ids_differ(self):
        r = self.c["resolver"]
        self.assertEqual(r.resolve(self.turn("cô là Loan đây", InputChannel.HOTLINE, "0958421083")).customer_id, "C034")
        self.assertEqual(r.resolve(self.turn("ok lấy máy lọc nước", InputChannel.HOTLINE, "0958421083")).customer_id, "C034")
        r2 = build_components()["resolver"]
        a = r2.resolve(self.turn("alo", InputChannel.HOTLINE, "0958421083"))
        self.assertTrue(a.is_ambiguous)
        b1 = self.c["brief"].build(a, "2026-10-15")
        self.assertNotEqual(b1.customer_id, "AMBIGUOUS")
        self.assertTrue(b1.customer_id.startswith("AMB-"))
        self.assertNotIn("0958421083", b1.customer_id)

    def test_shared_phone_wrong_name_stays_ambiguous(self):
        ident = self.c["resolver"].resolve(self.turn("tôi là Lan", InputChannel.HOTLINE, "0958421083"))
        self.assertTrue(ident.is_ambiguous)

    def test_channels_seen_in_brief_after_fanpage_then_hotline(self):
        r, mem, bb = self.c["resolver"], self.c["memory"], self.c["brief"]
        r.resolve(self.turn("shop oi gia bn", InputChannel.FANPAGE, "fb.hạnh.274"), memory=mem)
        r.resolve(self.turn("sdt minh 0994893949 nhe", InputChannel.FANPAGE, "fb.hạnh.274"), memory=mem)
        ident = r.resolve(self.turn("alo chị vừa nhắn facebook", InputChannel.HOTLINE, "0994893949"), memory=mem)
        brief = bb.build(ident, "2026-10-16")
        self.assertEqual(ident.customer_id, "C017")
        self.assertEqual(brief.channels_seen, ["fanpage", "hotline"])
        self.assertEqual((brief.honorific, brief.customer_name), ("chị", "Hạnh"))

    def test_anonymous_phone_linked_from_facebook_is_stable_across_channels(self):
        r, mem = self.c["resolver"], self.c["memory"]
        a1 = r.resolve(self.turn("shop oi", InputChannel.FANPAGE, "fb.moi.1"), memory=mem)
        mem.set_profile_fact(a1.customer_id, "product_advised", "SKU-AP-Y")
        linked = r.resolve(self.turn("sdt em 0900000777", InputChannel.FANPAGE, "fb.moi.1"), memory=mem)
        hotline = r.resolve(self.turn("alo", InputChannel.HOTLINE, "0900000777"), memory=mem)
        self.assertEqual(linked.customer_id, hotline.customer_id)               # không có trong CRM: mã ổn định theo SĐT
        self.assertTrue(hotline.customer_id.startswith("CUST-ANON"))
        self.assertEqual(mem.get_profile_facts(hotline.customer_id).get("product_advised"), "SKU-AP-Y")
        self.assertNotEqual(a1.customer_id, hotline.customer_id)
        self.assertEqual(mem.get_profile_facts(a1.customer_id), {})              # mã tạm đã được gộp và xóa

    def test_self_honorific_from_conversation_when_crm_unknown(self):
        r, mem, bb = self.c["resolver"], self.c["memory"], self.c["brief"]
        ident = r.resolve(self.turn("anh muốn mua máy lọc không khí", InputChannel.HOTLINE, "0900000888"), memory=mem)
        brief = bb.build(ident, "2026-10-15")
        self.assertEqual(brief.honorific, "anh")
        self.assertEqual(brief.customer_name, "Quý khách")
        self.assertEqual(brief.addressing(), "anh")

    def test_unknown_caller_neutral_greeting(self):
        ident = self.c["resolver"].resolve(self.turn("alo", InputChannel.HOTLINE, "0900000999"), memory=self.c["memory"])
        brief = self.c["brief"].build(ident, "2026-10-15")
        self.assertEqual(brief.honorific, "anh/chị")
        self.assertEqual(brief.addressing(), "anh/chị")


if __name__ == "__main__":
    unittest.main()
