"""MCP thật (bước 19): ≥ 2 server, agent là client qua giao thức MCP, phân quyền theo caller, kết quả y hệt gọi trực tiếp,
loại field nội bộ, lỗi có cấu trúc, và đường stdio (server = tiến trình riêng)."""
import json
import os
import time
import unittest

import asyncio

from mcp import Client

from mcp_servers import catalog_server, crm_server
from mcp_servers.common import Permissions
from src.tools.mcp_gateway import LocalToolGateway, MCPConnectionError, MCPToolGateway
from src.tools.tool_impl import reset_mock_state

EXPECTED = {
    "catalog": {"catalog.search", "inventory.check", "pricing.get_quote", "pricing.quote_order", "product.shortlist", "admin.audit"},
    "crm": {"crm.get_customer", "order.create", "order.status", "order.update", "schedule.callback", "handoff.transfer",
            "admin.reset_state", "admin.audit"},
}
MEMORY_TOOLS = {"memory.open", "memory.close", "memory.begin_turn", "memory.drain_writes", "memory.abort_turn", "memory.working_get",
                "memory.working_set", "memory.profile_set", "memory.profile_get", "memory.facts_by_channel", "memory.profile_versions",
                "memory.episode_add", "memory.episodes_get", "memory.merge_customer", "memory.query_policy", "memory.identity_links_load",
                "memory.identity_link_save", "memory.admin_audit",                                                   # tầng thấp (chỉ lõi)
                "memory.get_call_brief", "memory.search", "memory.timeline", "memory.commit_turn", "memory.commit_episode",
                "memory.delete_customer"}                                                                           # 6 tool cao; test riêng ở test_mcp_memory.py
SCENARIO = [
    ("catalog.search", {"query": "AirPure"}, "LLMOrchestrator"),
    ("catalog.search", {"sku": "SKU-SN-CAS"}, "SkuResolver"),
    ("inventory.check", {"sku": "SKU-AP-Y", "on": "2026-10-17"}, "LLMOrchestrator"),
    ("pricing.get_quote", {"sku": "SKU-AP-Y", "on": "2026-10-15", "customer_phone": "0984726714"}, "LLMOrchestrator"),
    ("pricing.get_quote", {"sku": "SKU-AP-X", "on": "2026-10-15", "basket_skus": ["SKU-AP-Y"]}, "LLMOrchestrator"),
    ("crm.get_customer", {"phone": "0984726714"}, "IdentityResolver"),
    ("crm.get_customer", {"phone": "0900000000"}, "IdentityResolver"),
    ("product.shortlist", {"category": "máy lọc không khí", "room_area_m2": 25, "has_children": True, "budget_vnd": 5000000, "on": "2026-10-15"}, "LLMOrchestrator"),
    ("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-Y", "price_vnd": 5200000, "payment": "COD", "on": "2026-10-15"}, "LLMOrchestrator"),
    ("order.status", {"customer_phone": "0984726714"}, "CallBriefBuilder"),
    ("schedule.callback", {"customer_phone": "0984726714", "callback_at": "2026-10-16T09:00"}, "LLMOrchestrator"),
]


def run_scenario(gw):
    gw.reset_state()
    return [gw.execute_tool(t, a, caller=c) for t, a, c in SCENARIO]


class InprocMCPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gw = MCPToolGateway(transport="inproc")

    @classmethod
    def tearDownClass(cls):
        cls.gw.close()

    def test_at_least_two_real_servers_with_expected_tools(self):
        tools = self.gw.list_tools()
        self.assertGreaterEqual(len(tools), 2)
        for server, expected in EXPECTED.items():
            self.assertEqual(set(tools[server]), expected, server)

    def test_results_identical_to_direct_calls(self):
        local = run_scenario(LocalToolGateway())
        over_mcp = run_scenario(self.gw)
        self.assertEqual(len(local), len(over_mcp))
        for (tool, args, _), a, b in zip(SCENARIO, local, over_mcp):
            self.assertEqual(a, b, f"{tool} {args}")

    def test_internal_underscore_fields_never_leave_the_server(self):
        server, _ = catalog_server.build_server()

        async def go():
            async with Client(server) as c:
                r = await c.call_tool("catalog.search", {"query": "AirPure"}, meta={"caller": "LLMOrchestrator"})
                return r.content[0].text
        raw = asyncio.run(go())

        def keys(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    yield k
                    yield from keys(v)
            elif isinstance(o, list):
                for v in o:
                    yield from keys(v)
        self.assertFalse([k for k in keys(json.loads(raw)) if str(k).startswith("_")])

    def test_unknown_tool_and_bad_arguments_give_structured_errors(self):
        self.assertIn("không tồn tại", self.gw.execute_tool("nope.tool", {}, caller="LLMOrchestrator")["error"])
        bad = self.gw.execute_tool("pricing.get_quote", {"on": "2026-10-15"}, caller="LLMOrchestrator")   # thiếu sku
        self.assertEqual(bad["error"], "tool_execution_failed")

    def test_default_deny_permissions(self):
        for caller in ("Orchestrator", "", "KeAnhHung"):
            r = self.gw.execute_tool("pricing.get_quote", {"sku": "SKU-AP-Y"}, caller=caller)
            self.assertEqual(r["error"], "forbidden", caller)
        # đọc được nhưng KHÔNG được ghi
        r = self.gw.execute_tool("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-Y"}, caller="CallBriefBuilder")
        self.assertEqual(r["error"], "forbidden")
        r = self.gw.execute_tool("order.update", {"order_id": "OD1", "action": "cancel"}, caller="SkuResolver")
        self.assertEqual(r["error"], "forbidden")
        # tool quản trị chỉ dành cho bộ chạy đánh giá/test
        self.assertEqual(self.gw.execute_tool("admin.reset_state", {}, caller="LLMOrchestrator")["error"], "forbidden")
        self.assertEqual(self.gw.execute_tool("admin.reset_state", {}, caller="TestHarness"), {"reset": True})

    def test_forbidden_write_really_did_not_write(self):
        import mock_tools
        self.gw.reset_state()
        self.gw.execute_tool("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-Y", "price_vnd": 5200000},
                             caller="IdentityResolver")
        self.assertEqual(len(mock_tools._ORDERS), 0)

    def test_server_side_audit_records_caller_and_denials_without_arguments(self):
        self.gw.execute_tool("pricing.get_quote", {"sku": "SKU-AP-Y", "customer_phone": "0912345678"}, caller="Hacker")
        self.gw.execute_tool("pricing.get_quote", {"sku": "SKU-AP-Y", "customer_phone": "0912345678"}, caller="LLMOrchestrator")
        audit = [a for a in self.gw.server_audit() if a["tool"] == "pricing.get_quote"][-2:]
        self.assertEqual([(a["caller"], a["ok"]) for a in audit], [("Hacker", False), ("LLMOrchestrator", True)])
        self.assertEqual(audit[0]["error"], "forbidden")
        self.assertNotIn("0912345678", json.dumps(self.gw.server_audit()))      # SĐT không bao giờ vào nhật ký server

    def test_gateway_audit_log_has_transport_and_latency(self):
        self.gw.execute_tool("inventory.check", {"sku": "SKU-AP-Y"}, caller="LLMOrchestrator")
        last = self.gw.audit_log[-1]
        self.assertEqual(last["transport"], "inproc")
        self.assertGreaterEqual(last["duration_ms"], 0)
        self.assertEqual(last["caller"], "LLMOrchestrator")

    def test_permissions_file_covers_every_tool_and_denies_by_default(self):
        perms = Permissions.load()
        every = set().union(*EXPECTED.values()) | MEMORY_TOOLS
        self.assertEqual(set(perms.tools), every)
        self.assertFalse(perms.allowed("order.create", None))
        self.assertFalse(perms.allowed("order.create", "AnyoneElse"))

    def test_shortlist_over_mcp_matches_in_process_retriever(self):
        from src.catalog import ProductRetriever
        mcp_res = self.gw.execute_tool("product.shortlist", {"category": "giày", "budget_vnd": 1500000, "on": "2026-10-15"}, caller="LLMOrchestrator")
        direct = ProductRetriever().shortlist({"budget_vnd": 1500000}, category="giày", in_stock_fn=lambda s: None).to_dict()
        self.assertEqual([i["sku"] for i in mcp_res["items"]], [i["sku"] for i in direct["items"]])
        self.assertEqual(mcp_res["recommendation"], direct["recommendation"])

    def test_closed_gateway_returns_error_not_hang(self):
        gw = MCPToolGateway(transport="inproc")
        gw.close()
        self.assertEqual(gw.execute_tool("inventory.check", {"sku": "SKU-AP-Y"}, caller="LLMOrchestrator")["error"], "gateway_closed")

    def test_invalid_transport_rejected(self):
        with self.assertRaises(ValueError):
            MCPToolGateway(transport="carrier-pigeon")


class StdioMCPTest(unittest.TestCase):
    """Server là TIẾN TRÌNH riêng (giao thức MCP qua stdin/stdout) — đường chạy thật của main.py / run_eval.py."""

    @classmethod
    def setUpClass(cls):
        cls.gw = MCPToolGateway(transport="stdio", timeout_s=60)

    @classmethod
    def tearDownClass(cls):
        cls.gw.close()

    def test_two_separate_server_processes_are_running(self):
        import psutil
        me = psutil.Process(os.getpid())
        cmdlines = [" ".join(p.cmdline()) for p in me.children(recursive=True)]
        self.assertTrue(any("mcp_servers.catalog_server" in c for c in cmdlines), cmdlines)
        self.assertTrue(any("mcp_servers.crm_server" in c for c in cmdlines), cmdlines)

    def test_same_results_as_direct_and_state_lives_in_the_server(self):
        import mock_tools
        local = run_scenario(LocalToolGateway())
        reset_mock_state()
        over_stdio = run_scenario(self.gw)
        for (tool, args, _), a, b in zip(SCENARIO, local, over_stdio):
            self.assertEqual(a, b, f"{tool} {args}")
        self.assertEqual(len(mock_tools._ORDERS), 0)                    # đơn được tạo trong TIẾN TRÌNH server, không phải ở đây

    def test_reset_state_over_stdio_gives_reproducible_order_ids(self):
        ids = []
        for _ in range(2):
            self.gw.reset_state()
            r = self.gw.execute_tool("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-Y", "price_vnd": 5200000,
                                                      "payment": "COD", "on": "2026-10-15"}, caller="LLMOrchestrator")
            ids.append(r.get("order_id"))
        self.assertEqual(ids[0], ids[1])

    def test_permissions_enforced_in_the_server_process(self):
        self.assertEqual(self.gw.execute_tool("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-Y"}, caller="CallBriefBuilder")["error"], "forbidden")

    def test_close_terminates_server_processes(self):
        import psutil
        me = psutil.Process(os.getpid())
        before = {p.pid for p in me.children(recursive=True)}
        gw = MCPToolGateway(transport="stdio", timeout_s=60)
        mine = {p.pid for p in me.children(recursive=True)} - before          # tiến trình do cổng MỚI này sinh ra
        self.assertGreaterEqual(len(mine), 2)
        gw.close()
        deadline = time.time() + 15
        while time.time() < deadline and any(psutil.pid_exists(pid) for pid in mine):
            time.sleep(0.2)
        self.assertFalse([pid for pid in mine if psutil.pid_exists(pid)])

    def test_overhead_is_small(self):
        samples = []
        for _ in range(40):
            t = time.perf_counter()
            self.gw.execute_tool("inventory.check", {"sku": "SKU-AP-Y", "on": "2026-10-15"}, caller="LLMOrchestrator")
            samples.append((time.perf_counter() - t) * 1000)
        samples.sort()
        self.assertLess(samples[len(samples) // 2], 100.0)             # trung vị < 100 ms (thực tế vài ms)


if __name__ == "__main__":
    unittest.main()
