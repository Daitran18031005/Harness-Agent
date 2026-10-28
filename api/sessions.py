"""Kho phiên của API. Một phiên = MỘT cuộc gọi/cuộc chat của một liên hệ: API tự cấp `call_name` (call_1, call_2…) và `turn_num` (1, 2…) — sửa lỗi UI cũ
luôn gửi call_1 và đếm lượt theo số tin nhắn (cả tin của khách lẫn của agent).

shortcut: kho nằm trong RAM của tiến trình uvicorn (mất khi khởi động lại; bộ nhớ khách vẫn còn trong DB), không giới hạn số phiên/độ dài nhật ký tool — nâng lên
DB khi chạy nhiều worker (hiện PHẢI chạy MỘT worker: pipeline, khóa lượt và nhật ký tool đều ở trong tiến trình)."""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scrub import scrub

ORDER_TOOLS = ("order.create", "order.update", "schedule.callback")


@dataclass
class Session:
    session_id: str
    contact_id: str
    channel: str
    call_date: str
    call_name: str
    customer_id: Optional[str] = None
    turn_num: int = 0                        # số lượt đã xử lý xong; lượt kế tiếp là turn_num + 1
    ended: bool = False
    created_at: float = field(default_factory=time.time)
    tool_log: List[Dict[str, Any]] = field(default_factory=list)    # nhật ký tool đã che PII, của RIÊNG phiên này

    def info(self) -> Dict[str, Any]:
        return {"session_id": self.session_id, "call_name": self.call_name, "turn_num": self.turn_num, "channel": self.channel,
                "call_date": self.call_date, "customer_id": self.customer_id, "ended": self.ended}


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._calls_per_contact: Dict[str, int] = {}
        self._lock = threading.Lock()

    def create(self, contact_id: str, channel: str, call_date: str, previous_calls: int = 0) -> Session:
        """Phiên mới của `contact_id`. call_no = max(số cuộc đã mở trong tiến trình này, số cuộc trước trong bộ nhớ) + 1."""
        with self._lock:
            n = max(self._calls_per_contact.get(contact_id, 0), previous_calls) + 1
            self._calls_per_contact[contact_id] = n
            s = Session(uuid.uuid4().hex, contact_id, channel, call_date, f"call_{n}")
            self._sessions[s.session_id] = s
            return s

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(session_id)

    def active_for(self, contact_id: str) -> Optional[Session]:
        with self._lock:
            return next((s for s in self._sessions.values() if s.contact_id == contact_id and not s.ended), None)


def slim_trace(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Trace rút gọn cho API: chỉ số đo + tên tool + khóa bộ nhớ đã ghi. Không có lời khách/agent, args/kết quả tool, giá trị bộ nhớ (SĐT, địa chỉ, tên…)."""
    return scrub({
        "scenario_id": rec.get("scenario_id"), "call": rec.get("call"), "turn": rec.get("turn"),
        "latency": rec.get("latency"), "call_brief_latency_ms": rec.get("call_brief_latency_ms"),
        "questions": len(rec.get("questions") or []), "claims": len(rec.get("claims") or []),
        "facts_used": rec.get("facts_used") or [],
        "tool_calls": [{"tool": c.get("tool") or c.get("name"), "error": bool((c.get("result") or {}).get("error"))} for c in rec.get("tool_calls") or []],
        "memory_writes": [{"key": w.get("key"), "op": w.get("op"), "source": w.get("source")} for w in rec.get("memory_writes") or []],
        "customer_input_mode": rec.get("customer_input_mode"), "llm_cost": rec.get("llm_cost"),
    })


def tool_entry(a: Dict[str, Any]) -> Dict[str, Any]:
    """Một dòng nhật ký tool (audit_log của cổng MCP) đã che PII."""
    return scrub({k: a.get(k) for k in ("call_id", "timestamp", "tool", "caller", "args", "result", "duration_ms")})
