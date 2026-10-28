"""
`spoken_form(text)` — "ITN ngược": đổi văn bản VIẾT (số, tiền, ngày, SĐT, mã đơn, tên hãng, bỏ dấu câu) thành văn bản ĐỌC THÀNH LỜI,
đúng quy ước của `asr/ground_truth.json` của BTC (số bằng chữ, tên hãng đọc theo tiếng Việt, không dấu câu, chữ thường).
Đây vừa là văn bản đưa vào TTS, vừa là transcript chuẩn để đo WER. Sinh BẰNG CODE (không để LLM tự đọc số) và có test hai chiều
`ITN(spoken_form(x))` trả lại đúng các số trong `x` (xem tests/test_dataset_spoken.py).

Bảng đọc tên hãng/mẫu là cách đọc do nhóm tự đoán (D01–D04 đã đối chiếu: "e pia x", "ka rô phi chín lõi", "run lai hai pro"); chưa nghe thử TTS.
"""
import re
from typing import List

_DIGIT = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _two(n: int, full: bool) -> str:
    """0..99. `full`=True: đọc cả khi có chữ số hàng chục = 0 (dùng sau 'trăm' → 'lẻ')."""
    if n < 10:
        return _DIGIT[n]
    t, u = divmod(n, 10)
    if t == 1:
        head = "mười"
    else:
        head = _DIGIT[t] + " mươi"
    if u == 0:
        return head
    if u == 1 and t > 1:
        tail = "mốt"
    elif u == 5:
        tail = "lăm"
    else:
        tail = _DIGIT[u]
    return f"{head} {tail}"


def _group(n: int, leading: bool) -> str:
    """Đọc một nhóm 3 chữ số (0..999). Nhóm không đứng đầu mà hàng trăm = 0 thì đọc 'không trăm'."""
    h, rest = divmod(n, 100)
    parts: List[str] = []
    if h > 0:
        parts.append(f"{_DIGIT[h]} trăm")
    elif not leading and rest > 0:
        parts.append("không trăm")
    if rest > 0:
        if rest < 10 and (h > 0 or not leading):
            parts.append("lẻ " + _DIGIT[rest])
        else:
            parts.append(_two(rest, h > 0))
    return " ".join(parts)


def number_to_words(n: int) -> str:
    if n == 0:
        return "không"
    if n < 0:
        return "âm " + number_to_words(-n)
    units = ["", "nghìn", "triệu", "tỷ"]
    groups: List[int] = []
    while n > 0:
        n, g = divmod(n, 1000)
        groups.append(g)
    out: List[str] = []
    for idx in range(len(groups) - 1, -1, -1):
        g = groups[idx]
        if g == 0:
            continue
        leading = idx == len(groups) - 1
        words = _group(g, leading)
        out.append(words + (" " + units[idx] if units[idx] else ""))
    return " ".join(out)


def digits_to_words(digits: str) -> str:
    return " ".join(_DIGIT[int(c)] for c in digits)


_MONTH = {i: number_to_words(i) for i in range(1, 13)}

# Cách đọc tên hãng/mẫu (thay SAU khi đã đổi số thành chữ; so khớp không phân biệt hoa thường)
BRAND_READINGS = [
    (r"lock\s*&\s*lock", "lốc en lốc"), (r"airpure", "e pia"), (r"runlite", "run lai"), (r"xiaomi", "xiao mi"), (r"samsung", "sam sung"),
    (r"karofi", "ka rô phi"), (r"kangaroo", "căng gu ru"), (r"sunhouse", "san hao"), (r"panasonic", "pa na so nic"), (r"senko", "sen cô"),
    (r"philips", "phi líp"), (r"spectra", "xpec tra"), (r"medela", "me đê la"), (r"joie", "giô i"), (r"combi", "côm bi"),
    (r"pigeon", "pi giần"), (r"chicco", "chi cô"), (r"urban classic", "ơ bần cla xích"), (r"hikepro", "hai cơ pro"),
    (r"windbreak", "uynd brếch"), (r"warmly", "quôm li"), (r"moaz bebe", "mô áz be bê"), (r"fatz", "phát"), (r"sunmum", "san mum"),
]
OTHER_READINGS = [
    (r"\bbtc\b", "bê tê xê"), (r"\bcod\b", "cê ô đê"), (r"\bsđt\b", "số điện thoại"), (r"\bapp\b", "áp"), (r"\bwifi\b|\bwi-fi\b", "quai phai"),
    (r"\bhepa\b|\bhepa h13\b", "hếp pa"), (r"\bmi home\b", "mi hôm"), (r"\buv\b", "u vê"),
    (r"\bmini\b", "mi ni"), (r"\bpro\b", "pro"), (r"\bax\s*(\d+)\b", None),   # AX40 xử lý riêng
    (r"\bpm2[.,]5\b", "pi em hai phẩy năm"),
]

LETTER_NAMES = {"a": "ây", "b": "bi", "c": "xi", "d": "đi", "e": "i", "f": "ép", "g": "gi", "h": "ết", "i": "ai", "j": "giây", "k": "kê", "l": "eo",
                "m": "em", "n": "en", "o": "ô", "p": "pi", "q": "kiu", "r": "a", "s": "ét", "t": "ti", "u": "diu", "v": "vi", "w": "đắp liu",
                "x": "ích", "y": "quai", "z": "đét"}
_CODE = re.compile(r"(?<!\w)([A-Za-z]{1,3})(\d{1,4})(?!\w)")       # mã model chữ+số: S1, TS16, AX40, H13


def _code_words(m) -> str:
    letters = " ".join(LETTER_NAMES[c] for c in m.group(1).lower())
    return f"{letters} {number_to_words(int(m.group(2)))}"


_ORDER = re.compile(r"\bOD(\d{4,9})\b")
_PHONE = re.compile(r"(?<!\d)(0\d{9})(?!\d)")
_DATE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?:/(\d{4}))?(?!\d)")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_AREA = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2|mét vuông)", re.I)
_MONEY = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d{4,})\s*(?:đ|đồng|vnđ|vnd)?(?![\d])", re.I)
_K = re.compile(r"(?<![\d.,])(\d{1,4})\s*k\b", re.I)
_TRIEU = re.compile(r"(?<![\d.,])(\d+)(?:[.,](\d+))?\s*(?:triệu|tr)\b(?:\s*(\d{1,3})\b(?!\s*(?:m|%|ngày|tháng|giờ|năm|cm|kg|lít|người|tuổi|lõi|phút)))?", re.I)
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_LITER = re.compile(r"(?<![\w.,])(\d+)(?:[.,](\d+))?\s*(?:[lL](?!\w)|lít)")                # dung tích trong tên hàng: 4.5L, 6.2L, 4L
_DECIMAL = re.compile(r"(?<![\d.,])(\d+),(\d{1,2})(?![\d.,])")
_INT = re.compile(r"(?<!\d)(?<!\d[.,])\d+(?!\d)(?![.,]\d)")


def _money_words(raw: str) -> str:
    return number_to_words(int(re.sub(r"[.,]", "", raw)))


def normalize_liters(text: str) -> str:
    """"Xiaomi 4.5L" → "Xiaomi 4.5 lít" (dạng alias trong config/product_aliases.json) — để bộ kiểm nhận ra tên sản phẩm có dung tích."""
    return _LITER.sub(lambda m: f"{m.group(1)}{'.' + m.group(2) if m.group(2) else ''} lít", text or "")


def _liter_words(m) -> str:
    out = number_to_words(int(m.group(1)))
    if m.group(2):
        out += " phẩy " + (digits_to_words(m.group(2)) if m.group(2).startswith("0") else number_to_words(int(m.group(2))))
    return out + " lít"


def spoken_form(text: str) -> str:
    t = text or ""
    t = _CODE.sub(lambda m: m.group(0) if m.group(1).upper() == "OD" else _code_words(m), t)      # AX40 → "ây ích bốn mươi", S1 → "ét một", TS16 → "ti ét mười sáu"
    # Mã đơn đọc TỪNG CHỮ SỐ ("ô đê sáu không không không không một"): đọc như một con số ("sáu trăm nghìn không trăm lẻ một") bị ITN của
    # normalizer hiểu sai ("lẻ một" → 100) — lỗi đã ghi ở CHECKING; đọc từng chữ số vừa tự nhiên vừa trích lại được bằng _ORDER_DIGITWORDS.
    t = _ORDER.sub(lambda m: "ô đê " + digits_to_words(m.group(1)), t)
    t = _PHONE.sub(lambda m: digits_to_words(m.group(1)), t)
    t = _ISO.sub(lambda m: f"ngày {number_to_words(int(m.group(3)))} tháng {_MONTH.get(int(m.group(2)), number_to_words(int(m.group(2))))}", t)
    t = _DATE.sub(lambda m: f"{number_to_words(int(m.group(1)))} tháng {_MONTH.get(int(m.group(2)), number_to_words(int(m.group(2))))}"
                  + (f" năm {number_to_words(int(m.group(3)))}" if m.group(3) else ""), t)
    t = _AREA.sub(lambda m: (number_to_words(int(float(m.group(1).replace(",", ".")))) if float(m.group(1).replace(",", ".")).is_integer()
                             else m.group(1).replace(",", " phẩy ").replace(".", " phẩy ")) + " mét vuông", t)
    t = _PERCENT.sub(lambda m: number_to_words(int(float(m.group(1).replace(",", ".")))) + " phần trăm", t)
    t = _LITER.sub(_liter_words, t)

    def trieu(m):
        whole, frac, tail = m.group(1), m.group(2), m.group(3)
        out = number_to_words(int(whole)) + " triệu"
        if frac:                                    # 2,5 triệu → hai triệu năm trăm nghìn
            out += " " + number_to_words(int((frac + "00")[:3])) + " nghìn"
        elif tail:                                  # 5tr2 → năm triệu hai trăm nghìn
            out += " " + number_to_words(int(tail) * (100 if len(tail) == 1 else 1)) + " nghìn"
        return out
    t = _TRIEU.sub(trieu, t)
    t = _K.sub(lambda m: number_to_words(int(m.group(1)) * 1000), t)          # 249k = 249.000; 4590k = 4.590.000
    t = _MONEY.sub(lambda m: _money_words(m.group(1)), t)
    t = _DECIMAL.sub(lambda m: number_to_words(int(m.group(1))) + " phẩy " + (digits_to_words(m.group(2)) if m.group(2).startswith("0") else number_to_words(int(m.group(2)))), t)
    t = _INT.sub(lambda m: number_to_words(int(m.group(0))), t)
    low = t.lower()
    for pat, rep in BRAND_READINGS:
        low = re.sub(pat, rep, low)
    for pat, rep in OTHER_READINGS:
        if rep:
            low = re.sub(pat, rep, low)
    low = re.sub(r"[^\w\s]", " ", low)
    return re.sub(r"\s+", " ", low).strip()
