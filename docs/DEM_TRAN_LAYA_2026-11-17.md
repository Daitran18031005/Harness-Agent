# Đếm trần cho bộ quyết định cục bộ (Laya) — 2026-11-17

Giai đoạn C, bước 1. Chỉ offline: đọc log có sẵn, không gọi LLM, không tải model, không sửa code hệ thống.
Script: `scripts/dem_tran_laya.py` (các bảng dưới do script in ra; chạy lại bằng `nlp_env/python.exe scripts/dem_tran_laya.py`).
Dữ liệu: `runs/m1_final7/r*/s[123]` (mốc nộp, 3114 lượt), `runs/ab_rerank_1116/router-a|b` (461), `runs/ab_noshort_1116/*` (941).

## Kết luận: KHÔNG ĐI (Laya không đủ để đạt TTFT p95 < 3 s)

| mức phủ (m1_final7) | TTFT p95 | lượt > 3 s | đạt (≤ 5 %)? |
|---|---|---|---|
| hiện tại | 5,82 s | 32,2 % | không |
| phủ 100 % | 5,37 s | 25,7 % | không |
| phủ 80 % | 5,48 s | 27,0 % | không |
| phủ 60 % | 5,58 s | 28,3 % | không |
| 100 % + bỏ vòng nhắc vô ích | 5,35 s | 24,5 % | không |
| cận dưới lý thuyết: MỌI lượt 0 vòng | 4,08 s | 16,2 % | không |

- Ngay ở trần 100 % vẫn còn 799/3114 lượt > 3 s (25,7 %), cần ≤ 156 (5 %) → **thiếu ~640 lượt**. Kể cả bỏ hết mọi vòng gọi tool của mọi lượt vẫn còn 16,2 %.
- Lý do: chỉ 572/4516 lượt (12,7 %) là tra cứu suy ra được tham số; 27,8 % là lượt GHI (không được tra trước), 48 % đã 0 vòng.
- 799 lượt còn > 3 s ở trần 100 %: thành phần lớn nhất là **chuẩn bị** (366 lượt), các vòng tool không loại bỏ được (291, phần lớn lượt ghi), **thời gian tool** (124 — tra chính sách/reader p95 ~2,4 s), token đầu (18).
  Theo nhãn: ghi 341, khong_tra 145, tra_san_pham 76, nhieu_loai 73, chinh_sach 69, vong_nhac_vo_ich 44, khac 40.
- Bỏ vòng nhắc vô ích một mình chỉ bớt ~1 điểm % (35 lượt).
- Lượt 0 vòng THẬT hiện tại vẫn có 7,6 % > 3 s (p95 3,3 s) — tức phần chuẩn bị + token đầu tự nó đã sát ngưỡng.

**Cần thêm (thay vì Laya):** (1) cắt phần chuẩn bị — p95 2,9 s ở lượt có vòng, 3,4 s ở lượt 0 vòng (là đòn bẩy lớn nhất, đo xem reader/brief/RAG chiếm gì);
(2) câu đệm phát ngay trước vòng tool / lượt ghi (đưa token đầu về ~0,7 s cho 1.257 lượt ghi);
(3) model nhanh hơn cho vòng gọi tool (vòng 1 p50 1,5 s, p95 2,7 s); (4) tăng tốc tool chính sách (search_policy p95 cao).
Không đề xuất bước 2 (tải Laya + ViSoBERT).

## Cách tính / giới hạn

- Nhãn lấy từ tool LLM gọi (bỏ `speculative=True`; chưa có log nào có trường `by`). Lượt có tool ghi → `ghi` dù tool gọi sau token đầu.
  `nhieu_loai` = nhiều loại tra cứu một lượt (Laya chỉ chọn một → không tính). `vong_khong_tool` = có vòng trước token đầu, không tool, không nudged.
- "Suy ra được" tra_san_pham: SKU cha LLM gọi ∈ {SKU đã xuất hiện trong tool call các lượt trước + tra trước lượt này + sản phẩm agent lượt trước nêu tên + sản phẩm khách gọi tên (khớp tên/brand trong products.json)},
  ngữ cảnh ≤ 3 sản phẩm, và biến thể khớp size/màu khách đã nêu. Log không có `_discussed_parents`/`focus`/`_precomp` nên dựng lại từ log → là cận trên hơi lạc quan.
- don_hang: 3 lượt, LLM tra theo mã đơn không có trong lời khách → đếm "không"; không kiểm CRM số đơn (không ảnh hưởng kết luận).
- TTFT mới = chuẩn bị + tool_ms thật + token đầu vòng cuối thật. Phủ 80/60 % = trung bình 200 lần chọn ngẫu nhiên.
- Teencode thấp (1,7 %) — dữ liệu train sẽ lệch về câu sạch.

## 1. Phân rã TTFT (lượt có ≥1 vòng gọi tool trước token đầu)

**m1_final7**: 3114 lượt, 1107 có vòng tool (36%), 2007 không vòng

| phần | p50 ms | p95 ms |
|---|---|---|
| TTFT (lượt có vòng) | 3819 | 6979 |
| chuẩn bị | 410 | 2925 |
| vòng 1 | 1493 | 2740 |
| vòng 2+ (lượt có) | 1199 | 2107 |
| tổng các vòng | 1626 | 3491 |
| tool | 32 | 2456 |
| token đầu vòng cuối | 746 | 1076 |
| TTFT lượt 0 vòng | 1321 | 3577 |
| chuẩn bị lượt 0 vòng | 1076 | 3361 |
| token đầu lượt 0 vòng | 631 | 1010 |
| TTFT tất cả | 2076 | 5818 |

**router_1116**: 461 lượt, 148 có vòng tool (32%), 313 không vòng

| phần | p50 ms | p95 ms |
|---|---|---|
| TTFT (lượt có vòng) | 3488 | 6263 |
| chuẩn bị | 468 | 1536 |
| vòng 1 | 1452 | 2475 |
| vòng 2+ (lượt có) | 1191 | 1936 |
| tổng các vòng | 1674 | 3237 |
| tool | 12 | 2414 |
| token đầu vòng cuối | 758 | 1012 |
| TTFT lượt 0 vòng | 1295 | 2764 |
| chuẩn bị lượt 0 vòng | 547 | 2427 |
| token đầu lượt 0 vòng | 751 | 1056 |
| TTFT tất cả | 1645 | 5103 |

**noshort_1116**: 941 lượt, 293 có vòng tool (31%), 648 không vòng

| phần | p50 ms | p95 ms |
|---|---|---|
| TTFT (lượt có vòng) | 3448 | 6478 |
| chuẩn bị | 370 | 1529 |
| vòng 1 | 1572 | 2858 |
| vòng 2+ (lượt có) | 1260 | 2640 |
| tổng các vòng | 1756 | 3841 |
| tool | 15 | 1860 |
| token đầu vòng cuối | 788 | 1206 |
| TTFT lượt 0 vòng | 1339 | 2925 |
| chuẩn bị lượt 0 vòng | 564 | 2524 |
| token đầu lượt 0 vòng | 788 | 1248 |
| TTFT tất cả | 1738 | 5275 |

**TẤT CẢ**: 4516 lượt, 1548 có vòng tool (34%), 2968 không vòng

| phần | p50 ms | p95 ms |
|---|---|---|
| TTFT (lượt có vòng) | 3691 | 6947 |
| chuẩn bị | 397 | 2653 |
| vòng 1 | 1497 | 2747 |
| vòng 2+ (lượt có) | 1206 | 2277 |
| tổng các vòng | 1656 | 3616 |
| tool | 26 | 2430 |
| token đầu vòng cuối | 756 | 1101 |
| TTFT lượt 0 vòng | 1324 | 3323 |
| chuẩn bị lượt 0 vòng | 936 | 3121 |
| token đầu lượt 0 vòng | 701 | 1067 |
| TTFT tất cả | 1927 | 5664 |

## 2. Nhãn (việc LLM thật sự làm trước khi nói)

| nhãn | số lượt | % | TTFT p50 | TTFT p95 | >3 s | suy ra được |
|---|---|---|---|---|---|---|
| khong_tra | 2185 | 48.4% | 1384 | 3392 | 179 | – |
| ghi | 1257 | 27.8% | 1570 | 6247 | 411 | – |
| tra_san_pham | 493 | 10.9% | 3454 | 6317 | 340 | 421 |
| nhieu_loai | 152 | 3.4% | 3902 | 6209 | 117 | – |
| chinh_sach | 151 | 3.3% | 5020 | 7622 | 141 | 151 |
| vong_nhac_vo_ich | 134 | 3.0% | 2955 | 5483 | 65 | – |
| khac | 126 | 2.8% | 3190 | 6198 | 74 | – |
| vong_khong_tool | 15 | 0.3% | 3329 | 7314 | 12 | – |
| don_hang | 3 | 0.1% | 1833 | 2221 | 0 | 0 |

## 3. Suy ra được tham số?

**tra_san_pham**: suy ra được 421/493, không 72

| loại | ví dụ | kịch bản | lời khách | lý do |
|---|---|---|---|---|
| được | 1 | TEST-93 | Nhận tại số 146 đường Sư Vạn Hạnh, Quận 10, TP.HCM nha em, tên Tiến, có gì bưu tá alo trướ | SKU ['SKU-AF-4L'] ∈ ngữ cảnh ['SKU-AF-4L'] |
| được | 2 | SC-TV-12 | Alo anh Hải đây, nay cậu em bận nên anh đặt riêng một đôi Urban Classic 40 xám thôi, nhớ t | SKU ['SKU-SN-CAS-40-XAM'] ∈ ngữ cảnh ['SKU-SN-CAS'] |
| được | 3 | TEST-15 | Lên đơn cho chị ngay nhé. | SKU ['SKU-AP-X'] ∈ ngữ cảnh ['SKU-AP-X'] |
| được | 4 | TEST-169 | Ghi nháp giúp anh Trung nơi nhận số 138 đường Yersin, Phương Sài, Nha Trang cho chiếc Quạt | SKU ['SKU-FAN-DC1'] ∈ ngữ cảnh ['SKU-FAN-DC1'] |
| được | 5 | SC-GEN-05 | Em ơi giày chạy RunLite 2 Pro màu đen size 40 có hàng không? | SKU ['SKU-SN-RUN2-40-DEN'] ∈ ngữ cảnh ['SKU-SN-RUN2'] |
| được | 6 | TEST-191 | Shop báo giúp Thành giá lăn bánh về Hải Phòng của Bộ lõi lọc thay thế RO 1-2-3 kèm khuyến  | SKU ['SKU-WF-CORE'] ∈ ngữ cảnh ['SKU-WF-CORE'] |
| được | 7 | TEST-107 | Shop check tồn kho giúp mình chiếc Xiaomi Smart 4 Pro nhé, mai giao luôn kịp không? Duy gử | SKU ['SKU-XM-4P'] ∈ ngữ cảnh ['SKU-XM-4P', 'SKU-XM-FLT'] |
| được | 8 | TEST-114 | Thế Hùng rút bớt Combo AirPure Y + 2 màng lọc lại đúng 1 cái 6.390.000đ để nằm dưới hạn mứ | SKU ['SKU-BDL-AIR'] ∈ ngữ cảnh ['SKU-AP-Y', 'SKU-BDL-AIR'] |
| được | 9 | SC-TV-09 | Để chị hỏi xem chồng có thích màu be sáng không rồi ít hôm báo nhé. Trâm để lại số 0900030 | SKU ['SKU-JK-DWN-XL-BE'] ∈ ngữ cảnh ['SKU-JK-DWN'] |
| được | 10 | TEST-210 | Tiến chốt mua Giày trekking HikePro bản 38 trang, đóng gói giao hàng COD về số 200 đường L | SKU ['SKU-SN-TRK-38-TRANG'] ∈ ngữ cảnh ['SKU-SN-TRK'] |
| không | 1 | SC-ULTRA-04 | Giá Medela Swing Maxi 5.018.000 hả em? Để chị hỏi bác sĩ đã nhé. | gọi không có sku: [{"query": "Medela Swing Maxi"}] |
| không | 2 | TEST-85 | chị tên vy hỏi gấp thông số kỹ thuật của màng lọc thay thế xiaomi smart 594.000 đồng phục  | gọi không có sku: [{"query": "màng lọc thay thế xiaomi smart"}] |
| không | 3 | TEST-25 | Em ơi anh muốn lấy chiếc AirPure Mini giá 2.190k cho phòng 30m². | gọi không có sku: [{"query": "AirPure Mini"}] |
| không | 4 | SC-ULTRA-04 | Giá Medela Swing Maxi 5.018.000 hả em? Để chị hỏi bác sĩ đã nhé. | gọi không có sku: [{"query": "Medela Swing Maxi"}] |
| không | 5 | SC-GEN-10 | Em so sánh giúp anh AirPure X, Y, Pro khác nhau thế nào, giá sao? | gọi không có sku: [{"query": "AirPure X"}, {"query": "AirPure Y"}, {"query": "AirPure Pro"}] |
| không | 6 | SC-ULTRA-07 | Combi Sugocal 15kg với Joie Pact 22kg thì xe nào êm cho bé sơ sinh hơn em? | gọi không có sku: [{"query": "Combi Sugocal 15kg"}, {"query": "Joie Pact 22kg"}] |
| không | 7 | SC-ULTRA-04 | Giá Medela Swing Maxi 5.018.000 hả em? Để chị hỏi bác sĩ đã nhé. | gọi không có sku: [{"query": "Medela Swing Maxi"}] |
| không | 8 | TEST-126 | Cho chị Trang hỏi nhanh mẫu Màng lọc thay thế AirPure X/Y, mình chú trọng tự lắp tại nhà k | gọi không có sku: [{"query": "Màng lọc thay thế AirPure X/Y"}] |
| không | 9 | TEST-118 | Bạn Oanh bảo mua hàng nội địa Trung Quốc hoặc thương hiệu ngoài siêu thị rẻ hơn con Nồi ch | gọi không có sku: [{"query": "Nồi chiên không dầu"}] |
| không | 10 | SC-ULTRA-14 | Phòng khách 38m2 nên lấy Samsung AX40 hay chờ Xiaomi Smart 4 Pro đang hết hàng tới 19 mới  | gọi không có sku: [{"query": "Samsung AX40"}, {"query": "Xiaomi Smart 4 Pro"}] |

**don_hang**: suy ra được 0/3, không 3

| loại | ví dụ | kịch bản | lời khách | lý do |
|---|---|---|---|---|
| không | 1 | SC-ULTRA-15 | Chiều nay 4 giờ chị tan làm rồi, xem giúp chị giao hàng tới quận 3 chưa để chị ở lại đợi. | mã đơn OD600001 không có trong ngữ cảnh |
| không | 2 | SC-ULTRA-15 | Chiều nay 4 giờ chị tan làm rồi, xem giúp chị giao hàng tới quận 3 chưa để chị ở lại đợi. | mã đơn OD600001 không có trong ngữ cảnh |
| không | 3 | SC-ULTRA-15 | Chiều nay 4 giờ chị tan làm rồi, xem giúp chị giao hàng tới quận 3 chưa để chị ở lại đợi. | mã đơn OD600001 không có trong ngữ cảnh |

**chinh_sach**: suy ra được 151/151, không 0

| loại | ví dụ | kịch bản | lời khách | lý do |
|---|---|---|---|---|
| được | 1 | TEST-19 | Với lại phí đổi size là 20.000 đồng phải không em? | truy vấn = lời khách |
| được | 2 | TEST-44 | Bên em có gói combo nào giá tốt hơn mua lẻ không em? | truy vấn = lời khách |
| được | 3 | TEST-202 | Cho chị Vy thắc mắc chút về Máy tiệt trùng sấy khô Moaz Bebe: phần bộ ống hút silicone, gi | truy vấn = lời khách |
| được | 4 | SC-GEN-07 | Em ơi cái máy lọc AirPure X chị mới mua được 12 ngày mà tự nhiên bật không lên nguồn nữa. | truy vấn = lời khách |
| được | 5 | SC-GEN-07 | Em ơi cái máy lọc AirPure X chị mới mua được 12 ngày mà tự nhiên bật không lên nguồn nữa. | truy vấn = lời khách |
| được | 6 | SC-GEN-15 | Anh ở quận 1 TP.HCM thì phí giao hàng thế nào em? | truy vấn = lời khách |
| được | 7 | SAMPLE-07 | Thế phí đổi size 20.000 à? | truy vấn = lời khách |
| được | 8 | TEST-161 | Bữa tháng 6 Duy đọc ảnh chụp chính sách của shop bảo Nồi chiên không dầu Lock&Lock 4L đổi  | truy vấn = lời khách |
| được | 9 | TEST-38 | Thế mấy cái phụ kiện như van một chiều với phễu hút có được bảo hành 12 tháng luôn không e | truy vấn = lời khách |
| được | 10 | SAMPLE-07 | Bên em cho đổi trả trong 14 ngày đúng không? Chị đọc trên web thấy thế. | truy vấn = lời khách |

Lý do không suy ra (tra_san_pham): gọi không: 51, ngữ cảnh: 9, SKU ['RUNLITE2PRO-BLACK-43']: 3, SKU ['AirPure: 3, SKU ['SKU-BDL-MOM']: 2, màu den: 1

## 4. Trần TTFT

Lượt suy ra được → 0 vòng: TTFT mới = chuẩn bị + tool tra trước + token đầu vòng cuối. Phủ k % = chọn ngẫu nhiên k % lượt suy ra được (trung bình 200 lần). Vòng nhắc vô ích: bỏ hết các vòng trước.

| bộ | kịch bản | TTFT p95 ms | lượt >3 s | % >3 s | đạt ≤5 %? |
|---|---|---|---|---|---|
| m1_final7 | hiện tại | 5818 | 1004 | 32.2% | không |
| m1_final7 | chỉ bỏ vòng nhắc vô ích | 5780 | 969 | 31.1% | không |
| m1_final7 | phủ 100 % | 5372 | 799 | 25.7% | không |
| m1_final7 | phủ 80 % | 5477 | 840 | 27.0% | không |
| m1_final7 | phủ 60 % | 5578 | 880 | 28.3% | không |
| m1_final7 | phủ 100 % + bỏ nhắc | 5347 | 764 | 24.5% | không |
| m1_final7 | cận dưới: MỌI lượt 0 vòng | 4077 | 505 | 16.2% | không |
| router_1116 | hiện tại | 5103 | 115 | 24.9% | không |
| router_1116 | chỉ bỏ vòng nhắc vô ích | 5048 | 106 | 23.0% | không |
| router_1116 | phủ 100 % | 4646 | 83 | 18.0% | không |
| router_1116 | phủ 80 % | 4728 | 89 | 19.4% | không |
| router_1116 | phủ 60 % | 4802 | 96 | 20.7% | không |
| router_1116 | phủ 100 % + bỏ nhắc | 4644 | 74 | 16.1% | không |
| router_1116 | cận dưới: MỌI lượt 0 vòng | 3306 | 32 | 6.9% | không |
| noshort_1116 | hiện tại | 5275 | 220 | 23.4% | không |
| noshort_1116 | chỉ bỏ vòng nhắc vô ích | 5275 | 208 | 22.1% | không |
| noshort_1116 | phủ 100 % | 4584 | 149 | 15.8% | không |
| noshort_1116 | phủ 80 % | 4681 | 163 | 17.3% | không |
| noshort_1116 | phủ 60 % | 4819 | 178 | 18.9% | không |
| noshort_1116 | phủ 100 % + bỏ nhắc | 4573 | 137 | 14.6% | không |
| noshort_1116 | cận dưới: MỌI lượt 0 vòng | 3204 | 57 | 6.1% | không |
| TẤT CẢ | hiện tại | 5664 | 1339 | 29.7% | không |
| TẤT CẢ | chỉ bỏ vòng nhắc vô ích | 5640 | 1283 | 28.4% | không |
| TẤT CẢ | phủ 100 % | 5219 | 1031 | 22.8% | không |
| TẤT CẢ | phủ 80 % | 5336 | 1092 | 24.2% | không |
| TẤT CẢ | phủ 60 % | 5412 | 1155 | 25.6% | không |
| TẤT CẢ | phủ 100 % + bỏ nhắc | 5181 | 975 | 21.6% | không |
| TẤT CẢ | cận dưới: MỌI lượt 0 vòng | 3966 | 594 | 13.2% | không |

Đối chiếu: TTFT thật lượt 0 vòng p50/p95 = 1324/3323 ms, >3 s 7.6%; TTFT ước tính lượt được chuyển p50/p95 = 1594/4560 ms, >3 s 24.5%.

## 5. Dữ liệu huấn luyện

4516 lượt, 277 kịch bản. Chế độ lời khách: clean: 4380 (97.0%), chat_teencode: 78 (1.7%), asr_transcript: 58 (1.3%)

| nhãn | train | test |
|---|---|---|
| khong_tra | 1634 | 551 |
| ghi | 966 | 291 |
| tra_san_pham | 375 | 118 |
| nhieu_loai | 117 | 35 |
| chinh_sach | 118 | 33 |
| vong_nhac_vo_ich | 98 | 36 |
| khac | 85 | 41 |
| vong_khong_tool | 10 | 5 |
| don_hang | 3 | 0 |

Chia THEO KỊCH BẢN, seed 42, 20 % kịch bản làm test (55 kịch bản). Lưu ý: cùng kịch bản lặp 3 lần chạy + các bộ 1116 → mẫu trùng lời khách, dedupe theo (kịch bản, lời khách) trước khi train.
Sau dedupe (kịch bản, lời khách, nhãn): 1243 mẫu; khong_tra: 548, ghi: 354, tra_san_pham: 169, chinh_sach: 46, vong_nhac_vo_ich: 45, nhieu_loai: 40, khac: 31, vong_khong_tool: 9, don_hang: 1
