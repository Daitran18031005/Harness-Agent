# Báo cáo đánh giá

Chấm bằng `eval/reference_eval.py` của BTC (bản 08/11/2026) trên **277 kịch bản**: 7 mẫu BTC (`test_set/public_sample`) + 270 kịch bản của nhóm (`test_set/team_eval`: 15 SC-GEN, 20 SC-TV, 15 SC-ULTRA, 220 TEST; 442 cuộc gọi; 105 kịch bản đa phiên; 241 ca khó; 33 kịch bản đa kênh). Model agent `gpt-4o-mini`, `temperature=0`, **1 seed (42)**. Hai cấu hình cùng model, cùng tool, cùng phần cứng:

- **Hệ thống** (`full`): bộ nhớ 4 tầng, Call Brief, harness.
- **Baseline** (`baseline_no_memory`): bộ nhớ mới ở mỗi cuộc gọi.

Lời khách là lời cố định của kịch bản. Theo hướng dẫn của BTC (11/2026), sau lượt khách cuối agent được **một lượt chốt** (`customer_text` rỗng) để đọc lại đơn và gọi `order.create`; hệ thống chỉ dùng lượt này khi đơn đang chờ. Không dùng khách mô phỏng.

Số liệu thô: `runs/m1_final2/` (`full.jsonl`, `baseline.jsonl`, `report.json`, `report.md`). Lệnh tái lập: [README.md](README.md) mục 3. Nhật ký: [CHECKING.md](../CHECKING.md) § 13.

## 1. Bảng A.6

| Chỉ số | Baseline | Hệ thống | Ngưỡng đề bài | Kết luận |
|---|---:|---:|---|---|
| Repeat-Question Rate | 4,7 % | **3,3 %** | giảm ≥ 40 % | **Chưa đạt** — giảm 30 % (9 câu thừa / 271 câu hỏi) |
| Context Carryover Rate | 10,7 % | **57,2 %** | — | hơn rõ; còn thiếu gần một nửa |
| Task Success Rate | 66,8 % (185/277) | **76,5 %** (212/277) | ≥ 70 % | **Đạt**, hơn baseline 9,7 điểm |
| TSR riêng ca khó | — | 75,0 % | — | — |
| Hallucination Rate giá & KM | 22,3 % | **14,6 %** | ≤ 5 % | **Chưa đạt theo script**; xem mục 4 (25/26 claim bị tính sai là giá đúng của sản phẩm khác đáp án) |
| Vi phạm guardrail (số ca) | 6 | 10 | 0 | **Kém baseline** — 5 chuyển máy thừa, 5 mẫu cấm nội bộ (mục 5, ca 7–8) |
| Số lượt TB / cuộc | 2,40 | 2,38 | — | — |
| Số cuộc gọi tới chốt đơn | 1,39 | 1,38 | — | — |
| Nạp Call Brief p95 | 31 ms | 47 ms | ≤ 5 s | **Đạt** (tra bằng code, không LLM) |
| TTFT p50 / p95 (1.084 lượt) | 4,8 s / 7,8 s | 4,5 s / 7,5 s | p95 ≤ 3 s | **Chưa đạt** |
| Total latency p95 | 9,2 s | 8,9 s | ≤ 8 s | **Chưa đạt** |

TSR theo nhóm kịch bản:

| Nhóm | Số kịch bản | Hệ thống | Baseline |
|---|---:|---:|---:|
| 7 mẫu BTC | 7 | 6/7 | 5/7 |
| SC-GEN (sinh theo khung) | 15 | 13/15 | 13/15 |
| SC-TV | 20 | 18/20 | 14/20 |
| SC-ULTRA (4–5 cuộc/khách) | 15 | 10/15 | 6/15 |
| TEST | 220 | 165/220 | 147/220 |

Bộ nhớ tạo khác biệt lớn nhất ở kịch bản nhiều cuộc gọi (SC-ULTRA 67 % so với 40 %, SC-TV 90 % so với 70 %); ở kịch bản một cuộc gọi hai cấu hình gần nhau.

Cách trích `questions[]` / `claims[]`: mô tả ở đầu `src/harness/extractor.py` (tách mệnh đề, gán vai trò số tiền theo kết quả tool rồi theo từ khóa, giá của mẫu khác sản phẩm đang bàn mang nhãn `alt_price_vnd`; mọi câu hỏi đều được đếm, câu không gán được slot có `slot = "other"`).

## 2. Trước và sau cải tiến

**(a) 7 mẫu BTC — cùng bộ, cùng model, cấu hình hệ thống**

| Lần đo | Thay đổi trước lần đó | TSR | HR giá & KM | RQR |
|---|---|---:|---:|---:|
| `runs/m1_final/sample` | hợp đồng tool BTC 11/2026 (`pricing.quote_order`, `order.create(lines)`) | 1/7 | — | — |
| `runs/m1_closing` | thêm lượt chốt theo luật BTC | **7/7** | 11,1 % | 8,0 % |
| `runs/m1_final2/sample` | bộ trích claim nhận sản phẩm đang bàn; không mở đơn sau khi đổi hàng | 6/7 | 0,0 % | 4,2 % |
| `runs/m1_check2` (3 kịch bản, gồm SAMPLE-03) | chốt độc lập ở lượt chốt; không mở đơn khi khách đã có đơn sản phẩm đó; lịch gọi lại quá khứ → lần kế tiếp | SAMPLE-03 đạt | — | 0,0 % |

SAMPLE-03 dao động giữa các lần (đạt ở `m1_closing`, trượt ở `m1_final2`, đạt lại sau sửa) vì LLM có lần gọi `order.update` sớm, có lần chờ khách đồng ý; lỗi gốc (mục 5, ca 2) đã sửa.

**(b) 14 kịch bản kiểm chứng** (7 mẫu BTC + 7 kịch bản liên quan các sửa; `runs/m1_check`): TSR 10/14 → 11/14, HR giá & KM 0,0 %, guardrail 0, TEST-198 không còn bị tạo đơn sai.

**(c) Lịch sử trên bộ 22 kịch bản cũ** (3 seed, có khách mô phỏng — không cùng cơ sở với bảng A.6): TSR 50,0 → 68,2 → 71,2 → 72,7 → 69,8 → 66,7 qua 6 lần đo; chi tiết ở CHECKING.md § 12.

**(d) Knowledge Gap Loop** (cơ chế cải tiến, [ARCHITECTURE.md](ARCHITECTURE.md) mục 7): vòng 0 gom được 9 câu hỏi kho chính sách không trả lời được; **đang chờ người duyệt, chưa đo vòng 1**.

Giới hạn: các sửa sau `runs/m1_final2` (mục 5, ca 1–3, 6) mới được kiểm trên 3 và 14 kịch bản, **chưa đo lại cả bộ 277**.

## 3. Độ trễ

Đo bằng `perf_counter` tại ranh giới harness, chế độ stream, 1.084 lượt (≥ 100 theo yêu cầu). TTFT p50 4,5 s, p95 7,5 s; Total p95 8,9 s — **cả hai chưa đạt ngưỡng**. Nguyên nhân: một lượt thường gồm 1 lần đọc hiểu lời khách + 1–2 vòng LLM có gọi tool, mỗi vòng 2–3 s; token đầu tiên chỉ có ở vòng cuối. Lượt do code xử lý (order gate, lượt chốt) không gọi LLM chính. Nạp Call Brief 47 ms (p95) vì tra sẵn bằng code lúc nhận diện khách.

## 4. Hallucination giá & khuyến mãi: 14,6 % theo script, 0,6 % theo giá của mock

`reference_eval.py` so **mọi** claim `price_vnd` trong một cuộc gọi với **một** giá trị `ground_truth_facts.price_vnd`. Nhóm đối chiếu từng claim bị tính sai với `mock_tools.pricing_get_quote` đúng ngày gọi (trên `runs/m1_final`, 26 claim; danh sách: `runs/m1_final/hr_price_check.json`):

| Loại | Số claim |
|---|---:|
| Giá `final` đúng của sản phẩm KHÁC sản phẩm đáp án (khách hỏi A rồi chuyển sang B) | 23 |
| Giá đúng của biến thể khác (size có phụ thu) | 1 |
| Giá đúng của máy thứ hai sau AIR-2ND-50 | 1 |
| Sai thật: báo giá niêm yết của mẫu đang giảm giá | 1 |

Tức 25/26 claim là agent nói đúng; chỉ tính claim khác giá mock thì tỷ lệ là 1/180 ≈ 0,6 %. Nhóm đã gửi câu hỏi cho BTC ([docs/BAO_CAO_HR_GUI_BTC.md](../docs/BAO_CAO_HR_GUI_BTC.md)). Con số chính thức vẫn là số của script.

## 5. Ca hệ thống làm sai (12 ca)

| # | Kịch bản | Hiện tượng | Nguyên nhân | Trạng thái |
|---|---|---|---|---|
| 1 | TEST-198 | Khách nói "khoan chốt… vội" nhưng lượt chốt vẫn tạo đơn (gọi tool bị cấm) | Bộ đọc hiểu nhận nhầm chữ "chốt" là cam kết mua; lượt chốt không có bước khách xác nhận | **Đã sửa**: `reply_reader.authorize_closing` — lớp LLM độc lập đọc toàn bộ lời khách, phải có trích dẫn nguyên văn yêu cầu đặt đơn. Kiểm lại: không còn tạo đơn |
| 2 | SAMPLE-03, TEST-40 (cuộc 2) | Khách đồng ý đổi size, hệ thống lại hỏi địa chỉ/thanh toán như đơn mới; không gọi `order.update` | Cổng mở đơn bằng code hiểu "ừ em làm thủ tục đổi" là chốt mua | **Đã sửa**: không tự mở đơn khi khách đã có đơn đúng sản phẩm đó. Kiểm lại: 2/2 đạt, RQR 0 |
| 3 | TEST-103, 121, 167, 188, 65 | Khách hẹn gọi lại "Tết Dương lịch 01/01", agent không báo ngày nghỉ | LLM điền `2026-01-01` (đã qua so với ngày gọi 15/10) nên tool không dời lịch | **Đã sửa**: ngày hẹn đã qua chuyển sang lần kế tiếp. Kiểm lại TEST-103: đạt |
| 4 | SAMPLE-06, TEST-172, 184 | Giá mẫu gợi ý thêm bị ghi là giá sản phẩm chính | Bộ trích claim lấy mẫu đứng đầu danh sách gợi ý làm chủ đề | **Đã sửa**: bộ trích nhận sản phẩm đang bàn. HR 7 mẫu BTC 11,1 % → 0,0 % |
| 5 | TEST-184 | Báo 7.990.000 cho AirPure Pro đang giảm còn 7.690.000 | `product.shortlist` chỉ trả giá niêm yết | **Đã sửa**: danh sách gợi ý kèm giá sau khuyến mãi của ngày gọi; chưa đo lại cả bộ |
| 6 | TEST-110, 116, 168, 174, 183, 46, 53, SC-TV-07 | Phiếu chuyển máy thiếu `product_advised` | LLM điền `null` dù khách nêu tên sản phẩm; code chỉ bù trường vắng, không bù trường `null` | **Đã sửa**: bù cả trường rỗng, lấy sản phẩm khách nêu từ catalog; chưa đo lại bằng LLM |
| 7 | TEST-135, 154, 21 | Trace chứa "giá nhập", "giá sàn", "biên lợi nhuận" | Agent từ chối đúng nhưng **lặp lại chữ của khách** ("em không thể tiết lộ giá nhập") | Chưa sửa |
| 8 | SC-ULTRA-01, 04, 10, 12, TEST-208 | Chuyển máy thừa | Chưa phân tích từng ca; 3/5 ca baseline cũng dính | Chưa sửa |
| 9 | TEST-130, 132, 138, 148, 153… (21 cuộc) | Không có `order.create` khớp đáp án | Đã xem TEST-130: khách chat không dấu, không có SĐT nhận hàng → gate hỏi, lượt chốt không tạo đơn. Các ca còn lại chưa phân loại (lỗi hệ thống hay đáp án) | Chưa sửa |
| 10 | TEST-111, 179, 211 | Không nói "quá hạn 7 ngày" khi khách xin đổi trả muộn | Chưa phân tích | Chưa sửa |
| 11 | SC-GEN-14, TEST-11, TEST-12 | Không nói sản phẩm ngừng bán; nói còn hàng | Chưa phân tích | Chưa sửa |
| 12 | TEST-181 | Agent tự nhân 2 × giá thay vì gọi `pricing.quote_order` (tổng vẫn đúng vì không có khuyến mãi) | LLM bỏ qua luật "không tự nhân" | Bộ trích đã gán đúng nhãn `total_vnd`; hành vi chưa chốt bằng code |

Danh sách đầy đủ 71 cuộc gọi trượt: `runs/m1_final2/report.md`.

## 6. Chi phí

| Hạng mục | Giá trị |
|---|---|
| Lần đo 277 kịch bản × 2 cấu hình (455 cuộc × 2, 2.175 lượt) | **63.391 VND** |
| Trung bình mỗi cuộc gọi (mọi lệnh gọi LLM: đọc hiểu, chat chính, router chính sách, trích bộ nhớ cuối cuộc) | **≈ 70 VND** |
| Trung bình mỗi lượt | ≈ 29 VND |
| Kiểm chứng sau sửa (17 kịch bản) | 4.465 VND |

Giá theo `config/pricing.yaml`. Trần chi phí cứng luôn bật (`--max-cost-vnd`, mặc định 20.000 VND), kiểm trước mỗi lần gọi API.

## 7. Tác động kinh doanh (ước lượng — giả định, không phải số đo)

| Tác động | Số đo làm đầu vào | Ghi chú |
|---|---|---|
| Khách không phải nhắc lại thông tin | CCR 10,7 % → 57,2 % | lợi ích chính là trải nghiệm; chưa có số chốt đơn thật |
| Hoàn thành việc ở cuộc gọi lại | TSR 66,8 % → 76,5 %; kịch bản 4–5 cuộc: 40 % → 67 % | chênh lớn nhất ở khách gọi nhiều lần |
| Ít câu hỏi thừa | RQR 4,7 % → 3,3 % | giả định 5 câu hỏi/cuộc, 8 giây/câu: tiết kiệm dưới 1 giây/cuộc — nhỏ |
| Chi phí | ≈ 70 VND/cuộc | so với lương nhân viên theo cuộc gọi do doanh nghiệp tự tính |

## 8. Giới hạn của phép đo

- **Một seed**: chưa có độ lệch chuẩn; SAMPLE-03 cho thấy cùng kịch bản có thể đạt/trượt giữa các lần chạy.
- 270/277 kịch bản do nhóm viết; đáp án có thể sai (mục 4). Bộ ẩn của BTC có thể cho số khác.
- Các sửa ở mục 5 (ca 1–6) chưa được đo lại trên cả bộ.
- Chưa có LLM-judge và chưa có bảng chấm tay 20 lượt.
- ASR chỉ đo trên 4 file TTS (xem [DATASET.md](DATASET.md)); ngưỡng ≥ 20 file chưa đạt.
