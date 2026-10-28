"""
ORDER GATE (người dùng chốt 2026-10-21) — bằng CODE, không phó thác cho LLM — kiểm soát khi nào `order.create` được chạy.

Checklist trước khi tạo đơn: sản phẩm + biến thể (size/màu nếu sản phẩm có), số lượng, TÊN người nhận, SĐT nhận, ĐỊA CHỈ, THANH TOÁN.
Mỗi trường có một trạng thái:
  stated     — khách NÓI trong cuộc gọi này (đối chiếu với lời khách; giá trị LLM tự điền mà khách chưa nói KHÔNG được tính),
  confirmed  — đã có sẵn (bộ nhớ/CRM/số đang gọi) VÀ khách vừa xác nhận ở lượt ngay sau câu xác nhận,
  known      — đã có sẵn nhưng CHƯA được xác nhận trong cuộc gọi này  → câu XÁC NHẬN,
  missing    — chưa có                                                   → câu HỎI (tối đa 2 trường mỗi lượt).
Quy trình: còn missing/known → chặn + hỏi/xác nhận → đủ checklist → chặn + ĐỌC LẠI ĐƠN một lần → CHỈ khi lượt SAU khách đồng ý RÕ RÀNG
(`is_explicit_consent`) và lời gọi `order.create` khớp đúng đơn đã đọc lại thì mới cho chạy. Khách sửa gì sau khi nghe đọc lại → đơn đổi
→ phải đọc lại. Khách không đồng ý ở lượt ngay sau → bản đọc lại hết hiệu lực.

Kết quả chặn được trả cho LLM kèm `say` (câu cần nói, do code dựng từ dữ liệu thật) và được ghi vào trace dưới khóa `order_gate`
(KHÔNG xuất hiện trong `tool_calls` của trace, để lời gọi bị chặn không bị tính là đã tạo đơn).
"""
import copy
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.harness.fact_usage import fold

GATE_ONLY_ARGS = ("recipient_name", "recipient_phone")       # tham số chỉ có ở phía LLM/gate, gỡ trước khi gọi MCP và trước khi ghi trace
FIELDS = ("item", "qty", "recipient_name", "recipient_phone", "address", "payment")
LABEL = {"item": "sản phẩm/biến thể", "qty": "số lượng", "recipient_name": "tên người nhận", "recipient_phone": "số điện thoại nhận hàng",
         "address": "địa chỉ nhận hàng", "payment": "hình thức thanh toán"}
ASK = {"item": "mình chọn size và màu nào", "recipient_name": "tên người nhận hàng", "recipient_phone": "số điện thoại nhận hàng",
       "address": "địa chỉ nhận hàng", "payment": "hình thức thanh toán, nhận hàng trả tiền (COD) hay chuyển khoản"}
MUST_WORD = {"item": "size", "recipient_name": "ten", "recipient_phone": "dien thoai", "address": "dia chi", "payment": "thanh toan"}
LABEL_SHORT = {"item": "size/màu", "recipient_name": "tên người nhận", "recipient_phone": "số điện thoại nhận hàng", "address": "địa chỉ nhận hàng",
               "payment": "hình thức thanh toán"}
EXAMPLE = {"item": "ví dụ: size 40 màu đen", "recipient_name": "ví dụ: Nguyễn Văn A", "recipient_phone": "ví dụ: 0912345678",
           "address": "ví dụ: số 12 đường Nguyễn Trãi, phường Thanh Xuân Trung, quận Thanh Xuân, Hà Nội", "payment": "ví dụ: COD hoặc chuyển khoản"}
ASK_ORDER = ("item", "address", "recipient_name", "recipient_phone", "payment")
PAYMENT_LABEL = {"COD": "thanh toán khi nhận hàng (COD)", "bank": "chuyển khoản", "momo": "ví MoMo", "zalopay": "ví ZaloPay"}
DRAFT_TTL_TURNS = 4                  # đơn nháp im quá số lượt này (không ai hỏi/đáp) thì hủy
UNKNOWN_NAMES ={"", "quy khach", "khach", "unknown", "none"}

# ---------------------------------------------------------------------------------------------------- đồng ý rõ ràng
_STRONG = ("dong y", "ok", "oke", "okay", "oki", "dung roi", "dung vay", "chinh xac", "chot", "len don", "dat di", "xac nhan", "nhat tri",
           "duoc roi")
# Lời đáp lại ("dạ", "vâng", "ừ", "có", "được", "đúng"): chỉ là đồng ý khi CÂU KHÔNG CÒN GÌ KHÁC ngoài chúng và từ đệm. "Dạ đắt thật đấy" là than phiền, không phải chốt đơn.
_ACK = frozenset({"da", "vang", "u", "uh", "uk", "duoc", "dung", "co"})
_FILLER = frozenset({"a", "nhe", "nha", "nhen", "em", "anh", "chi", "cung", "roi", "vay", "van"})
_HEDGE = ("khong", "chua", "khoan", "doi", "de ", "hoi", "phan van", "sao", "bao nhieu", "nua", "them", "nhung", "tuy nhien", "thoi", "huy", "xem lai",
          "sai", "nham", "khac", "nhung ma", "cho hoi", "bao gio", "may ngay", "tai sao", "?")


def is_explicit_consent(text: str, max_words: int = 14, lenient: bool = False) -> bool:
    """Đồng ý RÕ RÀNG: có cụm đồng ý mạnh ("đồng ý", "chốt", "ok"…) hoặc CHỈ có lời đáp lại ("dạ", "vâng", "ừ"…) + từ đệm; KHÔNG kèm phủ định/do dự/câu hỏi/
    điều kiện/đổi ý/ý khác, và ngắn gọn (≤ `max_words` từ; mặc định 14).
    `lenient=True`: chỉ dùng để xác nhận THÔNG TIN ĐÃ LƯU (SĐT, địa chỉ, tên) — câu được kèm thông tin mới ("đúng sdt, giao về 45/1…"); một lời đáp lại ở đầu là đủ.
    Chốt đơn KHÔNG dùng chế độ này (sau đó còn bước đọc lại đơn nên rủi ro thấp)."""
    f = " " + fold(text).strip() + " "
    words = re.findall(r"\w+", f)
    if not words or len(words) > max_words or "?" in text:
        return False
    for h in _HEDGE:
        if h != "?" and re.search(rf"(?<!\w){re.escape(h.strip())}(?!\w)", f):
            return False
    for s in _STRONG:
        if re.search(rf"(?<!\w){re.escape(s)}(?!\w)", f):
            return True
    if lenient:
        return any(w in _ACK for w in words)
    return any(w in _ACK for w in words) and all(w in _ACK or w in _FILLER for w in words)


_PHONE_OK = re.compile(r"(?<!\w)(?:dung|phai|van|chinh)\s+(?:la\s+)?(?:sdt|so dien thoai|so nay|so dang goi|so may nay)(?!\w)|(?<!\w)(?:sdt|so dien thoai|so nay)\s+(?:nay\s+)?(?:dung|ok)(?!\w)")

_PAYMENT = (("zalopay", re.compile(r"zalo\s*pay|zalopay")), ("momo", re.compile(r"\bmomo\b|mo mo")),
            ("bank", re.compile(r"chuyen khoan|\bck\b|ngan hang|\bbank\b|quet ma|qr")),
            ("COD", re.compile(r"\bcod\b|nhan hang (?:roi )?(?:moi )?(?:tra|thanh toan)|tra tien (?:khi|luc) nhan|thanh toan (?:khi|luc) nhan|tien mat")))


def detect_payment(text: str) -> Optional[str]:
    """Hình thức thanh toán khách NÓI trong `text` (None nếu không nói). Lấy lần nhắc CUỐI CÙNG nếu khách đổi ý."""
    f = fold(text)
    best, pos = None, -1
    for key, rx in _PAYMENT:
        for m in rx.finditer(f):
            if m.start() >= pos:
                best, pos = key, m.start()
    return best


_GATE_TOPIC = re.compile(r"xac nhan lai|cho em xin|dung khong|dia chi|thanh toan|ten nguoi nhan|so dien thoai|\bsize\b|mau nao|chon size|nhan hang")


def money(v: Any) -> str:
    return f"{int(v):,}".replace(",", ".") + "đ"


def norm_value(v: Any) -> str:
    return re.sub(r"\s+", " ", fold(str(v or ""))).strip()


# ---------------------------------------------------------------------------------------------------- dữ liệu vào
@dataclass
class OrderDraft:
    """Đơn nháp = tham số LLM truyền vào order.create (đã mở token). Chỉ dùng giá trị khách THỰC SỰ nói (gate tự kiểm)."""
    sku: str
    qty: int = 1
    payment: Optional[str] = None
    price_vnd: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None            # SĐT nhận riêng (None = số đang gọi)
    phone_token: Optional[str] = None
    address: Optional[str] = None
    address_token: Optional[str] = None


@dataclass
class OrderKnown:
    """Dữ liệu CÓ SẴN trước cuộc gọi (bộ nhớ/CRM) hoặc suy ra (số đang gọi)."""
    name: Optional[str] = None
    address: Optional[str] = None
    address_token: Optional[str] = None
    payment: Optional[str] = None
    caller_phone: Optional[str] = None


@dataclass
class ProductInfo:
    name: str = ""
    variant_label: str = ""
    needs_variant: bool = False
    is_variant: bool = False
    unit_price: Optional[int] = None


@dataclass
class FieldState:
    status: str                            # stated | confirmed | known | missing
    value: Optional[str] = None            # giá trị THẬT (dùng cho snapshot/so khớp, KHÔNG đưa cho LLM)
    shown: Optional[str] = None            # dạng đưa vào câu nói (token PII)


@dataclass
class GateState:
    stage: str = "collect"                 # collect | readback | consented | done
    snapshot: Optional[Dict[str, str]] = None
    readback_turn: Optional[int] = None
    pending_confirm: Optional[Dict[str, Any]] = None
    confirmed: Dict[str, str] = field(default_factory=dict)
    texts: List[str] = field(default_factory=list)
    turn: int = -1
    events: List[Dict[str, Any]] = field(default_factory=list)
    last_decision: Optional[Dict[str, Any]] = None
    created: Optional[Dict[str, Any]] = None
    abandoned_turn: Optional[int] = None   # lượt khách từ chối/mặc cả/hẹn gọi lại: đơn nháp bị HỦY (orchestrator xóa tham số nháp, không nối câu hỏi nữa)
    last_ask_key: Optional[tuple] = None   # (hành động, trường hỏi, trường xác nhận) của câu hỏi gần nhất — để phát hiện câu hỏi LẶP
    last_ask_turn: Optional[int] = None
    ask_streak: int = 0                    # số lần LIÊN TIẾP hỏi đúng câu đó mà khách chưa trả lời được
    phone_ok: bool = False                 # khách đã nói "đúng sdt/số này" (kể cả TRƯỚC khi gate hỏi) → số đang gọi coi như đã xác nhận


# ---------------------------------------------------------------------------------------------------- gate
class OrderGate:
    def __init__(self) -> None:
        # Cổng LUÔN BẬT ở mọi cấu hình (demo, UI, eval) — không có tham số/cờ/biến môi trường để tắt (quyết định của người dùng 2026-10-22).
        self._enabled = True
        self._s: Dict[str, GateState] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def disable_for_unit_tests(self) -> None:
        """CHỈ cho `tests/_helpers.py` (test đơn vị của cơ chế khác: chống gọi lặp, PII…). Có test quét mã nguồn: không nơi nào ngoài tests/ được gọi hàm này."""
        self._enabled = False

    # --- vòng đời
    def state(self, sid: str) -> GateState:
        return self._s.setdefault(sid, GateState())

    def forget(self, sid: str) -> None:
        self._s.pop(sid, None)

    def forget_prefix(self, prefix: str) -> None:
        for k in [k for k in self._s if k.startswith(prefix)]:
            del self._s[k]

    def begin_turn(self, sid: str, turn_no: int, text: str, reading: Any = None) -> None:
        """Gọi MỘT lần ở đầu mỗi lượt: ghi lời khách, chuyển trạng thái theo việc khách vừa đồng ý/không đồng ý.
        `reading` (reply_reader.ReplyReading, đã kiểm chứng trích dẫn nguyên văn) là nguồn HIỂU lời khách; None (không có LLM/LLM lỗi) → regex dự phòng."""
        st = self.state(sid)
        if st.turn == turn_no and st.texts:                      # cùng lượt được gọi lại: không xử lý hai lần
            return
        st.turn, st.events = turn_no, []
        st.texts.append(text or "")
        if reading is not None:
            consent = lenient_consent = reading.agrees
            declined, affirmed = reading.declines, set(reading.affirmed)
            if "recipient_phone" in affirmed:
                st.phone_ok = True
        else:
            consent, declined = is_explicit_consent(text or ""), is_decline(text or "")
            lenient_consent, affirmed = None, set()
            if _PHONE_OK.search(fold(text or "")) and not any(re.search(rf"(?<!\w){h}(?!\w)", fold(text or "")) for h in ("khong", "sai", "khac", "nham", "chua")):
                st.phone_ok = True
        open_draft = st.stage in ("collect", "readback", "consented") and (st.last_decision is not None) and not st.last_decision.get("allow", False)
        stale = open_draft and st.last_decision.get("turn") is not None and turn_no - st.last_decision["turn"] > DRAFT_TTL_TURNS    # đơn nháp không tiến triển → tự rút lui
        if open_draft and (declined or stale):
            st.abandoned_turn = turn_no                            # khách không muốn tiếp tục (đắt, chưa đủ tiền, để sau…) → hủy đơn nháp, không hỏi tiếp
            st.stage, st.snapshot, st.pending_confirm, st.readback_turn = "collect", None, None, None
            st.ask_streak, st.last_ask_key, st.last_ask_turn, st.last_decision = 0, None, None, None
            return
        if st.pending_confirm and turn_no == st.pending_confirm["turn"] + 1:
            if reading is not None:                                # LLM: chỉ các mục khách nêu là đúng, hoặc khách đồng ý chung với câu hỏi xác nhận
                vals = st.pending_confirm["values"]
                st.confirmed.update(vals if lenient_consent else {k: v for k, v in vals.items() if k in affirmed})
            elif consent or is_explicit_consent(text or "", max_words=40, lenient=True):       # xác nhận thông tin đã lưu có thể kèm thông tin mới ("đúng rồi, giao về…")
                st.confirmed.update(st.pending_confirm["values"])
            st.pending_confirm = None
        elif st.pending_confirm and turn_no > st.pending_confirm["turn"] + 1:
            st.pending_confirm = None
        if st.stage == "readback" and st.readback_turn is not None:
            if turn_no == st.readback_turn + 1 and consent:
                st.stage = "consented"
            elif turn_no >= st.readback_turn + 1:
                st.stage, st.snapshot = "collect", None          # không đồng ý rõ ràng → bản đọc lại hết hiệu lực
        elif st.stage == "consented":
            st.stage, st.snapshot = "collect", None              # đồng ý chỉ có giá trị cho lượt NGAY SAU lần đọc lại

    def events(self, sid: str) -> List[Dict[str, Any]]:
        return list(self.state(sid).events)

    # --- trích từ lời khách
    def _said(self, st: GateState, value: Optional[str]) -> bool:
        v = norm_value(value)
        return bool(v) and any(v in norm_value(t) for t in st.texts)

    def _fields(self, st: GateState, d: OrderDraft, k: OrderKnown, p: ProductInfo, addr_stated: Callable[[Optional[str]], bool]) -> Dict[str, FieldState]:
        out: Dict[str, FieldState] = {}
        # sản phẩm + biến thể
        out["item"] = FieldState("stated" if (not p.needs_variant or p.is_variant) else "missing", d.sku, p.name)
        out["qty"] = FieldState("stated", str(max(1, int(d.qty or 1))), str(max(1, int(d.qty or 1))))
        # tên
        name_known = k.name if norm_value(k.name) not in UNKNOWN_NAMES else None
        if d.name and self._said(st, d.name):
            out["recipient_name"] = FieldState("stated", d.name, d.name)
        elif d.name and name_known and norm_value(d.name) == norm_value(name_known):
            out["recipient_name"] = FieldState("known", d.name, d.name)
        elif not d.name and name_known:
            out["recipient_name"] = FieldState("known", name_known, name_known)
        else:
            out["recipient_name"] = FieldState("missing")           # LLM tự điền mà khách chưa nói → không tính
        # SĐT nhận
        if d.phone:
            stated = bool(re.search(re.escape(d.phone), " ".join(st.texts))) or bool(d.phone_token and d.phone_token.startswith("<PHONE_"))
            out["recipient_phone"] = FieldState("stated" if stated else "missing", d.phone if stated else None, d.phone_token or d.phone)
        elif k.caller_phone:
            out["recipient_phone"] = FieldState("known", k.caller_phone, "CURRENT_CUSTOMER")
        else:
            out["recipient_phone"] = FieldState("missing")
        # địa chỉ
        if d.address and (addr_stated(d.address_token) or self._said(st, d.address)):
            out["address"] = FieldState("stated", d.address, d.address_token or d.address)
        elif d.address and k.address and norm_value(d.address) == norm_value(k.address):
            out["address"] = FieldState("known", d.address, d.address_token or k.address_token)
        elif not d.address and k.address:
            out["address"] = FieldState("known", k.address, k.address_token)
        else:
            out["address"] = FieldState("missing")
        # thanh toán
        said_pay = detect_payment(" ".join(st.texts))
        cand = d.payment
        if said_pay and (not cand or cand == said_pay):
            out["payment"] = FieldState("stated", said_pay, said_pay)
        elif said_pay and cand and cand != said_pay:
            out["payment"] = FieldState("missing")                 # LLM điền khác điều khách nói → hỏi lại cho chắc
        elif cand and k.payment and cand == k.payment:
            out["payment"] = FieldState("known", cand, cand)
        elif not cand and k.payment:
            out["payment"] = FieldState("known", k.payment, k.payment)
        else:
            out["payment"] = FieldState("missing")                 # mặc định "COD" của LLM mà khách chưa nói
        for key, fs in out.items():
            if fs.status == "known" and (st.confirmed.get(key) == norm_value(fs.value) or (key == "recipient_phone" and st.phone_ok)):
                fs.status = "confirmed"
        return out

    @staticmethod
    def _snapshot(fields: Dict[str, FieldState]) -> Dict[str, str]:
        return {k: norm_value(v.value) for k, v in fields.items()}

    # --- dựng câu
    @staticmethod
    def _readback(addr: str, fields: Dict[str, FieldState], p: ProductInfo, d: OrderDraft, total: Optional[int]) -> str:
        qty = int(fields["qty"].value or 1)
        item = (p.name + (f" {p.variant_label}" if p.variant_label else "")).strip() or d.sku
        price = f", giá {money(p.unit_price)} một sản phẩm" if p.unit_price else ""
        tot = f", tổng {money(total)}" if total else ""
        pay = PAYMENT_LABEL.get(fields["payment"].value or "", fields["payment"].value or "")
        return (f"Dạ em đọc lại đơn mình nhé: {qty} {item}{price}{tot}; giao cho {fields['recipient_name'].shown}, số điện thoại "
                f"{fields['recipient_phone'].shown}, địa chỉ {fields['address'].shown}; {pay}. {addr[:1].upper() + addr[1:]} xác nhận đặt đơn này giúp em nhé?")

    @staticmethod
    def _confirm_and_ask(addr: str, fields: Dict[str, FieldState], to_confirm: List[str], asks: List[str]) -> str:
        parts = []
        if to_confirm:
            bits = []
            if "recipient_name" in to_confirm:
                bits.append(f"giao cho {fields['recipient_name'].shown}")
            if "recipient_phone" in to_confirm:
                bits.append(f"số điện thoại {fields['recipient_phone'].shown}")
            if "address" in to_confirm:
                bits.append(f"địa chỉ {fields['address'].shown}")
            if "payment" in to_confirm:
                bits.append(PAYMENT_LABEL.get(fields["payment"].value or "", fields["payment"].value or ""))
            parts.append("Dạ em xin xác nhận lại: " + ", ".join(bits) + ", đúng không ạ?")
        nouns = [ASK[a] for a in asks if a != "item"]
        if nouns:
            parts.append(("Dạ " if not parts else "") + "mình cho em xin " + " và ".join(nouns) + " ạ?")
        if "item" in asks:
            parts.append(("Dạ " if not parts else "") + ASK["item"] + " ạ?")       # "mình chọn size và màu nào ạ?" (câu riêng, không ghép vào "cho em xin …")
        return " ".join(parts)

    @staticmethod
    def _rephrase_ask(addr: str, asks: List[str]) -> str:
        """Lần hỏi LẠI (khách chưa trả lời được): nói rõ chưa ghi nhận được gì và đưa ví dụ định dạng, không lặp nguyên câu cũ."""
        labels = " và ".join(LABEL_SHORT[a] for a in asks)
        ex = "; ".join(f"{LABEL_SHORT[a]}: {EXAMPLE[a]}" for a in asks)
        return f"Dạ em chưa ghi nhận được {labels} ạ. {addr[:1].upper() + addr[1:]} nhắn lại giúp em theo mẫu — {ex} — nhé?"

    def block(self, sid: str, action: str, say: str, must_contain: Optional[List[str]] = None, **extra: Any) -> Dict[str, Any]:
        """Ghi một quyết định CHẶN do bên ngoài gate phát hiện (giá khách đề nghị khác bảng giá, hết hàng…): đơn nháp không được mở/tiếp tục."""
        st = self.state(sid)
        st.stage, st.snapshot, st.pending_confirm, st.readback_turn = "collect", None, None, None
        st.ask_streak, st.last_ask_key, st.last_ask_turn = 0, None, None
        st.abandoned_turn = st.turn
        dec = {"turn": st.turn, "fields": {}, "allow": False, "action": action, "missing": [], "to_confirm": [], "say": say, "must_contain": must_contain or [], **extra}
        return self._record(st, dec)

    # --- đánh giá một lần gọi order.create
    def evaluate(self, sid: str, draft: OrderDraft, known: OrderKnown, product: ProductInfo, addressing: str = "anh/chị",
                 addr_stated: Optional[Callable[[Optional[str]], bool]] = None, total: Optional[int] = None) -> Dict[str, Any]:
        st = self.state(sid)
        if not self.enabled:
            return {"allow": True, "action": "allow", "turn": st.turn, "fields": {}}
        fields = self._fields(st, draft, known, product, addr_stated or (lambda tok: False))
        snap = self._snapshot(fields)
        missing = [f for f in ASK_ORDER if fields[f].status == "missing"]
        to_confirm = [f for f in FIELDS if fields[f].status == "known"]
        report = {f: {"status": fields[f].status, "shown": fields[f].shown if fields[f].status != "missing" else None} for f in FIELDS}
        base = {"turn": st.turn, "fields": report}

        if missing or to_confirm:
            asks = missing[:2]
            action = "ask_confirm" if (asks and to_confirm) else ("confirm" if to_confirm else "ask")
            key = (action, tuple(asks), tuple(to_confirm))
            if st.last_ask_key == key and st.last_ask_turn == st.turn - 1:
                st.ask_streak += 1                                # cùng một câu hỏi ở lượt liền trước mà khách vẫn chưa trả lời được
            elif not (st.last_ask_key == key and st.last_ask_turn == st.turn):
                st.ask_streak = 0
            st.last_ask_key, st.last_ask_turn = key, st.turn
            st.stage, st.snapshot = "collect", None
            if st.ask_streak >= 2:                                 # hỏi 3 lần vẫn không được: dừng, không lặp mãi (lỗi lặp câu trên UI)
                st.abandoned_turn = st.turn
                st.pending_confirm, st.ask_streak, st.last_ask_key, st.last_ask_turn = None, 0, None, None
                labels = " và ".join(LABEL_SHORT[a] for a in asks) or "thông tin đặt đơn"
                say = (f"Dạ em chưa ghi nhận được {labels} ạ. {addressing[:1].upper() + addressing[1:]} cứ nhắn/gọi lại khi tiện, em giữ giúp thông tin sản phẩm cho mình nhé!")
                dec = {**base, "allow": False, "action": "give_up", "missing": missing, "to_confirm": to_confirm, "say": say, "must_contain": []}
                return self._record(st, dec)
            if st.ask_streak == 1 and asks:
                say = self._rephrase_ask(addressing, asks)
            else:
                say = self._confirm_and_ask(addressing, fields, to_confirm, asks)
            if to_confirm:
                st.pending_confirm = {"turn": st.turn, "values": {f: norm_value(fields[f].value) for f in to_confirm}}
            must = [MUST_WORD[a] for a in asks] + (["dung khong"] if to_confirm else [])
            dec = {**base, "allow": False, "action": action, "missing": missing, "to_confirm": to_confirm, "say": say, "must_contain": must}
            return self._record(st, dec)

        if st.stage == "consented" and st.snapshot == snap:
            st.stage, st.created = "done", {"snapshot": snap, "turn": st.turn, "real": {k: v.value for k, v in fields.items()}}
            return self._record(st, {**base, "allow": True, "action": "allow"})
        if st.stage == "done" and st.snapshot == snap:
            return self._record(st, {**base, "allow": True, "action": "allow"})
        if st.stage == "readback" and st.snapshot == snap and st.readback_turn == st.turn and st.last_decision:
            return self._record(st, copy.deepcopy(st.last_decision))   # cùng lượt gọi lại: giữ nguyên câu đã đọc
        say = self._readback(addressing, fields, product, draft, total)
        st.stage, st.snapshot, st.readback_turn = "readback", snap, st.turn
        dec = {**base, "allow": False, "action": "readback", "missing": [], "to_confirm": [], "say": say,
               "must_contain": ([money(total)] if total else []) + ["xac nhan"], "retry_with_same_args": True}
        return self._record(st, dec)

    def _record(self, st: GateState, dec: Dict[str, Any]) -> Dict[str, Any]:
        st.last_decision = dec
        st.events.append(dict(dec))
        return dec

    # --- ép câu trả lời có nội dung cần nói
    @staticmethod
    def enforce_reply(text: str, decision: Dict[str, Any]) -> str:
        """Nếu câu LLM không chứa nội dung bắt buộc của lượt bị chặn (câu hỏi/xác nhận/đọc lại đơn) → nối `say` do code dựng."""
        if not decision or decision.get("allow", True):
            return text
        f = fold(text)
        ok = all(fold(m) in f for m in decision.get("must_contain", []))
        if decision.get("action") == "readback":
            ok = ok and "xac nhan" in f
        if ok:
            return text
        # Bỏ các câu của LLM đã nói dở về đúng việc gate sắp hỏi (tránh "xác nhận lại… xác nhận lại… ạ ạ?") rồi nối câu của gate
        keep = [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x and not _GATE_TOPIC.search(fold(x))]
        return " ".join(keep + [decision["say"]]).strip()

    def summary_for_history(self, sid: str, retry_args: Optional[Dict[str, Any]] = None) -> str:
        """Dòng tóm tắt đưa vào lịch sử cho lượt sau (LLM thấy tình trạng gate và biết phải gọi lại order.create thế nào)."""
        st = self.state(sid)
        ev = st.events[-1] if st.events else None
        if not ev or ev.get("allow"):
            return ""
        if ev["action"] == "readback":
            return ("[order_gate] ĐÃ đọc lại đơn cho khách, đơn CHƯA được tạo. Nếu khách đồng ý RÕ RÀNG ở lượt tiếp theo → gọi lại order.create với ĐÚNG "
                    f"tham số cũ ({retry_args}); nếu khách sửa thông tin/hỏi thêm → xử lý, rồi gọi order.create với tham số mới (sẽ đọc lại).")
        if ev["action"] in ("price_mismatch", "out_of_stock", "give_up"):
            return f"[order_gate] đơn CHƯA tạo và đơn nháp đã HỦY ({ev['action']}); chỉ gọi lại order.create khi khách chốt lại với mức giá/sản phẩm hợp lệ."
        return f"[order_gate] đơn CHƯA tạo, đang {ev['action']} (thiếu: {ev.get('missing')}, cần xác nhận: {ev.get('to_confirm')}); chờ khách trả lời rồi gọi lại order.create."


def with_order_gate_params(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """BẢN SAO tools schema cho LLM: thêm `recipient_name`/`recipient_phone` (chỉ dùng cho gate; được gỡ trước khi gọi MCP và trước khi ghi trace)."""
    out = copy.deepcopy(tools)
    for t in out:
        fn = t.get("function", {})
        if fn.get("name", "").replace("__", ".") == "order.create":                     # tên gửi OpenAI dùng '__' thay '.'
            props = fn["parameters"]["properties"]
            props.setdefault("recipient_name", {"type": "string", "description": "Tên người nhận hàng — CHỈ điền khi khách đã NÓI trong cuộc gọi này"})
            props.setdefault("recipient_phone", {"type": "string", "description": "SĐT người nhận nếu KHÁC số đang gọi (truyền nguyên token <PHONE_n>); bỏ trống nếu nhận bằng số đang gọi"})
    return out


# ---------------------------------------------------------------------------------------------------- bộ điều khiển đơn (không cần LLM)
_NAME_PREFIX = re.compile(r"(?i:tên(?:\s+người\s+nhận)?(?:\s+(?:anh|chị|em|tôi|mình|cháu))?(?:\s+là)?|người\s+nhận(?:\s+là)?|giao\s+cho|gửi\s+cho)\s+(?:(?i:anh|chị|cô|chú|bác|em)\s+)?")


_NON_NAME = frozenset("""dung roi ok oke okay vang da nhe nha nhen a ah khong chua co cod chuyen khoan thanh toan tien mat momo zalopay bank ck sdt so nay dien thoai
giao hang nhan gui cho de se ma thi la muon can toi tui gia mac dat re bao nhieu sao gi xem them doi huy thoi luon khac size mau dia chi
dong y chot len don xac nhan u uh um uhm hm hmm oi ua vay the nua day kia do""".split())
_ADDR_CUE = re.compile(r"(?i)\b(?:duong|pho|phuong|xa|quan|huyen|tinh|thanh pho|tp|khu pho|to dan pho|ngo|ngach|hem|kiet|thon|xom|chung cu|toa)\b")


def _fold_ascii(t: str) -> str:
    return fold(t)


def _name_from_segment(seg: str) -> Optional[str]:
    """Đoạn câu (giữa hai dấu phẩy) trông như MỘT TÊN NGƯỜI: 1–4 từ chữ cái, không phải từ đồng ý/thanh toán/địa chỉ/số. Viết thường cũng nhận (khách gõ chat)."""
    seg = seg.strip()
    if not seg or re.search(r"\d", seg) or detect_payment(seg) or _ADDR_CUE.search(_fold_ascii(seg)):
        return None
    toks = re.findall(r"[^\W\d_]+", seg)
    while toks and _fold_ascii(toks[-1]) in ("a", "nhe", "nha", "nhen", "da", "vang"):          # bỏ từ đệm cuối câu ("Nguyễn Thu ạ", "Đại nhé")
        toks.pop()
    if not (1 <= len(toks) <= 4) or len(re.findall(r"[^\s,]+", seg)) > len(toks) + 2:            # chỉ chấp nhận câu gần như toàn là tên
        return None
    if any(_fold_ascii(t) in _NON_NAME for t in toks) or any(len(t) < 2 for t in toks):        # "ừ", "ờ", "à"… không phải tên
        return None
    return " ".join(t.capitalize() for t in toks)


def extract_recipient_name(text: str, name_pending: bool = False) -> Optional[str]:
    """Tên người nhận khách VỪA NÓI. Hai đường: (1) có cụm dẫn ("tên người nhận là Thu", "giao cho chị Hoa", "tôi tên Đại") → lấy tên ngay sau đó (cần viết hoa,
    trừ khi gate đang chờ tên); (2) gate ĐANG CHỜ tên → lấy đoạn câu trông như tên người (kể cả viết thường, hay đứng CUỐI câu địa chỉ: "…hồ chí minh, Đại";
    hay đứng cạnh thanh toán: "đại, COD"). Không đoán khi gate không chờ tên và không có cụm dẫn."""
    text = text or ""
    m = _NAME_PREFIX.search(text)
    if m:
        toks = re.findall(r"[^\s,.;:!?]+", text[m.end():])
        out = []
        for t in toks[:5]:
            if t.isalpha() and (t[0].isupper() or name_pending) and _fold_ascii(t) not in _NON_NAME:
                out.append(t)
            else:
                break
        if out:
            return " ".join(w.capitalize() if w.islower() else w for w in out)
    if not name_pending:
        return None
    cands = [n for n in (_name_from_segment(seg) for seg in re.split(r"[,;.!?\n]+", text)) if n]
    return cands[-1] if cands else None                                    # tên thường đứng CUỐI ("…, Đại")


_DECLINE = re.compile(r"(?<!\w)(?:(?:không|chưa|đừng)\s+(?:mua|lấy|cần|muốn|đặt)|thôi|để sau|gọi lại sau|sẽ gọi lại|gọi lại sau|để (?:tôi|mình|anh|chị|em)?\s*(?:suy nghĩ|cân nhắc|xem lại|xem thêm|hỏi)|"
                      r"chưa đủ tiền|không đủ tiền|hết tiền|đợi (?:vài|lương|mấy)|chờ (?:vài|lương|mấy)|hủy|huỷ|mắc quá|đắt quá|cao quá|hơi mắc|hơi đắt|giảm thêm|bớt thêm|bớt chút|giảm chút|"
                      r"không,? mắc|chưa cần|hiện tại chưa|hiện chưa|tạm thời chưa)(?!\w)", re.I)


def is_decline(text: str) -> bool:
    """Khách từ chối/mặc cả/hẹn lại ("mắc quá, giảm thêm 90k", "chưa cần, sẽ gọi lại sau", "chưa đủ tiền") → đang có đơn nháp thì HỦY, không hỏi tiếp địa chỉ/tên."""
    return bool(_DECLINE.search(text or ""))


_QUESTION = re.compile(r"(?<!\w)(?:bao nhiêu|bao lâu|thế nào|ra sao|mấy|tại sao|vì sao|có\b[^.?!]{0,40}\bkhông|được không|hay không)(?!\w)", re.I)
_CHANGE_CUE = re.compile(r"(?<!\w)(?:đổi|thôi|hủy|huỷ|khác|size|màu|cỡ|thêm|bớt|rẻ hơn|không mua|không lấy|giảm giá)(?!\w)", re.I)


def has_question(text: str) -> bool:
    return "?" in (text or "") or bool(_QUESTION.search(text or ""))


def is_pure_gate_reply(text: str) -> bool:
    """Lượt khách CHỈ trả lời câu hỏi/xác nhận của gate (không hỏi thêm, không đổi/thêm sản phẩm) → code tự xử lý, không cần LLM."""
    return not has_question(text) and not _CHANGE_CUE.search(text or "")
