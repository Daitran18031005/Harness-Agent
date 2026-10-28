"""
Client của MCP server `mcp-memory` (kiến trúc "một nơi ghi duy nhất").

  orchestrator / CallBriefBuilder / UI / bộ chạy đánh giá ──► RemoteMemoryService ──MCP──► mcp-memory ──► MemoryService ──► SQLite
                                                              (giao diện Y HỆT MemoryService)          (người ghi duy nhất)

`RemoteMemoryService` có đúng các phương thức công khai của `MemoryService` mà phần còn lại của hệ thống dùng, nên orchestrator/Call Brief/
IdentityResolver không đổi. Khác biệt:
  - Mỗi thành phần nhận một "view" mang TÊN CALLER riêng (`memory.as_caller("CallBriefBuilder")`) — server kiểm quyền theo caller (mặc định từ chối).
  - Hai tầng tool. LÕI (`HarnessCore`, và `EvalRunner`/`TestHarness` thay lõi khi chạy đánh giá/test) dùng TOOL THẤP (`memory.profile_set`, `memory.drain_writes`…).
    Mọi caller khác đi qua 6 TOOL CAO: đọc -> `memory.get_call_brief` / `memory.search` / `memory.timeline`; ghi -> `memory.commit_turn` / `memory.commit_episode`
    (chỉ `HarnessOrchestrator`); xóa khách -> `memory.delete_customer` (chỉ `Operator`). Server vẫn là nơi quyết định quyền — client chỉ chọn tool theo tên caller.
  - Dữ liệu qua JSON: trả về bản SAO của WorkingMemoryState / EpisodeRecord / ProfileFact (muốn đổi phải gọi `set_working` / `add_episode`…).
  - Listener xóa khách (`register_delete_listener`) chạy ở phía client sau khi server xóa xong.
Vận chuyển (`MEMORY_TRANSPORT` hoặc tham số `transport`): `local` = MemoryService trong tiến trình (mặc định cho test), `inproc` = cùng giao thức MCP qua luồng
bộ nhớ trong cùng tiến trình, `stdio` = server là TIẾN TRÌNH RIÊNG (`python -m mcp_servers.memory_server`; mặc định của main.py/UI/run_eval.py).
"""
import asyncio
import atexit
import json
import os
import sys
import threading
import time
import weakref
from collections import Counter
from contextlib import AsyncExitStack
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from .episodic import EpisodeRecord
from .profile import ProfileFact
from .service import MemoryService
from .sqlite_store import default_db_path
from .working import WorkingMemoryState

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER_MODULE = "mcp_servers.memory_server"
TRANSPORTS = ("local", "inproc", "stdio")
CORE_CALLERS = frozenset({"HarnessCore", "EvalRunner", "TestHarness"})        # dùng tool thấp; mọi caller khác dùng 6 tool cao


class MemoryServerError(RuntimeError):
    pass


class MemoryAccessDenied(PermissionError):
    pass


class MemoryLink:
    """Kết nối MCP tới mcp-memory: một vòng lặp asyncio chạy nền, kết nối một lần dùng lại; gọi đồng bộ từ phía agent."""

    def __init__(self, transport: str = "stdio", timeout_s: float = 60.0):
        if transport not in ("inproc", "stdio"):
            raise ValueError(f"transport không hợp lệ: '{transport}' (inproc | stdio)")
        self.transport, self.timeout_s = transport, timeout_s
        self.calls: Counter = Counter()          # số lời gọi theo tool (đo chi phí MCP của bộ nhớ)
        self.ms_by_tool: Counter = Counter()     # tổng thời gian (ms) theo tool — tách lời gọi nhẹ khỏi lời gọi nặng (memory.open dựng KB)
        self.total_ms = 0.0
        self.registry = None                     # (inproc) StoreRegistry của server — để test đọc trạng thái phía server
        self.server_guard = None
        self._client: Any = None
        self._ready = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._stop: Optional[asyncio.Event] = None
        self._thread = threading.Thread(target=self._loop.run_forever, name="mcp-memory-link", daemon=True)
        self._thread.start()
        self._supervisor = asyncio.run_coroutine_threadsafe(self._supervise(), self._loop)
        if not self._ready.wait(self.timeout_s):
            self.close()
            raise MemoryServerError(f"mcp-memory không sẵn sàng sau {self.timeout_s:.0f}s (transport={transport})")
        if self._startup_error is not None:
            err = self._startup_error
            self.close()
            raise MemoryServerError(f"không kết nối được mcp-memory ({transport}): {err}") from err
        ref = weakref.ref(self)
        atexit.register(lambda: ref() is not None and ref().close())

    def _target(self) -> Any:
        if self.transport == "inproc":
            from mcp_servers import memory_server
            server, self.server_guard, self.registry = memory_server.build_server()
            return server
        from mcp.client.stdio import StdioServerParameters
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONPATH": CODE_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")}
        return StdioServerParameters(command=sys.executable, args=["-m", SERVER_MODULE], cwd=CODE_DIR, env=env)

    async def _supervise(self) -> None:
        """Mở/đóng kết nối trong CÙNG MỘT task (yêu cầu của anyio)."""
        from mcp import Client
        self._stop = asyncio.Event()
        try:
            async with AsyncExitStack() as stack:
                self._client = await stack.enter_async_context(Client(self._target()))
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

    async def _call(self, tool: str, args: Dict[str, Any], caller: str) -> Dict[str, Any]:
        res = await self._client.call_tool(tool, args, meta={"caller": caller})
        text = "".join(getattr(c, "text", "") for c in res.content)
        if res.is_error:
            return {"error": "tool_execution_failed", "details": text[:500]}
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            return {"error": "tool_bad_response", "details": text[:200]}
        return out if isinstance(out, dict) else {"result": out}

    def call(self, tool: str, args: Dict[str, Any], caller: str) -> Dict[str, Any]:
        if self._closed:
            return {"error": "link_closed"}
        started = time.perf_counter()
        try:
            res = asyncio.run_coroutine_threadsafe(self._call(tool, args, caller), self._loop).result(self.timeout_s)
        except Exception as e:                           # hết thời gian chờ / server chết
            res = {"error": "tool_execution_failed", "details": f"{type(e).__name__}: {e}"}
        elapsed = (time.perf_counter() - started) * 1000
        self.calls[tool] += 1
        self.ms_by_tool[tool] += elapsed
        self.total_ms += elapsed
        return res


_LINKS: Dict[str, MemoryLink] = {}
_LINKS_LOCK = threading.Lock()


def shared_link(transport: str) -> MemoryLink:
    """MỘT kết nối dùng chung cho cả tiến trình theo transport (spawn server ~2–4 s nên không dựng lại cho mỗi kho)."""
    with _LINKS_LOCK:
        link = _LINKS.get(transport)
        if link is None or link._closed:
            link = _LINKS[transport] = MemoryLink(transport)
        return link


class _Shared:
    """Trạng thái dùng chung giữa các view của cùng một kho."""

    def __init__(self, link: MemoryLink, info: Dict[str, Any]):
        self.link = link
        self.store_id: str = info["store_id"]
        self.persistent: bool = bool(info.get("persistent"))
        self.available: bool = bool(info.get("available"))
        self.db_path: Optional[str] = info.get("db_path")
        self.listeners: List[Callable[[str], None]] = []
        self.closed = False


class RemoteBackend:
    """Mặt "backend" mà IdentityLinkMap cần (`available`, `load_identity_links`, `save_identity_link`) — nhưng đi qua mcp-memory (tool thấp: chỉ lõi)."""

    def __init__(self, memory: "RemoteMemoryService"):
        self._memory = memory

    @property
    def available(self) -> bool:
        return self._memory._shared.available

    @property
    def db_path(self) -> Optional[str]:
        return self._memory._shared.db_path

    def load_identity_links(self) -> Dict[str, str]:
        return self._memory._call("memory.identity_links_load")["links"]

    def save_identity_link(self, contact_hash: str, master_customer_id: str) -> bool:
        return bool(self._memory._call("memory.identity_link_save", contact_hash=contact_hash, master_id=master_customer_id)["saved"])


class RemoteMemoryService:
    """Giao diện y hệt `MemoryService`, mọi thao tác đi qua MCP tới mcp-memory (người ghi duy nhất)."""

    def __init__(self, enable_persistence: bool = True, db_path: Optional[str] = None, policy_dir: Optional[str] = None,
                 transport: str = "stdio", caller: str = "HarnessCore", link: Optional[MemoryLink] = None):
        self.caller = caller
        self._low = caller in CORE_CALLERS
        link = link or shared_link(transport)
        path = os.path.abspath(db_path or default_db_path()) if enable_persistence else None
        info = link.call("memory.open", {"enable_persistence": enable_persistence, "db_path": path, "policy_dir": policy_dir}, caller)
        self._raise_on_error(info, "memory.open", caller)
        self._shared = _Shared(link, info)

    # ------------------------------------------------------------------ view theo caller
    def as_caller(self, caller: str) -> "RemoteMemoryService":
        """View dùng chung kho nhưng khai báo tên caller khác — server kiểm quyền theo tên này."""
        view = object.__new__(RemoteMemoryService)
        view.caller, view._low, view._shared = caller, caller in CORE_CALLERS, self._shared
        return view

    @property
    def link(self) -> MemoryLink:
        return self._shared.link

    @property
    def store_id(self) -> str:
        return self._shared.store_id

    @property
    def backend(self) -> Optional[RemoteBackend]:
        return RemoteBackend(self) if self._shared.persistent else None

    # ------------------------------------------------------------------ gọi
    @staticmethod
    def _raise_on_error(res: Dict[str, Any], tool: str, caller: str) -> None:
        if res.get("error") == "forbidden":
            raise MemoryAccessDenied(f"{caller} không được phép gọi {tool}")
        if "error" in res:
            raise MemoryServerError(f"{tool}: {res['error']}: {res.get('details', '')}")

    def _call(self, tool: str, **args: Any) -> Dict[str, Any]:
        res = self._shared.link.call(tool, {"store_id": self._shared.store_id, **args}, self.caller)
        self._raise_on_error(res, tool, self.caller)
        return res

    def _brief(self, include: List[str], customer_id: str = "", on_date: Optional[str] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        return self._call("memory.get_call_brief", customer_id=customer_id, on_date=on_date, session_id=session_id, include=include)

    def _commit(self, op: Dict[str, Any]) -> Dict[str, Any]:
        return self._call("memory.commit_turn", ops=[op])["results"][0]

    # ------------------------------------------------------------------ giao dịch theo lượt
    def begin_turn(self, source: str, customer_id: str = "", call_date: Optional[str] = None, channel: Optional[str] = None) -> None:
        self._call("memory.begin_turn", source=source, customer_id=customer_id, call_date=call_date, channel=channel)

    def drain_writes(self) -> List[Dict[str, Any]]:
        """Chốt lượt: commit giao dịch DB và lấy nhật ký ghi. Lõi: `memory.drain_writes`; còn lại: `memory.commit_turn` (chỉ HarnessOrchestrator)."""
        if self._low:
            return self._call("memory.drain_writes")["writes"]
        return self._call("memory.commit_turn", finalize=True)["writes"]

    end_turn = drain_writes

    def abort_turn(self) -> None:
        self._call("memory.abort_turn")

    def close(self) -> None:
        """Đóng tham chiếu tới kho: tham chiếu cuối cùng thì server chốt giao dịch + checkpoint WAL + đóng DB."""
        if not self._shared.closed:
            self._call("memory.close")
            self._shared.closed = True                  # đặt SAU khi server đã chấp nhận (bị từ chối quyền thì kho vẫn mở)

    # ------------------------------------------------------------------ Working
    def set_working(self, session_id: str, **kwargs: Any) -> WorkingMemoryState:
        if self._low:
            return WorkingMemoryState(**self._call("memory.working_set", session_id=session_id, fields=kwargs)["state"])
        return WorkingMemoryState(**self._commit({"op": "set_working", "session_id": session_id, "fields": kwargs})["state"])

    def get_working(self, session_id: str) -> WorkingMemoryState:
        if self._low:
            return WorkingMemoryState(**self._call("memory.working_get", session_id=session_id)["state"])
        return WorkingMemoryState(**self._brief(["working"], session_id=session_id)["working"])

    # ------------------------------------------------------------------ Episodic
    def add_episode(self, customer_id: str, episode: EpisodeRecord) -> None:
        self._call("memory.episode_add" if self._low else "memory.commit_episode", customer_id=customer_id, episode=asdict(episode))

    def get_episodes(self, customer_id: str) -> List[EpisodeRecord]:
        raw = (self._call("memory.episodes_get", customer_id=customer_id) if self._low else self._brief(["episodes"], customer_id))["episodes"]
        return [EpisodeRecord(**e) for e in raw]

    def get_last_episode(self, customer_id: str) -> Optional[EpisodeRecord]:
        episodes = self.get_episodes(customer_id)
        return episodes[-1] if episodes else None

    # ------------------------------------------------------------------ Profile
    def set_profile_fact(self, customer_id: str, key: str, value: Any, session_id: str = "", ttl_days: Optional[int] = None,
                         observed_on: Optional[str] = None, source_channel: Optional[str] = None, source_turn: Optional[int] = None,
                         source_call: Optional[str] = None) -> ProfileFact:
        fields = dict(customer_id=customer_id, key=key, value=value, session_id=session_id, ttl_days=ttl_days, observed_on=observed_on,
                      source_channel=source_channel, source_turn=source_turn, source_call=source_call)
        res = self._call("memory.profile_set", **fields) if self._low else self._commit({"op": "set_fact", **fields})
        return ProfileFact(**res["fact"])

    def get_profile_facts(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Any]:
        if self._low:
            return self._call("memory.profile_get", customer_id=customer_id, on_date=on_date)["facts"]
        return self._brief(["facts"], customer_id, on_date)["facts"]

    def facts_by_channel(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        if self._low:
            return self._call("memory.facts_by_channel", customer_id=customer_id, on_date=on_date)["by_channel"]
        return self._brief(["by_channel"], customer_id, on_date)["by_channel"]

    def profile_versions(self, customer_id: str) -> Dict[str, List[ProfileFact]]:
        """Mọi phiên bản của mọi fact (tool thấp, chỉ lõi). Thành phần khác dùng `timeline`."""
        raw = self._call("memory.profile_versions", customer_id=customer_id)["versions"]
        return {key: [ProfileFact(**f) for f in facts] for key, facts in raw.items()}

    def timeline(self, customer_id: str) -> Dict[str, Any]:
        """Dòng thời gian của khách: {"episodes": [EpisodeRecord], "versions": {key: [ProfileFact]}}."""
        if self._low:
            return {"episodes": self.get_episodes(customer_id), "versions": self.profile_versions(customer_id)}
        raw = self._call("memory.timeline", customer_id=customer_id)
        return {"episodes": [EpisodeRecord(**e) for e in raw["episodes"]],
                "versions": {key: [ProfileFact(**f) for f in facts] for key, facts in raw["versions"].items()}}

    def merge_customer(self, src_id: str, dst_id: str) -> None:
        if not src_id or not dst_id or src_id == dst_id:
            return
        if self._low:
            self._call("memory.merge_customer", src_id=src_id, dst_id=dst_id)
        else:
            self._commit({"op": "merge", "src_id": src_id, "dst_id": dst_id})

    # ------------------------------------------------------------------ Xóa khách
    def register_delete_listener(self, fn: Callable[[str], None]) -> None:
        if fn not in self._shared.listeners:
            self._shared.listeners.append(fn)

    def delete_customer_data(self, customer_id: str) -> None:
        """Server (chỉ `Operator`) xóa sạch mọi tầng/bảng; trạng thái phía client (liên kết định danh trong RAM, trạng thái theo cuộc gọi) xóa qua listener."""
        self._call("memory.delete_customer", customer_id=customer_id)
        for fn in list(self._shared.listeners):
            fn(customer_id)

    # ------------------------------------------------------------------ Semantic
    last_policy_route: Optional[Dict[str, Any]] = None

    def query_policy(self, query: str, on_date: str = "2026-10-15") -> List[Dict[str, Any]]:
        res = self._call("memory.query_policy" if self._low else "memory.search", query=query, on_date=on_date)
        self.last_policy_route = res.get("route_info")
        return res["chunks"]


def create_memory_service(enable_persistence: bool = True, db_path: Optional[str] = None, policy_dir: Optional[str] = None,
                          transport: Optional[str] = None, caller: str = "HarnessCore"):
    """Dựng bộ nhớ theo transport: `local` (MemoryService trong tiến trình), `inproc` hoặc `stdio` (qua mcp-memory).
    Không truyền `transport` thì lấy `MEMORY_TRANSPORT`, mặc định `local`."""
    transport = (transport or os.environ.get("MEMORY_TRANSPORT") or "local").strip().lower()
    if transport not in TRANSPORTS:
        raise ValueError(f"MEMORY_TRANSPORT không hợp lệ: '{transport}' ({' | '.join(TRANSPORTS)})")
    if transport == "local":
        return MemoryService(policy_dir=policy_dir, db_path=db_path, enable_persistence=enable_persistence)
    return RemoteMemoryService(enable_persistence=enable_persistence, db_path=db_path, policy_dir=policy_dir, transport=transport, caller=caller)
