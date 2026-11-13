# Điều tra 9 điểm TSR: m1_final4 → m1_final7 (13/11/2026)

Không gọi LLM. Chỉ đọc trace có sẵn, chấm lại bằng `reference_eval` trên cùng `runs/m1_final7/scen_all`.
Script: `tsr_diff.py` (scratchpad của phiên, không đưa vào repo).

## Mốc so sánh

| Lần đo | Mã | TSR TB (3 lượt) |
|---|---|---:|
| m1_final4 | code trước 73958d2 (chạy 19–21 h 12/11) | 79,4 |
| m1_final5 | 73958d2 (ghi trong commit message) | 85,9 |
| m1_final6 | 7762e83 (chạm trần, chỉ ~175/277 kịch bản) | — |
| m1_final7 | 616b3cc | 88,6 |

Chênh tính lại theo kịch bản: **+9,39 điểm**. Dùng m1_final5/6 làm điểm giữa để biết thay đổi xảy ra ở đoạn nào:

- **A** = m1_final4 → m1_final5: commit 73958d2.
- **B** = m1_final5 → m1_final6: d8eb0a8, d1a3cc6, 12daae0, 7e3db55, 5cb4954 (dữ liệu), 6cc9cd3, ef55147, 2fa7769, 7762e83.
- **C** = m1_final6 → m1_final7: 74ccad3, 97761b1, 816df49, e101c63, 699d657, 108b85a.
- **B|C**: m1_final6 không có kịch bản này (chạm trần), nên không tách được.

Tiêu chí: một cuộc gọi tính là "đổi" khi trượt ≥2/3 lượt trước và đạt ≥2/3 lượt sau, hoặc ngược lại. Có 40 cuộc tốt lên và 15 cuộc xấu đi. Kịch bản có cuộc đổi kết quả dưới ngưỡng đó được xếp vào nhóm "nhiễu".

## Tổng hợp: quy điểm TSR cho từng nhóm

| Nhóm | Điểm TSR | Mức tin |
|---|---:|---|
| **Dữ liệu đầu vào đổi (5cb4954)** — sinh lại customer_turns_asr của TEST-130, 157, 196, 58, 89 (bản teencode cũ làm mất câu đọc SĐT) | **+1,81** | chắc |
| 73958d2 — báo ngày gọi lại khi lịch dời khỏi ngày nghỉ (họ `lich_nghi_hen_goi_lai`: TEST-103, 121, 167, 29, 65) | +1,69 | chắc |
| 73958d2 — câu đọc lại đơn và lượt chốt (họ `cod_vuot_han_muc`: TEST-104, 114, 165, 189) | +1,32 | có thể |
| 73958d2 — lượt chốt (họ `cod_can_xac_nhan`: +TEST-129, 158, 204, 70, 92; −TEST-15, SC-GEN-03) | +0,96 | có thể |
| 73958d2 — "miễn phí vận chuyển" trong câu đọc lại (TEST-200, 219) | +0,60 | có thể |
| 73958d2 — đọc qty/sản phẩm, A3 (họ `mua_kem_phu_kien`: TEST-69, 94) | +0,60 | có thể |
| d8eb0a8 / d1a3cc6 — các lỗi đã điều tra từ m1_final5 (TEST-08, 111, 148, 179, 21, 211, 67) | +2,53 | chắc |
| d8eb0a8 — khuyến mãi máy thứ hai (TEST-171) | +0,24 | có thể |
| **12daae0 — hồi quy:** phiếu chuyển máy để `product_advised` = null khi bộ đọc không trả SKU (họ `cau_hoi_y_te`: TEST-110, 116, 183, 53) | **−1,44** | chắc |
| **Đoạn C — hồi quy:** TEST-122, TEST-113, TEST-181 | **−0,96** | có thể |
| Đoạn A, chưa rõ nguyên nhân (+TEST-109, 30, 74; −TEST-107, 124) | +0,36 | không rõ |
| TEST-81 (B\|C) | +0,12 | không rõ |
| Nhiễu (kịch bản đổi 1/3 lượt, không cuộc nào qua ngưỡng 2/3) | +1,56 | không rõ (nhiễu LLM) |
| **Tổng** | **+9,39** | |

**Kết luận:**

- **Chắc chắn:** +4,59 điểm. Gồm +1,69 (lịch nghỉ, 73958d2), +2,53 (d8eb0a8/d1a3cc6), −1,44 (12daae0) và +1,81 từ đổi dữ liệu.
- **Có thể:** +2,78 điểm, chủ yếu từ lượt chốt và câu đọc lại đơn của 73958d2. Cả nhóm 73958d2 chắc chắn nằm ở đoạn A, vì m1_final5 đo trên đúng commit đó. Chỉ việc gán cho từng mục sửa bên trong commit là suy luận.
- **Không rõ:** 2,04 điểm (nhiễu 1,56 + 0,48). Dưới ngưỡng 3 điểm nên **không đề xuất bisect**.
- **Lưu ý khi báo số:**
  - Khoảng **1,8 điểm** đến từ việc sửa câu khách đầu vào của 5 kịch bản do nhóm tự sinh (team_eval), không phải do hệ thống giỏi hơn. Đáp án (`success_if`, `facts_established`) không đổi.
  - So trên cùng bộ dữ liệu, mức tăng của hệ thống là khoảng **+7,6 điểm**.
- Các sửa của đoạn C (độ trễ) **không làm tăng TSR**. Phần tách được của đoạn C là −0,96, cộng thêm SAMPLE-01/call_2 nói ở dưới.

## Hồi quy cần sửa sau (chưa sửa, theo yêu cầu)

1. **12daae0, phiếu chuyển máy thiếu sản phẩm (chắc).**
   - Ở m1_final5, `brief.product_advised = "SKU-MB-BOT"`; ở m1_final7 là `null`.
   - Nguyên nhân: 12daae0 đổi phiếu chuyển máy sang dùng SKU bộ đọc thay cho alias. Lượt hỏi y tế không có lời chốt nên bộ đọc không trả SKU.
   - Mất 4 kịch bản, 3/3 lượt mỗi kịch bản.
2. **Chạy trước catalog.search tra nhầm sản phẩm (699d657/108b85a, chắc về cơ chế).**
   - SAMPLE-01/call_2 lượt 1: m1_final6 tra trước SKU-AP-Y ở cả 3 lượt chạy, m1_final7 tra trước SKU-AP-X ở cả 3 lượt chạy.
   - Agent báo nhầm sản phẩm và giá (4.890.000 thay vì 5.200.000), nên lên đơn sai.
   - Kịch bản không đổi TSR vì các cuộc khác của nó vẫn trượt theo cách khác. Riêng cuộc này mất 3/3 lượt.
3. **TEST-122 (có thể, đoạn C).**
   - Khách gọi "Màng lọc thay thế AirPure X/Y". Gate gặp `ambiguous_product` [SKU-AP-X, SKU-AP-FLT-X] với `listing=false`, nên agent hỏi lại khách thay vì lên đơn.
   - Ở m1_final6 có `listing=true` và đơn vẫn được tạo. Nghi do prefetch thêm máy AirPure X vào danh sách sản phẩm đã nhắc.
4. **TEST-181 (có thể, đoạn C).**
   - Gate mở ngay ở lượt 1, khi khách nói "định gom 2 máy". Lượt chốt sau đó tạo đơn qty 2, vượt hạn mức COD, nên bị từ chối.
   - Nghi do đổi prompt bộ đọc (816df49/e101c63).

Hai mục 2 và 3 liên quan trực tiếp đến hướng 1 của việc 2 (mở rộng tra trước). Cần xử lý trước khi mở rộng, nếu không sẽ khuếch đại lỗi tra nhầm.

## Danh sách cuộc gọi đổi kết quả (đạt/tổng số lượt: m1_final4 · m1_final5 · m1_final6 · m1_final7)

**Tốt lên (40 cuộc):**
- SC-TV-10/call_3 0·1·3·3 (d8eb0a8, lời hứa chuyển máy)
- SC-TV-18/call_3 1·3·3·3
- SC-ULTRA-02/call_4 1·3·3·3
- TEST-08 0·0·3·3
- TEST-103 0·3·3·3
- TEST-104 0·3·3·3
- TEST-109 0·3·3·2
- TEST-111/call_2 0·0·3·3
- TEST-114 0·3·2·3
- TEST-121 0·3·3·3
- TEST-123/call_2 0·3·3·3
- TEST-129 1·3·3·3
- TEST-130 0·0·3·3 (dữ liệu)
- TEST-148 0·0·3·3
- TEST-157 0·0·3·3 (dữ liệu)
- TEST-158 1·3·3·3
- TEST-165 1·3·3·3
- TEST-167 0·3·3·3
- TEST-171 1·1·2·3
- TEST-179/call_1 1·0·3·3
- TEST-179/call_2 0·0·3·3
- TEST-189 0·3·3·3
- TEST-196 0·0·1·3 (dữ liệu)
- TEST-200 0·3·1/2·3
- TEST-204 0·3·–·3
- TEST-21 0·0·–·3
- TEST-211/call_2 0·0·–·3
- TEST-219 1·3·–·3
- TEST-29 0·3·–·3
- TEST-30 0·2·–·2
- TEST-58 0·0·–·3 (dữ liệu)
- TEST-65 1·3·–·3
- TEST-67 0·0·–·3
- TEST-69 0·3·–·3
- TEST-70 0·3·–·3
- TEST-74/call_2 1·3·–·3
- TEST-81 1·1·–·2
- TEST-89 0·0·–·3 (dữ liệu)
- TEST-92 0·3·–·3
- TEST-94 1·2·–·3

**Xấu đi (15 cuộc):**
- SAMPLE-01/call_2 3·3·3·0 (prefetch)
- SC-GEN-03 2·1·2·0
- SC-ULTRA-05/call_4 2·1·1·1
- SC-ULTRA-07/call_4 3·1·1·1 (đã điều tra: dao động cách nói của LLM)
- SC-ULTRA-08/call_4 2·1·1·1
- TEST-107 2·1·0·1
- TEST-110 3·3·0·0 (12daae0)
- TEST-113 3·2·2·0
- TEST-116 3·3·0·0 (12daae0)
- TEST-122 3·3·3·0
- TEST-124 2·1·1·0
- TEST-15 3·1·2·0
- TEST-181 3·3·3·1
- TEST-183 3·3·0·0 (12daae0)
- TEST-53 3·3·–·0 (12daae0)

Ghi chú: các cuộc SC-* nhiều cuộc gọi có thể đổi kết quả ở mức cuộc mà không đổi TSR của cả kịch bản.
