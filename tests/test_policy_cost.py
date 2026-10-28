"""Bước 11: chi phí/quyết định của router chính sách phải vào trace và trần chi phí (trước đây router có LLMClient riêng nên chi phí không được đếm)."""
import unittest

from tests.test_order_gate import GateBase, NEW_PHONE
from src.llm.cost_tracker import CostTracker
from src.memory.policy_router import PolicyRouter
from src.memory.service import MemoryService

USAGE = {"model": "gpt-4o-mini", "usd_cost": 0.001, "vnd_cost": 25.4, "llm_calls": 1, "latency_ms": 900}
ROUTE = {"files": ["chinh-sach-doi-tra.md"], "as_of_date": None, "as_of_evidence": None, "answerable": True}


class RouterLLM:
    available = True

    def complete_json(self, messages):
        return dict(ROUTE), dict(USAGE)


class ServiceTest(unittest.TestCase):
    def test_query_policy_exposes_route_and_usage(self):
        svc = MemoryService(enable_persistence=False)
        svc.semantic.router = PolicyRouter(RouterLLM())
        svc.query_policy("đổi size có mất phí không?")
        info = svc.last_policy_route
        self.assertEqual(info["route"]["files"], ["chinh-sach-doi-tra.md"])
        self.assertEqual([u["vnd_cost"] for u in info["usage"]], [25.4])
        svc.query_policy("giao hàng mất mấy ngày?")                       # mỗi lần search lấy chi phí của CHÍNH lần đó
        self.assertEqual(len(svc.last_policy_route["usage"]), 1)

    def test_without_router_usage_is_empty(self):
        svc = MemoryService(enable_persistence=False)
        svc.semantic.router = None
        svc.query_policy("đổi size")
        self.assertEqual(svc.last_policy_route["usage"], [])


class RemoteTest(unittest.TestCase):
    def test_route_info_crosses_the_mcp_boundary(self):
        from src.memory.remote import MemoryLink, RemoteMemoryService
        link = MemoryLink("inproc")
        self.addCleanup(link.close)
        m = RemoteMemoryService(enable_persistence=False, transport="inproc", link=link, caller="TestHarness")
        self.addCleanup(m.close)
        chunks = m.query_policy("đổi size có mất phí không?")
        self.assertTrue(chunks)
        self.assertEqual(set(m.last_policy_route), {"route", "usage"})     # server không có LLM trong test → usage rỗng, nhưng khóa đã được chuyển sang client
        self.assertEqual(m.last_policy_route["usage"], [])


class OrchestratorTest(GateBase):
    def setUp(self):
        super().setUp()
        self.llm.cost_tracker = CostTracker()
        self.c["memory"].semantic.router = PolicyRouter(RouterLLM())

    def ask(self):
        return self.turn(NEW_PHONE, "mua giày về chật, đổi size có mất phí không", [("search_policy", {"query": "đổi size có mất phí không"})])

    def test_router_cost_goes_to_the_hard_cap_total_and_the_trace(self):
        _, _, meta = self.ask()
        self.assertAlmostEqual(self.llm.cost_tracker.cumulative_usd_cost, 0.001)
        pr = meta["policy_route"]
        self.assertEqual((pr[0]["files"], pr[0]["answerable"], pr[0]["vnd_cost"], pr[0]["latency_ms"]), (["chinh-sach-doi-tra.md"], True, 25.4, 900))

    def test_turn_without_policy_search_has_no_route_entry(self):
        _, _, meta = self.turn(NEW_PHONE, "alo em", [])
        self.assertIsNone(meta["policy_route"])

    def test_cap_stops_after_the_router_spend(self):
        self.llm.cost_tracker.set_hard_cap(1.0)                            # 1 VND << 25,4 VND của router
        self.ask()
        from src.llm.cost_tracker import BudgetExceeded
        with self.assertRaises(BudgetExceeded):
            self.llm.cost_tracker.check_cap()


if __name__ == "__main__":
    unittest.main()
