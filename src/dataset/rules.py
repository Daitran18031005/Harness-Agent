"""
Luật sinh/kiểm lời thoại BỔ SUNG (người duyệt 2026-10-21) — áp cho 54 kịch bản còn lại, kiểm bằng CODE (không LLM):

  P1  Khách KHÔNG nói thông tin ngoài cốt truyện: giá đối thủ, nhu cầu mới (trẻ nhỏ, diện tích, ngân sách, size, màu), SĐT, số tiền lạ.
      Cần thông tin nào thì thêm vào `customer_facts` của khung (và đáp án) TRƯỚC khi sinh.
  P2  Mỗi lượt agent trả lời ĐỦ mọi câu hỏi khách vừa hỏi (giá + còn hàng + khuyến mãi + bảo hành + giao hàng + thanh toán…).
      Câu trả lời lấy từ ô trống (giá/tồn kho/…) — không để LLM bịa; nếu không có đáp án thì phải nói rõ sẽ kiểm tra/chuyển nhân viên.
  P3  Đa dạng phong cách theo persona/số cuộc: cộc lốc, ngập ngừng ("ờ/à/để chị xem"), ngắt lời – đổi chủ đề, nghe không rõ → nhờ nhắc lại,
      cuộc gọi thứ 3 hết kiên nhẫn; không phải câu nào cũng lịch sự/đủ chủ vị.
  P4  Teencode chỉ ở kênh chat (fanpage/zalo/web chat); hotline là lời nói → chữ Việt chuẩn, không viết tắt kiểu chat.

Mọi hàm trả về danh sách lỗi (chuỗi) — đưa lại cho LLM ở lần sinh lại (`LOI_LAN_TRUOC_PHAI_SUA`) và dùng trong `validate_all`.
"""
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Set

from src.harness.fact_usage import fold

CHAT_CHANNELS = {"chat_fanpage", "zalo_oa", "chat_web", "chat_zalo", "chat_app"}
# ---------------------------------------------------------------------------------------------------- P3: hồ sơ phong cách
PROFILES: Dict[str, Dict[str, Any]] = {
    "curt": {"instruction": "Khách bận, cộc lốc: đa số lượt chỉ 1–5 từ ('giá?', 'còn hàng không', 'ừ lên đơn'), không chào hỏi, không cảm ơn, không câu nào đủ chủ vị.",
             "short_share": 0.5, "polite_max": 0.25},
    "hesitant": {"instruction": "Khách ngập ngừng, phân vân: ít nhất 2 lượt có từ đệm 'ờ', 'à', 'ừm', 'để chị/anh xem', 'hơi phân vân'; câu bỏ lửng; chưa vội chốt.",
                 "markers": ["ờ", "à", "ừm", "ơ", "hmm", "để chị xem", "để anh xem", "để mình xem", "để em xem", "để xem", "phân vân", "chưa chắc", "để suy nghĩ"],
                 "min_marker_turns": 2,
                 "short_share": 0.25, "polite_max": 0.7},
    "interrupting": {"instruction": "Khách hay chen ngang/đổi chủ đề: ít nhất một lượt bỏ lửng câu hoặc mở bằng 'à mà…', 'khoan đã…', 'nhân tiện…' rồi hỏi sang chuyện khác "
                                    "(chuyện mới phải nằm trong cốt truyện).",
                     "markers": ["à mà", "khoan", "nhân tiện", "mà này", "quên", "còn nữa", "mà có", "..."], "min_marker_turns": 1,
                     "short_share": 0.25, "polite_max": 0.7},
    "repeat": {"instruction": "Khách nghe không rõ (đường truyền/ồn): ít nhất một lượt nhờ nhắc lại ('em nói lại giúp chị', 'chưa nghe rõ', 'hả em', 'gì cơ'); "
                              "agent nhắc lại NGẮN gọn đúng thông tin lượt trước (dùng lại cùng ô trống).",
              "markers": ["nói lại", "nhắc lại", "chưa nghe rõ", "không nghe rõ", "hả", "gì cơ", "nghe không rõ", "lặp lại", "alo"], "min_marker_turns": 1,
              "short_share": 0.25, "polite_max": 0.7, "repeat_info": True},
    "impatient": {"instruction": "Khách đã gọi nhiều lần nên hết kiên nhẫn: giọng cộc, nhắc 'em nói mấy lần rồi', 'lần thứ ba rồi', 'nhanh giúp chị', đòi giải quyết ngay; câu ngắn.",
                  "markers": ["mấy lần", "lần thứ", "nói rồi", "đã nói", "nhanh", "mãi", "gấp", "bao nhiêu lần", "lại nữa", "nhiều lần"], "min_marker_turns": 1,
                  "short_share": 0.33, "polite_max": 0.4},
}
_DEFAULT_CYCLE = ["hesitant", "curt", "interrupting", "repeat"]


def style_profile(persona: str, call_name: str) -> str:
    """Tên hồ sơ phong cách — xác định theo persona + số cuộc (không ngẫu nhiên giữa các lần chạy)."""
    try:
        idx = int(str(call_name).rsplit("_", 1)[-1])
    except ValueError:
        idx = 1
    p = fold(persona)
    if idx >= 3 or ("het_kien_nhan" in p and "lan_3" not in p):        # persona "gọi lần 3 hết kiên nhẫn": chỉ cạn kiên nhẫn từ cuộc thứ 3
        return "impatient"
    if "do_du" in p or "so_gia" in p or "phan_van" in p:
        return "hesitant"
    if "da_kenh" in p or "hoi_nhieu" in p or "doi_y" in p:
        return "interrupting"
    if "nhieu_mon" in p or "da_mua" in p or "ban" in p:
        return "curt"
    h = int(hashlib.md5(f"{persona}/{call_name}".encode("utf-8")).hexdigest(), 16)
    return _DEFAULT_CYCLE[h % len(_DEFAULT_CYCLE)]


def profile_instruction(name: str) -> str:
    return PROFILES[name]["instruction"]


def min_short_turns(name: str, n_turns) -> int:
    """Số lượt khách NGẮN tối thiểu phải yêu cầu LLM để luật P3 (`short_share` lượt ≤ 6 từ) đạt với MỌI số lượt khách có thể có.
    Số lượt khách ≈ ceil(tổng/2); yêu cầu = ceil(share × lượt khách tối đa), thêm 1 làm biên nhưng không vượt (lượt khách tối thiểu − 1) để còn lượt dài mang fact."""
    lo, hi = int(n_turns[0]), int(n_turns[1])
    req = math.ceil(PROFILES[name]["short_share"] * math.ceil(hi / 2) - 1e-9)
    return max(req, min(req + 1, max(1, math.ceil(lo / 2) - 1)))


def short_turns_instruction(name: str, n_turns) -> str:
    n = min_short_turns(name, n_turns)
    return (f"BẮT BUỘC có ÍT NHẤT {n} lượt khách chỉ 1–4 từ (ví dụ 'Ừ.', 'COD nhé.', 'Đúng rồi.', 'Giá bao nhiêu?', 'Để chị xem.'). Lượt ngắn vẫn có thể mang fact (tên, thanh toán, 'size 41'…). "
            "Các lượt khác (địa chỉ, SĐT…) được dài hơn. Cuộc thiếu lượt ngắn sẽ bị loại và phải sinh lại.")


# ---------------------------------------------------------------------------------------------------- tiện ích
def _cust(turns) -> List[Dict[str, Any]]:
    return [t for t in turns if t["speaker"] == "C"]


def _words(t: Dict[str, Any]) -> int:
    return len(t["text_written"].split())




def _is_polite(text: str) -> bool:
    f = fold(text)
    return bool(re.search(r"\b(da|vang|xin chao|xin|lam on|cam on|cam on nhieu)\b", f)) or bool(re.search(r"\ba[.,!?]?$", f))


def _marker_hit(text: str, markers: List[str]) -> bool:
    """Marker viết CÓ DẤU, khớp theo từ trên chữ có dấu ("ạ" lịch sự ≠ "à" ngập ngừng; "ngày mai" ≠ "mãi"). Lời khách luôn có dấu (luật prompt)."""
    low = text.lower()
    return any(re.search(rf"(?<!\w){re.escape(m)}(?!\w)" if m[-1].isalpha() else re.escape(m), low) for m in markers)


_MONEY = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)\s*(đồng|đ|triệu|tr|nghìn|ngàn|k)?\b", re.I)


def _money_values(text: str) -> Set[int]:
    """Số tiền (VND) khách/agent nhắc trong câu: '5 triệu', '5tr2', '4.890.000đ', '249k', '2,5 triệu'."""
    out: Set[int] = set()
    low = text.lower()
    for m in re.finditer(r"(?<![\d,.])(\d+)\s*(?:triệu|tr)\s*(\d{1,3})?(?!\d)", low):
        base = int(m.group(1)) * 1_000_000
        if m.group(2):
            out.add(base + int(m.group(2)) * (100_000 if len(m.group(2)) == 1 else 10_000 if len(m.group(2)) == 2 else 1_000))
        out.add(base)
    for m in re.finditer(r"(\d+),(\d+)\s*(?:triệu|tr)", low):
        out.add(int(round(float(f"{m.group(1)}.{m.group(2)}") * 1_000_000)))
    for m in re.finditer(r"(\d{1,3}(?:\.\d{3})+)\s*(?:đ|đồng|₫)?", low):
        out.add(int(m.group(1).replace(".", "")))
    for m in re.finditer(r"(\d+)\s*(?:k|nghìn|ngàn)\b", low):
        out.add(int(m.group(1)) * 1000)
    return {v for v in out if v >= 10_000}


def _fact_numbers(call: Dict[str, Any], all_facts: List[Dict[str, Any]]) -> Set[int]:
    out: Set[int] = set()
    for f in all_facts:
        v = f.get("value")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.add(int(v))
    for spec in (call.get("agent_vars") or {}).values():
        out |= _money_values(str(spec.get("text", "")))
    return out


def _near(v: int, pool: Set[int], tol: float = 0.12) -> bool:
    return any(abs(v - p) <= tol * p for p in pool if p)


# ---------------------------------------------------------------------------------------------------- P1
_RX_COMPETITOR = re.compile(r"\b(ben khac|cho khac|shop khac|noi khac|doi thu|dien may|shopee|lazada|tiki|the gioi di dong|cellphones|fpt shop|nguyen kim)\b")
_RX_CHILD = re.compile(r"\b(bé nhỏ|em bé|con nhỏ|trẻ em|trẻ nhỏ|cháu nhỏ|bỉm|nhà có bé|có bé|có con|con \d+ tuổi|bé \d+ tuổi|bé \w+ tuổi)\b")      # trên chữ CÓ DẤU: "còn nhớ" ≠ "con nhỏ"
_RX_AREA = re.compile(r"\b\d+\s*(?:m2|m vuong|met vuong)\b")
_RX_BUDGET = re.compile(r"\b(ngan sach|khong qua|toi da|trong tam|tam)\b[^.?!]{0,25}\b\d+\s*(?:trieu|tr|k)\b")
_RX_SIZE = re.compile(r"\b(?:size|sz|co)\s*\d{2}\b")
_RX_COLOR = re.compile(r"\b(đen|trắng|hồng|xanh|đỏ|xám|kem|vàng|nâu|tím)\b")
_RX_PHONE = re.compile(r"(?<!\d)0\d{9}(?!\d)")


def check_outside_plot(turns: List[Dict[str, Any]], call: Dict[str, Any], all_facts: Optional[List[Dict[str, Any]]] = None, scenario_phone: str = "") -> List[str]:
    """P1 — lượt khách chứa thông tin không có trong khung (facts của cuộc này + các cuộc trước + kịch bản)."""
    facts = list(all_facts if all_facts is not None else call.get("customer_facts") or [])
    keys = {f["key"] for f in facts}
    plot = fold(" ".join([call.get("customer_plot", ""), call.get("goal", "")] + [f.get("hint", "") for f in facts]))
    plot_raw = " ".join([call.get("customer_plot", ""), call.get("goal", "")] + [f.get("hint", "") for f in facts]).lower()
    fnum = _fact_numbers(call, facts)
    errs: List[str] = []
    agent_money: Set[int] = set()
    for t in turns:
        if t["speaker"] == "A":
            agent_money |= _money_values(t["text_written"])
            continue
        raw, f = t["text_written"], fold(t["text_written"])
        if _RX_COMPETITOR.search(f) and "competitor_price_vnd" not in keys and not _RX_COMPETITOR.search(plot):
            errs.append(f"P1 lượt {t['idx']}: khách nhắc đối thủ/nơi khác ({_RX_COMPETITOR.search(f).group(0)!r}) nhưng cốt truyện không có — thêm fact competitor_price_vnd vào khung hoặc bỏ")
        if _RX_CHILD.search(raw.lower()) and "has_children" not in keys and not _RX_CHILD.search(plot_raw):
            errs.append(f"P1 lượt {t['idx']}: khách nói có trẻ nhỏ ({_RX_CHILD.search(raw.lower()).group(0)!r}) ngoài cốt truyện")
        if _RX_AREA.search(f) and "room_area_m2" not in keys:
            errs.append(f"P1 lượt {t['idx']}: khách nêu diện tích phòng ngoài cốt truyện")
        if _RX_BUDGET.search(f) and "budget_vnd" not in keys:
            errs.append(f"P1 lượt {t['idx']}: khách nêu ngân sách ngoài cốt truyện")
        if _RX_SIZE.search(f) and not ({"size", "size_new"} & keys) and not _RX_SIZE.search(plot):
            errs.append(f"P1 lượt {t['idx']}: khách nêu size ngoài cốt truyện")
        m = _RX_COLOR.search(raw.lower())
        if m and "color" not in keys and m.group(1) not in plot_raw:
            errs.append(f"P1 lượt {t['idx']}: khách nêu màu '{m.group(1)}' ngoài cốt truyện")
        for ph in _RX_PHONE.findall(raw):
            allowed = {str(f_["value"]) for f_ in facts if f_["key"] == "phone_provided"} | ({scenario_phone} if scenario_phone else set())
            if ph not in allowed:
                errs.append(f"P1 lượt {t['idx']}: khách nêu SĐT {ph} không có trong khung")
        for v in _money_values(raw):
            if not _near(v, fnum | agent_money) and not _near(v, {int(p) * 1_000_000 for p in fnum if 0 < p < 1000}):
                errs.append(f"P1 lượt {t['idx']}: khách nêu số tiền {v:,} không có trong khung và agent chưa nói")
    return errs


# ---------------------------------------------------------------------------------------------------- P2
_ASK = re.compile(r"\?|\b(khong|chua|bao nhieu|bn|nao|the nao|ra sao|sao|phai khong|dung khong|may ngay|bao lau|duoc khong|co\b.*\bkhong)\b")
TOPICS = {
    "price": re.compile(r"\b(bao nhieu|bn|nhieu tien|gia (?:bao|sao|the nao|nhieu|ra sao|co|van|con|la|vay|nay)|gia ca)\b"),
    "stock": re.compile(r"\b(con hang|het hang|con khong|con size|con mau|co san|ton kho|con cai nay|con may nay|con san)\b"),
    "promo": re.compile(r"\b(khuyen mai|giam gia|uu dai|qua tang|co qua|tang gi|co tang|voucher|ma giam)\b"),
    "warranty": re.compile(r"\b(bao hanh)\b"),
    "return": re.compile(r"\b(doi tra|hoan tien|tra hang|tra lai hang)\b"),
    "delivery": re.compile(r"\b(giao hang|ship|van chuyen|khi nao nhan|bao lau nhan|may ngay)\b"),
    "payment": re.compile(r"\b(cod|tra gop|chuyen khoan|thanh toan)\b"),
}
_ANS = {
    "price": re.compile(r"\d{1,3}(?:\.\d{3})+|\btrieu\b|\bgia\b.*\d"),
    "stock": re.compile(r"\b(con hang|het hang|het san|con san|con ton|con \d+|khong con|con size|con mau|con du|san hang|co hang|con trong kho|co san)\b"),
    "promo": re.compile(r"\b(khuyen mai|giam|tang|qua|uu dai|chuong trinh|ma giam|het han)\b"),
    "warranty": re.compile(r"\bbao hanh\b"),
    "return": re.compile(r"\b(doi tra|hoan|doi|tra lai)\b"),
    "delivery": re.compile(r"\b(giao|ship|van chuyen|nhan hang|ngay)\b"),
    "payment": re.compile(r"\b(cod|tra gop|chuyen khoan|thanh toan|tien mat)\b"),
}
_DESC_HINT = {"price": ["gia", "phi", "tien"], "stock": ["ton kho", "con hang", "het hang"], "promo": ["khuyen mai", "qua", "ma "],
              "warranty": ["bao hanh"], "return": ["doi tra"], "delivery": ["ngay giao", "giao", "ngay"], "payment": ["thanh toan", "cod"]}
_DEFER = re.compile(r"\b(chua co thong tin|khong co thong tin|xin phep|chuyen (?:may|cho|sang)|kiem tra lai|khong the|khong ho tro|ben em khong|chua the|nhan vien|chuyen vien|goi lai|de em kiem tra|ngoai pham vi)\b")
STOCK_VAR = "stock"


def asked_topics(text: str) -> Set[str]:
    f = fold(text)
    if not _ASK.search(f):
        return set()
    return {k for k, rx in TOPICS.items() if rx.search(f)}


def check_answers_all_questions(turns: List[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """P2 — lượt A ngay sau lượt C phải đáp mọi chủ đề C vừa hỏi (bằng ô trống/từ khóa trả lời, hoặc nói rõ sẽ kiểm tra/chuyển)."""
    errs: List[str] = []
    var_descs = {k: fold(v.get("desc", "")) for k, v in (call.get("agent_vars") or {}).items()}
    for i, t in enumerate(turns[:-1]):
        if t["speaker"] != "C" or turns[i + 1]["speaker"] != "A":
            continue
        asked = asked_topics(t["text_written"])
        if not asked:
            continue
        reply = turns[i + 1]
        f = fold(reply["text_written"])
        used = re.findall(r"\{([a-z_0-9]+)\}", reply.get("text_template", ""))
        used_desc = " ".join(var_descs.get(u, "") for u in used)
        if _DEFER.search(f):
            continue
        missing = []
        for topic in sorted(asked):
            ok = bool(_ANS[topic].search(f)) or any(h in used_desc for h in _DESC_HINT[topic])
            if topic == "stock":
                ok = ok and (any(h in used_desc for h in _DESC_HINT["stock"]) or not var_descs or STOCK_VAR in used)
                if not any(any(h in d for h in _DESC_HINT["stock"]) for d in var_descs.values()):
                    errs.append(f"P2 lượt {t['idx']}: khách hỏi còn hàng nhưng khung KHÔNG có ô trống tồn kho (thêm `stock` vào agent_vars để đáp án là thật)")
                    ok = True                                  # lỗi khung đã báo ở trên; không báo thêm lỗi "thiếu trả lời"
            if not ok:
                missing.append(topic)
        if missing:
            errs.append(f"P2 lượt {reply['idx']}: khách hỏi {sorted(asked)} ở lượt {t['idx']} nhưng agent chưa trả lời: {missing} (dùng ô trống tương ứng)")
    return errs


# ---------------------------------------------------------------------------------------------------- P3 + P4
def check_style(turns: List[Dict[str, Any]], call: Dict[str, Any], persona: str) -> List[str]:
    errs: List[str] = []
    cust = _cust(turns)
    if not cust:
        return errs
    prof_name = style_profile(persona, call.get("name", "call_1"))
    prof = PROFILES[prof_name]
    n = len(cust)
    short = sum(1 for t in cust if _words(t) <= 6)
    polite = sum(1 for t in cust if _is_polite(t["text_written"]))
    if short / n < prof["short_share"] - 1e-9:
        errs.append(f"P3 hồ sơ '{prof_name}': chỉ {short}/{n} lượt khách ≤ 6 từ (cần ≥ {int(prof['short_share'] * 100)}%) — rút ngắn, bỏ bớt câu đủ chủ vị")
    if polite / n > prof["polite_max"] + 1e-9:
        errs.append(f"P3 hồ sơ '{prof_name}': {polite}/{n} lượt khách có từ lịch sự (dạ/vâng/xin/cảm ơn/…ạ; tối đa {int(prof['polite_max'] * 100)}%) — không phải câu nào cũng lịch sự")
    if "markers" in prof:
        hit = sum(1 for t in cust if _marker_hit(t["text_written"], prof["markers"]))
        if hit < prof["min_marker_turns"]:
            errs.append(f"P3 hồ sơ '{prof_name}': cần ≥ {prof['min_marker_turns']} lượt khách thể hiện phong cách này, mới có {hit}. {prof['instruction']}")
    if prof.get("repeat_info"):
        for i, t in enumerate(turns[:-1]):
            if t["speaker"] == "C" and _marker_hit(t["text_written"], prof["markers"]) and turns[i + 1]["speaker"] == "A":
                prev = [x for x in turns[:i] if x["speaker"] == "A"]
                if prev:
                    before = set(re.findall(r"\{([a-z_0-9]+)\}", prev[-1].get("text_template", "")))
                    after = set(re.findall(r"\{([a-z_0-9]+)\}", turns[i + 1].get("text_template", "")))
                    if before and not (before & after):
                        errs.append(f"P3 lượt {turns[i + 1]['idx']}: khách nhờ nhắc lại nhưng agent không nhắc lại thông tin lượt trước (dùng lại cùng ô trống)")
                break
    return errs


_TEEN_TOKEN = re.compile(r"(?<!\w)(ko|k|đc|dc|vs|bn|ntn|mik|hok|hông|thks|tks|j|r|ah|oke|okie)(?!\w)", re.I)


def check_channel_style(turns: List[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """P4 — teencode/viết tắt chỉ ở kênh chat; hotline là lời nói."""
    errs: List[str] = []
    chat = call.get("channel") in CHAT_CHANNELS
    if call.get("style") == "teencode" and not chat:
        errs.append(f"P4 kênh '{call.get('channel')}' không phải kênh chat nhưng style=teencode")
    if not chat:
        for t in _cust(turns):
            m = _TEEN_TOKEN.search(t["text_written"])
            if m:
                errs.append(f"P4 lượt {t['idx']}: lời nói (hotline) có viết tắt kiểu chat '{m.group(0)}'")
            if "text_asr" in t:
                errs.append(f"P4 lượt {t['idx']}: hotline không được có text_asr (teencode)")
    return errs


def plot_rule_errors(turns: List[Dict[str, Any]], call: Dict[str, Any], persona: str, all_facts: Optional[List[Dict[str, Any]]] = None,
                     scenario_phone: str = "") -> List[str]:
    return (check_outside_plot(turns, call, all_facts, scenario_phone) + check_answers_all_questions(turns, call)
            + check_style(turns, call, persona) + check_channel_style(turns, call) + check_order_flow(turns, call) + check_decline_flow(turns, call))


def prior_facts(frame: Dict[str, Any], call: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Facts khách của cuộc này + các cuộc TRƯỚC trong cùng kịch bản (khách được nhắc lại điều đã nói)."""
    out: List[Dict[str, Any]] = []
    for c in frame["calls"]:
        out += list(c.get("customer_facts") or [])
        if c["name"] == call["name"]:
            break
    return out


# ---------------------------------------------------------------------------------------------------- P5: order gate
ORDER_FLOW_STEPS = [
    "1. Agent ĐÃ có/CHƯA có từng mục sau: tên người nhận, địa chỉ, số điện thoại nhận, hình thức thanh toán. Mục khách chưa nói → agent HỎI (tối đa 2 mục mỗi lượt); "
    "mục đã lưu từ cuộc trước → agent chỉ XÁC NHẬN ('… như lần trước, đúng không ạ?', khách trả lời ngắn 'đúng rồi' và KHÔNG đọc lại địa chỉ). "
    "Số điện thoại nhận mặc định là số khách đang gọi/nhắn ({caller_phone}) nhưng vẫn phải xác nhận một lần.",
    "2. Khi đủ thông tin, agent ĐỌC LẠI ĐƠN đúng MỘT lần, trong một lượt: {product}, giá {price}, tổng {readback_total}, giao cho {recipient_name}, SĐT {caller_phone}, "
    "địa chỉ {address}, hình thức {payment_label}, rồi hỏi xác nhận ('mình xác nhận đặt đơn này chứ ạ?'). CHƯA nói mã đơn, CHƯA nói 'đã lên đơn'.",
    "3. Lượt ngay sau đó khách đồng ý RÕ RÀNG, ngắn, không kèm điều kiện/câu hỏi ('ok em', 'đúng rồi', 'vâng chốt đi').",
    "4. Lượt ngay sau lời đồng ý, agent mới chốt: nêu mã đơn {order_id} và ngày/số ngày giao. Khách sửa gì sau khi nghe đọc lại → agent đọc lại đơn mới rồi chờ khách đồng ý lại.",
]
def is_gate_decline_call(call: Dict[str, Any]) -> bool:
    """Cuộc đi tới bước ĐỌC LẠI ĐƠN rồi khách từ chối/hoãn: có ô `readback_total` nhưng cấm `order.create` (D26 từ chối, D28 hoãn…)."""
    si = (call.get("expected") or {}).get("success_if") or {}
    return (not is_order_call(call)) and "readback_total" in (call.get("agent_vars") or {}) and "order.create" in (si.get("must_not_call_tools") or [])


_CALLBACK_CUE = re.compile(r"goi lai|lien he lai|nhan lai|khi nao|tiep tuc|quay lai|ghi nhan")


def check_decline_flow(turns: List[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """P6 — cuộc khách TỪ CHỐI/HOÃN sau khi nghe đọc lại đơn: (1) có lượt agent đọc lại đơn; (2) lượt khách ngay sau KHÔNG phải lời đồng ý; (3) cuộc KHÔNG được kết thúc ở lượt
    khách — agent phải đáp lại; (4) lời đáp không nói đã lên đơn/mã đơn; (5) hoãn (hen_goi_lai) thì agent phải ghi nhận và hẹn quay lại/gọi lại."""
    if not is_gate_decline_call(call):
        return []
    from src.harness.order_gate import is_explicit_consent
    tpl = lambda t: t.get("text_template", t["text_written"])
    required = ("{readback_total}", "{address}", "{recipient_name}", "{caller_phone}")
    rb = [i for i, t in enumerate(turns) if t["speaker"] == "A" and all(r in tpl(t) for r in required)]
    if not rb:
        return ["P6 chưa có lượt agent ĐỌC LẠI ĐƠN (cần {readback_total}, {address}, {recipient_name}, {caller_phone}) trước khi khách từ chối/hoãn"]
    r = rb[-1]
    errs: List[str] = []
    nxt = turns[r + 1] if r + 1 < len(turns) else None
    if nxt is None or nxt["speaker"] != "C":
        errs.append("P6 sau khi đọc lại đơn, lượt kế phải là lời từ chối/hoãn của khách")
    elif is_explicit_consent(nxt["text_written"]):
        errs.append(f"P6 lượt {nxt['idx']}: khách đồng ý đơn nhưng cuộc này KHÔNG tạo đơn — lượt ngay sau khi đọc lại đơn phải là từ chối/hoãn")
    replies = [t for t in turns[r + 2:] if t["speaker"] == "A"]
    if not replies or turns[-1]["speaker"] != "A":
        errs.append("P6 cuộc không được kết thúc ở lượt khách: agent phải ĐÁP LẠI việc từ chối/hoãn bằng một lượt cuối")
        return errs
    said = fold(" ".join(t["text_written"] for t in replies))
    if _CREATED_CLAIM.search(said) or any("{order_id}" in tpl(t) for t in replies):
        errs.append("P6 agent nói đã lên đơn/mã đơn sau khi khách từ chối/hoãn")
    if (call.get("expected") or {}).get("expected_outcome") == "hen_goi_lai" and not _CALLBACK_CUE.search(said):
        errs.append("P6 khách hoãn: agent phải ghi nhận và hẹn quay lại/gọi lại (vd 'ghi nhận', 'gọi lại', 'liên hệ lại', 'khi nào chị tiện')")
    return errs


_CREATED_CLAIM = re.compile(r"\b(da len don|da tao don|ma don|len don thanh cong|dat don thanh cong)\b")
_PHONE_WORDS = ("so dien thoai", "sdt", "so nay", "so may", "so dang goi", "so lien he")


def is_order_call(call: Dict[str, Any]) -> bool:
    return (((call.get("expected") or {}).get("success_if") or {}).get("tool_called")) == "order.create"


def check_order_flow(turns: List[Dict[str, Any]], call: Dict[str, Any]) -> List[str]:
    """P5 — lời thoại cuộc gọi có tạo đơn phải đúng quy trình của order gate (src/harness/order_gate.py): hỏi/xác nhận thông tin → đọc lại đơn →
    khách đồng ý RÕ RÀNG ở lượt ngay sau → mới chốt (mã đơn)."""
    if not is_order_call(call):
        return []
    from src.harness.order_gate import is_explicit_consent
    errs: List[str] = []
    tpl = lambda t: t.get("text_template", t["text_written"])
    required = ("{readback_total}", "{address}", "{recipient_name}", "{caller_phone}")

    def is_readback(t: Dict[str, Any]) -> bool:
        if t["speaker"] != "A":
            return False
        w = fold(t["text_written"])
        return all(r in tpl(t) for r in required) and bool(re.search(r"xac nhan|dung (?:khong|chua)|chot", w)) and "?" in t["text_written"]

    rb = [i for i, t in enumerate(turns) if is_readback(t)]
    order_turns = [i for i, t in enumerate(turns) if t["speaker"] == "A" and "{order_id}" in tpl(t)]
    if not rb:
        errs.append("P5 chưa có lượt agent ĐỌC LẠI ĐƠN (cần {readback_total}, {address}, {recipient_name}, {caller_phone}, hình thức thanh toán và câu hỏi xác nhận)")
        return errs
    if not order_turns:
        errs.append("P5 cuộc gọi tạo đơn nhưng agent chưa nêu mã đơn {order_id}")
    for oi in order_turns:
        prev = [i for i in rb if i < oi]
        if not prev:
            errs.append(f"P5 lượt {turns[oi]['idx']}: nêu mã đơn khi CHƯA đọc lại đơn")
            continue
        r = prev[-1]
        nxt = turns[r + 1] if r + 1 < len(turns) else None
        if not nxt or nxt["speaker"] != "C" or not is_explicit_consent(nxt["text_written"]):
            errs.append(f"P5 lượt {turns[r]['idx']}: sau khi đọc lại đơn, lượt kế phải là khách đồng ý RÕ RÀNG (ngắn, không điều kiện/câu hỏi)")
        elif oi != r + 2:
            errs.append(f"P5 lượt {turns[oi]['idx']}: agent phải chốt đơn (mã đơn) ngay lượt sau lời đồng ý của khách")
    first_consent = next((i + 1 for i in rb if i + 1 < len(turns) and turns[i + 1]["speaker"] == "C"), None)
    for i, t in enumerate(turns):
        if t["speaker"] == "A" and first_consent is not None and i < first_consent and _CREATED_CLAIM.search(fold(t["text_written"])):
            errs.append(f"P5 lượt {t['idx']}: agent nói đã tạo đơn/mã đơn trước khi khách đồng ý")
    before = turns[: rb[0]]
    agent_before = " ".join(fold(t["text_written"]) for t in before if t["speaker"] == "A")
    cust_states = {k for t in before if t["speaker"] == "C" for k in (t.get("states") or [])}
    saved = bool(call.get("saved_address"))
    checks = [("address", ("dia chi",), "địa chỉ"), ("payment", ("thanh toan", "cod", "chuyen khoan"), "hình thức thanh toán"),
              ("recipient_name", ("ten", "nguoi nhan"), "tên người nhận"), ("phone_provided", _PHONE_WORDS, "SĐT nhận hàng")]
    for key, words, label in checks:
        said_by_customer = key in cust_states and not (saved and key == "address")
        asked = any(w in agent_before for w in words)
        if key == "phone_provided":
            ok = asked or said_by_customer
        else:
            ok = said_by_customer or asked
        if saved and key == "address":
            ok = asked and "address" not in cust_states
            if not ok:
                errs.append("P5 khách đã có địa chỉ lưu sẵn: agent chỉ XÁC NHẬN địa chỉ (nêu địa chỉ + 'đúng không ạ') và khách KHÔNG đọc lại địa chỉ")
            continue
        if not ok:
            errs.append(f"P5 trước khi đọc lại đơn, {label} chưa được khách nói hay agent hỏi/xác nhận")
    w = fold(turns[rb[0]]["text_written"])
    if not any(k in w for k in ("cod", "chuyen khoan", "momo", "zalopay", "thanh toan")):
        errs.append("P5 lượt đọc lại đơn thiếu hình thức thanh toán")
    return errs
