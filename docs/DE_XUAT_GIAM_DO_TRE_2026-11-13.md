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

## 8. Kết quả thực hiện (2026-11-13, chiều)

Đã đọc toàn văn 10/10 nguồn. Speculative Actions đọc bản HTML v2. *The Tail at Scale* trích từ PDF: hedging sau mốc p95 tốn thêm khoảng 5 % tải; ví dụ BigTable gửi bản sao sau 10 ms thì p99.9 giảm từ 1.800 ms xuống 74 ms, chỉ gửi thêm 2 % yêu cầu.

**Nguyên nhân 119 vòng thừa:** đó là "vòng nhắc" (nudge) trong `LLMClient._chat_with_tools`.
- Vòng đầu trả lời không gọi tool, client nhắc model gọi tool, model lặp lại câu trả lời. Mỗi lần mất trọn một vòng LLM trước token đầu.
- Vòng nhắc mặc định bật vì bỏ hẳn thì TSR giảm từ 92,5 xuống 72,5 % (đo 11/11).
- Soát lại các lượt bị nhắc ở lần đo mới: phần lớn là nhắc CÓ ích (sau khi nhắc, model mới gọi `pricing.get_quote`, `handoff.transfer`, `search_policy`). Lượt nhắc vô ích chủ yếu rơi vào lượt bộ đọc bị bỏ qua (lượt khám phá) hoặc khách từ chối.

**Đã sửa (commit 74ccad3, 97761b1; 1054 test đạt):**
- `NUDGE_BY_READER`: bỏ vòng nhắc khi bộ đọc LLM hiểu khách không yêu cầu gì. Hiệu quả rất nhỏ: số lượt bị nhắc giảm từ 19 xuống 18 trên 150 lượt.
- `LLM_HEDGE_MS`: hedging cho vòng stream của LLM chính.
- `LLM_JSON_HEDGE_MS`: hedging cho lời gọi JSON (bộ đọc, chốt).

**Đo tách** trên 39 kịch bản team_eval (lấy mỗi 7 kịch bản một), hai bản chạy song song cùng giờ:

| Lần | Bản | Số lượt | TSR cuộc gọi % | TTFT p50 | TTFT p95 | Total p95 | Bộ đọc p50 / p95 | VND |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | base | 150 | 70,6 | 3192 | 9221 | 10402 | — | 4042 |
| 1 | nudge + hedge stream 1,5 s | 151 | 73,5 | 3265 | 8993 | 10350 | — | 4181 |
| 2 | base | 152 | 76,5 | 3212 | 9042 | 10682 | 2576 / 8415 | 4008 |
| 2 | + hedge JSON 2,5 s | 151 | 70,6 | 3051 | 9339 | 10479 | 2494 / 8060 | 4778 |

**Kết luận:**
- Hai sửa C và D **không** cải thiện p95 một cách đáng kể; chênh lệch nằm trong nhiễu.
- TSR dao động ±6 điểm giữa hai lần chạy base cùng mã, tức nhiễu của mẫu 68 cuộc gọi lớn hơn mọi hiệu ứng ở trên.
- API lúc chạy nhanh: TTFT vòng cuối p50 khoảng 865 ms, ngang m1_final4. Vậy mà TTFT p95 vẫn khoảng 9 s, nên vấn đề nằm ở cấu trúc.

**Gốc rễ thật của đuôi TTFT** (đo trực tiếp bộ đọc, 4 lần gọi):
- Prompt khoảng 2.100 token, đã cache 2.048.
- Đầu ra 72–222 token, mất 2,6–6,8 s, tức khoảng 30 ms/token. Lời gọi không stream nên phải chờ hết phần sinh.
- Prompt đã yêu cầu chỉ ghi khóa khác mặc định, nhưng model vẫn in `null`, `[]`, cùng các trường `*_quote`.
- Hedging không giúp được, vì đuôi không do xếp hàng phía API mà do độ dài đầu ra. Điều này đúng như *Tail at Scale* phân biệt: hedging chỉ chữa biến động do nhiễu, không chữa phần việc vốn đã dài.
- Trong 10 % lượt chậm nhất, thời gian bộ đọc trung bình 4,5 s, và `tool_ms` 2,3 s gồm cả thời gian chờ bộ đọc ở `sync_gate` trước tool đầu tiên.

**Hướng còn lại (cần duyệt):**
1. Rút đầu ra của bộ đọc: thêm ví dụ đầu ra thưa vào prompt, hoặc tách bộ đọc thành câu hỏi ngắn theo giai đoạn. Đây là thay đổi prompt, phải đo TSR.
2. A — bộ đọc không chặn tool đầu và các lượt code xử lý. Đây là thay đổi lớn trong order gate.
3. Đổi model riêng cho bộ đọc sang model sinh nhanh hơn. Đây là thay đổi model, cần duyệt.
4. Chưa chạy 3 × 277: với mã hiện tại, đo tách cho thấy p95 vẫn khoảng 9 s, nên chạy đầy đủ (khoảng 90.000 VND) chỉ xác nhận lại việc chưa đạt ngưỡng.

## 9. Bộ đọc thưa + tool chỉ đọc không chờ bộ đọc (e101c63) — đo tách 13/11 chiều

**Chấm tay độ chính xác bộ đọc** (150 lời khách thật, prompt cũ chạy 2 lần để đo nhiễu). Chi tiết ở `runs/lat_ab3_0113/reader_diff_labels*.csv`.

| Trường | Mới đúng hơn | Cũ đúng hơn | Không rõ |
|---|---:|---:|---:|
| product_sku | 25 | 12 | 3 |
| order_intent | 5 | 2 | 6 |
| affirmed | 9 | 1 | 1 |
| address | 3 | 6 | 0 |

- Lỗi nguy hiểm:
  - Mất SKU khi khách gọi rõ tên: bên cũ 24 lần, bên mới 10.
  - Chốt mua sai: chỉ còn 1 lượt (TEST-01), và cả hai bên cùng mắc.
  - Bị cắt hỏng cả lượt ở trần 220 token: 1 lần. Đã nâng trần lên 300.
- Token đầu ra p50 / p95: 87 / 335 → 53 / 167.

**Đo tách**: 39 kịch bản, chạy song song cùng giờ; cũ = ca9d237, mới = e101c63; mỗi bên 2 lần.

| Lần | TSR % | TTFT p50 | TTFT p95 | Total p95 | Bộ đọc p50 / p95 | VND |
|---|---:|---:|---:|---:|---:|---:|
| cũ a | 70,6 | 3297 | 10334 | 12151 | 2787 / 6661 | 4007 |
| cũ b | 75,0 | 3324 | 10314 | 12391 | 2768 / 7279 | 3923 |
| mới a | 72,1 | 2923 | 8890 | 10750 | 1976 / 3662 | 4121 |
| mới b | 73,5 | 2973 | 9816 | 11291 | 2063 / 4201 | 4206 |

- **Đơn hàng** (mức cuộc gọi, theo `success_if` của kịch bản):
  - Đơn nháp mở ở cuộc không cần đơn: mỗi lần chạy 1 cuộc (TEST-96/call_2), như nhau ở cả 4 lần.
  - Cuộc cần tạo đơn mà không tạo: mỗi lần chạy 1 cuộc (SC-ULTRA-01/call_2 hoặc TEST-141/call_2), cả hai bên đều có.
  - Tạo đơn ở cuộc cấm tạo đơn: 0.
- **Đuôi còn lại** (10 % lượt chậm nhất của bản mới, TTFT trung bình 10,4 s):

  | Thành phần | Thời gian TB |
  |---|---:|
  | Các vòng LLM gọi tool trước token | 4,2 s |
  | Chạy tool | 1,9 s |
  | Chờ bộ đọc tuần tự | 0,9 s |
  | TTFT vòng cuối | 2,1 s |

  Prompt trung bình 10,9k token.
- **TTFT theo số vòng LLM trước token đầu** (bản mới, cả hai lần chạy):

  | Số vòng | Số lượt | TTFT p50 / p95 |
  |---|---:|---:|
  | 0 | 71 | 1,6 / 2,3 s (đạt ngưỡng) |
  | 1 | 117 | 3,8 / 10,7 s |
  | ≥ 2 | 28 | 6,4 / 12,5 s |
  | Code xử lý | 87 | 1,8 / 6,1 s |

## 10. Đo tách e101c63 vs 699d657 (prefetch catalog.search + F2 bật) — 13/11, 39 kịch bản đo độ trễ, mỗi bên 2 lần

**Chưa quyết bật F2.** Toàn bộ hướng tối ưu độ trễ đang tạm dừng để đo hồi quy so với mốc 73958d2.

| | cũ a / b (e101c63) | mới a / b (699d657, F2 bật) |
|---|---|---|
| Số lượt theo số vòng LLM trước token (0 / 1 / ≥ 2 / code) | 36/59/16/40 · 34/60/18/37 | 47/49/11/43 · 48/51/10/41 |
| TTFT p50 | 2,49 / 2,68 s | 2,35 / 2,35 s |
| TTFT p95 | 7,47 / 7,37 s | 6,67 / 6,99 s |
| Total p95 | 9,81 / 9,85 s | 9,10 / 9,49 s |
| TSR (68 cuộc) | 73,5 / 72,1 | 73,5 / 70,6 |
| TTFT lượt có search_policy, p50 / p95 | 6,3 / 10,9 s · 5,9 / 10,2 s | 5,4 / 6,7 s · 5,8 / 8,0 s |
| Đơn mở khi không cần / tạo đơn khi cấm / cần đơn mà không tạo | 1 / 0 / 1 (TEST-89) | 1 / 0 / 1 (TEST-122) |
| Chi phí | 4.150 / 4.126 | 3.988 / 3.888 |

**F2:**
- Số lượt LLM vẫn tự gọi lại đúng tool đã tra sẵn: 15 (bên cũ 13–14). F2 không chặn được.
- Số lượt F2 không ẩn chỉ vì chặn an toàn "số 1–2 chữ số": ước tính 17 mỗi lần chạy (tính lại offline từ trace).

**TEST-122 trượt ở cả 2 lần chạy bản mới:** prefetch chỉ tra máy AirPure X mà bộ đọc chọn nhầm, bỏ qua "Màng lọc thay thế AirPure X/Y" khách gọi tên. Bản sửa 108b85a chưa được đo bằng LLM thật.

Lần đo này chạy cùng mã e101c63 nhưng TTFT p95 khác lần đo trước (7,4 s so với 8,9–9,8 s): API thay đổi tốc độ theo giờ chạy.

## 11. Đo hồi quy 73958d2 (mốc m1_final4) vs HEAD 108b85a — bộ 40 kịch bản chuẩn (runs/ab_ids.txt), 13/11

- Bên HEAD dùng cờ mặc định, `PREFETCH_HIDE_TOOLS` tắt.
- Mỗi bên chạy 2 lần, song song cùng giờ, trần 6.000 VND mỗi lần. Tổng đã chi 23.084 VND.
- **Lần chạy không trọn vẹn:**
  - head-a/b chạm trần.
  - base-b thoát bất thường (timeout API).
  - base-a bị ngắt khi phiên làm việc đóng.
  - Vì vậy chỉ so trên **37/40 kịch bản** có đủ ở cả 4 lần (bỏ SC-TV-18, 19, 20).

| Lần | TSR kịch bản | TSR cuộc gọi | HR giá-KM | over_escalation | TTFT p50 | TTFT p95 | Total p95 | VND/cuộc |
|---|---|---|---|---|---|---|---|---|
| base10 (73958d2, chạy 12/11) | 100 (37/37) | 95,7 (45/47) | 0,0 % | 1 | 2,26 s | 5,13 s | 6,46 s | 57 |
| base-a (73958d2) | 100 (37/37) | 95,7 (45/47) | 8,3 % | 3 | 2,82 s | 7,37 s | 10,04 s | 57 |
| base-b (73958d2) | 94,6 (35/37) | 91,5 (43/47) | 5,4 % | 3 | 2,96 s | 6,93 s | 8,93 s | 57 |
| head-a (108b85a) | 97,3 (36/37) | 93,6 (44/47) | 2,9 % | 4 | 2,26 s | 6,30 s | 8,86 s | 59 |
| head-b (108b85a) | 86,5 (32/37) | 85,1 (40/47) | 7,7 % | 3 | 2,22 s | 6,81 s | 8,77 s | 61 |

**Đọc bảng:**
- **Không thấy tụt có hệ thống.** Chỉ 1 cuộc đạt ở base cả 2 lần mà trượt ở head cả 2 lần: SC-ULTRA-07/call_4. Không có chiều ngược lại.
- **5 cuộc dao động:** SAMPLE-01/call_2, SAMPLE-05/call_2, SC-GEN-06/call_2, SC-TV-10/call_3, SC-TV-16/call_3.
- **Độ trễ:** head nhanh hơn base khi chạy cùng giờ.
- **Không so độ trễ giữa các giờ chạy khác nhau.** base10 và base-a/b là cùng mã 73958d2; base10 nhanh hơn chỉ vì API hôm 12/11 nhanh hơn.
- **VND/cuộc là ước tính hơi cao:** chi phí cộng dồn của cả lần chạy (kể cả kịch bản bị loại) chia cho số cuộc của 37 kịch bản.

**SC-ULTRA-07/call_4**, điều tra từ trace, không gọi LLM:
- Khách hỏi cách mở khóa đẩy 2 chiều và tháo đệm Dacco giặt máy. Tài liệu chính sách và catalog không có nội dung này.
- Cả base lẫn head đều trả lời "em chưa có thông tin chuyên môn" và đều gọi các tool giống nhau (catalog.search, inventory.check, pricing.get_quote); không có lời gọi chạy trước nào.
- Base đạt vì câu đề nghị có nhắc lại chủ đề ("nhờ nhân viên hỗ trợ về cách tháo đệm Dacco giặt máy"), khớp `must_say_any`. Head nói chung chung ("chuyển máy cho nhân viên phụ trách") nên trượt.
- Prompt phần từ chối/chuyển máy không đổi từ commit đầu tiên (086c2d4). 108b85a không tác động vào lượt này: không có lời gọi chạy trước, chỉ đổi nhãn trace.
- Các cuộc 1–3 của kịch bản này giống nhau ở hai bên.
- **Kết luận:** khác biệt nằm ở cách LLM diễn đạt, không quy được cho commit nào từ trace sẵn có. Không sửa, không đề xuất revert.
