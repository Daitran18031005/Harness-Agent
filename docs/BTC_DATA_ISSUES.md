# BTC_DATA_ISSUES.md — Danh sách "nghi lỗi dữ liệu BTC"

> **Nguyên tắc:** chúng tôi **không sửa ground truth (GT)** của BTC. Mục dưới đây chỉ là *nghi vấn* kèm bằng chứng để hỏi lại BTC; hệ thống vẫn được chấm theo GT nguyên bản.
> Quét tự động bằng `python scripts/scan_btc_data.py` (so GT với lời khách và với `mock_tools.py` của chính BTC) — lần quét 2026-10-21 trên 7 kịch bản `public_sample`.

| # | Vị trí | Nghi vấn | Bằng chứng | Tác động | Trạng thái |
|---|---|---|---|---|---|
| 1 | `SAMPLE-01` call_1, `facts_established.budget_vnd` | GT ghi **5.700.000** nhưng khách nói "ngân sách tầm **5 triệu** thôi em" (ITN → 5.000.000) | `scripts/scan_btc_data.py`; lời khách trong `SAMPLE-01.json` | Slot `budget_vnd` hệ thống ghi **5.000.000 (đúng lời khách)** bị tính "sai" so với GT; không ảnh hưởng 5 chỉ số bắt buộc (không có `must_carry_over` về ngân sách) nhưng làm sai thống kê chất lượng trích slot | **Chưa hỏi BTC** — GT giữ nguyên |
| 2 | `SAMPLE-03` call_2, `success_if.args_match.order_id = OD682761` | Mã đơn này `mock_tools` không thể sinh ra (chỉ ra `OD600001`, `OD600002`…) | `mock_tools.order_create` | Trước đây làm kịch bản trượt oan | **Đã được BTC xử lý** (script chấm cập nhật 2026-10-20: chấp nhận mã do `order.create` trả về) — ghi lại để đầy đủ |
| 3 | `README.md` của gói BTC | Liệt kê `eval/validate_scenarios.py` ("BTC chạy sau mỗi lần sửa") nhưng **file không có trong gói** | `ls BTC-Data-Vong1-TEAMS/eval` | Nhóm không tự kiểm được kịch bản ↔ catalog theo công cụ của BTC; chúng tôi viết công cụ thay thế (kế hoạch: `scripts/validate_scenarios.py`, xem `DATASET_PLAN.md`) | Cần xác nhận với BTC |
| 4 | `asr/ground_truth.json` (`description`) | Mô tả nói "D01–D04 **kèm audio**", nhưng thư mục `asr/audio/` của gói không có file BTC cấp; 4 file `D01–D04.mp3` trong repo do **nhóm tự sinh bằng TTS** từ GT | ngày tạo file 2026-10-10 do `scripts/generate_test_audio.py` | WER đo trên TTS 1 giọng không phản ánh audio thật (GT ghi D01–D04 có giọng Bắc/Nam/Trung và 1/4 có nhiễu; 8/12 hội thoại còn lại BTC giữ, audio phát ngày chấm) | Cần xác nhận audio chính thức có được cấp trước không |

## Ghi chú

- Mục 1 là mục duy nhất bị quét tự động bắt được còn tồn tại; 2 đã giải quyết. Các nghi vấn 3–4 là về *gói dữ liệu*, không phải sai đáp án.
- Khi hỏi BTC về mục 1, nên nêu kèm: nếu GT đúng thì `budget_vnd` 5,7 triệu bắt nguồn từ đâu (lời khách nói 5 triệu, sản phẩm đáp án là AirPure Y 5,2 triệu có khóa trẻ em).
