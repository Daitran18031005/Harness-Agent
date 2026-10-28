# 5 khung chọn ngẫu nhiên (seed 42: SC-D02, SC-D08, SC-D18, SC-D41, SC-D48)

Mỗi khung gồm: thông tin khách, từng cuộc (kênh/ngày/mục tiêu), **dàn ý khách và agent** (LLM chỉ viết lời từ đây), **fact khách PHẢI nói**, **ô trống lời agent** (giá trị do code tính), và **đáp án định dạng BTC**. File đầy đủ: `dataset/frames54/SC-Dxx.frame.json`.

## SC-D02 — adv (nhóm A, 2 cuộc)

- Khách: **anh Bình**, SĐT 0900020002; persona `khach_do_du_hoi_nguoi_nha`; ca khó `None`; ngành máy lọc không khí; miền Nam
- Ghi chú: A1 tư vấn qua chat → chốt hotline (máy lọc không khí cho phòng khách); sản phẩm đứng đầu theo luật slot.

### call_1 — zalo_oa — 2026-10-14 — `hỏi tư vấn máy lọc không khí cho phòng khách qua chat`
- Mở đầu: `customer` · số lượt [7, 10] · style `normal`
- **Dàn ý khách:** Khách nhắn hỏi máy lọc không khí cho phòng khách. Khi được hỏi mới nói: phòng khoảng 38m²; ngân sách tầm 7 triệu. Nghe giá xong nói 'để anh hỏi vợ đã' và đọc SĐT để hotline gọi lại.
- **Dàn ý agent:** Agent hỏi các thông tin còn thiếu (một câu mỗi lượt), đề xuất MỘT sản phẩm {product} giá {price} (lý do chọn: diện tích phủ phải ≥ diện tích phòng; giá 6.490.000đ trong ngân sách 7.000.000đ); ghi nhận khách cần hỏi người nhà và xin SĐT để gọi lại.
- **Fact khách phải nói:** `room_area_m2`=38 (phòng khoảng 38m²); `budget_vnd`=7000000 (ngân sách tầm 7 triệu); `blocker`='can hoi vo' (để anh hỏi vợ đã); `phone_provided`='0900020002' (đọc SĐT 0900020002 để hotline gọi lại)
- **Ô trống agent:** `{product}`='Máy lọc không khí Samsung AX40'; `{price}`='6.490.000đ'; `{stock}`='hiện còn hàng'
- **Đáp án BTC:** `{"facts_established": {"product_advised": "SKU-SS-AX40", "room_area_m2": 38, "budget_vnd": 7000000, "price_quoted_vnd": 6490000, "blocker": "can hoi vo", "channel": "zalo", "phone_provided": "0900020002"}, "expected_outcome": "hen_goi_lai"}`

### call_2 — hotline — 2026-10-16 — `gọi hotline chốt đơn sau khi hỏi người nhà` — **ORDER GATE**
- Mở đầu: `agent` · số lượt [11, 15] · style `normal`
- **Dàn ý khách:** Khách gọi hotline: 'vừa nhắn hỏi máy lọc không khí cho phòng khách'; vợ anh đồng ý rồi; hỏi giá còn như cũ không; chốt lấy, giao về số 61 đường Láng, quận Cầu Giấy, Hà Nội, COD (không nhắc lại thông tin đã nói ở cuộc 1).
- **Dàn ý agent:** Agent nhận ra khách từ cuộc chat, xác nhận {product} giá {price}, KHÔNG hỏi lại các thông tin đã có; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.
- **Fact khách phải nói:** `blocker_resolved`=True (vợ anh đồng ý rồi); `payment`='COD' (thanh toán khi nhận hàng (COD)); `address`='số 61 đường Láng, quận Cầu Giấy, Hà Nội' (giao về số 61 đường Láng, quận Cầu Giấy, Hà Nội); `recipient_name`='Bình' (nói tên người nhận là Bình)
- **Ô trống agent:** `{product}`='Máy lọc không khí Samsung AX40'; `{price}`='6.490.000đ'; `{order_id}`='OD600001'; `{delivery_days}`='3'; `{address}`='số 61 đường Láng, quận Cầu Giấy, Hà Nội' [sau khi khách nói `address`]; `{stock}`='hiện còn hàng'; `{readback_total}`='6.490.000đ'; `{payment_label}`='thanh toán khi nhận hàng (COD)'; `{recipient_name}`='Bình' [sau khi khách nói `recipient_name`]; `{caller_phone}`='0900020002'
- **Đáp án BTC:** `{"must_carry_over": ["product_advised", "price_quoted_vnd", "room_area_m2", "blocker"], "must_not_ask": ["product_advised", "room_area_m2", "budget_vnd"], "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-SS-AX40", "price_vnd": 6490000, "payment": "COD"}}, "ground_truth_facts": {"price_vnd": 6490000, "in_stock": true}, "memory_expectation": {"room_area_m2": 38, "product_advised": "SKU-SS-AX40"}, "expected_outcome": "chot_don"}`

## SC-D08 — promo_expired (nhóm A, 2 cuộc)

- Khách: **chị Linh**, SĐT 0900020008; persona `khach_so_gia`; ca khó `khuyen_mai_het_han`; ngành giày; miền Bắc
- Ghi chú: Khuyến mãi RUN2-SALE hết 2026-10-07: cuộc 1 (2026-10-05) còn hạn, cuộc 2 (2026-10-09) đã hết → agent không giữ ưu đãi cũ.

### call_1 — chat_fanpage — 2026-10-05 — `hỏi Giày chạy bộ RunLite 2 Pro và khuyến mãi`
- Mở đầu: `customer` · số lượt [6, 8] · style `normal`
- **Dàn ý khách:** Khách nhắn hỏi Giày chạy bộ RunLite 2 Pro giá bao nhiêu, nghe nói đang có khuyến mãi; nói 'để chị suy nghĩ rồi gọi hotline' và đọc SĐT.
- **Dàn ý agent:** Agent báo {product} giá {price}, đang giảm đến hết {promo_end}; xin SĐT để hotline gọi lại.
- **Fact khách phải nói:** `product_asked`='SKU-SN-RUN2' (hỏi Giày chạy bộ RunLite 2 Pro); `phone_provided`='0900020008' (đọc SĐT 0900020008)
- **Ô trống agent:** `{product}`='Giày chạy bộ RunLite 2 Pro'; `{price}`='1.352.000đ'; `{promo_end}`='7/10'; `{old_price}`='1.352.000đ'; `{stock}`='hiện còn hàng'
- **Đáp án BTC:** `{"facts_established": {"product_advised": "SKU-SN-RUN2", "price_quoted_vnd": 1352000, "promo_code": "RUN2-SALE", "promo_expiry": "2026-10-07", "channel": "fanpage", "phone_provided": "0900020008"}, "expected_outcome": "hen_goi_lai"}`

### call_2 — hotline — 2026-10-09 — `gọi lại khi khuyến mãi đã hết hạn rồi vẫn mua` — **ORDER GATE**
- Mở đầu: `agent` · số lượt [10, 14] · style `normal`
- **Dàn ý khách:** Khách gọi: 'chị gọi lấy Giày chạy bộ RunLite 2 Pro hôm trước, vẫn giá 1.352.000đ đúng không?'; nghe tin khuyến mãi đã hết thì hơi tiếc nhưng vẫn lấy, COD, giao về số 62 đường Láng, quận Cầu Giấy, Hà Nội.
- **Dàn ý agent:** Agent nói rõ khuyến mãi đã kết thúc ngày {promo_end}; báo giá hôm nay {price}; KHÔNG còn mức giá cũ {old_price}, không hứa giữ giá; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.
- **Fact khách phải nói:** `payment`='COD' (COD); `address`='số 62 đường Láng, quận Cầu Giấy, Hà Nội' (giao về số 62 đường Láng, quận Cầu Giấy, Hà Nội); `recipient_name`='Linh' (nói tên người nhận là Linh)
- **Ô trống agent:** `{product}`='Giày chạy bộ RunLite 2 Pro'; `{price}`='1.690.000đ'; `{promo_end}`='7/10'; `{order_id}`='OD600001'; `{delivery_days}`='2'; `{address}`='số 62 đường Láng, quận Cầu Giấy, Hà Nội' [sau khi khách nói `address`]; `{old_price}`='1.352.000đ'; `{stock}`='hiện còn hàng'; `{readback_total}`='1.690.000đ'; `{payment_label}`='thanh toán khi nhận hàng (COD)'; `{recipient_name}`='Linh' [sau khi khách nói `recipient_name`]; `{caller_phone}`='0900020008'
- **Đáp án BTC:** `{"must_carry_over": ["product_advised"], "must_not_ask": ["product_advised"], "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-SN-RUN2", "price_vnd": 1690000}, "forbidden_claims": [{"field": "price_vnd", "value": 1352000}]}, "ground_truth_facts": {"price_vnd": 1690000, "promo_RUN2-SALE_active": false, "in_stock": true}, "expected_outcome": "chot_don"}`

## SC-D18 — exchange (nhóm B, 3 cuộc)

- Khách: **anh Bảo**, SĐT 0900020018; persona `khach_da_mua_doi_size`; ca khó `None`; ngành áo khoác; miền Nam
- Ghi chú: 3 cuộc, 2 kênh chat + hotline: hỏi giá → chốt → đổi size L→XL có phụ thu 40.000đ.

### call_1 — chat_fanpage — 2026-10-14 — `hỏi giá Áo phao lông vũ Warmly qua chat`
- Mở đầu: `customer` · số lượt [5, 7] · style `normal`
- **Dàn ý khách:** Khách nhắn hỏi Áo phao lông vũ Warmly size L màu đen giá bao nhiêu; đọc SĐT 0900020018; nói 'tối anh nhắn chốt'.
- **Dàn ý agent:** Agent báo giá {price} cho size L màu đen; xin SĐT.
- **Fact khách phải nói:** `size`='L' (size L); `color`='den' (màu đen); `phone_provided`='0900020018' (đọc SĐT 0900020018)
- **Ô trống agent:** `{product}`='Áo phao lông vũ Warmly'; `{price}`='1.490.000đ'; `{stock}`='hiện còn hàng'
- **Đáp án BTC:** `{"facts_established": {"product_advised": "SKU-JK-DWN", "size": "L", "color": "den", "price_quoted_vnd": 1490000, "channel": "fanpage", "phone_provided": "0900020018"}, "expected_outcome": "hen_goi_lai"}`

### call_2 — zalo_oa — 2026-10-15 — `chốt đơn qua chat` — **ORDER GATE**
- Mở đầu: `customer` · số lượt [9, 12] · style `normal`
- **Dàn ý khách:** Khách nhắn: 'anh hỏi Áo phao lông vũ Warmly hôm qua'; chốt lấy size L màu đen, COD, giao về số 29 đường Hùng Vương, quận Ninh Kiều, Cần Thơ.
- **Dàn ý agent:** Agent nhận ra khách từ cuộc trước, KHÔNG hỏi lại sản phẩm/size/màu; xác nhận giá {price}; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày về {address}.
- **Fact khách phải nói:** `payment`='COD' (COD); `address`='số 29 đường Hùng Vương, quận Ninh Kiều, Cần Thơ' (giao về số 29 đường Hùng Vương, quận Ninh Kiều, Cần Thơ); `recipient_name`='Bảo' (nói tên người nhận là Bảo)
- **Ô trống agent:** `{product}`='Áo phao lông vũ Warmly'; `{price}`='1.490.000đ'; `{order_id}`='OD600001'; `{delivery_days}`='3'; `{address}`='số 29 đường Hùng Vương, quận Ninh Kiều, Cần Thơ' [sau khi khách nói `address`]; `{stock}`='hiện còn hàng'; `{readback_total}`='1.490.000đ'; `{payment_label}`='thanh toán khi nhận hàng (COD)'; `{recipient_name}`='Bảo' [sau khi khách nói `recipient_name`]; `{caller_phone}`='0900020018'
- **Đáp án BTC:** `{"must_carry_over": ["product_advised", "size", "color", "price_quoted_vnd"], "must_not_ask": ["product_advised", "size", "color"], "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-JK-DWN-L-DEN", "price_vnd": 1490000, "payment": "COD"}}, "ground_truth_facts": {"price_vnd": 1490000, "in_stock": true}, "facts_established": {"order_id": "OD600001", "variant_sku": "SKU-JK-DWN-L-DEN", "payment": "COD"}, "expected_outcome": "chot_don"}`

### call_3 — hotline — 2026-10-18 — `gọi hotline đổi sang size XL`
- Mở đầu: `agent` · số lượt [7, 10] · style `normal`
- **Dàn ý khách:** Khách gọi: 'anh mới nhận giày/áo, size L không vừa, đổi lên size XL được không, mất phí gì không?'; nghe phụ thu 40.000đ thì đồng ý, nhờ làm thủ tục đổi.
- **Dàn ý agent:** Agent biết ngay đơn {order_id} ({product}, size {old_size}); báo chính sách đổi trả {return_days} ngày, phí đổi {exchange_fee}, nhưng size {new_size} có phụ thu: khách trả thêm {extra_payment}; sau khi khách đồng ý thì làm thủ tục đổi. KHÔNG hỏi lại mã đơn/sản phẩm/màu.
- **Fact khách phải nói:** `size_new`='XL' (đổi lên size XL)
- **Ô trống agent:** `{order_id}`='OD600001'; `{product}`='Áo phao lông vũ Warmly'; `{old_size}`='L'; `{new_size}`='XL'; `{exchange_fee}`='không'; `{return_days}`='7'; `{extra_payment}`='40.000đ'; `{stock}`='hiện còn hàng'
- **Đáp án BTC:** `{"must_carry_over": ["order_id", "variant_sku", "size", "color"], "must_not_ask": ["product_advised", "order_id", "color", "payment"], "success_if": {"tool_called": "order.update", "args_match": {"order_id": "OD600001", "new_variant_sku": "SKU-JK-DWN-XL-DEN", "action": "exchange_size"}}, "ground_truth_facts": {"return_days": 7, "exchange_fee_vnd": 0, "extra_payment_vnd": 40000, "new_size_in_stock": true}, "expected_outcome": "chot_don"}`

## SC-D41 — off_doc (nhóm C, 1 cuộc)

- Khách: **chị Oanh**, SĐT 0900020041; persona `khach_hoi_ngoai_tai_lieu`; ca khó `hoi_ngoai_tai_lieu_doi_thu`; ngành máy lọc nước; miền Bắc
- Ghi chú: So giá đối thủ (máy lọc nước).

### call_1 — hotline — 2026-10-15 — `so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)`
- Mở đầu: `agent` · số lượt [7, 10] · style `normal`
- **Dàn ý khách:** Khách hỏi Máy lọc nước RO Kangaroo 10 lõi giá bao nhiêu; nói 'bên Nguyễn Kim bán 6.3 triệu thôi, bên em có bằng giá không?'; hỏi thêm 'có bảo hành quốc tế không?'; cuối cùng 'để chị cân nhắc rồi gọi lại'.
- **Dàn ý agent:** Agent báo {product} giá {price}, bảo hành {warranty} tháng chính hãng; KHÔNG chê đối thủ, KHÔNG hứa khớp giá/giảm không có chương trình; về bảo hành quốc tế nói thẳng là em chưa có thông tin trong tài liệu và sẽ nhờ nhân viên phản hồi.
- **Fact khách phải nói:** `product_asked`='SKU-WF-RO10' (hỏi Máy lọc nước RO Kangaroo 10 lõi); `competitor_price_vnd`=6300000 (bên Nguyễn Kim bán rẻ hơn, chỉ 6.3 triệu); `blocker`='so sanh gia' (để chị cân nhắc rồi gọi lại)
- **Ô trống agent:** `{product}`='Máy lọc nước RO Kangaroo 10 lõi'; `{price}`='6.890.000đ'; `{warranty}`='36'; `{stock}`='hiện còn hàng'
- **Đáp án BTC:** `{"success_if": {"tool_called": null, "agent_must_say": true, "forbidden_claims": [{"field": "price_vnd", "value": 6300000}, "bảo hành quốc tế có"]}, "ground_truth_facts": {"price_vnd": 6890000, "warranty_months": 36}, "facts_established": {"product_advised": "SKU-WF-RO10", "price_quoted_vnd": 6890000, "competitor_price_vnd": 6300000, "blocker": "so sanh gia"}, "expected_outcome": "hen_goi_lai"}`

## SC-D48 — claims_returning (nhóm C, 1 cuộc)

- Khách: **anh Bảo**, SĐT 0900020048; persona `khach_da_kenh_fb_hotline`; ca khó `tu_nhan_khach_cu_chua_sdt`; ngành mẹ & bé; miền Nam
- Ghi chú: Khách tự nhận khách cũ trên kênh chat khi chưa có SĐT: agent không giả vờ nhớ, hỏi SĐT/tài khoản, không nối hồ sơ theo lời khai.

### call_1 — chat_fanpage — 2026-10-15 — `tự nhận khách cũ nhưng chưa có SĐT, rồi mua` — **ORDER GATE**
- Mở đầu: `customer` · số lượt [10, 13] · style `normal`
- **Dàn ý khách:** Khách nhắn: 'anh là khách cũ của shop, mua hồi tháng trước rồi, giờ muốn mua Máy hâm sữa Fatz 4 chức năng' (không kèm SĐT); khi agent hỏi SĐT/tài khoản đã dùng thì mới đọc SĐT 0900020048; nghe agent nói chưa thấy hồ sơ thì vẫn mua như khách mới, COD, giao về số 39 đường Hùng Vương, quận Ninh Kiều, Cần Thơ. Tính cách: thân mật.
- **Dàn ý agent:** Agent KHÔNG giả vờ nhớ khách (không nói 'em nhớ…', 'như lần trước'); lịch sự hỏi SĐT hoặc tên tài khoản đã dùng để tra hồ sơ; tra xong nói rõ em CHƯA thấy hồ sơ mua hàng với số này nên hỗ trợ như khách mới, không nêu thông tin cũ nào; rồi báo {product} giá {price}; theo quy trình đặt đơn rồi chốt: mã đơn {order_id}, giao {delivery_days} ngày.
- **Fact khách phải nói:** `product_asked`='SKU-MB-MON' (hỏi mua Máy hâm sữa Fatz 4 chức năng); `claimed_status`='khách cũ' (nói mình là khách cũ, đã mua ở shop hồi tháng trước (KHÔNG đọc SĐT ngay từ đầu)); `phone_provided`='0900020048' (chỉ đọc SĐT 0900020048 khi agent hỏi để tra hồ sơ); `payment`='COD' (COD); `address`='số 39 đường Hùng Vương, quận Ninh Kiều, Cần Thơ' (giao về số 39 đường Hùng Vương, quận Ninh Kiều, Cần Thơ); `recipient_name`='Bảo' (nói tên người nhận là Bảo)
- **Ô trống agent:** `{product}`='Máy hâm sữa Fatz 4 chức năng'; `{price}`='490.000đ'; `{order_id}`='OD600001'; `{delivery_days}`='3'; `{address}`='số 39 đường Hùng Vương, quận Ninh Kiều, Cần Thơ' [sau khi khách nói `address`]; `{stock}`='hiện còn hàng'; `{readback_total}`='490.000đ'; `{payment_label}`='thanh toán khi nhận hàng (COD)'; `{recipient_name}`='Bảo' [sau khi khách nói `recipient_name`]; `{caller_phone}`='0900020048'
- **Đáp án BTC:** `{"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-MB-MON", "price_vnd": 490000, "payment": "COD"}, "forbidden_claims": ["em nhớ", "như lần trước", "giống lần trước"]}, "ground_truth_facts": {"price_vnd": 490000, "in_stock": true}, "facts_established": {"product_advised": "SKU-MB-MON", "price_quoted_vnd": 490000, "payment": "COD"}, "expected_outcome": "chot_don"}`

