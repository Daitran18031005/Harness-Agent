"""
Cổng công cụ của agent = CLIENT của các MCP server thật (giao thức Model Context Protocol, SDK `mcp`).

  agent (orchestrator) ──execute_tool──► MCPToolGateway ──MCP (JSON-RPC)──► mcp-catalog   (catalog.search, inventory.check,
                                              │                                          pricing.get_quote, product.shortlist)
                                              └────────────────────────────► mcp-crm       (crm.get_customer, order.*, schedule.callback,
                                                                                            handoff.transfer, admin.*)

Hai kiểu vận chuyển (`transport` hoặc biến môi trường `MCP_TRANSPORT`):
  - `stdio`  : mỗi server là MỘT TIẾN TRÌNH riêng (`python -m mcp_servers.<server>`), nói chuyện qua stdin/stdout — dùng khi chạy thật
               (`main.py`, `run_eval.py`, UI). Trạng thái đơn/vé nằm trong tiến trình server.
  - `inproc` : cùng giao thức MCP nhưng qua luồng bộ nhớ trong CÙNG tiến trình — dùng cho test (test đọc được trạng thái mock).
  - `local`  : (chỉ để so độ trễ/gỡ lỗi) gọi thẳng hàm, KHÔNG qua MCP.
Hành vi giữ nguyên so với cổng cũ: bỏ field `_*` khỏi kết quả (N15), lỗi tool → {error: ...}, nhật ký kiểm toán tập trung (`audit_log`, thêm
`transport` và `mcp_ms`). Phân quyền theo caller kiểm ở PHÍA SERVER (config/mcp_permissions.json), mặc định từ chối.
"""
import asyncio
import atexit
import json
import os
import sys
import threading
import time
import uuid
import weakref
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any, Dict, List, Optional

# Tương thích ngược: các tên này từng nằm ở đây.
from src.tools.tool_impl import (CRMTool, CatalogPricingTool, OrderCallbackTool, btc_mock, reset_mock_state,  # noqa: F401
                                 strip_internal)

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SERVER_OF = {
    "catalog.search": "catalog", "inventory.check": "catalog", "pricing.get_quote": "catalog", "pricing.quote_order": "catalog", "product.shortlist": "catalog",
    "crm.get_customer": "crm", "order.create": "crm", "order.status": "crm", "order.update": "crm",
    "schedule.callback": "crm", "handoff.transfer": "crm", "admin.reset_state": "crm", "admin.audit": "crm",
}
SERVER_MODULE = {"catalog": "mcp_servers.catalog_server", "crm": "mcp_servers.crm_server"}


class MCPConnectionError(RuntimeError):
    pass


def _unknown_tool(tool_name: str) -> Dict[str, Any]:
    return {"error": f"Tool '{tool_name}' không tồn tại hoặc chưa được cấp quyền."}


class _BaseGateway:
    def __init__(self) -> None:
        self.audit_log: List[Dict[str, Any]] = []

    def _record(self, tool_name: str, args: Dict[str, Any], caller: str, transport: str) -> Dict[str, Any]:
        entry = {"call_id": f"CALL-{uuid.uuid4().hex[:6]}", "caller": caller, "tool": tool_name, "args": args,
                 "timestamp": datetime.now().isoformat(), "transport": transport}
        self.audit_log.append(entry)
        return entry

    def reset_state(self) -> None:
        """Xóa trạng thái đơn/vé/lịch/KM dùng-một-lần (mỗi kịch bản chạy độc lập). Chỉ caller `TestHarness`/`EvalRunner`."""
        self.execute_tool("admin.reset_state", {}, caller="TestHarness")


class LocalToolGateway(_BaseGateway):
    """Cổng cũ: gọi thẳng hàm Python, KHÔNG qua MCP. Chỉ để đo độ trễ tăng thêm của MCP và gỡ lỗi (`MCP_TRANSPORT=local`)."""

    def __init__(self, crm: Optional[CRMTool] = None, catalog: Optional[CatalogPricingTool] = None, order: Optional[OrderCallbackTool] = None):
        super().__init__()
        self.crm, self.catalog, self.order = crm or CRMTool(), catalog or CatalogPricingTool(), order or OrderCallbackTool()
        self.transport = "local"
        self._retriever = None

    def _shortlist(self, **kw: Any) -> Dict[str, Any]:
        if self._retriever is None:
            from src.catalog import ProductRetriever
            self._retriever = ProductRetriever()
        on = kw.pop("on", "2026-10-15")
        category, query, top_k = kw.pop("category", None), kw.pop("query", None), kw.pop("top_k", None)
        list_all = bool(kw.pop("list_all", None))

        def in_stock(sku: str) -> Optional[bool]:
            res = self.catalog.inventory_check(sku=sku, on=on)
            return res.get("in_stock") if "error" not in res else None
        return self._retriever.shortlist({k: v for k, v in kw.items() if v is not None}, category=category, query=query,
                                         top_k=top_k, in_stock_fn=in_stock, list_all=list_all).to_dict()

    def execute_tool(self, tool_name: str, args: Dict[str, Any], caller: str = "Orchestrator") -> Dict[str, Any]:
        entry = self._record(tool_name, args, caller, "local")
        started = time.perf_counter()
        table = {"crm.get_customer": self.crm.get_customer, "catalog.search": self.catalog.search, "inventory.check": self.catalog.inventory_check,
                 "pricing.get_quote": self.catalog.get_quote, "pricing.quote_order": self.catalog.quote_order, "order.create": self.order.create_order, "order.status": self.order.order_status,
                 "order.update": self.order.order_update, "schedule.callback": self.order.schedule_callback,
                 "handoff.transfer": self.order.handoff_transfer, "product.shortlist": self._shortlist,
                 "admin.reset_state": lambda: (reset_mock_state(), {"reset": True})[1]}
        try:
            result = table[tool_name](**args) if tool_name in table else _unknown_tool(tool_name)
        except Exception as e:
            result = {"error": "tool_execution_failed", "details": str(e)}
        result = strip_internal(result)
        entry["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        entry["result"] = result
        return result


class MCPToolGateway(_BaseGateway):
    """Client MCP đồng bộ: giữ một vòng lặp asyncio chạy nền, kết nối tới các server một lần và dùng lại cho mọi lượt."""

    def __init__(self, crm: Optional[CRMTool] = None, catalog: Optional[CatalogPricingTool] = None,
                 order: Optional[OrderCallbackTool] = None, transport: Optional[str] = None, timeout_s: float = 60.0):
        super().__init__()
        self.transport = (transport or os.environ.get("MCP_TRANSPORT") or "inproc").strip().lower()
        if self.transport not in ("stdio", "inproc"):
            raise ValueError(f"MCP_TRANSPORT không hợp lệ: '{self.transport}' (stdio | inproc; 'local' dùng LocalToolGateway)")
        self.timeout_s = timeout_s
        self.crm, self.catalog, self.order = crm, catalog, order
        self._clients: Dict[str, Any] = {}
        self._servers: Dict[str, Any] = {}               # (inproc) server + guard để đọc nhật ký phía server
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._stop: Optional[asyncio.Event] = None
        self._thread = threading.Thread(target=self._loop.run_forever, name="mcp-gateway", daemon=True)
        self._thread.start()
        self._supervisor = asyncio.run_coroutine_threadsafe(self._supervise(), self._loop)
        if not self._ready.wait(self.timeout_s):
            self.close()
            raise MCPConnectionError(f"MCP server không sẵn sàng sau {self.timeout_s:.0f}s (transport={self.transport})")
        if self._startup_error is not None:
            err = self._startup_error
            self.close()
            raise MCPConnectionError(f"không kết nối được MCP server ({self.transport}): {err}") from err
        ref = weakref.ref(self)                           # thoát tiến trình → đóng kết nối, kết thúc các tiến trình server con
        atexit.register(lambda: ref() is not None and ref().close())

    # ------------------------------------------------------------------------------------------ kết nối
    def _targets(self) -> Dict[str, Any]:
        if self.transport == "inproc":
            from mcp_servers import catalog_server, crm_server
            cat_server, cat_guard = catalog_server.build_server(self.catalog)
            crm_srv, crm_guard = crm_server.build_server(self.crm, self.order)
            self._servers = {"catalog": (cat_server, cat_guard), "crm": (crm_srv, crm_guard)}
            return {"catalog": cat_server, "crm": crm_srv}
        from mcp.client.stdio import StdioServerParameters
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": CODE_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")}
        return {name: StdioServerParameters(command=sys.executable, args=["-m", module], cwd=CODE_DIR, env=env)
                for name, module in SERVER_MODULE.items()}

    async def _supervise(self) -> None:
        """Mở/đóng mọi kết nối trong CÙNG MỘT task (yêu cầu của anyio): vào `async with`, báo sẵn sàng, đợi lệnh dừng, thoát."""
        from mcp import Client
        self._stop = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                for name, target in self._targets().items():
                    self._clients[name] = await stack.enter_async_context(Client(target))
                self._ready.set()
                await self._stop.wait()
        except BaseException as e:                       # noqa: BLE001 — báo lỗi khởi động cho luồng chính
            self._startup_error = e
            self._ready.set()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._stop is not None:
                self._loop.call_soon_threadsafe(self._stop.set)
                try:
                    self._supervisor.result(timeout=10)
                except Exception:
                    pass
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)

    def __enter__(self) -> "MCPToolGateway":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------------------------------ gọi tool
    async def _call(self, server: str, tool_name: str, args: Dict[str, Any], caller: str) -> Dict[str, Any]:
        res = await self._clients[server].call_tool(tool_name, args, meta={"caller": caller})
        text = "".join(getattr(c, "text", "") for c in res.content)
        if res.is_error:
            return {"error": "tool_execution_failed", "details": text[:500]}
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            return {"error": "tool_bad_response", "details": text[:200]}
        return out if isinstance(out, dict) else {"result": out}

    def execute_tool(self, tool_name: str, args: Dict[str, Any], caller: str = "Orchestrator") -> Dict[str, Any]:
        entry = self._record(tool_name, args, caller, self.transport)
        started = time.perf_counter()
        server = SERVER_OF.get(tool_name)
        if server is None:
            result = _unknown_tool(tool_name)
        elif self._closed:
            result = {"error": "gateway_closed"}
        else:
            try:
                result = asyncio.run_coroutine_threadsafe(self._call(server, tool_name, args, caller), self._loop).result(self.timeout_s)
            except Exception as e:                       # hết thời gian chờ / server chết
                result = {"error": "tool_execution_failed", "details": f"{type(e).__name__}: {e}"}
        result = strip_internal(result)
        entry["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        entry["result"] = result
        return result

    # ------------------------------------------------------------------------------------------ tiện ích
    def list_tools(self) -> Dict[str, List[str]]:
        async def go() -> Dict[str, List[str]]:
            return {name: sorted(t.name for t in (await c.list_tools()).tools) for name, c in self._clients.items()}
        return asyncio.run_coroutine_threadsafe(go(), self._loop).result(self.timeout_s)

    def server_audit(self) -> List[Dict[str, Any]]:
        """Nhật ký kiểm toán phía SERVER của cả hai server (caller, tool, có lỗi không, thời gian) — không chứa tham số."""
        out: List[Dict[str, Any]] = []
        for server in ("catalog", "crm"):
            res = asyncio.run_coroutine_threadsafe(self._call(server, "admin.audit", {}, "TestHarness"), self._loop).result(self.timeout_s)
            out.extend(res.get("audit", []))
        return out
