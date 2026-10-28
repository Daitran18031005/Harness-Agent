# Báo cáo đánh giá

Đo bằng `reference_eval.py` của BTC (qua package `evaluation/`) trên **22 kịch bản** (7 mẫu BTC + 15 kịch bản sinh), **3 seed**, mỗi seed một mẫu; model agent `gpt-4o-mini`, `temperature=0`, order gate luôn bật. Hai cấu hình: **hệ thống** (`full`: có bộ nhớ, Call Brief, harness) và **baseline** (`baseline_no_memory`: cùng model, cùng tool, bộ nhớ mới ở mỗi cuộc). Số liệu thô: `runs/gd2_run4/` (`gd2_report.md/json`, `failures_all.txt`); nhật ký từng lần chạy: [CHECKING.md](../CHECKING.md) § 11.87–11.95. Lệnh chạy lại: [README.md](README.md) mục 3.

## 1. Kết quả chính (lần chạy 4, 92 lượt/seed)

| Chỉ số | Hệ thống (mean ± std) | Baseline | Ngưỡng | Kết luận |
|---|---:|---:|---|---|
| TSR — tỷ lệ hoàn thành tác vụ | **72,7 ± 0,0 %** (16/22, cả 3 seed) | 71,2 ± 2,6 % | ≥ 70 % và hơn baseline | **Đạt** (hơn baseline 1,5 điểm — *nằm trong độ lệch chuẩn của baseline, không nên coi là khác biệt rõ*) |
| — trong đó bộ sinh (tương tác) | **100 %** (15/15, 3 seed) | — | — | tiêu chí chính của hệ có order gate |
| — trong đó 7 mẫu BTC cố định | 14,3 % | 14,3 % | — | bị order gate chặn theo thiết kế (mục 4) |
| RQR — câu hỏi lặp | **2,1 ± 3,6 %** | 12,2 ± 3,4 % | giảm ≥ 40 % | **Đạt**: giảm 76,5 % (theo seed 100 / 29,5 / 100 %: **độ biến thiên lớn**) |
| CCR — mang ngữ cảnh sang cuộc sau | **52,4 ± 2,1 %** | 3,6 ± 0,0 % | — | hơn rõ rệt; vẫn còn thiếu một nửa |
| HR giá/KM — bịa giá/khuyến mãi | **6,0 ± 0,2 %** | 33,9 ± 5,8 % | ≤ 5 % | **Chưa đạt** (phần còn lại là sự thật kịch bản lệch tool, mục 5) |
| Guardrail — vi phạm | 0 | — | 0 | Đạt |
| Cuộc gọi tới chốt | 1,12 | — | — | — |
| Lượt/cuộc | 2,95 | — | — | — |
| Call Brief p95 | 67 ms | — | — | tra sẵn bằng code, không LLM |
| TTFT p95 | 26,2 s trung bình 3 seed; **seed sạch 6,7 và 7,3 s** (trung vị 3,6–3,7 s) | — | ≤ 3 s | **Chưa đạt** (mục 3) |

Theo seed (hệ thống): TSR 72,7 / 72,7 / 72,7; RQR 0,0 / 6,2 / 0,0; HR giá/KM 5,9 / 5,9 / 6,2; CCR 53,6 / 50,0 / 53,6.

## 2. Trước và sau cải tiến (cùng bộ 22 kịch bản, cấu hình hệ thống)

| Lần chạy | Thay đổi chính trước lần đó | TSR | TSR bộ sinh | RQR | HR giá/KM | TTFT p95 | Chi phí |
|---|---|---:|---|---:|---:|---:|---:|
| 1 (§ 11.87) | — | 50,0 ± 4,5 | 60 / 73 / 67 | 0,0 | 31,1 ± 7,2 | 12,9 s | 10.716 VND |
| 2 (§ 11.90) | 5 sửa từ phân tích lỗi (giá/qty/SĐT trong tool, câu hỏi định danh, phân loại giá sản phẩm phụ, gate sau câu trả lời) | 68,2 | 93 / 93 / 93 | 7,3 ± 6,5 | 6,2 ± 0,5 | 8,3 s | 11.331 VND |
| 3 (§ 11.92) | câu chuyển máy ca ngoài phạm vi bằng code; gate không lấn câu trả lời giá/KM | 71,2 ± 2,6 | 93 / 100 / 100 | 2,2 ± 3,9 | 9,5 ± 6,2 (seed 1 dính lỗi mạng) | 14,0 s | 11.707 VND |
| 4 (§ 11.94) | nhánh dự phòng mất LLM không chọn cứng sản phẩm (không kích hoạt vì không có lỗi mạng) | **72,7 ± 0,0** | **100 / 100 / 100** | **2,1 ± 3,6** | **6,0 ± 0,2** | 26,2 s (seed 1 có 3 lượt API đứng) | 11.639 VND |

Mỗi lần có nhiều sửa cùng lúc và mỗi seed một mẫu nên **không tách được đóng góp từng sửa**; chiều cải thiện rõ ở TSR (50 → 72,7) và HR (31,1 → 6,0). Sau lần 4 còn thêm timeout + thử lại cho cuộc gọi LLM (§ 11.95) và router chính sách tính chi phí vào trần (§ 11.96) — **chưa đo bằng LLM thật**.

## 3. Độ trễ

TTFT/Total đo thật bằng `perf_counter` ở chế độ stream. Lần 4: seed 2 và 3 có TTFT p95 6,7 s và 7,3 s (trung vị 3,6–3,7 s); seed 1 có 3 lượt bị API đứng 68–128 s (SC-GEN-07, SC-GEN-02, SC-GEN-11, console không báo lỗi) kéo p95 lên 64,6 s. Nguyên nhân gốc: timeout mặc định của SDK là 600 s. Đã thêm timeout 20 s theo khoảng lặng và thử lại cả vòng (§ 11.95) nhưng chưa đo lại. **Mục tiêu ≤ 3 s chưa đạt ngay cả ở seed sạch** (một lượt thường 1–2 vòng LLM, mỗi vòng gần 2–3 s); tối ưu token/TTFT là việc sau khi hoàn thiện chức năng.

## 4. Vì sao TSR của 7 mẫu BTC chỉ 14,3 %

Order gate (luôn bật) chỉ tạo đơn sau khi **khách xác nhận** bản đọc lại. Kịch bản BTC cố định là chuỗi lời khách soạn sẵn, không có câu trả lời cho các câu hỏi của gate (địa chỉ, thanh toán, đồng ý) nên đơn không bao giờ được tạo — cả baseline cũng vậy (14,3 %). Đây là lựa chọn an toàn có chủ đích (không tạo đơn khi khách chưa đồng ý). Vì vậy nhóm báo hai loại đo riêng: TSR tương tác (bộ sinh, khách mô phỏng trả lời gate, lượt chèn gắn `_injected` trong trace) là số chính; kịch bản cố định chỉ kiểm "không tạo đơn sớm và có tới bước đọc lại đơn". Cần xác nhận với BTC cách chấm kịch bản có order gate.

## 5. Ca hệ thống làm sai (14 ca) — nguyên nhân và trạng thái

| # | Ca | Hiện tượng | Nguyên nhân | Trạng thái |
|---|---|---|---|---|
| 1 | SC-GEN-01 cuộc 2 | giá nói 1.521.000, sự thật kịch bản 1.690.000 → tính là bịa giá | khuyến mãi RUN-10 hiệu lực 12–25/10 nên tool trả 1.521.000; sự thật kịch bản lệch tool (không phải LLM bịa) | **chờ BTC xác nhận**; là toàn bộ phần HR còn lại |
| 2 | SC-GEN-02 cuộc 1 | tổng 15.380.000 so với 15.980.000 | cùng loại: sự thật kịch bản lệch tool | chờ BTC (ngoài công thức HR giá/KM) |
| 3 | SC-GEN-05 cuộc 2 | chênh biến thể 40.000 so với 50.000 | cùng loại | chờ BTC |
| 4 | SAMPLE-01, 02, 04, 05, 06 (tạo đơn) và SAMPLE-03 (cập nhật đơn) cuộc 2 | không có `order.create/update` khớp | order gate chặn vì kịch bản cố định không trả lời gate | theo thiết kế; xem mục 4 |
| 5 | SAMPLE-03 cuộc 2 | hỏi lại "mã đơn hàng" ở lượt 2–3 (xuất hiện ở 4/9 lượt đo từ lần 2 đến lần 4) | LLM biến thiên; mã đơn BTC (OD682761) không có trong mock tool, hệ thống không thể tự biết | chưa sửa; hỏi BTC về mã đơn |
| 6 | SAMPLE-02 cuộc 2 | không mang `product_advised`, `competitor_price_vnd`, `objection` | chưa phân tích sâu nguyên nhân; cần đọc trace (có thể do agent không nhắc lại các thông tin này bằng lời) | chưa sửa (CCR còn 52 %) |
| 7 | SC-GEN-05 cuộc 2 | không mang `size`, `color`; `order.update` gọi trước khi khách đồng ý | LLM gọi tool ghi trước khi gate xác nhận | chưa sửa |
| 8 | SC-GEN-06 cuộc 2 | không mang `promo_code` | agent chưa nêu mã khuyến mãi cũ trong cuộc 2; chưa phân tích sâu (khuyến mãi đó đã hết hạn nên có thể nên không nêu) | chưa sửa / cần hỏi BTC |
| 9 | Lần 1: nhiều ca bộ sinh | HR 31 %: giá sản phẩm phụ (quà tặng) bị tính là giá sản phẩm chính; `order.create` thiếu `price_vnd`; `qty` sai; `get_quote` thiếu SĐT | trích claim không phân biệt sản phẩm; LLM bỏ trường | **đã sửa** (§ 11.89): nhãn `alt_price_vnd`, code điền `price_vnd`/SĐT/qty |
| 10 | SC-GEN-08 (lần 1–2) | chuyển máy đúng nhưng không nói "chưa có thông tin chuyên môn" | LLM bỏ qua luật prompt | **đã sửa** (§ 11.91): câu chuyển máy ca ngoài phạm vi do code dựng; đạt 3/3 seed ở lần 3, 4 |
| 11 | SAMPLE-05 cuộc 2 (lần 2) | RQR 7,3 %: câu hỏi về giảm giá bị thay bằng câu xác nhận SĐT của gate | gate mở sớm lấn câu trả lời | **đã sửa** (§ 11.91): không mở gate khi khách hỏi giá/KM; RQR về 2,2 |
| 12 | SC-GEN-06 cuộc 1–2 (lần 3, seed 1) | tư vấn máy lọc AirPure Y cho khách hỏi máy hút sữa rồi chốt đơn nhầm (5.200.000 so với 4.290.000) | mất kết nối LLM → nhánh dự phòng dùng mặc định cứng SKU-AP-Y | **đã sửa** (§ 11.93): chưa biết sản phẩm thì hỏi lại; chưa đo bằng LLM thật |
| 13 | 3 lượt lần 4, seed 1 | TTFT 68–128 s | không có timeout hữu hạn (SDK 600 s) | **đã sửa** (§ 11.95), chưa đo lại |
| 14 | GEN-02 lượt 1 (lần 1–2) | báo "giá cuối cho 2 máy" bằng giá một máy | LLM nhầm đơn vị giá | giảm nhờ luật prompt + gate đọc lại tổng; chưa có chốt bằng code |

Ca 1–3 (3 chỗ sự thật kịch bản lệch tool) cần gửi BTC; nếu BTC xác nhận sự thật của GEN-01 thì HR giá/KM về 0 ở các seed không bị lỗi mạng.

## 6. Chi phí

| Hạng mục | Giá trị |
|---|---|
| Lần chạy 4 (2 cấu hình × 3 seed × 22 kịch bản ≈ 186 cuộc) | **11.639 VND** (mẫu BTC 5.540 + bộ sinh 6.099) |
| Trung bình mỗi cuộc (cả hai cấu hình, mọi lệnh gọi LLM) | **≈ 63 VND/cuộc** |
| Riêng chat chính của hệ thống (seed 1) | ≈ 50 VND/cuộc (31 cuộc, 1.537 VND) |
| Trung bình mỗi lượt | ≈ 21–24 VND (`gpt-4o-mini`, giá `config/pricing.yaml`) |
| Router chính sách | ≈ 8–9 VND/lần tra chính sách; trước § 11.96 **không** nằm trong tổng/trần chi phí (thiếu vài trăm VND trên mỗi lần chạy 3 seed) |

Trần chi phí cứng luôn bật (`--max-cost-vnd`), kiểm trước mỗi lần gọi API.

## 7. Tác động kinh doanh (ước lượng — *giả định, không phải số đo*)

Số đo thật dùng làm đầu vào: RQR 12,2 % → 2,1 % (câu hỏi thừa trên tổng câu hỏi agent ở cuộc gọi lại), CCR 3,6 % → 52,4 %, HR giá/KM 33,9 % → 6,0 %, 1,12 cuộc tới chốt.

| Tác động | Cách ước lượng | Ví dụ với giả định |
|---|---|---|
| Rút ngắn thời gian xử lý | (12,2 − 2,1)% × số câu hỏi/cuộc gọi lại × giây/câu hỏi thừa | giả định 5 câu hỏi/cuộc và 8 giây/câu → ≈ 4 giây/cuộc gọi lại (nhỏ; lợi ích chính là trải nghiệm khách) |
| Giảm tư vấn sai giá/khuyến mãi | (33,9 − 6,0)% số câu nói giá/KM | trên 1.000 câu nói giá, ≈ 280 câu ít sai hơn; mỗi câu sai có thể kéo theo khiếu nại/hoàn COD (chưa đo) |
| Tăng khả năng chốt ở cuộc gọi lại | CCR cao hơn → không bắt khách nhắc lại thông tin; số cuộc tới chốt 1,12 | chưa có dữ liệu chốt đơn thật để quy ra tỷ lệ |

Các giả định (số câu hỏi/cuộc, giây/câu) do nhóm đặt; cần thay bằng số của doanh nghiệp.

## 8. Giới hạn của phép đo

- 22 kịch bản, mỗi seed một mẫu: phương sai lớn (RQR theo seed 100 / 29,5 / 100 %; baseline TSR 72,7 / 68,2 / 72,7 %).
- Hai lần chạy khác nhau nhiều thứ cùng lúc; không có thí nghiệm cắt bỏ từng thành phần.
- Chưa có LLM-judge 12 tiêu chí (bước 14b) và chưa có điểm chấm tay 20 lượt (`manual_review.csv` chưa được người điền).
- Ba chỗ sự thật kịch bản lệch tool ảnh hưởng cả hai cấu hình; HR phản ánh phần lệch đó.
- Dataset nhỏ (xem [DATASET.md](DATASET.md)); ASR chỉ đo trên 4 file TTS.
