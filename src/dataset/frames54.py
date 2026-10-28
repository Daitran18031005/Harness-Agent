"""
KHUNG XÁC ĐỊNH của 54 kịch bản còn lại (SC-D01…SC-D54) — CHƯA gọi LLM. Cùng định dạng với `specs.py` (10 mẫu); mọi đáp án do CODE tính từ mock BTC
(`truth.py`) và bộ chọn sản phẩm của hệ thống (`ProductRetriever`). Cuộc gọi có `order.create` đi qua `apply_order_flow` (order gate).

Cơ cấu (khớp DATASET_PLAN: 64 kịch bản mới = 10 mẫu + 54): nhóm A (đa phiên 2 cuộc) 13 · nhóm B (3 cuộc) 10 · nhóm C (1 cuộc) 31.
`PLAN` liệt kê từng kịch bản: kiểu (archetype) + tham số; `build_frames54()` dựng khung; `distribution()` in bảng phân bố.
"""
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.dataset import truth as T
from src.dataset.specs import apply_order_flow, call, fact, var, _meta

_RET = None


def retr():
    global _RET
    if _RET is None:
        from src.catalog import ProductRetriever
        _RET = ProductRetriever()
    return _RET


NAMES = [("Thảo", "chị"), ("Bình", "anh"), ("Châu", "chị"), ("Đạt", "anh"), ("Giang", "chị"), ("Hiếu", "anh"), ("Khánh", "anh"), ("Linh", "chị"), ("Minh", "anh"),
         ("Ngọc", "chị"), ("Oanh", "chị"), ("Phúc", "anh"), ("Quang", "anh"), ("Trang", "chị"), ("Uyên", "chị"), ("Việt", "anh"), ("Yến", "chị"), ("Bảo", "anh"),
         ("Cúc", "chị"), ("Dũng", "anh"), ("Hà", "chị"), ("Huy", "anh"), ("Lan", "chị"), ("Nam", "anh"), ("Phương", "chị"), ("Sơn", "anh"), ("Tâm", "chị"),
         ("Vân", "chị"), ("Hòa", "anh"), ("Kiên", "anh")]
ADDR_B = ["số 14 phố Tây Sơn, quận Đống Đa, Hà Nội", "số 60 đường Láng, quận Cầu Giấy, Hà Nội", "số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội",
          "số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội", "số 31 phố Nguyễn Chí Thanh, quận Ba Đình, Hà Nội", "số 5 đường Phạm Văn Đồng, quận Bắc Từ Liêm, Hà Nội"]
ADDR_N = ["số 48 đường Võ Văn Tần, quận 3, TP.HCM", "số 17 đường Lý Thường Kiệt, quận Tân Bình, TP.HCM", "số 76 đường Nguyễn Huệ, quận 1, TP.HCM",
          "số 130 đường Phan Văn Trị, quận Gò Vấp, TP.HCM", "số 8 đường Trần Não, TP. Thủ Đức, TP.HCM", "số 25 đường Hùng Vương, quận Ninh Kiều, Cần Thơ"]
HEAD = "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)"
D0 = "2026-10-15"


def person(i: int) -> Tuple[str, str]:
    return NAMES[(i - 1) % len(NAMES)]


def phone(i: int) -> str:
    return f"09000200{i:02d}"


# i → south của các khung đã có lời thoại ĐẠT chứa địa chỉ cũ (lô đại diện 2026-10-27): giữ nguyên để không phải sinh lại
ADDR_LEGACY = {3: False, 4: False, 24: False, 26: False, 27: False, 31: False}


def _shift_no(a: str, n: int) -> str:
    return re.sub(r"^số (\d+)", lambda m: f"số {int(m.group(1)) + n}", a)


def _pool_addr(i: int, south: bool) -> str:
    pool = ADDR_N if south else ADDR_B
    return pool[(i - 1) % len(pool)]


def addr(i: int, south: bool = False) -> str:
    """Bảng chỉ 6 địa chỉ/miền nên i và i+6 trùng → S10 báo trùng câu giữa các kịch bản. Từ vòng thứ 2 đổi số nhà (+2 mỗi vòng) để địa chỉ là DUY NHẤT;
    khung đã sinh đạt (ADDR_LEGACY) giữ địa chỉ cũ, khung khác nếu trùng địa chỉ của chúng thì +1."""
    if ADDR_LEGACY.get(i) == bool(south):
        return _pool_addr(i, south)
    out = _shift_no(_pool_addr(i, south), 2 * ((i - 1) // 6))
    return _shift_no(out, 1) if out in {_pool_addr(j, s) for j, s in ADDR_LEGACY.items()} else out


def parent(sku: str) -> str:
    return T.PRODUCTS[sku]["sku"] if sku in T.PRODUCTS else sku.rsplit("-", 2)[0]


def pv(sku: str, desc: str = HEAD) -> Dict[str, Any]:
    return var(T.product_name(sku), desc, ("sku", parent(sku)))


def price_var(q: Dict[str, Any], desc: str = "giá cuối (đã tính khuyến mãi)") -> Dict[str, Any]:
    return var(T.money(q["final_price_vnd"]), desc, ("price_vnd", q["final_price_vnd"]))


def variants(sku: str) -> List[Dict[str, Any]]:
    return T.PRODUCTS[sku].get("variants") or []


def vsku(sku: str, size: Any, color: str) -> str:
    return next(v["variant_sku"] for v in variants(sku) if str(v["size"]) == str(size) and v["color"] == color)


COLOR_VI = {"den": "đen", "trang": "trắng", "xam": "xám", "navy": "xanh navy", "be": "be"}


def facts_for(slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for k, v in slots.items():
        if k == "room_area_m2":
            out.append(fact(k, v, f"phòng khoảng {v:g}m²"))
        elif k == "has_children":
            out.append(fact(k, True, "nhà có bé nhỏ"))
        elif k == "budget_vnd":
            out.append(fact(k, v, f"ngân sách tầm {v / 1e6:g} triệu"))
    return out


# ============================================================================================ NHÓM A (2 cuộc)
BLOCKERS = {"chong": ("can hoi chong", "để chị hỏi chồng đã", "chồng đã đồng ý rồi"), "vo": ("can hoi vo", "để anh hỏi vợ đã", "vợ anh đồng ý rồi"),
            "bome": ("can hoi bo me", "để mình hỏi bố mẹ đã", "bố mẹ đồng ý rồi")}


def adv(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """A1 — hỏi tư vấn qua chat (có blocker) → gọi hotline chốt. Sản phẩm = đứng đầu `ProductRetriever` theo slot khách nêu."""
    name, hon = person(i)
    ph, d1, d2 = phone(i), p.get("d1", "2026-10-14"), p.get("d2", "2026-10-16")
    res = retr().shortlist(p["slots"], category=p["category"])
    assert res.decision["mode"] == "single", (p, res.decision)
    sku = res.items[0].sku
    q1, q2 = T.quote(sku, d1), T.quote(sku, d2)
    ad = addr(i)
    o = T.simulate_order(ph, sku, q2["final_price_vnd"], None, "COD", ad, d2)
    over = res.decision.get("overage_pct") or 0
    code, say, resolved = BLOCKERS[p["blocker"]]
    v1 = {"product": pv(sku, "tên sản phẩm đề xuất"), "price": price_var(q1)}
    if over:
        v1["overage"] = var(f"{round(over)}%", "mức giá vượt ngân sách khách nêu")
    v2 = {"product": pv(sku, "tên sản phẩm khách đã hỏi ở cuộc trước"), "price": price_var(q2, "giá cuối hôm nay"),
          "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao dự kiến"),
          "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    why = "; ".join(m["why"] for m in res.items[0].matched[:2]) or "phù hợp nhu cầu"
    c1 = call("call_1", p["ch1"], f"hỏi tư vấn {p['phrase']} qua chat", "customer",
              f"Khách nhắn hỏi {p['phrase']}. Khi được hỏi mới nói: " + "; ".join(f["hint"] for f in facts_for(p["slots"])) + f". Nghe giá xong nói '{say}' và đọc SĐT để hotline gọi lại.",
              f"Agent hỏi các thông tin còn thiếu (một câu mỗi lượt), đề xuất MỘT sản phẩm {{product}} giá {{price}} (lý do chọn: {why})"
              + (" nêu rõ giá vượt ngân sách {overage}" if over else "") + "; ghi nhận khách cần hỏi người nhà và xin SĐT để gọi lại.",
              facts_for(p["slots"]) + [fact("blocker", code, say), fact("phone_provided", ph, f"đọc SĐT {ph} để hotline gọi lại")], v1,
              {"facts_established": {"product_advised": parent(sku), **p["slots"], "price_quoted_vnd": q1["final_price_vnd"], "blocker": code,
                                     "channel": "fanpage" if p["ch1"] == "chat_fanpage" else "zalo", "phone_provided": ph}, "expected_outcome": "hen_goi_lai"},
              n_turns=(7, 10), identity=f"{'fb' if p['ch1'] == 'chat_fanpage' else 'zalo'}.d{i:02d}", date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "gọi hotline chốt đơn sau khi hỏi người nhà", "agent",
              f"Khách gọi hotline: 'vừa nhắn hỏi {p['phrase']}'; {resolved}; hỏi giá còn như cũ không; chốt lấy, giao về {ad}, COD (không nhắc lại thông tin đã nói ở cuộc 1).",
              "Agent nhận ra khách từ cuộc chat, xác nhận {product} giá {price}, KHÔNG hỏi lại các thông tin đã có; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("blocker_resolved", True, resolved), fact("payment", "COD", "thanh toán khi nhận hàng (COD)"), fact("address", ad, f"giao về {ad}")], v2,
              {"must_carry_over": ["product_advised", "price_quoted_vnd", *[k for k in p["slots"] if k in ("room_area_m2", "has_children")], "blocker"],
               "must_not_ask": ["product_advised", *[k for k in p["slots"] if k in ("room_area_m2", "has_children", "budget_vnd")]],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "price_vnd": q2["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "in_stock": T.stock(sku, d2)["in_stock"]},
               "memory_expectation": {**{k: v for k, v in p["slots"].items() if k != "budget_vnd"}, "product_advised": parent(sku)},
               "expected_outcome": "chot_don"}, n_turns=(8, 11), days_later=2, abs_date=d2)
    return {"scenario": _meta(f"SC-D{i:02d}", "A", p["persona"], None, ph, name, hon, f"A1 tư vấn qua chat → chốt hotline ({p['phrase']}); sản phẩm đứng đầu theo luật slot."), "calls": [c1, c2]}


def size_conflict(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """A2 — mâu thuẫn với phiên trước: size/màu khách nói ở cuộc 2 khác cuộc 1; bộ nhớ phải ghi giá trị MỚI."""
    name, hon = person(i)
    ph, d1, d2 = phone(i), "2026-10-15", "2026-10-18"
    sku, (s1, c1_), (s2, c2_) = p["sku"], p["v1"], p["v2"]
    v1sku, v2sku = vsku(sku, s1, c1_), vsku(sku, s2, c2_)
    q1, q2 = T.quote(v1sku, d1), T.quote(v2sku, d2)
    ad = addr(i, p.get("south", False))
    o = T.simulate_order(ph, v2sku, q2["final_price_vnd"], None, "COD", ad, d2)
    rd = T.attr(sku, "return_days")
    unit = "size"
    vv1 = {"product": pv(sku), "price": price_var(q1, f"giá cuối {unit} {s1} màu {COLOR_VI[c1_]}"), "return_days": var(str(rd), "số ngày đổi trả")}
    vv2 = {"product": pv(sku), "price": price_var(q2, f"giá cuối {unit} {s2} màu {COLOR_VI[c2_]}"), "old_size": var(str(s1), "size khách nói ở cuộc trước (đã lưu)"),
           "new_size": var(str(s2), "size khách vừa đổi"), "old_color": var(COLOR_VI[c1_], "màu cũ đã lưu"), "new_color": var(COLOR_VI[c2_], "màu mới khách chọn"),
           "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao")}
    c1 = call("call_1", "hotline", f"hỏi {T.product_name(sku)}, chưa quyết", "agent",
              f"Khách hỏi chi tiết: {T.product_name(sku)} {unit} {s1} màu {COLOR_VI[c1_]} giá bao nhiêu, đổi trả thế nào; cuối cùng 'để {hon} xem thêm' (chưa mua).",
              f"Agent báo giá {{price}} cho {unit} {s1} màu {COLOR_VI[c1_]}, chính sách đổi trả {{return_days}} ngày; không ép mua.",
              [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}"), fact("size", s1, f"size {s1}"), fact("color", c1_, f"màu {COLOR_VI[c1_]}")], vv1,
              {"facts_established": {"product_advised": parent(sku), "size": s1, "color": c1_, "price_quoted_vnd": q1["final_price_vnd"]}, "expected_outcome": "hen_goi_lai"},
              n_turns=(6, 8), date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "gọi lại, ĐỔI size/màu khác lần trước rồi chốt", "agent",
              f"Khách gọi lại: 'hôm trước {hon} nói {unit} {s1} màu {COLOR_VI[c1_]} nhưng nhầm, {hon} dùng {unit} {s2} và muốn màu {COLOR_VI[c2_]}'; chốt lấy, COD, giao về {ad}.",
              "Agent KHÔNG hỏi lại sản phẩm/giá; ghi nhận đúng thay đổi (size {old_size}→{new_size}, màu {old_color}→{new_color}) và báo giá {price}; theo quy trình đặt đơn rồi chốt: "
              "mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("size", s2, f"{unit} {s2}"), fact("color", c2_, f"màu {COLOR_VI[c2_]}"), fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], vv2,
              {"must_carry_over": ["product_advised"], "must_not_ask": ["product_advised"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": v2sku, "price_vnd": q2["final_price_vnd"]}},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "in_stock": T.stock(v2sku, d2)["in_stock"]},
               "memory_expectation": {"size": s2, "color": c2_, "superseded": {"size": s1, "color": c1_}}, "expected_outcome": "chot_don"},
              n_turns=(7, 10), days_later=3, abs_date=d2)
    return {"scenario": _meta(f"SC-D{i:02d}", "A", p["persona"], "mau_thuan_phien_truoc", ph, name, hon,
                              "Mâu thuẫn với phiên trước: size/màu cuộc 2 khác cuộc 1 → ghi giá trị MỚI, đánh dấu giá trị cũ bị thay thế."), "calls": [c1, c2]}


def promo_expired(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """A3 — khuyến mãi hết hạn giữa hai cuộc: cuộc 2 phải báo giá/quà thật hôm nay, không giữ ưu đãi cũ."""
    name, hon = person(i)
    ph, d1, d2 = phone(i), p["d1"], p["d2"]
    sku, code = p["sku"], p["promo"]
    q1, q2 = T.quote(sku, d1), T.quote(sku, d2)
    pr = T.promo(code)
    assert T.promo_active(code, d1) and not T.promo_active(code, d2), (code, d1, d2)
    ad = addr(i, p.get("south", False))
    o = T.simulate_order(ph, sku, q2["final_price_vnd"], None, "COD", ad, d2)
    end = pr["end"]
    gift = T.product_name(pr["gift_sku"]) if pr.get("gift_sku") else None
    is_gift = bool(gift)
    v1 = {"product": pv(sku), "price": price_var(q1, "giá cuối (đã tính khuyến mãi)"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi", ("promo_expiry", end))}
    v2 = {"product": pv(sku), "price": price_var(q2, "giá hôm nay (khuyến mãi đã kết thúc)"), "promo_end": var(T.dmy(end), "ngày khuyến mãi đã kết thúc", ("promo_expiry", end)),
          "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
          "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    if is_gift:
        v1["gift"], v2["gift"] = var(gift, "quà tặng kèm"), var(gift, "quà tặng trước đây")
        offer = f"có tặng {gift}"
    else:
        v1["old_price"] = v1["price"]
        v2["old_price"] = var(T.money(q1["final_price_vnd"]), "giá khuyến mãi cũ (đã hết hạn)", ("price_vnd", q1["final_price_vnd"]))
        offer = f"giá {T.money(q1['final_price_vnd'])}"
    c1 = call("call_1", p["ch1"], f"hỏi {T.product_name(sku)} và khuyến mãi", "customer",
              f"Khách nhắn hỏi {T.product_name(sku)} giá bao nhiêu, nghe nói đang có khuyến mãi; nói 'để {hon} suy nghĩ rồi gọi hotline' và đọc SĐT.",
              "Agent báo {product} giá {price}" + (", có tặng {gift} đến hết {promo_end}" if is_gift else ", đang giảm đến hết {promo_end}") + "; xin SĐT để hotline gọi lại.",
              [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}"), fact("phone_provided", ph, f"đọc SĐT {ph}")], v1,
              {"facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q1["final_price_vnd"], "promo_code": code, "promo_expiry": end,
                                     "channel": "fanpage" if p["ch1"] == "chat_fanpage" else "zalo", "phone_provided": ph}, "expected_outcome": "hen_goi_lai"},
              n_turns=(6, 8), identity=f"{'fb' if p['ch1'] == 'chat_fanpage' else 'zalo'}.d{i:02d}", date=d1, abs_date=d1)
    forbidden = [{"field": f"promo_{code}_active", "value": True}] if is_gift else [{"field": "price_vnd", "value": q1["final_price_vnd"]}]
    c2 = call("call_2", "hotline", "gọi lại khi khuyến mãi đã hết hạn rồi vẫn mua", "agent",
              f"Khách gọi: '{hon} gọi lấy {T.product_name(sku)} hôm trước, vẫn {offer} đúng không?'; nghe tin khuyến mãi đã hết thì hơi tiếc nhưng vẫn lấy, COD, giao về {ad}.",
              "Agent nói rõ khuyến mãi đã kết thúc ngày {promo_end}; báo giá hôm nay {price}" + ("; KHÔNG còn quà {gift}, không hứa tặng bù" if is_gift else "; KHÔNG còn mức giá cũ {old_price}, không hứa giữ giá")
              + "; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], v2,
              {"must_carry_over": ["product_advised"], "must_not_ask": ["product_advised"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "price_vnd": q2["final_price_vnd"]}, "forbidden_claims": forbidden},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], f"promo_{code}_active": False, "in_stock": T.stock(sku, d2)["in_stock"]},
               "expected_outcome": "chot_don"}, n_turns=(7, 10), days_later=(__import__("datetime").datetime.strptime(d2, "%Y-%m-%d") - __import__("datetime").datetime.strptime(d1, "%Y-%m-%d")).days,
              abs_date=d2)
    return {"scenario": _meta(f"SC-D{i:02d}", "A", p["persona"], "khuyen_mai_het_han", ph, name, hon,
                              f"Khuyến mãi {code} hết {end}: cuộc 1 ({d1}) còn hạn, cuộc 2 ({d2}) đã hết → agent không giữ ưu đãi cũ."), "calls": [c1, c2]}


def saved_address(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """A4 — khách cũ đã có địa chỉ/tên/thanh toán lưu từ đơn trước: mua thêm → order gate chỉ XÁC NHẬN (khách không đọc lại địa chỉ)."""
    name, hon = person(i)
    ph, d1, d2 = phone(i), "2026-10-13", "2026-10-17"
    s1, s2 = p["sku1"], p["sku2"]
    sku1 = vsku(s1, *p["variant"]) if p.get("variant") else s1
    q1, q2 = T.quote(sku1, d1), T.quote(s2, d2)
    ad = addr(i, p.get("south", False))
    o1 = T.simulate_order(ph, sku1, q1["final_price_vnd"], None, "COD", ad, d1)
    o2 = T.simulate_order(ph, s2, q2["final_price_vnd"], None, "COD", ad, d2)
    v1 = {"product": pv(sku1), "price": price_var(q1), "order_id": var(o1["order_id"], "mã đơn", ("order_id", o1["order_id"])),
          "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"), "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    v2 = {"product": pv(s2), "price": price_var(q2), "order_id": var(o2["order_id"], "mã đơn", ("order_id", o2["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
          "prev_product": pv(sku1, "sản phẩm khách đã mua ở đơn trước")}
    fv = [fact("product_asked", parent(sku1), f"hỏi mua {T.product_name(sku1)}")] + ([fact("size", p["variant"][0], f"size {p['variant'][0]}"), fact("color", p["variant"][1], f"màu {COLOR_VI[p['variant'][1]]}")] if p.get("variant") else [])
    c1 = call("call_1", "hotline", f"mua {T.product_name(sku1)}", "agent",
              f"Khách mới gọi mua {T.product_name(sku1)}" + (f" size {p['variant'][0]} màu {COLOR_VI[p['variant'][1]]}" if p.get("variant") else "") + f", COD, giao về {ad}.",
              "Agent báo {product} giá {price}; theo quy trình đặt đơn (hỏi tên/địa chỉ/thanh toán, đọc lại đơn) rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.",
              fv + [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], v1,
              {"success_if": {"tool_called": "order.create", "args_match": {"sku": sku1, "price_vnd": q1["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q1["final_price_vnd"], "in_stock": T.stock(sku1, d1)["in_stock"]},
               "facts_established": {"product_advised": parent(sku1), "price_quoted_vnd": q1["final_price_vnd"], "order_id": o1["order_id"], "payment": "COD"},
               "expected_outcome": "chot_don"}, n_turns=(6, 9), date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", f"mua thêm {T.product_name(s2)} cho đơn trước", "agent",
              f"Khách gọi lại: 'lấy thêm {T.product_name(s2)} cho cái {T.product_name(sku1)} hôm trước, giao như lần trước nhé'; khi agent xác nhận địa chỉ/người nhận/COD đã lưu thì trả lời ngắn 'đúng rồi' (KHÔNG đọc lại địa chỉ).",
              "Agent nhận ra khách và đơn trước {prev_product}; báo giá {price} của {product}; chỉ XÁC NHẬN địa chỉ/người nhận/SĐT/thanh toán đã lưu (không hỏi lại), đọc lại đơn, khách đồng ý rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("product_asked", s2, f"muốn mua thêm {T.product_name(s2)}")], v2,
              {"must_carry_over": ["product_advised", "order_id", "payment"], "must_not_ask": ["product_advised", "payment"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": s2, "price_vnd": q2["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "in_stock": T.stock(s2, d2)["in_stock"]}, "expected_outcome": "chot_don"},
              n_turns=(6, 9), days_later=4, abs_date=d2)
    c2["saved_address"] = ad
    return {"scenario": _meta(f"SC-D{i:02d}", "A", p["persona"], None, ph, name, hon,
                              "Khách cũ có sẵn địa chỉ/tên/thanh toán từ đơn trước: cuộc 2 order gate chỉ XÁC NHẬN rồi đọc lại đơn (khách không đọc lại địa chỉ)."), "calls": [c1, c2]}


# ============================================================================================ NHÓM B (3 cuộc)
def exchange(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """B1 — hỏi giá (chat) → chốt (chat khác) → đổi size ở hotline (phụ thu theo `price_delta_vnd` thật của biến thể)."""
    name, hon = person(i)
    ph, d1, d2, d3 = phone(i), "2026-10-14", "2026-10-15", "2026-10-18"
    sku, (s1, col), s2 = p["sku"], p["v1"], p["size2"]
    v1sku, v2sku = vsku(sku, s1, col), vsku(sku, s2, col)
    q = T.quote(v1sku, d1)
    ad = addr(i, p.get("south", False))
    sim = T.simulate_exchange(ph, v1sku, q["final_price_vnd"], None, ad, d2, v2sku, d3)
    oid, upd = sim["order"]["order_id"], sim["update"]
    assert "error" not in upd, upd
    rd = T.attr(sku, "return_days")
    v1 = {"product": pv(sku), "price": price_var(q, f"giá cuối size {s1} màu {COLOR_VI[col]}")}
    v2 = {"product": pv(sku), "price": price_var(q), "order_id": var(oid, "mã đơn", ("order_id", oid)), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
          "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    extra = upd["extra_payment_vnd"]
    v3 = {"order_id": var(oid, "mã đơn khách đã đặt", ("order_id", oid)), "product": pv(sku), "old_size": var(str(s1), "size hiện tại của đơn"), "new_size": var(str(s2), "size khách muốn đổi"),
          "exchange_fee": var(T.money(upd["fee_vnd"]) if upd["fee_vnd"] else "không", "phí đổi size (miễn phí lần đầu)"), "return_days": var(str(rd), "số ngày đổi trả")}
    if extra:
        v3["extra_payment"] = var(T.money(extra), f"số tiền khách phải trả thêm khi đổi sang size {s2}", ("extra_payment_vnd", extra))
    ch1, ch2 = p["chs"]
    c1 = call("call_1", ch1, f"hỏi giá {T.product_name(sku)} qua chat", "customer",
              f"Khách nhắn hỏi {T.product_name(sku)} size {s1} màu {COLOR_VI[col]} giá bao nhiêu; đọc SĐT {ph}; nói 'tối {hon} nhắn chốt'.",
              f"Agent báo giá {{price}} cho size {s1} màu {COLOR_VI[col]}; xin SĐT.",
              [fact("size", s1, f"size {s1}"), fact("color", col, f"màu {COLOR_VI[col]}"), fact("phone_provided", ph, f"đọc SĐT {ph}")], v1,
              {"facts_established": {"product_advised": parent(sku), "size": s1, "color": col, "price_quoted_vnd": q["final_price_vnd"], "channel": "fanpage" if ch1 == "chat_fanpage" else "zalo",
                                     "phone_provided": ph}, "expected_outcome": "hen_goi_lai"},
              n_turns=(5, 7), identity=f"{'fb' if ch1 == 'chat_fanpage' else 'zalo'}.d{i:02d}", date=d1, abs_date=d1)
    c2 = call("call_2", ch2, "chốt đơn qua chat", "customer",
              f"Khách nhắn: '{hon} hỏi {T.product_name(sku)} hôm qua'; chốt lấy size {s1} màu {COLOR_VI[col]}, COD, giao về {ad}.",
              "Agent nhận ra khách từ cuộc trước, KHÔNG hỏi lại sản phẩm/size/màu; xác nhận giá {price}; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày về {address}.",
              [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], v2,
              {"must_carry_over": ["product_advised", "size", "color", "price_quoted_vnd"], "must_not_ask": ["product_advised", "size", "color"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": v1sku, "price_vnd": q["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(v1sku, d2)["in_stock"]},
               "facts_established": {"order_id": oid, "variant_sku": v1sku, "payment": "COD"}, "expected_outcome": "chot_don"},
              n_turns=(6, 8), identity=f"{'zalo_' if ch2 == 'zalo_oa' else 'fb.'}d{i:02d}b", days_later=1, abs_date=d2)
    tail = (f"nghe phụ thu {T.money(extra)} thì đồng ý" if extra else "nghe không mất phí thì đồng ý")
    c3 = call("call_3", "hotline", f"gọi hotline đổi sang size {s2}", "agent",
              f"Khách gọi: '{hon} mới nhận giày/áo, size {s1} không vừa, đổi lên size {s2} được không, mất phí gì không?'; {tail}, nhờ làm thủ tục đổi.",
              ("Agent biết ngay đơn {order_id} ({product}, size {old_size}); báo chính sách đổi trả {return_days} ngày, phí đổi {exchange_fee}"
               + (", nhưng size {new_size} có phụ thu: khách trả thêm {extra_payment}" if extra else ", size {new_size} không phụ thu") + "; sau khi khách đồng ý thì làm thủ tục đổi. KHÔNG hỏi lại mã đơn/sản phẩm/màu."),
              [fact("size_new", s2, f"đổi lên size {s2}")], v3,
              {"must_carry_over": ["order_id", "variant_sku", "size", "color"], "must_not_ask": ["product_advised", "order_id", "color", "payment"],
               "success_if": {"tool_called": "order.update", "args_match": {"order_id": oid, "new_variant_sku": v2sku, "action": "exchange_size"}},
               "ground_truth_facts": {"return_days": rd, "exchange_fee_vnd": upd["fee_vnd"], "extra_payment_vnd": extra, "new_size_in_stock": True}, "expected_outcome": "chot_don"},
              n_turns=(7, 10), days_later=3, abs_date=d3)
    return {"scenario": _meta(f"SC-D{i:02d}", "B", p["persona"], None, ph, name, hon,
                              f"3 cuộc, 2 kênh chat + hotline: hỏi giá → chốt → đổi size {s1}→{s2}" + (f" có phụ thu {T.money(extra)}." if extra else " không phụ thu.")), "calls": [c1, c2, c3]}


def status_complaint(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """B2 — mua (hotline) → hỏi đơn → khiếu nại giao trễ (khách cạn kiên nhẫn) → chuyển nhân viên kèm Handoff Brief chứa mã đơn."""
    name, hon = person(i)
    ph, d1, d2, d3 = phone(i), "2026-10-12", "2026-10-14", "2026-10-17"
    sku = p["sku"]
    q = T.quote(sku, d1)
    ad = addr(i, p.get("south", False))
    o = T.simulate_order(ph, sku, q["final_price_vnd"], None, "COD", ad, d1)
    est = o["estimated_delivery"]
    v1 = {"product": pv(sku), "price": price_var(q), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])),
          "delivery_date": var(T.dmy(est), "ngày giao dự kiến", ("delivery_date", est)), "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    v2 = {"order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "product": pv(sku), "order_status": var("đã tạo, đang chờ giao", "trạng thái đơn theo hệ thống (order.status)"),
          "delivery_date": var(T.dmy(est), "ngày giao dự kiến", ("delivery_date", est))}
    v3 = {"order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_date": var(T.dmy(est), "ngày giao dự kiến ban đầu", ("delivery_date", est))}
    c1 = call("call_1", "hotline", f"mua {T.product_name(sku)}", "agent",
              f"Khách gọi mua {T.product_name(sku)}, hỏi giá; chốt luôn, COD, giao về {ad}.",
              "Agent báo {product} giá {price}; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, dự kiến giao {delivery_date} tại {address}.",
              [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], v1,
              {"success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "price_vnd": q["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(sku, d1)["in_stock"]},
               "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"], "order_id": o["order_id"], "payment": "COD"}, "expected_outcome": "chot_don"},
              n_turns=(6, 9), date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "hỏi đơn đến đâu rồi", "agent",
              f"Khách gọi hỏi 'đơn {T.product_name(sku)} hôm trước của {hon} đến đâu rồi?' (không đọc mã đơn); nghe trả lời thì nói 'ừ, {hon} chờ thêm'.",
              "Agent tra đơn bằng thông tin đã lưu (KHÔNG hỏi mã đơn/sản phẩm), báo đơn {order_id} {order_status}, dự kiến giao {delivery_date}.",
              [fact("order_query", True, "hỏi đơn hôm trước đến đâu rồi")], v2,
              {"must_carry_over": ["order_id", "product_advised"], "must_not_ask": ["order_id", "product_advised", "payment"],
               "success_if": {"tool_called": "order.status"}, "ground_truth_facts": {"order_status": "created"}, "expected_outcome": "hen_goi_lai"},
              n_turns=(5, 7), days_later=2, abs_date=d2)
    c3 = call("call_3", "hotline", "khiếu nại giao trễ → chuyển nhân viên", "agent",
              f"Khách bực, cộc lốc: đơn dự kiến giao {T.dmy(est)} mà giờ vẫn chưa nhận; đòi gặp người có thẩm quyền xử lý.",
              "Agent xin lỗi ngắn gọn, KHÔNG hỏi lại mã đơn, nói đơn {order_id} dự kiến giao {delivery_date} đã quá hạn; không hứa thời hạn; chuyển máy cho nhân viên kèm tóm tắt (handoff).",
              [fact("complaint_late_delivery", True, f"đơn dự kiến giao {T.dmy(est)} mà vẫn chưa nhận")], v3,
              {"must_carry_over": ["order_id"], "must_not_ask": ["order_id", "product_advised"],
               "success_if": {"tool_called": "handoff.transfer", "brief_must_contain": [o["order_id"]]}, "expected_outcome": "chuyen_may"}, n_turns=(5, 7), days_later=3, abs_date=d3)
    return {"scenario": _meta(f"SC-D{i:02d}", "B", "khach_goi_lan_3_het_kien_nhan", None, ph, name, hon,
                              "3 cuộc hotline: mua → hỏi đơn → khiếu nại giao trễ (cạn kiên nhẫn) → chuyển máy với Handoff Brief chứa mã đơn."), "calls": [c1, c2, c3]}


# ============================================================================================ NHÓM C (1 cuộc)
def _sc(i, group, persona, hard, notes, calls, pf=None):
    name, hon = person(i)
    return {"scenario": _meta(f"SC-D{i:02d}", group, persona, hard, pf or phone(i), name, hon, notes), "calls": calls}


def simple_buy(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-mua — khách mới hỏi sản phẩm (còn hàng? giá?) rồi chốt: kiểm cả quy trình order gate với khách chưa có dữ liệu lưu."""
    name, hon = person(i)
    ph, ch = phone(i), p["ch"]
    sku = p["sku"]
    full = vsku(sku, *p["variant"]) if p.get("variant") else sku
    q = T.quote(full, D0, ph, addr(i, p.get("south", False)))
    ad = addr(i, p.get("south", False))
    pay = p.get("payment", "COD")
    o = T.simulate_order(ph, full, q["final_price_vnd"], None, pay, ad, D0)
    v = {"product": pv(sku), "price": price_var(q), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
         "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    vf = [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}")] + ([fact("size", p["variant"][0], f"size {p['variant'][0]}"), fact("color", p["variant"][1], f"màu {COLOR_VI[p['variant'][1]]}")] if p.get("variant") else [])
    ptxt = "COD" if pay == "COD" else "chuyển khoản"
    c = call("call_1", ch, f"hỏi {T.product_name(sku)} rồi mua", "agent" if ch == "hotline" else "customer",
             f"Khách hỏi {T.product_name(sku)}" + (f" size {p['variant'][0]} màu {COLOR_VI[p['variant'][1]]}" if p.get("variant") else "") + f" còn hàng không, giá bao nhiêu; nghe xong chốt lấy, {ptxt}, giao về {ad}. Tính cách: {p['style']}.",
             "Agent trả lời ĐỦ câu hỏi (còn hàng + giá); theo quy trình đặt đơn (hỏi tên/địa chỉ/SĐT/thanh toán, đọc lại đơn) rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.",
             vf + [fact("payment", pay, ptxt), fact("address", ad, f"giao về {ad}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": full, "price_vnd": q["final_price_vnd"], "payment": pay}},
              "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(full, D0)["in_stock"]},
              "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"], "payment": pay}, "expected_outcome": "chot_don"},
             n_turns=(6, 8), identity=None if ch == "hotline" else f"{'zalo' if ch == 'zalo_oa' else 'fb'}.d{i:02d}", date=D0, abs_date=D0)
    return _sc(i, "C", p["persona"], None, f"Khách mới hỏi rồi mua {T.product_name(sku)} ({ch}): kiểm quy trình order gate với khách chưa có dữ liệu lưu.", [c])


def over_budget(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-vượt ngân sách > 20% — nhánh HAI LỰA CHỌN: sản phẩm phù hợp nhất (vượt ngân sách) + sản phẩm tốt nhất trong ngân sách."""
    name, hon = person(i)
    ph = phone(i)
    res = retr().shortlist(p["slots"], category="máy lọc không khí")
    assert res.decision["mode"] == "two_options", (p, res.decision)
    top, alt = res.items[0].sku, res.alternative.sku
    qt, qa = T.quote(top, D0), T.quote(alt, D0)
    over = round(res.decision["overage_pct"])
    ad = addr(i, p.get("south", False))
    choose = p["choose"]
    pick = {"alt": alt, "top": top}.get(choose)
    qp = {"alt": qa, "top": qt}.get(choose)
    o = T.simulate_order(ph, pick, qp["final_price_vnd"], None, "COD", ad, D0) if pick else None
    v = {"product_top": pv(top, "sản phẩm phù hợp nhất nhưng vượt ngân sách"), "price_top": price_var(qt, "giá cuối sản phẩm phù hợp nhất"), "overage": var(f"{over}%", "mức giá sản phẩm phù hợp nhất vượt ngân sách"),
         "product_alt": pv(alt, "sản phẩm tốt nhất TRONG ngân sách"), "price_alt": price_var(qa, "giá cuối sản phẩm trong ngân sách")}
    if pick:
        v.update({"product": pv(pick, "sản phẩm khách chọn"), "price": price_var(qp, "giá cuối sản phẩm khách chọn"), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])),
                  "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"), "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")})
    ends = {"alt": "chọn mẫu TRONG ngân sách", "top": "cân nhắc rồi vẫn chọn mẫu phù hợp nhất dù đắt hơn", "none": "chưa quyết, nhờ nhân viên gọi lại"}[choose]
    facts_c = facts_for(p["slots"]) + ([fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")] if pick else [])
    exp = ({"success_if": {"tool_called": "order.create", "args_match": {"sku": pick, "price_vnd": qp["final_price_vnd"], "payment": "COD"}},
            "ground_truth_facts": {"price_vnd": qp["final_price_vnd"], "overage_pct": over, "in_stock": T.stock(pick, D0)["in_stock"]},
            "facts_established": {"product_advised": pick, **p["slots"], "price_quoted_vnd": qp["final_price_vnd"]}, "expected_outcome": "chot_don"}
           if pick else {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"]},
                         "ground_truth_facts": {"price_vnd": qt["final_price_vnd"], "overage_pct": over}, "facts_established": {**p["slots"]}, "expected_outcome": "hen_goi_lai"})
    c = call("call_1", p["ch"], "hỏi máy lọc không khí có bé nhỏ, ngân sách thấp hơn nhiều so với mẫu phù hợp", "agent" if p["ch"] == "hotline" else "customer",
             f"Khách cần máy lọc không khí: " + "; ".join(f["hint"] for f in facts_for(p["slots"])) + f". Nghe mẫu phù hợp nhất vượt ngân sách nhiều, nghe thêm mẫu trong ngân sách rồi {ends}.",
             "Agent hỏi thông tin còn thiếu; giới thiệu CẢ HAI: {product_top} giá {price_top} (vượt ngân sách {overage}, có khóa an toàn trẻ em/đủ diện tích) và {product_alt} giá {price_alt} (trong ngân sách) để khách chọn; "
             + ("theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày." if pick else "không ép mua, hẹn nhân viên gọi lại."),
             facts_c, v, exp, n_turns=(8, 11), identity=None if p["ch"] == "hotline" else f"{'zalo' if p['ch'] == 'zalo_oa' else 'fb'}.d{i:02d}", date=D0, abs_date=D0)
    return _sc(i, "C", p["persona"], "vuot_ngan_sach_2_lua_chon", f"Vượt ngân sách {over}% (> 20%): nhánh HAI LỰA CHỌN ({T.product_name(top)} vs {T.product_name(alt)}); khách {ends}.", [c])


def change_mind(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-đổi ý giữa cuộc: hỏi mẫu đắt → nghe giá → chuyển sang mẫu rẻ hơn (cùng ngành) → đơn phải đúng sản phẩm CUỐI."""
    name, hon = person(i)
    ph = phone(i)
    s1, s2 = p["sku1"], p["sku2"]
    q1, q2 = T.quote(s1, D0), T.quote(s2, D0)
    ad = addr(i, p.get("south", False))
    o = T.simulate_order(ph, s2, q2["final_price_vnd"], None, "COD", ad, D0)
    v = {"product_first": pv(s1, "sản phẩm khách hỏi ban đầu"), "price_first": price_var(q1, "giá cuối sản phẩm đầu tiên"), "product": pv(s2, "sản phẩm rẻ hơn agent gợi ý và khách chọn"),
         "price": price_var(q2, "giá cuối sản phẩm khách chọn"), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
         "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c = call("call_1", "hotline", "hỏi mẫu cao cấp rồi ĐỔI Ý sang mẫu rẻ hơn", "agent",
             f"Khách hỏi {T.product_name(s1)}; nghe giá thì thấy đắt và ĐỔI Ý: 'thôi cho {hon} cái rẻ hơn'; chọn mẫu agent gợi ý, COD, giao về {ad}.",
             "Agent báo {product_first} giá {price_first}; khi khách đổi ý thì gợi ý MỘT mẫu rẻ hơn cùng loại là {product} giá {price}; theo quy trình đặt đơn rồi chốt {product}, mã đơn {order_id}, giao {delivery_days} ngày. KHÔNG đặt đơn mẫu đầu.",
             [fact("product_asked", parent(s1), f"hỏi {T.product_name(s1)}"), fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": s2, "price_vnd": q2["final_price_vnd"]}},
              "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "in_stock": T.stock(s2, D0)["in_stock"]}, "facts_established": {"product_advised": parent(s2), "price_quoted_vnd": q2["final_price_vnd"]},
              "expected_outcome": "chot_don"}, n_turns=(8, 11), date=D0, abs_date=D0)
    return _sc(i, "C", "khach_so_gia", "doi_y_giua_cuoc", f"Đổi ý giữa cuộc: {T.product_name(s1)} → {T.product_name(s2)}; đơn phải đúng sản phẩm CUỐI.", [c])


def off_doc(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-hỏi ngoài tài liệu — y tế / so giá đối thủ / bảo hành quốc tế: không bịa, không khẳng định chữa bệnh, không hứa khớp giá."""
    name, hon = person(i)
    ph, sku = phone(i), p["sku"]
    q = T.quote(sku, D0)
    w = T.attr(sku, "warranty_months")
    v = {"product": pv(sku), "price": price_var(q), "warranty": var(str(w), "số tháng bảo hành", ("warranty_months", w))}
    kind = p["kind"]
    if kind == "medical":
        plot, aplot = p["plot"], f"Agent KHÔNG tư vấn y tế/không khẳng định chữa bệnh; nói rõ em chỉ có thông tin sản phẩm, khuyên hỏi bác sĩ; chỉ nêu thông tin có thật: {{product}} giá {{price}}, bảo hành {{warranty}} tháng; mời để nhân viên gọi lại."
        facts_c = [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}"), fact("medical_question", True, p["hint"])]
        exp = {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"], "forbidden_claims": p["forbidden"]},
               "ground_truth_facts": {"warranty_months": w, "price_vnd": q["final_price_vnd"]}, "expected_outcome": "hen_goi_lai"}
        hard, persona = "hoi_ngoai_tai_lieu_y_te", "khach_ngoai_pham_vi_chuyen_may"
    elif kind == "competitor":
        cp = p["competitor"]
        plot = f"Khách hỏi {T.product_name(sku)} giá bao nhiêu; nói 'bên {p['shop']} bán {cp / 1e6:g} triệu thôi, bên em có bằng giá không?'; hỏi thêm 'có bảo hành quốc tế không?'; cuối cùng 'để {hon} cân nhắc rồi gọi lại'."
        aplot = "Agent báo {product} giá {price}, bảo hành {warranty} tháng chính hãng; KHÔNG chê đối thủ, KHÔNG hứa khớp giá/giảm không có chương trình; về bảo hành quốc tế nói thẳng là em chưa có thông tin trong tài liệu và sẽ nhờ nhân viên phản hồi."
        facts_c = [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}"), fact("competitor_price_vnd", cp, f"bên {p['shop']} bán rẻ hơn, chỉ {cp / 1e6:g} triệu"), fact("blocker", "so sanh gia", f"để {hon} cân nhắc rồi gọi lại")]
        exp = {"success_if": {"tool_called": None, "agent_must_say": True, "forbidden_claims": [{"field": "price_vnd", "value": cp}, "bảo hành quốc tế có"]},
               "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "warranty_months": w},
               "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"], "competitor_price_vnd": cp, "blocker": "so sanh gia"}, "expected_outcome": "hen_goi_lai"}
        hard, persona = "hoi_ngoai_tai_lieu_doi_thu", "khach_hoi_ngoai_tai_lieu"
    else:      # warranty quốc tế / chính sách lạ
        plot, aplot = p["plot"], "Agent báo {product} giá {price}, bảo hành {warranty} tháng chính hãng; với câu hỏi ngoài tài liệu nói thẳng là em chưa có thông tin và sẽ nhờ nhân viên phản hồi, KHÔNG bịa chính sách."
        facts_c = [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}")]
        exp = {"success_if": {"tool_called": None, "agent_must_say": True, "forbidden_claims": p["forbidden"]}, "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "warranty_months": w}, "expected_outcome": "hen_goi_lai"}
        hard, persona = "hoi_ngoai_tai_lieu_chinh_sach", "khach_hoi_ngoai_tai_lieu"
    c = call("call_1", "hotline", p["goal"], "agent", plot, aplot, facts_c, v, exp, n_turns=(7, 10), date=D0, abs_date=D0)
    return _sc(i, "C", persona, hard, p["notes"], [c])


def cod_limit(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-COD vượt hạn mức 10 triệu: đọc lại đơn (COD) → khách đồng ý → hệ thống báo vượt hạn mức → chuyển khoản → đọc lại đơn mới → chốt."""
    name, hon = person(i)
    ph, sku, qty = phone(i), p["sku"], p["qty"]
    ad = addr(i, p.get("south", False))
    cod = T.simulate_order(ph, sku, None, None, "COD", ad, D0, qty=qty)
    assert cod.get("error") == "cod_limit_exceeded", cod
    bank = T.simulate_order(ph, sku, None, None, "bank", ad, D0, qty=qty)
    q = T.quote(sku, D0)
    total = cod["total_vnd"]
    unit = {2: "hai", 3: "ba"}[qty]
    v = {"product": pv(sku), "unit_price": price_var(q, "giá một sản phẩm"), "total": var(T.money(total), f"tổng tiền {unit} sản phẩm", ("total_vnd", total)),
         "cod_limit": var(T.money(cod["limit_vnd"]), "hạn mức thanh toán COD tối đa một đơn", ("cod_limit_vnd", cod["limit_vnd"])),
         "order_id": var(bank["order_id"], "mã đơn sau khi khách chuyển sang chuyển khoản", ("order_id", bank["order_id"])),
         "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c = call("call_1", "hotline", f"mua {qty} sản phẩm, COD vượt hạn mức → đổi sang chuyển khoản", "agent",
             f"Khách muốn mua {qty} {p['unit']} {T.product_name(sku)}, thanh toán COD, giao về {ad}; nghe COD vượt hạn mức thì đồng ý chuyển khoản.",
             "Agent báo {product} giá {unit_price}/sản phẩm, tổng {total}; theo quy trình đặt đơn (đọc lại đơn với COD, khách đồng ý) rồi đặt đơn thì hệ thống báo vượt hạn mức COD {cod_limit}/đơn; "
             "giải thích rõ và đề nghị chuyển khoản; khách đồng ý → đọc lại đơn chuyển khoản, khách đồng ý rõ ràng rồi chốt: mã đơn {order_id}, giao về {address}.",
             [fact("quantity", qty, f"mua {qty} {p['unit']}"), fact("payment", "COD", "ban đầu muốn COD"), fact("address", ad, f"giao về {ad}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "qty": qty, "payment": "bank"}},
              "ground_truth_facts": {"cod_limit_vnd": cod["limit_vnd"], "total_vnd": total}, "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"]},
              "expected_outcome": "chot_don"}, n_turns=(8, 11), date=D0, abs_date=D0)
    return _sc(i, "C", "khach_mua_nhieu_mon", "cod_vuot_han_muc", f"COD vượt hạn mức 10 triệu ({qty} × {T.product_name(sku)} = {T.money(total)}): chuyển sang chuyển khoản.", [c])


def teencode_buy(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-teencode — khách nhắn không dấu/teencode trên kênh chat rồi chốt (lời viết ra có dấu; teencode do hệ thống áp)."""
    name, hon = person(i)
    ph, sku = phone(i), p["sku"]
    full = vsku(sku, *p["variant"]) if p.get("variant") else sku
    ad = addr(i, p.get("south", False))
    q = T.quote(full, D0, ph, ad)
    o = T.simulate_order(ph, full, q["final_price_vnd"], None, "COD", ad, D0)
    v = {"product": pv(sku), "price": price_var(q), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2" if not p.get("south") else "3", "số ngày giao"),
         "address": var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    vf = [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}")] + ([fact("size", p["variant"][0], f"size {p['variant'][0]}"), fact("color", p["variant"][1], f"màu {COLOR_VI[p['variant'][1]]}")] if p.get("variant") else [])
    c = call("call_1", p["ch"], f"hỏi {T.product_name(sku)} qua chat, nhắn teencode không dấu", "customer",
             f"Khách nhắn hỏi {T.product_name(sku)} còn hàng không, giá bao nhiêu; rồi chốt lấy 1 cái, COD, ship về {ad}. VIẾT CÂU CÓ DẤU BÌNH THƯỜNG (hệ thống sẽ tự chuyển sang teencode/không dấu; tuyệt đối đừng tự viết teencode).",
             "Agent trả lời lịch sự bình thường (có dấu), ĐỦ câu hỏi (còn hàng + giá); theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày về {address}.",
             vf + [fact("payment", "COD", "COD"), fact("address", ad, f"ship về {ad}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": full, "price_vnd": q["final_price_vnd"], "payment": "COD"}},
              "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(full, D0)["in_stock"]},
              "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"], "payment": "COD"}, "expected_outcome": "chot_don", "input_mode": "chat_teencode"},
             n_turns=(6, 8), identity=f"{'zalo' if p['ch'] == 'zalo_oa' else 'fb'}.d{i:02d}", date=D0, style="teencode", abs_date=D0)
    return _sc(i, "C", "khach_da_kenh_fb_hotline", None, "Khách nhắn teencode/không dấu (customer_turns_asr, input_mode chat_teencode): kiểm chuẩn hóa tiếng Việt trước khi hiểu ý.", [c])


def inquiry_only(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-chỉ hỏi — hỏi giá/bảo hành/tồn kho, không mua, hẹn gọi lại (có ca sản phẩm HẾT HÀNG → nêu ngày có hàng trở lại thật)."""
    name, hon = person(i)
    ph, sku = phone(i), p["sku"]
    q = T.quote(sku, D0)
    st = T.stock(sku, D0)
    w = T.attr(sku, "warranty_months")
    stock_txt = "hiện còn hàng" if st["in_stock"] else ("hiện đang hết hàng" + (f", dự kiến có lại ngày {T.dmy(st['restock_expected'])}" if st.get("restock_expected") else ""))
    v = {"product": pv(sku), "price": price_var(q), "warranty": var(str(w), "số tháng bảo hành", ("warranty_months", w))}
    c = call("call_1", p["ch"], f"hỏi {T.product_name(sku)} (chỉ tham khảo)", "agent" if p["ch"] == "hotline" else "customer",
             f"Khách hỏi {T.product_name(sku)}: còn hàng không, giá bao nhiêu, bảo hành mấy tháng; nghe xong nói 'để {hon} tham khảo thêm rồi gọi lại'. Tính cách: {p['style']}.",
             "Agent trả lời ĐỦ cả ba câu hỏi (còn hàng/giá/bảo hành) bằng ô trống; không ép mua; ghi nhận khách sẽ gọi lại." + ("" if st["in_stock"] else " Sản phẩm HẾT HÀNG: nói rõ và nêu ngày dự kiến có lại."),
             [fact("product_asked", parent(sku), f"hỏi {T.product_name(sku)}")], v,
             {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"]},
              "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "warranty_months": w, "in_stock": st["in_stock"]},
              "facts_established": {"product_advised": parent(sku), "price_quoted_vnd": q["final_price_vnd"]}, "expected_outcome": "hen_goi_lai"},
             n_turns=(6, 8), identity=None if p["ch"] == "hotline" else f"{'zalo' if p['ch'] == 'zalo_oa' else 'fb'}.d{i:02d}", date=D0, abs_date=D0)
    c["agent_vars"]["stock"] = var(stock_txt, "tình trạng tồn kho của sản phẩm (còn hàng/hết hàng)")
    return _sc(i, "C", "khach_hoi_nhieu_khong_mua", None, f"Chỉ hỏi {T.product_name(sku)} ({'còn hàng' if st['in_stock'] else 'HẾT HÀNG'}), không mua, hẹn gọi lại.", [c])


def defect(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    """C-khiếu nại lỗi nhà sản xuất — chính sách DT-05 (đổi mới 1-1 trong 30 ngày), khác đổi trả thường 7 ngày."""
    name, hon = person(i)
    ph, sku = phone(i), p["sku"]
    v = {"product": pv(sku)}
    c = call("call_1", "hotline", f"{T.product_name(sku)} bị lỗi {p['days']} ngày sau khi mua", "agent",
             f"Khách gọi: '{T.product_name(sku)} {hon} mua bị lỗi, {p['symptom']}, mới dùng {p['days']} ngày thôi'; hỏi 'vậy giờ xử lý sao em?'.",
             "Agent xin lỗi, nói rõ lỗi kỹ thuật từ nhà sản xuất trong 30 ngày được đổi mới 1-1 theo chính sách (khác đổi trả thường 7 ngày); không hứa thêm điều ngoài tài liệu; ghi nhận và hẹn nhân viên gọi lại.",
             [fact("product_asked", parent(sku), f"nói {T.product_name(sku)} bị lỗi")], v,
             {"success_if": {"must_say_any": ["30 ngày", "ba mươi ngày", "lỗi nhà sản xuất"]}, "ground_truth_facts": {"exchange_window_days": 30}, "expected_outcome": "hen_goi_lai"},
             n_turns=(6, 8), date=D0, abs_date=D0)
    return _sc(i, "C", "khach_khiếu_nại" if False else "khach_goi_lan_3_het_kien_nhan", "khieu_nai_loi_nsx", f"{T.product_name(sku)} lỗi nhà sản xuất sau {p['days']} ngày: chính sách DT-05 (30 ngày đổi mới 1-1).", [c])


BUILDERS: Dict[str, Callable[[int, Dict[str, Any]], Dict[str, Any]]] = {
    "adv": adv, "size_conflict": size_conflict, "promo_expired": promo_expired, "saved_address": saved_address, "exchange": exchange, "status_complaint": status_complaint,
    "simple_buy": simple_buy, "over_budget": over_budget, "change_mind": change_mind, "off_doc": off_doc, "cod_limit": cod_limit, "teencode_buy": teencode_buy,
    "inquiry_only": inquiry_only, "defect": defect}
from src.dataset import frames_extra          # noqa: E402  (kiểu khung mới 2026-10-24; frames_extra import frames54 TRỄ nên không vòng)
BUILDERS.update(frames_extra.BUILDERS)

P_HES, P_SG, P_NHIEU = "khach_do_du_hoi_nguoi_nha", "khach_so_gia", "khach_hoi_nhieu_khong_mua"
# ====================================================================================================== KẾ HOẠCH 54
PLAN: List[Tuple[str, Dict[str, Any]]] = [
    # --- A1: tư vấn chat → hotline chốt (4)
    ("adv", dict(category="máy lọc không khí", phrase="máy lọc không khí cho phòng ngủ", slots={"room_area_m2": 20, "has_children": True, "budget_vnd": 5_500_000}, ch1="chat_fanpage", blocker="chong", persona=P_HES)),
    ("adv", dict(category="máy lọc không khí", phrase="máy lọc không khí cho phòng khách", slots={"room_area_m2": 38, "budget_vnd": 7_000_000}, ch1="zalo_oa", blocker="vo", persona=P_HES, south=True)),
    ("cross_conflict", dict(kind="price", sku="SKU-AP-X", promo="AP-SEP", d1="2026-09-25", d2="2026-10-05", ch1="chat_fanpage")),                       # D03
    ("cross_conflict", dict(kind="info", category="máy lọc không khí", phrase="máy lọc không khí cho phòng ngủ có bé", ch1="zalo_oa", d1="2026-10-14", d2="2026-10-17",
                            slots1={"room_area_m2": 22, "has_children": True, "budget_vnd": 5_800_000}, slots2={"room_area_m2": 38, "budget_vnd": 7_000_000},
                            hints1={"room_area_m2": "phòng ngủ cỡ 22 mét vuông", "has_children": "nhà đang có con nhỏ", "budget_vnd": "ngân sách khoảng 5,8 triệu"})),   # D04
    # --- A2: mâu thuẫn phiên trước (3)
    ("size_conflict", dict(sku="SKU-SN-RUN1", v1=(40, "den"), v2=(41, "xam"), persona=P_NHIEU)),
    ("size_conflict", dict(sku="SKU-SN-CAS", v1=(39, "trang"), v2=(40, "den"), persona=P_NHIEU, south=True)),
    ("size_conflict", dict(sku="SKU-JK-WND", v1=("M", "den"), v2=("L", "navy"), persona=P_NHIEU)),
    # --- A3: khuyến mãi hết hạn (3)
    ("promo_expired", dict(sku="SKU-SN-RUN2", promo="RUN2-SALE", d1="2026-10-05", d2="2026-10-09", ch1="chat_fanpage", persona=P_SG)),
    ("promo_expired", dict(sku="SKU-AP-Y", promo="GIFT-FILTER", d1="2026-10-20", d2="2026-10-24", ch1="zalo_oa", persona=P_SG, south=True)),
    ("promo_expired", dict(sku="SKU-AP-PRO", promo="AIR-OCT", d1="2026-10-28", d2="2026-11-02", ch1="chat_fanpage", persona=P_SG)),
    # --- A4: khách cũ có sẵn địa chỉ → gate chỉ xác nhận (3)
    ("saved_address", dict(sku1="SKU-SN-CAS", variant=(40, "den"), sku2="SKU-SN-SOCK", persona="khach_da_mua_doi_size")),
    ("saved_address", dict(sku1="SKU-AP-Y", sku2="SKU-AP-FLT-X", persona="khach_quay_lai_sau_8_thang", south=True)),
    ("saved_address", dict(sku1="SKU-MB-PUMP1", sku2="SKU-MB-BAG", persona="khach_da_mua_doi_size")),
    # --- B1: hỏi → chốt → đổi size (5)
    ("exchange", dict(sku="SKU-SN-RUN2", v1=(40, "den"), size2=43, chs=("chat_fanpage", "zalo_oa"), persona="khach_da_mua_doi_size")),
    ("exchange", dict(sku="SKU-SN-CAS", v1=(39, "trang"), size2=40, chs=("zalo_oa", "zalo_oa"), persona="khach_da_mua_doi_size", south=True)),
    ("exchange", dict(sku="SKU-SN-TRK", v1=(41, "den"), size2=43, chs=("chat_fanpage", "chat_fanpage"), persona="khach_da_mua_doi_size")),
    ("exchange", dict(sku="SKU-JK-WND", v1=("M", "navy"), size2="XL", chs=("zalo_oa", "chat_fanpage"), persona="khach_da_mua_doi_size")),
    ("exchange", dict(sku="SKU-JK-DWN", v1=("L", "den"), size2="XL", chs=("chat_fanpage", "zalo_oa"), persona="khach_da_mua_doi_size", south=True)),
    # --- B2: mua → hỏi đơn → khiếu nại → chuyển máy (5)
    ("status_complaint", dict(sku="SKU-MB-PUMP2")),
    ("status_complaint", dict(sku="SKU-AP-X", south=True)),
    ("status_complaint", dict(sku="SKU-FAN-DC1")),
    ("status_complaint", dict(sku="SKU-MB-STR1", south=True)),
    ("status_complaint", dict(sku="SKU-AF-6L")),
    # --- C: mua mới, qua order gate (7)
    ("variant_oos", dict(mode="in_stock", sku="SKU-SN-RUN2", variant=(38, "den"), ch="hotline", style="nói nhanh, cộc", persona="khach_mua_nhieu_mon")),      # D24: gõ gọn "38 đen" vẫn CÒN hàng
    ("bargain", dict(sku="SKU-AF-XM", ch="chat_fanpage", end="buy", style="lịch sự, nài nỉ", persona=P_SG, south=True)),                                   # D25
    ("gate_decline", dict(kind="refuse", sku="SKU-SN-CAS", variant=(41, "den"), ch="zalo_oa", style="vui vẻ, nhiều chuyện", persona=P_SG)),                  # D26
    ("variant_oos", dict(mode="sold_out", sku="SKU-JK-DWN", variant=("M", "den"), alt_color="be", ch="hotline", style="vội, ngắt lời", persona="khach_mua_nhieu_mon")),  # D27: M đen HẾT, M be còn
    ("gate_decline", dict(kind="postpone", sku="SKU-MB-STR1", blocker="chong", ch="chat_fanpage", style="lo lắng, hỏi nhiều về an toàn", persona=P_HES)),   # D28
    ("simple_buy", dict(sku="SKU-AP-MINI", ch="hotline", style="ngập ngừng", persona=P_HES, south=True)),                                                  # D29 (giữ 1 ca mua đơn giản)
    ("bargain", dict(sku="SKU-WF-UF", ch="zalo_oa", end="leave", style="thực dụng", persona=P_SG)),                                                        # D30
    # --- C: vượt ngân sách > 20% → HAI LỰA CHỌN (4; yêu cầu ≥ 3)
    ("over_budget", dict(slots={"room_area_m2": 40, "has_children": True, "budget_vnd": 4_000_000}, ch="hotline", choose="alt", persona=P_SG)),
    ("over_budget", dict(slots={"room_area_m2": 40, "has_children": True, "budget_vnd": 4_500_000}, ch="zalo_oa", choose="top", persona=P_HES, south=True)),
    ("over_budget", dict(slots={"room_area_m2": 35, "has_children": True, "budget_vnd": 3_500_000}, ch="hotline", choose="none", persona=P_SG)),
    ("over_budget", dict(slots={"room_area_m2": 45, "has_children": True, "budget_vnd": 5_000_000}, ch="chat_fanpage", choose="alt", persona=P_SG)),
    # --- C: đổi ý giữa cuộc (3)
    ("change_mind", dict(sku1="SKU-WF-RO10", sku2="SKU-WF-UF")),
    ("change_mind", dict(sku1="SKU-AF-6L", sku2="SKU-AF-XM", south=True)),
    ("change_mind", dict(sku1="SKU-MB-STR2", sku2="SKU-MB-STR1")),
    # --- C: hỏi ngoài tài liệu (6)
    ("off_doc", dict(kind="medical", sku="SKU-MB-PUMP1", goal="hỏi công dụng y tế của máy hút sữa (ngoài tài liệu)",
                     plot="Khách lo lắng: bị căng tức ngực, hỏi 'dùng máy hút sữa Spectra S1 có chữa được viêm vú không, bác sĩ chưa khám'; muốn nghe lời khẳng định; cuối cùng đồng ý để nhân viên gọi lại.",
                     hint="hỏi có chữa được viêm vú không", forbidden=["chữa khỏi", "điều trị khỏi", "sẽ khỏi", "giúp khỏi"], notes="Hỏi ngoài tài liệu (y tế): không tư vấn/khẳng định chữa bệnh.")),
    ("off_doc", dict(kind="medical", sku="SKU-AP-Y", goal="hỏi máy lọc không khí có chữa hen suyễn cho bé không (ngoài tài liệu)",
                     plot="Khách có con nhỏ bị hen: hỏi 'máy lọc không khí AirPure Y có chữa được bệnh hen suyễn cho bé không em'; muốn nghe lời khẳng định; cuối cùng 'để chị hỏi bác sĩ rồi gọi lại'.",
                     hint="hỏi có chữa được bệnh hen suyễn cho bé không", forbidden=["chữa khỏi", "điều trị khỏi", "hết hen", "giúp khỏi"], notes="Hỏi ngoài tài liệu (y tế/hen suyễn).")),
    ("off_doc", dict(kind="competitor", sku="SKU-SS-AX40", competitor=5_800_000, shop="Điện Máy Xanh", goal="so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)", notes="So giá đối thủ + bảo hành quốc tế.")),
    ("off_doc", dict(kind="competitor", sku="SKU-WF-RO10", competitor=6_300_000, shop="Nguyễn Kim", goal="so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)", notes="So giá đối thủ (máy lọc nước).")),
    ("off_doc", dict(kind="competitor", sku="SKU-AF-6L", competitor=3_500_000, shop="Shopee", goal="so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)", notes="So giá đối thủ (nồi chiên).")),
    ("off_doc", dict(kind="policy", sku="SKU-FAN-DC1", goal="hỏi chính sách lạ (bảo hành tại nhà, đổi cũ lấy mới) ngoài tài liệu",
                     plot="Khách hỏi quạt Panasonic F-409 giá bao nhiêu; hỏi thêm 'bên em có thu cũ đổi mới quạt cũ nhà mình không, có sửa tại nhà không?'; cuối cùng 'để anh suy nghĩ'.",
                     forbidden=["thu cũ đổi mới quạt", "sửa tại nhà miễn phí", "có thu cũ"], notes="Hỏi chính sách không có trong tài liệu (thu cũ quạt, sửa tại nhà).")),
    # --- C: COD vượt hạn mức (3)
    ("cod_limit", dict(sku="SKU-AP-PRO", qty=2, unit="máy")),
    ("cod_limit", dict(sku="SKU-WF-RO10", qty=2, unit="máy", south=True)),
    ("cod_limit", dict(sku="SKU-AF-6L", qty=3, unit="cái")),
    # --- C: teencode chat (3)
    ("claims_returning", dict(sku="SKU-AF-XM", ch="zalo_oa", style="tự tin, nói như người quen")),                                                          # D47
    ("claims_returning", dict(sku="SKU-MB-MON", ch="chat_fanpage", south=True, style="thân mật")),                                                          # D48
    ("teencode_buy", dict(sku="SKU-JK-WND", variant=("M", "be"), ch="zalo_oa")),
    # --- C: chỉ hỏi, không mua (3, có 1 ca hết hàng)
    ("inquiry_only", dict(sku="SKU-WF-RO9", ch="hotline", style="hỏi tuần tự từng ý")),
    ("spoken_numbers", dict(sku="SKU-XM-4P", budget=4_500_000, style="nói rõ ràng, từng chữ số")),                                                         # D51
    ("spoken_numbers", dict(sku="SKU-MB-STR2", budget=2_800_000, style="nghe không rõ, nhờ nhắc lại")),                                                    # D52
    # --- C: khiếu nại lỗi nhà sản xuất (2)
    ("defect", dict(sku="SKU-AP-X", days=10, symptom="không lên nguồn")),
    ("defect", dict(sku="SKU-WF-UF", days=14, symptom="chảy nước ra sàn")),
]
assert len(PLAN) == 54, len(PLAN)

GROUP_OF = {"adv": "A", "size_conflict": "A", "promo_expired": "A", "saved_address": "A", "cross_conflict": "A", "exchange": "B", "status_complaint": "B"}


def build_frames54() -> List[Dict[str, Any]]:
    frames = []
    for idx, (kind, params) in enumerate(PLAN, start=1):
        fr = BUILDERS[kind](idx, params)
        fr["scenario"]["archetype"] = kind
        fr["scenario"]["industry"] = _industry(kind, params)
        fr["scenario"]["south"] = bool(params.get("south"))
        frames.append(apply_order_flow(fr))
    T.fresh_orders()
    return frames


def _industry(kind: str, p: Dict[str, Any]) -> str:
    sku = p.get("sku") or p.get("sku1") or ("SKU-AP-X" if kind in ("adv", "over_budget", "cross_conflict") else "")
    cat = T.PRODUCTS[sku]["category"] if sku in T.PRODUCTS else "gia-dung/may-loc-khong-khi"
    return {"gia-dung/may-loc-khong-khi": "máy lọc không khí", "gia-dung/may-loc-nuoc": "máy lọc nước", "gia-dung/quat": "quạt", "gia-dung/noi-chien": "nồi chiên",
            "thoi-trang/giay": "giày", "thoi-trang/ao-khoac": "áo khoác", "me-be": "mẹ & bé"}.get(cat, cat)
