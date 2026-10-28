"""
Profile Memory: Lưu các sự thật bền vững về khách hàng (Personal Facts).
- Có TTL (áp khi ĐỌC theo ngày cuộc gọi), confidence, source provenance (source_call, source_turn, source_channel).
- Xử lý khách đổi ý: fact cũ giữ lại ở trạng thái superseded (lịch sử), chỉ 1 phiên bản ACTIVE cho mỗi (khách, key).
- Ghi cùng giá trị -> không thêm phiên bản (chỉ gia hạn hiệu lực).
"""
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import itertools

_SEQ = itertools.count(1)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _stamp() -> str:
    """Dấu thời gian ghi nhận, DUY NHẤT trong process (kèm số thứ tự đơn điệu): đồng hồ Windows có độ phân giải thô nên
    2 lần ghi liên tiếp có thể trùng giờ -> trùng khóa chính (customer_id, key, observed_at) và mất 1 phiên bản lịch sử."""
    return f"{datetime.now().isoformat()}~{next(_SEQ):08d}"


@dataclass
class ProfileFact:
    key: str
    value: Any
    confidence: float = 1.0
    source_session: str = ""
    observed_at: str = field(default_factory=_stamp)
    ttl_days: Optional[int] = None
    superseded: bool = False
    superseded_by: Optional[str] = None
    # Provenance (D7): fact đến từ cuộc gọi nào, lượt nào, qua kênh nào
    source_call: str = ""
    source_turn: Optional[int] = None
    source_channel: str = ""
    observed_on: Optional[str] = None      # ngày NGHIỆP VỤ (ngày cuộc gọi), YYYY-MM-DD — trục thời gian của TTL

    def expires_on(self) -> Optional[str]:
        if self.ttl_days is None:
            return None
        base = self.observed_on or (self.observed_at or _today())[:10]
        try:
            return (datetime.strptime(base, "%Y-%m-%d") + timedelta(days=self.ttl_days)).strftime("%Y-%m-%d")
        except ValueError:
            return None

    def is_valid_on(self, on_date: Optional[str]) -> bool:
        """Còn hiệu lực tại on_date? Hết hạn khi on_date >= observed_on + ttl_days (ttl_days=0 -> hết ngay)."""
        if on_date is None:
            return True
        expiry = self.expires_on()
        return expiry is None or on_date < expiry


class ProfileMemoryStore:
    # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
    def __init__(self, backend=None):
        # customer_id -> key -> danh sách phiên bản (cũ -> mới); phiên bản active là cái cuối không superseded
        self._store: Dict[str, Dict[str, List[ProfileFact]]] = {}
        self.backend = backend
        # Callback ghi nhật ký thay đổi (MemoryService gắn vào) — nguồn của trace.memory_writes.
        self.on_write: Optional[Callable[[Dict[str, Any]], None]] = None
        if self.backend and self.backend.available:
            for cid, keys in self.backend.load_all_profiles().items():
                for key, versions in keys.items():
                    self._store.setdefault(cid, {})[key] = [
                        ProfileFact(
                            key=key, value=v["value"], confidence=v["confidence"], source_session=v["source_session"],
                            observed_at=v["observed_at"], ttl_days=v["ttl_days"], superseded=v["superseded"],
                            superseded_by=v["superseded_by"], source_call=v.get("source_call", ""),
                            source_turn=v.get("source_turn"), source_channel=v.get("source_channel", ""),
                            observed_on=v.get("observed_on")) for v in versions]

    def _current(self, customer_id: str, key: str) -> Optional[ProfileFact]:
        for fact in reversed(self._store.get(customer_id, {}).get(key, [])):
            if not fact.superseded:
                return fact
        return None

    def set_fact(self, customer_id: str, key: str, value: Any, source_session: str = "", ttl_days: Optional[int] = None,
                 confidence: float = 1.0, source_call: str = "", source_turn: Optional[int] = None,
                 source_channel: str = "", observed_on: Optional[str] = None) -> ProfileFact:
        versions = self._store.setdefault(customer_id, {}).setdefault(key, [])
        current = self._current(customer_id, key)
        observed_on = observed_on or _today()

        if current is not None and current.value == value:
            # Cùng giá trị: KHÔNG thêm phiên bản/dòng mới (D1); nếu được xác nhận lại ở ngày mới hơn thì gia hạn TTL.
            if observed_on > (current.observed_on or "") or (ttl_days is not None and ttl_days != current.ttl_days):
                current.observed_on = max(observed_on, current.observed_on or "")
                current.ttl_days = ttl_days if ttl_days is not None else current.ttl_days
                if self.backend and self.backend.available:
                    self.backend.renew_profile_fact(customer_id, key, current.observed_on, current.ttl_days)
            return current

        op = "set"
        if current is not None:
            op = "supersede"
            current.superseded = True
            current.superseded_by = str(value)

        fact = ProfileFact(
            key=key, value=value, confidence=confidence, source_session=source_session, ttl_days=ttl_days,
            source_call=source_call, source_turn=source_turn, source_channel=source_channel, observed_on=observed_on)
        versions.append(fact)
        if self.on_write:
            self.on_write({"customer_id": customer_id, "key": key, "value": value, "op": op,
                           "source_call": source_call, "source_turn": source_turn, "source_channel": source_channel})
        if self.backend and self.backend.available:
            self.backend.save_profile_version(customer_id, {
                "key": key, "value": value, "confidence": confidence, "source_session": source_session,
                "observed_at": fact.observed_at, "ttl_days": ttl_days, "source_call": source_call,
                "source_turn": source_turn, "source_channel": source_channel, "observed_on": observed_on},
                supersede_previous=(op == "supersede"))
        return fact

    def get_active_facts(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Any]:
        """Chỉ trả về fact còn hiệu lực: chưa bị superseded và (nếu có on_date) chưa hết TTL."""
        out: Dict[str, Any] = {}
        for key in self._store.get(customer_id, {}):
            fact = self._current(customer_id, key)
            if fact is not None and fact.is_valid_on(on_date):
                out[key] = fact.value
        return out

    def get_history(self, customer_id: str, key: str) -> List[ProfileFact]:
        """Mọi phiên bản của 1 fact theo thứ tự thời gian (kể cả đã bị thay thế)."""
        return list(self._store.get(customer_id, {}).get(key, []))

    def active_facts_full(self, customer_id: str, on_date: Optional[str] = None) -> List[ProfileFact]:
        """Các ProfileFact còn hiệu lực (đủ metadata: TTL, provenance) — dùng khi gộp hồ sơ giữa các mã khách."""
        facts = [self._current(customer_id, k) for k in self._store.get(customer_id, {})]
        return [f for f in facts if f is not None and f.is_valid_on(on_date)]

    def facts_by_channel(self, customer_id: str, on_date: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Dữ liệu khách theo từng nền tảng: kênh -> {key: value} của các fact còn hiệu lực, nhóm theo source_channel."""
        out: Dict[str, Dict[str, Any]] = {}
        for fact in self.active_facts_full(customer_id, on_date):
            out.setdefault(fact.source_channel or "unknown", {})[fact.key] = fact.value
        return out

    def delete_customer(self, customer_id: str):
        """Xóa toàn bộ dữ liệu 1 khách hàng theo yêu cầu (GDPR/Privacy) — kể cả lịch sử phiên bản."""
        self._store.pop(customer_id, None)
        if self.backend and self.backend.available:
            self.backend.delete_customer(customer_id)
