"""
Identity Linkage Mapping: ánh xạ 2 tầng contact_hash -> master_customer_id cho khách
CHƯA có trong CRM (crm_seed.json không khớp SĐT/Zalo/FB). Thay cho UUID ngẫu nhiên mỗi
lượt (bug thật đã gặp: làm "mất trí nhớ" working/profile/episodic ngay trong 1 cuộc gọi
và cả Call Brief/Memory Timeline trên UI), mapping này đảm bảo TÍNH TẤT ĐỊNH: cùng 1
liên hệ luôn ra cùng 1 master_customer_id xuyên phiên/lượt/kênh.

Bảo mật: customer_id KHÔNG được chứa SĐT/Zalo ID thô — băm SHA-256 có salt nội bộ
(chống dò ngược qua rainbow table) trước khi dùng làm khóa hoặc đưa vào customer_id/log.
"""
import os
import hashlib
import logging
from typing import Dict, Optional

logger = logging.getLogger("harness.identity")

# Salt nội bộ — đổi được qua env nếu cần xoay salt định kỳ mà không sửa code.
_SALT = os.environ.get("IDENTITY_HASH_SALT", "telesale_salt_2026")


def hash_contact(contact_key: str) -> str:
    """Băm SHA-256 có salt cho 1 định danh liên hệ (SĐT/zalo_id/fb_id), cắt 12 ký tự hex
    cho gọn — không thể dò ngược ra giá trị gốc, không lộ PII trong customer_id/log."""
    digest = hashlib.sha256(f"{_SALT}:{contact_key}".encode("utf-8")).hexdigest()
    return f"HASH-{digest[:12]}"


class IdentityLinkMap:
    """Bảng mapping contact_hash -> master_customer_id. Persist qua SQLiteStore nếu có
    (bền vững xuyên phiên/restart); fallback in-memory dict nếu SQLite không khả dụng
    hoặc backend=None (vd eval runner chạy enable_persistence=False để hermetic từng
    scenario) — không bao giờ crash pipeline."""

    def __init__(self, backend=None):
        self.backend = backend
        self._map: Dict[str, str] = {}
        if self.backend is not None and getattr(self.backend, "available", False):
            self._map.update(self.backend.load_identity_links())

    def resolve_master_id(self, contact_key: str) -> str:
        """Trả về master_customer_id ỔN ĐỊNH cho 1 liên hệ chưa có trong CRM — cùng
        contact_key luôn trả về cùng 1 master_id (deterministic), không sinh UUID ngẫu
        nhiên mỗi lần gọi."""
        contact_hash = hash_contact(contact_key)
        if contact_hash in self._map:
            return self._map[contact_hash]

        master_id = f"CUST-ANON-{contact_hash[5:17]}"  # bỏ tiền tố "HASH-", giữ 12 hex
        self._map[contact_hash] = master_id
        if self.backend is not None and getattr(self.backend, "available", False):
            self.backend.save_identity_link(contact_hash, master_id)
        return master_id

    def forget_master(self, master_id: str) -> None:
        """Xóa mọi liên kết định danh trỏ về master_id trong RAM (xóa khách; bảng DB do SQLiteStore.delete_customer lo)."""
        for contact_hash in [h for h, m in self._map.items() if m == master_id]:
            del self._map[contact_hash]

    def link_contact(self, contact_key: str, master_id: str) -> str:
        """Gắn 1 định danh kênh (FB/Zalo id) vào master_customer_id ĐÃ BIẾT (vd mã CRM 'C017' sau khi khách
        đọc SĐT trên Fanpage): các lần resolve sau của contact_key trả về master_id này."""
        contact_hash = hash_contact(contact_key)
        self._map[contact_hash] = master_id
        if self.backend is not None and getattr(self.backend, "available", False):
            self.backend.save_identity_link(contact_hash, master_id)
        logger.info("[IDENTITY] linked contact %s -> %s", contact_hash, master_id)
        return master_id

    def link_identities(self, hash_a: str, hash_b: str) -> str:
        """Gộp 2 contact_hash (vd SĐT + Zalo ID của cùng 1 khách phát hiện được giữa 2
        kênh) về chung 1 master_customer_id — ưu tiên giữ master_id đã gán cho hash_a
        (liên hệ xuất hiện trước) nếu có, rồi gán cả 2 hash cùng trỏ về master_id đó.
        Tiện ích sẵn sàng dùng khi có tín hiệu liên kết đa kênh đáng tin cậy (vd
        crm.get_customer xác nhận cùng identities); không tự động đoán liên kết."""
        master_id = self._map.get(hash_a) or self._map.get(hash_b)
        if master_id is None:
            master_id = f"CUST-ANON-{hash_a[5:17]}"
        self._map[hash_a] = master_id
        self._map[hash_b] = master_id
        if self.backend is not None and getattr(self.backend, "available", False):
            self.backend.save_identity_link(hash_a, master_id)
            self.backend.save_identity_link(hash_b, master_id)
        logger.info("[IDENTITY] linked %s + %s -> %s", hash_a, hash_b, master_id)
        return master_id
