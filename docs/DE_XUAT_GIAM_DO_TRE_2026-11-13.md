# Điều tra độ trễ và đề xuất giảm TTFT / Total (2026-11-13)

Trạng thái: **ĐỀ XUẤT — chờ duyệt.** Chưa sửa code. Chưa chạy đo đầy đủ. Đã dùng một lần đo thử API (8 lời gọi, dưới 50 VND).

## 1. Ngưỡng của BTC

Nguồn: `DIEU-CHINH-DE.md` và `eval/huong-dan-do-latency.md`.

| Chỉ số | Ngưỡng M1 |
|---|---|
| TTFT p95 | ≤ 3 s |
| Total p95 | ≤ 8 s |

- TTFT p50 không có ngưỡng, nhưng vẫn theo dõi.
- Cách đo: đo tại ranh giới harness, bỏ 3 lượt warm-up, chấm bằng `reference_eval.py`.

## 2. Nguyên nhân TTFT p95 tăng từ khoảng 6 s (m1_final4/5) lên khoảng 10,4 s (m1_final6)

**Kết luận: nguyên nhân là API OpenAI chậm hơn tại thời điểm chạy, không phải do thay đổi trong code.**

| | m1_final4 | m1_final5 | m1_final6 |
|---|---:|---:|---:|
| Giờ chạy (VN) | khoảng 19–20 h, 12/11 | khoảng 22 h, 12/11 | 03:31–04:47, 13/11 |
| TTFT p50 / p95 (ms) | 2537 / 6037 | 2378 / 6055 | 3481 / 10351 |
| **TTFT thuần của API ở vòng cuối, p50 (ms)** | 758–826 | 728–751 | **1504–1920** |
| Một vòng LLM có tool, p50 / p95 (ms) | 1403 / 2523 | 1365 / 2506 | 2782 / 4697 |
| Prompt tokens TB | 6894 | 7217 | 6942 |
| Tỉ lệ lượt: code xử lý / 0 vòng / 1 vòng / ≥2 vòng trước token | 25 / 27 / 35 / 14 % | 23 / 26 / 37 / 15 % | 24 / 28 / 34 / 14 % |
| Tỉ lệ lượt phải chờ bộ đọc tuần tự | 42 % | 43 % | 41 % |

- **Cấu trúc không đổi:** số vòng LLM trước token, kích thước prompt và tỉ lệ lượt chờ bộ đọc đều giữ nguyên.
- **Từng lời gọi API chậm hơn khoảng 2–2,3 lần.** Điều này đồng đều trên cả 9 shard của m1_final6, và không có lần nào chạy nhanh.
- **Đo thử lúc 12:12 ngày 13/11** (8 lời gọi streaming, prompt khoảng 3k token): TTFT p50 1476 ms. API vẫn đang chậm hơn tối 12/11.
- **Hệ quả cho yêu cầu "độ lệch ≤ 3 %":**
  - Độ trễ phụ thuộc rất nhiều vào tải phía OpenAI (lệch 2 lần theo giờ), nên nhóm không kiểm soát được hoàn toàn.
  - Giảm nhẹ bằng cách chạy 3 lượt liền nhau trong cùng một khung giờ, và đo thử API trước mỗi lượt rồi ghi vào báo cáo.

## 3. Khoảng cách về cấu trúc (có cả khi API nhanh)

Ngay cả m1_final4, chạy lúc API nhanh, vẫn có TTFT p95 6,0 s, gấp đôi ngưỡng. Phân rã thời gian trên 2180 lượt của m1_final6:

| Nhóm lượt | Số lượt | TTFT p50 | TTFT p95 |
|---|---:|---:|---:|
| 0 vòng LLM trước token | 609 | 2110 | 3690 |
| 1 vòng (LLM gọi tool rồi mới trả lời) | 737 | 5336 | 10531 |
| ≥ 2 vòng | 307 | 7715 | 13254 |
| Code xử lý (gate/đơn) | 527 | 2407 | 7394 |
| Lượt đầu cuộc gọi | 968 | 4382 | 11196 |

**5 % lượt chậm nhất** (TTFT TB 12,4 s) gồm:

| Thành phần | Thời gian TB |
|---|---:|
| Các vòng LLM gọi tool | 6,3 s |
| Bộ đọc tuần tự | 3,6 s |
| Chạy tool | 1,7 s |
| TTFT vòng cuối | 2,1 s |

Prompt của nhóm này trung bình 15,7k token.

**Tool mà LLM tự gọi ở vòng trước token** (1044 lượt):

| Số lượt | Tool |
|---:|---|
| 126 | chỉ `pricing.get_quote` |
| 74 | chỉ `catalog.search` |
| 72 | chỉ `search_policy` |
| 67 | chỉ `pricing.quote_order` |
| 68 | chỉ `handoff.transfer` |
| 43 | chỉ `product.shortlist` |
| 260 | combo `catalog.search` + `inventory.check` + `pricing.get_quote` |

- **119 lượt có vòng trước token nhưng không có lời gọi tool mới nào.** Vòng đó là thừa, cần tìm nguyên nhân.
- **Phần chạy trước tool bằng code** (`SPECULATIVE_TOOLS`) hiện chỉ đoán `inventory.check` và `pricing.get_quote`. Chỉ 357/1044 lượt có lời gọi chạy trước, và LLM vẫn tự gọi `catalog.search`, `search_policy`, `product.shortlist`.

**Kết luận:** ngưỡng 3 s chỉ đạt được nếu phần lớn lượt bắt đầu sinh token mà không phải chờ một vòng LLM gọi tool, và không phải chờ bộ đọc.

## 4. Tài liệu tham khảo

| Kỹ thuật | Nguồn | Kết quả báo cáo |
|---|---|---|
| Gọi hàm song song theo đồ thị phụ thuộc | Kim et al., *An LLM Compiler for Parallel Function Calling*, ICML 2024, [arXiv:2312.04511](https://arxiv.org/abs/2312.04511) | Nhanh hơn ReAct tới 3,7 lần; nhanh hơn parallel function calling của OpenAI tới 1,35 lần |
| Gọi hàm bất đồng bộ | Gim et al., *Asynchronous LLM Function Calling*, [arXiv:2412.07017](https://arxiv.org/abs/2412.07017) | Giảm độ trễ 1,6–5,4 lần trên BFCL |
| Thực thi đoán trước, có kiểm chứng (không làm sai kết quả) | *Speculative Actions*, [arXiv:2510.04371](https://arxiv.org/pdf/2510.04371) | Nhanh hơn tới 20 % end-to-end |
| Gọi tool đoán trước với API hộp đen | *Optimizing Agentic LM Inference via Speculative Tool Calls*, [arXiv:2512.15834](https://arxiv.org/html/2512.15834v1) | Có mô hình phân tích khi nào lợi |
| Đoán trước theo mẫu | PASTE, [arXiv:2603.18897](https://arxiv.org/html/2603.18897v1) | Giảm 55 % độ trễ tool TB |
| Đoán trước cho agent tìm kiếm | SPAgent, [arXiv:2511.20048](https://arxiv.org/abs/2511.20048) | Cảnh báo: đoán sai làm tăng độ trễ tới 26 % |
| Giữ lại tool có tác dụng phụ cho tới khi xác thực | *Speculative Interaction Agents*, [arXiv:2605.13360](https://arxiv.org/html/2605.13360) | Nguyên tắc an toàn |
| Đoán trước có bộ nhớ | *Speculate with Memory*, [arXiv:2607.12236](https://arxiv.org/pdf/2607.12236) | Giảm 28 % lên hơn 50 % (ALFWorld) |
| Gửi yêu cầu dự phòng để cắt đuôi | Dean & Barroso, *The Tail at Scale*, CACM 2013 ([tóm tắt](https://blog.acolyer.org/2015/01/15/the-tail-at-scale/)); hedging trong [gRPC](https://grpc.io/docs/guides/request-hedging) | Gửi bản sao sau mốc p95 chỉ tốn thêm khoảng 2–5 % tải mà cắt đuôi rất mạnh |
| Prompt caching cho agent dài | *Don't Break the Cache*, [arXiv:2601.06007](https://arxiv.org/pdf/2601.06007); *Auditing Prompt Caching*, [arXiv:2502.07776](https://arxiv.org/abs/2502.07776) | Giữ prefix ổn định thì cache trúng và TTFT giảm |

## 5. Đề xuất thay đổi (chờ duyệt)

Mỗi thay đổi có cờ môi trường riêng để đo tách (ablation). Không đổi model, không đổi kiến trúc tổng thể.

**A. Bộ đọc không bao giờ chặn token đầu**
- Hiện nay, khi có đơn nháp đang mở, bộ đọc chạy tuần tự (`orchestrator.py:410–415`, `:497`).
- Đề xuất:
  - Luôn chạy bộ đọc song song với LLM chính.
  - Nếu kết quả đọc dẫn tới quyết định khác (ví dụ khách đồng ý, code chốt đơn), bỏ bản nháp của LLM và đi theo nhánh code. Bản nháp chưa được phát token nào ra ngoài cho tới khi bộ đọc xong. Cách này là "đoán trước có kiểm chứng" của Speculative Actions.
- Rủi ro: thêm chi phí cho các lượt LLM bị bỏ. Sẽ đo tỉ lệ bỏ.
- Điểm cần duyệt: nếu bộ đọc chậm hơn LLM thì token đầu vẫn phải chờ bộ đọc, vì không được phát câu trả lời có thể sai. Phần lợi là thời gian chạy chồng lên nhau, không phải bỏ hẳn thời gian chờ.

**B. Mở rộng chạy trước cho tool CHỈ ĐỌC, chạy song song**
- Thêm `catalog.search`, `search_policy` (truy hồi chính sách theo câu khách) và `product.shortlist` vào phần code chạy trước, song song với bộ đọc.
- Đầu vào lấy từ thực thể LLM-first đã có (bộ đọc / ứng viên SKU), không thêm regex theo câu khách.
- LLM vẫn có quyền gọi thêm tool. Kết quả chạy trước chỉ là ngữ cảnh.
- **Không bao giờ** chạy trước các tool ghi: `order.*`, `handoff.transfer`, `schedule.callback`.

**C. Bỏ vòng LLM thừa**
- Điều tra 119 lượt có vòng trước token mà không có tool mới (có thể là vòng nhắc lại của gate hay retry), rồi sửa tận gốc.

**D. Gửi yêu cầu dự phòng (hedged request) cho lời gọi LLM**
- Nếu sau mốc khoảng p90 (dự kiến khoảng 2 s, chỉnh bằng cờ) chưa có token đầu, gửi một bản sao, lấy bản về trước và hủy bản kia.
- Chi phí dự kiến thêm ≤ 10 %.
- Có tác dụng trực tiếp lên p95 khi API dao động.

**E. Gọn prompt ở đuôi**
- Các lượt có prompt ≥ 12k token: rút gọn kết quả tool cũ trong lịch sử (giữ trường dùng để trả lời) và giữ prefix cố định để cache vẫn trúng.

**Không làm:**
- **Không chèn câu đệm cố định** kiểu "Dạ em kiểm tra" trước khi gọi tool để TTFT trông nhỏ. Làm vậy là đo sai định nghĩa "token đầu tiên của câu trả lời".
- **Không đổi model:** việc này cần một đề xuất riêng.
- **Không thêm luật if-else theo kịch bản hoặc theo ground truth.**

## 6. Ước lượng và rủi ro

| Bối cảnh | Ước lượng |
|---|---|
| API nhanh (m1_final4) | Lượt 0 vòng, không chờ bộ đọc có p95 1,85 s. Nếu A+B+C đưa phần lớn lượt về dạng này, TTFT p95 ≤ 3 s là khả thi |
| API chậm (m1_final6) | Cùng nhóm lượt có p95 2,8 s, sát ngưỡng. Phụ thuộc thêm vào D |

- Total p95 ≤ 8 s: hiện 12,4 s; m1_final4 là 7,3 s. A+B+C cũng giảm Total vì bớt vòng.
- **Độ chính xác:**
  - Nguy cơ chính ở A (nhánh code và nhánh LLM lệch nhau) và ở B (thêm ngữ cảnh làm LLM trả lời khác).
  - Giảm rủi ro: mỗi thay đổi đo riêng trên khoảng 40 kịch bản trước khi gộp.
- **Tái lập ±3 %:**
  - TSR giữa các lượt đo đã dao động hơn 3 % tương đối: m1_final4 là 76,9–81,6; m1_final6 là 87,9–92,1 trên phần đã chạy. Nguyên nhân là OpenAI không tất định dù đã đặt temperature 0 và seed.
  - Độ trễ phụ thuộc giờ chạy (mục 2).
  - Sẽ báo trung bình và khoảng dao động trung thực, không chọn lượt đẹp.

## 7. Kế hoạch kiểm chứng (sau khi được duyệt)

1. **Từng thay đổi:** test đơn vị, chạy toàn bộ test, commit riêng từng file của mình.
2. **Đo tách bằng LLM thật** trên khoảng 40 kịch bản (bộ so sánh đã dùng ở 12/11), mỗi cờ bật/tắt. Trần tổng 10.000 VND.
3. **Đo đầy đủ 3 × 277 kịch bản** chạy liền nhau, trần 120.000 VND.
   - Mỗi lượt khoảng 29.500 VND, cộng hedging khoảng 10 %, tổng dự kiến khoảng 98.000.
   - Đo thử API trước mỗi lượt.
   - Báo: TSR, HR giá-KM, TTFT p50/p95, Total p95 từng lượt và trung bình, so với m1_final4/5/6.

Ghi chú: yêu cầu ghi "227 kịch bản"; tôi hiểu là 277 (bộ public_sample + team_eval đang dùng).
