"""
Bộ trích bộ nhớ 2 tầng (bước 9) — thay cho việc nạp đáp án `facts_established` của kịch bản:

TẦNG 1 — SLOT DỄ, REGEX, CHẠY MỖI LƯỢT, KHÔNG GỌI LLM (`extract_easy_slots`):
  diện tích phòng, có trẻ nhỏ, ngân sách (khi có từ khóa "ngân sách/tầm giá/dưới/tối đa"), size, màu, hẹn gọi lại.

TẦNG 2 — SLOT KHÓ, LLM, CHỈ Ở 3 THỜI ĐIỂM KÍCH HOẠT (`CallFinalizer`):
  (1) cuối cuộc gọi (`end`), (2) khi chuyển máy/escalate (`handoff`), (3) khi cuộc gọi bị ngắt/timeout (`timeout`).
  Mỗi thời điểm gọi LLM TỐI ĐA 1 LẦN; nếu đã trích ở lúc chuyển máy thì lúc cuối cuộc chỉ trích PHẦN HỘI THOẠI MỚI.
  Slot khó: blocker, ngân sách (nêu gián tiếp), giá đối thủ, phản đối (objection), mục tiêu cuộc gọi.
  Mọi giá trị LLM trả về đều được KIỂM CHỨNG bằng lời khách (số phải xuất hiện trong lời khách), che PII, kiểm kiểu.

Cả hai tầng đều ghi fact kèm provenance (source_call, source_turn, source_channel). Mỗi thời điểm kích hoạt còn
tự ghi/ cập nhật EPISODE của cuộc gọi (upsert theo session). Cấu hình `baseline_no_memory` KHÔNG chạy tầng 2
(không finalize) — baseline chỉ khác ở việc không có bộ nhớ xuyên cuộc gọi.
"""
import os
import re
import unicodedata
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.common.money import extract_amounts, numbers_in
from src.memory.episodic import EpisodeRecord

logger = logging.getLogger("harness.memory")

# TTL (ngày) cho từng loại fact — áp khi ĐỌC theo ngày cuộc gọi.
SLOT_TTL = {"room_area_m2": 180, "budget_vnd": 90, "size": 180, "color": 180, "callback_at": 14,
            "blocker": 60, "competitor_price_vnd": 30, "objection": 60}

COLORS = ["den", "trang", "xam", "xanh", "do", "vang", "hong", "nau", "tim", "cam", "be", "kem", "bac"]
_COLOR_RE = re.compile(r"màu\s+(\w+)", re.I)
_SIZE_RE = re.compile(r"(?:\bsize|\bsz|\bcỡ)\s*(\d{2}(?![.,]?\d)|XXL|XL|S|M|L)\b", re.I)   # không nhận '20' trong 'size 20.000' 
_BUDGET_KEYWORD = re.compile(r"(?:ngân sách|tầm giá|budget|dưới|tối đa|không quá|nhiều nhất)", re.I)


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Xưng hô: cách khách TỰ xưng ("anh muốn hỏi…", "cho chị hỏi…"). "em" chỉ nhận với động từ không thể là lời gọi nhân viên
# ("em muốn/cần/định/mua/lấy/đặt/tên" — còn "em có/giúp/nói…" là khách gọi nhân viên bằng em).
_HON_SELF_VERBS = (r"muốn|cần|định|đang|vừa|mới|hỏi|mua|lấy|đặt|gọi|nhắn|ở|thích|tên|không biết|chưa biết|đã nhắn|đã hỏi|đã mua|đã đặt|"
                   r"có nhu cầu|quan tâm|tìm|xem|nghe|thấy|là khách")
_HON_EM_VERBS = r"muốn|cần|định|mua|lấy|đặt|tên|tìm|quan tâm"
_HON_SELF = re.compile(rf"(?<!\w)(anh|chị|cô|chú|bác)\s+(?:{_HON_SELF_VERBS})(?!\w)", re.I)
_HON_EM = re.compile(rf"(?<!\w)(em)\s+(?:{_HON_EM_VERBS})(?!\w)", re.I)
_HON_CHO = re.compile(r"(?<!\w)(?:cho|giúp|với)\s+(anh|chị|cô|chú|bác)\s+(?:hỏi|xem|đặt|lên|biết|một|được|thêm)(?!\w)", re.I)


def detect_self_honorific(text: str) -> Optional[str]:
    """Từ xưng hô khách dùng cho CHÍNH MÌNH (lần nhắc cuối trong câu), hoặc None. Không đoán từ tên/giới tính."""
    found: List[Tuple[int, str]] = []
    for rx in (_HON_SELF, _HON_EM, _HON_CHO):
        for m in rx.finditer(text or ""):
            found.append((m.start(), m.group(1).lower()))
    return max(found)[1] if found else None


# Giá nơi khác: cụm chỉ cửa hàng/sàn khác + số tiền ngay sau đó, trừ khi số tiền là mức CHÊNH ("rẻ hơn 500k").
_COMP_CUE = re.compile(r"(?:(?:bên|chỗ|ở|tại)\s+(?:shop|cửa hàng|tiệm|nơi|chỗ|hàng|đại lý)?\s*(?:khác|kia|nọ|đó)|shop\s+(?:khác|kia|nọ)|cửa hàng\s+(?:khác|kia|nọ)|nơi khác|chỗ khác|đối thủ|"
                       r"shopee|lazada|tiki|tiktok\s*shop|thế giới di động|điện máy xanh|nguyễn kim|fpt shop|cellphones|hoàng hà|điện máy chợ lớn)", re.I)
_COMP_DIFF = re.compile(r"(?:rẻ hơn|thấp hơn|giảm|bớt|chênh|kém hơn|kém)\s*(?:khoảng|tầm|gần)?\s*\d[\d.,]*\s*(?:triệu|tr|nghìn|ngàn|k|đ|đồng)?(?:\s*\d{1,3}\b)?", re.I)


def extract_competitor_price(text: str) -> Optional[int]:
    """Giá nơi khác khách nêu ("bên shop kia có 300k"). Bỏ số tiền là mức CHÊNH ("rẻ hơn 500k") — đó không phải giá."""
    for m in _COMP_CUE.finditer(text or ""):
        seg = text[m.end(): m.end() + 70]
        stop = re.search(r"[.!?](?:\s|$)", seg)                  # dấu chấm trong "4.500.000" không phải hết câu
        seg = _COMP_DIFF.sub(" ", seg[: stop.start()] if stop else seg)
        for value, _approx in extract_amounts(seg):
            if value >= 50_000:
                return int(value)
    return None


# Tên khách tự giới thiệu ("tôi tên Đại", "mình tên là Lan", "gọi tôi là Nam"). Chỉ nhận cụm "tên …" — KHÔNG nhận "tôi là …" ("tôi là vị khách hôm 15/10…").
_NAME_SELF = re.compile(r"(?i:(?:tôi|mình|em|anh|chị|cháu|tui)\s+tên(?:\s+là)?|tên\s+(?:của\s+)?(?:tôi|mình|em|anh|chị|cháu|tui)\s+là|gọi\s+(?:tôi|mình|em|anh|chị)\s+là)\s+")
_NAME_STOP = {"chi", "anh", "em", "toi", "minh", "tui", "cau", "la", "o", "va", "nhe", "nha", "a", "ah", "de", "se", "muon", "can", "dang", "da", "vua", "moi", "hoi", "mua", "lay", "dat", "goi", "nhan", "co", "khong"}


def extract_customer_name(text: str) -> Optional[str]:
    """Tên khách TỰ nói ("tôi tên Đại" → "Đại"); viết hoa/thường đều nhận (khách gõ chat), trả về dạng viết hoa chữ đầu mỗi từ."""
    last = None
    for m in _NAME_SELF.finditer(text or ""):
        last = m
    if last is None:
        # "Tôi là Đại, hôm trước…": chỉ nhận khi tên VIẾT HOA, đứng sát dấu câu/hết câu (để không nhầm "tôi là vị khách…", "anh là người…")
        for m in re.finditer(r"(?i:tôi|mình|em|anh|chị|cháu|tui)\s+là\s+((?:[^\W\d_]+\s*){1,3})(?=[,.;!?]|$)", text or ""):
            toks = m.group(1).split()
            if toks and all(t[0].isupper() for t in toks) and _fold(toks[0]) not in ("khach", "vi", "nguoi", "mot", "chu", "nhan"):
                return " ".join(toks)
        return None
    out = []
    rest = re.split(r"[,.;:!?]", text[last.end():], maxsplit=1)[0]          # tên dừng ở dấu câu đầu tiên ("Chị tên Lan, chị hỏi…" → "Lan", không phải "Lan Chị")
    for t in re.findall(r"\S+", rest)[:4]:
        if not t.isalpha() or _fold(t) in _NAME_STOP:
            break
        out.append(t.capitalize())
    return " ".join(out) or None


# Rào cản (blocker) và phản đối (objection) khách nêu ngay trong lượt — để Call Brief cập nhật TỨC THÌ (không đợi bộ trích LLM cuối cuộc gọi).
# Mã blocker viết không dấu theo quy ước của BTC ("can hoi chong", "so sanh gia"…).
_BLOCKER_RULES = [
    ("can hoi chong", r"hỏi\s+(?:ý\s+)?(?:chồng|ông xã)"),
    ("can hoi vo", r"hỏi\s+(?:ý\s+)?(?:vợ|bà xã)"),
    ("can hoi nguoi nha", r"hỏi\s+(?:ý\s+)?(?:bố mẹ|ba mẹ|người nhà|gia đình|cả nhà)"),
    ("chua du tien", r"chưa đủ tiền|không đủ tiền|hết tiền|chưa có tiền|đợi lương|chờ lương|để dành|(?:đợi|chờ)\s+(?:vài|mấy)\s+(?:hôm|ngày|tuần|tháng)"),
    ("so sanh gia", r"xem\s+(?:thêm\s+)?(?:chỗ|bên|shop|nơi)\s+khác|so sánh|hỏi\s+(?:chỗ|bên|shop)\s+khác"),
    ("de suy nghi", r"để\s+(?:tôi|mình|anh|chị|em)?\s*(?:suy nghĩ|cân nhắc|xem lại|xem thêm)|(?:sẽ\s+)?gọi lại sau|để sau|chưa cần|hiện (?:tại )?chưa|tạm thời chưa"),
]
_OBJECTION = re.compile(r"(?<!\w)(?:mắc|đắt|cao quá|hơi cao|giảm\s+(?:thêm|chút|giá)|bớt\s+(?:chút|thêm)|rẻ hơn)(?!\w)", re.I)


def detect_blocker(text: str) -> Optional[str]:
    for code, rx in _BLOCKER_RULES:
        if re.search(rx, text or "", re.I):
            return code
    return None


def detect_bargain(text: str) -> Optional[Dict[str, Any]]:
    """Khách MẶC CẢ: xin giảm ("giảm thêm 90k", "bớt chút"), chê mắc/đắt, hoặc đưa mức giá riêng ("6tr8 lấy luôn"). Trả {kind, amount?} hoặc None."""
    t = text or ""
    m = re.search(r"(?i)(?:giảm|bớt)\s+(?:thêm\s+|chút\s+)?(?=\d)", t)
    if m:
        amounts = extract_amounts(t[m.end(): m.end() + 24])
        return {"kind": "ask_discount", "amount": amounts[0][0] if amounts else None}
    if re.search(r"(?i)(?:lấy luôn|chốt luôn|lấy nhé|được không|thôi nhé)", t):
        amounts = [a for a, _ in extract_amounts(t) if a >= 50_000]
        if amounts and _OBJECTION.search(t) or (amounts and re.search(r"(?i)lấy luôn|chốt luôn", t)):
            return {"kind": "offer_price", "amount": amounts[0]}
    if _OBJECTION.search(t):
        return {"kind": "objection", "amount": None}
    return None


def extract_easy_slots(text: str, entities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Slot dễ bằng regex trên câu khách (đã chuẩn hóa ITN). Không gọi LLM."""
    entities = entities or {}
    out: Dict[str, Any] = {}
    cname = extract_customer_name(text)
    if cname:
        out["customer_name"] = cname
    blk = detect_blocker(text)
    if blk:
        out["blocker"] = blk
    if _OBJECTION.search(text or ""):
        out["objection"] = "gia cao"
    hon = detect_self_honorific(text)
    if hon:
        out["honorific"] = hon
    comp = extract_competitor_price(text)
    if comp:
        out["competitor_price_vnd"] = comp
    if "room_area_m2" in entities:
        out["room_area_m2"] = entities["room_area_m2"]
    if entities.get("has_children"):
        out["has_children"] = True
    text = text or ""
    # ngân sách: số tiền đứng NGAY SAU từ khóa ngân sách ("giảm 500.000" không bị nhầm)
    m = _BUDGET_KEYWORD.search(text)
    if m:
        amounts = extract_amounts(text[m.end(): m.end() + 40])
        if amounts and amounts[0][0] >= 100_000:
            out["budget_vnd"] = amounts[0][0]
    for m in _SIZE_RE.finditer(text):
        token = m.group(1)
        if token.isdigit():
            if not 18 <= int(token) <= 50:        # cỡ giày/quần áo hợp lý; '20' đứng trước 'nghìn/k' là tiền, không phải cỡ
                continue
            if re.match(r"\s*(?:nghìn|ngàn|k\b|đ\b|đồng|tr\b|triệu)", text[m.end():], re.I):
                continue
        out["size"] = token.upper() if not token.isdigit() else token
        break
    for m in _COLOR_RE.finditer(text):
        folded = _fold(m.group(1))
        if folded in COLORS:
            out["color"] = folded               # không dấu, thống nhất với màu parse từ variant SKU (…-DEN -> 'den')
            break
    hint = entities.get("callback_hint")
    if hint:
        out["callback_at"] = " ".join(v for v in (hint.get("date"), hint.get("time")) if v)
    return out


# ---------------------------------------------------------------- tầng 2: LLM, slot khó
HARD_SLOT_PROMPT = (
    "Bạn là bộ trích thông tin cho hệ thống telesale. Đọc hội thoại giữa khách và nhân viên (AI) và trả về DUY NHẤT "
    "một JSON object với các khóa sau (null nếu khách KHÔNG nói rõ — tuyệt đối không suy đoán, không bịa):\n"
    '  "blocker": rào cản khiến khách chưa chốt, viết ngắn không dấu (vd "can hoi chong", "so sanh gia", "cho ban be tu van"),\n'
    '  "budget_vnd": ngân sách khách nêu (số nguyên VND) hoặc null,\n'
    '  "competitor_price_vnd": giá nơi khác khách nêu (số nguyên VND) hoặc null,\n'
    '  "objection": phản đối chính của khách (câu ngắn) hoặc null,\n'
    '  "customer_goal": mục tiêu cuộc gọi trong 1 câu ngắn.\n'
    "Chỉ dựa vào lời của KHÁCH. Không chép số điện thoại, địa chỉ, CCCD, số tài khoản. Các token như <PHONE_1>, <ADDR_1>, "
    "<ID_1>, CURRENT_CUSTOMER là dữ liệu đã che — không giải mã."
)
_PII_DIGITS = re.compile(r"(?<!\d)(?!0\d{9}(?!\d))\d{9,14}(?!\d)")


def _clean_text(value: Any, limit: int = 80) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = _PII_DIGITS.sub("[REDACTED]", value.strip())
    return value[:limit] if value else None


def _grounded_amount(value: Any, customer_text: str) -> Optional[int]:
    """Số tiền do LLM trả về chỉ được nhận nếu CHÍNH số đó có trong lời khách."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = int(value)
    if value < 1000:
        return None
    return value if value in {v for v, _ in extract_amounts(customer_text)} else None


def _budget_cue_near(customer_text: str, amount: int) -> bool:
    """Khách có nói từ khóa ngân sách ('ngân sách', 'tầm giá', 'dưới', 'tối đa'…) ngay trước số tiền này không?"""
    for m in _BUDGET_KEYWORD.finditer(customer_text):
        if amount in {v for v, _ in extract_amounts(customer_text[m.end(): m.end() + 40])}:
            return True
    return False


def validate_hard_slots(raw: Dict[str, Any], customer_text: str, known_prices=()) -> Dict[str, Any]:
    """Kiểm kiểu + kiểm chứng với lời khách; bỏ mọi giá trị không hợp lệ/không có căn cứ.
    `known_prices`: giá HỆ THỐNG đã báo (từ tool/profile). Một "ngân sách" trùng đúng giá đó mà khách không nói kèm
    từ khóa ngân sách là LLM nhầm giá đã báo thành ngân sách -> bỏ (lỗi thật gặp ở bước 15 giai đoạn A)."""
    out: Dict[str, Any] = {}
    for key in ("blocker", "objection", "customer_goal"):
        v = _clean_text(raw.get(key), 120 if key == "customer_goal" else 80)
        if v:
            out[key] = v
    for key in ("budget_vnd", "competitor_price_vnd"):
        v = _grounded_amount(raw.get(key), customer_text)
        if v and key == "budget_vnd" and v in set(known_prices) and not _budget_cue_near(customer_text, v):
            v = None
        if v:
            out[key] = v
    return out


class HardSlotExtractor:
    """Gọi LLM (nếu có) để trích slot khó từ một đoạn hội thoại. `llm` cần `available` và `complete_json(messages)`."""

    def __init__(self, llm=None):
        self.llm = llm

    @property
    def enabled(self) -> bool:
        if os.environ.get("MEMORY_EXTRACTOR_LLM", "1").strip() == "0":
            return False
        return self.llm is not None and bool(getattr(self.llm, "available", False)) and hasattr(self.llm, "complete_json")

    def extract(self, messages: List[Dict[str, str]], known_prices=()) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """messages: các tin MỚI của hội thoại ({role: user|assistant, content}). Trả về (slot đã kiểm chứng, usage)."""
        customer_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if not customer_text.strip():
            return {}, None
        transcript = "\n".join(f"{'KHÁCH' if m['role'] == 'user' else 'NHÂN VIÊN'}: {m['content']}"
                               for m in messages if m.get("role") in ("user", "assistant"))
        try:
            raw, usage = self.llm.complete_json([{"role": "system", "content": HARD_SLOT_PROMPT},
                                                 {"role": "user", "content": transcript}])
        except Exception as e:          # LLM lỗi -> bỏ phần trích khó, không làm hỏng việc chốt cuộc gọi
            logger.warning("[MEMORY] trích slot khó bằng LLM lỗi (%s) — bỏ qua.", e)
            return {}, None
        return validate_hard_slots(raw or {}, customer_text, known_prices), usage


# ---------------------------------------------------------------- chốt cuộc gọi: episode + slot khó
@dataclass
class FinalizeResult:
    trigger: str
    llm_called: bool = False
    usage: Optional[Dict[str, Any]] = None
    hard_slots: Dict[str, Any] = field(default_factory=dict)
    episode: Optional[EpisodeRecord] = None


class CallFinalizer:
    """Thực hiện bước 'chốt cuộc gọi' ở 1 trong 3 thời điểm: end | handoff | timeout."""
    TRIGGERS = ("end", "handoff", "timeout")

    def __init__(self, memory, extractor: Optional[HardSlotExtractor] = None):
        self.memory = memory
        self.extractor = extractor or HardSlotExtractor(None)
        self._progress: Dict[str, int] = {}        # session -> số tin đã được LLM trích (để lần sau chỉ trích phần mới)

    def finalize(self, *, customer_id: str, session_id: str, call_name: str, call_date: str, channel: str,
                 trigger: str, messages: List[Dict[str, str]], tool_calls: List[Dict[str, Any]],
                 goal_hint: str = "") -> FinalizeResult:
        if trigger not in self.TRIGGERS:
            raise ValueError(f"trigger phải thuộc {self.TRIGGERS}")
        result = FinalizeResult(trigger=trigger)
        mem = self.memory

        # 1) slot khó bằng LLM — tối đa 1 lần cho thời điểm này, chỉ trên phần hội thoại MỚI
        start = self._progress.get(session_id, 0)
        new_messages = [m for m in messages[start:] if m.get("role") in ("user", "assistant")]
        if new_messages and self.extractor.enabled:
            known_prices = {int(v) for v in numbers_in([tc.get("result") for tc in tool_calls]) if v}
            for fact_key in ("price_quoted_vnd",):
                fv = mem.get_profile_facts(customer_id, on_date=call_date).get(fact_key)
                if isinstance(fv, (int, float)):
                    known_prices.add(int(fv))
            slots, usage = self.extractor.extract(new_messages, known_prices)
            result.llm_called, result.usage, result.hard_slots = True, usage, slots
            self._progress[session_id] = len(messages)
            for key in ("blocker", "budget_vnd", "competitor_price_vnd", "objection"):
                if key in slots:
                    mem.set_profile_fact(customer_id, key, slots[key], ttl_days=SLOT_TTL.get(key), observed_on=call_date)

        # 2) episode của cuộc gọi (upsert theo session): dựng từ fact THẬT trong bộ nhớ + tool đã chạy
        facts = mem.get_profile_facts(customer_id, on_date=call_date)
        others = [e for e in mem.get_episodes(customer_id) if e.session_id != session_id]
        created_order = next((tc.get("result") for tc in tool_calls
                              if tc.get("name") == "order.create" and (tc.get("result") or {}).get("status") == "created"), None)
        if created_order:
            outcome = "chot_don"
        elif trigger == "handoff":
            outcome = "chuyen_may"
        elif trigger == "timeout":
            outcome = "ngat_cuoc"
        else:
            outcome = "hen_goi_lai"
        bits = [f"[{trigger}]"]
        if facts.get("product_advised"):
            bits.append(f"tư vấn {facts['product_advised']}")
        if facts.get("price_quoted_vnd"):
            bits.append(f"giá {int(facts['price_quoted_vnd']):,}đ".replace(",", "."))
        if facts.get("blocker"):
            bits.append(f"blocker: {facts['blocker']}")
        if created_order:
            bits.append(f"đơn {created_order.get('order_id')}")
        episode = EpisodeRecord(
            session_id=session_id, call_index=len(others) + 1, call_date=call_date, channel=channel or "hotline",
            customer_goal=result.hard_slots.get("customer_goal") or goal_hint,
            product_advised=facts.get("product_advised"), price_quoted_vnd=facts.get("price_quoted_vnd"),
            promo_code=facts.get("promo_code"), promo_expiry=facts.get("promo_expiry"), blocker=facts.get("blocker"),
            outcome=outcome, summary="; ".join(bits))
        mem.add_episode(customer_id, episode)
        result.episode = episode
        return result

    def forget_session(self, session_id: str) -> None:
        self._progress.pop(session_id, None)
