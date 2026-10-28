"""Kiểm xem một fact khách PHẢI nói có thực sự nằm trong lời khách không — bộ kiểm riêng cho các khóa của khung kịch bản mẫu
(bổ sung cho `validate.fact_in_text`, vốn chỉ biết các khóa của `facts_established`)."""
import re
from typing import Any

from src.dataset.validate import fact_in_text
from src.harness.fact_usage import fold

CUES = {
    "blocker_resolved": ["dong y", "ok roi", "dong y roi", "cho phep", "chap nhan", "bao duoc", "dong y cho"],
    "medical_question": ["tac tia sua", "viem vu", "chua", "benh", "bac si", "dieu tri"],
    "order_query": ["don"],
    "complaint_late_delivery": ["chua nhan", "tre", "chua thay", "chua giao", "qua han"],
}


def fact_present(key: str, value: Any, text: str) -> bool:
    f = fold(text)
    if key in CUES:
        return any(c in f for c in CUES[key])
    if key == "address":
        head = fold(str(value)).split(",")[0]
        street = re.split(r"\b(?:duong|pho)\b", head)[-1].strip()
        return bool(street) and street in f
    if key == "product_asked":
        from src.channels.asr_entities import product_mentions
        from src.dataset.spoken import normalize_liters
        return any(s == value or s.startswith(str(value)) for _, s, _ in product_mentions(normalize_liters(text)))
    if key == "recipient_name":
        return fold(str(value)) in f
    if key == "size_new":
        v = str(value).strip().lower()
        return bool(re.search(rf"\b{int(v)}\b", f)) if v.isdigit() else bool(re.search(rf"(?:size|sz|co)\s*{re.escape(v)}\b", f))
    if key == "quantity" and str(value).isdigit():
        words = {2: "hai", 3: "ba", 4: "bon", 5: "nam"}
        n = int(value)
        return (bool(re.search(rf"\b(?:{n}|{words.get(n, n)})\s*(?:may|cai|chiec|con|bo|doi|cuon|hop|san pham)\b", f))
                or bool(re.search(rf"mua\s+(?:{n}|{words.get(n, n)})\b", f)))
    return fact_in_text(key, value, text)
