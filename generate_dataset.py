"""
Sinh thêm kịch bản test M1 (đa phiên, đa kênh, ca biên) dựa trên dữ liệu THẬT trong
catalog/products.json, catalog/promotions.json, catalog/crm_seed.json — không bịa SKU/giá/
ngày/khách hàng. Output: BTC-Data-Vong1-TEAMS/test_set/generated_m1/SC-GEN-NN.json (thư mục
mới, chỉ thêm, không đụng file gốc của BTC).

Ca biên dùng SỐ LIỆU THẬT đã verify trong eval/mock_tools.py (không theo con số brief gốc
có thể lệch với mock thật):
- Khuyến mãi hết hạn theo ngày (RUN2-SALE hết hạn 2026-10-07, RUN-10 hết hạn 2026-10-25...).
- Hạn mức COD thật: order.create trả error nếu COD total > 10.000.000đ; cần xác nhận gọi lại
  (needs_confirmation_call=true) nếu COD total > 2.000.000đ.
- SĐT dùng chung: lấy đúng cặp C034/C035 (shared_phone_with) có sẵn trong crm_seed.json.
- Đổi size có phụ thu biến thể: RunLite 2 Pro size 43 có price_delta_vnd=50000 (so với size
  khác delta=0) — đổi từ size không phụ thu sang size 43 sẽ phát sinh extra_payment_vnd thật
  theo đúng logic order.update trong mock_tools.py (không phải DT-03 service fee).
"""
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "test_set", "generated_m1")

ALLOWED_CALL_FIELDS = {
    "channel", "channel_identity", "call_date", "days_later", "customer_turns",
    "customer_turns_asr", "input_mode", "seed_history", "facts_established",
    "must_carry_over", "must_not_ask", "success_if", "ground_truth_facts",
    "memory_expectation", "expected_outcome", "customer_goal",
}

SCENARIOS = [
    # 1. Khuyến mãi RUN2-SALE (giảm 20% RunLite 2 Pro) hết hạn 2026-10-07 — call_2 sau đó
    # phải báo hết KM, không được giữ giá đã giảm.
    {
        "scenario_id": "SC-GEN-01", "level": "M1", "persona": "khach_thich_khuyen_mai",
        "hard_case": "khuyen_mai_het_han", "customer_phone": "0949066882",
        "customer_name": "Phương", "honorific": "chị",
        "notes": "RUN2-SALE (giảm 20% RunLite 2 Pro) hết hạn 2026-10-07. call_1 trong hạn, call_2 sau khi hết hạn phải báo giá về lại giá gốc, không giữ giá khuyến mãi cũ.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-06",
                "customer_turns": [
                    "Em ơi giày RunLite 2 Pro đang giảm giá đúng không?",
                    "Giá bao nhiêu sau giảm vậy em?",
                    "Để chị suy nghĩ thêm, mai chị gọi lại."
                ],
                "facts_established": {"product_advised": "SKU-SN-RUN2", "promo_code": "RUN2-SALE"},
                "expected_outcome": "hen_goi_lai"
            },
            "call_2": {
                "days_later": 10,
                "customer_turns": [
                    "Alo em, giày RunLite 2 Pro hôm trước đang giảm 20% đó, chị lấy luôn nhé."
                ],
                "must_carry_over": ["product_advised"],
                "must_not_ask": ["product_advised"],
                "ground_truth_facts": {"promo_active": False, "price_vnd": 1690000},
                "success_if": {"forbidden_claims": [{"field": "promo_active", "value": True}]},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 2. COD vượt hạn mức thật (>10.000.000đ) — AirPure Pro x2 = 15.980.000đ.
    {
        "scenario_id": "SC-GEN-02", "level": "M1", "persona": "khach_mua_cho_bo_me",
        "hard_case": "cod_vuot_han_muc", "customer_phone": "0911265844",
        "customer_name": "Toàn", "honorific": "anh",
        "notes": "Mua 2 máy AirPure Pro (7.990.000đ/máy = 15.980.000đ) thanh toán COD — vượt hạn mức COD thật 10.000.000đ của mock_tools.order_create, phải báo lỗi/đề xuất chuyển khoản, không được tự tạo đơn COD vượt hạn mức.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Anh muốn mua 2 máy AirPure Pro biếu bố mẹ hai bên, thanh toán COD nhé.",
                    "Vậy giờ lên đơn COD cho anh đi."
                ],
                "facts_established": {"product_advised": "SKU-AP-PRO"},
                "success_if": {
                    "tool_called": "order.create",
                    "forbidden_claims": [{"field": "order_created", "value": True}]
                },
                "ground_truth_facts": {"cod_limit_vnd": 10000000, "total_vnd": 15980000},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 3. COD trong hạn mức nhưng cần gọi xác nhận (>2.000.000đ).
    {
        "scenario_id": "SC-GEN-03", "level": "M1", "persona": "khach_can_ship_gap",
        "hard_case": "cod_can_xac_nhan", "customer_phone": "0932448452",
        "customer_name": "Diệp", "honorific": "chị",
        "notes": "Đơn COD 4.890.000đ (AirPure X) — dưới hạn mức 10tr nhưng trên 2tr nên mock_tools.order_create trả needs_confirmation_call=true, agent phải báo khách sẽ có người gọi xác nhận trước khi giao.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi chị cần máy lọc không khí AirPure X giao gấp trong hôm nay.",
                    "Ok COD nhé, lên đơn cho chị."
                ],
                "facts_established": {"product_advised": "SKU-AP-X", "price_quoted_vnd": 4890000},
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-X", "price_vnd": 4890000}},
                "ground_truth_facts": {"needs_confirmation_call": True},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 4. SĐT dùng chung thật (C034/C035).
    {
        "scenario_id": "SC-GEN-04", "level": "M1", "persona": "khach_dung_chung_sdt",
        "hard_case": "sdt_dung_chung", "customer_phone": "0958421083",
        "customer_name": "Loan", "honorific": "cô",
        "notes": "SĐT 0958421083 dùng chung giữa cô Loan (C034) và chị Dung (C035) — đúng dữ liệu crm_seed.json. Agent PHẢI hỏi xác nhận danh tính trước khi nạp lại thông tin cá nhân nhạy cảm (diện tích, đơn hàng cũ...).",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Alo, cho hỏi máy lọc nước Karofi 9 lõi bên em giá bao nhiêu?"
                ],
                "must_not_ask": [],
                "success_if": {"must_say_any": ["xác nhận", "tên mình", "cho em hỏi tên"]},
                "ground_truth_facts": {"ambiguous_identity": True},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 5. Đổi size có phụ thu biến thể thật (size 43 price_delta_vnd=50000).
    {
        "scenario_id": "SC-GEN-05", "level": "M1", "persona": "khach_doi_size",
        "hard_case": "doi_size_phu_thu_bien_the", "customer_phone": "0930976582",
        "customer_name": "Cường", "honorific": "anh",
        "notes": "Đổi từ RunLite 2 Pro size 40 màu đen (delta 0) sang size 43 màu đen (delta +50.000đ) — phụ thu biến thể thật theo products.json, cộng dồn với fee đổi size lần đầu (DT-03: miễn phí dịch vụ đổi, nhưng vẫn phải trả phần chênh giá biến thể extra_payment_vnd).",
        "calls": {
            "call_1": {
                "call_date": "2026-09-20",
                "customer_turns": [
                    "Em ơi giày RunLite 2 Pro còn size 40 màu đen không?",
                    "Ok lên đơn cho anh, COD nhé."
                ],
                "facts_established": {
                    "product_advised": "SKU-SN-RUN2", "variant_sku": "SKU-SN-RUN2-40-DEN",
                    "size": 40, "color": "den", "price_quoted_vnd": 1690000, "payment": "COD"
                },
                "expected_outcome": "chot_don"
            },
            "call_2": {
                "days_later": 5,
                "customer_turns": [
                    "Alo em, giày RunLite nhận rồi nhưng anh muốn đổi lên size 43 cùng màu đen.",
                    "Có phụ thu gì không em?"
                ],
                "must_carry_over": ["variant_sku", "size", "color"],      # v2: bỏ order_id (mã đơn do mock sinh lúc chạy, cuộc 1 không có fact tĩnh tương ứng)
                "must_not_ask": ["product_advised", "color"],
                "success_if": {
                    "tool_called": "order.update",
                    "args_match": {"new_variant_sku": "SKU-SN-RUN2-43-DEN", "action": "exchange_size"}
                },
                "ground_truth_facts": {"variant_price_delta_vnd": 50000},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 6. Đa kênh: chat Fanpage trước, rồi hotline (khách mới, chưa từng dùng trong public_sample).
    {
        "scenario_id": "SC-GEN-06", "level": "M1", "persona": "khach_da_kenh_fb_hotline",
        "hard_case": None, "customer_phone": "0930048764",
        "customer_name": "Hà", "honorific": "chị",
        "notes": "Khách hỏi giá máy hút sữa Spectra S1 qua Fanpage trước, 2 ngày sau gọi hotline chốt đơn — phải nhận diện liên thông kênh và không hỏi lại giá/sản phẩm đã tư vấn.",
        "calls": {
            "call_1": {
                "channel": "chat_fanpage", "channel_identity": "fb.ha.seed",
                "call_date": "2026-10-13",
                "customer_turns": [
                    "shop oi may hut sua Spectra S1 gia bn a",
                    "co tang gi khong",
                    "sdt minh 0930048764 de minh goi hotline sau nhe"
                ],
                "facts_established": {
                    "product_advised": "SKU-MB-PUMP1", "price_quoted_vnd": 4290000,
                    "promo_code": "PUMP-GIFT", "channel": "fanpage", "phone_provided": "0930048764"
                },
                "expected_outcome": "hen_goi_lai"
            },
            "call_2": {
                "channel": "hotline", "days_later": 2,
                "customer_turns": [
                    "Alo, chị vừa nhắn Fanpage hỏi máy hút sữa Spectra đó em.",
                    "Giá vẫn vậy đúng không, lên đơn cho chị COD nhé.",
                    "À mà hôm trước em nói có tặng túi trữ sữa, giờ còn không em?"
                ],
                "must_carry_over": ["product_advised", "price_quoted_vnd", "promo_code"],
                "must_not_ask": ["product_advised", "price_quoted_vnd"],
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-MB-PUMP1", "price_vnd": 4290000}},
                "ground_truth_facts": {"price_vnd": 4290000, "promo_active": False, "promo_end_date": "2026-10-13"},      # v2: PUMP-GIFT (quà) hết hạn 13/10, call_2 ngày 15/10; giá không đổi
                "expected_outcome": "chot_don"
            }
        }
    },
    # 7. Khách khiếu nại (persona khach_khiếu_nại) — sản phẩm lỗi, cần chính sách DT-05.
    {
        "scenario_id": "SC-GEN-07", "level": "M1", "persona": "khach_khiếu_nại",
        "hard_case": None, "customer_phone": "0956517883",
        "customer_name": "Thủy", "honorific": "chị",
        "notes": "Máy lọc không khí AirPure X bị lỗi kỹ thuật từ nhà sản xuất sau 10 ngày sử dụng — chính sách DT-05 cho đổi mới 1-1 trong 30 ngày với lỗi nhà sản xuất (khác DT-01 7 ngày đổi trả thường), agent phải phân biệt đúng.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Alo, máy lọc AirPure X chị mua bị lỗi, không lên nguồn, mới dùng 10 ngày thôi.",
                    "Vậy giờ xử lý sao em?"
                ],
                "success_if": {"must_say_any": ["30 ngày", "ba mươi ngày", "lỗi nhà sản xuất"]},
                "ground_truth_facts": {"exchange_window_days": 30},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 8. Khách hỏi ngoài phạm vi (y tế) — phải handoff.
    {
        "scenario_id": "SC-GEN-08", "level": "M1", "persona": "khach_hoi_ngoai_pham_vi",
        "hard_case": "cau_hoi_y_te", "customer_phone": "0954742843",
        "customer_name": "Giang", "honorific": "chị",
        "notes": "Khách hỏi máy hút sữa có an toàn cho người đang uống thuốc kháng sinh không — câu hỏi y tế ngoài phạm vi tư vấn bán hàng, agent phải từ chối trả lời chuyên môn y tế và chuyển máy/hẹn chuyên viên, không tự bịa lời khuyên y tế.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi máy hút sữa Spectra S1 dùng khi mẹ đang uống kháng sinh có ảnh hưởng gì không?"
                ],
                "success_if": {"agent_must_say": True, "must_not_call_tools": []},
                "ground_truth_facts": {"is_medical_question": True},
                "expected_outcome": "chuyen_may"
            }
        }
    },
    # 9. Khách thay đổi ý định (đổi SKU giữa buổi).
    {
        "scenario_id": "SC-GEN-09", "level": "M1", "persona": "khach_thay_doi_y_dinh",
        "hard_case": None, "customer_phone": "0928144976",
        "customer_name": "Trung", "honorific": "anh",
        "notes": "Khách ban đầu hỏi AirPure Mini, sau đó đổi ý sang AirPure X trong CÙNG cuộc gọi — profile memory phải supersede đúng (không giữ cả 2 giá trị product_advised).",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi máy lọc AirPure Mini giá bao nhiêu?",
                    "À thôi anh đổi ý, lấy AirPure X cho chắc, giá sao em?",
                    "Ok lên đơn AirPure X cho anh, COD."
                ],
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-X"}},
                "ground_truth_facts": {"final_product_advised": "SKU-AP-X"},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 10. Khách hỏi nhiều nhưng không mua (so sánh nhiều sản phẩm).
    {
        "scenario_id": "SC-GEN-10", "level": "M1", "persona": "khach_hoi_nhieu_khong_mua",
        "hard_case": None, "customer_phone": "0963279264",
        "customer_name": "Đạt", "honorific": "anh",
        "notes": "Khách so sánh AirPure X/Y/Pro rồi không chốt — không được agent tự chốt hộ hoặc bịa giá so sánh, chỉ dùng catalog.search/pricing.get_quote thật cho từng SKU được hỏi.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em so sánh giúp anh AirPure X, Y, Pro khác nhau thế nào, giá sao?",
                    "Thôi để anh suy nghĩ thêm."
                ],
                "success_if": {"must_not_call_tools": []},
                "ground_truth_facts": {},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 11. Khách hết kiên nhẫn — agent hỏi lại nhiều lần thông tin đã có (test RQR).
    {
        "scenario_id": "SC-GEN-11", "level": "M1", "persona": "khach_het_kien_nhan",
        "hard_case": None, "customer_phone": "0924410646",
        "customer_name": "Sơn", "honorific": "anh",
        "notes": "Khách đã cung cấp diện tích/ngân sách ngay turn 1 — agent không được hỏi lại các slot này ở turn sau trong CÙNG cuộc gọi (test RQR nội bộ 1 call, không chỉ carry-over liên call).",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Anh cần máy lọc không khí cho phòng 40m², ngân sách 6 triệu, có bé nhỏ.",
                    "Vậy mẫu nào hợp lý nhất?"
                ],
                "facts_established": {"room_area_m2": 40, "budget_vnd": 6000000, "has_children": True},      # v2: slot nêu ngay trong cuộc 1 (cơ sở cho must_not_ask cùng cuộc)
                "must_not_ask": ["room_area_m2", "budget_vnd", "has_children"],
                "success_if": {"must_say_any": ["AX40", "Samsung AX40"]},
                "ground_truth_facts": {"best_fit_sku": "SKU-SS-AX40", "price_vnd": 6490000, "child_safe_lock": True, "room_area_m2": 40},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 12. Khách mua cho bố mẹ (địa chỉ giao khác số đặt).
    {
        "scenario_id": "SC-GEN-12", "level": "M1", "persona": "khach_mua_cho_bo_me",
        "hard_case": None, "customer_phone": "0925822018",
        "customer_name": "Quỳnh", "honorific": "chị",
        "notes": "Mua máy lọc nước Sunhouse UF biếu bố mẹ, giao địa chỉ khác — order.create cần address khác customer_phone liên lạc.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi máy lọc nước UF Sunhouse giá bao nhiêu, chị mua biếu bố mẹ ở quê.",
                    "Ok lên đơn, giao về địa chỉ khác số này nhé, để chị gửi sau."
                ],
                "facts_established": {"product_advised": "SKU-WF-UF", "price_quoted_vnd": 3290000},
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-WF-UF"}},
                "ground_truth_facts": {"price_vnd": 3290000},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 13. Trade-in thật (TRADE-IN-AP yêu cầu requires_owned_sku=SKU-AP-X-2024) — dùng C031 (đã sở hữu).
    {
        "scenario_id": "SC-GEN-13", "level": "M1", "persona": "khach_so_gia",
        "hard_case": "trade_in_dieu_kien", "customer_phone": "0985003703",
        "customer_name": "Oanh", "honorific": "chị",
        "notes": "Khách C031 đã sở hữu AirPure X bản 2024 (SKU-AP-X-2024, đơn OD188213 delivered) — đủ điều kiện TRADE-IN-AP (trừ 400.000đ khi đổi sang AirPure X/Y/Pro). pricing.get_quote với customer_phone thật phải tự áp dụng đúng promo này.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi chị có máy AirPure X đời 2024 rồi, giờ muốn đổi lên AirPure Pro, có ưu đãi thu cũ đổi mới không?",
                    "Vậy giá sau ưu đãi là bao nhiêu, lên đơn cho chị luôn."
                ],
                "must_not_ask": [],
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-PRO"}},
                "ground_truth_facts": {"promo_code": "TRADE-IN-AP", "discount_vnd": 400000, "final_price_vnd": 7590000},
                "expected_outcome": "chot_don"
            }
        }
    },
    # 14. Sản phẩm ngừng bán (SKU-AP-X-2024 discontinued, successor SKU-AP-X).
    {
        "scenario_id": "SC-GEN-14", "level": "M1", "persona": "khach_hoi_nhieu_khong_mua",
        "hard_case": "sku_ngung_ban", "customer_phone": "0965237355",
        "customer_name": "Xuân", "honorific": "chị",
        "notes": "Khách hỏi mua AirPure X bản 2024 (SKU-AP-X-2024, đã ngừng bán theo products.json attributes.discontinued=true) — agent phải báo ngừng bán và gợi ý sản phẩm thay thế SKU-AP-X (successor_sku thật), không được tạo đơn cho SKU ngừng bán.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi AirPure X bản 2024 còn bán không, chị thấy quảng cáo cũ."
                ],
                "success_if": {"must_not_call_tools": ["order.create"], "must_say_any": ["ngừng bán", "AirPure X"]},
                "ground_truth_facts": {"discontinued": True, "successor_sku": "SKU-AP-X"},
                "expected_outcome": "hen_goi_lai"
            }
        }
    },
    # 15. Freeship miền Nam (NAM-SHIP0) — khách ở vùng Nam mua đồ gia dụng.
    {
        "scenario_id": "SC-GEN-15", "level": "M1", "persona": "khach_thich_khuyen_mai",
        "hard_case": None, "customer_phone": "0957990659",
        "customer_name": "Bảo", "honorific": "anh",
        "notes": "Khách ở TP.HCM (miền Nam) mua quạt Panasonic — đủ điều kiện NAM-SHIP0 (freeship gia dụng miền Nam), agent phải báo đúng freeship thật từ pricing.get_quote, không tự đoán.",
        "calls": {
            "call_1": {
                "call_date": "2026-10-15",
                "customer_turns": [
                    "Em ơi quạt đứng Panasonic F-409 giá bao nhiêu, anh ở quận 1 TP.HCM.",
                    "Có freeship không em, lên đơn cho anh."
                ],
                "facts_established": {"product_advised": "SKU-FAN-DC1"},
                "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-FAN-DC1"}},
                "ground_truth_facts": {"freeship": True, "price_vnd": 2450000},
                "expected_outcome": "chot_don"
            }
        }
    },
]


def validate_scenario(spec: dict) -> None:
    required_top = {"scenario_id", "level", "persona", "customer_phone", "customer_name", "honorific", "calls"}
    missing = required_top - set(spec.keys())
    assert not missing, f"{spec.get('scenario_id')}: thiếu field top-level {missing}"
    for call_name, call_spec in spec["calls"].items():
        assert call_name in ("call_1", "call_2", "call_3"), f"{spec['scenario_id']}: tên call lạ {call_name}"
        extra = set(call_spec.keys()) - ALLOWED_CALL_FIELDS
        assert not extra, f"{spec['scenario_id']}.{call_name}: field lạ không có trong scenario_format.md: {extra}"
        assert call_spec.get("customer_turns"), f"{spec['scenario_id']}.{call_name}: thiếu customer_turns"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for spec in SCENARIOS:
        validate_scenario(spec)
        out_path = os.path.join(OUT_DIR, f"{spec['scenario_id']}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=2)
        written.append(out_path)
        print(f"[OK] {spec['scenario_id']} ({spec['persona']}, hard_case={spec.get('hard_case')}) -> {out_path}")

    print(f"\nĐã sinh {len(written)} kịch bản vào {OUT_DIR}")


if __name__ == "__main__":
    main()
