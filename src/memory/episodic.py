"""
Episodic Memory: Tóm tắt từng cuộc gọi/phiên đã diễn ra.
Chứa: ngày gọi, sản phẩm tư vấn, giá đã báo, blocker chưa giải quyết, outcome.
Mỗi cuộc gọi chỉ có MỘT episode (unique theo (khách, session_id)): ghi lại cùng cuộc gọi (vd lúc chuyển máy rồi
lúc kết thúc) cập nhật episode đó thay vì thêm bản trùng. Đọc theo NGÀY GỌI, không theo giờ máy.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class EpisodeRecord:
    session_id: str
    call_index: int
    call_date: str
    channel: str
    customer_goal: str
    product_advised: Optional[str] = None
    price_quoted_vnd: Optional[int] = None
    promo_code: Optional[str] = None
    promo_expiry: Optional[str] = None
    blocker: Optional[str] = None
    # chot_don, hen_goi_lai, tu_choi, khieu_nai, chuyen_may (chuyển nhân viên), ngat_cuoc (cuộc gọi bị ngắt/timeout)
    outcome: str = "hen_goi_lai"
    summary: str = ""
    created_at: str = ""


def _order_key(ep: EpisodeRecord):
    return (ep.call_date or "", ep.call_index or 0)


class EpisodicMemoryStore:
    # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
    def __init__(self, backend=None):
        # customer_id -> List[EpisodeRecord] (sắp theo call_date, call_index)
        self._store: Dict[str, List[EpisodeRecord]] = {}
        self.backend = backend
        if self.backend and self.backend.available:
            for cid, episodes in self.backend.load_all_episodes().items():
                self._store[cid] = sorted((EpisodeRecord(**ep) for ep in episodes), key=_order_key)

    def append(self, customer_id: str, episode: EpisodeRecord):
        """Upsert theo session_id."""
        episodes = self._store.setdefault(customer_id, [])
        for i, existing in enumerate(episodes):
            if existing.session_id == episode.session_id:
                episodes[i] = episode
                break
        else:
            episodes.append(episode)
        episodes.sort(key=_order_key)
        if self.backend and self.backend.available:
            self.backend.append_episode(customer_id, asdict(episode))

    def get_episodes(self, customer_id: str) -> List[EpisodeRecord]:
        return list(self._store.get(customer_id, []))

    def get_last_episode(self, customer_id: str) -> Optional[EpisodeRecord]:
        episodes = self.get_episodes(customer_id)
        return episodes[-1] if episodes else None

    def delete_customer(self, customer_id: str):
        """Xóa toàn bộ lịch sử episode của 1 khách hàng (GDPR)."""
        self._store.pop(customer_id, None)
        if self.backend and self.backend.available:
            self.backend.delete_customer(customer_id)
