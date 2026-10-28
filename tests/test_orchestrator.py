"""Bước 2, 4, 5 — tool args thật (N3), idempotency (A2/N4), product_advised (A1)."""
import unittest
from tests._helpers import build_components


class FakeLLM:
    """LLM giả: trả lần lượt các 'kịch bản' tool call rồi text, không gọi mạng."""
    available = True

    def __init__(self, plan):
        self.plan = plan  # list[(name, args)] + final text

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        log = []
        for name, args in self.plan["calls"]:
            result, executed = tool_executor(name, args)
            log.append({"name": name, "tool": name, "args": executed, "result": result})
        return self.plan["text"], log, {"prompt_tokens": 0, "completion_tokens": 0}


class OrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()

    def _brief(self, phone, date="2026-10-15"):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, phone)
        return t, self.c["brief"].build(self.c["resolver"].resolve(t), date)

    def test_gift_quote_does_not_override_product(self):  # A1 — SAMPLE-01
        orch = self.c["orchestrator"]
        tool_calls = [
            {"name": "pricing.get_quote", "args": {"sku": "SKU-AP-Y"}, "result": {"sku": "SKU-AP-Y", "final_price_vnd": 5200000,
             "applied_promos": [{"promo_code": "GIFT-FILTER", "type": "gift", "gift_sku": "SKU-AP-FLT-X"}]}},
            {"name": "pricing.get_quote", "args": {"sku": "SKU-AP-FLT-X"}, "result": {"sku": "SKU-AP-FLT-X", "final_price_vnd": 690000, "applied_promos": []}},
        ]
        orch._persist_tool_grounded_facts("C001", tool_calls, agent_text="Dạ mẫu AirPure Y giá 5.200.000đ, tặng kèm màng lọc ạ.")
        facts = self.c["memory"].get_profile_facts("C001")
        self.assertEqual(facts.get("product_advised"), "SKU-AP-Y")
        self.assertEqual(facts.get("price_quoted_vnd"), 5200000)
        self.assertEqual(facts.get("promo_code"), "GIFT-FILTER")

    def test_variant_order_sets_parent_and_variant(self):
        orch = self.c["orchestrator"]
        orch._persist_tool_grounded_facts("C012", [{"name": "order.create", "args": {"sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "qty": 1},
                                                    "result": {"status": "created", "order_id": "OD600001", "total_vnd": 890000}}])
        f = self.c["memory"].get_profile_facts("C012")
        self.assertEqual(f["product_advised"], "SKU-SN-CAS")
        self.assertEqual(f["variant_sku"], "SKU-SN-CAS-39-DEN")
        self.assertEqual(f["order_id"], "OD600001")
        self.assertEqual(str(f["size"]), "39")
        self.assertEqual(f["color"], "den")

    def test_executed_args_logged_and_on_injected(self):  # N3
        orch = self.c["orchestrator"]
        orch.llm_client = FakeLLM({"calls": [("inventory.check", {"sku": "SKU-AP-Y"})], "text": "Dạ còn hàng ạ."})
        t, b = self._brief("0984726714")
        _, tool_calls, _ = orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(tool_calls[0]["args"].get("on"), "2026-10-17")

    def test_phone_token_substituted(self):  # N13 — LLM không thấy SĐT thật
        orch = self.c["orchestrator"]
        orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"})],
                                   "text": "Dạ em đã lên đơn ạ."})
        t, b = self._brief("0984726714")
        _, tool_calls, _ = orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(tool_calls[0]["args"]["customer_phone"], "0984726714")
        self.assertEqual(tool_calls[0]["result"].get("status"), "created")

    def test_order_update_idempotent_within_call(self):  # A2 — SAMPLE-03
        orch = self.c["orchestrator"]
        t, b = self._brief("0922264686")
        orch.llm_client = FakeLLM({"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-CAS-39-DEN", "price_vnd": 890000, "payment": "COD"})], "text": "Dạ em đã lên đơn ạ."})
        _, tc, _ = orch.process_turn(t, b, current_date="2026-10-15")
        oid = tc[0]["result"]["order_id"]
        t2, b2 = self._brief("0922264686", "2026-10-19")
        upd = ("order.update", {"order_id": oid, "action": "exchange_size", "new_variant_sku": "SKU-SN-CAS-40-DEN"})
        fees = []
        for _ in range(3):
            orch.llm_client = FakeLLM({"calls": [upd], "text": "Dạ em đã làm thủ tục đổi size ạ."})
            _, tc, _ = orch.process_turn(t2, b2, current_date="2026-10-19")
            fees.append(tc[0]["result"].get("fee_vnd"))
        self.assertEqual(fees, [0, 0, 0])

    def test_no_duplicate_order_create_within_call(self):  # N4
        orch = self.c["orchestrator"]
        t, b = self._brief("0984726714")
        create = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD"})
        ids = set()
        for _ in range(2):
            orch.llm_client = FakeLLM({"calls": [create], "text": "Dạ em đã lên đơn ạ."})
            _, tc, _ = orch.process_turn(t, b, current_date="2026-10-17")
            ids.add(tc[0]["result"]["order_id"])
        self.assertEqual(len(ids), 1)


if __name__ == "__main__":
    unittest.main()
