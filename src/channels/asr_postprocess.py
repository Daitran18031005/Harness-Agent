"""
Hậu xử lý đầu ra ASR + trích thực thể cho `asr/hypotheses.json`.

Pipeline (không tốn API): đầu ra model (Gipformer: CHỮ HOA, không dấu câu, không chữ số)
  → `to_lower_vi`            : chữ thường, giữ dấu tiếng Việt, NFC, gộp khoảng trắng
  → `RequestNormalizer`      : sửa lỗi ngữ âm ASR, ITN (số tiền/SĐT/diện tích/ngày), che CCCD/STK  (bước 7 của kế hoạch)
  → PiiVault (ở orchestrator): SĐT/địa chỉ → token  (nằm ngoài module này)

`canonical_numbers` chỉ dùng khi ĐO WER: đưa hai vế (transcript chuẩn và giả thuyết) về cùng một dạng số.
"""
import re
import unicodedata
from typing import Any, Dict, Optional

from src.channels.normalizer import (InputChannel, RequestNormalizer, itn_digit_units, itn_number_words,
                                     itn_phone_digits, _PHONE_DIGIT_WORDS, _parse_number_run, _vocab_token)
from src.common.money import extract_amounts

_NORMALIZER = RequestNormalizer()


def to_lower_vi(text: str) -> str:
    """CHỮ HOA → chữ thường (giữ dấu), NFC, gộp khoảng trắng. Model Gipformer không xuất dấu câu."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "").lower()).strip()


def canonical_numbers(text: str) -> str:
    """Dạng chuẩn để so WER công bằng giữa model ra chữ ("năm triệu") và model ra số ("5.000.000"):
    đổi số đọc bằng chữ → chữ số (ITN của dự án), bỏ dấu phân cách hàng nghìn, rồi gộp khoảng trắng."""
    t = itn_phone_digits(text or "")
    t = itn_number_words(t)
    t = itn_digit_units(t)
    t = re.sub(r"(?<=\d)[.,](?=\d{3}(?!\d))", "", t)
    return re.sub(r"\s+", " ", t).strip()


def wer_normalize(text: str) -> str:
    """Chuẩn hóa ĐÚNG như `reference_eval.wer_cer` của BTC (lowercase, NFC, `[^\\w\\s]`→khoảng trắng, gộp khoảng trắng).
    Sao chép lại để dùng trong công cụ đo của nhóm; KHÔNG sửa script của BTC."""
    t = unicodedata.normalize("NFC", (text or "").lower())
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalize_transcript(text: str, contact_id: str = "0900000000", reference_date: Optional[str] = None):
    """Giả thuyết ASR → NormalizedTurn (ITN + che PII), dùng cùng bộ chuẩn hóa như đường chat."""
    return _NORMALIZER.normalize(to_lower_vi(text), InputChannel.HOTLINE, contact_id, is_audio=True,
                                 reference_date=reference_date)


_ORDER_PREFIX = r"\b(?:o|ô)\s*(?:đê|đề|de|d)\s+"                       # "ô đê" (model hay ra "ô d")
_ORDER_DIGITWORDS = re.compile(_ORDER_PREFIX + r"((?:(?:không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s*){4,})", re.I)
_ORDER_NUMBER = re.compile(_ORDER_PREFIX + r"(\d[\d.]{3,})", re.I)                 # sau ITN: "ô d 312.456"
_ORDER_WRITTEN = re.compile(r"\bOD\s*(\d{4,})\b", re.I)
_UNITS_AFTER_SMALL = {"tháng", "ngày", "năm", "mét", "m2", "m²", "cm", "kg", "lít", "giờ", "phút", "tiếng", "tuần", "đôi", "chiếc", "cái"}
_MAG_TOKENS = {"nghìn", "ngàn", "triệu", "tỷ", "tỉ"}
_NUMERIC_KEYS = ("price_vnd", "competitor_price_vnd", "min_free_ship_vnd", "bulky_fee_vnd", "exchange_fee_vnd",
                 "delivery_days", "warranty_months", "return_days")


def spoken_small_numbers(text: str) -> str:
    """Đổi số nhỏ (< 1000) đọc bằng chữ đứng ngay trước đơn vị ("ba mươi sáu tháng", "ba năm", "hai ngày") thành chữ số, để
    trích `warranty_months/delivery_days/return_days`. CHỈ dùng khi trích thực thể từ giả thuyết (ITN chung của chat cố ý
    không đổi 'một cái', 'năm nay'). "năm" cuối cụm là ĐƠN VỊ khi đứng sau số ("ba năm" = 3 năm)."""
    words, out, i = text.split(), [], 0
    while i < len(words):
        j = i
        while j < len(words) and _vocab_token(words[j]) is not None and words[j].lower().strip(",.") not in _MAG_TOKENS:
            j += 1
        toks = [words[k].lower().strip(",.") for k in range(i, j)]
        unit_idx = None
        if j > i and j < len(words) and words[j].lower().strip(",.") in _UNITS_AFTER_SMALL:
            unit_idx = j
        elif len(toks) >= 2 and toks[-1] == "năm" and toks[-2] not in ("mươi", "mười", "trăm", "lẻ", "linh"):
            toks, j, unit_idx = toks[:-1], j - 1, j - 1
        if unit_idx is not None and toks:
            value, has_mag = _parse_number_run([_vocab_token(t) for t in toks])
            if value and value < 1000 and not has_mag:
                out.append(str(value))
                i = j
                continue
        out.append(words[i])
        i += 1
    return " ".join(out)


_AMT = r"(\d{1,3}(?:\.\d{3})+)"
_ROLE_RULES = [
    ("price_vnd", re.compile(r"\b(?:mẫu|máy|con|bản|sản phẩm|giày|đôi)\b[^,.?]{0,25}?\blà\s+" + _AMT)),
    ("competitor_price_vnd", re.compile(r"\b(?:bên kia|chỗ khác|bên khác|nơi khác|shop khác|cửa hàng khác)\b[^.?]{0,45}?" + _AMT)),
    ("min_free_ship_vnd", re.compile(r"\b(?:đơn|hóa đơn|đơn hàng)\s+(?:từ|trên)\s+" + _AMT + r"[^.?]{0,25}?\bmiễn phí\b")),
    ("bulky_fee_vnd", re.compile(r"\b(?:cồng kềnh|hàng lớn)\b[^.?]{0,45}?\b(?:phụ thu|phí|thu)\s+" + _AMT)),
]
_ROOM = re.compile(r"\bphòng\s+(?:khoảng\s+|rộng\s+|tầm\s+)?(\d{1,3})\s*(?:mét|m2|m²)\b")


def _amount(text: str) -> int:
    return int(text.replace(".", ""))


def _role_overrides(norm: str, claims: list) -> Dict[str, Any]:
    """Vai trò số tiền theo cụm từ ("mẫu x là 4.890.000", "bên kia … 5.700.000", "đơn từ 2.000.000 … miễn phí",
    "hàng cồng kềnh … phụ thu 30.000"). Với `price_vnd` chỉ ghi đè khi cụm này đứng SAU lần báo giá cuối trong văn bản."""
    out: Dict[str, Any] = {}
    last_price_pos = -1
    for c in claims:
        if c["field"] == "price_vnd":
            last_price_pos = max(last_price_pos, norm.rfind(f"{c['value']:,}".replace(",", ".")))
    for field, pat in _ROLE_RULES:
        ms = list(pat.finditer(norm))
        if not ms:
            continue
        m = ms[-1]
        if field == "price_vnd" and m.start(1) < last_price_pos:
            continue
        out[field] = _amount(m.group(1))
    return out


def extract_hypothesis_entities(text: str, call_date: Optional[str] = None) -> Dict[str, Any]:
    """Thực thể trích TỪ GIẢ THUYẾT ASR (không dùng đáp án) cho `hypotheses.json[<id>].entities`.

    Số: số tiền theo vai trò (`price_vnd`, `competitor_price_vnd`, phí…), `room_area_m2`, `budget_vnd`, `has_children`,
    `delivery_days`, `warranty_months`, `return_days`, `phone` (SĐT 10 số), `order_id` ("o đê …" / "OD…").
    Phi số (`asr_entities.py`): `sku`, `color`, `promo_expiry`, `payment`, `in_stock`, `blocker`, `size_old/size_new`.
    Còn thiếu: `objection`, `address`… (không có trong ground truth mẫu của BTC).
    """
    from src.harness.extractor import extract_claims
    from src.memory.memory_extractor import extract_easy_slots

    turn = normalize_transcript(text, reference_date=call_date)
    norm = spoken_small_numbers(turn.normalized_text)
    out: Dict[str, Any] = {}
    in_stock = None
    for claim in extract_claims(norm, None, call_date):
        if claim["field"] in _NUMERIC_KEYS:
            out[claim["field"]] = claim["value"]          # nhắc nhiều lần → LẤY LẦN CUỐI (BTC: `entities` cấp hội thoại = giá trị ghi sau cùng)
        elif claim["field"] == "in_stock":
            in_stock = claim["value"]
    claims = extract_claims(norm, None, call_date)
    roles = _role_overrides(norm, claims)
    out.update(roles)
    if roles.get("bulky_fee_vnd") is not None and out.get("exchange_fee_vnd") == roles["bulky_fee_vnd"]:
        del out["exchange_fee_vnd"]                       # "phụ thu hàng cồng kềnh" không phải phí đổi hàng
    room = list(_ROOM.finditer(norm))
    if room:
        out["room_area_m2"] = int(room[-1].group(1))
    slots = extract_easy_slots(norm, turn.extracted_entities)
    for key in ("budget_vnd", "room_area_m2", "has_children"):
        if key in slots:
            value = slots[key]
            out[key] = int(value) if isinstance(value, float) and value.is_integer() else value
    phones = [p for p in turn.extracted_entities.get("phones", []) if re.fullmatch(r"0\d{9}", p)]
    if phones:
        out["phone"] = phones[-1]
    order = None
    for pat in (_ORDER_NUMBER, _ORDER_DIGITWORDS, _ORDER_WRITTEN):
        found = list(pat.finditer(norm))
        if found:
            raw = found[-1].group(1)
            if pat is _ORDER_DIGITWORDS:
                order = "".join(_PHONE_DIGIT_WORDS[w] for w in raw.lower().split() if w in _PHONE_DIGIT_WORDS)
            else:
                order = re.sub(r"\D", "", raw)
            break
    if order:
        out["order_id"] = "OD" + order
    from src.channels.asr_entities import extract_extra_entities
    out.update(extract_extra_entities(to_lower_vi(text), call_date, in_stock))
    return out


def money_values(text: str) -> set:
    """Mọi số tiền (VND) tìm được trong văn bản đã ITN — dùng để chấm entity accuracy theo số tiền."""
    norm = normalize_transcript(text).normalized_text
    norm = _ORDER_NUMBER.sub(" ", norm)                  # mã đơn "ô d 312.456" không phải số tiền
    return {v for v, _ in extract_amounts(norm)}
