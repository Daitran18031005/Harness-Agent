"""
Phát hiện một fact có được NHẮC TỚI trong một đoạn văn bản hay không — dùng cho `facts_used` (CCR) ở runtime và cho
phân tích offline, để hai nơi cho CÙNG một kết quả.

Một fact chỉ tính là "đã mang sang và dùng" (Context Carryover) khi:
  (1) agent dùng nó trong lời nói hoặc tham số tool (`fact_mentioned(agent_text + args)`), VÀ
  (2) agent CHƯA hỏi mở lại slot đó trong cuộc gọi, VÀ
  (3) khách CHƯA tự nhắc lại chính fact đó trong cuộc gọi (nếu khách đã nói lại thì agent dùng được là nhờ nghe, không phải nhờ nhớ).

So khớp KHÔNG phân biệt dấu/hoa-thường; số so theo ranh giới chữ số (không nhầm "25" trong "2025"); fact luận lý và
fact ngữ nghĩa (`blocker`, `has_children`) so theo từ khóa — trước đây `blocker` ("can hoi chong") và `has_children` (True)
không bao giờ khớp được nên không bao giờ được tính là đã dùng.
"""
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (kể cả đ/Đ)."""
    nfkd = unicodedata.normalize("NFKD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------- từ khóa theo ngữ nghĩa (trên văn bản đã fold)
CHILD_CUES = ["be nho", "tre nho", "con nho", "em be", "tre em", "tre con", "co be", "co con nho", "an toan cho be", "khoa tre em"]
FAMILY_GENERIC = ["nguoi nha", "gia dinh", "trao doi voi", "ban voi", "hoi y kien", "tham khao y kien", "hoi lai"]
_FAMILY = {
    "chong": ["chong", "ong xa", "nha toi", "anh nha"],
    "vo": [r"\bvo\b", "ba xa", "bo nha", "chi nha"],
    "bo me": ["bo me", "ba me", "phu huynh", "cha me"],
    "ban be": ["ban be", "ban chi", "ban anh"],
    "con": ["con gai", "con trai", "cac con"],
}
PRICE_COMPARE_CUES = ["so sanh", "ben kia", "noi khac", "cho khac", "re hon", "dat hon", "gia ben", "shop khac", "cua hang khac"]


def blocker_cues(value: Any) -> List[str]:
    """Từ khóa (đã fold) cho một giá trị blocker như 'can hoi chong', 'can hoi vo', 'so sanh gia'."""
    v = fold(str(value))
    cues: List[str] = []
    family_hit = False
    for token, words in _FAMILY.items():
        if re.search(rf"\b{re.escape(token)}\b", v) or any(w in v for w in ("hoi " + token,)):
            cues += words
            family_hit = True
    if family_hit or "nguoi nha" in v or "gia dinh" in v:
        cues += FAMILY_GENERIC
    if "so sanh" in v or "gia" in v.split() or "dat" in v.split():
        cues += PRICE_COMPARE_CUES
    if not cues:
        cues = [w for w in re.split(r"[^a-z0-9]+", v) if len(w) >= 4] or [v]
    return list(dict.fromkeys(cues))


def _has_cue(folded_text: str, cues: Iterable[str]) -> bool:
    for c in cues:
        if c.startswith("\\b") or "\\" in c:
            if re.search(c, folded_text):
                return True
        elif c in folded_text:
            return True
    return False


def _number_in(folded_text: str, n: float, near: Optional[str] = None) -> bool:
    """n xuất hiện như một số nguyên độc lập (không dính chữ số khác hoặc dấu nghìn); `near`: regex bắt buộc xuất hiện ngay sau/trước."""
    digits = str(int(n)) if float(n).is_integer() else str(n)
    forms = {digits}
    if float(n).is_integer() and abs(n) >= 1000:
        forms.add(f"{int(n):,}".replace(",", "."))
    for f in forms:
        pat = rf"(?<![\d.,]){re.escape(f)}(?![\d]|[.,]\d)"
        for m in re.finditer(pat, folded_text):
            if near is None:
                return True
            window = folded_text[max(0, m.start() - 14): m.end() + 14]
            if re.search(near, window):
                return True
    return False


def fact_mentioned(key: str, value: Any, text: str, names: Optional[Dict[str, str]] = None) -> bool:
    """`value` của slot `key` có được nhắc tới trong `text` không (chưa tính chuyện ai nói)."""
    if value is None or not text:
        return False
    ft = fold(text)
    if key == "blocker":
        return _has_cue(ft, blocker_cues(value))
    if key == "has_children":
        return bool(value) and _has_cue(ft, CHILD_CUES)
    if key == "room_area_m2" and isinstance(value, (int, float)):
        return _number_in(ft, value, near=r"m2|m²|met vuong|phong|dien tich")
    if key == "size":
        sz = re.escape(fold(str(value)))
        return bool(re.search(rf"(?:size|sz)\s*{sz}(?![\d.,]*\d)", ft))
    if key == "color":
        c = fold(str(value))
        return bool(re.search(rf"(?<![a-z]){re.escape(c)}(?![a-z])", ft))
    if key == "product_advised":
        s = fold(str(value))
        forms = {s, s.replace("sku-", "")}
        if names and names.get(str(value)):
            forms.add(fold(names[str(value)]))
        return any(f and f in ft for f in forms)
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return _number_in(ft, value)
    s = fold(str(value))
    return bool(s) and s in ft


def used_by_agent(key: str, value: Any, agent_text: str, tool_args: Iterable[Dict[str, Any]],
                  names: Optional[Dict[str, str]] = None) -> bool:
    import json
    haystack = (agent_text or "") + " " + json.dumps(list(tool_args), ensure_ascii=False)
    return fact_mentioned(key, value, haystack, names)
