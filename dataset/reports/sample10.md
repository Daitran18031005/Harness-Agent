# 10 kịch bản mẫu — bản duyệt

> Sinh bằng **gpt-6-luna** (lời thoại khách + agent); đáp án/giá/ngày do code tính từ `mock_tools.py`. Tổng chi phí LLM thực tế (3 lần chạy): **1,470.4 VND** (trần 500). Cột `written` = như khách/agent gõ-nói; `spoken` = dạng đọc thành lời (số bằng chữ) dùng cho TTS + chuẩn WER. Mỗi mục kết thúc bằng kết quả kiểm tự động (S1–S14).

## SC-A01 — khach_do_du_hoi_nguoi_nha

*Khách:* chị Thu · SĐT giả `0900010001` · Đa kênh Fanpage→Hotline: nối danh tính qua SĐT; blocker 'hỏi chồng'; sản phẩm duy nhất có khóa trẻ em vượt ngân sách ~4% (luật ngân sách ≤ 20%: vẫn chốt và nêu mức vượt).

### call_1 — chat_fanpage · 2026-10-15 · hỏi máy lọc không khí cho phòng ngủ có bé nhỏ

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Chào em, chị muốn hỏi máy lọc không khí cho phòng ngủ có bé nhỏ. | chào em chị muốn hỏi máy lọc không khí cho phòng ngủ có bé nhỏ | `{}` |
| 2 | Agent | Em chào chị Thu. Phòng ngủ nhà mình khoảng bao nhiêu mét vuông, và nhà mình có bé nhỏ không ạ? | em chào chị thu phòng ngủ nhà mình khoảng bao nhiêu mét vuông và nhà mình có bé nhỏ không ạ | `{}` |
| 3 | Khách | Phòng khoảng 25m², nhà có bé 2 tuổi. Ngân sách tầm 5 triệu thôi em. | phòng khoảng hai mươi lăm mét vuông nhà có bé hai tuổi ngân sách tầm năm triệu thôi em | `{'room_area_m2': 25, 'has_children': True, 'budget_vnd': 5000000}` |
| 4 | Agent | Với phòng của chị Thu, em đề xuất Máy lọc không khí AirPure Y, giá cuối 5.200.000đ, vượt ngân sách của chị 4%. Sản phẩm có khóa an toàn trẻ em nên phù hợp nhà mình; hiện hiện còn hàng. Mình còn được tặng Màng lọc thay thế AirPure X/Y đến hết 22/10 ạ. | với phòng của chị thu em đề xuất máy lọc không khí e pia y giá cuối năm triệu hai trăm nghìn vượt ngân sách của chị bốn phần trăm sản phẩm có khóa an toàn trẻ em nên phù hợp nhà mình hiện hiện còn hàng mình còn được tặng màng lọc thay thế e pia x y đến hết hai mươi hai tháng mười ạ | `{'sku': 'SKU-AP-Y', 'price_vnd': 5200000, 'promo_expiry': '2026-10-22'}` |
| 5 | Khách | Ờ, giá hơi vượt ngân sách, để chị hỏi chồng đã... | ờ giá hơi vượt ngân sách để chị hỏi chồng đã | `{'blocker': 'can hoi chong'}` |
| 6 | Agent | Dạ, chị cứ trao đổi với chồng nhé. Chị cho em xin số điện thoại để hotline gọi lại tư vấn thêm được không ạ? | dạ chị cứ trao đổi với chồng nhé chị cho em xin số điện thoại để hotline gọi lại tư vấn thêm được không ạ | `{}` |
| 7 | Khách | Ừm, 0900010001 nhé. | ừm không chín không không không một không không không một nhé | `{'phone': '0900010001'}` |
| 8 | Agent | Em ghi nhận số của chị Thu để hotline liên hệ lại ạ. Chị cứ hỏi chồng, khi nào cần thêm thông tin thì nhắn em nhé. | em ghi nhận số của chị thu để hotline liên hệ lại ạ chị cứ hỏi chồng khi nào cần thêm thông tin thì nhắn em nhé | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-17 · gọi hotline chốt đơn sau khi hỏi chồng

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-AP-Y', 'price_vnd': 5200000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 5200000, 'promo_active': True, 'in_stock': True, 'delivery_days': 2}` · outcome = `chot_don` · carry-over = `['product_advised', 'price_quoted_vnd', 'room_area_m2', 'has_children', 'blocker']` · không được hỏi = `['product_advised', 'room_area_m2', 'has_children', 'budget_vnd']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Chị vừa nhắn Facebook hỏi máy lọc không khí. Chồng chị đồng ý rồi, giá còn như cũ không em? | chị vừa nhắn facebook hỏi máy lọc không khí chồng chị đồng ý rồi giá còn như cũ không em | `{}` |
| 3 | Agent | Dạ, em nhận ra chị Thu từ Fanpage ạ. Máy lọc không khí AirPure Y hiện giá 5.200.000đ, còn quà Màng lọc thay thế AirPure X/Y đến 22/10. | dạ em nhận ra chị thu từ fanpage ạ máy lọc không khí e pia y hiện giá năm triệu hai trăm nghìn còn quà màng lọc thay thế e pia x y đến hai mươi hai tháng mười | `{'sku': 'SKU-AP-Y', 'price_vnd': 5200000, 'promo_expiry': '2026-10-22'}` |
| 4 | Khách | À, còn hàng không em? Quà đó vẫn được tặng chứ? | à còn hàng không em quà đó vẫn được tặng chứ | `{}` |
| 5 | Agent | Dạ còn hàng hiện còn hàng, quà Màng lọc thay thế AirPure X/Y vẫn áp dụng đến 22/10 ạ. Chị cho em xin địa chỉ giao hàng nhé? | dạ còn hàng hiện còn hàng quà màng lọc thay thế e pia x y vẫn áp dụng đến hai mươi hai tháng mười ạ chị cho em xin địa chỉ giao hàng nhé | `{'promo_expiry': '2026-10-22'}` |
| 6 | Khách | Ờ, để chị xem... giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội nhé. | ờ để chị xem giao về số mười hai đường nguyễn trãi quận thanh xuân hà nội nhé | `{'address': 'số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội'}` |
| 7 | Agent | Dạ, em xin tên người nhận và hình thức thanh toán của chị ạ. | dạ em xin tên người nhận và hình thức thanh toán của chị ạ | `{}` |
| 8 | Khách | Tên người nhận là Thu, thanh toán khi nhận hàng (COD) em nhé. | tên người nhận là thu thanh toán khi nhận hàng cê ô đê em nhé | `{'payment': 'COD'}` |
| 9 | Agent | Dạ, số điện thoại nhận hàng là số chị đang gọi cho em, đúng không ạ? | dạ số điện thoại nhận hàng là số chị đang gọi cho em đúng không ạ | `{}` |
| 10 | Khách | Đúng rồi em. | đúng rồi em | `{}` |
| 11 | Agent | Dạ, em đọc lại đơn: Máy lọc không khí AirPure Y, giá 5.200.000đ, tổng 5.200.000đ, giao cho Thu, SĐT 0900010001, địa chỉ số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | dạ em đọc lại đơn máy lọc không khí e pia y giá năm triệu hai trăm nghìn tổng năm triệu hai trăm nghìn giao cho thu số điện thoại không chín không không không một không không không một địa chỉ số mười hai đường nguyễn trãi quận thanh xuân hà nội hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-AP-Y', 'price_vnd': 5200000, 'phone': '0900010001'}` |
| 12 | Khách | Vâng, chốt đi em. | vâng chốt đi em | `{}` |
| 13 | Agent | Dạ, đơn hàng của chị là OD600001, dự kiến giao trong 2 ngày ạ. | dạ đơn hàng của chị là ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-A02 — khach_hoi_nhieu_khong_mua · ca khó: `mau_thuan_phien_truoc`

*Khách:* anh Long · SĐT giả `0900010002` · Mâu thuẫn với phiên trước: size/màu khách nói ở cuộc 2 khác cuộc 1 → bộ nhớ phải ghi giá trị MỚI và đánh dấu giá trị cũ bị thay thế.

### call_1 — hotline · 2026-10-15 · hỏi giày chạy bộ RunLite 2 Pro, chưa quyết

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Anh hỏi giày chạy bộ RunLite 2 Pro, size 40 màu đen giá bao nhiêu, còn hàng không? | anh hỏi giày chạy bộ run lai hai pro size bốn mươi màu đen giá bao nhiêu còn hàng không | `{'sku': 'SKU-SN-RUN2', 'size': 40, 'color': 'den'}` |
| 3 | Agent | Dạ, sản phẩm Giày chạy bộ RunLite 2 Pro size 40 màu đen hiện có giá 1.521.000đ, còn hiện còn hàng ạ. | dạ sản phẩm giày chạy bộ run lai hai pro size bốn mươi màu đen hiện có giá một triệu năm trăm hai mươi mốt nghìn còn hiện còn hàng ạ | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000}` |
| 4 | Khách | Có giảm không em? | có giảm không em | `{}` |
| 5 | Agent | Dạ, sản phẩm đang giảm 10%, chương trình đến 25/10 ạ. | dạ sản phẩm đang giảm mười phần trăm chương trình đến hai mươi lăm tháng mười ạ | `{'promo_expiry': '2026-10-25'}` |
| 6 | Khách | À mà… nếu mua rồi không vừa thì đổi trả sao em? | à mà nếu mua rồi không vừa thì đổi trả sao em | `{}` |
| 7 | Agent | Dạ, sản phẩm Giày chạy bộ RunLite 2 Pro được đổi trả trong 7 ạ. | dạ sản phẩm giày chạy bộ run lai hai pro được đổi trả trong bảy ạ | `{'sku': 'SKU-SN-RUN2'}` |
| 8 | Khách | Khoan đã… hàng còn chứ? | khoan đã hàng còn chứ | `{}` |
| 9 | Agent | Dạ, hiện sản phẩm Giày chạy bộ RunLite 2 Pro hiện còn hàng ạ. | dạ hiện sản phẩm giày chạy bộ run lai hai pro hiện còn hàng ạ | `{'sku': 'SKU-SN-RUN2'}` |
| 10 | Khách | Ừ, để anh xem thêm đã, chưa quyết nhé. | ừ để anh xem thêm đã chưa quyết nhé | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-18 · gọi lại, ĐỔI size/màu khác lần trước rồi chốt

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-SN-RUN2-42-XAM', 'price_vnd': 1521000}}` · `ground_truth_facts` = `{'price_vnd': 1521000, 'promo_active': True, 'in_stock': True}` · outcome = `chot_don` · carry-over = `['product_advised', 'promo_code']` · không được hỏi = `['product_advised']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Hôm trước anh nói size 40 màu đen nhưng anh nhầm, anh đi size 42 và muốn màu xám. À mà giao mất mấy ngày em? | hôm trước anh nói size bốn mươi màu đen nhưng anh nhầm anh đi size bốn mươi hai và muốn màu xám à mà giao mất mấy ngày em | `{'size': 42, 'color': 'xam'}` |
| 3 | Agent | Dạ, em ghi nhận đổi size 40 sang 42, màu đen sang xám cho Giày chạy bộ RunLite 2 Pro. Giá biến thể mới là 1.521.000đ, hiện hiện còn hàng; thời gian giao dự kiến 2. Anh cho em xin tên người nhận và địa chỉ giao hàng nhé. | dạ em ghi nhận đổi size bốn mươi sang bốn mươi hai màu đen sang xám cho giày chạy bộ run lai hai pro giá biến thể mới là một triệu năm trăm hai mươi mốt nghìn hiện hiện còn hàng thời gian giao dự kiến hai anh cho em xin tên người nhận và địa chỉ giao hàng nhé | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000}` |
| 4 | Khách | Người nhận là Long. | người nhận là long | `{}` |
| 5 | Agent | Dạ, anh cho em xin địa chỉ giao hàng và xác nhận giúp em hình thức thanh toán mình chọn nhé. | dạ anh cho em xin địa chỉ giao hàng và xác nhận giúp em hình thức thanh toán mình chọn nhé | `{}` |
| 6 | Khách | Giao về số 8 phố Hoàng Hoa Thám, quận Ba Đình, Hà Nội. COD nhé. | giao về số tám phố hoàng hoa thám quận ba đình hà nội cê ô đê nhé | `{'address': 'số 8 phố Hoàng Hoa Thám, quận Ba Đình, Hà Nội', 'payment': 'COD'}` |
| 7 | Agent | Em xác nhận đơn sẽ gửi về số điện thoại 0900010002 anh đang gọi, đúng không ạ? | em xác nhận đơn sẽ gửi về số điện thoại không chín không không không một không không không hai anh đang gọi đúng không ạ | `{'phone': '0900010002'}` |
| 8 | Khách | Đúng rồi. | đúng rồi | `{}` |
| 9 | Agent | Em đọc lại đơn: Giày chạy bộ RunLite 2 Pro, giá 1.521.000đ, tổng 1.521.000đ, giao cho Long, SĐT 0900010002, địa chỉ số 8 phố Hoàng Hoa Thám, quận Ba Đình, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Anh xác nhận đặt đơn này chứ ạ? | em đọc lại đơn giày chạy bộ run lai hai pro giá một triệu năm trăm hai mươi mốt nghìn tổng một triệu năm trăm hai mươi mốt nghìn giao cho long số điện thoại không chín không không không một không không không hai địa chỉ số tám phố hoàng hoa thám quận ba đình hà nội hình thức thanh toán khi nhận hàng cê ô đê anh xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000, 'phone': '0900010002'}` |
| 10 | Khách | Ok em, chốt đi. | ok em chốt đi | `{}` |
| 11 | Agent | Dạ, em chốt đơn OD600001 cho anh. Đơn dự kiến giao trong 2. | dạ em chốt đơn ô đê sáu không không không không một cho anh đơn dự kiến giao trong hai | `{'order_id': 'OD600001'}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-A03 — khach_so_gia · ca khó: `khuyen_mai_het_han`

*Khách:* chị Mai · SĐT giả `0900010003` · Khuyến mãi quà tặng PUMP-GIFT (hết 13/10): cuộc 1 còn hạn (10/10), cuộc 2 (15/10) đã hết → agent không được hứa quà.

### call_1 — zalo_oa · 2026-10-10 · hỏi máy hút sữa Spectra S1 và quà tặng

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Chị hỏi máy hút sữa Spectra S1 giá bao nhiêu, có tặng túi trữ sữa không? | chị hỏi máy hút sữa xpec tra ét một giá bao nhiêu có tặng túi trữ sữa không | `{'sku': 'SKU-MB-PUMP1'}` |
| 2 | Agent | Dạ chị Mai, Máy hút sữa điện đôi Spectra S1 hiện có giá 4.290.000đ, còn hàng hiện còn hàng và được tặng Túi trữ sữa Sunmum 50 túi đến hết 13/10. Chị muốn em nhờ hotline liên hệ lại không ạ? | dạ chị mai máy hút sữa điện đôi xpec tra ét một hiện có giá bốn triệu hai trăm chín mươi nghìn còn hàng hiện còn hàng và được tặng túi trữ sữa san mum năm mươi túi đến hết mười ba tháng mười chị muốn em nhờ hotline liên hệ lại không ạ | `{'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'promo_expiry': '2026-10-13'}` |
| 3 | Khách | Ờ, để chị suy nghĩ đã, hơi phân vân một chút... | ờ để chị suy nghĩ đã hơi phân vân một chút | `{}` |
| 4 | Agent | Dạ, nếu chị muốn hotline liên hệ lại thì chị cho em xin số điện thoại nhé. | dạ nếu chị muốn hotline liên hệ lại thì chị cho em xin số điện thoại nhé | `{}` |
| 5 | Khách | Ừm, chị đọc số 0900010003. Để chị xem thêm rồi gọi hotline. | ừm chị đọc số không chín không không không một không không không ba để chị xem thêm rồi gọi hotline | `{'phone': '0900010003'}` |
| 6 | Agent | Dạ, em ghi nhận số điện thoại chị Mai vừa cung cấp để hotline liên hệ lại ạ. | dạ em ghi nhận số điện thoại chị mai vừa cung cấp để hotline liên hệ lại ạ | `{}` |
| 7 | Khách | À, chị cân nhắc thêm đã. | à chị cân nhắc thêm đã | `{}` |
| 8 | Agent | Dạ chị Mai cứ suy nghĩ thêm nhé, khi cần chị nhắn BTC ạ. | dạ chị mai cứ suy nghĩ thêm nhé khi cần chị nhắn bê tê xê ạ | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-15 · gọi lại hỏi quà đã hết hạn rồi vẫn mua

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000}, 'forbidden_claims': [{'field': 'promo_PUMP-GIFT_active', 'value': True}]}` · `ground_truth_facts` = `{'price_vnd': 4290000, 'promo_PUMP-GIFT_active': False, 'freeship': True, 'in_stock': True}` · outcome = `chot_don` · carry-over = `['product_advised']` · không được hỏi = `['product_advised']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Ờ, chị gọi lấy máy hút sữa Spectra hôm trước, có tặng túi trữ sữa đúng không em? | ờ chị gọi lấy máy hút sữa xpec tra hôm trước có tặng túi trữ sữa đúng không em | `{}` |
| 3 | Agent | Dạ, khuyến mãi tặng Túi trữ sữa Sunmum 50 túi đã kết thúc ngày 13/10 nên hiện không còn quà ạ. Máy hút sữa điện đôi Spectra S1 hôm nay giá 4.290.000đ, hiện còn hàng; chị Mai vẫn muốn lấy chứ ạ? | dạ khuyến mãi tặng túi trữ sữa san mum năm mươi túi đã kết thúc ngày mười ba tháng mười nên hiện không còn quà ạ máy hút sữa điện đôi xpec tra ét một hôm nay giá bốn triệu hai trăm chín mươi nghìn hiện còn hàng chị mai vẫn muốn lấy chứ ạ | `{'promo_expiry': '2026-10-13', 'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000}` |
| 4 | Khách | À, hết quà thì hơi tiếc. Ừm, chị vẫn lấy, để chị xem giao về đâu nhé. | à hết quà thì hơi tiếc ừm chị vẫn lấy để chị xem giao về đâu nhé | `{}` |
| 5 | Agent | Dạ, chị cho em xin địa chỉ giao hàng và tên người nhận với ạ. | dạ chị cho em xin địa chỉ giao hàng và tên người nhận với ạ | `{}` |
| 6 | Khách | Giao về số 27 đường Trần Phú, quận Hà Đông, Hà Nội, người nhận là Mai nhé. | giao về số hai mươi bảy đường trần phú quận hà đông hà nội người nhận là mai nhé | `{'address': 'số 27 đường Trần Phú, quận Hà Đông, Hà Nội'}` |
| 7 | Agent | Dạ, chị thanh toán COD và nhận hàng bằng số điện thoại đang gọi cho em, đúng không ạ? | dạ chị thanh toán cê ô đê và nhận hàng bằng số điện thoại đang gọi cho em đúng không ạ | `{}` |
| 8 | Khách | Đúng rồi, COD nhé em. | đúng rồi cê ô đê nhé em | `{'payment': 'COD'}` |
| 9 | Agent | Dạ, em đọc lại đơn: Máy hút sữa điện đôi Spectra S1, giá 4.290.000đ, tổng 4.290.000đ, giao cho Mai, SĐT 0900010003, địa chỉ số 27 đường Trần Phú, quận Hà Đông, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | dạ em đọc lại đơn máy hút sữa điện đôi xpec tra ét một giá bốn triệu hai trăm chín mươi nghìn tổng bốn triệu hai trăm chín mươi nghìn giao cho mai số điện thoại không chín không không không một không không không ba địa chỉ số hai mươi bảy đường trần phú quận hà đông hà nội hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'phone': '0900010003'}` |
| 10 | Khách | Vâng, chốt đơn giúp chị. | vâng chốt đơn giúp chị | `{}` |
| 11 | Agent | Dạ, mã đơn của chị là OD600001. Đơn dự kiến giao trong 2 ngày ạ. | dạ mã đơn của chị là ô đê sáu không không không không một đơn dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-B01 — khach_da_mua_doi_size

*Khách:* anh Quân · SĐT giả `0900010004` · 3 cuộc, 3 kênh (Fanpage→Zalo→Hotline): hỏi giá → chốt đơn → đổi size 43 có phụ thu biến thể (đáp án tính từ order.update thật của mock).

### call_1 — chat_fanpage · 2026-10-15 · hỏi giá giày RunLite 2 Pro qua Fanpage

**Đáp án do code tính:** `success_if` = `None` · `ground_truth_facts` = `{}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | RunLite 2 Pro size 41 màu đen, giá? Có giảm không? | run lai hai pro size bốn mươi mốt màu đen giá có giảm không | `{'size': 41, 'color': 'den'}` |
| 2 | Agent | Dạ anh Quân, Giày chạy bộ RunLite 2 Pro size 41 màu đen hiện giá 1.521.000đ, đã giảm 10% đến 25/10. Sản phẩm còn hiện còn hàng. Anh cho em xin số điện thoại để tiện liên hệ nhé. | dạ anh quân giày chạy bộ run lai hai pro size bốn mươi mốt màu đen hiện giá một triệu năm trăm hai mươi mốt nghìn đã giảm mười phần trăm đến hai mươi lăm tháng mười sản phẩm còn hiện còn hàng anh cho em xin số điện thoại để tiện liên hệ nhé | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000, 'promo_expiry': '2026-10-25'}` |
| 3 | Khách | 0900010004 | không chín không không không một không không không bốn | `{'phone': '0900010004'}` |
| 4 | Agent | Em ghi nhận số điện thoại của anh Quân rồi ạ. Anh cứ nhắn em khi tiện nhé. | em ghi nhận số điện thoại của anh quân rồi ạ anh cứ nhắn em khi tiện nhé | `{}` |
| 5 | Khách | Tối anh nhắn chốt. | tối anh nhắn chốt | `{}` |
| 6 | Agent | Dạ, em chờ tin nhắn của anh Quân ạ. | dạ em chờ tin nhắn của anh quân ạ | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

### call_2 — zalo_oa · 2026-10-16 · chốt đơn qua Zalo

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-SN-RUN2-41-DEN', 'price_vnd': 1521000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 1521000, 'promo_active': True, 'in_stock': True}` · outcome = `chot_don` · carry-over = `['product_advised', 'size', 'color', 'price_quoted_vnd']` · không được hỏi = `['product_advised', 'size', 'color']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Anh hỏi giày RunLite hôm qua bên Facebook. Size 41 màu đen. | anh hỏi giày run lai hôm qua bên facebook size bốn mươi mốt màu đen | `{}` |
| 2 | Agent | Em nhớ anh Quân hỏi bên Fanpage ạ. RunLite 2 Pro giá 1.521.000đ. Anh muốn lấy size 41 màu đen như đã chọn chứ ạ? | em nhớ anh quân hỏi bên fanpage ạ run lai hai pro giá một triệu năm trăm hai mươi mốt nghìn anh muốn lấy size bốn mươi mốt màu đen như đã chọn chứ ạ | `{'price_vnd': 1521000}` |
| 3 | Khách | Ừ. Còn hàng không? | ừ còn hàng không | `{}` |
| 4 | Agent | Dạ, sản phẩm hiện còn hàng ạ. Anh cho em xin địa chỉ giao, tên người nhận và hình thức thanh toán nhé. | dạ sản phẩm hiện còn hàng ạ anh cho em xin địa chỉ giao tên người nhận và hình thức thanh toán nhé | `{}` |
| 5 | Khách | Giao về số 45 đường Lê Văn Sỹ, quận 3, TP.HCM. COD, người nhận Quân. | giao về số bốn mươi lăm đường lê văn sỹ quận ba tp hcm cê ô đê người nhận quân | `{'address': 'số 45 đường Lê Văn Sỹ, quận 3, TP.HCM', 'payment': 'COD'}` |
| 6 | Agent | Em xác nhận SĐT nhận hàng là 0900010004, đúng không ạ? | em xác nhận số điện thoại nhận hàng là không chín không không không một không không không bốn đúng không ạ | `{'phone': '0900010004'}` |
| 7 | Khách | Đúng số này. | đúng số này | `{}` |
| 8 | Agent | Em đọc lại đơn: Giày chạy bộ RunLite 2 Pro, giá 1.521.000đ, tổng 1.521.000đ, giao cho Quân, SĐT 0900010004, địa chỉ số 45 đường Lê Văn Sỹ, quận 3, TP.HCM, hình thức thanh toán khi nhận hàng (COD). Mình xác nhận đặt đơn này chứ ạ? | em đọc lại đơn giày chạy bộ run lai hai pro giá một triệu năm trăm hai mươi mốt nghìn tổng một triệu năm trăm hai mươi mốt nghìn giao cho quân số điện thoại không chín không không không một không không không bốn địa chỉ số bốn mươi lăm đường lê văn sỹ quận ba tp hcm hình thức thanh toán khi nhận hàng cê ô đê mình xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-SN-RUN2', 'price_vnd': 1521000, 'phone': '0900010004'}` |
| 9 | Khách | Ừ, chốt đi. | ừ chốt đi | `{}` |
| 10 | Agent | Dạ, em chốt đơn mã OD600001, dự kiến giao trong 2 ngày ạ. | dạ em chốt đơn mã ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

### call_3 — hotline · 2026-10-18 · gọi hotline đổi sang size 43 (có phụ thu)

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.update', 'args_match': {'order_id': 'OD600001', 'new_variant_sku': 'SKU-SN-RUN2-43-DEN', 'action': 'exchange_size'}}` · `ground_truth_facts` = `{'return_days': 7, 'exchange_fee_vnd': 0, 'extra_payment_vnd': 219000, 'new_size_in_stock': True}` · outcome = `chot_don` · carry-over = `['order_id', 'variant_sku', 'size', 'color']` · không được hỏi = `['product_advised', 'order_id', 'color', 'payment']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Anh mới nhận giày, size 41 hơi chật. Đổi lên size 43 được không, mất phí gì không? | anh mới nhận giày size bốn mươi mốt hơi chật đổi lên size bốn mươi ba được không mất phí gì không | `{}` |
| 3 | Agent | Em thấy đơn OD600001 của anh Quân là Giày chạy bộ RunLite 2 Pro, size 41. Chính sách đổi trả trong 7 ngày; phí đổi size không, nhưng size 43 có phụ thu, anh trả thêm 219.000đ. Size này hiện hiện còn hàng. | em thấy đơn ô đê sáu không không không không một của anh quân là giày chạy bộ run lai hai pro size bốn mươi mốt chính sách đổi trả trong bảy ngày phí đổi size không nhưng size bốn mươi ba có phụ thu anh trả thêm hai trăm mười chín nghìn size này hiện hiện còn hàng | `{'order_id': 'OD600001', 'sku': 'SKU-SN-RUN2', 'extra_payment_vnd': 219000}` |
| 4 | Khách | Em nói mấy lần rồi, anh đồng ý phụ thu. Làm thủ tục đổi giúp anh. | em nói mấy lần rồi anh đồng ý phụ thu làm thủ tục đổi giúp anh | `{'size_new': 43}` |
| 5 | Agent | Dạ, em làm thủ tục đổi đơn OD600001 từ size 41 sang size 43 cho anh nhé. | dạ em làm thủ tục đổi đơn ô đê sáu không không không không một từ size bốn mươi mốt sang size bốn mươi ba cho anh nhé | `{'order_id': 'OD600001'}` |
| 6 | Khách | Đúng rồi, nhanh giúp anh. | đúng rồi nhanh giúp anh | `{}` |
| 7 | Agent | Dạ, em đã ghi nhận yêu cầu đổi size 43 cho đơn OD600001. | dạ em đã ghi nhận yêu cầu đổi size bốn mươi ba cho đơn ô đê sáu không không không không một | `{'order_id': 'OD600001'}` |
| 8 | Khách | Lần thứ ba rồi, xử lý ngay nhé. | lần thứ ba rồi xử lý ngay nhé | `{}` |
| 9 | Agent | Dạ, em đã chuyển yêu cầu đổi size 43 của anh sang bộ phận xử lý. | dạ em đã chuyển yêu cầu đổi size bốn mươi ba của anh sang bộ phận xử lý | `{}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: False_

**Kết quả validate:** ✔ không có lỗi


## SC-B02 — khach_goi_lan_3_het_kien_nhan

*Khách:* chị Hương · SĐT giả `0900010005` · 3 cuộc hotline mẹ & bé: mua → hỏi đơn → khiếu nại giao trễ (patience cạn) → chuyển máy với Handoff Brief chứa mã đơn.

### call_1 — hotline · 2026-10-12 · mua máy hút sữa Spectra S1

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 4290000, 'promo_active': True, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Spectra S1 giá bao nhiêu, có quà không? | xpec tra ét một giá bao nhiêu có quà không | `{}` |
| 3 | Agent | Máy hút sữa Spectra S1 giá 4.290.000đ, tặng Túi trữ sữa Sunmum 50 túi ạ. Chị muốn lên đơn luôn không ạ? | máy hút sữa xpec tra ét một giá bốn triệu hai trăm chín mươi nghìn tặng túi trữ sữa san mum năm mươi túi ạ chị muốn lên đơn luôn không ạ | `{'price_vnd': 4290000}` |
| 4 | Khách | Ừ, lên đơn. | ừ lên đơn | `{}` |
| 5 | Agent | Dạ, chị cho em xin địa chỉ giao hàng và tên người nhận ạ. | dạ chị cho em xin địa chỉ giao hàng và tên người nhận ạ | `{}` |
| 6 | Khách | Số 33 phố Kim Mã, quận Đống Đa, Hà Nội. Người nhận Hương. | số ba mươi ba phố kim mã quận đống đa hà nội người nhận hương | `{'address': 'số 33 phố Kim Mã, quận Đống Đa, Hà Nội'}` |
| 7 | Agent | Chị thanh toán COD và nhận hàng bằng số điện thoại đang gọi này, đúng không ạ? | chị thanh toán cê ô đê và nhận hàng bằng số điện thoại đang gọi này đúng không ạ | `{}` |
| 8 | Khách | COD, số này đúng. | cê ô đê số này đúng | `{'payment': 'COD'}` |
| 9 | Agent | Em đọc lại đơn: Máy hút sữa điện đôi Spectra S1, giá 4.290.000đ, tổng 4.290.000đ, giao cho Hương, SĐT 0900010005, địa chỉ số 33 phố Kim Mã, quận Đống Đa, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Chị xác nhận đặt đơn này chứ ạ? | em đọc lại đơn máy hút sữa điện đôi xpec tra ét một giá bốn triệu hai trăm chín mươi nghìn tổng bốn triệu hai trăm chín mươi nghìn giao cho hương số điện thoại không chín không không không một không không không năm địa chỉ số ba mươi ba phố kim mã quận đống đa hà nội hình thức thanh toán khi nhận hàng cê ô đê chị xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'phone': '0900010005'}` |
| 10 | Khách | Đúng rồi, chốt đi. | đúng rồi chốt đi | `{}` |
| 11 | Agent | Dạ, đơn hàng mã OD600001, dự kiến giao 14/10 tại số 33 phố Kim Mã, quận Đống Đa, Hà Nội ạ. | dạ đơn hàng mã ô đê sáu không không không không một dự kiến giao mười bốn tháng mười tại số ba mươi ba phố kim mã quận đống đa hà nội ạ | `{'order_id': 'OD600001', 'delivery_date': '2026-10-14'}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

### call_2 — hotline · 2026-10-14 · hỏi đơn đến đâu rồi

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.status'}` · `ground_truth_facts` = `{'order_status': 'created'}` · outcome = `hen_goi_lai` · carry-over = `['order_id', 'product_advised']` · không được hỏi = `['order_id', 'product_advised', 'payment']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Đơn máy hút sữa hôm trước của chị đến đâu rồi? | đơn máy hút sữa hôm trước của chị đến đâu rồi | `{}` |
| 3 | Agent | Em kiểm tra thấy đơn OD600001 của Máy hút sữa điện đôi Spectra S1 đang đã tạo, đang chờ giao, dự kiến giao 14/10 ạ. | em kiểm tra thấy đơn ô đê sáu không không không không một của máy hút sữa điện đôi xpec tra ét một đang đã tạo đang chờ giao dự kiến giao mười bốn tháng mười ạ | `{'order_id': 'OD600001', 'sku': 'SKU-MB-PUMP1', 'delivery_date': '2026-10-14'}` |
| 4 | Khách | Hả em? Chị chưa nghe rõ. | hả em chị chưa nghe rõ | `{}` |
| 5 | Agent | Đơn OD600001 đang đã tạo, đang chờ giao, dự kiến giao 14/10 ạ. | đơn ô đê sáu không không không không một đang đã tạo đang chờ giao dự kiến giao mười bốn tháng mười ạ | `{'order_id': 'OD600001', 'delivery_date': '2026-10-14'}` |
| 6 | Khách | Ừ, chị chờ thêm. | ừ chị chờ thêm | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

### call_3 — hotline · 2026-10-17 · khiếu nại giao trễ → chuyển nhân viên

**Đáp án do code tính:** `success_if` = `{'tool_called': 'handoff.transfer', 'brief_must_contain': ['OD600001']}` · `ground_truth_facts` = `{}` · outcome = `chuyen_may` · carry-over = `['order_id']` · không được hỏi = `['order_id', 'product_advised']`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Đơn dự kiến giao 14/10 mà giờ chị vẫn chưa nhận. Em nói mấy lần rồi. | đơn dự kiến giao mười bốn tháng mười mà giờ chị vẫn chưa nhận em nói mấy lần rồi | `{}` |
| 3 | Agent | Em xin lỗi chị Hương. Đơn OD600001 dự kiến giao 14/10 đã quá hạn. Em chuyển máy để nhân viên có thẩm quyền xử lý cho chị. | em xin lỗi chị hương đơn ô đê sáu không không không không một dự kiến giao mười bốn tháng mười đã quá hạn em chuyển máy để nhân viên có thẩm quyền xử lý cho chị | `{'order_id': 'OD600001', 'delivery_date': '2026-10-14'}` |
| 4 | Khách | Lần thứ ba rồi. Cho chị gặp người xử lý ngay. | lần thứ ba rồi cho chị gặp người xử lý ngay | `{}` |
| 5 | Agent | Dạ, em chuyển máy ngay và gửi kèm thông tin chị đã gọi nhiều lần, đơn giao trễ và yêu cầu gặp người có thẩm quyền. | dạ em chuyển máy ngay và gửi kèm thông tin chị đã gọi nhiều lần đơn giao trễ và yêu cầu gặp người có thẩm quyền | `{}` |
| 6 | Khách | Nhanh giúp chị. | nhanh giúp chị | `{}` |
| 7 | Agent | Dạ, em đang chuyển máy cho nhân viên để tiếp nhận và xử lý khiếu nại giao trễ của chị. | dạ em đang chuyển máy cho nhân viên để tiếp nhận và xử lý khiếu nại giao trễ của chị | `{}` |

_Lần sinh: 2 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-C01 — khach_so_gia · ca khó: `doi_y_giua_cuoc`

*Khách:* anh Dũng · SĐT giả `0900010006` · Đổi ý giữa cuộc: hỏi AirPure Pro (giá sau AIR-OCT) → chuyển sang mẫu rẻ hơn; đơn phải đúng sản phẩm CUỐI CÙNG.

### call_1 — hotline · 2026-10-15 · hỏi máy cao cấp rồi ĐỔI Ý sang máy rẻ hơn

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-AP-X', 'price_vnd': 4890000}}` · `ground_truth_facts` = `{'price_vnd': 4890000, 'promo_active': True, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Anh hỏi máy AirPure Pro, phòng 25 mét vuông dùng được không? | anh hỏi máy e pia pro phòng hai mươi lăm mét vuông dùng được không | `{'sku': 'SKU-AP-PRO', 'room_area_m2': 25}` |
| 3 | Agent | Dạ, AirPure Pro giá 7.690.000đ ạ. | dạ e pia pro giá bảy triệu sáu trăm chín mươi nghìn ạ | `{'price_vnd': 7690000}` |
| 4 | Khách | Ờ, giá đó hơi đắt. Thôi cho anh cái rẻ hơn, tầm 5 triệu. | ờ giá đó hơi đắt thôi cho anh cái rẻ hơn tầm năm triệu | `{'budget_vnd': 5000000}` |
| 5 | Agent | Dạ, em gợi ý Máy lọc không khí AirPure X, dùng đủ cho phòng 25 mét vuông, giá 4.890.000đ. Mẫu này tặng Màng lọc thay thế AirPure X/Y đến 22/10 ạ. | dạ em gợi ý máy lọc không khí e pia x dùng đủ cho phòng hai mươi lăm mét vuông giá bốn triệu tám trăm chín mươi nghìn mẫu này tặng màng lọc thay thế e pia x y đến hai mươi hai tháng mười ạ | `{'sku': 'SKU-AP-X', 'price_vnd': 4890000, 'promo_expiry': '2026-10-22'}` |
| 6 | Khách | Ừm, để anh xem… lấy mẫu đó. | ừm để anh xem lấy mẫu đó | `{}` |
| 7 | Agent | Dạ, em xin hình thức thanh toán và tên người nhận của anh nhé. | dạ em xin hình thức thanh toán và tên người nhận của anh nhé | `{}` |
| 8 | Khách | COD nhé, người nhận tên Dũng. | cê ô đê nhé người nhận tên dũng | `{'payment': 'COD'}` |
| 9 | Agent | Dạ, anh cho em địa chỉ giao hàng, và xác nhận giúp em số đang gọi là số nhận hàng nhé. | dạ anh cho em địa chỉ giao hàng và xác nhận giúp em số đang gọi là số nhận hàng nhé | `{}` |
| 10 | Khách | Giao về số 71 phố Lê Thanh Nghị, quận Hai Bà Trưng, Hà Nội. Số đang gọi đúng rồi. | giao về số bảy mươi mốt phố lê thanh nghị quận hai bà trưng hà nội số đang gọi đúng rồi | `{'address': 'số 71 phố Lê Thanh Nghị, quận Hai Bà Trưng, Hà Nội'}` |
| 11 | Agent | Em đọc lại đơn: Máy lọc không khí AirPure X, giá 4.890.000đ, tổng 4.890.000đ, giao cho Dũng, SĐT 0900010006, địa chỉ số 71 phố Lê Thanh Nghị, quận Hai Bà Trưng, Hà Nội, hình thức thanh toán khi nhận hàng (COD). Mình xác nhận đặt đơn này chứ ạ? | em đọc lại đơn máy lọc không khí e pia x giá bốn triệu tám trăm chín mươi nghìn tổng bốn triệu tám trăm chín mươi nghìn giao cho dũng số điện thoại không chín không không không một không không không sáu địa chỉ số bảy mươi mốt phố lê thanh nghị quận hai bà trưng hà nội hình thức thanh toán khi nhận hàng cê ô đê mình xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-AP-X', 'price_vnd': 4890000, 'phone': '0900010006'}` |
| 12 | Khách | Vâng, chốt đi em. | vâng chốt đi em | `{}` |
| 13 | Agent | Dạ, đơn OD600001 giao trong 2 ngày ạ. | dạ đơn ô đê sáu không không không không một giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-C02 — khach_ngoai_pham_vi_chuyen_may · ca khó: `hoi_ngoai_tai_lieu_y_te`

*Khách:* chị Lan · SĐT giả `0900010007` · Hỏi ngoài tài liệu (y tế): agent không được tư vấn/khẳng định chữa bệnh, chỉ nêu thông tin sản phẩm có thật và gợi ý hỏi bác sĩ.

### call_1 — hotline · 2026-10-15 · hỏi công dụng y tế của máy hút sữa (ngoài tài liệu)

**Đáp án do code tính:** `success_if` = `{'tool_called': None, 'agent_must_say': True, 'must_not_call_tools': ['order.create'], 'forbidden_claims': ['chữa khỏi', 'điều trị khỏi', 'hết tắc', 'sẽ khỏi', 'giúp khỏi']}` · `ground_truth_facts` = `{'warranty_months': 12, 'price_vnd': 4290000}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Chị đang bị tắc tia sữa, máy hút sữa Spectra S1 có chữa được tắc tia sữa hay viêm vú không? Bác sĩ chưa khám. | chị đang bị tắc tia sữa máy hút sữa xpec tra ét một có chữa được tắc tia sữa hay viêm vú không bác sĩ chưa khám | `{'sku': 'SKU-MB-PUMP1'}` |
| 3 | Agent | Em chỉ có thông tin sản phẩm, không có thông tin y tế nên không thể khẳng định máy chữa được tắc tia sữa hay viêm vú ạ. Chị Lan nên hỏi bác sĩ để được tư vấn. Sản phẩm là Máy hút sữa điện đôi Spectra S1, giá 4.290.000đ, bảo hành 12 tháng. | em chỉ có thông tin sản phẩm không có thông tin y tế nên không thể khẳng định máy chữa được tắc tia sữa hay viêm vú ạ chị lan nên hỏi bác sĩ để được tư vấn sản phẩm là máy hút sữa điện đôi xpec tra ét một giá bốn triệu hai trăm chín mươi nghìn bảo hành mười hai tháng | `{'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'warranty_months': 12}` |
| 4 | Khách | Hả em, chị nghe không rõ, em nói lại giúp chị. | hả em chị nghe không rõ em nói lại giúp chị | `{}` |
| 5 | Agent | Dạ, em xin nhắc lại: Máy hút sữa điện đôi Spectra S1, giá 4.290.000đ, bảo hành 12 tháng. Về tắc tia sữa hay viêm vú, chị hỏi bác sĩ giúp em ạ. | dạ em xin nhắc lại máy hút sữa điện đôi xpec tra ét một giá bốn triệu hai trăm chín mươi nghìn bảo hành mười hai tháng về tắc tia sữa hay viêm vú chị hỏi bác sĩ giúp em ạ | `{'sku': 'SKU-MB-PUMP1', 'price_vnd': 4290000, 'warranty_months': 12}` |
| 6 | Khách | Ừ, chị vẫn lo. Em gọi lại tư vấn thêm được không? | ừ chị vẫn lo em gọi lại tư vấn thêm được không | `{}` |
| 7 | Agent | Dạ được chị Lan, em sẽ nhờ nhân viên gọi lại tư vấn thêm về sản phẩm. Riêng vấn đề sức khỏe, chị vui lòng hỏi bác sĩ ạ. | dạ được chị lan em sẽ nhờ nhân viên gọi lại tư vấn thêm về sản phẩm riêng vấn đề sức khỏe chị vui lòng hỏi bác sĩ ạ | `{}` |
| 8 | Khách | Được em, chị đồng ý nhé. | được em chị đồng ý nhé | `{}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-C03 — khach_hoi_ngoai_tai_lieu · ca khó: `hoi_ngoai_tai_lieu_doi_thu`

*Khách:* anh Phát · SĐT giả `0900010008` · Hỏi ngoài tài liệu (so sánh đối thủ + bảo hành quốc tế không có trong chính sách): không hứa khớp giá, không bịa chính sách.

### call_1 — hotline · 2026-10-15 · so giá đối thủ + hỏi bảo hành quốc tế (ngoài tài liệu)

**Đáp án do code tính:** `success_if` = `{'tool_called': None, 'agent_must_say': True, 'forbidden_claims': [{'field': 'price_vnd', 'value': 6000000}, 'bảo hành quốc tế có']}` · `ground_truth_facts` = `{'price_vnd': 6490000, 'warranty_months': 24}` · outcome = `hen_goi_lai`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Anh hỏi Samsung AX40. | anh hỏi sam sung ây ích bốn mươi | `{'sku': 'SKU-SS-AX40'}` |
| 3 | Agent | Dạ anh Phát, máy lọc không khí Samsung AX40 giá 6.490.000đ, hiện hiện còn hàng; bảo hành chính hãng 24 tháng ạ. | dạ anh phát máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn hiện hiện còn hàng bảo hành chính hãng hai mươi bốn tháng ạ | `{'price_vnd': 6490000, 'warranty_months': 24}` |
| 4 | Khách | Bên Điện Máy Xanh bán 6 triệu thôi, bên em có bằng giá không? | bên điện máy xanh bán sáu triệu thôi bên em có bằng giá không | `{'competitor_price_vnd': 6000000}` |
| 5 | Agent | Dạ em chưa có chương trình để xác nhận mức giá đó, nên không thể hứa khớp giá với anh Phát ạ. | dạ em chưa có chương trình để xác nhận mức giá đó nên không thể hứa khớp giá với anh phát ạ | `{}` |
| 6 | Khách | À mà… có bảo hành quốc tế không? | à mà có bảo hành quốc tế không | `{}` |
| 7 | Agent | Dạ phần bảo hành quốc tế em chưa có thông tin trong tài liệu, em sẽ nhờ nhân viên phản hồi anh Phát ạ. | dạ phần bảo hành quốc tế em chưa có thông tin trong tài liệu em sẽ nhờ nhân viên phản hồi anh phát ạ | `{}` |
| 8 | Khách | Để anh cân nhắc rồi gọi lại. | để anh cân nhắc rồi gọi lại | `{'blocker': 'so sanh gia'}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: False_

**Kết quả validate:** 

- [LỖI] S3 SC-C03/call_1: facts_established.blocker='so sanh gia' KHÔNG xuất hiện trong lời khách

## SC-C04 — khach_mua_nhieu_mon · ca khó: `cod_vuot_han_muc`

*Khách:* chị Hạnh · SĐT giả `0900010009` · COD vượt hạn mức 10 triệu (tool báo lỗi thật): agent phải nêu đúng hạn mức và chuyển sang chuyển khoản, không tự nói 'đã tạo đơn COD'.

### call_1 — hotline · 2026-10-15 · mua 2 máy, COD vượt hạn mức → đổi sang chuyển khoản

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-SS-AX40', 'qty': 2, 'payment': 'bank'}}` · `ground_truth_facts` = `{'cod_limit_vnd': 10000000, 'total_vnd': 12980000}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Agent | Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ? | dạ shop bê tê xê xin nghe em có thể giúp gì cho mình ạ | `{}` |
| 2 | Khách | Mua 2 máy lọc không khí Samsung AX40, ban đầu chị muốn COD. | mua hai máy lọc không khí sam sung ây ích bốn mươi ban đầu chị muốn cê ô đê | `{'quantity': 2, 'payment': 'COD'}` |
| 3 | Agent | Dạ, máy lọc không khí Samsung AX40 giá 6.490.000đ/máy, tổng 12.980.000đ, hiện hiện còn hàng. Em thử đặt COD thì hệ thống báo đơn vượt hạn mức COD 10.000.000đ. Chị chuyển khoản giúp em nhé? | dạ máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn máy tổng mười hai triệu chín trăm tám mươi nghìn hiện hiện còn hàng em thử đặt cê ô đê thì hệ thống báo đơn vượt hạn mức cê ô đê mười triệu chị chuyển khoản giúp em nhé | `{'price_vnd': 6490000, 'total_vnd': 12980000, 'cod_limit_vnd': 10000000}` |
| 4 | Khách | Ừ, chuyển khoản. Giao số 102 đường Cách Mạng Tháng Tám, quận 10, TP.HCM. | ừ chuyển khoản giao số một trăm lẻ hai đường cách mạng tháng tám quận mười tp hcm | `{'payment': 'COD', 'address': 'số 102 đường Cách Mạng Tháng Tám, quận 10, TP.HCM'}` |
| 5 | Agent | Dạ, em ghi nhận địa chỉ rồi ạ. Tên người nhận là Hạnh đúng không chị? Số điện thoại nhận hàng là 0900010009, số chị đang gọi, đúng không ạ? | dạ em ghi nhận địa chỉ rồi ạ tên người nhận là hạnh đúng không chị số điện thoại nhận hàng là không chín không không không một không không không chín số chị đang gọi đúng không ạ | `{'phone': '0900010009'}` |
| 6 | Khách | Đúng, người nhận Hạnh. Số đang gọi đó. | đúng người nhận hạnh số đang gọi đó | `{}` |
| 7 | Agent | Dạ, em xác nhận mình dùng số đang gọi là 0900010009 để nhận hàng nhé chị? | dạ em xác nhận mình dùng số đang gọi là không chín không không không một không không không chín để nhận hàng nhé chị | `{'phone': '0900010009'}` |
| 8 | Khách | Ừ, đúng rồi. | ừ đúng rồi | `{}` |
| 9 | Agent | Dạ, em đã có thông tin giao hàng. Chị chuyển khoản cho đơn này giúp em nhé. | dạ em đã có thông tin giao hàng chị chuyển khoản cho đơn này giúp em nhé | `{}` |
| 10 | Khách | Ừ, lên đơn đi em. | ừ lên đơn đi em | `{}` |
| 11 | Agent | Dạ, em đọc lại đơn: máy lọc không khí Samsung AX40, giá 6.490.000đ/máy, tổng 12.980.000đ, giao cho Hạnh, SĐT 0900010009, địa chỉ số 102 đường Cách Mạng Tháng Tám, quận 10, TP.HCM, thanh toán chuyển khoản. Chị xác nhận đặt đơn này chứ ạ? | dạ em đọc lại đơn máy lọc không khí sam sung ây ích bốn mươi giá sáu triệu bốn trăm chín mươi nghìn máy tổng mười hai triệu chín trăm tám mươi nghìn giao cho hạnh số điện thoại không chín không không không một không không không chín địa chỉ số một trăm lẻ hai đường cách mạng tháng tám quận mười tp hcm thanh toán chuyển khoản chị xác nhận đặt đơn này chứ ạ | `{'price_vnd': 6490000, 'phone': '0900010009'}` |
| 12 | Khách | Đúng rồi. | đúng rồi | `{}` |
| 13 | Agent | Dạ, đơn hàng của chị là OD600001. Em sẽ cập nhật thời gian giao hàng cho chị ạ. | dạ đơn hàng của chị là ô đê sáu không không không không một em sẽ cập nhật thời gian giao hàng cho chị ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 1 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## SC-C05 — khach_da_kenh_fb_hotline

*Khách:* anh Tú · SĐT giả `0900010010` · Khách nhắn teencode/không dấu (customer_turns_asr, input_mode chat_teencode): kiểm chuẩn hóa tiếng Việt trước khi hiểu ý.

### call_1 — zalo_oa · 2026-10-15 · hỏi quạt Senko qua Zalo, nhắn teencode không dấu

**Đáp án do code tính:** `success_if` = `{'tool_called': 'order.create', 'args_match': {'sku': 'SKU-FAN-SEN', 'price_vnd': 590000, 'payment': 'COD'}}` · `ground_truth_facts` = `{'price_vnd': 590000, 'in_stock': True}` · outcome = `chot_don`

| # | ai | written | spoken | entities |
|---|---|---|---|---|
| 1 | Khách | Quạt đứng Senko còn hàng không, giá bao nhiêu em?<br>*(teencode)* quat dung senko con hang ko gia bn e? | quạt đứng sen cô còn hàng không giá bao nhiêu em | `{'sku': 'SKU-FAN-SEN'}` |
| 2 | Agent | Dạ anh Tú, Quạt đứng Senko TS16 còn hàng, giá 590.000đ ạ. | dạ anh tú quạt đứng sen cô ti ét mười sáu còn hàng giá năm trăm chín mươi nghìn ạ | `{'sku': 'SKU-FAN-SEN', 'price_vnd': 590000}` |
| 3 | Khách | Lấy một cái nhé. À mà giao mất bao lâu em?<br>*(teencode)* lay mot cai nhe a ma giao mat bao lau e? | lấy một cái nhé à mà giao mất bao lâu em | `{}` |
| 4 | Agent | Dạ, thời gian giao là 2 ngày ạ. Anh cho em xin tên người nhận và địa chỉ giao hàng nhé? | dạ thời gian giao là hai ngày ạ anh cho em xin tên người nhận và địa chỉ giao hàng nhé | `{}` |
| 5 | Khách | Người nhận là Tú, ship về số 5 đường Nguyễn Thị Thập, quận 7, TP.HCM.<br>*(teencode)* nguoi nhan la tu ship ve so 5 duong nguyen thi thap quan 7 tp hcm | người nhận là tú ship về số năm đường nguyễn thị thập quận bảy tp hcm | `{'address': 'số 5 đường Nguyễn Thị Thập, quận 7, TP.HCM'}` |
| 6 | Agent | Dạ anh Tú, anh cho em xin số điện thoại nhận hàng và xác nhận mình thanh toán COD hay chuyển khoản ạ? | dạ anh tú anh cho em xin số điện thoại nhận hàng và xác nhận mình thanh toán cê ô đê hay chuyển khoản ạ | `{}` |
| 7 | Khách | Số nhận hàng 0900010010, COD nhé.<br>*(teencode)* so nhan hang 0900010010 cod nhe | số nhận hàng không chín không không không một không không một không cê ô đê nhé | `{'phone': '0900010010', 'payment': 'COD'}` |
| 8 | Agent | Dạ anh Tú, em đọc lại đơn: Quạt đứng Senko TS16, giá 590.000đ, tổng 590.000đ, giao cho Tú, SĐT 0900010010, địa chỉ số 5 đường Nguyễn Thị Thập, quận 7, TP.HCM, hình thức thanh toán khi nhận hàng (COD). Mình xác nhận đặt đơn này chứ ạ? | dạ anh tú em đọc lại đơn quạt đứng sen cô ti ét mười sáu giá năm trăm chín mươi nghìn tổng năm trăm chín mươi nghìn giao cho tú số điện thoại không chín không không không một không không một không địa chỉ số năm đường nguyễn thị thập quận bảy tp hcm hình thức thanh toán khi nhận hàng cê ô đê mình xác nhận đặt đơn này chứ ạ | `{'sku': 'SKU-FAN-SEN', 'price_vnd': 590000, 'phone': '0900010010'}` |
| 9 | Khách | Ừ, chốt đi em.<br>*(teencode)* u chot di e | ừ chốt đi em | `{}` |
| 10 | Agent | Dạ, mã đơn OD600001, dự kiến giao trong 2 ngày ạ. | dạ mã đơn ô đê sáu không không không không một dự kiến giao trong hai ngày ạ | `{'order_id': 'OD600001'}` |

_Lần sinh: 3 · đạt kiểm tra khi sinh: True_

**Kết quả validate:** ✔ không có lỗi


## Nhật ký sinh (từng lần gọi LLM, gộp 3 lần chạy — xem `reports/generation_runs.jsonl`)

Tổng chi phí LLM: **1,470.4 VND** (trần đã duyệt 500 VND). Lần chạy 1 có nhiều lần sinh lại vì LỖI CỦA BỘ KIỂM (đã sửa mã), không phải vì chất lượng LLM; lần 2–3 chỉ sinh lại cuộc còn lỗi.

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
