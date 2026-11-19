# Kế hoạch TTFT p95 ≤ 3 s (M1) → nền cho TTFA p95 ≤ 2,5 s (M2) — 19/11/2026, hạn nộp 28/11

Mọi số dưới đây đo **offline** trên trace m1_final9 (3×277, 3.242 lượt, commit d11210c) hoặc bằng LLM giả, không gọi LLM thật. Cách tính p95 như `reference_eval.py`. Cần còn ≤ 163 lượt > 3 s.

## 1. TTFT đang tốn ở đâu

| Thành phần (lượt có LLM) | mọi lượt p50 / p90 | lượt > 3 s p50 / p90 |
|---|---|---|
| Chuẩn bị (từ lúc nhận lượt tới vòng LLM đầu, + khoảng hở giữa các vòng) | 458 / 1.004 ms | **749 / 1.347 ms** |
| Vòng LLM chọn tool (khi có) | 1.320 / 1.911 ms | 1.438 / 2.312 ms |
| Chạy tool | 39 / 866 ms | 489 / 1.111 ms |
| Vòng cuối → token đầu | 801 / 975 ms | 764 / 919 ms |

Lượt code trả lời không qua LLM (1.062 lượt): p50 1,31 s, chỉ 30 lượt > 3 s.

**Phát hiện mới — phần chuẩn bị là code Python, không phải LLM.** Chạy cả hệ thống với LLM giả trả lời ngay (`scripts/probes/prep_profile.py`, 40 kịch bản, 153 lượt, 0 VND): thời gian trước LLM vẫn p50 621 / p90 1.029 ms. cProfile: gần hết nằm ở `asr_entities.product_mentions` — dò tên sản phẩm bằng `difflib.SequenceMatcher` trên mọi cửa sổ 1–7 từ × mọi alias (~12.000 lần `ratio()` mỗi câu), gọi 5 chỗ mỗi lượt (ứng viên cho bộ đọc ×1–3, tra trước, F2), có chỗ chạy trên cả câu trả lời trước của nhân viên (dài). Python thuần giữ GIL → làm chậm luôn reranker chạy song song (đã thấy 17/11: reranker 236 ms rảnh → 3,9 s khi luồng Python bận) — giải thích tool `search_policy` p50 489 ms ở lượt chậm.

Các bước khác trước LLM (đo bằng bộ đếm): catalog.search qua MCP 13,8 lần/lượt × 3,7 ms = 51 ms; memory.get_call_brief qua MCP 6 lần/lượt × 4,8 ms = 29 ms; Call Brief 15 ms; nhận diện 12 ms; dựng prompt 0,1 ms.

## 2. Mô phỏng các hướng (trên trace m1_final9, gốc p95 3.843 ms / 556 lượt > 3 s)

| Hướng | p95 | lượt > 3 s |
|---|---:|---:|
| Chuẩn bị ≤ 250 ms | 3.317 | 323 |
| + tool chính sách ≤ 300 ms | 3.227 | 254 |
| + mỗi vòng LLM nhanh hơn 20 % | **2.802** | 111 |
| + mỗi vòng LLM nhanh hơn 30 % | 2.658 | 73 |
| Chỉ đổi vòng LLM ×0,6 (không sửa code) | 3.006 | 164 |
| Trả lời đoán trước song song (tool đọc, phủ 100 %) | 3.691 | 417 |
| Bỏ vòng chọn tool ở mọi lượt (cận dưới, 19/11 sáng) | 2.699 | 116 |

→ Đường thực tế: **(A) gỡ phần chuẩn bị bằng code (0 VND) + (B) bớt ~20 % mỗi vòng LLM**. "Trả lời đoán trước" lợi ít, bỏ.

## 3. Các hướng, xếp theo thứ tự làm

### A. Code (không đổi hành vi, không tốn LLM) — làm trước
1. **`product_mentions` nhanh hơn, kết quả y hệt:** lọc bằng `real_quick_ratio()` / `quick_ratio()` (cận trên của `ratio()`) trước khi tính `ratio()`, giữ chuỗi `w` cố định trong `SequenceMatcher` (`set_seq1` đổi alias); nhớ kết quả theo văn bản trong lượt (`lru_cache`) vì cùng câu được dò nhiều lần. Kiểm: so kết quả cũ/mới trên mọi câu khách + câu nhân viên trong trace m1_final8/9 — phải trùng 100 %. Số đo: xem mục 5.
2. **Giảm gọi lặp qua MCP trước LLM:** catalog.search 13,8 lần/lượt, get_call_brief 6 lần/lượt → nhớ trong lượt. ~50–80 ms.
3. **Đo lại tool `search_policy`** sau A1 (hết tranh chấp GIL). Kỳ vọng về ~250–300 ms.
4. **Ghi tách phần chuẩn bị vào trace** (`latency_detail.pre_llm_ms`, `between_rounds_ms`) để lần đo LLM sau thấy ngay.
Kiểm: `prep_profile.py` (0 VND) trước/sau; toàn bộ test.

### B. Bớt ~20 % thời gian mỗi vòng LLM — cần đo thật (xin duyệt)
- **Đo lại WebSocket mode (`LLM_WS`)** sau A: 18/11 vòng p50 1,30 → 1,19 s (−8 %) nhưng p95 lượt bị nhiễu bởi phần chuẩn bị; nay phần đó đã gỡ thì so được sạch hơn.
- **Rút đầu ra vòng chọn tool:** vòng gọi tool = token đầu (~0,8 s) + sinh JSON tham số. Đo số token đầu ra của vòng tool (chưa ghi trong trace) rồi xem bỏ được tham số thừa / mô tả dài trong schema không.
- **Thử nhà cung cấp/model nhanh hơn — chỉ khi đo từ máy mình:** số công bố khác nhau nhiều theo vị trí (Groq gpt-oss-120b: token đầu trung vị 0,8 s từ São Paulo nhưng 1,5 s từ Tokyo); Azure gpt-4o-mini token đầu chậm hơn OpenAI (Artificial Analysis ~1,8 s vs ~1,0 s). Đề bài cho tự chọn model/tier, cấm fine-tune; đổi model thì phải chạy lại baseline cùng model. Bước đầu: probe 1 lượt × vài model (≤ ~500 VND), cùng prompt thật.
- `tool_choice` dạng `allowed_tools` (Chat Completions có) giữ nguyên danh sách tool → có thể không phá cache khi muốn giới hạn tool theo lượt; chưa kiểm chứng ảnh hưởng tới cache.

### C. Nền cho TTFA ≤ 2,5 s (M2)
TTFA = (VAD báo dừng nói) → chốt ASR → LLM tới cụm từ đầu đủ để đọc → TTS ra audio đầu (VieNeu v3 turbo int8: ~115 ms GPU / ~140 ms CPU) → phát.
Ngân sách: 2,5 s − ASR chốt ~0,25 s − TTS ~0,15 s − cụm từ đầu ~0,1 s ⇒ **LLM TTFT p95 cần ≈ ≤ 2,0 s**, chặt hơn M1 ~1 s. Hướng:
1. **Chạy trước trên bản ASR tạm (preemptive):** mọi việc làm TRƯỚC lúc VAD báo dừng không tính vào TTFA. Khi có bản ASR tạm ổn định: chạy chuẩn bị (A), bộ đọc, tra trước, thậm chí vòng LLM chọn tool; bản cuối khác thì bỏ. LiveKit Agents bật mặc định ("preemptive generation"); lợi phụ thuộc độ dài câu khách.
2. **ASR streaming + endpointing** (gipformer hiện chạy theo file).
3. **TTS từng cụm:** cắt câu trả lời ở dấu phẩy/chấm đầu tiên rồi đọc ngay; guardrail phải duyệt theo cụm (hiện chạy sau khi sinh xong — CHECKING.md).
4. **GPU dùng chung:** ASR + reranker + TTS trên RTX 4060, M2 cần ≥ 2 phiên → cân nhắc TTS đường CPU int8.
A và B của M1 là điều kiện cần cho C.

## 3b. Rà tài liệu (20/11) — OpenAI Latency optimization (7 nguyên tắc), Conveyor (arXiv 2406.00059), LLMCompiler (ICML 2024), Predicted Outputs, Tail at Scale
- Thời gian bộ đọc (replay 100 câu, Fast): bản gốc ≈ 751 ms + 10,2 ms × token ra; bản gọn ≈ 698 + 6,6 ms/token → phần CỐ ĐỊNH ~0,7 s (mạng + xử lý prompt đã cache + hàng đợi) chiếm phần lớn; ms/token không cố định theo loại token (giả thuyết: giải mã đoán trước phía OpenAI làm token dễ đoán — chép nguyên văn, khóa JSON — rẻ hơn; chưa kiểm chứng).
- Gửi bản sao bộ đọc khi chậm (hedging, mô phỏng trên phân bố replay): sau 1,2 s p95 2.390 → 2.261 ms nhưng thêm 54 % lời gọi; sau 1,5 s gần như không đổi → đuôi do đầu ra dài, bản sao cũng chậm. Không làm.
- Tham số tool vòng chọn tool ngắn (search_policy p50 23 ký tự, order.update 112); handoff.transfer dài (624) là do code tự điền brief sau — vòng chuyển máy p50 1.329 ms ≈ lượt khác 1.323. Không có gì để bớt.
- Chạy tool sớm kiểu Conveyor — ước tính trước khi cài (20/11, trace m1_final10): 75 lượt vòng 1 có ≥ 2 lời gọi (23 lượt > 3 s; 27 là 2 × search_policy). Lợi = thời gian LLM sinh tham số các lời gọi sau (tham số ngắn, ~0,1–0,2 s) → bớt 100–200 ms chỉ gỡ 1–2 lượt (p95 3.055 → 3.048), 400 ms gỡ 5 lượt. Conveyor lợi khi phần giải mã dài (sinh code, kế hoạch) — không phải trường hợp này. **Không cài.**
- **Predicted Outputs cho bộ đọc (20/11, duyệt ≤ 2.800, chi ≈ 2.460 VND)** — cờ `READER_PREDICT` (mặc định tắt), nháp = lời khách. Thử tương thích: API từ chối `response_format` đi cùng `prediction` (400, không tính tiền) → khi có nháp bỏ chế độ JSON (prompt vẫn đòi JSON; bóc khối ```json```); 100/100 câu vẫn ra JSON hợp lệ. Replay 100 câu, hai bản chạy cùng lúc:

  | | bản gốc | có nháp |
  |---|---:|---:|
  | ms p50 / p90 / p95 | 1.176 / 1.978 / 2.258 | 1.188 / 2.196 / 2.448 |
  | token nháp được nhận / bị loại (tổng 100 câu) | — | **26 / 1.524** |
  | câu khác bản gốc ở ≥ 1 trường chính | — | 23/100 |

  Nhiễu cùng prompt (bản gốc lần 1 vs lần 2 cùng ngày) là **25/100** → có nháp đọc như bản gốc, nhưng gần như không token nào được nhận (đầu ra là JSON ngắn, trích dẫn vài từ — không trùng thứ tự với lời khách) → không nhanh hơn, p95 chậm hơn, trả tiền thêm cho token bị loại. **Không dùng.** (Nhiễu 25/100 cũng là mốc đúng để đọc lại READER_COMPACT: 61/100 vẫn cao hơn nhiều.)
- **Tool tra sản phẩm "564 ms" (20/11, offline):** không phải tool chậm — `READ_ONLY_TOOLS` chỉ có inventory.check / pricing.get_quote / catalog.search / search_policy, nên pricing.quote_order (p50 167, tối đa 2.020 ms), order.status (tối đa 6.544 ms), product.shortlist, crm.get_customer phải CHỜ BỘ ĐỌC (sync_gate) dù chỉ đọc. Mock BTC của cả bốn không ghi gì. **Đã sửa:** thêm vào READ_ONLY_TOOLS (1.135 test OK). Mô phỏng: 32 lượt hưởng lợi, 63 → 59 lượt > 3 s, p95 3.055 → 3.037.
- **LOOKUP_BUNDLE (xem lại 20/11):** 25 lượt ≥ 2 vòng ở m1_final10 (16 lượt > 3 s); dạng hay gặp nhất `catalog.search → pricing.get_quote` (9) vì mặc định chỉ gắn giá/tồn khi tìm ra đúng 1 sản phẩm không biến thể. Bỏ sót: tìm ra 2 sản phẩm (AirPure X + màng lọc; 5 lượt) và sản phẩm có biến thể khách đã nêu size/màu (RunLite 2 Pro size 41 đen…; 6 lượt, có lượt 4,0–4,2 s). LOOKUP_BUNDLE phủ cả hai. Cận trên (bỏ trọn vòng 2 ở 11 lượt) cộng hai sửa trên: **p95 3.022, 57 lượt** (cần ≤ 55). Chưa đo LLM.
- **m1_final11 (1×277, commit df0b8db + LOOKUP_BUNDLE=on, 20/11 02:11–02:58, chi 59.042 VND) — LẦN ĐẦU p95 ≤ 3 s trên cả bộ:**

  | | m1_final10 | **m1_final11** |
  |---|---:|---:|
  | TTFT p50 / p95 | 1.396 / 3.293 ms | 1.366 / **2.865 ms** |
  | Lượt > 3 s (cần ≤ 55) | 86 / 1.082 | **40 / 1.080** |
  | Lượt > 2,8 s | 140 | 66 |
  | Lượt ≥ 2 vòng tool | 25 | 16 |
  | Total p95 | 4.300 | 4.005 |
  | TSR / ca khó | 86,6 / 85,2 | 86,6 / 85,2 |
  | HR giá&KM / CCR / RQR / guardrail | 17,5 / 69,1 / 0,0 / 13 | 16,3 / 67,9 / 0,4 / 12 |
  | Call Brief p95 | 44 ms | 18 ms |
  | Vòng chọn tool / vòng cuối p50 | 1.324 / 808 | 1.282 / 781 (API nhanh hơn ~3 %) |

  TSR không đổi. 1 lượt chạy: p95 dao động ±0,1 s giữa các lượt (m1_final9: 3,80–3,95) → cần 3 lượt để chốt số nộp; biên hiện có 15 lượt.
- Còn lại chưa thử: (b) Predicted Outputs cho bộ đọc (không dùng được với tool; chưa rõ hợp json_object), cần probe nhỏ; (c) câu báo tiến độ thật ("Dạ em đang kiểm tra tồn kho") — OpenAI khuyên (nguyên tắc 6) nhưng chủ dự án đã loại vì định nghĩa "token đầu của câu trả lời" của BTC → chỉ làm nếu BTC xác nhận được tính.

## 4. Không làm / đã loại
- Câu đệm cố định ("Dạ em kiểm tra…") — chủ dự án loại (sai định nghĩa token đầu).
- Fine-tune model nhỏ — đề cấm.
- Bộ phân loại nhỏ thay vòng chọn tool, chặn search_policy theo reranker — đã thử 19/11, lợi ≤ 0,1 s (KE_HOACH_2026-11-17_TTFT.md).
- Semantic cache câu trả lời — dữ liệu đổi theo khách/ngày, rủi ro trả nhầm.

## 5. Số đo bổ sung
- **A1 thử nghiệm (19/11, bản thử `pm_fast_probe.py`, chưa sửa code):** 4.529 câu (lời khách + câu nhân viên ≤ 400 ký tự, m1_final8/9): bản cũ **349 ms/câu**, bản lọc cận trên **46 ms/câu** (×7,6), **khác kết quả 0/4.529**. Mỗi lượt gọi ~3–5 lần → kỳ vọng gỡ ~1 s CPU/lượt (một phần chạy ở luồng bộ đọc nhưng vẫn giữ GIL). Cộng nhớ kết quả theo văn bản trong lượt thì còn ~1–2 lần tính thật/lượt.
- **Nhóm A đã làm (19/11, chưa commit, chưa đo LLM thật):**
  - A1 `asr_entities.product_mentions`: lọc cận trên + `lru_cache(512)` theo văn bản (trả list mới mỗi lần). So với bản HEAD trên 500 câu trace (cả câu nhân viên dài): khác 0/500, 706 → 52 ms/câu, lần gọi lại ~0 ms. Khóa ASR cập nhật `asr-rules-v2.1-2026-11-19` (không đổi luật; test D01–D04 vẫn đúng).
  - A2 `_product_info`: cache tên/danh mục dùng chung mọi phiên (không lưu khi cổng tool lỗi) — catalog.search trước LLM 10,5 → ~0 lần/lượt sau lượt đầu.
  - A3 trace: `latency_detail.pre_llm_ms` (code trước vòng LLM đầu).
  - Đo bằng LLM giả, 40 kịch bản, 153 lượt (`runs/prep_profile_1119/`):

    | | trước | A1 | A1 + A2 |
    |---|---:|---:|---:|
    | trước LLM p50 / p90 / p95 (ms) | 621 / 1.029 / 1.264 | 58 / 131 / 141 | **51 / 84 / 113** |
    | gọi MCP trước LLM (ms/lượt) | 92 | 53 | 36 |
    | thời gian cả lần chạy (s) | 124 | 24 | 21 |

  - Hành vi: câu trả lời + tool + ghi nhớ của 153/153 lượt y hệt bản trước (LLM giả, tất định). 1.131 test OK.
  - Còn lại trước LLM: memory.get_call_brief 6 lần/lượt (~18 ms) — không cache vì phải thấy ngay dữ liệu vừa ghi.
- **A/B nhóm A bằng LLM thật (19/11 21:37–22:02, duyệt ~27k, chi ≈ 26.000 VND)** — `runs/ab_prep_1119`: mốc HEAD 344f386 (worktree) vs bản sửa, 40 kịch bản `ab_ids.txt`, xen kẽ theo nửa (base1, fix1, base2, fix2); nửa sau hai bên chạm trần 6.750 → bỏ kịch bản dở, so 38 kịch bản chung (227 lượt, bỏ 3 lượt khởi động khi tính TTFT).

  | | mốc | nhóm A |
  |---|---:|---:|
  | TTFT p50 / p95 | 1.728 / 3.599 ms | **1.088 / 2.946 ms** |
  | Lượt > 3 s | 33/224 (14,7 %) | **10/224 (4,5 %)** |
  | Total p95 | 4.791 ms | 4.033 ms |
  | Chuẩn bị p50 / p90 | 616 / 1.327 ms | **99 / 219 ms** (pre_llm_ms 98 / 206) |
  | Vòng chọn tool p50 / p90 | 1.188 / 1.556 | 1.211 / 1.595 (API ngang nhau) |
  | Vòng cuối → token đầu p50 | 768 | 782 |
  | Tool ở lượt LLM gọi search_policy p50 / p90 | 605 / 2.024 | 544 / 1.944 (gần như không đổi) |
  | TSR / HR giá&KM / CCR / guardrail (reference_eval, 38 kịch bản) | 89,5 / 12,5 / 75,3 / 4 | 94,7 / 0,0 / 76,5 / 4 |

  - Lợi đến đúng từ phần chuẩn bị (−517 ms p50); tốc độ API hai bên như nhau. TSR/HR lệch là nhiễu 38 kịch bản (hành vi đã kiểm y hệt bằng LLM giả).
  - **m1_final10 (1×277, commit 28f3029, 19/11 22:05–23:00, chi 58.647 VND):** TTFT p50 / p95 **1.396 / 3.293 ms** (m1_final9: 1.766–1.813 / 3.803–3.953), lượt > 3 s 86/1.082 = 7,9 % (cần ≤ 55), Total p95 4.300 ms (m1_final9 4.769–4.988), TSR 86,6 % (m1_final9 87,0–88,8; 1 lượt — chưa tách được nhiễu), HR 17,5 %, CCR 69,1 %, guardrail 13, Call Brief p95 44 ms. **Chưa đạt ≤ 3 s.**
  - 86 lượt > 3 s: order.update 28 (tool chờ p50 937 ms — chờ bộ đọc + việc của order gate trong `sync_gate()`), search_policy 16 (tool p50 568 ms), vòng 1 không lời gọi hợp lệ 11, báo giá 9… Phần chuẩn bị chỉ còn p50 100 ms.
  - Mô phỏng tiếp trên trace m1_final10: order.update ≤ 150 ms → 3.037 / 58 lượt; + search_policy ≤ 300 ms → **2.948 / 46**; + mỗi vòng LLM −10 % → 2.714 / 31. Chỉ LLM −15 % → 2.942.
  - **Điều tra 2 chỗ chờ tool (19/11 đêm, offline, 0 VND):**
    - order.update chậm = lượt **đổi size** (42/49 lượt; update_address chỉ p50 124 ms): `_return_window_expired` gọi LLM `days_since_received` NỐI TIẾP trong tool (p50 tool 582 ms; lượt đọc muộn 1.014 ms vì còn chờ bộ đọc). Sửa: `RECEIVED_PREFETCH` (mặc định bật) — khách có `order_id` trong brief (95/1.082 lượt; phủ 43/43 lượt đổi hàng) → chạy sẵn lời gọi này từ đầu lượt trên đúng chuỗi lời khách, tool dùng kết quả đó. Thêm ~95 lời gọi LLM ngắn mỗi 277 kịch bản. Test: `test_exchange_after_return_window_is_refused` kiểm dùng kết quả đọc sẵn, không gọi LLM lần hai. 1.131 test OK. Chưa đo LLM thật.
    - search_policy: đo riêng (`scripts/probes/policy_latency_probe.py`) p50 248 ms khi gọi liên tiếp (qua MCP hay trong tiến trình như nhau), 400–550 ms khi nghỉ 2 s giữa các lần và tăng dần theo thời gian chạy; giữ ấm GPU / CPU không đổi → do máy (nhiệt/nguồn), không sửa bằng code. 27/57 lượt chính sách LLM tra 2 câu nối tiếp (p50 719 ms) — gộp 2 câu vào một lần chấm reranker cần thêm tool phía mcp-memory; để sau. `RERANK_POOL_N` đã là 5.
  - **A/B RECEIVED_PREFETCH (19–20/11 23:33–00:09, duyệt ≤ 40k, chi ≈ 39.500 VND)** — `runs/ab_recv_1120`: cùng code, cờ tắt/bật, 65 kịch bản (40 ab_ids + 27 đổi hàng), xen kẽ theo nửa; 3/4 phần chạm trần → so 61 kịch bản chung (24 đổi hàng, 326 lượt).

    | | tắt (mốc) | bật |
    |---|---:|---:|
    | TTFT p50 / p95 | 1.379 / 3.621 ms | 1.413 / **3.177 ms** |
    | Lượt > 3 s | 48/323 (14,9 %) | **24/324 (7,4 %)** |
    | Total p95 | 4.499 | 4.069 |
    | Lượt đổi hàng: tool p50 / p90 | 919 / 1.655 ms | **118 / 584 ms** |
    | Lượt đổi hàng: TTFT p50 / p90 | 3.183 / 4.120 ms | 2.473 / 2.934 ms |
    | TSR / CCR / HR / guardrail (61 kịch bản) | 91,8 / 80,6 / 11,8 / 6 | 93,4 / 78,5 / 13,3 / 5 |

    Bộ này nhiều lượt đổi hàng nên p95 của nó không đại diện cả bộ. Chiếu lên trace m1_final10 (đổi hàng tool ≤ 118–584 ms): **p95 ≈ 3,03–3,06 s, 58–63 lượt > 3 s (cần ≤ 55)** — sát nhưng chưa đạt.
  - **Hai hướng 0 VND tiếp theo (20/11, offline) — đều KHÔNG làm:**
    - Lượt LLM gọi order.* bị gate chặn (252 lượt m1_final9/10, 13 lượt chậm ở m1_final10): câu cuối = câu mở đầu LLM viết + `say` của gate (229/252), chỉ 15 lượt trùng nguyên văn `say` → bỏ vòng LLM cuối sẽ mất phần LLM trả lời câu hỏi/nhắc giá (đổi hành vi, rủi ro TSR/CCR).
    - Gộp nhiều câu search_policy: gọi song song qua mcp-memory không nhanh hơn (20 cặp: nối tiếp p50 807 / song song 794 ms — server xử lý tuần tự); gộp thật cần tool mới xuyên 5 lớp, mô phỏng chỉ gỡ 3 lượt (63 → 60).
  - Mô phỏng sau RECEIVED_PREFETCH (trace m1_final10): p95 3.055 / 63 lượt; **mỗi vòng LLM −5 % → 2.935 / 48**; −8 % → 2.878 / 43. Còn lại là tốc độ mỗi vòng LLM (WebSocket mode, đầu ra vòng chọn tool) và điều kiện máy lúc đo (cắm sạc, Power mode "Best performance").
  - **A/B LLM_WS lần 2 (20/11 00:20–00:42, duyệt ≤ 26k, chi ≈ 25.900 VND)** — `runs/ab_ws_1120`: cùng code (3388021 + sửa: hủy lượt thì bỏ kết nối WS, không đọc hết câu bị hủy dưới khóa, mở sẵn kết nối mới ở nền), cờ LLM_WS tắt/bật, 40 kịch bản, xen kẽ theo nửa; so 38 kịch bản chung (226 lượt).

    | | HTTP (mốc) | WebSocket |
    |---|---:|---:|
    | TTFT p50 / p95 | 1.211 / **2.901 ms** | 1.062 / 3.131 ms |
    | Lượt > 3 s | **7/223 (3,1 %)** | 14/222 (6,3 %) |
    | Vòng chọn tool p50 / p90 | 1.318 / **1.662** | 1.290 / 1.900 |
    | Vòng cuối → token đầu p50 / p90 | 811 / 1.049 | **716 / 884** |
    | Cache trúng p50 (lượt < 0,5) | **0,93** (3) | 0,82 (7) |
    | Total p95 | 4.095 | 4.200 |
    | TSR / CCR / HR / guardrail | 89,5 / 74,1 / 13,3 / 5 | 86,8 / 77,6 / 12,5 / 6 |

    Giống lần 18/11: WS nhanh hơn ở trung vị nhưng cache thấp hơn → đuôi vòng chọn tool dài hơn → p95 kém. **Không dùng LLM_WS.** Sửa hủy kết nối vẫn giữ (cờ mặc định tắt).
  - **Phân tích "lượt bị gate chặn trả lời trong 1 vòng" (20/11, offline, 0 VND)** — 252 lượt bị chặn ở m1_final9 ×3 + m1_final10 (114 lượt > 3 s):
    - 206/252 lượt khách NÊU trường mới ngay trong lượt (địa chỉ/thanh toán/tên) → câu `say` của gate phụ thuộc thông tin chỉ LLM/bộ đọc trích được trong lượt đó; chỉ **16/252 (6 %)** đoán được câu `say` trước khi gọi LLM (có đơn nháp + không nêu trường mới). 171/252 là lần đầu có ý mua — code chưa biết sản phẩm/ý định (gate_open: intent_not_commit 91, not_evaluated 64, no_product_in_play 41).
    - Cận trên nếu code tự trả lời ngay khi bộ đọc về (bộ đọc ở các lượt này p50 1.688 ms) cho MỌI lượt bị chặn: p95 3.055 → 3.000, 63 → 54 lượt — và phải bỏ phần LLM trả lời câu hỏi của khách. **Không làm.**
  - **Bộ đọc nhanh hơn (20/11, offline):** trên trace m1_final10 bộ đọc nằm trên đường găng ở 155 lượt tool ghi/bị gate chặn (20 lượt > 3 s) + 356 lượt code nhận (3 lượt > 3 s). Mô phỏng (đã tính RECEIVED_PREFETCH): bộ đọc nhanh hơn 20 % → p95 2.994 / 51 lượt; 30 % → 2.984 / 48; 50 % → 2.981 / 46. Thời gian bộ đọc gần tuyến tính theo token ĐẦU RA (16/11: 52 token 1,30 s, 103 token 2,35 s ≈ 20 ms/token; rút ngắn PROMPT không giúp, READER_PROMPT_SHORT còn làm đầu ra dài gấp đôi). Hai cách bớt token ra: (a) tên khóa JSON ngắn (`asks_price_promo` → `pp`…, code đổi lại tên cũ); (b) địa chỉ/tên không chép hai lần (giá trị + *_quote). Cần replay 100 câu thật + eval_reply_reader trước khi A/B.
    - Đã cài `READER_COMPACT` (mặc định tắt): `PROMPT_COMPACT` sinh từ PROMPT (đổi tên khóa, địa chỉ một lần), `expand_compact` đổi về khóa cũ (cả giá trị `affirmed` và `qty` trong `extra_items`) trước verify(). Test `CompactOutputTest`: cùng lời đọc → cùng ReplyReading. 22 test bộ đọc OK.
    - Replay lần 1 (20/11, duyệt ≤ 2.500, `runs/reader_compact_1120`) **mất trắng ~2.218 VND**: Fast mode ~11 VND/câu → 100 câu chạm trần 1.100/tiến trình ở gần cuối, script cũ chỉ ghi kết quả khi xong cả bộ. Đã sửa script: ghi từng câu, chạm trần thì dừng gửi và giữ kết quả.
    - Replay lần 2 (20/11, duyệt ≤ 2.800, chi 1.152 + 1.106 + eval 387 = **2.645 VND**), 100 câu, hai bản chạy cùng lúc, Fast mode:

      | | bản gốc | READER_COMPACT |
      |---|---:|---:|
      | ms p50 / p90 / p95 | 1.243 / 2.059 / 2.390 | **987 / 1.495 / 1.720** |
      | token ra p50 / p90 / p95 | 49 / 134 / 167 | 44 / 119 / 140 |
      | câu khác bản gốc ở ≥ 1 trường chính | — | **61/100** (nhiễu cùng prompt 16/11: 10/100) |
      | eval_reply_reader (38 câu có đáp án) | 26/38 (19/11, bản prompt sửa đã bỏ) | 21/38 |

      Khác nhiều nhất ở asks_question 16, asks_price_promo 15, claims_prior_contact 14, product_sku 12, recipient_name 10 — đúng các trường gate dùng để quyết định code nhận lượt. Tên khóa ngắn làm mất gợi ý nghĩa → LLM đọc khác. **Không dùng READER_COMPACT** (giữ cờ, mặc định tắt). Nhanh hơn ~20 % dù token ra chỉ bớt ~10 % → thời gian không chỉ do token ra; chưa rõ phần còn lại.
  - Mốc HTTP ở đây (HEAD 3388021, 40 kịch bản) p95 2,90 s — bộ 40 vẫn lạc quan hơn cả bộ 277 (ước ~3,06 s).
  - Giới hạn: bộ 40 kịch bản từng lạc quan hơn cả bộ 277 (18/11: mốc 3,25 s vs 4,0 s cả bộ); lần này mốc 3,60 s. Cần đo 277 kịch bản trước khi nhận "đạt ≤ 3 s". Tool search_policy vẫn ~0,55 s — không phải do GIL của product_mentions; chỗ cắt tiếp theo.

Nguồn: [LiveKit — preemptive generation](https://docs.livekit.io/agents/build/speech/), [Voice agent latency playbook](https://huggingface.co/blog/dvalle08/voice-agent-latency-playbook), [Groq/Cerebras TTFT theo vùng](https://dev.to/max_bob/fastest-ai-inference-api-in-2026-30-days-of-latency-data-for-groq-cerebras-sambanova-and-43-386k), [Artificial Analysis — gpt-4o-mini providers](https://artificialanalysis.ai/models/gpt-4o-mini/providers), [OpenAI Chat Completions — allowed_tools](https://developers.openai.com/api/reference/resources/chat/subresources/completions).
