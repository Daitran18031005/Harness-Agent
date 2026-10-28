"""Bước 13 — chủ động đưa thông tin: CODE tra sẵn giá/tồn kho/KM/bảo hành lúc nhận diện khách quay lại (một lần/cuộc), LLM không tra lại, câu chào gộp một câu và nhắc ≤ 2 thông tin cũ."""
import unittest

from src.channels.normalizer import InputChannel
from src.harness.call_brief import CallBriefBuilder
from src.harness.orchestrator import HarnessOrchestrator as H
from src.memory.episodic import EpisodeRecord
from tests._helpers import build_components
from tests.test_order_gate import GateBase, KNOWN_PHONE

DATE = "2026-10-17"
GETQ = ("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 1})
INV = ("inventory.check", {"sku": "SKU-AP-Y"})
CHECKS = ("inventory.check", "pricing.get_quote")


def seed_returning_customer(mem):
    mem.set_profile_fact("C001", "product_advised", "SKU-AP-Y")
    mem.set_profile_fact("C001", "price_quoted_vnd", 5200000)
    mem.set_profile_fact("C001", "room_area_m2", 25.0)
    mem.add_episode("C001", EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="x",
                                          product_advised="SKU-AP-Y", price_quoted_vnd=5200000))


class CountingGateway:
    """Bọc cổng tool thật, đếm lời gọi theo tên."""
    def __init__(self, inner):
        self.inner, self.log = inner, []

    def execute_tool(self, name, args, caller="x"):
        self.log.append(name)
        return self.inner.execute_tool(name, args, caller=caller)


class PrecomputeTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()
        seed_returning_customer(self.c["memory"])
        self.gw = CountingGateway(self.c["mcp"])
        self.builder = CallBriefBuilder(self.c["memory"].as_caller("CallBriefBuilder"), tool_gateway=self.gw)

    def brief(self, date=DATE, builder=None):
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, KNOWN_PHONE)
        return (builder or self.builder).build(self.c["resolver"].resolve(t), date)

    def checks(self, name):
        return len([x for x in self.gw.log if x == name])

    def test_checked_once_per_call_with_real_tools_and_no_phone_in_args(self):
        pre = self.brief().precomputed
        self.assertEqual([c["name"] for c in pre["calls"]], ["catalog.search", "inventory.check", "pricing.get_quote"])
        self.assertEqual((pre["stock"]["in_stock"], pre["price"]["final_price_vnd"], pre["warranty_months"]), (True, 5200000, 24))
        self.assertEqual(pre["calls"][2]["args"]["customer_phone"], "CURRENT_CUSTOMER")        # trace không có SĐT thật
        self.assertNotIn(KNOWN_PHONE, str(pre["calls"]))
        self.assertEqual((self.checks("inventory.check"), self.checks("pricing.get_quote")), (1, 1))
        self.brief()                                                                           # lượt sau của cùng cuộc: lấy từ bộ nhớ đệm
        self.assertEqual((self.checks("inventory.check"), self.checks("pricing.get_quote")), (1, 1))
        self.brief(date="2026-10-18")                                                          # ngày khác = cuộc khác → tra lại
        self.assertEqual(self.checks("pricing.get_quote"), 2)

    def test_only_for_returning_customers_with_a_product(self):
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0911222333")
        self.assertIsNone(self.builder.build(self.c["resolver"].resolve(t), DATE).precomputed)

    def test_opening_is_one_combined_sentence_with_at_most_two_old_facts(self):
        op = self.brief().suggested_opening
        self.assertIn("Em vừa kiểm tra hôm nay: còn hàng, giá 5.200.000đ", op)
        self.assertIn("bảo hành 24 tháng", op)
        self.assertEqual(op.count("Em vừa kiểm tra hôm nay"), 1)
        self.assertNotIn("25m²", op)
        legacy = self.brief(builder=CallBriefBuilder(self.c["memory"].as_caller("CallBriefBuilder"), tool_gateway=None)).suggested_opening
        self.assertIn("5.200.000đ", legacy)
        self.assertNotIn("25m²", legacy)                                                       # không có tool: vẫn ≤ 2 thông tin cũ

    def test_out_of_stock_is_said_as_is(self):
        pre = {"stock": {"in_stock": False, "qty": 0, "restock_expected": "2026-10-25"}, "price": None, "warranty_months": None}
        self.assertEqual(CallBriefBuilder._today_sentence(pre), "Em vừa kiểm tra hôm nay: tạm hết hàng, dự kiến có lại ngày 2026-10-25.")

    def test_tool_failure_means_no_precompute_not_a_broken_brief(self):
        class Boom:
            def execute_tool(self, *a, **k):
                raise RuntimeError("mcp chết")
        b = self.brief(builder=CallBriefBuilder(self.c["memory"].as_caller("CallBriefBuilder"), tool_gateway=Boom()))
        self.assertIsNone(b.precomputed)
        self.assertIn("Dạ em chào", b.suggested_opening)


class HitRulesTest(unittest.TestCase):
    PRE = {"sku": "SKU-AP-Y", "checked_on": DATE, "calls": [{"name": "inventory.check", "result": {"in_stock": True, "qty": 15}},
                                                             {"name": "pricing.get_quote", "result": {"final_price_vnd": 5200000}}]}

    def hit(self, name, **args):
        return H._precomputed_hit(self.PRE, name, {"sku": "SKU-AP-Y", **args}, "0984726714", DATE)

    def test_same_request_is_served(self):
        self.assertEqual(self.hit("inventory.check")["qty"], 15)
        self.assertEqual(self.hit("pricing.get_quote", qty=1, customer_phone="0984726714")["final_price_vnd"], 5200000)

    def test_any_change_of_the_request_goes_to_the_real_tool(self):
        for kw in ({"qty": 2}, {"address": "Hà Nội"}, {"basket_skus": ["SKU-AP-X"]}, {"customer_phone": "0999999999"}):
            self.assertIsNone(self.hit("pricing.get_quote", **kw), kw)
        self.assertIsNone(H._precomputed_hit(self.PRE, "inventory.check", {"sku": "SKU-AP-X"}, None, DATE))
        self.assertIsNone(H._precomputed_hit(self.PRE, "inventory.check", {"sku": "SKU-AP-Y"}, None, "2026-10-18"))      # ngày khác
        self.assertIsNone(H._precomputed_hit(None, "inventory.check", {"sku": "SKU-AP-Y"}, None, DATE))
        self.assertIsNone(H._precomputed_hit(self.PRE, "order.create", {"sku": "SKU-AP-Y"}, None, DATE))                 # tool ghi không bao giờ


class OrchestratorServesPrecomputedTest(GateBase):
    def setUp(self):
        super().setUp()
        seed_returning_customer(self.c["memory"])

    def test_first_turn_trace_has_the_code_calls_and_llm_repeats_are_not_run_twice(self):
        txt, tc, meta = self.turn(KNOWN_PHONE, "ừ cho chị hỏi lại giá", [GETQ, INV], "Dạ giá 5.200.000đ ạ.", date=DATE)
        names = [c["name"] for c in tc]
        self.assertEqual(names.count("pricing.get_quote"), 1)                                 # chỉ lần CODE tra sẵn, lời gọi lặp của LLM không chạy lại
        self.assertEqual(names.count("inventory.check"), 1)
        self.assertEqual(sorted(meta["precomputed"]["served"]), sorted(CHECKS))
        self.assertEqual(meta["precomputed"]["sku"], "SKU-AP-Y")

    def test_calls_are_logged_once_and_kept_as_evidence_for_later_turns(self):
        self.turn(KNOWN_PHONE, "alo", [], "Dạ em nghe ạ.", date=DATE)
        _, tc2, meta2 = self.turn(KNOWN_PHONE, "giá sao em", [GETQ], "Dạ giá 5.200.000đ ạ.", date=DATE)
        self.assertEqual([c["name"] for c in tc2], [])                                        # lượt 2: LLM hỏi lại, được trả từ kết quả tra sẵn, không có tool mới
        self.assertEqual(meta2["precomputed"]["served"], ["pricing.get_quote"])
        sid = [k for k in self.orch._call_log if k.startswith("SESS-")][0]
        self.assertEqual([c["name"] for c in self.orch._call_log[sid]].count("pricing.get_quote"), 1)

    def test_a_different_quantity_still_calls_the_real_tool(self):
        _, tc, _ = self.turn(KNOWN_PHONE, "lấy 2 cái", [("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 2})], "Dạ ạ.", date=DATE)
        self.assertEqual([c["args"].get("qty") for c in tc if c["name"] == "pricing.get_quote"].count(2), 1)

    def test_llm_is_told_not_to_recheck(self):
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, KNOWN_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), DATE)
        msgs = self.orch._build_llm_messages(t, brief, [], DATE, None, precomputed=brief.precomputed)
        ctx = " ".join(m["content"] for m in msgs if m["role"] == "system")
        self.assertIn("ĐÃ kiểm tra THẬT đầu cuộc gọi hôm nay", ctx)
        self.assertIn("KHÔNG gọi lại pricing.get_quote/inventory.check", ctx)
        self.assertIn("giá cuối 5200000đ", ctx)
        plain = " ".join(m["content"] for m in self.orch._build_llm_messages(t, brief, [], DATE, None) if m["role"] == "system")
        self.assertNotIn("ĐÃ kiểm tra THẬT đầu cuộc gọi hôm nay (", plain)                  # không có tra sẵn thì không có dòng này


if __name__ == "__main__":
    unittest.main()
