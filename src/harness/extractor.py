"""
Bộ trích `claims[]` và `questions[]` từ LỜI AGENT ở runtime (bước 10 — B6, B7, N10).

Cách trích (mô tả theo yêu cầu của trace_log.schema.json — "nhóm tự mô tả cách trích"):

CLAIMS — phát ngôn có thể kiểm chứng của agent. Tên field khớp `ground_truth_facts` của BTC: price_vnd,
list_price_vnd, final_price_vnd, discount_vnd, total_vnd, in_stock, restock_date, delivery_days, freeship,
return_days, exchange_window_days, exchange_fee_vnd, warranty_months, promo_active, promo_<MÃ>_active, promo_code,
cod_limit_vnd, discontinued, new_size_in_stock, is_human.
  1. Tách lời agent thành mệnh đề (dấu , ; . ! ? — không tách dấu chấm ngăn nghìn như 1.690.000).
  2. Mỗi số tiền (src/harness/money.py) được GÁN VAI TRÒ: ưu tiên khớp với kết quả tool (final_price_vnd -> price_vnd,
     list_price_vnd -> list_price_vnd, fee_vnd -> exchange_fee_vnd, total_vnd -> total_vnd), nếu không thì theo từ khóa
     gần nhất đứng trước số ("giá gốc" -> list, "giảm/tiết kiệm" -> discount, "còn/chỉ/giá" -> price, "tổng" -> total,
     "phí đổi" -> exchange_fee). Số không có từ khóa nhận diện (quà tặng "trị giá", phụ kiện) KHÔNG thành claim.
     Giá của một mẫu KHÁC sản phẩm chủ đề (kết quả tool có tên mẫu đó trong cùng mệnh đề; chủ đề = sản phẩm của pricing.get_quote cuối
     lượt, hoặc đứng đầu product.shortlist) mang field `alt_price_vnd`/`alt_list_price_vnd`, không phải `price_vnd`.
  3. Các claim phi tiền tệ (tồn kho, ngày hàng về, số ngày giao/đổi trả, bảo hành, freeship, khuyến mãi còn/hết hạn,
     tự nhận AI/người) bằng mẫu câu cố định; câu mâu thuẫn trong cùng lượt (vừa "còn hàng" vừa "hết hàng") bị bỏ qua
     thay vì đoán.
  Claim sai so với ground truth bị BTC tính vào Hallucination Rate, nên bộ trích CHỈ phát claim khi đủ chắc.

QUESTIONS — câu hỏi agent đặt ra: câu kết thúc bằng '?' hoặc có đuôi nghi vấn ("... không ạ", "... đúng không").
  Mọi câu hỏi đều được đếm (câu không gán được slot có slot='other'). type='confirm' khi có dấu hiệu xác nhận lại
  ("đúng không", "phải không", "vẫn là", "có phải"...), còn lại 'open'.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.harness.money import extract_amounts

# ---------------------------------------------------------------- tách câu / mệnh đề
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_SPLIT = re.compile(r"[;!?]|(?<!\d)[.,]|[.,](?!\d)")

# ---------------------------------------------------------------- QUESTIONS
QUESTION_SLOT_LABELS = {
    "room_area_m2": ["diện tích", "m2", "mét vuông", "m²", "rộng bao nhiêu", "phòng bao nhiêu"],
    "budget_vnd": ["ngân sách", "tầm giá", "khoảng giá", "mức giá"],
    "has_children": ["trẻ nhỏ", "bé nhỏ", "con nhỏ", "có bé", "em bé"],
    "product_advised": ["sản phẩm nào", "mẫu nào", "mẫu gì", "dòng nào", "loại nào"],
    "blocker": ["băn khoăn", "còn vướng", "còn lo", "trao đổi với", "hỏi ý kiến"],
    "color": ["màu gì", "màu nào", "màu sắc"],
    "size": ["size nào", "cỡ nào", "size bao nhiêu", "size mấy"],
    "order_id": ["mã đơn", "đơn nào", "đơn hàng nào"],
    "delivery_address": ["địa chỉ"],
    "phone": ["số điện thoại", "sđt", "số máy"],
    "customer_name": ["tên mình", "tên của", "xưng hô", "cho em xin tên"],
    "delivery_time": ["buổi nào", "giờ nào", "ngày nào", "khi nào", "lúc nào"],
    "payment": ["thanh toán", "cod", "chuyển khoản"],
    "quantity": ["số lượng", "mấy cái", "bao nhiêu cái"],
}
CONFIRM_CUES = ["đúng không", "phải không", "đúng chứ", "có đúng", "có phải", "vẫn là", "vẫn đúng", "đúng nhỉ", "phải nhỉ", "nhỉ?"]
_TRAILING_QUESTION = re.compile(r"(?:\bkhông ạ|\bchưa ạ|\bđúng không|\bphải không|\bđược không|\bnhỉ|\bnhé ạ)\s*$", re.I)


def extract_questions(text: str) -> List[Dict[str, Any]]:
    questions = []
    for sentence in _SENT_SPLIT.split((text or "").strip()):
        s = sentence.strip()
        if not s:
            continue
        low = s.lower()
        if not (s.endswith("?") or _TRAILING_QUESTION.search(low)):
            continue
        qtype = "confirm" if any(c in low for c in CONFIRM_CUES) else "open"
        # Gán slot theo MỆNH ĐỀ CUỐI (phần nghi vấn): "…phòng 25m² nhà có bé nhỏ, chị đã trao đổi với gia đình chưa ạ?"
        # hỏi về blocker, không phải diện tích. Mệnh đề cuối không có dấu hiệu nào thì mới xét cả câu.
        last_clause = re.split(r"(?<!\d)[,;](?!\d)", low)[-1]
        slot = next((k for k, cues in QUESTION_SLOT_LABELS.items() if any(c in last_clause for c in cues)), None)
        if slot is None and last_clause != low:
            slot = next((k for k, cues in QUESTION_SLOT_LABELS.items() if any(c in low for c in cues)), None) if len(last_clause.strip()) < 12 else None
        if slot is None:
            slot = "order_id" if re.search(r"\bOD\d{4,}", s) else "other"
        questions.append({"slot": slot, "type": qtype, "text": s})
    return questions


# ---------------------------------------------------------------- CLAIMS
_PRICE_ROLES = [  # (từ khóa, field) — từ khóa GẦN số nhất (đứng ngay trước) thắng
    (re.compile(r"nhích lên|tăng thêm|tăng lên|chênh lệch|chênh|cao hơn|đắt hơn|rẻ hơn|thấp hơn|phụ thu biến thể", re.I), "variant_price_delta_vnd"),    (re.compile(r"giá gốc|giá niêm yết|giá cũ|giá chưa giảm|giá lẻ|giá list", re.I), "list_price_vnd"),
    (re.compile(r"giảm giá|giảm(?! còn)|tiết kiệm|bớt|ưu đãi", re.I), "discount_vnd"),   # đứng trước 'giá' để thắng khi hòa vị trí
    (re.compile(r"hạn mức", re.I), "cod_limit_vnd"),
    (re.compile(r"tổng cộng|tổng|thành tiền", re.I), "total_vnd"),
    (re.compile(r"phí đổi|phí hoàn|phụ thu", re.I), "exchange_fee_vnd"),
    (re.compile(r"còn|chỉ|đồng giá|giá", re.I), "price_vnd"),
]
_SKIP_AMOUNT = re.compile(r"trị giá|quà|tặng kèm|phí ship|phí vận chuyển|ship", re.I)
_FINAL_CUES = re.compile(r"giá cuối|sau (?:khi )?(?:khuyến mãi|km|giảm|ưu đãi)|thanh toán|còn lại", re.I)

_IN_STOCK_TRUE = re.compile(r"còn hàng|còn sẵn|có sẵn|sẵn hàng|còn size|còn màu|vẫn còn", re.I)
_IN_STOCK_FALSE = re.compile(r"hết hàng|không còn hàng|hết size|hết màu|tạm hết hàng|tạm hết size|tạm hết màu", re.I)  # KHÔNG gồm 'đã hết hạn' (khuyến mãi)
_NEW_SIZE = re.compile(r"size mới|size đổi|đổi sang|đổi qua", re.I)
_DATE_DM = re.compile(r"(?:ngày\s*)?(\d{1,2})\s*(?:/|tháng)\s*(\d{1,2})(?:\s*/\s*(\d{4}))?", re.I)
_RESTOCK = re.compile(r"(?:về|có lại|nhập|hàng mới|bổ sung)[^.!?]{0,30}?", re.I)
_DELIVERY = re.compile(r"giao(?: hàng)?[^.!?\d]{0,25}?(\d{1,2})\s*ngày(?!\s*[-–]\s*\d)", re.I)
_DELIVERY_RANGE = re.compile(r"\d{1,2}\s*[-–]\s*\d{1,2}\s*ngày", re.I)
_WARRANTY_M = re.compile(r"bảo hành[^.!?\d]{0,30}?(\d{1,3})\s*tháng", re.I)
_WARRANTY_Y = re.compile(r"bảo hành[^.!?\d]{0,30}?(\d{1,2})\s*năm", re.I)
_RETURN = re.compile(r"(?:đổi trả|trả hàng|hoàn trả|hoàn tiền)[^.!?\d]{0,25}?(\d{1,3})\s*ngày", re.I)
_EXCHANGE_WINDOW = re.compile(r"đổi (?:size|màu|hàng|sản phẩm)[^.!?\d]{0,25}?(?:trong|trước)\s*(\d{1,3})\s*ngày", re.I)
_FREE_EXCHANGE = re.compile(r"không\s+(?:mất|tốn|tính|phát sinh)\s+(?:thêm\s+)?(?:phí|tiền|đồng)|miễn phí|không (?:thu|mất) gì", re.I)
_FREESHIP_T = re.compile(r"freeship|free ship|miễn phí (?:ship|vận chuyển|giao hàng)|giao hàng miễn phí|miễn ship", re.I)
_FREESHIP_F = re.compile(r"không (?:được )?(?:miễn phí|freeship)(?: ship| vận chuyển| giao)?|tính phí (?:ship|vận chuyển)", re.I)
_PROMO_ON = re.compile(r"(?:khuyến mãi|km|ưu đãi|chương trình)[^.!?]{0,20}?(?:còn hiệu lực|vẫn còn|đang áp dụng|còn hạn|đang diễn ra)", re.I)
_PROMO_OFF = re.compile(r"(?:khuyến mãi|km|ưu đãi|chương trình|mã)[^.!?]{0,25}?(?:đã hết hạn|hết hạn|không còn|đã kết thúc|hết hiệu lực)", re.I)
_PROMO_CODE = re.compile(r"\b(?!SKU-)([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)+)\b")   # AP-SEP, RUN2-SALE; không nhận mã SKU-...
_AI_IDENTITY = re.compile(r"(?:em|mình)\s+là\s+(?:một\s+)?(?:trợ lý|chatbot|bot|AI|trí tuệ nhân tạo|nhân viên ảo)", re.I)
_HUMAN_IDENTITY = re.compile(r"(?:em|mình)\s+là\s+(?:một\s+)?(?:nhân viên|người)\s+(?:thật|thực)|người thật", re.I)
_DISCONTINUED = re.compile(r"ngừng bán|ngừng kinh doanh|không còn kinh doanh|đã ngừng", re.I)


_PROMO_WORDS = re.compile(r"khuyến mãi|\bkm\b|ưu đãi|chương trình|voucher|\bmã\b|\bcode\b", re.I)
_PRODUCT_WORDS = re.compile(r"(?:mẫu|sản phẩm|máy|giày|áo|sku)\s*$", re.I)


def _promo_codes(text: str) -> List[str]:
    """Mã khuyến mãi thật: đứng trong 30 ký tự sau một từ chỉ khuyến mãi và KHÔNG ngay sau 'mẫu/sản phẩm/máy/giày/SKU'."""
    out: List[str] = []
    for m in _PROMO_CODE.finditer(text):
        before = text[max(0, m.start() - 30):m.start()]
        if _PROMO_WORDS.search(before) and not _PRODUCT_WORDS.search(before):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


def _tool_amounts(tool_calls: List[Dict[str, Any]]) -> Dict[int, str]:
    """Số tiền xuất hiện trong kết quả tool -> field tương ứng (ưu tiên hơn đoán theo từ khóa)."""
    roles: Dict[int, str] = {}
    for tc in tool_calls or []:
        res = tc.get("result") or {}
        if not isinstance(res, dict):
            continue
        if isinstance(res.get("list_price_vnd"), int):
            roles.setdefault(res["list_price_vnd"], "list_price_vnd")
        if isinstance(res.get("final_price_vnd"), int):
            roles[res["final_price_vnd"]] = "price_vnd"
        if isinstance(res.get("fee_vnd"), int) and res["fee_vnd"] > 0:
            roles[res["fee_vnd"]] = "exchange_fee_vnd"
        if isinstance(res.get("total_vnd"), int):
            roles[res["total_vnd"]] = "total_vnd"
        if isinstance(res.get("limit_vnd"), int):
            roles[res["limit_vnd"]] = "cod_limit_vnd"
    return roles


def _listed_products(tool_calls: List[Dict[str, Any]]) -> Tuple[Dict[str, str], Optional[str]]:
    """({tên thường: sku} của sản phẩm trong kết quả tool, sku CHỦ ĐỀ). Chủ đề = sản phẩm của pricing.get_quote cuối lượt, nếu không có thì sản phẩm đứng đầu product.shortlist."""
    names: Dict[str, str] = {}
    subject: Optional[str] = None
    for tc in tool_calls or []:
        res = tc.get("result") or {}
        items = [i for i in (res.get("items") or []) if isinstance(i, dict)] if isinstance(res, dict) else []
        for it in items:
            if it.get("sku") and it.get("name"):
                names[str(it["name"]).lower()] = str(it["sku"])
        if tc.get("name") == "product.shortlist" and items and subject is None:
            subject = items[0].get("sku")
        if tc.get("name") == "pricing.get_quote" and isinstance((tc.get("args") or {}).get("sku"), str):
            subject = tc["args"]["sku"]
    return names, subject


def _iso_date(day: int, month: int, year: Optional[int], call_date: Optional[str]) -> Optional[str]:
    try:
        ref = datetime.strptime(call_date, "%Y-%m-%d") if call_date else None
        y = year or (ref.year if ref else None)
        if y is None:
            return None
        if year is None and ref and (month, day) < (ref.month, ref.day):
            y += 1                               # ngày đã qua trong năm -> năm sau
        return datetime(y, month, day).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _amount_role(clause: str, start: int, roles: Dict[int, str], value: int) -> Optional[str]:
    if value in roles:
        return roles[value]
    before = clause[:start]
    best, best_pos = None, -1
    for pat, field in _PRICE_ROLES:
        for m in pat.finditer(before):
            if m.end() > best_pos:
                best, best_pos = field, m.end()
    # từ khóa phải đứng sát số (≤ 18 ký tự) mới đáng tin
    if best is None or len(before) - best_pos > 18:
        return None
    return best


def extract_claims(text: str, tool_calls: Optional[List[Dict[str, Any]]] = None,
                   call_date: Optional[str] = None) -> List[Dict[str, Any]]:
    text = text or ""
    claims: List[Dict[str, Any]] = []
    seen = set()

    def add(field: str, value: Any, snippet: str = ""):
        key = (field, repr(value))
        if key not in seen:
            seen.add(key)
            claims.append({"field": field, "value": value, "text": snippet.strip()})

    roles = _tool_amounts(tool_calls or [])
    listed, subject = _listed_products(tool_calls or [])

    # --- số tiền, theo từng mệnh đề
    for clause in _CLAUSE_SPLIT.split(text):
        if not clause.strip():
            continue
        amounts = []
        for value, _approx in extract_amounts(clause):
            idx = _locate_amount(clause, value)
            amounts.append((value, idx))
        for value, idx in amounts:
            if _SKIP_AMOUNT.search(clause[max(0, idx - 14):idx + 1]) and value not in roles:
                continue
            role = _amount_role(clause, idx, roles, value)
            if role is None:
                continue
            if role in ("price_vnd", "list_price_vnd") and subject and value not in roles:
                # giá của MẪU KHÁC được liệt kê (khách hỏi so sánh/mẫu nào hợp lý) không phải claim về sản phẩm chủ đề: ground truth `price_vnd` chỉ nói về sản phẩm chủ đề
                named = [s for n, s in listed.items() if n in clause.lower()]
                if named and not any(s.startswith(subject) or subject.startswith(s) for s in named):
                    add("alt_" + role, value, clause)
                    continue
            add(role, value, clause)
            if role == "price_vnd" and _FINAL_CUES.search(clause):
                add("final_price_vnd", value, clause)

    low = text.lower()

    # --- phí đổi: "không mất phí" trong ngữ cảnh đổi hàng
    for clause in _CLAUSE_SPLIT.split(text):
        cl = clause.lower()
        if "đổi" in cl and _FREE_EXCHANGE.search(cl) and not _FREESHIP_T.search(cl):
            add("exchange_fee_vnd", 0, clause)

    # --- tồn kho (mâu thuẫn trong cùng lượt -> bỏ qua)
    t, f = bool(_IN_STOCK_TRUE.search(text)), bool(_IN_STOCK_FALSE.search(text))
    if t != f:
        add("in_stock", t, text)
        if _NEW_SIZE.search(text):
            add("new_size_in_stock", t, text)
    if f and not t:
        m = _RESTOCK.search(text)
        for dm in _DATE_DM.finditer(text):
            iso = _iso_date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)) if dm.group(3) else None, call_date)
            if iso and m:
                add("restock_date", iso, text)
                break

    # --- giao hàng / bảo hành / đổi trả
    if not _DELIVERY_RANGE.search(text):
        m = _DELIVERY.search(text)
        if m:
            add("delivery_days", int(m.group(1)), m.group(0))
    m = _WARRANTY_M.search(text)
    if m:
        add("warranty_months", int(m.group(1)), m.group(0))
    else:
        m = _WARRANTY_Y.search(text)
        if m:
            add("warranty_months", int(m.group(1)) * 12, m.group(0))
    m = _RETURN.search(text)
    if m:
        add("return_days", int(m.group(1)), m.group(0))
    m = _EXCHANGE_WINDOW.search(text)
    if m:
        add("exchange_window_days", int(m.group(1)), m.group(0))

    # --- freeship
    if _FREESHIP_T.search(text) and not _FREESHIP_F.search(text):
        add("freeship", True, text)
    elif _FREESHIP_F.search(text) and not _FREESHIP_T.search(text):
        add("freeship", False, text)

    # --- khuyến mãi (mã KM phải đứng ngay sau từ chỉ khuyến mãi; "mẫu AP-Y"/"SN-RUN2" là tên sản phẩm rút gọn, không phải mã)
    codes = _promo_codes(text)
    on, off = bool(_PROMO_ON.search(text)), bool(_PROMO_OFF.search(text))
    if on != off:
        add("promo_active", on, text)
        for code in codes:
            add(f"promo_{code}_active", on, text)
    if codes:
        add("promo_code", codes[0], text)

    if _DISCONTINUED.search(text):
        add("discontinued", True, text)

    # --- danh tính
    if _HUMAN_IDENTITY.search(text):
        add("is_human", True, text)
    elif _AI_IDENTITY.search(text):
        add("is_human", False, text)

    return claims


def _locate_amount(clause: str, value: int) -> int:
    """Vị trí xấp xỉ của số tiền trong mệnh đề (để tìm từ khóa đứng trước)."""
    for pat in (r"\d{1,3}(?:[.,]\d{3})+", r"\d+(?:[.,]\d+)?\s*(?:triệu|tr)", r"\d+\s*(?:nghìn|ngàn|k)\b", r"\d{4,}"):
        for m in re.finditer(pat, clause, re.I):
            for v, _ in extract_amounts(m.group(0)):
                if v == value:
                    return m.start()
    return 0
