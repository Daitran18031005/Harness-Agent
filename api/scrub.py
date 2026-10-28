"""Che SĐT/địa chỉ/giấy tờ trước khi trả qua API. Khác trace JSONL (BTC cho phép SĐT 10 số), API trả cho trình duyệt nên KHÔNG đưa PII thô."""
import re
from typing import Any

from src.privacy.pii_vault import ADDRESS_KEYS

MASK = "***"
_SENSITIVE_KEYS = ("phone", "sdt", "email", "cccd", "stk", "account") + ADDRESS_KEYS
_DIGITS = re.compile(r"(?<!\d)\d{9,14}(?!\d)")       # SĐT 10 số, CCCD 12, STK 9–14 chữ số; mã đơn/giá tiền ngắn hơn nên không bị che


def _sensitive(key: Any) -> bool:
    return isinstance(key, str) and any(s in key.lower() for s in _SENSITIVE_KEYS)


def scrub(obj: Any, key: Any = None) -> Any:
    """Bản sao đã che. Che theo tên khóa (phone/address/...), theo dạng {"key": "<khóa nhạy cảm>", "value": ...} của fact hồ sơ, và mọi dãy 9–14 chữ số trong chuỗi."""
    if isinstance(obj, dict):
        by_fact_key = _sensitive(obj.get("key"))
        return {k: scrub(v, k) if not (by_fact_key and k == "value") else MASK for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub(v, key) for v in obj]
    if obj is None or isinstance(obj, bool):
        return obj
    if _sensitive(key):
        return MASK
    return _DIGITS.sub(MASK, obj) if isinstance(obj, str) else obj
