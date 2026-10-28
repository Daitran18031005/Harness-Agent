"""
ClarificationPolicy — chính sách hỏi lại bằng if/else (không LLM): CHỌN câu hỏi tiếp theo đáng hỏi nhất và CHẶN câu hỏi lặp.

  - slot đã biết (từ bộ nhớ / Call Brief / lời khách trong cuộc gọi) → không hỏi mở (chỉ được xác nhận một lần);
  - slot đã hỏi mở trong cuộc gọi này → không hỏi lại;
  - slot thuộc `must_not_ask` → không hỏi;
  - chọn tối đa `max_questions` (mặc định 1) slot phân biệt tốt nhất theo `question_priority`, bỏ qua slot không làm đổi kết quả.
`rewrite_repeated_questions` ĐỔI câu hỏi mở lặp về slot đã biết thành câu XÁC NHẬN ("Phòng nhà mình vẫn khoảng 25m² đúng không ạ?")
thay vì gỡ bỏ; mỗi slot chỉ xác nhận MỘT lần trong cuộc gọi (lần lặp tiếp theo mới gỡ câu đó). Slot chưa biết giá trị (chỉ bị hỏi ở lượt
trước, khách chưa trả lời) thì giữ nguyên — không có gì để xác nhận. `strip_repeated_questions` (gỡ hẳn) còn lại cho trường hợp
cần gỡ. Câu hỏi về `blocker` ("chị đã trao đổi với gia đình chưa ạ?") là hỏi TIẾP tình trạng nên luôn được phép.
"""
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .slot_schema import RuleSet


class ClarificationPolicy:
    ALWAYS_ALLOWED = {"blocker"}

    def __init__(self, rules: RuleSet, max_questions: int = 1):
        self.rules = rules
        self.max_questions = max_questions

    @staticmethod
    def forbidden_slots(known: Iterable[str], asked: Iterable[str], must_not_ask: Iterable[str]) -> Set[str]:
        return (set(known) | set(asked) | set(must_not_ask)) - ClarificationPolicy.ALWAYS_ALLOWED

    def next_questions(self, missing_slots: List[Dict[str, Any]], known: Iterable[str], asked: Iterable[str],
                       must_not_ask: Iterable[str]) -> List[Dict[str, Any]]:
        """`missing_slots`: đầu ra `ShortlistResult.missing_slots` (đã xếp theo mức đáng hỏi)."""
        banned = self.forbidden_slots(known, asked, must_not_ask)
        picked = [m for m in missing_slots if m["slot"] not in banned and m.get("question")]
        return picked[: self.max_questions]

    def strip_repeated_questions(self, text: str, questions: List[Dict[str, Any]], banned: Set[str]) -> Tuple[str, List[Dict[str, Any]]]:
        """Gỡ các câu hỏi MỞ về slot trong `banned` khỏi `text`. Trả (văn bản mới, các câu đã gỡ).
        Nếu gỡ xong không còn nội dung thì giữ nguyên văn bản gốc (không để agent im lặng)."""
        removed = [q for q in questions if q.get("type") == "open" and q.get("slot") in banned and q.get("slot") not in self.ALWAYS_ALLOWED]
        if not removed:
            return text, []
        new = text
        for q in removed:
            qt = q.get("text", "").strip()
            if qt and qt in new:
                new = new.replace(qt, " ", 1)
        new = re.sub(r"\s{2,}", " ", new).strip(" ,;")
        if len(re.sub(r"[\W_]+", "", new)) < 8:       # gần như không còn gì để nói
            return text, []
        return new, removed


    # ------------------------------------------------------------------ xác nhận thay vì hỏi lặp
    _COLOR_ACCENT = {"den": "đen", "trang": "trắng", "xam": "xám", "do": "đỏ", "nau": "nâu", "hong": "hồng", "vang": "vàng", "tim": "tím"}

    @classmethod
    def format_value(cls, slot: str, value: Any) -> str:
        if slot == "budget_vnd" and isinstance(value, (int, float)):
            return f"{int(value):,}đ".replace(",", ".")
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if slot == "color":
            return cls._COLOR_ACCENT.get(str(value), str(value))
        return str(value)

    def confirm_question(self, slot: str, value: Any, display: Optional[Callable[[str, Any], str]] = None) -> Optional[str]:
        """Câu xác nhận cho (slot, giá trị đã biết); None nếu chưa có mẫu cho slot này."""
        tpl = self.rules.confirm_templates.get(slot)
        if tpl is None or value in (None, ""):
            return None
        if isinstance(tpl, dict):
            flag = value if isinstance(value, bool) else str(value).strip().lower() in ("true", "có", "co", "1")
            return tpl.get("true" if flag else "false")
        shown = display(slot, value) if display else None
        return tpl.format(value=shown or self.format_value(slot, value))

    def rewrite_repeated_questions(self, text: str, questions: List[Dict[str, Any]], banned: Set[str], known_values: Dict[str, Any],
                                   confirmed_before: Set[str], display: Optional[Callable[[str, Any], str]] = None
                                   ) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Trả (văn bản mới, các câu đã đổi thành xác nhận, các câu bị gỡ vì đã xác nhận rồi, các câu giữ nguyên + lý do)."""
        new = text
        rewritten: List[Dict[str, Any]] = []
        dropped: List[Dict[str, Any]] = []
        kept: List[Dict[str, Any]] = []
        confirmed_now: Set[str] = set()
        for q in questions:
            slot, qt = q.get("slot"), (q.get("text") or "").strip()
            if q.get("type") != "open" or slot not in banned or slot in self.ALWAYS_ALLOWED or not qt or qt not in new:
                continue
            if slot in confirmed_before or slot in confirmed_now:
                trial = re.sub(r"\s{2,}", " ", new.replace(qt, " ", 1)).strip(" ,;")
                if len(re.sub(r"[\W_]+", "", trial)) >= 8:         # còn nội dung khác để nói thì mới gỡ
                    new = trial
                    dropped.append({"slot": slot, "text": qt, "why": "đã xác nhận slot này trong cuộc gọi"})
                else:
                    kept.append({"slot": slot, "text": qt, "why": "gỡ sẽ làm trả lời rỗng"})
                continue
            value = known_values.get(slot)
            confirm = self.confirm_question(slot, value, display) if value not in (None, "") else None
            if not confirm:
                kept.append({"slot": slot, "text": qt, "why": "chưa biết giá trị để xác nhận" if value in (None, "") else "chưa có mẫu xác nhận"})
                continue
            new = new.replace(qt, confirm, 1)
            confirmed_now.add(slot)
            rewritten.append({"slot": slot, "from": qt, "to": confirm})
        return new, rewritten, dropped, kept
