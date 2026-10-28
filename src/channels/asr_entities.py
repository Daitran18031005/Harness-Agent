"""
Trích các thực thể KHÔNG phải số tiền từ giả thuyết ASR cho `hypotheses.json[<id>].entities`, theo ĐÚNG định dạng giá trị của
ground truth BTC (`asr/ground_truth.json`, đối chiếu thêm `facts_established` của 7 kịch bản public):

    sku            SKU cha trong catalog, vd "SKU-AP-Y", "SKU-WF-RO9", "SKU-SN-RUN2"
    color          không dấu, vd "den"
    promo_expiry   ISO "2026-10-22"
    payment        "COD" | "bank" | "momo" | "zalopay"   (tools.schema.json)
    in_stock       true/false
    blocker        "can hoi chong" | "can hoi vo" | "so sanh gia" (không dấu, cách nhau bằng khoảng trắng)
    size_old / size_new   số nguyên

Nhắc nhiều lần → LẤY LẦN CUỐI (BTC: `entities` cấp hội thoại là giá trị ghi sau cùng). Mọi hàm chỉ đọc giả thuyết, KHÔNG dùng đáp án.

Giới hạn trung thực: bảng cách đọc tên sản phẩm (`config/product_aliases.json`) và các cụm "size" được viết dựa trên cách BTC viết
ground truth và các biến thể ASR quan sát trên D01–D04 → số đo trên 4 file đó là TRONG-TẬP (in-sample), không phải khái quát hóa.
"""
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from src.channels.normalizer import _parse_number_run, _vocab_token

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ALIAS_PATH = os.path.join(CODE_DIR, "config", "product_aliases.json")
_MAG = {"nghìn", "ngàn", "triệu", "tỷ", "tỉ"}


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> List[str]:
    return re.sub(r"[^\w\s&]", " ", (text or "").lower()).split()


def _number_at(tokens: List[str], i: int) -> Tuple[Optional[int], int]:
    """Số (chữ số hoặc số đọc bằng chữ, không có bậc nghìn/triệu) bắt đầu ở tokens[i] → (giá trị, chỉ số sau cụm)."""
    if i >= len(tokens):
        return None, i
    if tokens[i].isdigit():
        return int(tokens[i]), i + 1
    j = i
    while j < len(tokens) and _vocab_token(tokens[j]) is not None and tokens[j] not in _MAG:
        j += 1
    if j == i:
        return None, i
    value, has_mag = _parse_number_run([_vocab_token(t) for t in tokens[i:j]])
    return (value, j) if value and not has_mag else (None, i)


# ------------------------------------------------------------------------------------------------ sku
@lru_cache(maxsize=1)
def _alias_table() -> List[Tuple[str, str]]:
    """[(alias đã fold & bỏ khoảng trắng, sku)] sinh từ config/product_aliases.json (brand × model + alone)."""
    with open(ALIAS_PATH, encoding="utf-8") as fh:
        products = json.load(fh)["products"]
    table: List[Tuple[str, str]] = []
    for sku, spec in products.items():
        for b in spec.get("brand", []):
            for m in spec.get("model", [""]):
                table.append((fold(b + m).replace(" ", ""), sku))
        for a in spec.get("alone", []):
            table.append((fold(a).replace(" ", ""), sku))
    return [(a, s) for a, s in dict.fromkeys(table) if a]


_LETTER_MODEL = {"x": "SKU-AP-X", "ix": "SKU-AP-X", "it": "SKU-AP-X", "ich": "SKU-AP-X", "y": "SKU-AP-Y", "i": "SKU-AP-Y", "quai": "SKU-AP-Y"}


def product_mentions(text: str) -> List[Tuple[int, str, float]]:
    """[(vị trí token đầu, sku, điểm)] theo thứ tự xuất hiện. Khớp mờ trên cửa sổ 1–4 từ đã fold; alias ≤ 6 ký tự phải khớp tuyệt đối (khớp mờ trên chuỗi ngắn gây nhận nhầm, vd "chị chờ" ~ "chicco")."""
    toks = [fold(t) for t in _tokens(text)]
    table = _alias_table()
    cands: List[Tuple[float, int, int, str]] = []          # (điểm, số từ, vị trí, sku)
    for i in range(len(toks)):
        for n in range(1, 8):
            if i + n > len(toks):
                break
            w = "".join(toks[i:i + n])
            if len(w) < 2:
                continue
            for alias, sku in table:
                if len(alias) <= 6:
                    score = 1.0 if w == alias else 0.0
                else:
                    if abs(len(w) - len(alias)) > 2:
                        continue
                    score = SequenceMatcher(None, w, alias).ratio()
                    if score < 0.84:
                        continue
                if score:
                    cands.append((score, n, i, sku))
    cands.sort(key=lambda c: (-c[0], -c[1], c[2]))
    taken = [False] * len(toks)
    chosen: List[Tuple[int, str, float]] = []
    for score, n, i, sku in cands:
        if any(taken[i:i + n]):
            continue
        for k in range(i, i + n):
            taken[k] = True
        chosen.append((i, sku, score))
    chosen.sort()
    # "mẫu x" / "mẫu ít": chữ cái đứng một mình sau "mẫu" → anh em cùng họ AirPure với sản phẩm vừa nhắc
    out: List[Tuple[int, str, float]] = list(chosen)
    for i, t in enumerate(toks[:-1]):
        if t == "mau" and toks[i + 1] in _LETTER_MODEL and not taken[i + 1]:
            if any(s.startswith("SKU-AP-") and p < i for p, s, _ in chosen):
                out.append((i + 1, _LETTER_MODEL[toks[i + 1]], 0.5))
    return sorted(out)


# ------------------------------------------------------------------------------------------------ các trường khác
_COLORS = {"den", "trang", "xam", "xanh", "do", "nau", "be", "hong", "vang", "cam", "tim", "kem", "bac", "ghi", "navy"}
_PAY = [(r"\b(?:ce o de|c o d|co ?d|k ?o ?d|ko ?d|thanh toan khi nhan|tra tien khi nhan|giao hang thu tien|ship cod)\b", "COD"),
        (r"\b(?:chuyen khoan|banking|ck truoc|chuyen tien)\b", "bank"),
        (r"\bmomo\b", "momo"), (r"\bzalo ?pay\b", "zalopay")]
_FAMILY_BLOCKER = [(r"\bhoi (?:ong xa|chong|anh nha|nha toi|ong nha)\b", "can hoi chong"),
                   (r"\bhoi (?:ba xa|vo|co nha|ba nha)\b", "can hoi vo"),
                   (r"\bhoi (?:gia dinh|nguoi nha|bo me|ba me|cha me)\b", "can hoi gia dinh")]
_COMPARE = re.compile(r"\b(?:so sanh gia|ben kia|cho khac|ben khac|noi khac|shop khac|dat hon|re hon|thay re hon)\b")
_SIZE_WORD = {"size", "sizer", "saier", "sizes", "cỡ", "co"}
_SIZE_SOUND = re.compile(r"^(?:sai|saier|sizer|size)$")


def _last(pairs):
    return pairs[-1][1] if pairs else None


def extract_color(text: str) -> Optional[str]:
    toks = [fold(t) for t in _tokens(text)]
    found = [(i, toks[i + 1]) for i in range(len(toks) - 1) if toks[i] == "mau" and toks[i + 1] in _COLORS]
    return _last(found)


def extract_payment(text: str) -> Optional[str]:
    f = fold(text)
    found = []
    for pat, val in _PAY:
        for m in re.finditer(pat, f):
            found.append((m.start(), val))
    return _last(sorted(found))


def extract_blocker(text: str) -> Optional[str]:
    f = fold(text)
    found = []
    for pat, val in _FAMILY_BLOCKER:
        for m in re.finditer(pat, f):
            found.append((m.start(), val))
    for m in _COMPARE.finditer(f):
        found.append((m.start(), "so sanh gia"))
    return _last(sorted(found))


def extract_promo_expiry(text: str, call_date: Optional[str]) -> Optional[str]:
    """"... đến hết ngày hai mươi hai tháng mười" → 2026-10-22 (năm lấy theo ngày gọi; ngày đã qua → năm sau)."""
    from src.harness.extractor import _iso_date
    toks = _tokens(text)
    out = None
    for i, t in enumerate(toks):
        if t != "ngày":
            continue
        day, j = _number_at(toks, i + 1)
        if day is None or not (1 <= day <= 31) or j >= len(toks) or toks[j] != "tháng":
            continue
        month, _ = _number_at(toks, j + 1)
        if month is None or not (1 <= month <= 12):
            continue
        if not any(c in toks[max(0, i - 6):i] for c in ("hết", "đến", "tới", "hạn", "thúc")):
            continue
        out = _iso_date(day, month, None, call_date) or out
    return out


def extract_sizes(text: str) -> Dict[str, int]:
    """size_new: số sau "đổi lên/sang/qua/thành"; size_old: số đứng sau chữ "size" (kể cả cách ASR nghe: "sai rơ", "sizer")
    mà khác size_new, lấy lần đầu."""
    toks = _tokens(text)
    sizes: List[int] = []
    new: Optional[int] = None
    for i, t in enumerate(toks):
        is_size = fold(t) in {"size", "sizer", "saier", "sizes"} or (fold(t) == "sai" and i + 1 < len(toks) and fold(toks[i + 1]) in {"ro", "zo", "z", "do"})
        if is_size:
            k = i + (2 if fold(t) == "sai" else 1)
            v, _ = _number_at(toks, k)
            if v and 30 <= v <= 50:
                sizes.append(v)
        if t == "đổi" and i + 1 < len(toks) and toks[i + 1] in ("lên", "sang", "qua", "thành", "xuống"):
            k = i + 2
            if k < len(toks) and fold(toks[k]) in {"size", "sizer", "saier", "sai"}:
                k += 2 if fold(toks[k]) == "sai" else 1
            v, _ = _number_at(toks, k)
            if v and 30 <= v <= 50:
                new = v
    out: Dict[str, int] = {}
    if new is not None:
        out["size_new"] = new
    olds = [s for s in sizes if s != new]
    if olds:
        out["size_old"] = olds[0]
    return out


def extract_extra_entities(text: str, call_date: Optional[str] = None, in_stock: Optional[bool] = None) -> Dict[str, Any]:
    """Gộp các thực thể phi số. `in_stock` do caller lấy từ `extract_claims` (đã có luật tồn kho)."""
    out: Dict[str, Any] = {}
    mentions = product_mentions(text)
    if mentions:
        out["sku"] = mentions[-1][1]
    for key, val in (("color", extract_color(text)), ("payment", extract_payment(text)), ("blocker", extract_blocker(text)),
                     ("promo_expiry", extract_promo_expiry(text, call_date))):
        if val:
            out[key] = val
    out.update(extract_sizes(text))
    if in_stock is not None:
        out["in_stock"] = in_stock
    return out
