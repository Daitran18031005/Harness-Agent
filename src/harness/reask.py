"""
Tầng ĐẦU RA của lời gửi cho khách (không đụng LLM):
  * `strip_markdown`  — bỏ **, #, gạch đầu dòng... (lời nói/nhắn tin cho khách không có markdown; LLM hay viết danh sách ** **).
  * `rewrite_reasks`  — hỏi LẠI cùng một slot ở lượt kế tiếp khi khách chưa trả lời: lần 2 đổi cách (ghi nhận điều đã nghe + cho phép bỏ qua,
    không lặp y nguyên), lần 3 trở đi gỡ câu hỏi. Lỗi thật: sau "tôi tên Đại" agent lặp nguyên câu xin SĐT lần hai (ui_replay hội thoại B).
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

REASK_LABEL = {"phone": "số điện thoại", "customer_name": "tên", "delivery_address": "địa chỉ", "delivery_time": "thời gian", "quantity": "số lượng"}

_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")
_END = tuple(".!?:;…")


def strip_markdown(text: str) -> str:
    """Bỏ định dạng markdown. Danh sách gạch đầu dòng được nối bằng '; ' để đọc/nhắn liền mạch."""
    if not text or not re.search(r"(?m)[*_`#]|^\s*(?:-|•|\d+[.)])\s", text):
        return text
    lines: List[str] = []
    in_list = False
    for raw in text.replace("\r", "").split("\n"):
        line = _HEADING.sub("", raw)
        is_item = bool(_BULLET.match(line))
        line = _BULLET.sub("", line).strip()
        if not line:
            if lines and in_list and not lines[-1].endswith(_END):
                lines[-1] += "."
            in_list = False
            continue
        if is_item and in_list and lines:
            lines[-1] = lines[-1].rstrip(";.") + "; " + line
        else:
            if lines and in_list and not lines[-1].endswith(_END):
                lines[-1] += "."
            lines.append(line)
        in_list = is_item
    if lines and in_list and not lines[-1].endswith(_END):
        lines[-1] += "."
    out = " ".join(lines)
    out = re.sub(r"(\*\*|__)(.+?)\1", r"\2", out)
    out = re.sub(r"(?<![\w*])\*(\S[^*]*?)\*(?![\w*])", r"\1", out)
    out = out.replace("`", "")
    return re.sub(r"\s{2,}", " ", out).strip()


def rewrite_reasks(text: str, questions: List[Dict[str, Any]], counts: Dict[str, int], answered: Set[str],
                   heard_name: Optional[str], addressing: str) -> Tuple[str, Dict[str, int], List[Dict[str, Any]]]:
    """`counts[slot]` = số lượt LIÊN TIẾP agent đã hỏi mở slot đó mà khách chưa trả lời. Trả (văn bản mới, counts mới, sự kiện)."""
    new, events = text, []
    before = {k: v for k, v in counts.items() if k not in answered}
    after: Dict[str, int] = {}
    for q in questions:
        slot, qt = q.get("slot"), (q.get("text") or "").strip()
        if q.get("type") != "open" or slot not in REASK_LABEL or not qt or qt not in new:
            continue
        n = before.get(slot, 0)
        after[slot] = n + 1
        if n == 0:
            continue
        label = REASK_LABEL[slot]
        ack = f"Dạ em đã ghi nhận tên {heard_name}. " if heard_name and slot != "customer_name" else ""
        if n == 1:
            soft = f"{ack}Nếu {addressing} chưa tiện cho em {label} thì không sao, em vẫn hỗ trợ {addressing} bình thường ạ."
            new = new.replace(qt, soft, 1)
            events.append({"slot": slot, "action": "rephrased", "from": qt, "to": soft})
        else:
            trial = re.sub(r"\s{2,}", " ", new.replace(qt, " ", 1)).strip(" ,;")
            if len(re.sub(r"[\W_]+", "", trial)) >= 8:
                new = trial
                events.append({"slot": slot, "action": "dropped", "from": qt})
            else:
                events.append({"slot": slot, "action": "kept_only_content", "from": qt})
    return new, after, events
