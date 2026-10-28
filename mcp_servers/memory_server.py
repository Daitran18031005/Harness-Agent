"""
MCP server `mcp-memory`: NƠI GHI DUY NHẤT của bộ nhớ khách hàng (Working / Episodic / Profile / Semantic KB + liên kết định danh).

Kiến trúc "một nơi ghi duy nhất": tiến trình server giữ các `MemoryService` (và thông qua đó là kết nối SQLite); orchestrator, Call Brief, UI, bộ chạy
đánh giá... chỉ là CLIENT (`src/memory/remote.py::RemoteMemoryService`) — không ai mở file DB bằng tay. Mỗi file DB có đúng MỘT `MemoryService`
trong server (nhiều client cùng đường dẫn dùng chung, đếm tham chiếu), nên không có hai tiến trình tranh nhau ghi một DB.

Hai tầng tool, phân quyền theo caller (config/mcp_permissions.json, mặc định TỪ CHỐI):
  TOOL CAO (dành cho các thành phần; mỗi tool bên trong gọi các hàm của tầng thấp):
    memory.get_call_brief   đọc ngữ cảnh khách một lần: fact còn hiệu lực, fact theo kênh, episode, working memory của phiên   (CallBriefBuilder, HarnessOrchestrator)
    memory.search           tìm chính sách (Semantic KB, lọc theo ngày hiệu lực, chỉ tài liệu public)                              (HarnessOrchestrator)
    memory.timeline         dòng thời gian của khách: episode + mọi phiên bản fact                                               (StreamlitUI, Operator)
    memory.commit_turn      ghi trong lượt (lô thao tác set_fact / set_working / merge) và/hoặc CHỐT lượt: commit giao dịch DB,
                            trả nhật ký ghi đã che PII                                                                             (HarnessOrchestrator)
    memory.commit_episode   ghi/cập nhật episode của một cuộc gọi (upsert theo session_id)                                       (HarnessOrchestrator)
    memory.delete_customer  xóa SẠCH mọi dữ liệu một khách ở mọi tầng/bảng (quyền riêng tư)                                       (Operator)
  TOOL THẤP (chỉ LÕI: HarnessCore; bộ chạy đánh giá/test thay lõi khi không có pipeline):
    memory.open · close · begin_turn · drain_writes · abort_turn · working_get · working_set · profile_set · profile_get · facts_by_channel ·
    profile_versions · episode_add · episodes_get · merge_customer · query_policy · identity_links_load · identity_link_save · admin_audit
Nhật ký kiểm toán phía server không chứa tham số (có thể chứa SĐT/địa chỉ). Tool là `async def` gọi thẳng mã đồng bộ trên MỘT vòng lặp sự kiện →
mọi lời gọi được tuần tự hóa, SQLite chỉ bị đụng từ một luồng.
Chạy riêng:  python -m mcp_servers.memory_server   (stdio)
"""
import os
import uuid
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.mcpserver import Context, MCPServer

from mcp_servers.common import Guarded, Permissions
from src.memory.episodic import EpisodeRecord
from src.memory.service import MemoryService
from src.memory.sqlite_store import default_db_path

GET_CALL_BRIEF_PARTS = ("facts", "by_channel", "episodes", "working")


class StoreRegistry:
    """Các kho bộ nhớ đang mở. Kho bền vững khóa theo đường dẫn DB (dùng chung + đếm tham chiếu = một người ghi duy nhất cho mỗi file);
    kho không bền vững (in-memory, mỗi kịch bản eval một kho) khóa theo mã ngẫu nhiên."""

    def __init__(self) -> None:
        self._stores: Dict[str, MemoryService] = {}
        self._refs: Dict[str, int] = {}

    def open(self, enable_persistence: bool, db_path: Optional[str], policy_dir: Optional[str]) -> Tuple[str, MemoryService]:
        if enable_persistence:
            path = os.path.abspath(db_path or default_db_path())
            store_id = f"db:{path}"
            if store_id not in self._stores:
                self._stores[store_id] = MemoryService(policy_dir=policy_dir, db_path=path, enable_persistence=True)
        else:
            store_id = f"mem:{uuid.uuid4().hex[:12]}"
            self._stores[store_id] = MemoryService(policy_dir=policy_dir, enable_persistence=False)
        self._refs[store_id] = self._refs.get(store_id, 0) + 1
        return store_id, self._stores[store_id]

    def get(self, store_id: str) -> MemoryService:
        if store_id not in self._stores:
            raise KeyError(f"unknown_store: {store_id}")
        return self._stores[store_id]

    def close(self, store_id: str) -> int:
        svc = self.get(store_id)
        self._refs[store_id] -= 1
        if self._refs[store_id] <= 0:
            svc.close()                     # chốt giao dịch + checkpoint WAL: chỉ copy file .db vẫn đủ dữ liệu
            del self._stores[store_id], self._refs[store_id]
            return 0
        return self._refs[store_id]

    def close_all(self) -> None:
        for store_id in list(self._stores):
            self._refs[store_id] = 1
            self.close(store_id)

    def __len__(self) -> int:
        return len(self._stores)


def build_server(permissions: Optional[Permissions] = None, registry: Optional[StoreRegistry] = None):
    registry = registry if registry is not None else StoreRegistry()
    guard = Guarded("mcp-memory", permissions or Permissions.load(), strip=False)
    server = MCPServer("mcp-memory", instructions="Bộ nhớ khách hàng 4 tầng (Working/Episodic/Profile/Semantic) — nơi ghi duy nhất. "
                                                  "Tool cao dành cho các thành phần, tool thấp chỉ cho lõi; phân quyền theo caller.")

    def run(tool: str, ctx: Context, fn, **p: Any) -> Dict[str, Any]:
        # Mỗi tool gói tham số vào MỘT dict `p` rồi mới qua Guarded.run (Guarded bỏ tham số None — với bộ nhớ, `None` là giá trị hợp lệ, vd value=None).
        return guard.run(tool, ctx, fn, p=p)

    # ------------------------------------------------------------------ thân tool: hàm thuần (p: dict) -> dict, dùng chung giữa tầng cao và tầng thấp
    def svc(p: Dict[str, Any]) -> MemoryService:
        return registry.get(p["store_id"])

    def do_profile_set(p):
        fact = svc(p).set_profile_fact(
            p["customer_id"], p["key"], p.get("value"), session_id=p.get("session_id") or "", ttl_days=p.get("ttl_days"),
            observed_on=p.get("observed_on"), source_channel=p.get("source_channel"), source_turn=p.get("source_turn"),
            source_call=p.get("source_call"))
        return {"fact": asdict(fact)}

    def do_working_set(p):
        return {"state": asdict(svc(p).set_working(p["session_id"], **p["fields"]))}

    def do_merge(p):
        svc(p).merge_customer(p["src_id"], p["dst_id"])
        return {"ok": True}

    def do_drain(p):
        return {"writes": svc(p).drain_writes()}

    def do_episode_add(p):
        svc(p).add_episode(p["customer_id"], EpisodeRecord(**p["episode"]))
        return {"ok": True}

    def do_delete(p):
        svc(p).delete_customer_data(p["customer_id"])
        return {"ok": True}

    def do_query_policy(p):
        s = svc(p)
        chunks = s.query_policy(p["query"], on_date=p.get("on_date") or "2026-10-15")
        return {"chunks": chunks, "route_info": s.last_policy_route}     # router chạy ở đây: chi phí/quyết định gửi kèm để client tính vào trần

    def do_versions(p):
        return {"versions": {k: [asdict(f) for f in fs] for k, fs in svc(p).profile_versions(p["customer_id"]).items()}}

    def do_episodes(p):
        return {"episodes": [asdict(e) for e in svc(p).get_episodes(p["customer_id"])]}

    # ================================================================== TOOL CAO
    @server.tool(name="memory.get_call_brief")
    async def memory_get_call_brief(ctx: Context, store_id: str, customer_id: str = "", on_date: Optional[str] = None,
                                    session_id: Optional[str] = None, include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Ngữ cảnh khách trong MỘT lời gọi: `facts` (còn hiệu lực theo `on_date`), `by_channel`, `episodes`, `working` (cần `session_id`).
        `include` chọn phần cần (mặc định: facts, by_channel, episodes)."""
        def go(p):
            parts = p["include"] or ["facts", "by_channel", "episodes"]
            unknown = [x for x in parts if x not in GET_CALL_BRIEF_PARTS]
            if unknown:
                raise ValueError(f"include không hợp lệ: {unknown}")
            s, cid, out = svc(p), p["customer_id"], {}
            if "facts" in parts:
                out["facts"] = s.get_profile_facts(cid, on_date=p["on_date"])
            if "by_channel" in parts:
                out["by_channel"] = s.facts_by_channel(cid, on_date=p["on_date"])
            if "episodes" in parts:
                out["episodes"] = [asdict(e) for e in s.get_episodes(cid)]
            if "working" in parts:
                if not p["session_id"]:
                    raise ValueError("include 'working' cần session_id")
                out["working"] = asdict(s.get_working(p["session_id"]))
            return out
        return run("memory.get_call_brief", ctx, go, store_id=store_id, customer_id=customer_id, on_date=on_date, session_id=session_id, include=include)

    @server.tool(name="memory.search")
    async def memory_search(ctx: Context, store_id: str, query: str, on_date: str = "2026-10-15") -> Dict[str, Any]:
        """Tìm chính sách (Semantic KB; lọc theo ngày hiệu lực, chỉ tài liệu public)."""
        return run("memory.search", ctx, do_query_policy, store_id=store_id, query=query, on_date=on_date)

    @server.tool(name="memory.timeline")
    async def memory_timeline(ctx: Context, store_id: str, customer_id: str) -> Dict[str, Any]:
        """Dòng thời gian của khách: các episode (theo ngày gọi) + mọi phiên bản của mọi fact (kể cả đã bị thay thế)."""
        return run("memory.timeline", ctx, lambda p: {**do_episodes(p), **do_versions(p)}, store_id=store_id, customer_id=customer_id)

    @server.tool(name="memory.commit_turn")
    async def memory_commit_turn(ctx: Context, store_id: str, ops: Optional[List[Dict[str, Any]]] = None, finalize: bool = False) -> Dict[str, Any]:
        """Ghi trong lượt và/hoặc chốt lượt. `ops` là lô thao tác áp NGAY theo thứ tự (đọc thấy ngay): {"op":"set_fact", customer_id, key, value, ...} ·
        {"op":"set_working", session_id, fields} · {"op":"merge", src_id, dst_id}. `finalize=True`: commit giao dịch DB của lượt và trả `writes`
        (nhật ký ghi đã che PII → trace.memory_writes)."""
        def go(p):
            results = []
            for op in p["ops"] or []:
                kind, body = op.get("op"), {"store_id": p["store_id"], **op}
                if kind == "set_fact":
                    results.append(do_profile_set(body))
                elif kind == "set_working":
                    results.append(do_working_set(body))
                elif kind == "merge":
                    results.append(do_merge(body))
                else:
                    raise ValueError(f"op không hợp lệ: {kind!r}")
            out: Dict[str, Any] = {"results": results}
            if p["finalize"]:
                out.update(do_drain(p))
            return out
        return run("memory.commit_turn", ctx, go, store_id=store_id, ops=ops, finalize=finalize)

    @server.tool(name="memory.commit_episode")
    async def memory_commit_episode(ctx: Context, store_id: str, customer_id: str, episode: Dict[str, Any]) -> Dict[str, Any]:
        """Ghi/cập nhật episode của một cuộc gọi (upsert theo session_id)."""
        return run("memory.commit_episode", ctx, do_episode_add, store_id=store_id, customer_id=customer_id, episode=episode)

    @server.tool(name="memory.delete_customer")
    async def memory_delete_customer(ctx: Context, store_id: str, customer_id: str) -> Dict[str, Any]:
        """Xóa SẠCH mọi dữ liệu một khách ở mọi tầng/bảng (profile kể cả lịch sử phiên bản, episode, working, liên kết định danh) — chỉ Operator."""
        return run("memory.delete_customer", ctx, do_delete, store_id=store_id, customer_id=customer_id)

    # ================================================================== TOOL THẤP (chỉ lõi)
    @server.tool(name="memory.open")
    async def memory_open(ctx: Context, enable_persistence: bool = True, db_path: Optional[str] = None, policy_dir: Optional[str] = None) -> Dict[str, Any]:
        """Mở (hoặc nối vào) một kho bộ nhớ; trả `store_id` dùng cho mọi tool khác."""
        def go(p):
            store_id, s = registry.open(p["enable_persistence"], p["db_path"], p["policy_dir"])
            backend = s.backend
            return {"store_id": store_id, "persistent": backend is not None, "available": bool(backend and backend.available),
                    "db_path": getattr(backend, "db_path", None)}
        return run("memory.open", ctx, go, enable_persistence=enable_persistence, db_path=db_path, policy_dir=policy_dir)

    @server.tool(name="memory.close")
    async def memory_close(ctx: Context, store_id: str) -> Dict[str, Any]:
        """Đóng một tham chiếu tới kho (tham chiếu cuối cùng: chốt giao dịch + checkpoint WAL + đóng DB)."""
        return run("memory.close", ctx, lambda p: {"remaining_refs": registry.close(p["store_id"])}, store_id=store_id)

    @server.tool(name="memory.begin_turn")
    async def memory_begin_turn(ctx: Context, store_id: str, source: str, customer_id: str = "", call_date: Optional[str] = None,
                                channel: Optional[str] = None) -> Dict[str, Any]:
        """Bắt đầu một lượt: đặt nguồn ghi/provenance và mở giao dịch DB của lượt."""
        def go(p):
            svc(p).begin_turn(p["source"], customer_id=p["customer_id"], call_date=p["call_date"], channel=p["channel"])
            return {"ok": True}
        return run("memory.begin_turn", ctx, go, store_id=store_id, source=source, customer_id=customer_id, call_date=call_date, channel=channel)

    @server.tool(name="memory.drain_writes")
    async def memory_drain_writes(ctx: Context, store_id: str) -> Dict[str, Any]:
        """Lấy nhật ký ghi của lượt (đã che PII) và CHỐT giao dịch DB của lượt (bản tầng thấp của memory.commit_turn)."""
        return run("memory.drain_writes", ctx, do_drain, store_id=store_id)

    @server.tool(name="memory.abort_turn")
    async def memory_abort_turn(ctx: Context, store_id: str) -> Dict[str, Any]:
        """Lượt lỗi: hủy các ghi DB của lượt."""
        def go(p):
            svc(p).abort_turn()
            return {"ok": True}
        return run("memory.abort_turn", ctx, go, store_id=store_id)

    @server.tool(name="memory.working_get")
    async def memory_working_get(ctx: Context, store_id: str, session_id: str) -> Dict[str, Any]:
        """Working memory của phiên (tạo mới nếu chưa có)."""
        return run("memory.working_get", ctx, lambda p: {"state": asdict(svc(p).get_working(p["session_id"]))}, store_id=store_id, session_id=session_id)

    @server.tool(name="memory.working_set")
    async def memory_working_set(ctx: Context, store_id: str, session_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Cập nhật trạng thái phiên (GHI). Tên trường lạ là lỗi."""
        return run("memory.working_set", ctx, do_working_set, store_id=store_id, session_id=session_id, fields=fields)

    @server.tool(name="memory.profile_set")
    async def memory_profile_set(ctx: Context, store_id: str, customer_id: str, key: str, value: Any = None, session_id: str = "",
                                 ttl_days: Optional[int] = None, observed_on: Optional[str] = None, source_channel: Optional[str] = None,
                                 source_turn: Optional[int] = None, source_call: Optional[str] = None) -> Dict[str, Any]:
        """Ghi fact vào Profile (GHI): supersede, TTL, provenance lấy từ ngữ cảnh lượt nếu không truyền."""
        return run("memory.profile_set", ctx, do_profile_set, store_id=store_id, customer_id=customer_id, key=key, value=value, session_id=session_id,
                   ttl_days=ttl_days, observed_on=observed_on, source_channel=source_channel, source_turn=source_turn, source_call=source_call)

    @server.tool(name="memory.profile_get")
    async def memory_profile_get(ctx: Context, store_id: str, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Any]:
        """Fact còn hiệu lực (áp TTL theo `on_date` nếu có)."""
        return run("memory.profile_get", ctx, lambda p: {"facts": svc(p).get_profile_facts(p["customer_id"], on_date=p["on_date"])},
                   store_id=store_id, customer_id=customer_id, on_date=on_date)

    @server.tool(name="memory.facts_by_channel")
    async def memory_facts_by_channel(ctx: Context, store_id: str, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Any]:
        """Dữ liệu khách theo từng nền tảng (kênh → {key: value})."""
        return run("memory.facts_by_channel", ctx, lambda p: {"by_channel": svc(p).facts_by_channel(p["customer_id"], on_date=p["on_date"])},
                   store_id=store_id, customer_id=customer_id, on_date=on_date)

    @server.tool(name="memory.profile_versions")
    async def memory_profile_versions(ctx: Context, store_id: str, customer_id: str) -> Dict[str, Any]:
        """Mọi phiên bản của mọi fact (kể cả đã bị thay thế)."""
        return run("memory.profile_versions", ctx, do_versions, store_id=store_id, customer_id=customer_id)

    @server.tool(name="memory.episode_add")
    async def memory_episode_add(ctx: Context, store_id: str, customer_id: str, episode: Dict[str, Any]) -> Dict[str, Any]:
        """Ghi/cập nhật episode của một cuộc gọi (GHI; upsert theo session_id) — bản tầng thấp của memory.commit_episode."""
        return run("memory.episode_add", ctx, do_episode_add, store_id=store_id, customer_id=customer_id, episode=episode)

    @server.tool(name="memory.episodes_get")
    async def memory_episodes_get(ctx: Context, store_id: str, customer_id: str) -> Dict[str, Any]:
        """Các episode của khách, sắp theo ngày gọi."""
        return run("memory.episodes_get", ctx, do_episodes, store_id=store_id, customer_id=customer_id)

    @server.tool(name="memory.merge_customer")
    async def memory_merge_customer(ctx: Context, store_id: str, src_id: str, dst_id: str) -> Dict[str, Any]:
        """Gộp hồ sơ mã khách tạm vào mã chính (GHI)."""
        return run("memory.merge_customer", ctx, do_merge, store_id=store_id, src_id=src_id, dst_id=dst_id)

    @server.tool(name="memory.query_policy")
    async def memory_query_policy(ctx: Context, store_id: str, query: str, on_date: str = "2026-10-15") -> Dict[str, Any]:
        """Tìm chính sách — bản tầng thấp của memory.search."""
        return run("memory.query_policy", ctx, do_query_policy, store_id=store_id, query=query, on_date=on_date)

    @server.tool(name="memory.identity_links_load")
    async def memory_identity_links_load(ctx: Context, store_id: str) -> Dict[str, Any]:
        """Bảng liên kết contact_hash → master_customer_id đã lưu."""
        def go(p):
            backend = svc(p).backend
            return {"links": backend.load_identity_links() if backend is not None and backend.available else {}}
        return run("memory.identity_links_load", ctx, go, store_id=store_id)

    @server.tool(name="memory.identity_link_save")
    async def memory_identity_link_save(ctx: Context, store_id: str, contact_hash: str, master_id: str) -> Dict[str, Any]:
        """Lưu một liên kết định danh (GHI; contact_hash là băm có salt, không phải SĐT thô)."""
        def go(p):
            backend = svc(p).backend
            return {"saved": bool(backend is not None and backend.available and backend.save_identity_link(p["contact_hash"], p["master_id"]))}
        return run("memory.identity_link_save", ctx, go, store_id=store_id, contact_hash=contact_hash, master_id=master_id)

    @server.tool(name="memory.admin_audit")
    async def memory_admin_audit(ctx: Context) -> Dict[str, Any]:
        """(Chỉ bộ chạy đánh giá/test) nhật ký kiểm toán phía server (không chứa tham số) + số kho đang mở."""
        return guard.run("memory.admin_audit", ctx, lambda: {"audit": list(guard.audit), "open_stores": sorted(registry._stores), "pid": os.getpid()})

    return server, guard, registry


if __name__ == "__main__":
    _server, _guard, _registry = build_server()
    try:
        _server.run("stdio")
    finally:
        _registry.close_all()                   # tiến trình server kết thúc: chốt mọi giao dịch + checkpoint WAL
