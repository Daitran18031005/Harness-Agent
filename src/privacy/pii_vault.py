"""
PII Vault (bước 7, N13): che thông tin cá nhân trước khi đưa cho LLM; mở lại có kiểm soát khi gọi tool.

Token:
- `CURRENT_CUSTOMER` : CHỈ số điện thoại của người đang gọi (đã định danh).
- `<PHONE_n>`        : mọi số điện thoại khác khách đọc ra (giao cho người khác, số người thân...).
- `<ADDR_n>`         : địa chỉ.
- `<ID_n>`           : CCCD / số tài khoản — do normalizer gán; KHÔNG BAO GIỜ được mở.

Nguyên tắc:
1. Bảng token chỉ nằm trong bộ nhớ process của đối tượng này. Không có hàm serialize: pickle/copy bị chặn,
   `repr` không lộ giá trị -> không thể vô tình ghi vào DB/trace/log.
2. Chỉ mở token cho (tool, field) nằm trong UNMASK_ALLOWED. Token ở chỗ khác giữ nguyên.
3. Kết quả tool được che lại (mask_value) trước khi trả cho LLM.
4. Lời agent nói với khách được mở token (unmask_text) — trừ `<ID_n>` (không bao giờ đọc lại).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

CALLER_TOKEN = "CURRENT_CUSTOMER"
PHONE_RE = re.compile(r"(?<!\d)0\d{9}(?!\d)")
TOKEN_RE = re.compile(r"CURRENT_CUSTOMER|<(PHONE|ADDR|ID)_(\d+)>")
REDACTED = "[đã bảo mật]"

# (tool) -> các field (ở mọi độ sâu của args) được phép nhận giá trị thật.
UNMASK_ALLOWED: Dict[str, frozenset] = {
    "order.create": frozenset({"customer_phone", "address", "recipient_phone"}),     # recipient_phone chỉ dùng cho order gate, gỡ trước khi gọi MCP
    "order.status": frozenset({"customer_phone"}),
    "pricing.get_quote": frozenset({"customer_phone", "address"}),
    "schedule.callback": frozenset({"customer_phone"}),
    "handoff.transfer": frozenset({"customer_phone"}),     # nằm trong brief{}
    "crm.get_customer": frozenset({"phone"}),
}

ADDRESS_KEYS = ("address", "addr", "dia_chi")

_ADMIN = r"(?:phường|xã|thị trấn|quận|huyện|thành phố|tp\.?|tỉnh|đường|phố|ngõ|ngách|hẻm|kiệt|thôn|xóm|khu phố|chung cư|tòa|tổ dân phố)"
_TRIGGER = re.compile(
    r"(?:giao(?: hàng)?|ship|gửi|chuyển)\s+(?:về|tới|đến)\s+"
    r"|địa chỉ(?:\s+(?:là|nhà|giao hàng|nhận hàng))?\s*(?:ở|là|:)?\s*"
    r"|nhà\s+(?:chị|anh|em|cô|chú|bác|mình)\s+(?:ở|tại)\s+", re.I)
_CLAUSE = re.compile(r"(?:[^.!?\n]|(?<=tp)\.|(?<=TP)\.|(?<=\d)\.(?=\d))+")
_CUE = re.compile(rf"(?:\bsố\s*\d{{1,4}}\b|\b\d+[a-zA-Z]?(?:/\d+)+|\b\d{{1,4}}\b|\b{_ADMIN}\b)", re.I)
_STREET = re.compile(rf"(?:số\s*)?\d+[a-zA-Z]?(?:/\d+)*\s+(?:đường|phố|ngõ|ngách|hẻm|kiệt)\b[^.!?\n]*", re.I)
_PHONE_INSIDE = re.compile(r"(?<!\d)0\d{9}(?!\d)")
_DANGLING = re.compile(r"[\s,;:.-]*(?:số điện thoại|sđt|sdt|liên hệ|số|gọi|điện)?[\s,;:.-]*$", re.I)
_PAY_TAIL = re.compile(r"[\s,;]*(?:thanh toán|cod\b|chuyển khoản|trả tiền|nhận hàng (?:rồi )?(?:mới )?trả).*$", re.I)
_TAIL_PARTICLES = re.compile(r"(?:\s+(?:nhé|nha|nhá|ạ|với|đi|nhỉ|đấy|nghen|nhen|thôi|luôn))+\s*$", re.I)


_PROVINCES = frozenset(x.strip() for x in """ha noi, ho chi minh, tphcm, tp hcm, hcm, sai gon, da nang, hai phong, can tho, hue, nghe an, thanh hoa, ha tinh, quang ninh, quang binh, quang tri,
quang nam, quang ngai, binh dinh, phu yen, khanh hoa, ninh thuan, binh thuan, kon tum, gia lai, dak lak, dak nong, lam dong, binh phuoc, tay ninh, binh duong, dong nai, ba ria vung tau,
long an, tien giang, ben tre, tra vinh, vinh long, dong thap, an giang, kien giang, hau giang, soc trang, bac lieu, ca mau, lao cai, yen bai, tuyen quang, ha giang, cao bang, bac kan,
lang son, thai nguyen, phu tho, bac giang, vinh phuc, bac ninh, hai duong, hung yen, thai binh, ha nam, nam dinh, ninh binh, son la, dien bien, lai chau, hoa binh, vung tau, thu duc""".replace(chr(10), " ").split(",") if x.strip())


def _province_phrase(seg_folded: str) -> bool:
    words = seg_folded.split()
    return bool(words) and (" ".join(words) in _PROVINCES or any(" ".join(words[i:i + 3]) in _PROVINCES or " ".join(words[i:i + 2]) in _PROVINCES for i in range(len(words))))


def _trim_trailing_name(seg: str) -> str:
    """"…hồ chí minh, Đại": phần sau dấu phẩy cuối là TÊN NGƯỜI (1–3 từ chữ cái, không phải tỉnh/thành, không phải đơn vị hành chính) → không thuộc địa chỉ."""
    head, sep, tail = seg.rpartition(",")
    t = tail.strip()
    if not sep or not t or not _CUE.search(head):
        return seg
    words = t.split()
    from src.harness.fact_usage import fold as _f
    if 1 <= len(words) <= 3 and all(w.isalpha() for w in words) and not _CUE.search(t) and not _province_phrase(_f(t)):
        return head
    return seg


_HOUSE = re.compile(r"(?<![\w/.,])(số\s*)?(\d{1,4}[a-zA-Z]?(?:/\d+)*)(?=\s+[^\W\d_])", re.I)


def _province_end(seg: str) -> Optional[int]:
    """Vị trí cuối của tên tỉnh/thành đứng ở CUỐI `seg` (đoạn cuối sau dấu phẩy, bỏ đuôi 'nhé/ạ…'), hoặc None."""
    from src.harness.fact_usage import fold
    pos, last = 0, None
    for piece in seg.split(","):
        core = _TAIL_PARTICLES.sub("", piece).strip()
        if core:
            start = pos + piece.index(core)
            last = (start + len(core), core)
        pos += len(piece) + 1
    if last and fold(last[1]).replace(".", "").strip() in _PROVINCES:
        return last[0]
    return None


def _spans_by_province(text: str) -> List[Tuple[int, int]]:
    """Địa chỉ KHÔNG có đường/phường/quận: 'số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội' (kể cả khi không có 'giao về' đứng trước, vd 'Giao cho Lan, số 12 …').
    Dấu hiệu = số nhà + các đoạn phân cách bằng dấu phẩy + TỈNH/THÀNH ở cuối. Có 'số' phía trước thì viết thường vẫn nhận; số trần ('12 Nguyễn Trãi,…')
    phải mở đầu bằng chữ hoa. Dừng ở lời thanh toán, số điện thoại hoặc con số kế tiếp (vd giá tiền)."""
    out: List[Tuple[int, int]] = []
    for m in _HOUSE.finditer(text):
        clause = _CLAUSE.match(text, m.end())
        if not clause:
            continue
        seg = _PAY_TAIL.sub("", clause.group(0))
        pm = _PHONE_INSIDE.search(seg)
        if pm:
            seg = _DANGLING.sub("", seg[:pm.start()])
        dm = re.search(r"\d", seg)
        if dm:
            seg = seg[:dm.start()]
        end = _province_end(seg)
        if end is None:
            continue
        mid = seg[:end]
        if "," not in mid or (not m.group(1) and not mid.strip()[:1].isupper()):
            continue
        out.append((m.start(), m.end() + end))
    return out


def detect_addresses(text: str) -> List[Tuple[int, int]]:
    """Tìm các đoạn địa chỉ (start, end). Heuristic: sau cụm 'giao về/địa chỉ/nhà ... ở' lấy tới hết câu nếu có
    dấu hiệu địa chỉ (số nhà / đơn vị hành chính); hoặc mẫu 'số 12 ngõ 5 ...'. Không đoán khi không có dấu hiệu."""
    spans: List[Tuple[int, int]] = []
    for m in _TRIGGER.finditer(text):
        clause = _CLAUSE.match(text, m.end())
        if not clause:
            continue
        seg = clause.group(0)
        pm = _PHONE_INSIDE.search(seg)
        if pm:                       # địa chỉ dừng trước số điện thoại đi kèm
            seg = _DANGLING.sub("", seg[:pm.start()])
        seg = _PAY_TAIL.sub("", seg)                # "…Hà Nội, thanh toán COD" — phần thanh toán không thuộc địa chỉ
        seg = _trim_trailing_name(_TAIL_PARTICLES.sub("", seg))
        seg = _TAIL_PARTICLES.sub("", seg)
        if seg and _CUE.search(seg):
            spans.append((m.end(), m.end() + len(seg)))
    for m in _STREET.finditer(text):
        seg = _trim_trailing_name(_TAIL_PARTICLES.sub("", _PAY_TAIL.sub("", m.group(0))))
        seg = _TAIL_PARTICLES.sub("", seg)
        spans.append((m.start(), m.start() + len(seg)))
    spans += _spans_by_province(text)
    # gộp các đoạn chồng nhau
    spans.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


class PiiVault:
    def __init__(self):
        self._real_to_token: Dict[Tuple[str, str], str] = {}   # (kind, real) -> token
        self._token_to_real: Dict[str, str] = {}
        self._counters = {"PHONE": 0, "ADDR": 0}
        self._source: Dict[str, str] = {}                      # token -> "customer" (khách nói trong cuộc gọi) | "system" (bộ nhớ/tool)

    # --- chặn lan truyền ra ngoài process ---
    def __repr__(self) -> str:
        return f"<PiiVault phones={self._counters['PHONE']} addrs={self._counters['ADDR']}>"

    def __reduce__(self):
        raise TypeError("PiiVault không được serialize (chỉ sống trong bộ nhớ process)")

    def __copy__(self):
        raise TypeError("PiiVault không được copy")

    def __deepcopy__(self, memo):
        raise TypeError("PiiVault không được copy")

    # --- token ---
    def _token_for(self, kind: str, real: str, source: str = "customer") -> str:
        key = (kind, real)
        if key not in self._real_to_token:
            self._counters[kind] += 1
            token = f"<{kind}_{self._counters[kind]}>"
            self._real_to_token[key] = token
            self._token_to_real[token] = real
            self._source[token] = source
        return self._real_to_token[key]

    def address_token_for(self, real: str) -> str:
        """Token cho địa chỉ ĐÃ LƯU (bộ nhớ) — đánh dấu nguồn 'system' để order gate phân biệt với địa chỉ khách vừa nói."""
        return self._token_for("ADDR", real.strip(), source="system")

    def is_customer_token(self, token: Optional[str]) -> bool:
        """Token do KHÁCH nói trong cuộc gọi này (không phải do hệ thống đăng ký từ bộ nhớ/kết quả tool)."""
        return bool(token) and self._source.get(token) == "customer"

    def phone_token(self, phone: str, caller_phone: Optional[str] = None) -> str:
        if caller_phone and phone == caller_phone:
            return CALLER_TOKEN
        return self._token_for("PHONE", phone)

    # --- che (vào LLM) ---
    def mask_text(self, text: str, caller_phone: Optional[str] = None) -> str:
        if not text:
            return text
        for start, end in reversed(detect_addresses(text)):
            text = text[:start] + self._token_for("ADDR", text[start:end].strip()) + text[end:]
        text = PHONE_RE.sub(lambda m: self.phone_token(m.group(0), caller_phone), text)
        # địa chỉ đã biết xuất hiện lại ở lượt sau (không có từ khóa dẫn)
        for (kind, real), token in list(self._real_to_token.items()):
            if kind == "ADDR" and real and real in text:
                text = text.replace(real, token)
        return text

    def mask_value(self, obj: Any, caller_phone: Optional[str] = None, key: Optional[str] = None) -> Any:
        """Che đệ quy giá trị trong kết quả tool: số điện thoại (kể cả field *phone*), địa chỉ (field address)."""
        if isinstance(obj, dict):
            return {k: self.mask_value(v, caller_phone, k if isinstance(k, str) else None) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.mask_value(v, caller_phone, key) for v in obj]
        if isinstance(obj, str):
            if key and any(a in key.lower() for a in ADDRESS_KEYS):
                return self._token_for("ADDR", obj.strip(), source="system") if obj.strip() else obj
            masked = PHONE_RE.sub(lambda m: self.phone_token(m.group(0), caller_phone), obj)
            for (kind, real), token in list(self._real_to_token.items()):
                if kind == "ADDR" and real and real in masked:
                    masked = masked.replace(real, token)
            return masked
        return obj

    # --- mở (cho tool) ---
    def _unmask_string(self, s: str, caller_phone: Optional[str]) -> str:
        def sub(m: "re.Match") -> str:
            tok = m.group(0)
            if tok == CALLER_TOKEN:
                return caller_phone if caller_phone and caller_phone != "UNKNOWN" else tok
            if m.group(1) == "ID":
                return tok                              # CCCD/STK: không bao giờ mở
            return self._token_to_real.get(tok, tok)
        return TOKEN_RE.sub(sub, s)

    def unmask_args(self, tool_name: str, args: Any, caller_phone: Optional[str] = None, _key: Optional[str] = None) -> Any:
        """Trả về BẢN SAO args với token được mở ở các field được phép của tool. Tool không có trong
        UNMASK_ALLOWED -> không mở gì."""
        allowed = UNMASK_ALLOWED.get(tool_name)
        if not allowed:
            return args
        return self._unmask(args, allowed, caller_phone, None)

    def _unmask(self, obj: Any, allowed: frozenset, caller_phone: Optional[str], key: Optional[str]) -> Any:
        if isinstance(obj, dict):
            return {k: self._unmask(v, allowed, caller_phone, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._unmask(v, allowed, caller_phone, key) for v in obj]
        if isinstance(obj, str) and key in allowed:
            return self._unmask_string(obj, caller_phone)
        return obj

    def redact_args_for_trace(self, obj: Any) -> Any:
        """Args để ghi trace: giữ SĐT (BTC cho phép SĐT 10 số) nhưng thay địa chỉ thật bằng token."""
        if isinstance(obj, dict):
            return {k: self.redact_args_for_trace(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact_args_for_trace(v) for v in obj]
        if isinstance(obj, str):
            for (kind, real), token in list(self._real_to_token.items()):
                if kind == "ADDR" and real and real in obj:
                    obj = obj.replace(real, token)
        return obj

    # --- mở cho lời nói với khách ---
    def unmask_text(self, text: str, caller_phone: Optional[str] = None) -> str:
        def sub(m: "re.Match") -> str:
            tok = m.group(0)
            if tok == CALLER_TOKEN:
                return caller_phone if caller_phone and caller_phone != "UNKNOWN" else "số máy mình đang gọi"
            if m.group(1) == "ID":
                return REDACTED
            return self._token_to_real.get(tok, REDACTED)
        return TOKEN_RE.sub(sub, text or "")
