"""
Normalizer Module: Tiếp nhận và chuẩn hóa đầu vào đa kênh
- Hỗ trợ Hotline, Fanpage, Zalo, Web chat
- ASR repair, Teencode normalization (theo ngữ cảnh, không thay tuyệt đối các chữ cái đơn)
- Inverse Text Normalization (ITN) TỔNG QUÁT: số tiền đọc bằng chữ (triệu/nghìn/trăm/mươi/lẻ/rưỡi), 5tr/249k,
  số điện thoại đọc từng chữ số, ngày giờ tương đối ("ngày mai", "3 giờ chiều")
- PII: CCCD / số tài khoản được thay bằng token <ID_n> NGAY trong normalized_text (không bao giờ mở lại).
  SĐT giữ nguyên số (cần để nhận diện khách / BTC cho phép SĐT 10 số); việc che SĐT/địa chỉ trước khi đưa cho LLM
  do PiiVault (src/privacy/pii_vault.py) đảm nhiệm.
"""
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class InputChannel(Enum):
    HOTLINE = "hotline"
    FANPAGE = "fanpage"
    ZALO = "zalo"
    WEB_CHAT = "web_chat"

    @classmethod
    def from_scenario(cls, name):
        """Ánh xạ tên kênh trong kịch bản BTC (hotline / chat_fanpage / zalo_oa / web_chat);
        thiếu hoặc lạ -> HOTLINE."""
        key = (name or "hotline").strip().lower()
        if "fanpage" in key or key in ("fb", "facebook", "messenger"):
            return cls.FANPAGE
        if "zalo" in key:
            return cls.ZALO
        if "web" in key:
            return cls.WEB_CHAT
        return cls.HOTLINE


@dataclass
class NormalizedTurn:
    raw_input: str
    normalized_text: str
    channel: InputChannel
    contact_id: str  # Phone / Zalo ID / FB ID
    is_noisy_asr: bool = False
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    pii_masked_text: str = ""   # = normalized_text (CCCD/STK đã thành <ID_n>)
    llm_text: str = ""          # bản đưa cho LLM (SĐT/địa chỉ đã thành token) — do orchestrator gán qua PiiVault


# ---------------------------------------------------------------- ITN số tiếng Việt
_DIGITS = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "nhăm": 5,
           "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
_FILLERS = {"lẻ", "linh"}
_MAGS = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000, "tỷ": 1_000_000_000, "tỉ": 1_000_000_000}
_VOCAB = set(_DIGITS) | _FILLERS | set(_MAGS) | {"trăm", "mươi", "mười", "rưỡi"}
# Biến thể KHÔNG dấu chỉ nhận với từ không gây nhầm (không nhận sau/nam/tam/tu: trùng từ thường).
_ASCII = {"khong": "không", "mot": "một", "hai": "hai", "bon": "bốn", "chin": "chín", "bay": "bảy", "tram": "trăm",
          "nghin": "nghìn", "ngan": "ngàn", "trieu": "triệu", "ty": "tỷ", "muoi": "mươi", "ruoi": "rưỡi"}
_PHONE_DIGIT_WORDS = {"không": "0", "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5", "sáu": "6", "bảy": "7",
                      "tám": "8", "chín": "9", "linh": "0"}
_PUNCT = ",.?!;:"
# Danh từ đơn vị/loại từ: số đếm đứng NGAY TRƯỚC chúng là số lượng, không phải phần dư của số tiền
# ("mười triệu một đơn" = 10.000.000 + "một đơn", không phải 10.100.000).
_COUNT_NOUNS = {"đơn", "chiếc", "cái", "máy", "bộ", "đôi", "cuốn", "hộp", "túi", "bình", "chai", "lần", "người", "phòng", "gói", "bản", "món",
                "suất", "tháng", "tuần", "ngày"}
_COUNT_NOUNS_RE = "|".join(sorted(_COUNT_NOUNS, key=len, reverse=True))


def _fmt_money(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _vocab_token(tok: str) -> Optional[str]:
    core = tok.lower().strip(_PUNCT)
    if core in _VOCAB:
        return core
    return _ASCII.get(core)


def _parse_section(toks: List[str]) -> int:
    """Giá trị < 1000 từ các từ chữ số/trăm/mươi/mười/lẻ (hỗ trợ cách nói tắt 'hai trăm bốn chín' = 249)."""
    val, i, n, after_hundred = 0, 0, len(toks), False
    while i < n:
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < n else None
        if t in _DIGITS:
            d = _DIGITS[t]
            if nxt == "trăm":
                val += d * 100
                i += 2
                after_hundred = True
                continue
            if nxt == "mươi":
                tens, i = d * 10, i + 2
                if i < n and toks[i] in _DIGITS:
                    tens += _DIGITS[toks[i]]
                    i += 1
                val += tens
                after_hundred = False
                continue
            if after_hundred:  # 'hai trăm bốn' = 240; 'hai trăm bốn chín' = 249
                if nxt in _DIGITS:
                    val += d * 10 + _DIGITS[nxt]
                    i += 2
                else:
                    val += d * 10
                    i += 1
                after_hundred = False
                continue
            val += d
            i += 1
        elif t in _FILLERS:
            if nxt in _DIGITS:
                val += _DIGITS[nxt]
                i += 2
            else:
                i += 1
            after_hundred = False
        elif t == "mười":
            val += 10
            i += 1
            if i < n and toks[i] in _DIGITS:
                val += _DIGITS[toks[i]]
                i += 1
            after_hundred = False
        elif t == "trăm":
            val = (val or 1) * 100 if val < 10 else val + 100
            i += 1
        else:
            i += 1
    return val


def _parse_number_run(toks: List[str]) -> Tuple[int, bool]:
    """Trả về (giá trị, có_từ_chỉ_bậc). Quy tắc số dư sau 'triệu' không kèm đơn vị: 1 chữ số -> trăm nghìn
    ('năm triệu hai' = 5.200.000); 2–3 chữ số -> nghìn ('bốn triệu tám trăm chín mươi' = 4.890.000)."""
    total, section, last_mag, has_mag = 0, [], None, False
    for t in toks:
        if t in _MAGS:
            if not section:
                return 0, False   # 'triệu' không có số đứng trước (vd '5 triệu' đã là chữ số) -> không phải số chữ
            has_mag = True
            total += _parse_section(section) * _MAGS[t]
            section, last_mag = [], _MAGS[t]
        else:
            section.append(t)
    if "rưỡi" in section:
        section = [t for t in section if t != "rưỡi"]
        if last_mag:
            total += last_mag // 2
        return total, has_mag
    rest = _parse_section(section) if section else 0
    if section and last_mag and (section[0] in _FILLERS or section[0] == "không"):
        # "sáu trăm nghìn lẻ một" = 600.001; "… không trăm lẻ một" = 600.001: có "lẻ/không" thì đọc theo nghĩa đen (không áp cách nói tắt)
        total += rest
    elif section and last_mag:
        if last_mag >= 1_000_000:
            total += rest * (100_000 if rest < 10 else 1000)
        else:
            total += rest * (100 if rest < 10 else 1)
    else:
        total += rest
    return total, has_mag


def itn_phone_digits(text: str) -> str:
    """Chuỗi ≥ 9 từ chữ số liên tiếp ('không chín tám bốn ...') -> dãy số điện thoại."""
    words = text.split()
    out, i = [], 0
    while i < len(words):
        j = i
        digits = []
        while j < len(words):
            core = words[j].lower().strip(_PUNCT)
            if core in _PHONE_DIGIT_WORDS:
                digits.append(_PHONE_DIGIT_WORDS[core])
                j += 1
            else:
                break
        if len(digits) >= 9:
            out.append("".join(digits))
            i = j
        else:
            out.append(words[i])
            i += 1
    return " ".join(out)


def itn_number_words(text: str) -> str:
    """ITN tổng quát số tiền đọc bằng chữ. Chỉ đổi khi chuỗi có từ chỉ bậc (nghìn/triệu/tỷ), hoặc đi kèm 'k',
    đơn vị tiền (đồng/đ/vnd) hoặc đơn vị diện tích (mét vuông/m2) — tránh đổi 'năm nay', 'một cái'."""
    words = text.split()
    out, i, n = [], 0, len(words)
    while i < n:
        if _vocab_token(words[i]) is None:
            out.append(words[i])
            i += 1
            continue
        j = i
        while j < n and _vocab_token(words[j]) is not None:
            j += 1
        toks = [_vocab_token(w) for w in words[i:j]]
        trail = words[j - 1][len(words[j - 1].rstrip(_PUNCT)):]          # dấu câu dính cuối cụm
        nxt = words[j].lower().strip(_PUNCT) if j < n else ""
        if nxt in _COUNT_NOUNS:
            mags = [k for k, t in enumerate(toks) if t in _MAGS]
            if mags and len(toks) - mags[-1] == 2 and toks[-1] in _DIGITS:      # <số tiền có bậc> + MỘT chữ số + danh từ đơn vị → chữ số là số lượng
                toks = toks[:-1]
                j -= 1
                trail = words[j - 1][len(words[j - 1].rstrip(_PUNCT)):]
                nxt = words[j].lower().strip(_PUNCT)
        value, has_mag = _parse_number_run(toks)
        convert, consumed_next = False, False
        if has_mag and value:
            convert = True
        elif nxt == "k" and value:
            value *= 1000
            convert = consumed_next = True
        elif nxt in ("đồng", "đ", "vnd", "vnđ") and value:
            convert = True
        elif nxt in ("mét", "m2", "m²") and value and not has_mag:
            convert = True
        if convert:
            out.append(_fmt_money(value) if (has_mag or consumed_next or nxt in ("đồng", "đ", "vnd", "vnđ")) else str(value))
            if trail:
                out[-1] += trail
            i = j + 1 if consumed_next else j
        else:
            out.extend(words[i:j])
            i = j
    return " ".join(out)


_RE_TR = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:triệu|tr)(?![^\W\d_])(?:\s*(\d{1,3})\b(?!\s*(?:m|%|ngày|tháng|giờ|năm|cm|kg|lít|người|" + _COUNT_NOUNS_RE + r")))?", re.I)
_RE_K = re.compile(r"(?<![\d.,])(\d+)\s*(?:nghìn|ngàn|k)\b", re.I)


def itn_digit_units(text: str) -> str:
    """5tr -> 5.000.000; 2,5 triệu -> 2.500.000; 5tr2 -> 5.200.000; 249k -> 249.000; 1521k -> 1.521.000."""
    def tr(m):
        value = int(round(float(m.group(1).replace(",", ".")) * 1_000_000))
        if m.group(2):
            value += int(m.group(2)) * (100_000 if len(m.group(2)) == 1 else 1000)
        out = _fmt_money(value)
        nxt = m.string[m.end(): m.end() + 1]
        return out + " " if nxt.isdigit() else out          # "5tr2 máy": chữ số dính liền là số lượng → tách ra, không dính vào số tiền
    text = _RE_TR.sub(tr, text)
    return _RE_K.sub(lambda m: _fmt_money(int(m.group(1)) * 1000), text)


# ---------------------------------------------------------------- ngày giờ tương đối
# --- Số nhỏ nói bằng chữ cạnh đơn vị ("mười lõi", "mười lăm tháng mười", "hai mươi mét vuông") -> chữ số. Hàm RIÊNG, không nằm trong phần ITN đã KHÓA
# (scripts/lock_asr_rules.py băm `itn_number_words` & các hàm tiền); chỉ ≤ 99, chỉ khi đứng cạnh đơn vị/tháng/ngày/size để không đổi nhầm "thứ hai", "năm ngoái".
_SMALL_UNITS = {"lõi", "tháng", "mét", "tuổi", "giờ", "phút", "lít", "kg", "cm", "tầng", "tiếng", "ký"}
_SMALL_BEFORE = {"tháng", "ngày", "size", "mùng", "mồng"}
_UNIT_DIGIT = {**_DIGITS, "bẩy": 7}


def _small_value(toks: List[str]) -> Optional[int]:
    t = [x.lower() for x in toks]
    if not t or any(x not in _UNIT_DIGIT and x not in ("mười", "mươi") for x in t):
        return None
    if t == ["mười"]:
        return 10
    if t[0] == "mười" and len(t) == 2 and t[1] in _UNIT_DIGIT and t[1] != "không":
        return 10 + _UNIT_DIGIT[t[1]]
    if len(t) == 1 and t[0] in _UNIT_DIGIT and t[0] != "không":
        return _UNIT_DIGIT[t[0]]
    if len(t) in (2, 3) and t[1] == "mươi" and t[0] in _UNIT_DIGIT and t[0] not in ("không", "một", "mốt"):
        if len(t) == 2:
            return _UNIT_DIGIT[t[0]] * 10
        return _UNIT_DIGIT[t[0]] * 10 + _UNIT_DIGIT[t[2]] if t[2] in _UNIT_DIGIT and t[2] != "không" else None
    return None


def itn_small_numbers(text: str) -> str:
    toks = text.split(" ")
    out: List[str] = []
    i = 0
    while i < len(toks):
        done = False
        for n in (3, 2, 1):
            run = toks[i:i + n]
            if len(run) < n:
                continue
            core = [r.strip(_PUNCT) for r in run]
            val = _small_value(core)
            prev = out[-1].lower().strip(_PUNCT) if out else ""
            if val is None and prev == "size" and n == 2 and all(c.lower() in _UNIT_DIGIT and c.lower() != "không" for c in core):
                val = int("".join(str(_UNIT_DIGIT[c.lower()]) for c in core))        # "size ba tám" = 38 (đọc từng chữ số)
            if val is None:
                continue
            nxt = toks[i + n].lower().strip(_PUNCT) if i + n < len(toks) else ""
            if prev == "thứ" or not (nxt in _SMALL_UNITS or prev in _SMALL_BEFORE):
                continue
            out.append(str(val) + run[-1][len(run[-1].rstrip(_PUNCT)):])
            i += n
            done = True
            break
        if not done:
            out.append(toks[i])
            i += 1
    return " ".join(out)


_WEEKDAYS = {"thứ hai": 0, "thứ ba": 1, "thứ tư": 2, "thứ năm": 3, "thứ sáu": 4, "thứ bảy": 5, "chủ nhật": 6}
_REL_DAYS = [("ngày kia", 2), ("ngày mốt", 2), ("ngày mai", 1), ("hôm nay", 0), ("bữa nay", 0), ("tuần sau", 7), ("tuần tới", 7)]
_RE_TIME = re.compile(r"(?<![\d.,])(\d{1,2})\s*(?:giờ|h(?![^\W\d_]))\s*(?:(\d{1,2})\b)?\s*(sáng|trưa|chiều|tối)?", re.I)


def relative_date_hint(text: str, reference_date: str) -> Optional[Dict[str, str]]:
    """Gợi ý ngày/giờ hẹn gọi lại từ cách nói tương đối, tính theo ngày cuộc gọi (reference_date YYYY-MM-DD)."""
    try:
        ref = datetime.strptime(reference_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    low = text.lower()
    target: Optional[date] = None
    for phrase, off in _REL_DAYS:
        if phrase in low:
            target = ref + timedelta(days=off)
            break
    if target is None and re.search(r"(?<!\w)mai(?!\w)", low):
        target = ref + timedelta(days=1)
    for name, wd in _WEEKDAYS.items():
        if name in low:
            delta = (wd - ref.weekday()) % 7 or 7
            target = ref + timedelta(days=delta + (7 if "tuần sau" in low or "tuần tới" in low else 0))
            break
    time_str = None
    tm = _RE_TIME.search(low)
    if tm:
        hour, minute, part = int(tm.group(1)), int(tm.group(2) or 0), tm.group(3)
        if part in ("chiều", "tối") and hour < 12:
            hour += 12
        elif part == "trưa" and hour < 11:
            hour += 12
        if 0 <= hour < 24 and 0 <= minute < 60:
            time_str = f"{hour:02d}:{minute:02d}"
    if target is None and time_str is None:
        return None
    hint = {}
    if target is not None:
        hint["date"] = target.isoformat()
    if time_str:
        hint["time"] = time_str
    return hint


class RequestNormalizer:
    # Từ điển thay thế TUYỆT ĐỐI: chỉ các từ nhiều chữ cái, không nhập nhằng. KHÔNG có 'k' (xử lý theo ngữ cảnh),
    # 'sai' (V2), 'a'/'c'/'e' (xử lý theo ngữ cảnh), 'ng', 'tam'.
    TEENCODE_DICT = {
        "sp": "sản phẩm", "ko": "không", "khong": "không", "hok": "không",
        "co": "có", "dc": "được", "đc": "được", "trc": "trước", "r": "rồi",
        "ad": "admin", "ib": "inbox", "ship": "giao hàng", "cod": "COD",
        "sz": "size", "sze": "size", "bn": "bao nhiêu", "bnhieu": "bao nhiêu",
        "tr": "triệu", "trieu": "triệu",
        "m2": "m²", "sdt": "số điện thoại", "tl": "trả lời", "nt": "nhắn tin",
        "fb": "Facebook", "zl": "Zalo"
    }
    _PRONOUNS = {"a": "anh", "c": "chị", "e": "em"}
    _VERB_AFTER = {"có", "đã", "vừa", "muốn", "cần", "hỏi", "đồng", "nói", "gọi", "lấy", "mua", "đang", "sẽ", "cho",
                   "xin", "bảo", "thấy", "biết", "nhắn", "đặt", "ok", "oke", "order", "chưa", "định", "thích",
                   "chốt", "lên", "ơi", "là", "ở", "nhờ", "gửi", "chờ", "đợi"}
    _OBJECT_PREV = {"cho", "giúp", "gọi", "báo", "nhắn", "với", "bảo"}
    _YES_NO_PREV = {"không", "nhé", "đúng", "phải", "chưa"}

    ASR_FIXES = {
        "xiao mi": "Xiaomi",
        "sai z eo": "size L",
        "sai zét": "size S",
        "sai dét": "size S",
        "sai em": "size M",
        "e pơ": "AirPure",
        "e po": "AirPure",
        "run lai": "RunLite",
        "răn lai": "RunLite"
    }

    # Số điện thoại có thể viết cách quãng: 0994 893 949 / 0994.893.949 / 0994-893-949
    PHONE_CANDIDATE = re.compile(r"(?<!\d)0(?:[ .\-]?\d){9}(?!\d)")
    CCCD_REGEX = re.compile(r"(?<!\d)\d{12}(?!\d)")
    BANK_REGEX = re.compile(r"(?<!\d)(?!0\d{9}(?!\d))\d{9,14}(?!\d)")
    SELF_HONORIFIC = re.compile(
        r"(?:^|[.!?,]\s*)(anh|chị|cô|chú|bác)\s+(?:vừa|muốn|cần|đã|có|đang|sẽ|là|hỏi|lấy|đặt|mua|gọi|nhắn|ở)\b", re.I)

    def _expand_words(self, text: str) -> Tuple[str, bool]:
        """Teencode theo từ + đại từ đơn chữ (a/c/e) theo ngữ cảnh; 'k' đứng riêng = 'không'."""
        out: List[str] = []
        noisy = False
        words = text.split()
        for idx, w in enumerate(words):
            core = w.lower().strip(_PUNCT)
            suffix = w[len(w.rstrip(_PUNCT)):]
            nxt = words[idx + 1].lower().strip(_PUNCT) if idx + 1 < len(words) else ""
            prev = out[-1].lower().strip(_PUNCT) if out else ""
            repl = None
            if core == "k":
                repl = "không"
            elif core in self._PRONOUNS:
                is_last = idx == len(words) - 1
                if nxt in self._VERB_AFTER or prev in self._OBJECT_PREV:
                    repl = self._PRONOUNS[core]
                elif core == "a" and is_last and prev in self._YES_NO_PREV:
                    repl = "ạ"        # "... k a" = "... không ạ"
            elif core in self.TEENCODE_DICT:
                repl = self.TEENCODE_DICT[core]
            if repl is not None:
                out.append(repl + suffix)
                noisy = True
            else:
                out.append(w)
        return " ".join(out), noisy

    def normalize(self, raw_text: str, channel: InputChannel, contact_id: str, is_audio: bool = False,
                  audio_path: Optional[str] = None, reference_date: Optional[str] = None) -> NormalizedTurn:
        # [INTEGRATION POINT: LOCAL ASR MODEL]
        # audio_path (file .wav/.mp3 thật) khác với is_audio/customer_turns_asr (text ASR-lỗi
        # giả lập sẵn trong kịch bản eval) — audio_path dùng cho input audio thật (UI upload,
        # eval_asr.py). Transcribe thất bại -> offline_asr trả "" (không crash), raw_text giữ
        # nguyên để caller tự xử lý (nhập tay).
        if audio_path:
            from src.channels.offline_asr import transcribe_audio
            transcript = transcribe_audio(audio_path)
            if transcript:
                raw_text = transcript
                is_audio = True

        text = raw_text.strip()
        is_noisy = False

        # 1. Sửa lỗi ngữ âm ASR
        for err, fix in self.ASR_FIXES.items():
            if re.search(r'\b' + re.escape(err) + r'\b', text, re.I):
                text = re.sub(r'\b' + re.escape(err) + r'\b', fix, text, flags=re.I)
                is_noisy = True

        # 2. ITN (TRƯỚC teencode để 'k' sau số là nghìn, không bị đổi thành 'không')
        before = text
        text = itn_phone_digits(text)
        text = itn_number_words(text)
        text = itn_digit_units(text)
        text = itn_small_numbers(text)
        if text != before:
            is_noisy = True

        # 3. Teencode / đại từ theo ngữ cảnh
        text, noisy = self._expand_words(text)
        is_noisy = is_noisy or noisy

        # 4. Số điện thoại viết cách quãng -> dạng liền
        text = self.PHONE_CANDIDATE.sub(lambda m: re.sub(r"\D", "", m.group(0)), text)

        # 5. Entity
        entities: Dict[str, Any] = {}
        area = re.search(r'(\d+)\s*(?:m2|mét vuông|m²)', text, re.I)
        if area:
            entities["room_area_m2"] = float(area.group(1))
        if any(w in text.lower() for w in ["bé nhỏ", "con nhỏ", "trẻ nhỏ", "em bé"]):
            entities["has_children"] = True
        phones = re.findall(r"(?<!\d)0\d{9}(?!\d)", text)
        if phones:
            entities["phone"] = phones[0]
            entities["phones"] = list(dict.fromkeys(phones))
        m = self.SELF_HONORIFIC.search(text)
        if m:
            entities["self_honorific"] = m.group(1).lower()
        if reference_date:
            hint = relative_date_hint(text, reference_date)
            if hint:
                entities["callback_hint"] = hint

        # 6. PII: CCCD / số tài khoản -> <ID_n> (không bao giờ mở lại)
        counter = [0]

        def to_id(_m):
            counter[0] += 1
            return f"<ID_{counter[0]}>"
        text = self.CCCD_REGEX.sub(to_id, text)
        text = self.BANK_REGEX.sub(to_id, text)

        return NormalizedTurn(
            raw_input=raw_text,
            normalized_text=text,
            channel=channel,
            contact_id=contact_id,
            is_noisy_asr=is_noisy,
            extracted_entities=entities,
            pii_masked_text=text,
            llm_text=text,
        )
