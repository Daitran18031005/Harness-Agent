"""
Working Memory: Lưu trữ ngữ cảnh trong phiên hiện tại (tuổi thọ bằng phiên hoặc ngắn hơn).
Lưu lượt hiện tại, các slot đang chờ xác nhận, tool observation gần nhất.
Khóa phiên có dạng `SESS-<customer_id>-<ngày cuộc gọi>`.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class WorkingMemoryState:
    session_id: str
    current_turn: int = 1
    intent: str = "inquire"
    pending_slots: Dict[str, Any] = field(default_factory=dict)
    waiting_for_confirmation: Optional[str] = None
    last_tool_observation: Optional[Dict[str, Any]] = None
    messages_in_session: list = field(default_factory=list)


class WorkingMemoryStore:
    # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
    def __init__(self, backend=None):
        self._store: Dict[str, WorkingMemoryState] = {}
        self.backend = backend

    def get_or_create(self, session_id: str) -> WorkingMemoryState:
        if session_id not in self._store:
            loaded = self.backend.load_working(session_id) if (self.backend and self.backend.available) else None
            self._store[session_id] = WorkingMemoryState(**loaded) if loaded else WorkingMemoryState(session_id=session_id)
        return self._store[session_id]

    def update(self, session_id: str, **kwargs):
        """Cập nhật trạng thái phiên. Tên trường lạ là lỗi lập trình -> báo ngay (trước đây bị bỏ qua âm thầm,
        vd `last_intent` không bao giờ được lưu — N5)."""
        state = self.get_or_create(session_id)
        for k, v in kwargs.items():
            if not hasattr(state, k):
                raise TypeError(f"WorkingMemoryState không có trường '{k}'")
            setattr(state, k, v)
        if self.backend and self.backend.available:
            self.backend.save_working(session_id, asdict(state))
        return state

    def clear_session(self, session_id: str):
        self._store.pop(session_id, None)

    def clear_customer(self, customer_id: str) -> int:
        """Xóa mọi phiên `SESS-<customer_id>-*` (trong RAM; DB do SQLiteStore.delete_customer lo). Trả về số phiên đã xóa."""
        prefix = f"SESS-{customer_id}-"
        doomed = [sid for sid in self._store if sid.startswith(prefix)]
        for sid in doomed:
            del self._store[sid]
        return len(doomed)
