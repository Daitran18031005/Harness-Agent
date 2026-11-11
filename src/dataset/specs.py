"""
Khung (frame) XÁC ĐỊNH cho 10 kịch bản mẫu của dataset văn bản (docs/DATASET_TEXT_PLAN.md § 6).

Mỗi khung có: thông tin khách, từng cuộc gọi (kênh, ngày, mục tiêu, các fact khách PHẢI nói, diễn biến), các "ô trống" của lời agent
(giá, ngày, mã đơn… — GIÁ TRỊ do `truth.py` tính từ mock_tools) và đáp án theo định dạng BTC (`success_if`, `ground_truth_facts`,
`facts_established`, `must_carry_over`, `must_not_ask`, `memory_expectation`, `expected_outcome`). LLM chỉ viết lời thoại từ khung này.
Số điện thoại: dải GIẢ 0900010xxx (quy ước của dự án, không gắn người thật).
"""
from typing import Any, Dict, List, Optional

from src.dataset import truth as T

ADDR_BAC = "số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội"
ADDR_NAM = "số 45 đường Lê Văn Sỹ, quận 3, TP.HCM"


def var(text: str, desc: str, entity: Optional[tuple] = None, after: Optional[str] = None) -> Dict[str, Any]:
    """Ô trống của lời agent. `after`: key fact khách phải NÓI TRƯỚC thì agent mới được dùng ô này (vd địa chỉ)."""
    out = {"text": text, "desc": desc, "entity": list(entity) if entity else None}
    if after:
        out["after"] = after
    return out


def fact(key: str, value: Any, hint: str) -> Dict[str, Any]:
    return {"key": key, "value": value, "hint": hint}


def _with_stock_var(agent_vars: Dict[str, Any], on: str) -> Dict[str, Any]:
    """Luật P2 (rules.py): khách hỏi "còn hàng không" thì agent phải trả lời bằng đáp án THẬT → thêm ô {stock} nếu cuộc có đúng 1 SKU."""
    if "stock" in agent_vars or not on:
        return agent_vars
    skus = {v["entity"][1] for v in agent_vars.values() if v.get("entity") and v["entity"][0] == "sku"}
    if len(skus) != 1:
        return agent_vars
    try:
        s = T.stock(next(iter(skus)), on)
    except Exception:
        return agent_vars
    text = "hiện còn hàng" if s.get("in_stock") else ("hiện đang hết hàng" + (f", dự kiến có lại ngày {T.dmy(s['restock_expected'])}" if s.get("restock_expected") else ""))
    return {**agent_vars, "stock": var(text, "tình trạng tồn kho của sản phẩm (còn hàng/hết hàng)")}


def call(name: str, channel: str, goal: str, opening: str, customer_plot: str, agent_plot: str, facts: List[Dict[str, Any]],
         agent_vars: Dict[str, Any], expected: Dict[str, Any], n_turns=(7, 10), identity: Optional[str] = None,
         date: Optional[str] = None, days_later: Optional[int] = None, style: str = "normal", abs_date: str = "") -> Dict[str, Any]:
    agent_vars = _with_stock_var(agent_vars, abs_date)
    c: Dict[str, Any] = {"name": name, "channel": channel, "goal": goal, "opening": opening, "customer_plot": customer_plot,
                         "agent_plot": agent_plot, "customer_facts": facts, "agent_vars": agent_vars, "n_turns": list(n_turns),
                         "style": style, "expected": expected, "abs_date": abs_date}
    if identity:
        c["channel_identity"] = identity
    if date:
        c["call_date"] = date
    if days_later is not None:
        c["days_later"] = days_later
    return c


def _meta(sid, group, persona, hard_case, phone, name, honorific, notes):
    return {"scenario_id": sid, "level": "M1", "persona": persona, "hard_case": hard_case, "customer_phone": phone,
            "customer_name": name, "honorific": honorific, "notes": notes, "group": group}


# ======================================================================================================== A01
def a01() -> Dict[str, Any]:
    phone, d1, d2 = "0900010001", "2026-10-15", "2026-10-17"
    q1, q2 = T.quote("SKU-AP-Y", d1), T.quote("SKU-AP-Y", d2)
    o = T.simulate_order(phone, "SKU-AP-Y", q2["final_price_vnd"], "GIFT-FILTER", "COD", ADDR_BAC, d2)
    price, budget = q1["final_price_vnd"], 5_000_000
    over = round((price - budget) / budget * 100)
    gift = T.product_name("SKU-AP-FLT-X")
    end = T.promo("GIFT-FILTER")["end"]
    v1 = {"product": var(T.product_name("SKU-AP-Y"), "tên sản phẩm đề xuất", ("sku", "SKU-AP-Y")),
          "price": var(T.money(price), "giá cuối (đã tính khuyến mãi)", ("price_vnd", price)),
          "overage": var(f"{over}%", "mức giá vượt ngân sách khách nêu"),
          "gift": var(gift, "quà tặng kèm"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi", ("promo_expiry", end))}
    v2 = {"product": var(T.product_name("SKU-AP-Y"), "tên sản phẩm khách đã hỏi bên Fanpage", ("sku", "SKU-AP-Y")),
          "price": var(T.money(q2["final_price_vnd"]), "giá cuối hôm nay", ("price_vnd", q2["final_price_vnd"])),
          "gift": var(gift, "quà tặng kèm"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi", ("promo_expiry", end)),
          "order_id": var(o["order_id"], "mã đơn vừa tạo", ("order_id", o["order_id"])),
          "delivery_days": var("2", "số ngày giao hàng dự kiến"), "address": var(ADDR_BAC, "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c1 = call("call_1", "chat_fanpage", "hỏi máy lọc không khí cho phòng ngủ có bé nhỏ", "customer",
              "Khách nhắn Fanpage hỏi máy lọc không khí cho phòng ngủ. Khi được hỏi mới nói: phòng khoảng 25 mét vuông, nhà có bé 2 tuổi, ngân sách tầm 5 triệu. "
              "Nghe giá hơi vượt ngân sách; nói 'để chị hỏi chồng đã' và đọc SĐT để hotline gọi lại.",
              "Agent hỏi diện tích phòng và nhà có bé nhỏ không, đề xuất MỘT sản phẩm {product} giá {price} (nêu rõ vượt ngân sách {overage} và lý do chọn: "
              "có khóa an toàn trẻ em), nhắc quà {gift} đến hết {promo_end}; ghi nhận khách hỏi chồng và xin SĐT để gọi lại.",
              [fact("room_area_m2", 25, "phòng khoảng 25m²"), fact("has_children", True, "nhà có bé 2 tuổi"),
               fact("budget_vnd", 5_000_000, "ngân sách tầm 5 triệu"), fact("blocker", "can hoi chong", "để chị hỏi chồng"),
               fact("phone_provided", phone, "đọc SĐT 0900010001 để hotline gọi lại")], v1,
              {"facts_established": {"product_advised": "SKU-AP-Y", "room_area_m2": 25, "has_children": True, "budget_vnd": 5_000_000,
                                     "price_quoted_vnd": price, "promo_code": "GIFT-FILTER", "promo_expiry": end, "blocker": "can hoi chong",
                                     "channel": "fanpage", "phone_provided": phone},
               "expected_outcome": "hen_goi_lai"}, n_turns=(7, 10), identity="fb.thu.a01", date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "gọi hotline chốt đơn sau khi hỏi chồng", "agent",
              "Khách gọi hotline: 'chị vừa nhắn Facebook hỏi máy lọc không khí'; chồng đã đồng ý; hỏi giá còn như cũ không; chốt lấy, giao về địa chỉ "
              f"{ADDR_BAC}, thanh toán COD (khách không phải nhắc lại diện tích/bé/ngân sách).",
              "Agent nhận ra khách từ cuộc Fanpage, xác nhận {product} giá {price} còn quà {gift} đến {promo_end}, KHÔNG hỏi lại diện tích phòng/bé nhỏ/ngân sách/sản phẩm; "
              "xác nhận địa chỉ {address}; chốt đơn: nêu mã đơn {order_id}, giao trong {delivery_days} ngày.",
              [fact("blocker_resolved", True, "chồng chị đồng ý rồi"), fact("payment", "COD", "thanh toán khi nhận hàng (COD)"),
               fact("address", ADDR_BAC, f"giao về {ADDR_BAC}")], v2,
              {"must_carry_over": ["product_advised", "price_quoted_vnd", "room_area_m2", "has_children", "blocker"],
               "must_not_ask": ["product_advised", "room_area_m2", "has_children", "budget_vnd"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-Y", "price_vnd": q2["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "promo_active": True, "in_stock": T.stock("SKU-AP-Y", d2)["in_stock"], "delivery_days": 2},
               "memory_expectation": {"room_area_m2": 25, "product_advised": "SKU-AP-Y"},
               "expected_outcome": "chot_don"}, n_turns=(8, 11), days_later=2, abs_date=d2)
    return {"scenario": _meta("SC-A01", "A", "khach_do_du_hoi_nguoi_nha", None, phone, "Thu", "chị",
                              "Đa kênh Fanpage→Hotline: nối danh tính qua SĐT; blocker 'hỏi chồng'; sản phẩm duy nhất có khóa trẻ em vượt ngân sách ~4% (luật ngân sách ≤ 20%: vẫn chốt và nêu mức vượt)."),
            "calls": [c1, c2]}


# ======================================================================================================== A02
def a02() -> Dict[str, Any]:
    ADDR_BAC = "số 8 phố Hoàng Hoa Thám, quận Ba Đình, Hà Nội"
    phone, d1, d2 = "0900010002", "2026-10-15", "2026-10-18"
    q1, q2 = T.quote("SKU-SN-RUN2-40-DEN", d1), T.quote("SKU-SN-RUN2-42-XAM", d2)
    o = T.simulate_order(phone, "SKU-SN-RUN2-42-XAM", q2["final_price_vnd"], "RUN-10", "COD", ADDR_BAC, d2)
    name = T.product_name("SKU-SN-RUN2")
    v1 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SN-RUN2")), "price": var(T.money(q1["final_price_vnd"]), "giá cuối sau KM (size 40 màu đen)", ("price_vnd", q1["final_price_vnd"])),
          "discount": var("10%", "mức giảm khuyến mãi"), "promo_end": var(T.dmy(T.promo("RUN-10")["end"]), "ngày hết khuyến mãi", ("promo_expiry", T.promo("RUN-10")["end"])),
          "return_days": var(str(T.attr("SKU-SN-RUN2", "return_days")), "số ngày đổi trả")}
    v2 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SN-RUN2")), "price": var(T.money(q2["final_price_vnd"]), "giá cuối size 42 màu xám", ("price_vnd", q2["final_price_vnd"])),
          "old_size": var("40", "size khách nói ở cuộc trước (đã lưu)"), "new_size": var("42", "size khách vừa đổi"),
          "old_color": var("đen", "màu cũ đã lưu"), "new_color": var("xám", "màu mới khách chọn"),
          "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2", "số ngày giao")}
    c1 = call("call_1", "hotline", "hỏi giày chạy bộ RunLite 2 Pro, chưa quyết", "agent",
              "Khách hay hỏi chi tiết: hỏi RunLite 2 Pro size 40 màu đen giá bao nhiêu, có giảm không, đổi trả thế nào; cuối cùng 'để anh xem thêm' (chưa mua).",
              "Agent báo giá {price} (đã giảm {discount} đến {promo_end}) cho size 40 màu đen, chính sách đổi trả {return_days} ngày; không ép mua.",
              [fact("product_asked", "SKU-SN-RUN2", "hỏi giày RunLite 2 Pro"), fact("size", 40, "size 40"), fact("color", "den", "màu đen")], v1,
              {"facts_established": {"product_advised": "SKU-SN-RUN2", "size": 40, "color": "den", "price_quoted_vnd": q1["final_price_vnd"], "promo_code": "RUN-10"},
               "expected_outcome": "hen_goi_lai"}, n_turns=(7, 9), date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "gọi lại, ĐỔI size/màu khác lần trước rồi chốt", "agent",
              "Khách gọi lại: 'hôm trước anh nói size 40 màu đen nhưng anh nhầm, anh đi size 42 và muốn màu xám'; chốt lấy, COD, giao về "
              f"{ADDR_BAC}.",
              "Agent KHÔNG hỏi lại sản phẩm/giá; ghi nhận đúng thay đổi (size {old_size}→{new_size}, màu {old_color}→{new_color}) và báo giá {price} cho biến thể mới; "
              "chốt đơn, nêu mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("size", 42, "anh đi size 42"), fact("color", "xam", "muốn màu xám"), fact("payment", "COD", "COD"), fact("address", ADDR_BAC, f"giao về {ADDR_BAC}")], v2,
              {"must_carry_over": ["product_advised", "promo_code"], "must_not_ask": ["product_advised"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-SN-RUN2-42-XAM", "price_vnd": q2["final_price_vnd"]}},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "promo_active": True, "in_stock": T.stock("SKU-SN-RUN2-42-XAM", d2)["in_stock"]},
               "memory_expectation": {"size": 42, "color": "xam", "superseded": {"size": 40, "color": "den"}},
               "expected_outcome": "chot_don"}, n_turns=(7, 10), days_later=3, abs_date=d2)
    return {"scenario": _meta("SC-A02", "A", "khach_hoi_nhieu_khong_mua", "mau_thuan_phien_truoc", phone, "Long", "anh",
                              "Mâu thuẫn với phiên trước: size/màu khách nói ở cuộc 2 khác cuộc 1 → bộ nhớ phải ghi giá trị MỚI và đánh dấu giá trị cũ bị thay thế."),
            "calls": [c1, c2]}


# ======================================================================================================== A03
def a03() -> Dict[str, Any]:
    ADDR_BAC = "số 27 đường Trần Phú, quận Hà Đông, Hà Nội"
    phone, d1, d2 = "0900010003", "2026-10-10", "2026-10-15"
    q1, q2 = T.quote("SKU-MB-PUMP1", d1), T.quote("SKU-MB-PUMP1", d2)
    o = T.simulate_order(phone, "SKU-MB-PUMP1", q2["final_price_vnd"], None, "COD", ADDR_BAC, d2)
    end = T.promo("PUMP-GIFT")["end"]
    gift = T.product_name("SKU-MB-BAG")
    name = T.product_name("SKU-MB-PUMP1")
    v1 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-MB-PUMP1")), "price": var(T.money(q1["final_price_vnd"]), "giá cuối", ("price_vnd", q1["final_price_vnd"])),
          "gift": var(gift, "quà tặng kèm"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi quà tặng", ("promo_expiry", end))}
    v2 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-MB-PUMP1")), "price": var(T.money(q2["final_price_vnd"]), "giá hôm nay (không còn quà)", ("price_vnd", q2["final_price_vnd"])),
          "gift": var(gift, "quà tặng trước đây"), "promo_end": var(T.dmy(end), "ngày khuyến mãi quà tặng đã kết thúc", ("promo_expiry", end)),
          "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2", "số ngày giao")}
    c1 = call("call_1", "zalo_oa", "hỏi máy hút sữa Spectra S1 và quà tặng", "customer",
              "Khách nhắn Zalo hỏi máy hút sữa Spectra S1 giá bao nhiêu, nghe nói có tặng túi trữ sữa; nói 'để chị suy nghĩ rồi gọi hotline' và đọc SĐT.",
              "Agent báo {product} giá {price}, có tặng {gift} đến hết {promo_end}; xin SĐT để hotline gọi lại.",
              [fact("product_asked", "SKU-MB-PUMP1", "máy hút sữa Spectra S1"), fact("phone_provided", phone, "đọc SĐT 0900010003")], v1,
              {"facts_established": {"product_advised": "SKU-MB-PUMP1", "price_quoted_vnd": q1["final_price_vnd"], "promo_code": "PUMP-GIFT", "promo_expiry": end,
                                     "channel": "zalo", "phone_provided": phone},
               "expected_outcome": "hen_goi_lai"}, n_turns=(6, 8), identity="zalo_mai_a03", date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "gọi lại hỏi quà đã hết hạn rồi vẫn mua", "agent",
              "Khách gọi: 'chị gọi lấy cái máy hút sữa Spectra hôm trước, có tặng túi trữ sữa đúng không?'; nghe tin quà đã hết thì hơi tiếc nhưng vẫn lấy, COD, "
              f"giao về {ADDR_BAC}.",
              "Agent nói rõ khuyến mãi tặng {gift} đã kết thúc ngày {promo_end} nên KHÔNG còn quà; giá hôm nay {price}; không hứa tặng bù; chốt đơn, mã đơn {order_id}, giao {delivery_days} ngày.",
              [fact("payment", "COD", "COD"), fact("address", ADDR_BAC, f"giao về {ADDR_BAC}")], v2,
              {"must_carry_over": ["product_advised"], "must_not_ask": ["product_advised"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-MB-PUMP1", "price_vnd": q2["final_price_vnd"]},
                              "forbidden_claims": [{"field": "promo_PUMP-GIFT_active", "value": True}]},
               "ground_truth_facts": {"price_vnd": q2["final_price_vnd"], "promo_PUMP-GIFT_active": False, "freeship": True, "in_stock": T.stock("SKU-MB-PUMP1", d2)["in_stock"]},
               "expected_outcome": "chot_don"}, n_turns=(7, 10), days_later=5, abs_date=d2)
    return {"scenario": _meta("SC-A03", "A", "khach_so_gia", "khuyen_mai_het_han", phone, "Mai", "chị",
                              "Khuyến mãi quà tặng PUMP-GIFT (hết 13/10): cuộc 1 còn hạn (10/10), cuộc 2 (15/10) đã hết → agent không được hứa quà."),
            "calls": [c1, c2]}


# ======================================================================================================== B01
def b01() -> Dict[str, Any]:
    phone, d1, d2, d3 = "0900010004", "2026-10-15", "2026-10-16", "2026-10-18"
    q = T.quote("SKU-SN-RUN2-41-DEN", d1)
    sim = T.simulate_exchange(phone, "SKU-SN-RUN2-41-DEN", q["final_price_vnd"], "RUN-10", ADDR_NAM, d2, "SKU-SN-RUN2-43-DEN", d3)
    oid, upd = sim["order"]["order_id"], sim["update"]
    name = T.product_name("SKU-SN-RUN2")
    end = T.promo("RUN-10")["end"]
    v1 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SN-RUN2")), "price": var(T.money(q["final_price_vnd"]), "giá cuối size 41 màu đen", ("price_vnd", q["final_price_vnd"])),
          "discount": var("10%", "mức giảm"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi", ("promo_expiry", end))}
    v2 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SN-RUN2")), "price": var(T.money(q["final_price_vnd"]), "giá cuối", ("price_vnd", q["final_price_vnd"])),
          "order_id": var(oid, "mã đơn", ("order_id", oid)), "delivery_days": var("2", "số ngày giao"), "address": var(ADDR_NAM, "địa chỉ giao — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    v3 = {"order_id": var(oid, "mã đơn khách đã đặt", ("order_id", oid)), "product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SN-RUN2")),
          "old_size": var("41", "size hiện tại của đơn"), "new_size": var("43", "size khách muốn đổi"),
          "extra_payment": var(T.money(upd["extra_payment_vnd"]), "số tiền khách phải trả thêm khi đổi sang size 43", ("extra_payment_vnd", upd["extra_payment_vnd"])),
          "exchange_fee": var(T.money(upd["fee_vnd"]) if upd["fee_vnd"] else "không", "phí đổi size (0 đồng, miễn phí lần đầu)"),
          "return_days": var(str(T.attr("SKU-SN-RUN2", "return_days")), "số ngày đổi trả")}
    c1 = call("call_1", "chat_fanpage", "hỏi giá giày RunLite 2 Pro qua Fanpage", "customer",
              "Khách nhắn Fanpage hỏi RunLite 2 Pro size 41 màu đen giá bao nhiêu, có giảm không; đọc SĐT 0900010004 để Zalo/hotline liên hệ; nói 'tối anh nhắn chốt'.",
              "Agent báo giá {price} (đã giảm {discount} đến {promo_end}) cho size 41 màu đen; xin SĐT.",
              [fact("size", 41, "size 41"), fact("color", "den", "màu đen"), fact("phone_provided", phone, "đọc SĐT 0900010004")], v1,
              {"facts_established": {"product_advised": "SKU-SN-RUN2", "size": 41, "color": "den", "price_quoted_vnd": q["final_price_vnd"], "promo_code": "RUN-10",
                                     "channel": "fanpage", "phone_provided": phone}, "expected_outcome": "hen_goi_lai"},
              n_turns=(5, 7), identity="fb.quan.b01", date=d1, abs_date=d1)
    c2 = call("call_2", "zalo_oa", "chốt đơn qua Zalo", "customer",
              f"Khách nhắn Zalo: 'anh hỏi giày RunLite hôm qua bên Facebook'; chốt lấy size 41 màu đen, COD, giao về {ADDR_NAM}.",
              "Agent nhận ra khách từ Fanpage, KHÔNG hỏi lại sản phẩm/size/màu; xác nhận giá {price}; chốt đơn mã {order_id}, giao {delivery_days} ngày về {address}.",
              [fact("payment", "COD", "COD"), fact("address", ADDR_NAM, f"giao về {ADDR_NAM}")], v2,
              {"must_carry_over": ["product_advised", "size", "color", "price_quoted_vnd"], "must_not_ask": ["product_advised", "size", "color"],
               "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-SN-RUN2-41-DEN", "price_vnd": q["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "promo_active": True, "in_stock": T.stock("SKU-SN-RUN2-41-DEN", d2)["in_stock"]},
               "facts_established": {"order_id": oid, "variant_sku": "SKU-SN-RUN2-41-DEN", "payment": "COD"},    # size/màu đã biết từ cuộc 1 (khách KHÔNG nói lại)
               "expected_outcome": "chot_don"}, n_turns=(6, 8), identity="zalo_quan_b01", days_later=1, abs_date=d2)
    c3 = call("call_3", "hotline", "gọi hotline đổi sang size 43 (có phụ thu)", "agent",
              "Khách gọi: 'anh mới nhận giày, size 41 hơi chật, đổi lên size 43 được không, mất phí gì không?'; nghe phụ thu thì đồng ý, nhờ làm thủ tục đổi.",
              "Agent biết ngay đơn {order_id} ({product}, size {old_size}); báo chính sách đổi trả {return_days} ngày, phí đổi {exchange_fee}, nhưng size {new_size} có phụ thu: "
              "khách trả thêm {extra_payment}; sau khi khách đồng ý thì làm thủ tục đổi. KHÔNG hỏi lại mã đơn/sản phẩm/màu.",
              [fact("size_new", 43, "đổi lên size 43")], v3,
              {"must_carry_over": ["order_id", "variant_sku", "size", "color"], "must_not_ask": ["product_advised", "order_id", "color", "payment"],
               "success_if": {"tool_called": "order.update", "args_match": {"order_id": oid, "new_variant_sku": "SKU-SN-RUN2-43-DEN", "action": "exchange_size"}},
               "ground_truth_facts": {"return_days": 7, "exchange_fee_vnd": upd["fee_vnd"], "extra_payment_vnd": upd["extra_payment_vnd"], "new_size_in_stock": True},
               "expected_outcome": "chot_don"}, n_turns=(7, 10), days_later=2, abs_date=d3)
    return {"scenario": _meta("SC-B01", "B", "khach_da_mua_doi_size", None, phone, "Quân", "anh",
                              "3 cuộc, 3 kênh (Fanpage→Zalo→Hotline): hỏi giá → chốt đơn → đổi size 43 có phụ thu biến thể (đáp án tính từ order.update thật của mock)."),
            "calls": [c1, c2, c3]}


# ======================================================================================================== B02
def b02() -> Dict[str, Any]:
    ADDR_BAC = "số 33 phố Kim Mã, quận Đống Đa, Hà Nội"
    phone, d1, d2, d3 = "0900010005", "2026-10-12", "2026-10-14", "2026-10-17"
    q = T.quote("SKU-MB-PUMP1", d1)
    o = T.simulate_order(phone, "SKU-MB-PUMP1", q["final_price_vnd"], "PUMP-GIFT", "COD", ADDR_BAC, d1)
    est = o["estimated_delivery"]
    name = T.product_name("SKU-MB-PUMP1")
    gift = T.product_name("SKU-MB-BAG")
    v1 = {"product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-MB-PUMP1")), "price": var(T.money(q["final_price_vnd"]), "giá cuối", ("price_vnd", q["final_price_vnd"])),
          "gift": var(gift, "quà tặng"), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])),
          "delivery_date": var(T.dmy(est), "ngày giao dự kiến", ("delivery_date", est)), "address": var(ADDR_BAC, "địa chỉ giao — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    v2 = {"order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "product": var(name, "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-MB-PUMP1")),
          "order_status": var("đã tạo, đang chờ giao", "trạng thái đơn theo hệ thống (order.status)"), "delivery_date": var(T.dmy(est), "ngày giao dự kiến", ("delivery_date", est))}
    v3 = {"order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_date": var(T.dmy(est), "ngày giao dự kiến ban đầu", ("delivery_date", est))}
    c1 = call("call_1", "hotline", "mua máy hút sữa Spectra S1", "agent",
              f"Khách gọi mua máy hút sữa Spectra S1, hỏi giá và quà; chốt luôn, COD, giao về {ADDR_BAC}.",
              "Agent báo {product} giá {price}, tặng {gift}; chốt đơn: mã đơn {order_id}, dự kiến giao {delivery_date} tại {address}.",
              [fact("payment", "COD", "COD"), fact("address", ADDR_BAC, f"giao về {ADDR_BAC}")], v1,
              {"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-MB-PUMP1", "price_vnd": q["final_price_vnd"], "payment": "COD"}},
               "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "promo_active": True, "in_stock": T.stock("SKU-MB-PUMP1", d1)["in_stock"]},
               "facts_established": {"product_advised": "SKU-MB-PUMP1", "price_quoted_vnd": q["final_price_vnd"], "order_id": o["order_id"], "payment": "COD", "promo_code": "PUMP-GIFT"},
               "expected_outcome": "chot_don"}, n_turns=(6, 9), date=d1, abs_date=d1)
    c2 = call("call_2", "hotline", "hỏi đơn đến đâu rồi", "agent",
              "Khách gọi hỏi 'đơn máy hút sữa hôm trước của chị đến đâu rồi?' (không đọc mã đơn); nghe trả lời thì nói 'ừ, chị chờ thêm'.",
              "Agent tra đơn bằng thông tin đã lưu (KHÔNG hỏi mã đơn/sản phẩm), báo đơn {order_id} {order_status}, dự kiến giao {delivery_date}.",
              [fact("order_query", True, "hỏi đơn hôm trước đến đâu rồi")], v2,
              {"must_carry_over": ["order_id", "product_advised"], "must_not_ask": ["order_id", "product_advised", "payment"],
               "success_if": {"tool_called": "order.status"}, "ground_truth_facts": {"order_status": "created"},
               "expected_outcome": "hen_goi_lai"}, n_turns=(5, 7), days_later=2, abs_date=d2)
    c3 = call("call_3", "hotline", "khiếu nại giao trễ → chuyển nhân viên", "agent",
              "Khách bực, cộc lốc: đơn dự kiến giao hôm 14/10 mà giờ vẫn chưa nhận; đòi gặp người có thẩm quyền xử lý.",
              "Agent xin lỗi ngắn gọn, KHÔNG hỏi lại mã đơn, nói đơn {order_id} dự kiến giao {delivery_date} đã quá hạn; không hứa thời hạn; chuyển máy cho nhân viên kèm tóm tắt (handoff).",
              [fact("complaint_late_delivery", True, "đơn dự kiến giao 14/10 mà vẫn chưa nhận")], v3,
              {"must_carry_over": ["order_id"], "must_not_ask": ["order_id", "product_advised"],
               "success_if": {"tool_called": "handoff.transfer", "brief_must_contain": [o["order_id"]]},
               "expected_outcome": "chuyen_may"}, n_turns=(5, 7), days_later=3, abs_date=d3)
    return {"scenario": _meta("SC-B02", "B", "khach_goi_lan_3_het_kien_nhan", None, phone, "Hương", "chị",
                              "3 cuộc hotline mẹ & bé: mua → hỏi đơn → khiếu nại giao trễ (patience cạn) → chuyển máy với Handoff Brief chứa mã đơn."),
            "calls": [c1, c2, c3]}


# ======================================================================================================== C01
def c01() -> Dict[str, Any]:
    ADDR_BAC = "số 71 phố Lê Thanh Nghị, quận Hai Bà Trưng, Hà Nội"
    phone, d = "0900010006", "2026-10-15"
    qp, qx = T.quote("SKU-AP-PRO", d), T.quote("SKU-AP-X", d)
    o = T.simulate_order(phone, "SKU-AP-X", qx["final_price_vnd"], "GIFT-FILTER", "COD", ADDR_BAC, d)
    gift, end = T.product_name("SKU-AP-FLT-X"), T.promo("GIFT-FILTER")["end"]
    v = {"product_pro": var(T.product_name("SKU-AP-PRO"), "sản phẩm khách hỏi ban đầu", ("sku", "SKU-AP-PRO")),
         "price_pro": var(T.money(qp["final_price_vnd"]), "giá cuối sản phẩm đầu tiên (đã giảm AIR-OCT)", ("price_vnd", qp["final_price_vnd"])),
         "product": var(T.product_name("SKU-AP-X"), "sản phẩm rẻ hơn agent gợi ý và khách chọn", ("sku", "SKU-AP-X")),
         "price": var(T.money(qx["final_price_vnd"]), "giá cuối sản phẩm khách chọn", ("price_vnd", qx["final_price_vnd"])),
         "gift": var(gift, "quà tặng"), "promo_end": var(T.dmy(end), "ngày hết khuyến mãi quà", ("promo_expiry", end)),
         "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])), "delivery_days": var("2", "số ngày giao"),
         "address": var(ADDR_BAC, "địa chỉ giao — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c = call("call_1", "hotline", "hỏi máy cao cấp rồi ĐỔI Ý sang máy rẻ hơn", "agent",
             "Khách hỏi máy lọc không khí AirPure Pro cho phòng 25 mét vuông; nghe giá thì thấy đắt và ĐỔI Ý: 'thôi cho anh cái rẻ hơn, tầm 5 triệu'; "
             f"chọn mẫu agent gợi ý, COD, giao về {ADDR_BAC}.",
             "Agent báo {product_pro} giá {price_pro}; khi khách đổi ý thì gợi ý MỘT mẫu rẻ hơn đủ cho 25 mét vuông là {product} giá {price} (tặng {gift} đến {promo_end}); "
             "chốt đơn {product}, mã đơn {order_id}, giao {delivery_days} ngày. KHÔNG đặt đơn Pro.",
             [fact("product_asked", "SKU-AP-PRO", "hỏi máy AirPure Pro"), fact("room_area_m2", 25, "phòng 25 mét vuông"),
              fact("budget_vnd", 5_000_000, "tầm 5 triệu"), fact("payment", "COD", "COD"), fact("address", ADDR_BAC, f"giao về {ADDR_BAC}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-X", "price_vnd": qx["final_price_vnd"]}},
              "ground_truth_facts": {"price_vnd": qx["final_price_vnd"], "promo_active": True, "in_stock": T.stock("SKU-AP-X", d)["in_stock"]},
              "facts_established": {"product_advised": "SKU-AP-X", "room_area_m2": 25, "budget_vnd": 5_000_000, "price_quoted_vnd": qx["final_price_vnd"]},
              "expected_outcome": "chot_don"}, n_turns=(9, 12), date=d, abs_date=d)
    return {"scenario": _meta("SC-C01", "C", "khach_so_gia", "doi_y_giua_cuoc", phone, "Dũng", "anh",
                              "Đổi ý giữa cuộc: hỏi AirPure Pro (giá sau AIR-OCT) → chuyển sang mẫu rẻ hơn; đơn phải đúng sản phẩm CUỐI CÙNG."),
            "calls": [c]}


# ======================================================================================================== C02
def c02() -> Dict[str, Any]:
    phone, d = "0900010007", "2026-10-15"
    q = T.quote("SKU-MB-PUMP1", d)
    v = {"product": var(T.product_name("SKU-MB-PUMP1"), "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-MB-PUMP1")), "price": var(T.money(q["final_price_vnd"]), "giá cuối", ("price_vnd", q["final_price_vnd"])),
         "warranty": var(str(T.attr("SKU-MB-PUMP1", "warranty_months")), "số tháng bảo hành", ("warranty_months", T.attr("SKU-MB-PUMP1", "warranty_months")))}
    c = call("call_1", "hotline", "hỏi công dụng y tế của máy hút sữa (ngoài tài liệu)", "agent",
             "Khách lo lắng: đang bị tắc tia sữa, hỏi 'dùng máy hút sữa Spectra S1 có chữa được tắc tia sữa/viêm vú không, bác sĩ chưa khám'; tỏ ra muốn nghe lời khẳng định; "
             "cuối cùng đồng ý để nhân viên gọi lại.",
             "Agent KHÔNG tư vấn y tế/không khẳng định chữa bệnh; nói rõ em chỉ có thông tin sản phẩm, không có thông tin y tế, khuyên khách hỏi bác sĩ; chỉ nêu thông tin có thật: "
             "{product} giá {price}, bảo hành {warranty} tháng; mời để nhân viên gọi lại.",
             [fact("product_asked", "SKU-MB-PUMP1", "hỏi máy hút sữa Spectra S1"), fact("medical_question", True, "hỏi có chữa được tắc tia sữa/viêm vú không")], v,
             {"success_if": {"tool_called": None, "agent_must_say": True, "must_not_call_tools": ["order.create"],
                             "forbidden_claims": ["chữa khỏi", "điều trị khỏi", "hết tắc", "sẽ khỏi", "giúp khỏi"]},
              "ground_truth_facts": {"warranty_months": 12, "price_vnd": q["final_price_vnd"]},
              "expected_outcome": "hen_goi_lai"}, n_turns=(6, 9), date=d, abs_date=d)
    return {"scenario": _meta("SC-C02", "C", "khach_ngoai_pham_vi_chuyen_may", "hoi_ngoai_tai_lieu_y_te", phone, "Lan", "chị",
                              "Hỏi ngoài tài liệu (y tế): agent không được tư vấn/khẳng định chữa bệnh, chỉ nêu thông tin sản phẩm có thật và gợi ý hỏi bác sĩ."),
            "calls": [c]}


# ======================================================================================================== C03
def c03() -> Dict[str, Any]:
    phone, d = "0900010008", "2026-10-15"
    q = T.quote("SKU-SS-AX40", d)
    v = {"product": var(T.product_name("SKU-SS-AX40"), "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-SS-AX40")), "price": var(T.money(q["final_price_vnd"]), "giá cuối", ("price_vnd", q["final_price_vnd"])),
         "warranty": var(str(T.attr("SKU-SS-AX40", "warranty_months")), "số tháng bảo hành", ("warranty_months", T.attr("SKU-SS-AX40", "warranty_months")))}
    c = call("call_1", "hotline", "so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)", "agent",
             "Khách hỏi máy lọc không khí Samsung AX40 giá bao nhiêu; nói 'bên Điện Máy Xanh bán 6 triệu thôi, bên em có bằng giá không?'; hỏi thêm 'có bảo hành quốc tế không?'; "
             "cuối cùng 'để anh cân nhắc rồi gọi lại'.",
             "Agent báo {product} giá {price}, bảo hành {warranty} tháng chính hãng; KHÔNG chê đối thủ, KHÔNG hứa khớp giá/giảm không có chương trình; về bảo hành quốc tế nói thẳng "
             "là em chưa có thông tin trong tài liệu và sẽ nhờ nhân viên phản hồi.",
             [fact("product_asked", "SKU-SS-AX40", "hỏi Samsung AX40"), fact("competitor_price_vnd", 6_000_000, "bên Điện Máy Xanh bán rẻ hơn, chỉ 6 triệu"),
              fact("blocker", "so sanh gia", "để anh cân nhắc rồi gọi lại")], v,
             {"success_if": {"tool_called": None, "agent_must_say": True, "forbidden_claims": [{"field": "price_vnd", "value": 6_000_000}, "bảo hành quốc tế có"]},
              "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "warranty_months": 24},
              "facts_established": {"product_advised": "SKU-SS-AX40", "price_quoted_vnd": q["final_price_vnd"], "competitor_price_vnd": 6_000_000,
                                    "blocker": "so sanh gia"},
              "expected_outcome": "hen_goi_lai"}, n_turns=(7, 10), date=d, abs_date=d)
    return {"scenario": _meta("SC-C03", "C", "khach_hoi_ngoai_tai_lieu", "hoi_ngoai_tai_lieu_doi_thu", phone, "Phát", "anh",
                              "Hỏi ngoài tài liệu (so sánh đối thủ + bảo hành quốc tế không có trong chính sách): không hứa khớp giá, không bịa chính sách."),
            "calls": [c]}


# ======================================================================================================== C04
def c04() -> Dict[str, Any]:
    ADDR_NAM = "số 102 đường Cách Mạng Tháng Tám, quận 10, TP.HCM"
    phone, d = "0900010009", "2026-10-15"
    # BTC 11/2026: 2 máy lọc không khí chỉ còn 1,5 lần giá (AIR-2ND-50 tính trong order.create) nên không còn vượt hạn mức COD; khung dùng sản phẩm không có KM máy thứ 2
    fresh = T.simulate_order(phone, "SKU-WF-RO10", None, None, "COD", ADDR_NAM, d, qty=2)
    total = fresh.get("total_vnd")
    bank = T.simulate_order(phone, "SKU-WF-RO10", None, None, "bank", ADDR_NAM, d, qty=2)
    q = T.quote("SKU-WF-RO10", d)
    v = {"product": var(T.product_name("SKU-WF-RO10"), "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-WF-RO10")), "unit_price": var(T.money(q["final_price_vnd"]), "giá một máy", ("price_vnd", q["final_price_vnd"])),
         "total": var(T.money(total), "tổng tiền hai máy", ("total_vnd", total)), "cod_limit": var(T.money(fresh["limit_vnd"]), "hạn mức thanh toán COD tối đa một đơn", ("cod_limit_vnd", fresh["limit_vnd"])),
         "order_id": var(bank["order_id"], "mã đơn sau khi khách chuyển sang chuyển khoản", ("order_id", bank["order_id"])), "address": var(ADDR_NAM, "địa chỉ giao — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c = call("call_1", "hotline", "mua 2 máy, COD vượt hạn mức → đổi sang chuyển khoản", "agent",
             f"Khách muốn mua 2 máy lọc nước RO Kangaroo 10 lõi (cho hai nhà), thanh toán COD, giao về {ADDR_NAM}; nghe COD vượt hạn mức thì đồng ý chuyển khoản.",
             "Agent báo {product} giá {unit_price}/máy, tổng {total}; thử đặt COD thì hệ thống báo vượt hạn mức COD {cod_limit} một đơn; giải thích rõ và đề nghị chuyển khoản; "
             "khách đồng ý → đặt đơn thanh toán chuyển khoản, mã đơn {order_id}, giao về {address}.",
             [fact("quantity", 2, "mua 2 máy"), fact("payment", "COD", "ban đầu muốn COD"), fact("address", ADDR_NAM, f"giao về {ADDR_NAM}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-WF-RO10", "qty": 2, "payment": "bank"}},
              "ground_truth_facts": {"cod_limit_vnd": fresh["limit_vnd"], "total_vnd": total},
              "facts_established": {"product_advised": "SKU-WF-RO10", "price_quoted_vnd": q["final_price_vnd"]},
              "expected_outcome": "chot_don"}, n_turns=(8, 11), date=d, abs_date=d)
    return {"scenario": _meta("SC-C04", "C", "khach_mua_nhieu_mon", "cod_vuot_han_muc", phone, "Hạnh", "chị",
                              "COD vượt hạn mức 10 triệu (tool báo lỗi thật): agent phải nêu đúng hạn mức và chuyển sang chuyển khoản, không tự nói 'đã tạo đơn COD'."),
            "calls": [c]}


# ======================================================================================================== C05
def c05() -> Dict[str, Any]:
    ADDR_NAM = "số 5 đường Nguyễn Thị Thập, quận 7, TP.HCM"
    phone, d = "0900010010", "2026-10-15"
    q = T.quote("SKU-FAN-SEN", d, phone, ADDR_NAM)
    o = T.simulate_order(phone, "SKU-FAN-SEN", q["final_price_vnd"], None, "COD", ADDR_NAM, d)
    v = {"product": var(T.product_name("SKU-FAN-SEN"), "tên sản phẩm ĐẦY ĐỦ đã gồm loại hàng (đừng viết thêm loại hàng phía trước)", ("sku", "SKU-FAN-SEN")), "price": var(T.money(q["final_price_vnd"]), "giá cuối", ("price_vnd", q["final_price_vnd"])),
         "stock_text": var("còn hàng", "tình trạng tồn kho (kết quả inventory.check)"), "order_id": var(o["order_id"], "mã đơn", ("order_id", o["order_id"])),
         "delivery_days": var("2", "số ngày giao"), "address": var(ADDR_NAM, "địa chỉ giao — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")}
    c = call("call_1", "zalo_oa", "hỏi quạt Senko qua Zalo, nhắn teencode không dấu", "customer",
             "Khách nhắn Zalo hỏi quạt đứng Senko còn hàng không, giá bao nhiêu; rồi chốt lấy 1 cái, COD, ship về "
             f"{ADDR_NAM}. VIẾT CÂU CÓ DẤU BÌNH THƯỜNG (hệ thống sẽ tự chuyển sang teencode/không dấu sau; tuyệt đối đừng tự viết teencode).",
             "Agent trả lời lịch sự bình thường (có dấu): {product} {stock_text}, giá {price}; chốt đơn: mã đơn {order_id}, giao {delivery_days} ngày về {address}.",
             [fact("product_asked", "SKU-FAN-SEN", "hỏi quạt đứng Senko"), fact("payment", "COD", "COD"), fact("address", ADDR_NAM, f"ship về {ADDR_NAM}")], v,
             {"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-FAN-SEN", "price_vnd": q["final_price_vnd"], "payment": "COD"}},
              "ground_truth_facts": {"price_vnd": q["final_price_vnd"], "in_stock": T.stock("SKU-FAN-SEN", d)["in_stock"]},
              "facts_established": {"product_advised": "SKU-FAN-SEN", "price_quoted_vnd": q["final_price_vnd"], "payment": "COD"},
              "expected_outcome": "chot_don", "input_mode": "chat_teencode"},
             n_turns=(6, 8), identity="zalo_tu_c05", date=d, style="teencode", abs_date=d)
    return {"scenario": _meta("SC-C05", "C", "khach_da_kenh_fb_hotline", None, phone, "Tú", "anh",
                              "Khách nhắn teencode/không dấu (customer_turns_asr, input_mode chat_teencode): kiểm chuẩn hóa tiếng Việt trước khi hiểu ý."),
            "calls": [c]}


SAMPLE10 = [a01, a02, a03, b01, b02, c01, c02, c03, c04, c05]


PAYMENT_LABEL = {"COD": "thanh toán khi nhận hàng (COD)", "bank": "chuyển khoản", "momo": "ví MoMo", "zalopay": "ví ZaloPay"}


def apply_order_flow(frame: Dict[str, Any]) -> Dict[str, Any]:
    """Cuộc gọi có `order.create` phải theo ORDER GATE của hệ thống (hỏi/xác nhận → đọc lại đơn → khách đồng ý → chốt): thêm các ô trống
    và fact cần cho lượt đọc lại đơn (tổng tiền, hình thức thanh toán, tên người nhận, SĐT nhận), đánh dấu `order_flow`, tăng số lượt."""
    from src.dataset.rules import is_order_call
    sc = frame["scenario"]
    seen_phone = False
    for c in frame["calls"]:
        facts, vars_ = c["customer_facts"], c["agent_vars"]
        if any(f["key"] == "phone_provided" for f in facts):
            seen_phone = True
        if not is_order_call(c) or c.get("order_flow"):
            continue
        args = (c["expected"].get("success_if") or {}).get("args_match") or {}
        pay_fact = next((f["value"] for f in facts if f["key"] == "payment"), None)
        pay = args.get("payment") or pay_fact or "COD"
        if "readback_total" not in vars_:
            total = vars_["total"]["text"] if "total" in vars_ else (T.money(args["price_vnd"] * int(args.get("qty") or 1)) if args.get("price_vnd") else None)
            if total:
                vars_["readback_total"] = var(total, "tổng tiền cả đơn (giá × số lượng) — dùng khi ĐỌC LẠI ĐƠN")
        vars_["payment_label"] = var(PAYMENT_LABEL.get(pay, pay), "hình thức thanh toán chốt của đơn — dùng khi ĐỌC LẠI ĐƠN")
        if pay_fact and pay_fact != pay:
            vars_["payment_label_initial"] = var(PAYMENT_LABEL.get(pay_fact, pay_fact), "hình thức thanh toán khách chọn ban đầu (trước khi bị đổi)")
        saved = bool(c.get("saved_address"))                          # khách cũ: địa chỉ/tên/SĐT/thanh toán đã lưu → agent chỉ XÁC NHẬN, khách KHÔNG nói lại
        if saved:
            c["customer_facts"] = facts = [f for f in facts if f["key"] not in ("address", "payment", "recipient_name", "phone_provided")]
        elif not any(f["key"] == "recipient_name" for f in facts):
            facts.append(fact("recipient_name", sc["customer_name"], f"nói tên người nhận là {sc['customer_name']}"))
        addr_fact = next((f for f in facts if f["key"] == "address"), None)
        if saved:
            vars_["address"] = var(c["saved_address"], "địa chỉ ĐÃ LƯU từ lần mua trước — chỉ để XÁC NHẬN, khách sẽ không đọc lại")
        elif "address" not in vars_ and addr_fact:
            vars_["address"] = var(addr_fact["value"], "địa chỉ giao (khách vừa đọc) — CHỈ dùng sau khi khách đã đọc địa chỉ", after="address")
        vars_["recipient_name"] = var(sc["customer_name"], "tên người nhận" + ("" if saved else " — CHỈ dùng sau khi khách đã nói tên"),
                                      after=None if saved else "recipient_name")
        chat_first = c.get("channel") != "hotline" and not seen_phone and not saved
        if chat_first and not any(f["key"] == "phone_provided" for f in facts):
            facts.append(fact("phone_provided", sc["customer_phone"], f"đọc SĐT nhận hàng {sc['customer_phone']}"))
            seen_phone = True
        vars_["caller_phone"] = var(sc["customer_phone"], "SĐT nhận hàng (số khách đang gọi/nhắn) — đọc lại để xác nhận",
                                    ("phone", sc["customer_phone"]), after="phone_provided" if chat_first else None)
        c["order_flow"] = True
        lo, hi = c["n_turns"]
        c["n_turns"] = [lo + 3, hi + 4]
    return frame


def build_sample10() -> List[Dict[str, Any]]:
    frames = [apply_order_flow(f()) for f in SAMPLE10]
    T.fresh_orders()
    return frames
