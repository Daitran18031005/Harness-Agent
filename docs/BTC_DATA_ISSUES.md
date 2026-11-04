# BTC_DATA_ISSUES.md — nghi lỗi dữ liệu / công cụ của BTC và đề xuất cách xử lý (CHỜ DUYỆT, 2026-11-04)

> **Nguyên tắc hiện hành:** không sửa ground truth (GT) hay mã của BTC; hệ thống được chấm theo bản nguyên gốc. Mỗi mục dưới đây có **bằng chứng chạy lại được** và một **đề xuất** để chủ dự án duyệt trước khi áp dụng hoặc gửi BTC.
> Quét tự động: `python scripts/scan_btc_data.py --scenarios BTC-Data-Vong1-TEAMS/test_set/public_sample` và `python scripts/validate_scenarios.py --no-existing --scenarios BTC-Data-Vong1-TEAMS/test_set/public_sample`.
> Lỗi của **bộ kịch bản nhóm tự viết** (generated_m1, custom_test_45) không nằm ở đây — xem `BTC-Data-Vong1-TEAMS/test_set/team_eval/README.md`.

## A. Lỗi trong dữ liệu / công cụ BTC

| # | Vị trí | Vấn đề + bằng chứng | Tác động | Đề xuất (chờ duyệt) |
|---|---|---|---|---|
| 1 | `SAMPLE-01` call_1 `facts_established.budget_vnd` | GT **5.700.000**, khách nói "ngân sách tầm **5 triệu** thôi em" → ITN ra 5.000.000 (`scan_btc_data.py`) | slot `budget_vnd` của ta (5.000.000, đúng lời khách) bị tính sai trong thống kê trích slot; không ảnh hưởng 5 chỉ số bắt buộc | **A1 (khuyên)**: giữ nguyên GT, gửi BTC hỏi 5,7 triệu từ đâu; ghi chú khi báo cáo. **A2**: tạo lớp "errata" cục bộ `test_set/errata.json` (SAMPLE-01.budget_vnd=5.000.000) chỉ áp khi chấm nội bộ — số nộp vẫn theo GT gốc |
| 2 | `SAMPLE-03` call_2 `args_match.order_id=OD682761` | mock chỉ sinh `OD600001…` | từng làm trượt oan | **Đã xong**: BTC nới script chấm 2026-10-20 (chấp nhận mã do `order.create` trả về). Không cần làm gì |
| 3 | `README.md` gói BTC | liệt kê `eval/validate_scenarios.py` nhưng gói không có file này | không tự kiểm kịch bản theo công cụ BTC | **Không sửa**; dùng `scripts/validate_scenarios.py` của nhóm; hỏi BTC xin file |
| 4 | `asr/ground_truth.json` | mô tả D01–D04 "kèm audio" nhưng `asr/audio/` không có file BTC cấp; 4 file `.mp3` trong repo do nhóm TTS | WER trên TTS 1 giọng không đại diện | **Không sửa**; luôn ghi "TTS sạch, giọng Bắc, n = 4"; hỏi BTC audio chính thức có phát trước không |
| 5 | `schemas/tools.schema.json` `order.create` | không có `basket_skus` / nhiều dòng giá, trong khi `pricing.get_quote` có `basket_skus` cho **AIR-2ND-50** → đơn 2 máy không thể tạo đúng giá giảm | đơn nhiều máy phải chuyển nhân viên; SC-GEN-02/TEST-43 không kiểm được đơn đầy đủ | **A1 (khuyên)**: gửi BTC đề nghị thêm `basket_skus` (hoặc `lines[]`); trong lúc chờ giữ hành vi hiện tại (chuyển nhân viên, không tạo đơn sai giá). **A2**: không khuyên — tự thêm tham số vào tool sẽ lệch schema BTC |
| 6 | `mock_tools.pricing_get_quote` (AIR-2ND-50) | **hai máy GIỐNG NHAU cùng nhận −50%.** Chạy: `pricing_get_quote("SKU-AP-PRO", basket_skus=["SKU-AP-PRO"])` → 3.995.000; `order_create(qty=2, basket_skus=["SKU-AP-PRO"])` → `total_vnd` **7.990.000** (= 2 × 3.995.000). Không truyền basket thì `qty=2` → 2 × 7.690.000 = 15.380.000 (AIR-2ND-50 không áp). Theo KM-03/04 kỳ vọng: 7.690.000 (AIR-OCT) + 3.995.000 = **11.685.000** | tổng tiền đơn 2 máy cùng loại có tới 3 đáp án; `total_vnd` của SC-GEN-02 không xác minh được bằng tool | **A1 (khuyên)**: hỏi BTC đáp án đúng; **success_if SC-GEN-02 đã đổi để không phụ thuộc tổng** (chỉ cần báo vượt hạn mức COD 10.000.000đ / chuyển khoản, không tạo đơn COD). `ground_truth_facts.total_vnd=11.685.000` giữ làm ghi chú, ghi rõ "suy từ chính sách, BTC chưa xác nhận" |
| 7 | `dieu-khoan-khuyen-mai.md` / mock (AIR-2ND-50) | không nói rõ: từ máy thứ 3 thì giảm thế nào; máy 1 có nhận AIR-OCT khi máy 2 nhận AIR-2ND-50 không (11.685.000 hay 11.985.000) | mơ hồ khi khách mua ≥ 3 máy | hỏi BTC; hệ thống: ≥ 3 máy → không áp giảm, chuyển nhân viên (đã làm trong `price_basket`) |
| 8 | Cách chấm 7 mẫu BTC cố định | lời khách cố định không trả lời câu hỏi của order gate (địa chỉ, thanh toán…) nên gate chặn tạo đơn → TSR 14,3% (cả baseline) | số TSR của 7 mẫu BTC không phản ánh năng lực; ta tách 2 loại đo | hỏi BTC khi chấm có dùng khách mô phỏng trả lời gate không; nếu không, xin thêm địa chỉ/thanh toán vào lời khách mẫu |
| 9 | `SAMPLE-06` call_2 | `channel: zalo_oa` nhưng thiếu `channel_identity` (validator S8 cảnh báo) | nối định danh Zalo ↔ SĐT dựa vào lời khách | cảnh báo nhỏ; không sửa, nêu khi gửi BTC |

## B. Việc cần bạn quyết

1. Mục 1: A1 (giữ GT, hỏi BTC) hay A2 (thêm errata cục bộ)?
2. Mục 5–7: đồng ý gửi BTC một thư gồm các mục 1, 3, 4, 5, 6, 7, 8, 9?
3. Đồng ý giữ `ground_truth_facts.total_vnd` của SC-GEN-02 = 11.685.000 làm ghi chú chưa xác nhận?

## C. Phát hiện KHÔNG thuộc BTC (lỗi của hệ thống nhóm, ghi để khỏi lẫn)

- `RequestNormalizer`: "ngân sách tầm **5 triệu rưỡi**" (viết số) → `5.000.000 rưỡi` (mất nửa triệu); dạng chữ "năm triệu rưỡi" thì đúng 5.500.000. Chưa sửa (ngoài phạm vi lần dọn dữ liệu này); sẽ làm sai slot `budget_vnd` khi khách gõ "2 triệu rưỡi", "5 triệu rưỡi".
- Bộ kịch bản `custom_test_45` có hàng chục chỗ giá, ngày, khuyến mãi, bảo hành lệch `mock_tools` — đã sửa trong `team_eval` (xem README ở đó).
