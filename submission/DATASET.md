# Dataset — mô tả ngắn

Đối chiếu bảng C.1 / C.4 của đề. Số đếm lấy trực tiếp từ `BTC-Data-Vong1-TEAMS/test_set/{public_sample,team_eval}`, `asr/audio`, `catalog` (đếm 2026-11-11).

## 1. Thành phần

| Thành phần | Nguồn | Số lượng | Ngưỡng M1 |
|---|---|---|---|
| Kịch bản mẫu | BTC (`public_sample`) | 7 | — |
| Kịch bản của nhóm | `team_eval`: 15 SC-GEN, 20 SC-TV, 15 SC-ULTRA, 220 TEST | 270 | ≥ 20 đa phiên + ≥ 5 ca khó |
| **Tổng** | | **277 kịch bản = 455 cuộc gọi/chat, 908 lượt khách** | ≥ 120 cuộc |
| Kịch bản đa phiên (≥ 2 cuộc cùng khách) | | **111** (trong đó 47 có ≥ 3 cuộc; SC-ULTRA 4–5 cuộc) | ≥ 30 khách |
| Kịch bản đa kênh (gọi + chat) | hotline 382 cuộc · Fanpage 39 · Zalo OA 34 | **35** | ≥ 10 khách |
| Ca khó (`hard_case`) | 77 loại nhãn | 244 kịch bản | ≥ 5 |
| Audio | 4 file TTS (D01–D04 của BTC) | ≈ 148 giây | **≥ 40 cuộc / ≥ 1 giờ — CHƯA ĐẠT** |
| Catalog | BTC | 40 SKU cha + 96 biến thể, 3 ngành (gia dụng, mẹ & bé, thời trang) | ≥ 30 SKU |
| Chính sách | BTC | 14 tài liệu, 99 chunk, có bản cũ hết hiệu lực và tài liệu nội bộ | — |
| CRM | BTC | 50 khách, 3 miền, có cặp dùng chung SĐT | — |

Hội thoại ở đây là **kịch bản lời khách** (mỗi lượt một câu) kèm kỳ vọng; lời agent sinh ra khi chạy và nằm trong trace (`runs/m1_final2/*.jsonl`, 1.084 lượt mỗi cấu hình).

## 2. Cách sinh

- **SC-GEN, SC-TV, SC-ULTRA** (50 kịch bản): viết theo khung (`src/dataset/specs.py`, `frames54.py`) — persona, sản phẩm, ngày gọi, tình huống — rồi sinh lời khách bằng LLM (`gpt-6-luna`) hoặc viết tay; mỗi kịch bản có `must_carry_over`, `must_not_ask`, `success_if`, `ground_truth_facts`.
- **TEST-01…220**: sinh theo mẫu từ catalog/khuyến mãi/CRM của BTC, phủ đều persona và loại ca khó; có biến thể lời khách không dấu, teencode, ASR lỗi.
- **Kiểm tra tự động** (`src/dataset/validate.py`, `tests/test_team_eval_set.py`): SKU/giá/khuyến mãi/tồn kho trong đáp án phải khớp `mock_tools.py` đúng ngày gọi; 166 ca `order.create` đã đối chiếu với mock.
- **Audio**: 4 file TTS một giọng của BTC; nhiễu và kênh điện thoại mô phỏng bằng `audio_sim.py`. Nhóm **chưa** sinh thêm audio.
- Không dùng ghi âm hay dữ liệu khách thật.

## 3. Phân bố

| Persona (17 loại; 8 loại nhiều nhất) | Số kịch bản |
|---|---:|
| Khách so giá | 56 |
| Khách mua nhiều món | 41 |
| Khách do dự, hỏi người nhà | 38 |
| Khách hỏi nhiều không mua | 36 |
| Khách thích khuyến mãi | 35 |
| Khách cần giao gấp | 35 |
| Khách ngoài phạm vi, cần chuyển máy | 7 |
| Khách đã mua, đổi size | 6 |

| Kỳ vọng của cuộc gọi | Số cuộc |
|---|---:|
| Tạo đơn (`order.create`) | 171 |
| Hẹn gọi lại | 166 |
| Khách từ chối / chưa mua | 44 |
| Đổi/sửa đơn (`order.update`) | 41 |
| Chuyển máy (`handoff.transfer`) | 24 |
| Hỏi trạng thái đơn | 6 |

| Ca khó (14 loại nhiều nhất) | Số kịch bản |
|---|---:|
| Đổi ý giữa cuộc | 14 |
| Khuyến mãi hết hạn | 12 |
| COD vượt hạn mức | 12 |
| COD cần gọi xác nhận | 9 |
| Hỏi theo chính sách bản cũ · đổi size có phụ thu · khiếu nại lỗi nhà sản xuất · câu hỏi y tế · đổi size lần hai · dò giá nhập nội bộ · mua kèm phụ kiện · phạm vi bảo hành | 7 mỗi loại |
| Hẹn gọi lại rơi ngày nghỉ | 6 |

## 4. Hạn chế

1. **Audio và ASR chưa đạt ngưỡng**: 4 file TTS giọng Bắc; không có giọng Nam/Trung hay nhiễu thật; WER/CER chỉ nói được cho n = 4, chưa có số riêng cho số tiền/SĐT trên ≥ 20 file.
2. **270/277 kịch bản do nhóm viết**: đáp án có thể sai so với tool. Đã gặp và sửa: SC-GEN-01, 02, 05 (bỏ sót khuyến mãi đang hiệu lực), TEST-189, TEST-13. Còn một lớp lệch chưa sửa: kịch bản "khách hỏi A rồi chuyển sang B" chỉ có một `price_vnd` trong đáp án nên giá đúng của A bị tính là bịa (báo cáo đánh giá mục 4).
3. **Lời khách cố định**: không phản ứng với câu hỏi của agent; các lượt hỏi–đáp về địa chỉ/thanh toán chỉ được đo gián tiếp qua lượt chốt.
4. **Phân bố lệch**: khách "đã mua, đổi size" và "cần chuyển máy" ít (6–7 kịch bản mỗi loại); kênh chat chiếm 16 % số cuộc.
5. Bộ sinh mở rộng bằng LLM (`src/dataset/`, 54 khung) mới sinh 10 khung = 12 cuộc (2.076 VND), đang tạm dừng.

## 5. Thông tin cá nhân

- Số điện thoại, tên, địa chỉ trong dataset là **dữ liệu tổng hợp** (CRM seed của BTC và khách do nhóm sinh); không dùng dữ liệu khách thật.
- Runtime che PII trước khi vào LLM và trace: SĐT / địa chỉ / CCCD thành token (`<PHONE_n>`, `<ADDR_n>`, `<ID_n>`); bảng token chỉ sống trong process, theo cuộc gọi, và được giải phóng khi cuộc gọi kết thúc; API trả trace rút gọn.
- Khóa API không nằm trong repo/gói nộp: `.gitignore` loại `.env`; `scripts/package_submission.py` quét chuỗi giống khóa và hủy gói nếu phát hiện.
- Xóa dữ liệu một khách: `delete_customer_data` (chỉ caller `Operator`) xóa hồ sơ, episode, vector và liên kết định danh.
