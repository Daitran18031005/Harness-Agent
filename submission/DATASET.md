# Dataset — mô tả ngắn

Đối chiếu bảng C.1 / C.4 của đề. Số đếm lấy từ `BTC-Data-Vong1-TEAMS/test_set/{public_sample,team_eval}` (từ 2026-11-04 `generated_m1` đã gộp vào `team_eval`; số đếm trong bảng dưới là của bộ cũ 21–22 kịch bản dùng cho bước 15, chưa đếm lại với 49 kịch bản mới), `asr/audio`, `catalog`, `simulator` (đếm 2026-10-21, còn đúng cho bộ đang dùng để đo ở bước 15). Chi tiết kế hoạch mở rộng: [../docs/DATASET_PLAN.md](../docs/DATASET_PLAN.md).

## 1. Thành phần

| Thành phần | Nguồn | Số lượng |
|---|---|---|
| Kịch bản mẫu | BTC cấp (`public_sample`) | 7 kịch bản (SAMPLE-01…07) |
| Kịch bản sinh thêm | nhóm sinh/viết tay → `team_eval` (nguồn gốc là các file JSON; `generate_dataset.py` đã lưu trữ) | 14 kịch bản (SC-GEN-01, 03…15; đã bỏ SC-GEN-02) |
| Tổng | | **21 kịch bản = 30 cuộc gọi/chat**, 72 lượt khách |
| Khách đa phiên (≥ 2 cuộc) | 9 kịch bản | ngưỡng ≥ 30 |
| Khách đa kênh (gọi + chat) | SAMPLE-04, SAMPLE-06, SC-GEN-06 | 3 khách, ngưỡng ≥ 10 |
| Audio | 4 file TTS (D01–D04) | ≈ 148 giây, ngưỡng ≥ 40 cuộc / ≥ 1 giờ |
| Catalog | BTC | 40 SKU cha + 96 biến thể (136 SKU bán được), 3 nhóm hàng (gia dụng, mẹ & bé, thời trang) |
| Chính sách | BTC | 11 file public (+ tài liệu nội bộ không bao giờ đưa vào prompt), 99 chunk, có bản cũ hết hiệu lực |
| CRM | BTC | 50 khách, 3 miền (Bắc 15 / Trung 18 / Nam 17), có cặp dùng chung SĐT (C034/C035) |
| Persona | `simulator/personas.json` | 12 persona; có đủ 3 loại bắt buộc (dự người nhà, so giá, đã mua đổi size/khiếu nại) |

Kịch bản sinh thêm dùng **dữ liệu thật của BTC** (SKU, giá, khuyến mãi, khách CRM) và **số liệu đã kiểm trong mock tool** (hạn mức COD 10 triệu, gọi xác nhận trên 2 triệu, khuyến mãi theo ngày hiệu lực, SĐT dùng chung). Không bịa SKU/giá/ngày.

## 2. Cách sinh

- `generate_dataset.py` (đã lưu trữ ở `NotRelated/`; nội dung nay là các file JSON trong `team_eval/`): sinh kịch bản đa phiên / đa kênh / ca biên theo khung có sẵn (chỉ thêm, không sửa file BTC). Mỗi kịch bản gồm lời khách từng lượt, sự kiện phải mang sang (`must_carry_over`), điều không được hỏi lại (`must_not_ask`), điều kiện thành công (`success_if`) và `ground_truth_facts`.
- Dataset mở rộng bằng LLM (`src/dataset/`, `scripts/generate_dataset_text.py`): khung hội thoại → lời thoại → kiểm tra tự động (đúng SKU/giá/ngày theo tool thật). **Đã tạm dừng:** mới sinh một lô đại diện (10 khung = 12 cuộc, đều đạt kiểm tra tự động), chi phí 2.076 / 10.000 VND trần; chưa đưa vào bộ test.
- Audio: TTS một giọng; nhiễu và kênh điện thoại mô phỏng (`audio_sim.py`), **không phải** giọng thật nhiều vùng.

## 3. Phân bố và ca khó

| Loại | Hiện có |
|---|---|
| Đổi ý | 1 (SC-GEN-09) |
| Mâu thuẫn với phiên trước | 0 |
| Khuyến mãi hết hạn | 2 (SAMPLE-05, SC-GEN-01) |
| Hỏi ngoài tài liệu | 2 (SAMPLE-07 chính sách bản cũ, SC-GEN-08 câu hỏi y tế) |
| Kịch bản đa phiên | 9 (ngưỡng ≥ 20) |

## 4. Hạn chế (nói thẳng)

1. **Chưa đạt ngưỡng số lượng:** 31 cuộc so với ≥ 120; đa phiên 9 so với ≥ 30; đa kênh 3 so với ≥ 10; chưa có kịch bản 3 cuộc; chưa có ca "mâu thuẫn với phiên trước".
2. **Audio quá ít và quá sạch:** 4 file TTS giọng Bắc; không có giọng Nam/Trung hay nhiễu thật nên mọi số WER chỉ nói được cho phạm vi đó (n = 4).
3. **Đáp án kịch bản từng sai so với tool/chính sách** (lỗi của nhóm sinh dữ liệu, không phải BTC; đã sửa 2026-11-02): SC-GEN-01 (1.690.000 → 1.521.000, quên RUN-10 hiệu lực 12–25/10) và SC-GEN-05 (chênh size 50.000 → 40.000, giá cuộc 1 1.690.000 → 1.352.000, quên RUN2-SALE). SC-GEN-02 (đáp án tổng tiền sai) đã **bị xóa khỏi bộ**.
4. **Kịch bản cố định** do BTC viết không có lời khách trả lời câu hỏi của order gate nên TSR của 7 mẫu bị gate chặn theo thiết kế; kịch bản sinh có "khách mô phỏng" trả lời gate (`--gate-assist`, lượt chèn gắn `_injected` trong trace).

## 5. Thông tin cá nhân

- Số điện thoại, tên, địa chỉ trong dataset là **dữ liệu tổng hợp** (CRM seed của BTC và khách do nhóm sinh); không dùng dữ liệu khách thật.
- Runtime che PII trước khi vào LLM và trace: SĐT / địa chỉ / CCCD thành token (`<PHONE_n>`, `<ADDR_n>`, `<ID_n>`); bảng token chỉ nằm trong bộ nhớ của lượt; API trả trace rút gọn không có lời khách/agent hay tham số tool.
- Khóa API không nằm trong gói nộp: `scripts/package_submission.py` loại `.env` và `backup_*/`, quét chuỗi giống khóa và xóa gói nếu phát hiện.
- Xóa dữ liệu một khách: `delete_customer_data` (chỉ caller `Operator`), xóa cả hồ sơ, episode, vector và liên kết định danh.
