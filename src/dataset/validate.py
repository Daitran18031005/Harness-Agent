"""
Bộ kiểm tra tự động cho kịch bản + lời thoại (luật S1–S14 của docs/DATASET_TEXT_PLAN.md § 5).
Mỗi luật trả `Issue(code, severity, scenario, call, message)`; severity ∈ {"LỖI", "CẢNH BÁO"}. Không gọi mạng/LLM.
"""
import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from src.dataset import truth as T
from src.harness.fact_usage import fact_mentioned, fold

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BTC = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS")
REF_DATE = "2026-10-15"
FAKE_PHONE = re.compile(r"^09000\d{5}$")          # dải SĐT GIẢ của dự án (không gắn người thật)

TOP_FIELDS = {"scenario_id", "level", "persona", "hard_case", "customer_phone", "customer_name", "honorific", "notes", "calls"}
CALL_FIELDS = {"channel", "channel_identity", "call_date", "days_later", "customer_turns", "customer_turns_asr", "input_mode", "seed_history",
               "facts_established", "must_carry_over", "must_not_ask", "success_if", "ground_truth_facts", "memory_expectation",
               "expected_outcome", "customer_goal"}
SUCCESS_FIELDS = {"tool_called", "args_match", "also_ordered", "total_match_vnd", "brief_must_contain", "must_say_any", "agent_must_say",
                  "must_not_call_tools", "forbidden_claims", "trace_must_not_match"}
OUTCOMES = {"hen_goi_lai", "chot_don", "chuyen_may", "tu_choi"}
CHANNELS = {"hotline", "chat_fanpage", "zalo_oa"}
# Nhãn ca khó "tái hiện lỗi demo" (2026-10-24), NGOÀI 4 loại của đề. Khớp CHÍNH XÁC (không dùng `in`): "het_hang_bien_the" chứa chuỗi con "het_han" của nhãn KM hết hạn.
DEMO_HARD_CASES = ("mac_ca", "tu_choi_giua_gate", "hoan_giua_gate", "het_hang_bien_the", "tu_nhan_khach_cu_chua_sdt", "so_noi_bang_chu")
CHAT_CHANNELS = {"chat_fanpage", "zalo_oa"}
_RX_RETURNING_CLAIM = re.compile(r"khach cu|da mua|mua roi|lan truoc|mua hoi|mua thang truoc")
_DW = r"(?:khong|mot|hai|ba|bon|nam|sau|bay|tam|chin)"
_RX_SPOKEN_PHONE = re.compile(rf"(?:{_DW}\s+){{8,}}{_DW}")                     # ≥ 9 chữ số đọc liền bằng chữ (SĐT)
CUSTOMER_FACT_KEYS = {"room_area_m2", "has_children", "budget_vnd", "blocker", "size", "color", "competitor_price_vnd", "phone_provided", "payment"}


@dataclass
class Issue:
    code: str
    severity: str
    scenario: str
    call: str
    message: str

    def line(self) -> str:
        return f"[{self.severity}] {self.code} {self.scenario}{'/' + self.call if self.call else ''}: {self.message}"


def _tools_schema() -> Dict[str, Set[str]]:
    spec = json.load(open(os.path.join(BTC, "schemas", "tools.schema.json"), encoding="utf-8"))
    return {t["name"]: set(t["input"]) for t in spec["tools"] if "input" in t and "/" not in t["name"]}


TOOLS = _tools_schema()


def call_dates(spec: Dict[str, Any]) -> Dict[str, str]:
    out, prev = {}, REF_DATE
    for cn in ("call_1", "call_2", "call_3"):
        c = spec.get("calls", {}).get(cn)
        if c is None:
            continue
        if c.get("call_date"):
            prev = c["call_date"]
        else:
            prev = (datetime.strptime(prev, "%Y-%m-%d") + timedelta(days=c.get("days_later", 0))).strftime("%Y-%m-%d")
        out[cn] = prev
    return out


def _customer_text(c: Dict[str, Any]) -> str:
    return " ".join(c.get("customer_turns") or c.get("customer_turns_asr") or [])


def _amounts(text: str) -> Set[int]:
    from src.channels.asr_postprocess import money_values
    return money_values(text)


def fact_in_text(key: str, value: Any, text: str) -> bool:
    """Fact khách nêu có xuất hiện trong lời khách không (sau ITN; theo từ khóa cho fact ngữ nghĩa)."""
    f = fold(text)
    digits = re.sub(r"\D", "", text)
    if key in ("budget_vnd", "competitor_price_vnd", "offered_price_vnd", "prev_quote_vnd"):
        return int(value) in _amounts(text) or str(int(value)) in digits
    if key == "phone_provided":
        return re.sub(r"\D", "", str(value)) in digits
    if key == "payment":
        return any(c in f for c in ("cod", "thanh toan khi nhan", "tra tien khi nhan", "chuyen khoan"))
    if key == "size":
        v = str(value).strip().lower()
        if v.isdigit():
            return bool(re.search(rf"(?:size|sz|co)\s*{int(v)}\b", f)) or bool(re.search(rf"\b{int(v)}\b", f))
        return bool(re.search(rf"(?:size|sz|co|ao)\s*{re.escape(v)}\b", f))          # size chữ (S/M/L/XL): bắt buộc có từ 'size' để khỏi nhầm chữ cái rời
    if fact_mentioned(key, value, text):
        return True
    # số nói bằng chữ ("ba mươi lăm mét vuông"): thử lại trên bản đã chuẩn hóa (ITN) giống đường vào của hệ thống
    from src.channels.normalizer import InputChannel, RequestNormalizer
    return fact_mentioned(key, value, RequestNormalizer().normalize(text, InputChannel.HOTLINE, "0900000000").normalized_text)


# ------------------------------------------------------------------------------------------------ kịch bản (S1–S9)
def validate_scenario(spec: Dict[str, Any], all_phones: Optional[Dict[str, List[str]]] = None) -> List[Issue]:
    sid = spec.get("scenario_id", "?")
    issues: List[Issue] = []

    def add(code, sev, msg, call=""):
        issues.append(Issue(code, sev, sid, call, msg))

    # S1 schema
    for k in TOP_FIELDS:
        if k not in spec:
            add("S1", "LỖI", f"thiếu trường '{k}'")
    calls = spec.get("calls") or {}
    names = list(calls)
    if not names or names != [f"call_{i}" for i in range(1, len(names) + 1)] or len(names) > 3:
        add("S1", "LỖI", f"`calls` phải là call_1..call_n liên tục (n ≤ 3), đang là {names}")
    for cn, c in calls.items():
        extra = set(c) - CALL_FIELDS
        if extra:
            add("S1", "LỖI", f"trường không thuộc định dạng BTC: {sorted(extra)}", cn)
        if "expected_outcome" in c and c["expected_outcome"] not in OUTCOMES:       # BTC cho phép bỏ trống ở cuộc sau; có thì phải hợp lệ
            add("S1", "LỖI", f"expected_outcome '{c.get('expected_outcome')}' ∉ {sorted(OUTCOMES)}", cn)
        turns = c.get("customer_turns") or c.get("customer_turns_asr")
        if not turns or not all(isinstance(t, str) and t.strip() for t in turns):
            add("S1", "LỖI", "customer_turns trống/sai kiểu", cn)
        if c.get("channel") and c["channel"] not in CHANNELS:
            add("S1", "LỖI", f"channel '{c['channel']}' không hợp lệ", cn)
        bad = set(c.get("success_if") or {}) - SUCCESS_FIELDS
        if bad:
            add("S1", "LỖI", f"success_if có khóa lạ: {sorted(bad)}", cn)

    # S2 ngày
    dates = call_dates(spec)
    prev = None
    for cn, d in dates.items():
        if prev and d < prev:
            add("S2", "LỖI", f"ngày {d} < ngày cuộc trước {prev}", cn)
        if not ("2026-09-01" <= d <= "2027-01-01"):
            add("S2", "LỖI", f"ngày {d} ngoài khoảng 2026-09-01..2027-01-01", cn)
        prev = d
    for cn, c in calls.items():
        if cn != "call_1" and "call_date" not in c and "days_later" not in c:
            add("S2", "LỖI", "cuộc 2+ phải có call_date hoặc days_later", cn)

    # S3 facts khách nêu phải có trong lời khách
    for cn, c in calls.items():
        text = _customer_text(c)
        for k, v in (c.get("facts_established") or {}).items():
            if k in CUSTOMER_FACT_KEYS and not fact_in_text(k, v, text):
                add("S3", "LỖI", f"facts_established.{k}={v!r} KHÔNG xuất hiện trong lời khách", cn)

    # S4 đáp án khớp mock_tools
    last_sku: Optional[str] = None
    last_promo: Optional[str] = None
    for cn, c in calls.items():
        on = dates.get(cn, REF_DATE)
        fe, gt, si = c.get("facts_established") or {}, c.get("ground_truth_facts") or {}, c.get("success_if") or {}
        last_sku = fe.get("product_advised", last_sku)
        last_promo = fe.get("promo_code", last_promo)
        sku = (si.get("args_match") or {}).get("sku") or fe.get("variant_sku") or last_sku
        if "price_vnd" in gt and sku:
            try:
                q = T.quote(sku, on, spec.get("customer_phone"))
                if q.get("final_price_vnd") != gt["price_vnd"] and q.get("list_price_vnd") != gt["price_vnd"]:
                    add("S4", "LỖI", f"ground_truth price_vnd={gt['price_vnd']:,} khác mock_tools({sku}, {on}) = {q.get('final_price_vnd')}", cn)
            except Exception as e:
                add("S4", "CẢNH BÁO", f"không tính được giá {sku}: {e}", cn)
        if "price_quoted_vnd" in fe and (fe.get("variant_sku") or fe.get("product_advised")):
            qsku = fe.get("variant_sku") or fe.get("product_advised")
            try:
                q = T.quote(qsku, on, spec.get("customer_phone"))
                if fe["price_quoted_vnd"] not in (q.get("final_price_vnd"), q.get("list_price_vnd")):
                    add("S4", "LỖI", f"facts_established.price_quoted_vnd={fe['price_quoted_vnd']:,} khác mock_tools({qsku}, {on}) = {q.get('final_price_vnd'):,}", cn)
            except Exception:
                pass
        if "in_stock" in gt and sku:
            s = T.stock(sku, on)
            if "in_stock" in s and s["in_stock"] != gt["in_stock"]:
                add("S4", "LỖI", f"ground_truth in_stock={gt['in_stock']} khác mock_tools({sku}, {on}) = {s['in_stock']}", cn)
        if "promo_active" in gt and last_promo:
            if T.promo_active(last_promo, on) != gt["promo_active"]:
                add("S4", "LỖI", f"ground_truth promo_active={gt['promo_active']} khác hạn KM {last_promo} tại {on}", cn)
        for k, v in gt.items():
            m = re.fullmatch(r"promo_(.+)_active", k)
            if m and any(p["promo_code"] == m.group(1) for p in T.m.PROMOS) and T.promo_active(m.group(1), on) != v:
                add("S4", "LỖI", f"ground_truth {k}={v} khác hạn KM tại {on}", cn)
        base = (sku or "").split("-")
        parent = T.m._parent(sku)[0]["sku"] if sku and T.m._parent(sku)[0] else None
        for key, attr_key in (("warranty_months", "warranty_months"), ("return_days", "return_days")):
            if key in gt and parent and T.attr(parent, attr_key) is not None and T.attr(parent, attr_key) != gt[key]:
                add("S4", "LỖI", f"ground_truth {key}={gt[key]} khác catalog({parent}) = {T.attr(parent, attr_key)}", cn)
        if gt.get("cod_limit_vnd") not in (None, 10_000_000):
            add("S4", "LỖI", f"cod_limit_vnd phải 10.000.000 (mock_tools), đang {gt['cod_limit_vnd']}", cn)

    # S5 tool/args hợp lệ, SKU tồn tại
    skus = set(T.PRODUCTS) | {v["variant_sku"] for p in T.m.PRODUCTS for v in p["variants"]}
    for cn, c in calls.items():
        si = c.get("success_if") or {}
        tool = si.get("tool_called")
        if tool is not None and tool not in TOOLS:
            add("S5", "LỖI", f"tool_called '{tool}' không có trong tools.schema.json", cn)
        elif tool and si.get("args_match"):
            bad = set(si["args_match"]) - TOOLS[tool] - {"action", "order_id", "qty"}
            if bad:
                add("S5", "LỖI", f"args_match có khóa ngoài chữ ký tool {tool}: {sorted(bad)}", cn)
        for a in (si.get("args_match") or {}).values():
            pass
        for key in ("sku", "new_variant_sku"):
            v = (si.get("args_match") or {}).get(key)
            if v and v not in skus:
                add("S5", "LỖI", f"SKU '{v}' không có trong catalog", cn)
        for t in si.get("must_not_call_tools") or []:
            if t not in TOOLS:
                add("S5", "LỖI", f"must_not_call_tools: tool lạ '{t}'", cn)

    # S6 carry-over
    prev_fe: Set[str] = set()
    for cn, c in calls.items():
        mco, mna = set(c.get("must_carry_over") or []), set(c.get("must_not_ask") or [])
        if cn == "call_1" and not c.get("seed_history"):
            own = set(c.get("facts_established") or {})
            if mco:
                add("S6", "LỖI", "cuộc 1 không được có must_carry_over (không có phiên trước/seed_history)", cn)
            if mna - own:                          # must_not_ask ở cuộc 1 chỉ hợp lệ cho slot CHÍNH cuộc đó đã nêu (kiểm RQR trong cùng cuộc)
                add("S6", "LỖI", f"cuộc 1 có must_not_ask {sorted(mna - own)} nhưng các slot đó không có trong facts_established của chính cuộc 1 (và không có seed_history)", cn)
        if cn != "call_1":
            unknown = mco - prev_fe
            if unknown:
                add("S6", "LỖI", f"must_carry_over {sorted(unknown)} không có trong facts_established của các cuộc trước", cn)
        if cn != "call_1" and mna - mco - prev_fe:
            add("S6", "CẢNH BÁO", f"must_not_ask {sorted(mna - mco - prev_fe)} không nằm trong fact đã biết", cn)
        prev_fe |= set((c.get("facts_established") or {}))

    # S7 hard_case đúng cấu trúc
    hc = (spec.get("hard_case") or "")
    if hc in DEMO_HARD_CASES:
        for msg in demo_hard_errors(hc, calls):
            add("S7", "LỖI", msg)
    elif hc:
        if "mau_thuan" in hc:
            if len(calls) < 2 or not any("superseded" in (c.get("memory_expectation") or {}) for c in calls.values()):
                add("S7", "LỖI", "hard_case 'mâu thuẫn' cần ≥ 2 cuộc và memory_expectation.superseded")
        elif "het_han" in hc and "het_hang" not in hc:   # "het_hang_*" (hết hàng) KHÔNG phải "hết hạn"
            gts = [c.get("ground_truth_facts") or {} for c in calls.values()]
            if not any(("promo_active" in g and g["promo_active"] is False) or any(re.fullmatch(r"promo_.+_active", k) and v is False for k, v in g.items()) for g in gts):
                add("S7", "LỖI", "hard_case 'KM hết hạn' cần ground_truth_facts báo KM không còn hiệu lực (False)")
        elif "ngoai_tai_lieu" in hc or "chinh_sach" in hc:
            if not any((c.get("success_if") or {}).get("agent_must_say") or (c.get("success_if") or {}).get("must_say_any") for c in calls.values()):
                add("S7", "LỖI", "hard_case 'ngoài tài liệu' cần success_if.agent_must_say/must_say_any")
        elif "doi_y" in hc and not calls:
            add("S7", "LỖI", "hard_case đổi ý nhưng không có cuộc gọi")

    # S8 đa kênh + định danh kênh
    prev_ch = None
    phone_seen = False
    for cn, c in calls.items():
        ch = c.get("channel", "hotline")
        ident = c.get("channel_identity")
        if ch in ("chat_fanpage", "zalo_oa"):
            prefix = "fb" if ch == "chat_fanpage" else "zalo"
            if not ident:
                add("S8", "CẢNH BÁO", f"{ch} nên có channel_identity dạng {prefix}…", cn)
            elif not ident.startswith(prefix):
                add("S8", "LỖI", f"{ch} cần channel_identity dạng {prefix}…, đang '{ident}'", cn)
        text = _customer_text(c)
        if re.sub(r"\D", "", text).find(re.sub(r"\D", "", str(spec.get("customer_phone", "")))) >= 0 and spec.get("customer_phone"):
            phone_seen = True
        if (c.get("facts_established") or {}).get("phone_provided"):
            phone_seen = True
        if prev_ch is not None and ch != prev_ch and not phone_seen and ch == "hotline" and False:
            pass
        prev_ch = ch
    chans = [c.get("channel", "hotline") for c in calls.values()]
    if len(set(chans)) > 1 and not phone_seen and spec.get("customer_phone") not in {x["phone"] for x in T.m.CRM}:
        add("S8", "LỖI", "kịch bản đa kênh cần một lượt khách đọc SĐT để nối danh tính (khách không có trong CRM)")

    # S9 SĐT/CCCD chỉ dải giả; không trùng khách khác
    phone = str(spec.get("customer_phone", ""))
    crm_phones = {x["phone"] for x in T.m.CRM}
    if not (FAKE_PHONE.match(phone) or phone in crm_phones):
        add("S9", "LỖI", f"SĐT {phone} không thuộc dải giả 09000xxxxx hoặc CRM seed của BTC")
    if all_phones is not None and len(all_phones.get(phone, [])) > 1 and "chung_sdt" not in (spec.get("persona") or "") and "chung_sdt" not in (hc or ""):
        add("S9", "LỖI", f"SĐT {phone} bị dùng ở nhiều kịch bản: {all_phones[phone]}")
    for cn, c in calls.items():
        text = _customer_text(c)
        for ph in re.findall(r"(?<!\d)0\d{9}(?!\d)", re.sub(r"(?<=\d)[ .\-](?=\d)", "", text)):
            if not (ph == phone or FAKE_PHONE.match(ph) or ph in crm_phones):
                add("S9", "LỖI", f"lời khách chứa SĐT lạ {ph}", cn)
        if hc != "pii_protection" and re.search(r"(?<!\d)\d{12}(?!\d)", text):   # pii_protection: CCCD/STK giả là chủ đích của ca kiểm che PII
            add("S9", "LỖI", "lời khách chứa chuỗi 12 chữ số (giống CCCD)", cn)
    return issues


# ------------------------------------------------------------------------------------------------ lời thoại (S10–S13)
_DIGIT_RE = re.compile(r"\d")


def _model_name_pattern() -> "re.Pattern":
    """Các cụm tên sản phẩm có chữ số ("RunLite 2 Pro", "Spectra S1", "Samsung AX40", "Karofi 9 lõi") — được phép xuất hiện trong lời agent
    (không phải khẳng định số liệu). Chỉ nhận cụm GỒM CẢ chữ lẫn số, không nhận số trần ("giao 2 ngày")."""
    phrases = set()
    for p in T.m.PRODUCTS:
        toks = p["name"].replace("(", " ").replace(")", " ").split()
        for i in range(len(toks)):
            for j in range(i + 1, len(toks) + 1):
                seg = toks[i:j]
                joined = " ".join(seg)
                if any(re.search(r"\d", t) for t in seg) and any(re.search(r"[A-Za-zÀ-ỹ]", t) for t in seg):
                    phrases.add(joined)
    alts = sorted((re.escape(x) for x in phrases), key=len, reverse=True) + [r"size\s*\d{2}", r"cỡ\s*\d{2}"]
    return re.compile("|".join(alts), re.I)


_MODEL_RE = None
_PLACEHOLDER_RE = re.compile(r"\{[a-z_0-9]+\}")


def _norm_sentence(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", fold(s))).strip()


def _is_consent_line(text: str) -> bool:
    from src.harness.order_gate import is_explicit_consent
    return is_explicit_consent(text)


def similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, _norm_sentence(a), _norm_sentence(b)).ratio()


def validate_dialogue(rec: Dict[str, Any], scenario_call: Optional[Dict[str, Any]] = None, other_customer_lines: Optional[List[Tuple[str, str]]] = None) -> List[Issue]:
    sid, cn = rec.get("scenario_id", "?"), rec.get("call", "?")
    issues: List[Issue] = []

    def add(code, sev, msg):
        issues.append(Issue(code, sev, sid, cn, msg))

    turns = rec.get("turns") or []
    cust = [t for t in turns if t["speaker"] == "C"]
    # S10
    if not turns:
        add("S10", "LỖI", "không có lượt thoại")
    if len(cust) < 3:
        add("S10", "LỖI", f"chỉ có {len(cust)} lượt khách (cần ≥ 3)")
    for t in turns:
        if not t.get("text", "").strip():
            add("S10", "LỖI", f"lượt {t.get('idx')} rỗng")
        if t["speaker"] == "C" and len(t["text_written"].split()) > 40:
            add("S10", "CẢNH BÁO", f"lượt khách {t['idx']} dài {len(t['text_written'].split())} từ (> 40)")
    for a, b in zip(turns, turns[1:]):
        if a["speaker"] == b["speaker"]:
            add("S10", "LỖI", f"lượt {a['idx']} và {b['idx']} cùng người nói ({a['speaker']})")
    for t in cust:
        for other_id, line in other_customer_lines or []:
            if (other_id != f"{sid}/{cn}" and similarity(t["text_written"], line) >= 0.85 and len(t["text_written"].split()) >= 4
                    and not _is_consent_line(t["text_written"])):          # lời ĐỒNG Ý ngắn ("ok em", "đúng rồi, chốt đi") lặp giữa các kịch bản là tự nhiên (order gate bắt buộc có lượt này)
                add("S10", "LỖI", f"lượt khách {t['idx']} trùng ≥ 85% với {other_id}: {line!r}")
    # S11 lời agent
    for t in turns:
        if t["speaker"] != "A":
            continue
        raw = t.get("text_template", t["text_written"])
        global _MODEL_RE
        if _MODEL_RE is None:
            _MODEL_RE = _model_name_pattern()
        scrubbed = _MODEL_RE.sub(" ", _PLACEHOLDER_RE.sub("", raw))
        for n in rec.get("allowed_numbers") or []:                               # agent được NHẮC LẠI số khách vừa nói (25 m², 5 triệu…)
            scrubbed = re.sub(rf"(?<![\d.,]){n}(?![\d])(?:\s*(?:m²|m2|triệu|tr|k))?", " ", scrubbed)
        if _DIGIT_RE.search(scrubbed):
            add("S11", "LỖI", f"lời agent lượt {t['idx']} có chữ số ngoài ô trống: {raw!r}")
        if re.search(r"\{[^}]*\}", t["text_written"]):
            add("S11", "LỖI", f"lời agent lượt {t['idx']} còn ô trống chưa điền: {t['text_written']!r}")
    # S12 text_spoken
    from src.channels.asr_postprocess import normalize_transcript, spoken_small_numbers
    for t in turns:
        spoken = t.get("text_spoken", "")
        if _DIGIT_RE.search(spoken) or re.search(r"[^\w\s]", spoken):
            add("S12", "LỖI", f"text_spoken lượt {t['idx']} còn chữ số/dấu câu: {spoken!r}")
            continue
        back = {int(re.sub(r"[.,]", "", m)) for m in re.findall(r"\d[\d.,]*\d|\d", spoken_small_numbers(normalize_transcript(spoken).normalized_text))}
        written = t["text_written"]
        need = {int(re.sub(r"[.,]", "", m)) for m in re.findall(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?![\d.,])", written)}          # số tiền có dấu chấm
        need |= {int(m) for m in re.findall(r"(?<![\d.,])(\d{4,9})(?![\d.,])", written) if not re.fullmatch(r"0\d{9}", m)}
        need |= {int(m) for m in re.findall(r"(\d{1,3})\s*(?:m²|m2)", written)}
        need -= {int(m) for m in re.findall(r"OD(\d{4,9})", written)}              # mã đơn kiểm bằng bộ trích riêng (bên dưới)
        missing = {n for n in need if n not in back}
        if missing:                                                              # ITN đã KHÓA có chỗ nhập nhằng ("mười triệu một đơn") — cảnh báo, không chặn
            add("S12", "CẢNH BÁO", f"ITN(text_spoken) lượt {t['idx']} không trả lại {sorted(missing)}: {spoken!r}")
        from src.channels.asr_postprocess import extract_hypothesis_entities
        for oid in re.findall(r"OD\d{4,9}", written):
            if extract_hypothesis_entities(spoken).get("order_id") != oid:
                add("S12", "LỖI", f"mã đơn {oid} không trích lại được từ text_spoken lượt {t['idx']}: {spoken!r}")
        for ph in re.findall(r"(?<!\d)(0\d{9})(?!\d)", written):
            if ph not in normalize_transcript(spoken).normalized_text.replace(" ", ""):
                add("S12", "LỖI", f"SĐT {ph} không đọc lại được từ text_spoken lượt {t['idx']}")
    # S13 customer_turns == lượt C
    if scenario_call is not None:
        want = [t["text_written"] for t in cust]
        have = scenario_call.get("customer_turns")
        if have is not None and have != want:
            add("S13", "LỖI", "customer_turns trong kịch bản khác các lượt C trong file lời thoại")
    return issues


# ------------------------------------------------------------------------------------------------ nạp + báo cáo (S14)
def load_scenarios(dirs: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            if os.path.basename(f).startswith("_"):
                continue
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if "scenario_id" in data and "calls" in data:
                out[data["scenario_id"]] = data
    return out


def load_dialogues(d: Optional[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if d and os.path.isdir(d):
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            with open(f, encoding="utf-8") as fh:
                rec = json.load(fh)
            out[f"{rec['scenario_id']}/{rec['call']}"] = rec
    return out


def demo_hard_errors(hc: str, calls: Dict[str, Any]) -> List[str]:
    """S7 cho 6 nhãn "tái hiện lỗi demo": nhãn phải ĐÚNG cấu trúc đáp án (chỉ dùng trường BTC) — không gắn nhãn cho kịch bản không có tình huống đó."""
    def si(c): return c.get("success_if") or {}
    def gt(c): return c.get("ground_truth_facts") or {}
    def no_order(c): return "order.create" in (si(c).get("must_not_call_tools") or [])
    items = list(calls.items())
    if hc == "mac_ca":
        for _, c in items:
            amounts = _amounts(_customer_text(c))
            for x in si(c).get("forbidden_claims") or []:
                if isinstance(x, dict) and x.get("field") == "price_vnd" and x.get("value") in amounts and x["value"] != gt(c).get("price_vnd"):
                    paid = si(c).get("tool_called") == "order.create" and (si(c).get("args_match") or {}).get("price_vnd") == gt(c).get("price_vnd")
                    if paid or no_order(c):
                        return []
        return ["hard_case 'mac_ca' cần forbidden_claims price_vnd = giá khách đề nghị (có trong lời khách, khác giá thật) và đơn (nếu có) đúng giá thật hoặc must_not_call_tools order.create"]
    if hc in ("tu_choi_giua_gate", "hoan_giua_gate"):
        want = "tu_choi" if hc == "tu_choi_giua_gate" else "hen_goi_lai"
        errs: List[str] = []
        for _, c in items:
            if not no_order(c):
                errs.append(f"hard_case '{hc}' cần success_if.must_not_call_tools chứa order.create")
            if c.get("expected_outcome") != want:
                errs.append(f"hard_case '{hc}' cần expected_outcome={want}")
            if "payment" not in (c.get("facts_established") or {}):
                errs.append(f"hard_case '{hc}': khách phải đã đi tới bước thanh toán của order gate (facts_established.payment)")
            if hc == "hoan_giua_gate" and not (c.get("memory_expectation") or {}).get("blocker"):
                errs.append("hard_case 'hoan_giua_gate' cần memory_expectation.blocker")
        return errs
    if hc == "het_hang_bien_the":
        for _, c in items:
            g, s_ = gt(c), si(c)
            if isinstance(g.get("requested_variant_in_stock"), bool) and g.get("in_stock") is True:
                sku = (s_.get("args_match") or {}).get("sku")
                if s_.get("tool_called") == "order.create" and sku and (c.get("facts_established") or {}).get("variant_sku") == sku:
                    return []
        return ["hard_case 'het_hang_bien_the' cần ground_truth_facts.requested_variant_in_stock (bool) + in_stock True và order.create đúng variant_sku"]
    if hc == "tu_nhan_khach_cu_chua_sdt":
        c1 = calls.get("call_1") or {}
        errs = []
        if c1.get("channel") not in CHAT_CHANNELS:
            errs.append("hard_case 'tu_nhan_khach_cu_chua_sdt' cần cuộc 1 trên kênh chat (chưa có SĐT)")
        if not _RX_RETURNING_CLAIM.search(fold(_customer_text(c1))):
            errs.append("hard_case 'tu_nhan_khach_cu_chua_sdt': lời khách không tự nhận là khách cũ")
        if not any(isinstance(x, str) for x in si(c1).get("forbidden_claims") or []):
            errs.append("hard_case 'tu_nhan_khach_cu_chua_sdt' cần forbidden_claims (agent không được giả vờ nhớ khách)")
        if c1.get("seed_history"):
            errs.append("hard_case 'tu_nhan_khach_cu_chua_sdt' không được có seed_history")
        return errs
    if hc == "so_noi_bang_chu":
        for _, c in items:
            asr = c.get("customer_turns_asr") or []
            if c.get("input_mode") == "asr_transcript" and asr and not any(re.search(r"\d", t) for t in asr) and _RX_SPOKEN_PHONE.search(fold(" ".join(asr))):
                return []
        return ["hard_case 'so_noi_bang_chu' cần customer_turns_asr không chữ số (SĐT đọc ≥ 9 chữ số bằng chữ) và input_mode=asr_transcript"]
    return []


def hard_case_type(hc: Optional[str]) -> Optional[str]:
    h = hc or ""
    if h in DEMO_HARD_CASES:
        return "tái hiện lỗi demo"
    if "doi_y" in h:
        return "đổi ý"
    if "mau_thuan" in h:
        return "mâu thuẫn với phiên trước"
    if "het_han" in h and "het_hang" not in h:
        return "KM hết hạn"
    if "ngoai_tai_lieu" in h or "chinh_sach" in h or "doi_thu" in h or "y_te" in h:
        return "hỏi ngoài tài liệu"
    return "khác (giữ lại)" if h else None


def validate_all(scenarios: Dict[str, Dict[str, Any]], dialogues: Dict[str, Dict[str, Any]]) -> List[Issue]:
    phones: Dict[str, List[str]] = {}
    for sid, s in scenarios.items():
        phones.setdefault(str(s.get("customer_phone")), []).append(sid)
    issues: List[Issue] = []
    lines: List[Tuple[str, str]] = []
    for key, rec in dialogues.items():
        lines += [(key, t["text_written"]) for t in rec["turns"] if t["speaker"] == "C"]
    for sid, s in scenarios.items():
        issues += validate_scenario(s, phones)
    for key, rec in dialogues.items():
        sc = scenarios.get(rec["scenario_id"], {}).get("calls", {}).get(rec["call"])
        issues += validate_dialogue(rec, sc, lines)
    return issues


def distribution(scenarios: Dict[str, Dict[str, Any]], dialogues: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    n_calls = sum(len(s["calls"]) for s in scenarios.values())
    multi = [s for s in scenarios.values() if len(s["calls"]) >= 2]
    three = [s for s in scenarios.values() if len(s["calls"]) >= 3]
    multich = [s for s in scenarios.values() if len({c.get("channel", "hotline") for c in s["calls"].values()}) >= 2]
    hard: Dict[str, int] = {}
    for s in scenarios.values():
        t = hard_case_type(s.get("hard_case"))
        if t:
            hard[t] = hard.get(t, 0) + 1
    personas: Dict[str, int] = {}
    for s in scenarios.values():
        personas[s["persona"]] = personas.get(s["persona"], 0) + 1
    return {"scenarios": len(scenarios), "calls": n_calls, "multi_session": len(multi), "ge3_sessions": len(three), "multi_channel": len(multich),
            "multi_session_scenarios": len(multi), "hard_cases": hard, "personas": personas, "dialogue_files": len(dialogues)}
