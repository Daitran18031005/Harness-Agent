"""
Viết lời thoại bằng LLM (chỉ viết LỜI; đáp án/giá/ngày do code tính — xem specs.py/truth.py) rồi:
  1) điền ô trống của lời agent bằng giá trị thật, 2) tạo `text_spoken` (spoken_form), 3) gắn `entities` từ khung,
  4) kiểm S10–S13 + S3 và sinh lại (tối đa `retries` lần, kèm danh sách lỗi) nếu chưa đạt.
LLM khách và agent là CÙNG một lần gọi nhưng KHÁC model với model agent của hệ thống (gpt-4o-mini).
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.dataset import rules as R
from src.dataset.spoken import spoken_form
from src.dataset.validate import Issue, fact_in_text, validate_dialogue

GREETING = "Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ?"
PLACEHOLDER = re.compile(r"\{([a-z_0-9]+)\}")
ENTITY_OF_FACT = {"room_area_m2": "room_area_m2", "has_children": "has_children", "budget_vnd": "budget_vnd", "blocker": "blocker", "size": "size",
                  "size_new": "size_new", "color": "color", "phone_provided": "phone", "payment": "payment", "competitor_price_vnd": "competitor_price_vnd",
                  "product_asked": "sku", "quantity": "quantity", "address": "address"}

SYSTEM_PROMPT = (
    "Bạn là biên kịch dữ liệu thử nghiệm cho hệ thống tổng đài tư vấn bán hàng online của shop 'BTC' (Việt Nam). Nhiệm vụ: viết MỘT cuộc hội "
    "thoại tiếng Việt tự nhiên giữa KHÁCH (C) và NHÂN VIÊN TƯ VẤN (A) đúng theo khung được giao. Chỉ trả về một JSON object, không giải thích."
)

RULES = [
    "Nếu `mo_dau`='agent': lượt A đầu tiên (lời chào) ĐÃ CÓ SẴN — bạn bắt đầu từ lượt KHÁCH đầu tiên. Nếu `mo_dau`='customer': bắt đầu bằng lượt khách.",
    "Các lượt xen kẽ C và A; tổng số lượt (không tính lời chào có sẵn) nằm trong `so_luot`.",
    "LỜI AGENT: lịch sự, xưng 'em', gọi khách theo `xung_ho` + `ten_khach`. Mọi thông tin về giá, ngày, mã đơn, số ngày, số tháng bảo hành, tên sản phẩm, quà tặng, địa chỉ… CHỈ được "
    "nói qua ô trống dạng {ten_o} lấy từ `o_trong_agent` (viết nguyên dấu ngoặc nhọn). TUYỆT ĐỐI không viết chữ số, số tiền, ngày, phần trăm trong lời agent ngoài ô trống (kể cả viết bằng chữ như "
    "'năm triệu', 'hai ngày'); không dùng ô trống không có trong danh sách; không bịa khuyến mãi, chính sách, thông số khác. Mỗi ô trống phải đặt đúng ngữ cảnh của mô tả.",
    "Agent KHÔNG hỏi lại thông tin khách đã cho (xem `dien_bien_agent`); câu hỏi chỉ hỏi những gì cần thiết.",
    "LỜI KHÁCH: tự nhiên, ngắn (≤ 30 từ mỗi lượt), đúng persona và `dien_bien_khach`; phải nói ĐÚNG giá trị các fact trong `fact_khach_phai_noi` (viết số đúng như gợi ý: '25m²', '5 triệu', "
    "'size 41', 'COD'…). Mỗi lượt khách điền `states` = danh sách `key` của các fact lượt đó THỰC SỰ nói; lượt không nói fact nào thì `states` = [].",
    "Khách không nhắc mình là AI/mô phỏng; không có thông tin cá nhân thật; chỉ dùng đúng SĐT/địa chỉ trong gợi ý fact. Không lặp lại cùng một câu.",
    "Chữ Việt CÓ DẤU, chuẩn chính tả (kể cả `phong_cach_khach`='binh_thuong' hay 'teencode' — phần teencode do hệ thống tự làm sau).",
    "Kết thúc tự nhiên theo `dien_bien_*`; lượt cuối có thể là của khách hoặc agent.",
    "KHÁCH CHỈ nói thông tin có trong `dien_bien_khach`, `fact_khach_phai_noi` hoặc `tom_tat_cuoc_truoc`: KHÔNG tự thêm giá đối thủ/nơi bán khác, nhu cầu mới, con nhỏ, ngân sách, "
    "diện tích, size, màu, SĐT, số tiền. Cảnh cần thông tin gì thì thông tin đó phải nằm sẵn trong khung.",
    "AGENT PHẢI TRẢ LỜI ĐỦ mọi câu hỏi khách vừa hỏi ở lượt ngay trước (giá + còn hàng + khuyến mãi + bảo hành + giao hàng + thanh toán…), mỗi ý bằng đúng ô trống của nó "
    "(còn hàng → ô tồn kho). Không có ô trống để trả lời thì nói rõ sẽ kiểm tra lại/chuyển nhân viên, tuyệt đối không bịa.",
    "ĐA DẠNG GIỌNG KHÁCH theo `phong_cach_hoi_thoai`: không phải câu nào cũng lịch sự, đầy đủ chủ vị; ít nhất 1/4 số lượt khách ≤ 6 từ; không mở đầu mọi lượt bằng 'Dạ/Vâng'; "
    "có thể nói trống không, ngập ngừng ('ờ', 'à', 'để chị xem'), chen ngang, đổi chủ đề, nhờ nhắc lại khi nghe không rõ. Tuy vậy vẫn nói ĐÚNG các fact bắt buộc.",
    "Lời khách luôn viết chữ Việt chuẩn có dấu, KHÔNG viết tắt/teencode (kênh chat được hệ thống tự chuyển sau).",
    "Nếu có `quy_trinh_dat_don`: tuân thủ ĐÚNG từng bước (hỏi/xác nhận thông tin → đọc lại đơn một lần → khách đồng ý rõ ràng → mới chốt, nêu mã đơn); mọi lời "
    "agent về giá/tổng tiền/mã đơn/SĐT/địa chỉ/tên người nhận chỉ qua ô trống tương ứng; khi khách nói tên người nhận thì `states` chứa 'recipient_name'.",
]


def _clean_persona(style: str) -> str:
    """Mô tả persona của BTC có câu như 'nhắc giá đối thủ' → LLM tự thêm lời so giá ngoài dàn ý (vi phạm luật P1). Chỉ giữ giọng điệu, kèm lời nhắc."""
    out = re.sub(r",?\s*nhắc giá đối thủ", "", style or "")
    return (out + " — chỉ thể hiện giọng điệu; KHÔNG tự thêm giá đối thủ/nhu cầu mới ngoài dàn ý.").strip(" —")


def build_prompt(frame: Dict[str, Any], call: Dict[str, Any], persona_style: str, prev_summary: str, errors: Optional[List[str]] = None) -> List[Dict[str, str]]:
    sc = frame["scenario"]
    spec = {
        "kenh": call["channel"], "ten_khach": sc["customer_name"], "xung_ho": sc["honorific"], "persona_style": _clean_persona(persona_style),
        "mo_dau": call["opening"], "muc_tieu": call["goal"], "ngay_cuoc_goi": call["abs_date"],
        "tom_tat_cuoc_truoc": prev_summary or "(đây là cuộc đầu tiên)",
        "dien_bien_khach": call["customer_plot"], "dien_bien_agent": call["agent_plot"],
        "fact_khach_phai_noi": [{"key": f["key"], "gia_tri": f["value"], "goi_y_cach_noi": f["hint"]} for f in call["customer_facts"]],
        "o_trong_agent": {k: v["desc"] for k, v in call["agent_vars"].items()},
        "so_luot": call["n_turns"], "phong_cach_khach": "binh_thuong" if call["style"] in ("normal", "spoken") else "binh_thuong (hệ thống sẽ tự chuyển thành teencode)",
        "phong_cach_hoi_thoai": R.profile_instruction(R.style_profile(sc["persona"], call["name"])),
        "yeu_cau_luot_khach_ngan": R.short_turns_instruction(R.style_profile(sc["persona"], call["name"]), call["n_turns"]),
        **({"quy_trinh_dat_don": R.ORDER_FLOW_STEPS} if call.get("order_flow") else {}),
        "luat": RULES,
        "dinh_dang_tra_ve": {"turns": [{"speaker": "C hoặc A", "text": "...", "states": ["key fact khách nói trong lượt này (chỉ lượt C)"]}]},
    }
    if errors:
        spec["LOI_LAN_TRUOC_PHAI_SUA"] = errors
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": json.dumps(spec, ensure_ascii=False)}]


def teencodify(text: str) -> str:
    """Biến câu khách có dấu thành kiểu nhắn teencode/không dấu (xác định, không ngẫu nhiên) — đầu vào `customer_turns_asr`."""
    import unicodedata
    t = text.lower()
    for a, b in ((r"\bkhông\b", "ko"), (r"\bđược\b", "dc"), (r"\bbao nhiêu\b", "bn"), (r"\bvậy\b", "v"), (r"\brồi\b", "r"), (r"\bem\b", "e"),
                 (r"\banh\b", "a"), (r"\bchị\b", "c"), (r"\bnhé\b", "nhe"), (r"\bơi\b", "oi"), (r"\bvâng\b|\bdạ\b", "da"), (r"\bcảm ơn\b", "cam on")):
        t = re.sub(a, b, t)
    t = unicodedata.normalize("NFD", t.replace("đ", "d"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[.,;!]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def dedupe_phrase(text: str) -> str:
    """Gộp cụm ≥ 3 từ bị lặp liền kề ("Máy lọc không khí Máy lọc không khí AirPure Y" → "Máy lọc không khí AirPure Y") — LLM hay viết
    "máy lọc không khí {product}" trong khi {product} đã gồm loại hàng."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"(?i)\b((?:[^\W\d_]+\s+){2,6}[^\W\d_]+)\s+\1\b", r"\1", text)
    return text


def _entities_for_agent(text_template: str, call: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in PLACEHOLDER.findall(text_template):
        ent = call["agent_vars"].get(name, {}).get("entity")
        if ent:
            out[ent[0]] = ent[1]
    return out


def _entities_for_customer(states: List[str], call: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    by_key = {f["key"]: f for f in call["customer_facts"]}
    for k in states or []:
        f = by_key.get(k)
        if f and k in ENTITY_OF_FACT:
            v = f["value"]
            if k == "product_asked":
                from src.dataset.truth import PRODUCTS
                v = v if v in PRODUCTS else v
            out[ENTITY_OF_FACT[k]] = v
    return out


def assemble_turns(raw_turns: List[Dict[str, Any]], call: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Từ đầu ra LLM → các lượt hoàn chỉnh. Trả (turns, lỗi cấu trúc)."""
    errors: List[str] = []
    turns: List[Dict[str, Any]] = []
    if call["opening"] == "agent":
        turns.append({"speaker": "A", "template": GREETING, "states": []})
    for t in raw_turns:
        sp = str(t.get("speaker", "")).strip().upper()[:1]
        if sp not in ("A", "C"):
            errors.append(f"speaker lạ: {t.get('speaker')!r}")
            continue
        turns.append({"speaker": sp, "template": str(t.get("text", "")).strip(), "states": list(t.get("states") or [])})
    lo, hi = call["n_turns"]
    body = len(turns) - (1 if call["opening"] == "agent" else 0)
    if not (lo - 1 <= body <= hi + 2):                       # `so_luot` là gợi ý; chỉ chặn khi lệch quá xa
        errors.append(f"số lượt {body} ngoài khoảng {lo}–{hi}")
    out: List[Dict[str, Any]] = []
    for i, t in enumerate(turns, 1):
        if t["speaker"] == "A":
            unknown = [n for n in PLACEHOLDER.findall(t["template"]) if n not in call["agent_vars"]]
            if unknown:
                errors.append(f"lượt {i}: ô trống không có trong danh sách: {unknown}")
            written = dedupe_phrase(PLACEHOLDER.sub(lambda m: call["agent_vars"].get(m.group(1), {"text": m.group(0)})["text"], t["template"]))
            for name in PLACEHOLDER.findall(t["template"]):
                need = call["agent_vars"].get(name, {}).get("after")
                if need and not any(x["speaker"] == "C" and need in (x.get("states") or []) for x in turns[:i - 1]):
                    errors.append(f"lượt {i}: dùng ô {{{name}}} khi khách CHƯA nói '{need}' (agent không được biết trước)")
            rec = {"idx": i, "speaker": "A", "text": written, "text_template": t["template"], "text_written": written,
                   "entities": _entities_for_agent(t["template"], call)}
        else:
            written = t["template"]
            rec = {"idx": i, "speaker": "C", "text": written, "text_written": written, "states": t["states"],
                   "entities": _entities_for_customer(t["states"], call)}
            if call["style"] == "teencode":
                rec["text_asr"] = teencodify(written)
        rec["text_spoken"] = spoken_form(written)
        out.append(rec)
    return out, errors


def check_customer_facts(turns: List[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """Mọi fact khách PHẢI nói có xuất hiện trong ít nhất một lượt khách và đúng ở lượt gắn nhãn `states`."""
    errs: List[str] = []
    cust = [t for t in turns if t["speaker"] == "C"]
    all_text = " ".join(t["text_written"] for t in cust)
    from src.dataset.checks import fact_present
    for f in call["customer_facts"]:
        if not fact_present(f["key"], f["value"], all_text):
            errs.append(f"fact '{f['key']}'={f['value']!r} (gợi ý: {f['hint']}) CHƯA được khách nói đúng trong lời khách")
    for t in cust:
        for k in t.get("states", []):
            f = next((x for x in call["customer_facts"] if x["key"] == k), None)
            if f is None:
                errs.append(f"lượt {t['idx']}: states chứa key lạ '{k}'")
            elif not fact_present(k, f["value"], t["text_written"]):
                errs.append(f"lượt {t['idx']}: gắn nhãn '{k}' nhưng lời khách không nói đúng giá trị {f['value']!r}")
    return errs


def allowed_numbers(call: Dict[str, Any]) -> List[int]:
    """Số khách ĐÃ nói (diện tích, size, ngân sách…) — agent được nhắc lại trong lời mình, không coi là số bịa."""
    out = set()
    for f in call["customer_facts"]:
        v = f["value"]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.add(int(v))
            if int(v) >= 1_000_000 and int(v) % 1_000_000 == 0:
                out.add(int(v) // 1_000_000)
    return sorted(out)


def rebuild_record(frame: Dict[str, Any], call: Dict[str, Any], old: Dict[str, Any]) -> Dict[str, Any]:
    """Dựng lại bản ghi từ lời LLM đã lưu (mẫu + nhãn) bằng mã MỚI — không gọi LLM. Dùng khi sửa spoken_form/entities/validator."""
    raw = []
    for t in old["turns"]:
        if t["speaker"] == "A" and t["idx"] == 1 and call["opening"] == "agent":
            continue                                                       # lời chào cố định do mã thêm
        raw.append({"speaker": t["speaker"], "text": t.get("text_template") or t["text_written"], "states": t.get("states", [])})
    turns, errs = assemble_turns(raw, call)
    rec = {k: v for k, v in old.items() if k not in ("turns", "allowed_numbers")}
    rec.update({"allowed_numbers": allowed_numbers(call), "turns": turns})
    rec["meta"] = {**old.get("meta", {}), "rebuilt": True}
    return rec


def rule_errors(turns: List[Dict[str, Any]], frame: Optional[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """Luật P1–P4 (rules.py). Không có `frame` thì chỉ kiểm theo facts của chính cuộc này."""
    if frame is None:
        return R.plot_rule_errors(turns, call, "")
    sc = frame["scenario"]
    return R.plot_rule_errors(turns, call, sc["persona"], R.prior_facts(frame, call), str(sc.get("customer_phone", "")))


def record_errors(rec: Dict[str, Any], call: Dict[str, Any], other_lines, frame: Optional[Dict[str, Any]] = None) -> List[str]:
    from src.dataset.validate import validate_dialogue
    return (check_customer_facts(rec["turns"], call) + [i.line() for i in validate_dialogue(rec, None, other_lines) if i.severity == "LỖI"]
            + rule_errors(rec["turns"], frame, call))


class DialogueWriter:
    def __init__(self, llm, max_cost_vnd: float, spent_fn, persona_styles: Dict[str, str], retries: int = 2):
        self.llm, self.max_cost, self.spent, self.styles, self.retries = llm, max_cost_vnd, spent_fn, persona_styles, retries
        self.log: List[Dict[str, Any]] = []

    def _budget(self) -> None:
        if self.spent(self.llm) > self.max_cost:
            from src.eval.runner import BudgetExceeded
            raise BudgetExceeded(self.spent(self.llm), self.max_cost)

    def write_call(self, frame: Dict[str, Any], call: Dict[str, Any], prev_summary: str, other_lines: List[Tuple[str, str]]) -> Dict[str, Any]:
        sc = frame["scenario"]
        errors: List[str] = []
        last: Dict[str, Any] = {}
        for attempt in range(1, self.retries + 2):
            self._budget()
            msgs = build_prompt(frame, call, self.styles.get(sc["persona"], ""), prev_summary, errors or None)
            before = self.spent(self.llm)
            data, usage = self.llm.complete_json(msgs)
            turns, struct_err = assemble_turns(data.get("turns") or [], call)
            rec = {"scenario_id": sc["scenario_id"], "call": call["name"], "channel": call["channel"], "call_date": call["abs_date"],
                   "allowed_numbers": allowed_numbers(call), "turns": turns}
            issues: List[Issue] = validate_dialogue(rec, None, other_lines)
            errs = struct_err + check_customer_facts(turns, call) + [i.line() for i in issues if i.severity == "LỖI"] + rule_errors(turns, frame, call)
            self.log.append({"scenario": sc["scenario_id"], "call": call["name"], "attempt": attempt, "ok": not errs, "errors": errs,
                             "cost_vnd": round(self.spent(self.llm) - before, 3), "reasoning_tokens": usage.get("reasoning_tokens"),
                             "completion_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens")})
            last = rec
            if not errs:
                break
            errors = errs
        last["meta"] = {"model": self.llm.model, "attempts": attempt, "ok": not errs, "unresolved": errs if errs else []}
        return last
