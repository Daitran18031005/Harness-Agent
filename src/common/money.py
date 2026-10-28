"""
Trích số tiền từ văn bản tiếng Việt (dùng cho guardrail đối chiếu lời LLM với kết quả tool, và cho bộ
trích claims ở bước 10). Chỉ nhận số CÓ DẤU HIỆU là tiền: có dấu chấm/phẩy nghìn (5.200.000), có đơn vị
(triệu/tr/nghìn/k/đ/đồng/vnd). Số trần như "7 ngày", "24 tháng", mã đơn OD600003 không bị tính.
"""
import re
from typing import Any, List, Set, Tuple

_CUR = r"(?:đ|đồng|vnđ|vnd|₫)"
_A = re.compile(rf"(?<![\d.,])(\d{{1,3}}(?:[.,]\d{{3}})+)(?!\d)\s*(?:{_CUR}\b)?", re.I)
_B = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)(?![^\W\d_])(?:\s*(\d{1,3})\b(?!\s*(?:m|%|ngày|tháng|giờ|năm|cm|kg|lít|người)))?", re.I)
_C = re.compile(r"(?<![\d.,])(\d+)\s*(?:nghìn|ngàn|k)\b", re.I)
_D = re.compile(rf"(?<![\d.,])(\d{{4,}})\s*{_CUR}(?!\w)", re.I)
_APPROX = re.compile(r"(?:khoảng|tầm|gần|xấp xỉ|hơn|trên|dưới|ngót)\s*$", re.I)


def extract_amounts(text: str) -> List[Tuple[int, bool]]:
    """Trả về [(giá trị VND, là số ước chừng?)]. Ước chừng = có 'khoảng/tầm/gần...' ngay trước."""
    if not isinstance(text, str) or not text:
        return []
    found: List[Tuple[int, int, int, bool]] = []  # (start, end, value, approx)

    def add(m: "re.Match", value: int):
        for s, e, _, _ in found:
            if m.start() < e and s < m.end():
                return
        approx = bool(_APPROX.search(text[max(0, m.start() - 14):m.start()]))
        found.append((m.start(), m.end(), value, approx))

    for m in _D.finditer(text):
        add(m, int(m.group(1)))
    for m in _B.finditer(text):
        base = float(m.group(1).replace(",", "."))
        value = int(round(base * 1_000_000))
        tail = m.group(2)
        if tail:
            value += int(tail) * (100_000 if len(tail) == 1 else 1000)
        add(m, value)
    for m in _A.finditer(text):
        add(m, int(re.sub(r"[.,]", "", m.group(1))))
    for m in _C.finditer(text):
        add(m, int(m.group(1)) * 1000)
    found.sort()
    return [(v, a) for _, _, v, a in found]


def numbers_in(obj: Any, min_value: int = 1000) -> Set[int]:
    """Mọi số nguyên/thực ≥ min_value trong cấu trúc kết quả tool (kể cả số tiền nằm trong chuỗi, vd chunk chính sách)."""
    out: Set[int] = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        if abs(obj) >= min_value:
            out.add(int(round(abs(obj))))
    elif isinstance(obj, str):
        out.update(v for v, _ in extract_amounts(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= numbers_in(v, min_value)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= numbers_in(v, min_value)
    return out


def derived_numbers(values: Set[int], quantities: Set[int] = frozenset({2, 3})) -> Set[int]:
    """Tổng, hiệu và bội số theo số lượng của các số đã biết (LLM được phép tính tổng/chênh lệch từ số của tool)."""
    base = sorted(values)[:40]
    out = set(values)
    for i, a in enumerate(base):
        for q in quantities:
            out.add(a * q)
        for b in base[i + 1:]:
            out.add(a + b)
            out.add(abs(a - b))
    return out
