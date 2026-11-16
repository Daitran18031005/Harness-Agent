# TTFT p95 toàn hệ thống — các hướng không cần duyệt riêng (17/11)

Mục tiêu: TTFT p95 ≤ 3 s, không làm lệch các chỉ số nộp (m1_final7: TSR 88,6 % trên 3×277, Total p95 7,46 s). Câu đệm và đổi model chờ duyệt, làm cuối.

## Đã cài (mỗi hướng sau cờ riêng, mặc định tắt, toàn bộ test xanh cả khi bật)

| Hướng | Cờ | Commit |
|---|---|---|
| Bộ đọc song song cả khi có đơn nháp | `READER_PARALLEL_DRAFT` | 6d027f4 |
| Tool gộp: catalog.search tự gắn tồn kho + giá | `LOOKUP_BUNDLE` | 8449708 |
| Tra trước chính sách (reranker) + đi được qua MCP | `POLICY_PREFETCH` | d44e9cd, f1e6168 |
| Reranker thay router, nạp sẵn, N=5 | `POLICY_NO_ROUTER` + `VECTOR_BACKEND=qwen_rerank` (+ `POLICY_QUERY_CONTEXT`, `POLICY_ALL_VERSIONS`) | 421b364, 14a54ed |

## Kiểm offline, không làm (17/11)

- **4a giữ kết nối HTTP:** client OpenAI dùng chung cả lần chạy (run_eval.py:144) — đã có.
- **4b/4c thu gọn tool / system prompt:** tool ~2,1 nghìn / 5,2 nghìn token prompt, nhưng 99–100 % lượt trúng cache tiền tố nên phần này gần như không tốn thời gian xử lý; đổi danh sách tool theo lượt còn phá cache. Không làm.
- **5 bộ đọc nhanh hơn:** đầu ra trung vị ~52 token, phần còn lại là mạng + prompt đã cache; chỉ đổi model mới nhanh hơn (cần duyệt).
- **6 bỏ vòng nhắc:** mỗi lần chạy 22–25 lượt bị nhắc (12–19 lượt > 3 s), 12–14 lượt nhắc vô ích. Nhưng bộ đọc không nhận ra lượt nào "không cần gì" (0/29 lượt có bộ đọc) → `NUDGE_BY_READER` không tách được. Bỏ hẳn vòng nhắc đã từng làm TSR 92,5 → 72,5 (ghi chú trong client). Chưa có cách an toàn không cần duyệt.

## Đo chung tất cả cờ (17/11) — runs/ab_all_1117, HEAD f1e6168, 2 đợt × (router mặc định + bật tất cả cờ), chi ~24k VND

Bật: reranker thay router (+ lời khách, mọi phiên bản), POLICY_PREFETCH, READER_PARALLEL_DRAFT, LOOKUP_BUNDLE, EARLY_GATE_TAKEOVER, PARALLEL_TOOLS, PREFETCH_VARIANTS, PREFETCH_HIDE_TOOLS. So 36 kịch bản (cả 4 lần chạm trần).

| | router-a | router-b | tất cả cờ a | tất cả cờ b |
|---|---|---|---|---|
| TSR | 97,2 | 97,2 | 97,2 | 97,2 |
| HR giá/KM % | 11,8 | 13,3 | 0,0 | 13,3 |
| TTFT p50 / p95 (s) | 1,74 / 5,44 | 1,55 / 5,70 | 1,66 / 5,80 | 1,68 / 5,36 |
| Total p95 (s) | 7,57 | 7,52 | 7,84 | 7,26 |
| Lượt > 3 s | 70 | 64 | 60 | 60 |
| Lượt policy p50 (s) | 5,27 | 5,06 | 4,16 | 3,37 |
| Lượt 0 vòng p50 / p95 (s) | 1,23 / 2,22 | 1,25 / 2,22 | 1,46 / 2,29 | 1,47 / 2,68 |

- **TSR, HR, Total p95 không lệch** so với mặc định (không cuộc nào trượt riêng bên bật cờ).
- **TTFT p95 không đổi** (trong nhiễu ±0,3 s). Lượt > 3 s giảm 4–10 mỗi lần chạy; muốn ≤ 3 s cần ≤ ~11.
- Tra trước chính sách chạy 56–58 lượt; lượt policy p50 nhanh hơn 1,1–1,7 s. Cái giá: lượt 0 vòng chậm thêm ~0,22 s p50 do chờ tra trước (tối đa 0,3 s).
- Bộ đọc song song khi có đơn nháp gần như không thêm lượt (134–139 lượt đọc song song ở cả hai bên); tool gộp chỉ chạy 4–6 lượt.
- **Kết luận:** các hướng không cần duyệt đã làm hết; không hướng nào, kể cả cộng lại, kéo được TTFT p95 về ≤ 3 s. Không cần bỏ từng cờ: không cờ nào làm tụt TSR, còn TTFT p95 không đổi nên đo loại trừ không cho thêm thông tin. Còn lại hai hướng chờ duyệt: câu đệm, model nhanh hơn cho vòng gọi tool.
