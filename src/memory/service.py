"""
Memory Service: Gateway quản lý thống nhất 4 vùng nhớ chuyên biệt:
1. Working Memory
2. Episodic Memory
3. Profile Memory
4. Semantic / KB Memory
Cung cấp interface chuẩn: read, write, supersede, delete, provenance tracking.
"""
import os
import re
import glob
from typing import Dict, Any, List, Optional, Callable
from .working import WorkingMemoryStore, WorkingMemoryState
from .episodic import EpisodicMemoryStore, EpisodeRecord
from .profile import ProfileMemoryStore, ProfileFact
from .semantic_rag import SemanticKBStore, PolicyChunk
from .sqlite_store import SQLiteStore, default_db_path
from .policy_loader import load_policy_chunks


class MemoryService:
    # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
    def __init__(self, policy_dir: Optional[str] = None, db_path: Optional[str] = None,
                 enable_persistence: bool = True):
        # db_path=None -> đường dẫn TUYỆT ĐỐI mặc định (không phụ thuộc thư mục hiện hành, D14)
        backend = SQLiteStore(db_path or default_db_path()) if enable_persistence else None
        # Expose để các thành phần khác (IdentityResolver) dùng chung 1 SQLiteStore cho
        # identity_links — tránh mỗi nơi tự mở 1 connection riêng tới cùng file DB.
        self.backend = backend
        self.working = WorkingMemoryStore(backend=backend)
        self.episodic = EpisodicMemoryStore(backend=backend)
        self.profile = ProfileMemoryStore(backend=backend)
        self.semantic = SemanticKBStore()
        self._load_default_policies(policy_dir)
        # Nhật ký ghi bộ nhớ theo lượt -> trace.memory_writes (B8). begin_turn() đặt nguồn
        # "call_1#turn3"; drain_writes() lấy và xóa các thay đổi đã ghi kể từ lần trước.
        self._writes: List[Dict[str, Any]] = []
        self._write_source = ""
        # Ngữ cảnh provenance của lượt hiện tại (set bởi begin_turn): fact ghi trong lượt tự mang theo
        # source_call / source_turn / source_channel / observed_on (ngày cuộc gọi).
        self._ctx: Dict[str, Any] = {"source_call": "", "source_turn": None, "source_channel": "", "observed_on": None}
        self._delete_listeners: List[Callable[[str], None]] = []
        self.profile.on_write = self._log_write

    def _load_default_policies(self, policy_dir: Optional[str]):
        # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
        # Nạp 99 chunk chính sách thật từ BTC-Data-Vong1-TEAMS/policy/*.md.
        # Fallback về 3 chunk mẫu nếu không tìm/đọc được thư mục policy.
        try:
            chunks = load_policy_chunks(policy_dir)
            if not chunks:
                raise FileNotFoundError("no chunks parsed")
            for c in chunks:
                self.semantic.add_chunk(c)
            return
        except Exception as e:
            import logging
            logging.getLogger("harness.memory").warning(
                "[RAG] policy_dir not found/unreadable (%s) — falling back to 3 built-in sample chunks.", e
            )

        self.semantic.add_chunk(PolicyChunk(
            chunk_id="[DT-03]",
            doc_name="chinh-sach-doi-tra.md",
            content="Đổi size lần 1 miễn phí trong 7 ngày, đổi lần 2 trở đi phụ thu 60.000đ.",
            version="v2026-10",
            effective_from="2026-07-01",
            effective_to="2027-12-31",
            access="public"
        ))
        self.semantic.add_chunk(PolicyChunk(
            chunk_id="[BH-01]",
            doc_name="chinh-sach-bao-hanh.md",
            content="Bảo hành máy lọc không khí chính hãng 24 tháng tận nhà tại Hà Nội và TP.HCM.",
            version="v2026-10",
            effective_from="2026-01-01",
            effective_to="2027-12-31",
            access="public"
        ))
        self.semantic.add_chunk(PolicyChunk(
            chunk_id="[NOI-BO-01]",
            doc_name="ghi-chu-nhap-hang-NOI-BO.md",
            content="Giá nhập kho AirPure X là 3.200.000đ, không được để lộ giá nhập.",
            version="v2026-10",
            effective_from="2026-01-01",
            effective_to="2027-12-31",
            access="internal"
        ))

    # --- Nhật ký ghi (memory_writes) ---
    # PII phải mask trước khi vào trace: chuỗi 9–14 chữ số (CCCD/STK) bị che; SĐT 10 số bắt đầu 0 được phép.
    _PII_DIGITS = re.compile(r"(?<!\d)(?!0\d{9}(?!\d))\d{9,14}(?!\d)")

    def begin_turn(self, source: str, customer_id: str = "", call_date: Optional[str] = None,
                   channel: Optional[str] = None) -> None:
        """Bắt đầu 1 lượt: đặt nguồn ghi ('call_2#turn1'), ngữ cảnh provenance (cuộc gọi, lượt, kênh, ngày cuộc gọi)
        và mở GIAO DỊCH DB cho lượt (commit khi drain_writes()/end_turn()). Lượt trước chưa đóng thì được chốt."""
        self._write_source = source
        self._writes = []
        m = re.match(r"^(.+?)#(?:turn(\d+)|end|handoff|timeout)$", source or "")
        call, turn = (m.group(1), int(m.group(2)) if m.group(2) else None) if m else (source or "", None)
        self._ctx = {"source_call": call, "source_turn": turn, "source_channel": channel or "", "observed_on": call_date}
        if self.backend is not None:
            self.backend.begin_turn()

    _MASKED_KEYS = frozenset({"shipping_address", "recipient_phone"})      # PII: lưu trong DB (xóa được bằng delete_customer) nhưng KHÔNG vào trace

    def _log_write(self, entry: Dict[str, Any]) -> None:
        value = entry.get("value")
        if entry.get("key") in self._MASKED_KEYS and value is not None:
            value = "[đã bảo mật]"
        elif isinstance(value, str):
            value = self._PII_DIGITS.sub("[REDACTED]", value)
        self._writes.append({**entry, "value": value, "source": self._write_source})

    def drain_writes(self) -> List[Dict[str, Any]]:
        """Lấy (và xóa) nhật ký ghi của lượt, đồng thời CHỐT giao dịch DB của lượt."""
        out, self._writes = self._writes, []
        if self.backend is not None:
            self.backend.commit_turn()
        return out

    end_turn = drain_writes

    def abort_turn(self) -> None:
        """Lượt lỗi: hủy các ghi trong DB của lượt. (Bản in-memory không tự hoàn tác — chấp nhận ở M1.)"""
        self._writes = []
        if self.backend is not None:
            self.backend.rollback_turn()

    def close(self) -> None:
        """Chốt giao dịch + checkpoint WAL + đóng DB (chỉ cần copy file .db vẫn đủ dữ liệu)."""
        if self.backend is not None:
            self.backend.close()

    # --- Working Memory Interface ---
    def set_working(self, session_id: str, **kwargs) -> WorkingMemoryState:
        return self.working.update(session_id, **kwargs)

    def get_working(self, session_id: str) -> WorkingMemoryState:
        return self.working.get_or_create(session_id)

    # --- Episodic Memory Interface ---
    def add_episode(self, customer_id: str, episode: EpisodeRecord):
        """Upsert theo session_id (mỗi cuộc gọi 1 episode)."""
        self.episodic.append(customer_id, episode)
        self._log_write({"customer_id": customer_id, "key": f"episode:{episode.session_id}", "op": "set",
                         "value": f"{episode.outcome}; sản phẩm={episode.product_advised}; giá={episode.price_quoted_vnd}; blocker={episode.blocker}",
                         "source_call": self._ctx["source_call"], "source_turn": self._ctx["source_turn"],
                         "source_channel": self._ctx["source_channel"] or episode.channel})

    def get_episodes(self, customer_id: str) -> List[EpisodeRecord]:
        return self.episodic.get_episodes(customer_id)

    def get_last_episode(self, customer_id: str) -> Optional[EpisodeRecord]:
        return self.episodic.get_last_episode(customer_id)

    # --- Profile Memory Interface ---
    def set_profile_fact(self, customer_id: str, key: str, value: Any, session_id: str = "",
                         ttl_days: Optional[int] = None, observed_on: Optional[str] = None,
                         source_channel: Optional[str] = None, source_turn: Optional[int] = None,
                         source_call: Optional[str] = None) -> ProfileFact:
        """Ghi fact kèm provenance (call/turn/channel lấy từ ngữ cảnh begin_turn nếu không truyền)."""
        c = self._ctx
        return self.profile.set_fact(
            customer_id, key, value, source_session=session_id, ttl_days=ttl_days,
            source_call=source_call if source_call is not None else c["source_call"],
            source_turn=source_turn if source_turn is not None else c["source_turn"],
            source_channel=source_channel if source_channel is not None else c["source_channel"],
            observed_on=observed_on or c["observed_on"])

    def get_profile_facts(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Any]:
        """Fact còn hiệu lực. Truyền on_date (ngày cuộc gọi) để áp TTL; không truyền thì không lọc theo TTL."""
        return self.profile.get_active_facts(customer_id, on_date=on_date)

    def facts_by_channel(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        return self.profile.facts_by_channel(customer_id, on_date=on_date)

    def profile_versions(self, customer_id: str) -> Dict[str, List[ProfileFact]]:
        """Mọi phiên bản của mọi fact (kể cả đã bị thay thế), nhóm theo key — cho dòng thời gian trên UI."""
        return {key: self.profile.get_history(customer_id, key) for key in self.profile._store.get(customer_id, {})}

    def timeline(self, customer_id: str) -> Dict[str, Any]:
        """Dòng thời gian của khách: {"episodes": [EpisodeRecord], "versions": {key: [ProfileFact]}} (cùng giao diện RemoteMemoryService.timeline)."""
        return {"episodes": self.get_episodes(customer_id), "versions": self.profile_versions(customer_id)}

    def as_caller(self, caller: str) -> "MemoryService":
        """Cùng giao diện với `RemoteMemoryService.as_caller`: bản cục bộ không có phân quyền nên trả lại chính nó."""
        return self

    def merge_customer(self, src_id: str, dst_id: str) -> None:
        """Gộp hồ sơ của mã khách tạm (vd khách ẩn danh trên Fanpage) vào mã chính (vd C017 sau khi biết SĐT):
        fact (giữ nguyên provenance, TTL) và episode của src chuyển sang dst (fact đã có ở dst thì dst thắng),
        rồi xóa src — một khách một mã."""
        if not src_id or not dst_id or src_id == dst_id:
            return
        existing = self.get_profile_facts(dst_id)
        for fact in self.profile.active_facts_full(src_id):
            if fact.key not in existing:
                self.profile.set_fact(dst_id, fact.key, fact.value, source_session=fact.source_session,
                                      ttl_days=fact.ttl_days, confidence=fact.confidence, source_call=fact.source_call,
                                      source_turn=fact.source_turn, source_channel=fact.source_channel,
                                      observed_on=fact.observed_on)
        for ep in list(self.get_episodes(src_id)):
            self.add_episode(dst_id, ep)
        self.profile.delete_customer(src_id)
        self.episodic.delete_customer(src_id)

    # --- Xóa khách (D9, N11) ---
    def register_delete_listener(self, fn: Callable[[str], None]) -> None:
        """Các thành phần giữ trạng thái riêng về khách (bảng liên kết định danh, trạng thái theo cuộc gọi của
        orchestrator...) đăng ký để được xóa cùng khi xóa khách."""
        if fn not in self._delete_listeners:
            self._delete_listeners.append(fn)

    def delete_customer_data(self, customer_id: str):
        """Xóa SẠCH mọi dữ liệu 1 khách ở mọi tầng/bảng: profile (kể cả lịch sử phiên bản), episode, working session
        (nguyên văn hội thoại), identity link, và trạng thái của các thành phần đã đăng ký."""
        self.profile.delete_customer(customer_id)
        self.episodic.delete_customer(customer_id)
        self.working.clear_customer(customer_id)
        if self.backend is not None:
            self.backend.delete_customer(customer_id)
        for fn in list(self._delete_listeners):
            fn(customer_id)

    # --- Semantic / KB Interface ---
    last_policy_route: Optional[Dict[str, Any]] = None      # {route, usage} của lần query_policy gần nhất: router chạy phía bộ nhớ nên chi phí phải đi theo kết quả

    def query_policy(self, query: str, on_date: str = "2026-10-15") -> List[Dict[str, Any]]:
        chunks = self.semantic.search(query, on_date=on_date, access_level="public")
        self.last_policy_route = {"route": self.semantic.last_route, "usage": list(self.semantic.last_usage)}
        return chunks
