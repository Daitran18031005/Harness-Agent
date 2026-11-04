# 54 kịch bản (SC-Dxx) — bản duyệt theo lô

> Sinh bằng **gpt-6-luna** (lời thoại khách + agent); đáp án/giá/ngày do code tính từ `mock_tools.py`. Tổng chi phí LLM thực tế (mọi lần chạy trong sổ cái): **2,076.3 VND** (trần tích lũy 10,000 VND). Cột `written` = như khách/agent gõ-nói; `spoken` = dạng đọc thành lời (số bằng chữ) dùng cho TTS + chuẩn WER. Mỗi mục kết thúc bằng kết quả kiểm tự động (S1–S14).

## SC-D03 — khach_da_kenh_mau_thuan · ca khó: `mau_thuan_phien_truoc`

*Khách:* chị Châu · SĐT giả `0900020003` · Mâu thuẫn phiên trước (giá khác giữa các kênh): chat_fanpage (2026-09-25) báo 4.390.000đ còn KM AP-SEP, hotline (2026-10-05) báo 4.890.000đ → khách đòi giá thấp nhất từng được báo; agent giải thích KM theo ngày, không hứa giữ giá cũ.

### call_1 — chat_fanpage · 2026-09-25 · hỏi giá/tư vấn qua chat rồi để suy nghĩ

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Chị hỏi Máy lọc không khí AirPure X giá bao nhiêu? Mỗi kênh báo một kiểu, bực thật. | chị hỏi máy lọc không khí e pia x giá bao nhiêu mỗi kênh báo một kiểu bực thật | `{'sku': 'SKU-AP-X'}` |
| 2 | Agent | Em gửi chị Châu giá Máy lọc không khí AirPure X là 4.390.000đ, khuyến mãi đến hết 30/9. Em xin số điện thoại để hotline gọi lại tư vấn thêm nhé chị? | em gửi chị châu giá máy lọc không khí e pia x là bốn triệu ba trăm chín mươi nghìn khuyến mãi đến hết ba mươi tháng chín em xin số điện thoại để hotline gọi lại tư vấn thêm nhé chị | `{'price_vnd': 4390000, 'promo_expiry': '2026-09-30'}` |
| 3 | Khách | À mà… còn hàng không em? | à mà còn hàng không em | `{}` |
| 4 | Agent | Dạ, sản phẩm hiện hiện còn hàng chị Châu nhé. | dạ sản phẩm hiện hiện còn hàng chị châu nhé | `{}` |
| 5 | Khách | Ừ, để chị suy nghĩ rồi gọi hotline. Số chị là 0900020003. | ừ để chị suy nghĩ rồi gọi hotline số chị là không chín không không không hai không không không ba | `{'phone': '0900020003'}` |
| 6 | Agent | Dạ, em ghi nhận rồi chị Châu. Hotline sẽ gọi lại tư vấn cho chị nhé. | dạ em ghi nhận rồi chị châu hotline sẽ gọi lại tư vấn cho chị nhé | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-05 · gọi hotline, bực vì lệch thông tin so với phiên trước, rồi chốt

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-AP-X', 'price_vnd': 4890000, 'payment': 'COD'}, 'forbidden_claims': [{'field': 'price_vnd', 'value': 4390000}]}` · `ground_truth_facts` = `{'price_vnd': 4890000, 'promo_AP-SEP_active': False, 'in_stock': True}` · outcome = `chot_don` · carry-over = `['product_advised', 'price_quoted_vnd']` · không được hỏi = `['product_advised']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Chị bực thật đấy, hôm trước nhắn Fanpage/Zalo họ báo 4.390.000đ, sao giờ hotline lại báo giá khác? Giá thấp nhất từng báo là bao nhiêu? | chị bực thật đấy hôm trước nhắn fanpage zalo họ báo bốn triệu ba trăm chín mươi nghìn sao giờ hotline lại báo giá khác giá thấp nhất từng báo là bao nhiêu | `{}` |
| 3 | Agent | Em xin lỗi chị Châu vì thông tin khiến chị thấy mỗi kênh báo một giá. Khuyến mãi kết thúc ngày 30/9, nên mức 4.390.000đ ở kênh chat không còn áp dụng; giá hôm nay là 4.890.000đ. Em không thể giữ giá cũ ạ. | em xin lỗi chị châu vì thông tin khiến chị thấy mỗi kênh báo một giá khuyến mãi kết thúc ngày ba mươi tháng chín nên mức bốn triệu ba trăm chín mươi nghìn ở kênh chat không còn áp dụng giá hôm nay là bốn triệu tám trăm chín mươi nghìn em không thể giữ giá cũ ạ | `{'promo_expiry': '2026-09-30', 'price_vnd': 4890000}` |
| 4 | Khách | Nhưng chị hỏi giá thấp nhất từng được báo cơ mà. Sao không áp dụng mức đó nữa? | nhưng chị hỏi giá thấp nhất từng được báo cơ mà sao không áp dụng mức đó nữa | `{}` |
| 5 | Agent | Dạ, mức chị được báo ở cuộc trước là giá khuyến mãi theo thời điểm, chị Châu ạ. Khuyến mãi đã kết thúc nên hiện tại em chỉ có thể báo giá hôm nay là 4.890.000đ. Em xin lỗi chị vì sự bất tiện này. | dạ mức chị được báo ở cuộc trước là giá khuyến mãi theo thời điểm chị châu ạ khuyến mãi đã kết thúc nên hiện tại em chỉ có thể báo giá hôm nay là bốn triệu tám trăm chín mươi nghìn em xin lỗi chị vì sự bất tiện này | `{'price_vnd': 4890000}` |
| 6 | Khách | À mà… hôm nay đặt thì thanh toán khi nhận hàng được không? | à mà hôm nay đặt thì thanh toán khi nhận hàng được không | `{}` |
| 7 | Agent | Dạ được ạ. Chị Châu muốn chọn hình thức thanh toán nào để em lên đơn cho mình? | dạ được ạ chị châu muốn chọn hình thức thanh toán nào để em lên đơn cho mình | `{}` |
| 8 | Khách | COD nhé em. | cê ô đê nhé em | `{'payment': 'COD'}` |
| 9 | Agent | Dạ, chị cho em xin tên người nhận và địa chỉ giao hàng với ạ. | dạ chị cho em xin tên người nhận và địa chỉ giao hàng với ạ | `{}` |
| 10 | Khách | Người nhận là Châu, giao về số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội. | người nhận là châu giao về số chín phố bạch mai quận hai bà trưng hà nội | `{'address': 'số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội'}` |
| 11 | Agent | Em xác nhận số đang gọi là 0900020003 để nhận hàng nhé chị Châu? | em xác nhận số đang gọi là không chín không không không hai không không không ba để nhận hàng nhé chị châu | `{'phone': '0900020003'}` |
| 12 | Khách | Đúng rồi. | đúng rồi | `{}` |
| 13 | Agent | Em đọc lại đơn: Máy lọc không khí AirPure X, giá 4.890.000đ, tổng 4.890.000đ, giao cho Châu, SĐT 0900020003, địa chỉ số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | em đọc lại đơn máy lọc không khí e pia x giá bốn triệu tám trăm chín mươi nghìn tổng bốn triệu tám trăm chín mươi nghìn giao cho châu số điện thoại không chín không không không hai không không không ba địa chỉ số chín phố bạch mai quận hai bà trưng hà nội hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-AP-X', 'price_vnd': 4890000, 'phone': '0900020003'}` |
| 14 | Khách | Vâng, chốt đi em. | vâng chốt đi em | `{}` |
| 15 | Agent | Dạ, em chốt đơn mã OD600001 cho chị Châu. Dự kiến giao trong 2 ngày ạ. | dạ em chốt đơn mã ô đê sáu không không không không một cho chị châu dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |
| 16 | Khách | Ừ, cảm ơn em. | ừ cảm ơn em | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D04 — khach_da_kenh_mau_thuan · ca khó: `mau_thuan_phien_truoc`

*Khách:* anh Đạt · SĐT giả `0900020004` · Mâu thuẫn phiên trước (thông tin khác): cuộc 1 khách nêu {'room_area_m2': 22, 'has_children': True, 'budget_vnd': 5800000}, cuộc 2 nói {'room_area_m2': 38, 'budget_vnd': 7000000} → sản phẩm đổi Máy lọc không khí AirPure Y → Máy lọc không khí Samsung AX40; agent ghi giá trị MỚI, không hỏi lại slot còn đúng.

### call_1 — zalo_oa · 2026-10-14 · hỏi giá/tư vấn qua chat rồi để suy nghĩ

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Lọc không khí phòng ngủ? | lọc không khí phòng ngủ | `{}` |
| 2 | Agent | Dạ, em tư vấn máy lọc không khí cho anh Đạt nhé. Phòng ngủ nhà mình rộng khoảng bao nhiêu, nhà có trẻ nhỏ không và ngân sách dự kiến thế nào ạ? | dạ em tư vấn máy lọc không khí cho anh đạt nhé phòng ngủ nhà mình rộng khoảng bao nhiêu nhà có trẻ nhỏ không và ngân sách dự kiến thế nào ạ | `{}` |
| 3 | Khách | Phòng ngủ cỡ 22 mét vuông, nhà đang có con nhỏ. Ngân sách khoảng 5,8 triệu. | phòng ngủ cỡ hai mươi hai mét vuông nhà đang có con nhỏ ngân sách khoảng năm triệu tám trăm nghìn | `{'room_area_m2': 22, 'has_children': True, 'budget_vnd': 5800000}` |
| 4 | Agent | Dạ, em đề xuất Máy lọc không khí AirPure Y, giá cuối đã tính khuyến mãi là 5.200.000đ, hiện hiện còn hàng. Anh cho em xin số điện thoại để hotline gọi lại tư vấn nhé? | dạ em đề xuất máy lọc không khí e pia y giá cuối đã tính khuyến mãi là năm triệu hai trăm nghìn hiện hiện còn hàng anh cho em xin số điện thoại để hotline gọi lại tư vấn nhé | `{'sku': 'SKU-AP-Y', 'price_vnd': 5200000}` |
| 5 | Khách | Khoan đã… giá chốt chưa? | khoan đã giá chốt chưa | `{}` |
| 6 | Agent | Dạ, 5.200.000đ là giá cuối đã tính khuyến mãi rồi ạ. Anh cho em xin số điện thoại để hotline tiện gọi lại nhé? | dạ năm triệu hai trăm nghìn là giá cuối đã tính khuyến mãi rồi ạ anh cho em xin số điện thoại để hotline tiện gọi lại nhé | `{'price_vnd': 5200000}` |
| 7 | Khách | Để anh xem thêm. Số anh là 0900020004. | để anh xem thêm số anh là không chín không không không hai không không không bốn | `{'phone': '0900020004'}` |
| 8 | Agent | Dạ, em ghi nhận rồi ạ. Hotline sẽ gọi lại để tư vấn cho anh Đạt nhé. | dạ em ghi nhận rồi ạ hotline sẽ gọi lại để tư vấn cho anh đạt nhé | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-17 · gọi hotline, bực vì lệch thông tin so với phiên trước, rồi chốt

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-SS-AX40', 'price_vnd': 6490000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 6490000, 'in_stock': True}` · outcome = `chot_don` · carry-over = `['has_children']` · không được hỏi = `['has_children']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Hôm trước nhắn chat họ báo Máy lọc không khí AirPure Y một giá, giờ gọi lại thấy gợi ý mẫu khác, thông tin lệch thế này bực thật. Phòng khoảng 38m², ngân sách tầm 7 triệu. | hôm trước nhắn chat họ báo máy lọc không khí e pia y một giá giờ gọi lại thấy gợi ý mẫu khác thông tin lệch thế này bực thật phòng khoảng ba mươi tám mét vuông ngân sách tầm bảy triệu | `{'room_area_m2': 38, 'budget_vnd': 7000000}` |
| 3 | Agent | Em xin lỗi anh Đạt vì thông tin giữa các lần tư vấn chưa thống nhất. Theo thông tin mới anh vừa cung cấp, mẫu phù hợp là Máy lọc không khí Samsung AX40, giá 6.490.000đ; cuộc trước là Máy lọc không khí AirPure Y, giá 5.200.000đ. Em đã ghi nhận thông tin mới, anh cho em xin tên người nhận và địa chỉ giao hàng nhé. | em xin lỗi anh đạt vì thông tin giữa các lần tư vấn chưa thống nhất theo thông tin mới anh vừa cung cấp mẫu phù hợp là máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn cuộc trước là máy lọc không khí e pia y giá năm triệu hai trăm nghìn em đã ghi nhận thông tin mới anh cho em xin tên người nhận và địa chỉ giao hàng nhé | `{'sku': 'SKU-AP-Y', 'price_vnd': 5200000}` |
| 4 | Khách | Khoan đã… vì sao đổi mẫu rồi vẫn hợp với nhu cầu của tôi? | khoan đã vì sao đổi mẫu rồi vẫn hợp với nhu cầu của tôi | `{}` |
| 5 | Agent | Vì diện tích phòng và ngân sách anh vừa cập nhật khác với thông tin dùng để tư vấn lần trước, nên mẫu phù hợp được điều chỉnh. Anh đọc giúp em tên người nhận và địa chỉ giao hàng nhé. | vì diện tích phòng và ngân sách anh vừa cập nhật khác với thông tin dùng để tư vấn lần trước nên mẫu phù hợp được điều chỉnh anh đọc giúp em tên người nhận và địa chỉ giao hàng nhé | `{}` |
| 6 | Khách | Giao về số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội. Người nhận là Đạt. | giao về số hai mươi hai đường giải phóng quận hoàng mai hà nội người nhận là đạt | `{'address': 'số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội'}` |
| 7 | Agent | Em ghi nhận rồi ạ. Anh thanh toán COD và nhận hàng bằng số điện thoại anh đang gọi đến đây, đúng không ạ? | em ghi nhận rồi ạ anh thanh toán cê ô đê và nhận hàng bằng số điện thoại anh đang gọi đến đây đúng không ạ | `{}` |
| 8 | Khách | COD, đúng số đang gọi. | cê ô đê đúng số đang gọi | `{'payment': 'COD'}` |
| 9 | Agent | Em đọc lại đơn: Máy lọc không khí Samsung AX40, giá 6.490.000đ, tổng 6.490.000đ, giao cho Đạt, SĐT 0900020004, địa chỉ số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Anh xác nhận đặt đơn này chứ ạ? | em đọc lại đơn máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn tổng sáu triệu bốn trăm chín mươi nghìn giao cho đạt số điện thoại không chín không không không hai không không không bốn địa chỉ số hai mươi hai đường giải phóng quận hoàng mai hà nội hình thức thanh toán khi nhận hàng cê ô đê anh xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-SS-AX40', 'price_vnd': 6490000, 'phone': '0900020004'}` |
| 10 | Khách | Đúng rồi, chốt đi em. | đúng rồi chốt đi em | `{}` |
| 11 | Agent | Em chốt đơn cho anh Đạt, mã đơn OD600001, dự kiến giao trong 2 ngày ạ. | em chốt đơn cho anh đạt mã đơn ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D24 — khach_mua_nhieu_mon · ca khó: `het_hang_bien_the`

*Khách:* anh Nam · SĐT giả `0900020024` · Biến thể size 38 màu đen CÒN hàng nhưng khách nói gọn: agent không được báo hết hàng, không hỏi lại size/màu.

### call_1 — hotline · 2026-10-15 · hỏi gọn '38 đen' (CÒN hàng)

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-SN-RUN2-38-DEN', 'price_vnd': 1521000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 1521000, 'in_stock': True, 'requested_variant_in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Giày chạy bộ RunLite 2 Pro, 38 đen còn hàng không? | giày chạy bộ run lai hai pro ba mươi tám đen còn hàng không | `{'sku': 'SKU-SN-RUN2', 'size': 38, 'color': 'den'}` |
| 3 | Agent | Dạ, biến thể size 38 màu đen còn hiện còn hàng ạ. Giá 1.521.000đ. Em xin tên người nhận được không ạ? | dạ biến thể size ba mươi tám màu đen còn hiện còn hàng ạ giá một triệu năm trăm hai mươi mốt nghìn em xin tên người nhận được không ạ | `{'price_vnd': 1521000}` |
| 4 | Khách | Nam. | nam | `{}` |
| 5 | Agent | Dạ anh Nam cho em xin địa chỉ giao hàng ạ? | dạ anh nam cho em xin địa chỉ giao hàng ạ | `{}` |
| 6 | Khách | Số 5 đường Phạm Văn Đồng, quận Bắc Từ Liêm, Hà Nội. | số năm đường phạm văn đồng quận bắc từ liêm hà nội | `{'address': 'số 5 đường Phạm Văn Đồng, quận Bắc Từ Liêm, Hà Nội'}` |
| 7 | Agent | Dạ, số điện thoại nhận hàng là 0900020024, đúng không ạ? Anh muốn thanh toán COD hay chuyển khoản ạ? | dạ số điện thoại nhận hàng là không chín không không không hai không không hai bốn đúng không ạ anh muốn thanh toán cê ô đê hay chuyển khoản ạ | `{'phone': '0900020024'}` |
| 8 | Khách | Đúng số này. COD. | đúng số này cê ô đê | `{'payment': 'COD'}` |
| 9 | Agent | Em đọc lại đơn: Giày chạy bộ RunLite 2 Pro, giá 1.521.000đ, tổng 1.521.000đ, giao cho Nam, SĐT 0900020024, địa chỉ số 5 đường Phạm Văn Đồng, quận Bắc Từ Liêm, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Anh xác nhận đặt đơn này chứ ạ? | em đọc lại đơn giày chạy bộ run lai hai pro giá một triệu năm trăm hai mươi mốt nghìn tổng một triệu năm trăm hai mươi mốt nghìn giao cho nam số điện thoại không chín không không không hai không không hai bốn địa chỉ số năm đường phạm văn đồng quận bắc từ liêm hà nội hình thức thanh toán khi nhận hàng cê ô đê anh xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000, 'phone': '0900020024'}` |
| 10 | Khách | Ừ, chốt đi. | ừ chốt đi | `{}` |
| 11 | Agent | Dạ, mã đơn OD600001, dự kiến giao trong 2 ngày ạ. | dạ mã đơn ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D25 — khach_so_gia · ca khó: `mac_ca`

*Khách:* chị Phương · SĐT giả `0900020025` · Mặc cả: khách đòi 1.400.000đ (giá thật 1.590.000đ); agent giữ giá thật, không tạo đơn ở giá khách đòi; rồi khách chấp nhận giá thật.

### call_1 — chat_fanpage · 2026-10-15 · hỏi Nồi chiên không dầu Xiaomi 4.5L rồi mặc cả

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-AF-XM', 'price_vnd': 1590000, 'payment': 'COD'}, 'forbidden_claims': [{'field': 'price_vnd', 'value': 1400000}]}` · `ground_truth_facts` = `{'price_vnd': 1590000, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Chào em, nồi chiên không dầu Xiaomi 4.5L còn hàng không, giá bao nhiêu? | chào em nồi chiên không dầu xiao mi bốn phẩy năm lít còn hàng không giá bao nhiêu | `{'sku': 'SKU-AF-XM'}` |
| 2 | Agent | Dạ chị Phương, Nồi chiên không dầu Xiaomi 4.5L hiện hiện còn hàng, giá 1.590.000đ ạ. | dạ chị phương nồi chiên không dầu xiao mi bốn phẩy năm lít hiện hiện còn hàng giá một triệu năm trăm chín mươi nghìn ạ | `{'sku': 'SKU-AF-XM', 'price_vnd': 1590000}` |
| 3 | Khách | Ờ, bớt cho chị còn 1.4 triệu được không? | ờ bớt cho chị còn một triệu bốn trăm nghìn được không | `{}` |
| 4 | Agent | Dạ em xin phép giữ giá niêm yết 1.590.000đ ạ, hiện không có chương trình giảm thêm. | dạ em xin phép giữ giá niêm yết một triệu năm trăm chín mươi nghìn ạ hiện không có chương trình giảm thêm | `{'price_vnd': 1590000}` |
| 5 | Khách | Hơi phân vân… em xem giúp chị thêm lần nữa được không? | hơi phân vân em xem giúp chị thêm lần nữa được không | `{}` |
| 6 | Agent | Em hiểu ạ, nhưng bên em chưa có ưu đãi giảm thêm, giá sản phẩm vẫn là 1.590.000đ chị nhé. | em hiểu ạ nhưng bên em chưa có ưu đãi giảm thêm giá sản phẩm vẫn là một triệu năm trăm chín mươi nghìn chị nhé | `{'price_vnd': 1590000}` |
| 7 | Khách | Ừm, được rồi, chị lấy. Người nhận là Phương, giao về số 56 đường Võ Văn Tần, quận 3, TP.HCM nhé. | ừm được rồi chị lấy người nhận là phương giao về số năm mươi sáu đường võ văn tần quận ba tp hcm nhé | `{'address': 'số 56 đường Võ Văn Tần, quận 3, TP.HCM'}` |
| 8 | Agent | Dạ, chị cho em xin số điện thoại nhận hàng và hình thức thanh toán ạ. | dạ chị cho em xin số điện thoại nhận hàng và hình thức thanh toán ạ | `{}` |
| 9 | Khách | 0900020025, COD nhé. | không chín không không không hai không không hai năm cê ô đê nhé | `{'phone': '0900020025', 'payment': 'COD'}` |
| 10 | Agent | Em đọc lại đơn: Nồi chiên không dầu Xiaomi 4.5L, giá 1.590.000đ, tổng 1.590.000đ, giao cho Phương, SĐT 0900020025, địa chỉ số 56 đường Võ Văn Tần, quận 3, TP.HCM, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | em đọc lại đơn nồi chiên không dầu xiao mi bốn phẩy năm lít giá một triệu năm trăm chín mươi nghìn tổng một triệu năm trăm chín mươi nghìn giao cho phương số điện thoại không chín không không không hai không không hai năm địa chỉ số năm mươi sáu đường võ văn tần quận ba tp hcm hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-AF-XM', 'price_vnd': 1590000, 'phone': '0900020025'}` |
| 11 | Khách | Đúng rồi. | đúng rồi | `{}` |
| 12 | Agent | Dạ, em chốt đơn OD600001, dự kiến giao trong 3 ngày ạ. | dạ em chốt đơn ô đê sáu không không không không một dự kiến giao trong ba ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D26 — khach_so_gia · ca khó: `tu_choi_giua_gate`

*Khách:* anh Sơn · SĐT giả `0900020026` · Từ chối SAU khi nghe đọc lại đơn: không tạo đơn, không nối câu hỏi gate ở lượt sau.

### call_1 — zalo_oa · 2026-10-15 · đặt Giày sneaker Urban Classic nhưng từ chối sau khi nghe đọc lại đơn

**Đáp án do code tính:** `success_if` = `{'tool_called': None, 'agent_must_say': True, 'must_not_call_tools': ['order.create'], 'forbidden_claims': ['đã lên đơn', 'đã tạo đơn', 'mã đơn']}` · `ground_truth_facts` = `{'price_vnd': 890000, 'in_stock': True}` · outcome = `tu_choi`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Anh hỏi Giày sneaker Urban Classic size 41, màu đen còn hàng không, giá bao nhiêu? | anh hỏi giày sneaker ơ bần cla xích size bốn mươi mốt màu đen còn hàng không giá bao nhiêu | `{'sku': 'SKU-SN-CAS', 'size': 41, 'color': 'den'}` |
| 2 | Agent | Dạ, Giày sneaker Urban Classic hiện còn hàng, giá 890.000đ ạ. | dạ giày sneaker ơ bần cla xích hiện còn hàng giá tám trăm chín mươi nghìn ạ | `{'price_vnd': 890000}` |
| 3 | Khách | Ờ, để anh xem đã… | ờ để anh xem đã | `{}` |
| 4 | Agent | Anh Sơn cho em xin tên người nhận hàng ạ? | anh sơn cho em xin tên người nhận hàng ạ | `{}` |
| 5 | Khách | Sơn nhé. | sơn nhé | `{}` |
| 6 | Agent | Anh cho em xin địa chỉ giao hàng với ạ. | anh cho em xin địa chỉ giao hàng với ạ | `{}` |
| 7 | Khách | Giao về số 60 đường Láng, quận Cầu Giấy, Hà Nội. Số nhận hàng 0900020026 nhé. | giao về số sáu mươi đường láng quận cầu giấy hà nội số nhận hàng không chín không không không hai không không hai sáu nhé | `{'address': 'số 60 đường Láng, quận Cầu Giấy, Hà Nội', 'phone': '0900020026'}` |
| 8 | Agent | Anh Sơn muốn thanh toán theo hình thức nào ạ? | anh sơn muốn thanh toán theo hình thức nào ạ | `{}` |
| 9 | Khách | COD nhé, mà anh hơi phân vân… | cê ô đê nhé mà anh hơi phân vân | `{'payment': 'COD'}` |
| 10 | Agent | Em đọc lại đơn: Giày sneaker Urban Classic, giá 890.000đ, tổng 890.000đ, giao cho Sơn, SĐT 0900020026, địa chỉ số 60 đường Láng, quận Cầu Giấy, Hà Nội, thanh toán thanh toán khi nhận hàng (COD). Anh xác nhận giúp em ạ? | em đọc lại đơn giày sneaker ơ bần cla xích giá tám trăm chín mươi nghìn tổng tám trăm chín mươi nghìn giao cho sơn số điện thoại không chín không không không hai không không hai sáu địa chỉ số sáu mươi đường láng quận cầu giấy hà nội thanh toán thanh toán khi nhận hàng cê ô đê anh xác nhận giúp em ạ | `{'sku': 'SKU-SN-CAS', 'price_vnd': 890000, 'phone': '0900020026'}` |
| 11 | Khách | Thôi anh không lấy nữa, mắc quá. | thôi anh không lấy nữa mắc quá | `{}` |
| 12 | Agent | Em xin lỗi anh Sơn. Anh cho em hỏi lý do mình chưa lấy ạ? Khi nào cần, anh liên hệ lại với shop nhé. | em xin lỗi anh sơn anh cho em hỏi lý do mình chưa lấy ạ khi nào cần anh liên hệ lại với shop nhé | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D27 — khach_mua_nhieu_mon · ca khó: `het_hang_bien_the`

*Khách:* chị Tâm · SĐT giả `0900020027` · Hết hàng đúng biến thể size M màu đen: agent nói đúng tình trạng và gợi ý màu be (còn hàng) thay vì xin địa chỉ.

### call_1 — hotline · 2026-10-15 · hỏi size M màu đen đã HẾT → nhận biến thể thay thế

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-JK-DWN-M-BE', 'price_vnd': 1490000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 1490000, 'in_stock': True, 'requested_variant_in_stock': False}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Áo phao lông vũ Warmly size M màu đen còn hàng không? | áo phao lông vũ quôm li size m màu đen còn hàng không | `{'sku': 'SKU-JK-DWN', 'size': 'M', 'color': 'den'}` |
| 3 | Agent | Dạ, Áo phao lông vũ Warmly size M màu đen hiện hiện đang hết hàng. Em có thể đổi sang size M màu be, hiện hiện còn hàng, giá 1.490.000đ. Chị Tâm lấy màu be nhé? | dạ áo phao lông vũ quôm li size m màu đen hiện hiện đang hết hàng em có thể đổi sang size m màu be hiện hiện còn hàng giá một triệu bốn trăm chín mươi nghìn chị tâm lấy màu be nhé | `{'sku': 'SKU-JK-DWN', 'price_vnd': 1490000}` |
| 4 | Khách | Ừ, màu be. COD nhé. | ừ màu be cê ô đê nhé | `{'payment': 'COD'}` |
| 5 | Agent | Dạ chị Tâm cho em xin tên người nhận và địa chỉ giao hàng ạ. | dạ chị tâm cho em xin tên người nhận và địa chỉ giao hàng ạ | `{}` |
| 6 | Khách | Tâm, số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội. | tâm số chín phố bạch mai quận hai bà trưng hà nội | `{'address': 'số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội'}` |
| 7 | Agent | Dạ, em xác nhận số điện thoại nhận hàng là 0900020027, số chị đang gọi, đúng không ạ? | dạ em xác nhận số điện thoại nhận hàng là không chín không không không hai không không hai bảy số chị đang gọi đúng không ạ | `{'phone': '0900020027'}` |
| 8 | Khách | Đúng rồi. | đúng rồi | `{}` |
| 9 | Agent | Dạ chị Tâm, em đọc lại đơn Áo phao lông vũ Warmly màu be, giá 1.490.000đ, tổng 1.490.000đ, giao cho Tâm, SĐT 0900020027, địa chỉ số 9 phố Bạch Mai, quận Hai Bà Trưng, Hà Nội, thanh toán thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | dạ chị tâm em đọc lại đơn áo phao lông vũ quôm li màu be giá một triệu bốn trăm chín mươi nghìn tổng một triệu bốn trăm chín mươi nghìn giao cho tâm số điện thoại không chín không không không hai không không hai bảy địa chỉ số chín phố bạch mai quận hai bà trưng hà nội thanh toán thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-JK-DWN', 'price_vnd': 1490000, 'phone': '0900020027'}` |
| 10 | Khách | Ừ, chốt đi. | ừ chốt đi | `{}` |
| 11 | Agent | Dạ chị Tâm, đơn hàng có mã OD600001, dự kiến giao trong 2 ngày ạ. | dạ chị tâm đơn hàng có mã ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D28 — khach_do_du_hoi_nguoi_nha · ca khó: `hoan_giua_gate`

*Khách:* chị Vân · SĐT giả `0900020028` · Hoãn SAU khi nghe đọc lại đơn (cần hỏi người nhà): hủy đơn nháp, ghi blocker, hẹn gọi lại; không tạo đơn.

### call_1 — chat_fanpage · 2026-10-15 · đặt Xe đẩy gấp gọn Joie Pact nhưng hoãn sau khi nghe đọc lại đơn

**Đáp án do code tính:** `success_if` = `{'tool_called': None, 'agent_must_say': True, 'must_not_call_tools': ['order.create'], 'forbidden_claims': ['đã lên đơn', 'đã tạo đơn', 'mã đơn']}` · `ground_truth_facts` = `{'price_vnd': 3490000, 'in_stock': True}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Shop còn Xe đẩy gấp gọn Joie Pact không, giá bao nhiêu ạ? Ờ, chị cũng hơi lo về độ an toàn. | shop còn xe đẩy gấp gọn giô i pact không giá bao nhiêu ạ ờ chị cũng hơi lo về độ an toàn | `{'sku': 'SKU-MB-STR1'}` |
| 2 | Agent | Dạ, Xe đẩy gấp gọn Joie Pact hiện hiện còn hàng, giá 3.490.000đ ạ. Riêng thông tin an toàn cụ thể em chưa có dữ liệu để xác nhận, em xin phép kiểm tra lại. Nếu chị muốn đặt, em xin tên người nhận ạ. | dạ xe đẩy gấp gọn giô i pact hiện hiện còn hàng giá ba triệu bốn trăm chín mươi nghìn ạ riêng thông tin an toàn cụ thể em chưa có dữ liệu để xác nhận em xin phép kiểm tra lại nếu chị muốn đặt em xin tên người nhận ạ | `{'price_vnd': 3490000}` |
| 3 | Khách | Vân. | vân | `{}` |
| 4 | Agent | Dạ chị Vân cho em xin địa chỉ giao hàng với ạ. | dạ chị vân cho em xin địa chỉ giao hàng với ạ | `{}` |
| 5 | Khách | Giao về số 30 đường Giải Phóng, quận Hoàng Mai, Hà Nội nhé. À, chị vẫn muốn hỏi kỹ thêm về độ an toàn. | giao về số ba mươi đường giải phóng quận hoàng mai hà nội nhé à chị vẫn muốn hỏi kỹ thêm về độ an toàn | `{'address': 'số 30 đường Giải Phóng, quận Hoàng Mai, Hà Nội'}` |
| 6 | Agent | Dạ, em ghi nhận địa chỉ rồi ạ. Chị cho em xin số điện thoại nhận hàng để em đọc lại thông tin nhé. | dạ em ghi nhận địa chỉ rồi ạ chị cho em xin số điện thoại nhận hàng để em đọc lại thông tin nhé | `{}` |
| 7 | Khách | 0900020028. | không chín không không không hai không không hai tám | `{'phone': '0900020028'}` |
| 8 | Agent | Dạ, chị muốn thanh toán theo hình thức nào ạ? | dạ chị muốn thanh toán theo hình thức nào ạ | `{}` |
| 9 | Khách | COD nhé. | cê ô đê nhé | `{'payment': 'COD'}` |
| 10 | Agent | Dạ, em đọc lại thông tin để chị kiểm tra: Xe đẩy gấp gọn Joie Pact, giá 3.490.000đ, tổng tiền 3.490.000đ, người nhận Vân, SĐT 0900020028, địa chỉ số 30 đường Giải Phóng, quận Hoàng Mai, Hà Nội, thanh toán thanh toán khi nhận hàng (COD). Chị xác nhận giúp em ạ? | dạ em đọc lại thông tin để chị kiểm tra xe đẩy gấp gọn giô i pact giá ba triệu bốn trăm chín mươi nghìn tổng tiền ba triệu bốn trăm chín mươi nghìn người nhận vân số điện thoại không chín không không không hai không không hai tám địa chỉ số ba mươi đường giải phóng quận hoàng mai hà nội thanh toán thanh toán khi nhận hàng cê ô đê chị xác nhận giúp em ạ | `{'price_vnd': 3490000, 'phone': '0900020028'}` |
| 11 | Khách | Ừm, để chị hỏi chồng đã, giờ chị chưa chốt nhé. | ừm để chị hỏi chồng đã giờ chị chưa chốt nhé | `{'blocker': 'can hoi chong'}` |
| 12 | Agent | Dạ, em ghi nhận chị Vân muốn trao đổi với chồng trước và chưa xác nhận đặt hàng. Khi chị đã trao đổi xong, em sẽ liên hệ lại để hỗ trợ chị ạ. | dạ em ghi nhận chị vân muốn trao đổi với chồng trước và chưa xác nhận đặt hàng khi chị đã trao đổi xong em sẽ liên hệ lại để hỗ trợ chị ạ | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D31 — khach_so_gia · ca khó: `vuot_ngan_sach_2_lua_chon`

*Khách:* chị Thảo · SĐT giả `0900020031` · Vượt ngân sách 62% (> 20%): nhánh HAI LỰA CHỌN (Máy lọc không khí Samsung AX40 vs Máy lọc không khí Xiaomi Smart 4 Lite); khách chọn mẫu TRONG ngân sách.

### call_1 — hotline · 2026-10-15 · hỏi máy lọc không khí có bé nhỏ, ngân sách thấp hơn nhiều so với mẫu phù hợp

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-XM-4L', 'price_vnd': 2990000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 2990000, 'overage_pct': 62, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Chị cần máy lọc không khí cho phòng khoảng 40m², nhà có bé nhỏ. Ngân sách tầm 4 triệu. | chị cần máy lọc không khí cho phòng khoảng bốn mươi mét vuông nhà có bé nhỏ ngân sách tầm bốn triệu | `{'room_area_m2': 40, 'has_children': True, 'budget_vnd': 4000000}` |
| 3 | Agent | Dạ, với phòng của chị, mẫu phù hợp nhất là Máy lọc không khí Samsung AX40, giá 6.490.000đ, vượt ngân sách 62%, có khóa an toàn trẻ em và đủ diện tích. Mẫu Máy lọc không khí Xiaomi Smart 4 Lite giá 2.990.000đ thì trong ngân sách. Chị cân nhắc hai mẫu giúp em nhé. | dạ với phòng của chị mẫu phù hợp nhất là máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn vượt ngân sách sáu mươi hai phần trăm có khóa an toàn trẻ em và đủ diện tích mẫu máy lọc không khí xiao mi smart bốn lite giá hai triệu chín trăm chín mươi nghìn thì trong ngân sách chị cân nhắc hai mẫu giúp em nhé | `{'sku': 'SKU-XM-4L', 'price_vnd': 2990000}` |
| 4 | Khách | Ờ, mẫu đầu vượt nhiều quá. Mẫu trong ngân sách dùng được chứ em? Chị hơi phân vân. | ờ mẫu đầu vượt nhiều quá mẫu trong ngân sách dùng được chứ em chị hơi phân vân | `{}` |
| 5 | Agent | Dạ, nếu chị muốn chọn trong ngân sách thì em tư vấn Máy lọc không khí Xiaomi Smart 4 Lite giá 2.990.000đ. Chị chọn mẫu này để em hỗ trợ đặt hàng nhé? | dạ nếu chị muốn chọn trong ngân sách thì em tư vấn máy lọc không khí xiao mi smart bốn lite giá hai triệu chín trăm chín mươi nghìn chị chọn mẫu này để em hỗ trợ đặt hàng nhé | `{'sku': 'SKU-XM-4L', 'price_vnd': 2990000}` |
| 6 | Khách | Ừm, để chị xem... thôi, lấy mẫu trong ngân sách. | ừm để chị xem thôi lấy mẫu trong ngân sách | `{}` |
| 7 | Agent | Dạ chị Thảo, cho em xin tên người nhận và địa chỉ giao hàng với ạ. | dạ chị thảo cho em xin tên người nhận và địa chỉ giao hàng với ạ | `{}` |
| 8 | Khách | Người nhận là Thảo, giao về số 14 phố Tây Sơn, quận Đống Đa, Hà Nội. | người nhận là thảo giao về số mười bốn phố tây sơn quận đống đa hà nội | `{'address': 'số 14 phố Tây Sơn, quận Đống Đa, Hà Nội'}` |
| 9 | Agent | Dạ, chị thanh toán COD và nhận hàng bằng số điện thoại đang gọi cho em, đúng không ạ? | dạ chị thanh toán cê ô đê và nhận hàng bằng số điện thoại đang gọi cho em đúng không ạ | `{}` |
| 10 | Khách | Đúng rồi, COD nhé. | đúng rồi cê ô đê nhé | `{'payment': 'COD'}` |
| 11 | Agent | Em đọc lại đơn: Máy lọc không khí Xiaomi Smart 4 Lite, giá 2.990.000đ, tổng 2.990.000đ, giao cho Thảo, SĐT 0900020031, địa chỉ số 14 phố Tây Sơn, quận Đống Đa, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Mình xác nhận đặt đơn này chứ ạ? | em đọc lại đơn máy lọc không khí xiao mi smart bốn lite giá hai triệu chín trăm chín mươi nghìn tổng hai triệu chín trăm chín mươi nghìn giao cho thảo số điện thoại không chín không không không hai không không ba một địa chỉ số mười bốn phố tây sơn quận đống đa hà nội hình thức thanh toán khi nhận hàng cê ô đê mình xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-XM-4L', 'price_vnd': 2990000, 'phone': '0900020031'}` |
| 12 | Khách | Đúng rồi em, chốt đi. | đúng rồi em chốt đi | `{}` |
| 13 | Agent | Dạ, mã đơn của chị là OD600001, dự kiến giao trong 2 ngày ạ. | dạ mã đơn của chị là ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D47 — khach_da_kenh_fb_hotline · ca khó: `tu_nhan_khach_cu_chua_sdt`

*Khách:* chị Yến · SĐT giả `0900020047` · Khách tự nhận khách cũ trên kênh chat khi chưa có SĐT: agent không giả vờ nhớ, hỏi SĐT/tài khoản, không nối hồ sơ theo lời khai.

### call_1 — zalo_oa · 2026-10-15 · tự nhận khách cũ nhưng chưa có SĐT, rồi mua

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-AF-XM', 'price_vnd': 1590000, 'payment': 'COD'}, 'forbidden_claims': ['em nhớ', 'như lần trước', 'giống lần trước']}` · `ground_truth_facts` = `{'price_vnd': 1590000, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Chị là khách cũ của shop, mua hồi tháng trước rồi. Giờ chị muốn mua Nồi chiên không dầu Xiaomi 4.5L. | chị là khách cũ của shop mua hồi tháng trước rồi giờ chị muốn mua nồi chiên không dầu xiao mi bốn phẩy năm lít | `{'sku': 'SKU-AF-XM'}` |
| 2 | Agent | Dạ chị Yến cho em xin số điện thoại hoặc tên tài khoản chị đã dùng để em tra hồ sơ ạ. | dạ chị yến cho em xin số điện thoại hoặc tên tài khoản chị đã dùng để em tra hồ sơ ạ | `{}` |
| 3 | Khách | Số chị dùng là 0900020047. | số chị dùng là không chín không không không hai không không bốn bảy | `{'phone': '0900020047'}` |
| 4 | Agent | Em chưa thấy hồ sơ mua hàng với số này nên hỗ trợ chị như khách mới nhé. Nồi chiên không dầu Xiaomi 4.5L giá 1.590.000đ, hiện hiện còn hàng ạ. Chị cho em xin tên người nhận và địa chỉ giao hàng nhé. | em chưa thấy hồ sơ mua hàng với số này nên hỗ trợ chị như khách mới nhé nồi chiên không dầu xiao mi bốn phẩy năm lít giá một triệu năm trăm chín mươi nghìn hiện hiện còn hàng ạ chị cho em xin tên người nhận và địa chỉ giao hàng nhé | `{'price_vnd': 1590000}` |
| 5 | Khách | Người nhận là Yến, giao số 31 phố Nguyễn Chí Thanh, quận Ba Đình, Hà Nội. À mà shop có nhận COD không em? | người nhận là yến giao số ba mươi mốt phố nguyễn chí thanh quận ba đình hà nội à mà shop có nhận cê ô đê không em | `{'address': 'số 45 phố Nguyễn Chí Thanh, quận Ba Đình, Hà Nội'}` |
| 6 | Agent | Dạ được chị Yến, bên em nhận thanh toán COD ạ. Số điện thoại nhận hàng em xác nhận là 0900020047, đúng không ạ? | dạ được chị yến bên em nhận thanh toán cê ô đê ạ số điện thoại nhận hàng em xác nhận là không chín không không không hai không không bốn bảy đúng không ạ | `{'phone': '0900020047'}` |
| 7 | Khách | Đúng rồi, chị thanh toán COD nhé. | đúng rồi chị thanh toán cê ô đê nhé | `{'payment': 'COD'}` |
| 8 | Agent | Em đọc lại đơn: Nồi chiên không dầu Xiaomi 4.5L, giá 1.590.000đ, tổng 1.590.000đ, giao cho Yến, SĐT 0900020047, địa chỉ số 45 phố Nguyễn Chí Thanh, quận Ba Đình, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | em đọc lại đơn nồi chiên không dầu xiao mi bốn phẩy năm lít giá một triệu năm trăm chín mươi nghìn tổng một triệu năm trăm chín mươi nghìn giao cho yến số điện thoại không chín không không không hai không không bốn bảy địa chỉ số bốn mươi lăm phố nguyễn chí thanh quận ba đình hà nội hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'price_vnd': 1590000, 'phone': '0900020047'}` |
| 9 | Khách | Đúng rồi, chốt đi em. | đúng rồi chốt đi em | `{}` |
| 10 | Agent | Dạ, mã đơn OD600001, dự kiến giao trong 2 ngày ạ. | dạ mã đơn ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-D51 — khach_hoi_nhieu_khong_mua · ca khó: `so_noi_bang_chu`

*Khách:* chị Hà · SĐT giả `0900020051` · Số nói bằng chữ (customer_turns_asr, input_mode asr_transcript): ngân sách và SĐT đọc thành lời → kiểm ITN và Entity Accuracy.

### call_1 — hotline · 2026-10-15 · hỏi Máy lọc không khí Xiaomi Smart 4 Pro bằng giọng nói: ngân sách và SĐT đọc bằng chữ

**Đáp án do code tính:** `success_if` = `{'tool_called': None, 'agent_must_say': True, 'must_not_call_tools': ['order.create']}` · `ground_truth_facts` = `{'price_vnd': 5490000, 'warranty_months': 24, 'in_stock': False}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Chị hỏi Máy lọc không khí Xiaomi Smart 4 Pro, còn hàng không, giá bao nhiêu và bảo hành mấy tháng? | chị hỏi máy lọc không khí xiao mi smart bốn pro còn hàng không giá bao nhiêu và bảo hành mấy tháng | `{'sku': 'SKU-XM-4P'}` |
| 3 | Agent | Dạ, Máy lọc không khí Xiaomi Smart 4 Pro hiện hiện đang hết hàng, dự kiến có lại ngày 19/10, giá cuối là 5.490.000đ, bảo hành 24 tháng ạ. Sản phẩm hết hàng, ngày dự kiến có lại hiện chưa được cập nhật, chị Hà nhé. | dạ máy lọc không khí xiao mi smart bốn pro hiện hiện đang hết hàng dự kiến có lại ngày mười chín tháng mười giá cuối là năm triệu bốn trăm chín mươi nghìn bảo hành hai mươi bốn tháng ạ sản phẩm hết hàng ngày dự kiến có lại hiện chưa được cập nhật chị hà nhé | `{'price_vnd': 5490000, 'warranty_months': 24}` |
| 4 | Khách | Ngân sách chị tầm 4.5 triệu. | ngân sách chị tầm bốn triệu năm trăm nghìn | `{'budget_vnd': 4500000}` |
| 5 | Agent | Dạ, em ghi nhận ngân sách của chị Hà ạ. | dạ em ghi nhận ngân sách của chị hà ạ | `{}` |
| 6 | Khách | À mà… chị đọc số để em gọi lại nhé: 0900020051. | à mà chị đọc số để em gọi lại nhé không chín không không không hai không không năm một | `{'phone': '0900020051'}` |
| 7 | Agent | Dạ, em xác nhận số chị vừa đọc là 0900020051, để chị gọi lại đúng số này ạ. | dạ em xác nhận số chị vừa đọc là không chín không không không hai không không năm một để chị gọi lại đúng số này ạ | `{'phone': '0900020051'}` |
| 8 | Khách | Để chị tham khảo thêm rồi gọi lại. | để chị tham khảo thêm rồi gọi lại | `{}` |
| 9 | Agent | Dạ, em ghi nhận ạ. Chị Hà cứ tham khảo thêm, khi cần tư vấn chị gọi lại BTC nhé. | dạ em ghi nhận ạ chị hà cứ tham khảo thêm khi cần tư vấn chị gọi lại bê tê xê nhé | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## Nhật ký sinh (từng lần gọi LLM, gộp 3 lần chạy — xem `reports/generation_runs.jsonl`)

Tổng chi phí LLM: **2,076.3 VND** (trần tích lũy 10,000 VND). Cuộc sinh lại nhiều lần do lỗi của bộ kiểm hay của LLM được ghi ở cột số lần sinh.

| kịch bản | cuộc | số lần sinh | chi phí VND |
|---|---|---|---|
| SC-A01 | call_1 | 1 | 10.1 |
| SC-A01 | call_2 | 1 | 10.1 |
| SC-A02 | call_1 | 2 | 17.8 |
| SC-A02 | call_2 | 3 | 32.0 |
| SC-A03 | call_1 | 2 | 22.0 |
| SC-A03 | call_2 | 3 | 28.7 |
| SC-B01 | call_1 | 3 | 26.8 |
| SC-B01 | call_2 | 1 | 8.2 |
| SC-B01 | call_3 | 3 | 31.4 |
| SC-B02 | call_1 | 3 | 24.6 |
| SC-B02 | call_2 | 3 | 21.1 |
| SC-B02 | call_3 | 3 | 22.9 |
| SC-C01 | call_1 | 3 | 36.1 |
| SC-C02 | call_1 | 1 | 10.3 |
| SC-C03 | call_1 | 2 | 17.3 |
| SC-C04 | call_1 | 3 | 34.3 |
| SC-C05 | call_1 | 1 | 7.4 |
| SC-A01 | call_2 | 2 | 22.3 |
| SC-A02 | call_2 | 1 | 10.9 |
| SC-A03 | call_2 | 1 | 8.9 |
| SC-B02 | call_1 | 1 | 7.0 |
| SC-C01 | call_1 | 1 | 12.5 |
| SC-C04 | call_1 | 1 | 11.8 |
| SC-C05 | call_1 | 1 | 7.8 |
| SC-B01 | call_2 | 2 | 18.7 |
| SC-C05 | call_1 | 1 | 9.7 |
| SC-A01 | call_1 | 1 | 12.857 |
| SC-A01 | call_1 | 2 | 12.697 |
| SC-A01 | call_2 | 1 | 21.369 |
| SC-A01 | call_2 | 2 | 19.665 |
| SC-A01 | call_2 | 3 | 16.256 |
| SC-A02 | call_1 | 1 | 7.635 |
| SC-A02 | call_1 | 2 | 11.438 |
| SC-A02 | call_2 | 1 | 21.687 |
| SC-A02 | call_2 | 2 | 19.578 |
| SC-A02 | call_2 | 3 | 16.789 |
| SC-A03 | call_1 | 1 | 13.437 |
| SC-A03 | call_1 | 2 | 12.172 |
| SC-A03 | call_1 | 3 | 12.07 |
| SC-A03 | call_2 | 1 | 16.515 |
| SC-A03 | call_2 | 2 | 16.553 |
| SC-B01 | call_1 | 1 | 10.592 |
| SC-B01 | call_2 | 1 | 23.663 |
| SC-B01 | call_2 | 2 | 19.82 |
| SC-B01 | call_2 | 3 | 23.688 |
| SC-B01 | call_3 | 1 | 11.321 |
| SC-B01 | call_3 | 2 | 11.732 |
| SC-B01 | call_3 | 3 | 11.58 |
| SC-B02 | call_1 | 1 | 14.968 |
| SC-B02 | call_1 | 2 | 15.281 |
| SC-B02 | call_1 | 3 | 17.755 |
| SC-B02 | call_2 | 1 | 9.809 |
| SC-B02 | call_2 | 2 | 10.307 |
| SC-B02 | call_2 | 3 | 9.891 |
| SC-B02 | call_3 | 1 | 10.424 |
| SC-B02 | call_3 | 2 | 11.674 |
| SC-B02 | call_3 | 3 | 9.235 |
| SC-C01 | call_1 | 1 | 20.02 |
| SC-C01 | call_1 | 2 | 18.623 |
| SC-C01 | call_1 | 3 | 18.23 |
| SC-C02 | call_1 | 1 | 11.273 |
| SC-C03 | call_1 | 1 | 11.313 |
| SC-C03 | call_1 | 2 | 12.913 |
| SC-C03 | call_1 | 3 | 10.739 |
| SC-C04 | call_1 | 1 | 21.186 |
| SC-C04 | call_1 | 2 | 22.027 |
| SC-C04 | call_1 | 3 | 20.704 |
| SC-C05 | call_1 | 1 | 16.243 |
| SC-C05 | call_1 | 2 | 16.378 |
| SC-C05 | call_1 | 3 | 20.208 |
| SC-A01 | call_2 | 1 | 16.485 |
| SC-A01 | call_2 | 2 | 21.41 |
| SC-A03 | call_1 | 1 | 12.56 |
| SC-B01 | call_2 | 1 | 14.826 |
| SC-B01 | call_2 | 2 | 19.555 |
| SC-B01 | call_3 | 1 | 13.228 |
| SC-B01 | call_3 | 2 | 11.328 |
| SC-B01 | call_3 | 3 | 10.884 |
| SC-B02 | call_1 | 1 | 13.495 |
| SC-B02 | call_1 | 2 | 16.962 |
| SC-B02 | call_2 | 1 | 8.265 |
| SC-B02 | call_3 | 1 | 10.249 |
| SC-B02 | call_3 | 2 | 8.4 |
| SC-C01 | call_1 | 1 | 19.55 |
| SC-C01 | call_1 | 2 | 16.149 |
| SC-C01 | call_1 | 3 | 17.574 |
| SC-C03 | call_1 | 1 | 11.43 |
| SC-C03 | call_1 | 2 | 11.62 |
| SC-C03 | call_1 | 3 | 11.435 |
| SC-C04 | call_1 | 1 | 17.823 |
| SC-C05 | call_1 | 1 | 14.684 |
| SC-C05 | call_1 | 2 | 14.912 |
| SC-C05 | call_1 | 3 | 14.534 |
| SC-D03 | call_1 | 1 | 10.422 |
| SC-D03 | call_2 | 1 | 18.303 |
| SC-D03 | call_2 | 2 | 19.319 |
| SC-D04 | call_1 | 1 | 15.926 |
| SC-D04 | call_1 | 2 | 16.068 |
| SC-D04 | call_1 | 3 | 16.685 |
| SC-D04 | call_2 | 1 | 25.446 |
| SC-D04 | call_2 | 2 | 18.58 |
| SC-D24 | call_1 | 1 | 13.551 |
| SC-D25 | call_1 | 1 | 17.973 |
| SC-D25 | call_1 | 2 | 18.748 |
| SC-D25 | call_1 | 3 | 18.989 |
| SC-D26 | call_1 | 1 | 17.046 |
| SC-D26 | call_1 | 2 | 15.845 |
| SC-D27 | call_1 | 1 | 14.689 |
| SC-D27 | call_1 | 2 | 15.009 |
| SC-D28 | call_1 | 1 | 15.936 |
| SC-D28 | call_1 | 2 | 15.154 |
| SC-D28 | call_1 | 3 | 15.103 |
| SC-D31 | call_1 | 1 | 19.383 |
| SC-D47 | call_1 | 1 | 16.807 |
| SC-D47 | call_1 | 2 | 17.163 |
| SC-D47 | call_1 | 3 | 19.853 |
| SC-D51 | call_1 | 1 | 16.784 |
| SC-D51 | call_1 | 2 | 16.601 |
| SC-D51 | call_1 | 3 | 16.932 |
| SC-D04 | call_1 | 1 | 20.759 |
| SC-D04 | call_1 | 2 | 22.017 |
| SC-D25 | call_1 | 1 | 27.3 |
| SC-D25 | call_1 | 2 | 17.31 |
| SC-D28 | call_1 | 1 | 14.887 |
| SC-D28 | call_1 | 2 | 13.81 |
| SC-D51 | call_1 | 1 | 17.112 |
| SC-D51 | call_1 | 2 | 14.585 |
| SC-D28 | call_1 | 1 | 15.862 |
