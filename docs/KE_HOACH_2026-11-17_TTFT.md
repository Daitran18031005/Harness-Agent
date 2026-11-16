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
