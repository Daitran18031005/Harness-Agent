"""
KIỂU KHUNG MỚI (2026-10-24) — duyệt ở docs/DATASET_PLAN.md § 9.1. Vẫn là khung XÁC ĐỊNH (chưa gọi LLM): đáp án do `truth.py` tính từ mock BTC.

  cross_conflict   A  mâu thuẫn với phiên trước, persona `khach_da_kenh_mau_thuan` (kind=price: kênh báo giá khác nhau; kind=info: khách nói khác thông tin đã lưu)
  bargain          C  mặc cả (`mac_ca`): khách đề nghị giá thấp hơn bảng giá; agent giữ giá thật, không tạo đơn ở giá khách đòi
  gate_decline     C  từ chối (`tu_choi_giua_gate`) hoặc hoãn (`hoan_giua_gate`) SAU khi nghe đọc lại đơn: 0 `order.create`
  variant_oos      C  tồn kho theo BIẾN THỂ (`het_hang_bien_the`): gõ gọn "38 đen" vẫn phải thấy còn hàng / biến thể hết thì gợi ý biến thể còn
  claims_returning C  tự nhận khách cũ khi chưa có SĐT (`tu_nhan_khach_cu_chua_sdt`): không giả vờ nhớ, hỏi SĐT, không nối hồ sơ theo lời khai
  spoken_numbers   C  số nói bằng chữ (`so_noi_bang_chu`): `customer_turns_asr` = lời đọc (không chữ số), `input_mode=asr_transcript`

Import `frames54` TRỄ (trong hàm) để tránh vòng: frames54 nạp module này khi đăng ký BUILDERS.
"""
from typing import Any, Dict, List

from src.dataset import truth as T
from src.dataset.specs import PAYMENT_LABEL, _meta, call, fact, var

DEMO_HARD_CASES = ("mac_ca", "tu_choi_giua_gate", "hoan_giua_gate", "het_hang_bien_the", "tu_nhan_khach_cu_chua_sdt", "so_noi_bang_chu")
PERSONA_CHANNEL_CONFLICT = "khach_da_kenh_mau_thuan"
RETURNING_CLAIM_PHRASES = ["em nhớ", "như lần trước", "giống lần trước"]        # lời agent KHÔNG được nói với khách tự nhận (chưa xác minh)


def _F():
    from src.dataset import frames54
    return frames54


def _delivery(p: Dict[str, Any]) -> str:
    return "3" if p.get("south") else "2"


def _addr_var(ad: str) -> Dict[str, Any]:
    return var(ad, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")


def _ident(ch: str, i: int) -> str:
    return f"{'zalo' if ch == 'zalo_oa' else 'fb'}.d{i:02d}"


def _full_sku(F, sku: str, variant) -> str:
    return F.vsku(sku, *variant) if variant else sku


def _variant_facts(F, sku: str, variant) -> List[Dict[str, Any]]:
    out = [fact("product_asked", F.parent(sku), f"hỏi {T.product_name(sku)}")]
    if variant:
        out += [fact("size", variant[0], f"size {variant[0]}"), fact("color", variant[1], f"màu {F.COLOR_VI[variant[1]]}")]
    return out


def _gate_vars(F, i: int, sku: str, q: Dict[str, Any], pay: str, ad: str, ph: str, chat_first: bool) -> Dict[str, Any]:
    """Ô trống để agent ĐỌC LẠI ĐƠN trong cuộc KHÔNG tạo đơn (cuộc tạo đơn được `apply_order_flow` thêm các ô này)."""
    name, _ = F.person(i)
    return {"product": F.pv(sku), "price": F.price_var(q),
            "readback_total": var(T.money(q["final_price_vnd"]), "tổng tiền cả đơn (giá × số lượng) — dùng khi ĐỌC LẠI ĐƠN"),
            "payment_label": var(PAYMENT_LABEL.get(pay, pay), "hình thức thanh toán của đơn — dùng khi ĐỌC LẠI ĐƠN"),
            "recipient_name": var(name, "tên người nhận — CHỈ dùng sau khi khách đã nói tên", after="recipient_name"),
            "address": _addr_var(ad),
            "caller_phone": var(ph, "SĐT nhận hàng (số khách đang gọi/nhắn) — đọc lại để xác nhận", ("phone", ph), after="phone_provided" if chat_first else None)}


# ============================================================================================ A: mâu thuẫn phiên trước (persona khach_da_kenh_mau_thuan)
def cross_conflict(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    name, hon = F.person(i)
    ph, ch1 = F.phone(i), p["ch1"]
    ad = F.addr(i, p.get("south", False))
    d1, d2 = p["d1"], p["d2"]
    if p["kind"] == "price":
        sku, code = p["sku"], p["promo"]
        assert T.promo_active(code, d1) and not T.promo_active(code, d2), (code, d1, d2)
        q1, q2 = T.quote(sku, d1), T.quote(sku, d2)
        assert q1["final_price_vnd"] < q2["final_price_vnd"], (q1, q2)
        end = T.promo(code)["end"]
        sku1 = sku2 = sku
        slots1: Dict[str, Any] = {}
        slots2: Dict[str, Any] = {}
        sup = {"price_quoted_vnd": q1["final_price_vnd"]}
        notes = (f"Mâu thuẫn phiên trước (giá khác giữa các kênh): {ch1} ({d1}) báo {T.money(q1['final_price_vnd'])} còn KM {code}, hotline ({d2}) báo {T.money(q2['final_price_vnd'])} "
                 "→ khách đòi giá thấp nhất từng được báo; agent giải thích KM theo ngày, không hứa giữ giá cũ.")
        plot1 = f"Khách nhắn hỏi {T.product_name(sku)} giá bao nhiêu; nghe giá thì nói 'để {hon} suy nghĩ rồi gọi hotline' và đọc SĐT."
        facts1 = [fact("product_asked", F.parent(sku), f"hỏi {T.product_name(sku)}"), fact("phone_provided", ph, f"đọc SĐT {ph}")]
        plot2 = (f"Khách gọi hotline, BỰC: 'hôm trước {hon} nhắn Fanpage/Zalo họ báo {T.money(q1['final_price_vnd'])}, sao giờ gọi hotline lại báo giá khác, mỗi nơi một giá?'; "
                 f"đòi giá thấp nhất từng được báo; chỉ chấp nhận giá hiện hành nếu agent giải thích rõ (khuyến mãi theo thời điểm) và xin lỗi; nghe giải thích hợp lý thì vẫn lấy, COD, giao về {ad}.")
        facts2 = [fact("prev_quote_vnd", q1["final_price_vnd"], f"nhắc lại giá {T.money(q1['final_price_vnd'])} đã được báo ở kênh chat"),
                  fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")]
        v1 = {"product": F.pv(sku), "price": F.price_var(q1), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi", ("promo_expiry", end))}
        extra2 = {"old_price": var(T.money(q1["final_price_vnd"]), "giá khuyến mãi đã báo ở cuộc trước (nay đã hết)", ("price_vnd", q1["final_price_vnd"])),
                  "promo_end": var(T.dmy(end), "ngày khuyến mãi đã kết thúc", ("promo_expiry", end))}
        agent2 = ("Agent xin lỗi vì khách thấy lệch giá; giải thích khuyến mãi kết thúc ngày {promo_end} nên giá {old_price} ở kênh chat không còn, giá hôm nay là {price}; "
                  "KHÔNG hứa giữ giá cũ; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày. KHÔNG hỏi lại sản phẩm đã biết.")
        fe1 = {"product_advised": F.parent(sku), "price_quoted_vnd": q1["final_price_vnd"], "promo_code": code, "promo_expiry": end, "phone_provided": ph}
        gt2 = {"price_vnd": q2["final_price_vnd"], f"promo_{code}_active": False, "in_stock": T.stock(sku, d2)["in_stock"]}
        forb = [{"field": "price_vnd", "value": q1["final_price_vnd"]}]
        mem2 = {"price_quoted_vnd": q2["final_price_vnd"], "superseded": sup}
        carry = ["product_advised", "price_quoted_vnd"]
    else:
        slots1, slots2 = p["slots1"], p["slots2"]
        cat = p["category"]
        hints1 = p.get("hints1") or {}
        r1, r2 = F.retr().shortlist(slots1, category=cat), F.retr().shortlist(slots2, category=cat)
        assert r1.decision["mode"] == "single" and r2.decision["mode"] == "single", (r1.decision, r2.decision)
        sku1, sku2 = r1.items[0].sku, r2.items[0].sku
        assert sku1 != sku2, (sku1, sku2)
        q1, q2 = T.quote(sku1, d1), T.quote(sku2, d2)
        sup = {k: v for k, v in slots1.items() if k in slots2 and slots2[k] != v}
        notes = (f"Mâu thuẫn phiên trước (thông tin khác): cuộc 1 khách nêu {slots1}, cuộc 2 nói {slots2} → sản phẩm đổi {T.product_name(sku1)} → {T.product_name(sku2)}; "
                 "agent ghi giá trị MỚI, không hỏi lại slot còn đúng.")
        sf1 = [{**f, "hint": hints1.get(f["key"], f["hint"])} for f in F.facts_for(slots1)]         # gợi ý riêng để lời khai không trùng khung khác (S10)
        plot1 = (f"Khách nhắn hỏi {p['phrase']}. Khi được hỏi mới nói: " + "; ".join(f["hint"] for f in sf1) + ". Nghe giá xong nói 'để {h} xem thêm' và đọc SĐT.").replace("{h}", hon)
        facts1 = sf1 + [fact("phone_provided", ph, f"đọc SĐT {ph}")]
        changed = "; ".join(f["hint"] for f in F.facts_for({k: v for k, v in slots2.items() if k in sup}))
        plot2 = (f"Khách gọi hotline, BỰC vì hôm trước nhắn chat được báo {T.product_name(sku1)}, giờ nghe gợi ý mẫu khác: 'hôm trước nhắn họ báo một giá, giờ gọi lại thấy khác'; "
                 f"nói thông tin MỚI (nhầm hôm trước): {changed}; vẫn nhà có bé như đã nói (KHÔNG nhắc lại); đòi được giải thích rõ vì sao đổi mẫu rồi vẫn lấy, COD, giao về {ad}.")
        facts2 = F.facts_for({k: v for k, v in slots2.items() if k in sup}) + [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")]
        v1 = {"product": F.pv(sku1, "tên sản phẩm đề xuất ở cuộc 1"), "price": F.price_var(q1)}
        extra2 = {"old_product": F.pv(sku1, "sản phẩm đã đề xuất ở cuộc trước (theo thông tin cũ)"),
                  "old_price": var(T.money(q1["final_price_vnd"]), "giá sản phẩm đề xuất ở cuộc trước", ("price_vnd", q1["final_price_vnd"]))}
        agent2 = ("Agent xin lỗi vì lệch; giải thích ngắn: theo thông tin MỚI khách vừa nói thì mẫu phù hợp là {product} giá {price} (cuộc trước là {old_product} giá {old_price}); "
                  "ghi nhận thông tin mới, KHÔNG hỏi lại thông tin còn đúng; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.")
        fe1 = {"product_advised": F.parent(sku1), **slots1, "price_quoted_vnd": q1["final_price_vnd"], "phone_provided": ph}
        gt2 = {"price_vnd": q2["final_price_vnd"], "in_stock": T.stock(sku2, d2)["in_stock"]}
        forb = None
        mem2 = {**{k: v for k, v in slots2.items()}, "product_advised": F.parent(sku2), "superseded": sup}
        carry = [k for k in slots1 if k not in sup and k in ("room_area_m2", "has_children")]
    o = T.simulate_order(ph, sku2, q2["final_price_vnd"], None, "COD", ad, d2)
    v2 = {"product": F.pv(sku2), "price": F.price_var(q2, "giá cuối hôm nay"), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])),
          "delivery_days": var(_delivery(p), "số ngày giao dự kiến"), "address": _addr_var(ad), **extra2}
    c1 = call("call_1", ch1, "hỏi giá/tư vấn qua chat rồi để suy nghĩ", "customer", plot1,
              "Agent báo " + ("{product} giá {price}, KM đến hết {promo_end}" if p["kind"] == "price" else "đề xuất MỘT sản phẩm {product} giá {price}") + "; xin SĐT để hotline gọi lại.",
              facts1, v1, {"facts_established": fe1, "expected_outcome": "hen_goi_lai"}, n_turns=(6, 8), identity=_ident(ch1, i), date=d1, abs_date=d1)
    si2: Dict[str, Any] = {"tool_called": "order.create", "args_match": {"sku": sku2, "price_vnd": q2["final_price_vnd"], "payment": "COD"}}
    if forb:
        si2["forbidden_claims"] = forb
    must_not = ["product_advised"] if p["kind"] == "price" else carry
    c2 = call("call_2", "hotline", "gọi hotline, bực vì lệch thông tin so với phiên trước, rồi chốt", "agent", plot2, agent2, facts2, v2,
              {"must_carry_over": carry, "must_not_ask": must_not, "success_if": si2, "ground_truth_facts": gt2, "memory_expectation": mem2, "expected_outcome": "chot_don"},
              n_turns=(8, 11), days_later=(__import__("datetime").datetime.strptime(d2, "%Y-%m-%d") - __import__("datetime").datetime.strptime(d1, "%Y-%m-%d")).days, abs_date=d2)
    return {"scenario": _meta(f"SC-D{i:02d}", "A", PERSONA_CHANNEL_CONFLICT, "mau_thuan_phien_truoc", ph, name, hon, notes), "calls": [c1, c2]}


# ============================================================================================ C: mặc cả
def bargain(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    name, hon = F.person(i)
    ph, ch, sku = F.phone(i), p["ch"], p["sku"]
    ad = F.addr(i, p.get("south", False))
    q = T.quote(sku, F.D0, ph, ad)
    price = q["final_price_vnd"]
    offer = (int(price * p.get("pct", 0.9)) // 100_000) * 100_000
    assert 0 < offer < price, (price, offer)
    buy = p["end"] == "buy"
    v = {"product": F.pv(sku), "price": F.price_var(q)}
    facts = [fact("product_asked", F.parent(sku), f"hỏi {T.product_name(sku)}"), fact("offered_price_vnd", offer, f"đề nghị bớt còn {offer / 1e6:g} triệu")]
    forb = [{"field": "price_vnd", "value": offer}]
    haggle = (f"Khách hỏi {T.product_name(sku)} còn hàng không, giá bao nhiêu; nghe giá thì MẶC CẢ: 'bớt cho {hon} còn {offer / 1e6:g} triệu được không?'; "
              f"agent từ chối thì nài thêm một lần. Tính cách: {p['style']}.")
    agent_haggle = ("Agent báo {product} giá {price}; khi khách mặc cả thì từ chối lịch sự: không có chương trình giảm thêm, KHÔNG tự ý giảm, KHÔNG nhắc lại con số khách đề nghị, "
                    "KHÔNG tạo đơn với giá khách đòi; giữ giá niêm yết {price} (đã gồm khuyến mãi nếu có). ")
    if buy:
        o = T.simulate_order(ph, sku, price, None, "COD", ad, F.D0)
        v.update({"order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var(_delivery(p), "số ngày giao"), "address": _addr_var(ad)})
        facts += [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")]
        plot = haggle + f" Cuối cùng chấp nhận giá thật {T.money(price)}, chốt lấy, COD, giao về {ad}."
        agent = agent_haggle + "Khách chấp nhận giá thật thì theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày."
        exp = {"success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "price_vnd": price, "payment": "COD"}, "forbidden_claims": forb},
               "ground_truth_facts": {"price_vnd": price, "in_stock": T.stock(sku, F.D0)["in_stock"]},
               "facts_established": {"product_advised": F.parent(sku), "price_quoted_vnd": price, "payment": "COD"}, "expected_outcome": "chot_don"}
        n_turns = (7, 9)
    else:
        facts.append(fact("blocker", "so sanh gia", f"để {hon} cân nhắc rồi gọi lại"))
        plot = haggle + f" Cuối cùng KHÔNG mua: 'vậy để {hon} cân nhắc rồi gọi lại'."
        agent = agent_haggle + "Khách chưa mua thì không ép; ghi nhận khách sẽ gọi lại."
        exp = {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"], "forbidden_claims": forb},
               "ground_truth_facts": {"price_vnd": price, "in_stock": T.stock(sku, F.D0)["in_stock"]},
               "facts_established": {"product_advised": F.parent(sku), "price_quoted_vnd": price}, "expected_outcome": "hen_goi_lai"}
        n_turns = (6, 8)
    c = call("call_1", ch, f"hỏi {T.product_name(sku)} rồi mặc cả", "agent" if ch == "hotline" else "customer", plot, agent, facts, v, exp, n_turns=n_turns,
             identity=None if ch == "hotline" else _ident(ch, i), date=F.D0, abs_date=F.D0)
    return F._sc(i, "C", p["persona"], "mac_ca", f"Mặc cả: khách đòi {T.money(offer)} (giá thật {T.money(price)}); agent giữ giá thật, không tạo đơn ở giá khách đòi"
                 + ("; rồi khách chấp nhận giá thật." if buy else "; khách không mua."), [c])


# ============================================================================================ C: từ chối / hoãn giữa gate
def gate_decline(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    name, hon = F.person(i)
    ph, ch, sku = F.phone(i), p["ch"], p["sku"]
    variant = p.get("variant")
    full = _full_sku(F, sku, variant)
    ad = F.addr(i, p.get("south", False))
    q = T.quote(full, F.D0, ph, ad)
    chat_first = ch != "hotline"
    pay = "COD"
    v = _gate_vars(F, i, sku, q, pay, ad, ph, chat_first)
    facts = _variant_facts(F, sku, variant) + [fact("recipient_name", name, f"nói tên người nhận là {name}"), fact("payment", pay, "COD"), fact("address", ad, f"giao về {ad}")]
    if chat_first:
        facts.append(fact("phone_provided", ph, f"đọc SĐT nhận hàng {ph}"))
    refuse = p["kind"] == "refuse"
    base = (f"Khách hỏi {T.product_name(sku)}" + (f" size {variant[0]} màu {F.COLOR_VI[variant[1]]}" if variant else "") + f" còn hàng không, giá bao nhiêu; chốt lấy và trả lời các câu hỏi của agent "
            f"(tên người nhận {name}, địa chỉ {ad}, thanh toán COD). Tính cách: {p['style']}. ")
    fe = {"product_advised": F.parent(sku), "price_quoted_vnd": q["final_price_vnd"], "payment": pay}
    if refuse:
        plot = base + f"Nghe agent ĐỌC LẠI ĐƠN xong thì đổi ý, TỪ CHỐI rõ ràng: 'thôi {hon} không lấy nữa, mắc quá' (KHÔNG đồng ý đơn)."
        outcome, mem = "tu_choi", {"objection": "gia cao"}
        label, notes = "tu_choi_giua_gate", "Từ chối SAU khi nghe đọc lại đơn: không tạo đơn, không nối câu hỏi gate ở lượt sau."
        tail = ("Khách từ chối thì KHÔNG tạo đơn, KHÔNG nêu mã đơn, KHÔNG nói đã lên đơn; xin lỗi nhẹ, hỏi lý do một lần, nói cần thì liên hệ lại; không nài ép. "
                "BẮT BUỘC có một lượt agent CUỐI CÙNG đáp lại việc từ chối — cuộc không được kết thúc ở lượt khách.")
    else:
        code, say, _ = F.BLOCKERS[p["blocker"]]
        facts.append(fact("blocker", code, say))
        plot = base + f"Nghe agent ĐỌC LẠI ĐƠN xong thì HOÃN: '{say}'; không đồng ý chốt đơn lúc này."
        outcome, mem, fe["blocker"] = "hen_goi_lai", {"blocker": code}, code
        label, notes = "hoan_giua_gate", "Hoãn SAU khi nghe đọc lại đơn (cần hỏi người nhà): hủy đơn nháp, ghi blocker, hẹn gọi lại; không tạo đơn."
        tail = ("Khách hoãn thì KHÔNG tạo đơn, KHÔNG nêu mã đơn, KHÔNG nói đã lên đơn; ghi nhận lý do, hẹn gọi lại khi khách đã trao đổi xong. "
                "BẮT BUỘC có một lượt agent CUỐI CÙNG đáp lại việc hoãn (ghi nhận + hẹn gọi lại/liên hệ lại) — cuộc không được kết thúc ở lượt khách.")
    agent = ("Agent báo {product} giá {price}; theo quy trình đặt đơn: hỏi tên người nhận, địa chỉ, thanh toán; rồi ĐỌC LẠI ĐƠN đúng một lần ({product}, giá {price}, tổng {readback_total}, "
             "giao cho {recipient_name}, SĐT {caller_phone}, địa chỉ {address}, hình thức {payment_label}) và hỏi khách xác nhận. " + tail)
    exp = {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"],
                          "forbidden_claims": ["đã lên đơn", "đã tạo đơn", "mã đơn"]},
           "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(full, F.D0)["in_stock"]},
           "facts_established": fe, "memory_expectation": mem, "expected_outcome": outcome}
    c = call("call_1", ch, f"đặt {T.product_name(sku)} nhưng {'từ chối' if refuse else 'hoãn'} sau khi nghe đọc lại đơn", "agent" if ch == "hotline" else "customer", plot, agent, facts, v, exp,
             n_turns=(9, 12), identity=None if ch == "hotline" else _ident(ch, i), date=F.D0, abs_date=F.D0)
    return F._sc(i, "C", p["persona"], label, notes, [c])


# ============================================================================================ C: tồn kho theo biến thể
def variant_oos(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    name, hon = F.person(i)
    ph, ch, sku = F.phone(i), p["ch"], p["sku"]
    rs, rc = p["variant"]
    rv = F.vsku(sku, rs, rc)
    st = T.stock(rv, F.D0)
    sold_out = p["mode"] == "sold_out"
    assert st["in_stock"] != sold_out, (rv, st)
    fc = p["alt_color"] if sold_out else rc
    final = F.vsku(sku, rs, fc)
    assert T.stock(final, F.D0)["in_stock"], final
    ad = F.addr(i, p.get("south", False))
    q = T.quote(final, F.D0, ph, ad)
    o = T.simulate_order(ph, final, q["final_price_vnd"], None, "COD", ad, F.D0)
    stock_txt = "hiện còn hàng" if st["in_stock"] else "hiện đang hết hàng" + (f", dự kiến có lại ngày {T.dmy(st['restock_expected'])}" if st.get("restock_expected") else "")
    want = f"size {rs} màu {F.COLOR_VI[rc]}"
    v = {"product": F.pv(sku), "price": F.price_var(q), "stock": var(stock_txt, f"tình trạng tồn kho của ĐÚNG biến thể {want} khách hỏi (không phải của cả dòng sản phẩm)"),
         "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var(_delivery(p), "số ngày giao"), "address": _addr_var(ad)}
    facts = _variant_facts(F, sku, (rs, rc))
    if sold_out:
        v["alt"] = var(f"size {rs} màu {F.COLOR_VI[fc]}", "biến thể CÒN HÀNG đề xuất thay thế")
        v["alt_stock"] = var("hiện còn hàng", "tình trạng tồn kho của biến thể thay thế")
        facts.append(fact("color_final", fc, f"đồng ý đổi sang màu {F.COLOR_VI[fc]}"))
        plot = (f"Khách hỏi {T.product_name(sku)} {want} còn hàng không; nghe hết hàng và được gợi ý màu {F.COLOR_VI[fc]} thì đồng ý lấy màu {F.COLOR_VI[fc]}, COD, giao về {ad}. Tính cách: {p['style']}.")
        agent = ("Agent tra ĐÚNG biến thể {product} " + want + " rồi nói {stock}; KHÔNG xin địa chỉ, KHÔNG tạo đơn cho biến thể hết hàng; đề xuất {alt} ({alt_stock}) giá {price}; "
                 "khi khách đồng ý thì theo quy trình đặt đơn rồi chốt biến thể thay thế: mã đơn {order_id}, giao {delivery_days} ngày.")
        goal, notes = f"hỏi {want} đã HẾT → nhận biến thể thay thế", f"Hết hàng đúng biến thể {want}: agent nói đúng tình trạng và gợi ý màu {F.COLOR_VI[fc]} (còn hàng) thay vì xin địa chỉ."
    else:
        plot = (f"Khách hỏi {T.product_name(sku)} bằng cách nói GỌN '{rs} {F.COLOR_VI[rc]}' (không đủ chữ 'size', 'màu') còn hàng không; nghe còn hàng thì chốt lấy, COD, giao về {ad}. Tính cách: {p['style']}.")
        agent = ("Agent hiểu '{size} {color}' là size/màu, tra ĐÚNG biến thể " + want + " và nói {stock} (KHÔNG nói hết hàng, KHÔNG hỏi lại size/màu khách đã nói), báo giá {price}; "
                 "theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.").replace("{size} {color}", f"{rs} {F.COLOR_VI[rc]}")
        goal, notes = f"hỏi gọn '{rs} {F.COLOR_VI[rc]}' (CÒN hàng)", f"Biến thể {want} CÒN hàng nhưng khách nói gọn: agent không được báo hết hàng, không hỏi lại size/màu."
    facts += [fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")]
    exp = {"success_if": {"tool_called": "order.create", "args_match": {"sku": final, "price_vnd": q["final_price_vnd"], "payment": "COD"}},
           "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": True, "requested_variant_in_stock": st["in_stock"]},
           "facts_established": {"product_advised": F.parent(sku), "variant_sku": final, "price_quoted_vnd": q["final_price_vnd"], "payment": "COD", "size": rs, "color": fc},
           "expected_outcome": "chot_don"}
    c = call("call_1", ch, goal, "agent" if ch == "hotline" else "customer", plot, agent, facts, v, exp, n_turns=(7, 9),
             identity=None if ch == "hotline" else _ident(ch, i), date=F.D0, abs_date=F.D0)
    return F._sc(i, "C", p["persona"], "het_hang_bien_the", notes, [c])


# ============================================================================================ C: tự nhận khách cũ khi chưa có SĐT
def claims_returning(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    name, hon = F.person(i)
    ph, ch, sku = F.phone(i), p["ch"], p["sku"]
    ad = F.addr(i, p.get("south", False))
    q = T.quote(sku, F.D0, ph, ad)
    o = T.simulate_order(ph, sku, q["final_price_vnd"], None, "COD", ad, F.D0)
    v = {"product": F.pv(sku), "price": F.price_var(q), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var(_delivery(p), "số ngày giao"),
         "address": _addr_var(ad)}
    facts = [fact("product_asked", F.parent(sku), f"hỏi mua {T.product_name(sku)}"),
             fact("claimed_status", "khách cũ", f"nói mình là khách cũ, đã mua ở shop hồi tháng trước (KHÔNG đọc SĐT ngay từ đầu)"),
             fact("phone_provided", ph, f"chỉ đọc SĐT {ph} khi agent hỏi để tra hồ sơ"), fact("payment", "COD", "COD"), fact("address", ad, f"giao về {ad}")]
    plot = (f"Khách nhắn: '{hon} là khách cũ của shop, mua hồi tháng trước rồi, giờ muốn mua {T.product_name(sku)}' (không kèm SĐT); khi agent hỏi SĐT/tài khoản đã dùng thì mới đọc SĐT {ph}; "
            f"nghe agent nói chưa thấy hồ sơ thì vẫn mua như khách mới, COD, giao về {ad}. Tính cách: {p['style']}.")
    agent = ("Agent KHÔNG giả vờ nhớ khách (không nói 'em nhớ…', 'như lần trước'); lịch sự hỏi SĐT hoặc tên tài khoản đã dùng để tra hồ sơ; tra xong nói rõ em CHƯA thấy hồ sơ mua hàng "
             "với số này nên hỗ trợ như khách mới, không nêu thông tin cũ nào; rồi báo {product} giá {price}; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.")
    exp = {"success_if": {"tool_called": "order.create", "args_match": {"sku": sku, "price_vnd": q["final_price_vnd"], "payment": "COD"}, "forbidden_claims": list(RETURNING_CLAIM_PHRASES)},
           "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock(sku, F.D0)["in_stock"]},
           "facts_established": {"product_advised": F.parent(sku), "price_quoted_vnd": q["final_price_vnd"], "payment": "COD"}, "expected_outcome": "chot_don"}
    c = call("call_1", ch, "tự nhận khách cũ nhưng chưa có SĐT, rồi mua", "customer", plot, agent, facts, v, exp, n_turns=(7, 9), identity=_ident(ch, i), date=F.D0, abs_date=F.D0)
    return F._sc(i, "C", "khach_da_kenh_fb_hotline", "tu_nhan_khach_cu_chua_sdt",
                 "Khách tự nhận khách cũ trên kênh chat khi chưa có SĐT: agent không giả vờ nhớ, hỏi SĐT/tài khoản, không nối hồ sơ theo lời khai.", [c])


# ============================================================================================ C: số nói bằng chữ
def spoken_numbers(i: int, p: Dict[str, Any]) -> Dict[str, Any]:
    F = _F()
    ph, sku, budget = F.phone(i), p["sku"], p["budget"]
    fr = F.inquiry_only(i, {"sku": sku, "ch": "hotline", "style": p["style"]})
    c, sc = fr["calls"][0], fr["scenario"]
    c["customer_facts"] += [fact("budget_vnd", budget, f"nói ngân sách tầm {budget / 1e6:g} triệu"), fact("phone_provided", ph, f"đọc SĐT {ph} để nhân viên gọi lại")]
    c["customer_plot"] += (f" Khi nói số tiền và SĐT, nói rõ ràng. QUAN TRỌNG: trong lời VIẾT, SĐT phải là chữ số liền {ph} và số tiền viết bằng chữ số (vd '4,5 triệu'); "
                           "hệ thống tự đổi thành lời đọc từng chữ số — tuyệt đối đừng tự viết số bằng chữ.")
    c["agent_plot"] += " Nhắc lại SĐT khách vừa đọc ({caller_phone}) để xác nhận sẽ gọi lại đúng số đó."
    c["agent_vars"]["caller_phone"] = var(ph, "SĐT khách vừa đọc — CHỈ dùng sau khi khách đã đọc", ("phone", ph), after="phone_provided")
    c["goal"] = f"hỏi {T.product_name(sku)} bằng giọng nói: ngân sách và SĐT đọc bằng chữ"
    c["style"] = "spoken"
    c["n_turns"] = [7, 9]
    c["expected"]["input_mode"] = "asr_transcript"
    sc["persona"], sc["hard_case"] = "khach_hoi_nhieu_khong_mua", "so_noi_bang_chu"
    sc["notes"] = "Số nói bằng chữ (customer_turns_asr, input_mode asr_transcript): ngân sách và SĐT đọc thành lời → kiểm ITN và Entity Accuracy."
    return fr


BUILDERS = {"cross_conflict": cross_conflict, "bargain": bargain, "gate_decline": gate_decline, "variant_oos": variant_oos,
            "claims_returning": claims_returning, "spoken_numbers": spoken_numbers}
