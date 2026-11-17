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

## Điều tra phần chuẩn bị trước vòng LLM đầu (17/11, offline, runs/ab_all_1117)

Chuẩn bị = TTFT − các vòng LLM trước token − thời gian tool − token đầu vòng cuối. (Ước tính câu đệm trước đó quên trừ thời gian tool → phóng đại phần chuẩn bị.)

| | mặc định a | tất cả cờ a |
|---|---|---|
| Chuẩn bị p50 / p95 (ms) | 238 / 1.327 | 515 / 774 |
| Lượt chuẩn bị > 1 s | 11 (đều là chờ bộ đọc nối tiếp, có đơn nháp hoặc lượt 1) | 2 (lượt 1, đọc muộn khi khách nêu biến thể) |

- Chuẩn bị > 1 s chỉ do **chờ bộ đọc nối tiếp**; READER_PARALLEL_DRAFT gỡ gần hết (11 → 2).
- **POLICY_PREFETCH làm mọi lượt LLM chờ thêm ~0,28 s** (p50 238 → 515 ms, chờ tối đa 0,3 s) và thêm ~340 token prompt không cache.
- Vòng LLM đầu p50 ~1,9 s, p95 2,7–3,5 s (API, không phải code).

**Ước tính lại câu đệm (đã trừ đúng thời gian tool):**

| | mặc định a / b | tất cả cờ a / b |
|---|---|---|
| Hiện tại p95 (s) | 5,41 / 5,70 | 5,80 / 5,33 |
| Đệm khi LLM gọi tool | 4,98 / 5,19 | 5,72 / 4,99 |
| Đệm mọi lượt có vòng LLM (kể cả bị nhắc) | **3,15 / 3,14** | **3,27 / 3,27** |
| Lượt > 3 s còn lại (cần ≤ ~11) | 20 / 16 | 23 / 22 |

Còn lại sau câu đệm: vòng LLM đầu tự nó > 3 s (7–17 lượt), lượt code sau bộ đọc (3–8). Bên bật tất cả cờ kém hơn vì POLICY_PREFETCH làm chậm mọi lượt.

## Điều tra lại (17/11, sau khi bỏ câu đệm)

### Bộ đọc bằng model nhỏ — replay 50 câu (runs/reader_model_1117), chạy cùng lúc, chi ~6,4k VND (gồm ~2,5k mất do lần đầu chạm trần trước khi ghi kết quả)

Tài khoản có (GET /v1/models): gpt-4.1-mini, gpt-5-nano, gpt-5.4-nano, gpt-5.4-mini… (không có gpt-4.1-nano).

| Model | Đọc xong | p50 / p95 | Token ra | Khác gpt-4o-mini ở trường chính |
|---|---|---|---|---|
| gpt-4o-mini (hiện tại) | 50/50 | 1,42 / 2,46 s | 53 | — |
| gpt-4.1-mini | 34/50 | 1,20 / 2,73 s | 59 | 19/34 |
| gpt-5-nano (minimal) | 26/50 | 2,42 / 3,49 s | 173 | 22/26 |
| gpt-5.4-nano (none) | 28/50 | 1,10 / 1,86 s | 59 | 19/28 (mã sản phẩm 11) |

- Model mới chưa có giá trong bảng → tính theo giá mặc định, chạm trần 900 VND trước khi xong 50 câu.
- Không model nào đạt ~0,7 s. gpt-5.4-nano nhanh nhất (−0,3 s p50) nhưng đọc khác bộ đọc hiện tại ở 2/3 số câu; "khác" chưa chắc là sai, nhưng các trường này quyết định order gate → rủi ro TSR. Chưa đổi.

### Vòng nhắc — cờ NUDGE_OFF (8e4d165)
Bỏ vòng nhắc mặc định; client vẫn nhắc khi câu trả lời hứa tra cứu/hành động. Đang đo online (runs/ab_nudge_1117).

### Đo online B1 / B2 (17/11) — runs/ab_nudge_1117, mỗi đợt 1 router mặc định + 1 cấu hình, chi ~24k VND

B1 = tất cả cờ, TẮT POLICY_PREFETCH. B2 = B1 + NUDGE_OFF. So 37 kịch bản; số lượt > 3 s tính trên toàn file.

| | router a | B1 | router b | B2 |
|---|---|---|---|---|
| TSR | 91,9 | 91,9 | 91,9 | 86,5 |
| TTFT p95 (s) | 5,60 | 5,25 | 5,56 | 4,91 |
| Lượt > 3 s | 65 | 46 | 70 | 49 |
| Lượt bị nhắc | 20 | 23 | 23 | 8 |

- Tắt tra trước chính sách: lượt > 3 s 60 (ab_all, có tra trước) → 46, TSR giữ.
- NUDGE_OFF: p95 −0,35 s nhưng mất 2 cuộc đúng do bỏ nhắc: SAMPLE-07 (nói 14 ngày, không tra chính sách), SC-GEN-07 (thiếu "đổi mới 30 ngày").
- Bộ đọc không tách được lượt nhắc có ích / vô ích (khách hỏi: 36 có ích / 26 vô ích; không hỏi: 11 / 8).
- Tiếp: B3 = NUDGE_OFF + POLICY_PREFETCH (câu hỏi chính sách có dữ liệu sẵn thay cho vòng nhắc); lặp B1 để kiểm tái lập.

### Độ đúng bộ đọc gpt-5.4-nano (17/11) — scripts/eval_reply_reader.py, 34 câu có đáp án, chi ~2,1k VND (gồm ~0,5k lần đầu chạm trần)

| Model | Đúng | |
|---|---|---|
| gpt-4o-mini (hiện tại) | 21/34 | |
| gpt-5.4-nano (reasoning none) | 18/34 | đúng hơn 4 câu (khách sửa tên/địa chỉ, xác nhận SĐT), sai thêm 7 câu |

- Lỗi riêng của nano nguy hiểm cho order gate: coi câu HỎI là "chỉ trả lời câu hỏi của gate" (`only_answers=True` với "giao mất mấy ngày vậy em?", "bên em có size 41 không?"), bỏ sót tên người nhận ("đại", "tên là thu…"), bỏ sót xác nhận ("ừ đúng rồi").
- **Không đổi model bộ đọc.** Nano chỉ nhanh hơn ~0,3 s mà kém đúng hơn ở đúng các trường gate dùng để quyết định.

### Đo B3 + lặp B1 (17/11) — runs/ab_nudge2_1117, chi ~24k VND

B3 = B1 + NUDGE_OFF + POLICY_PREFETCH. Số tính trên toàn file (~230 lượt), TSR trên 38 kịch bản.

| | router a | B3 | router b | B1 (lặp) | B1 (lần trước) |
|---|---|---|---|---|---|
| TSR | 92,1 | 89,5 | 92,1 | 86,8 | 91,9 |
| TTFT p95 (s) | 5,42 | 4,75 | 5,36 | 4,30 | 5,25 |
| Lượt > 3 s | 66 | 44 | 57 | 45 | 46 |
| Lượt bị nhắc | 22 | 8 | 22 | 20 | 23 |

- **B1 không tái lập:** p95 5,25 → 4,30 s, TSR 91,9 → 86,8 giữa hai lần chạy cùng cấu hình. Số lượt > 3 s ổn định hơn (46 / 45).
- **SC-GEN-07 trượt ở cả B1 lặp (có vòng nhắc)** → lỗi chính sách "đổi mới 30 ngày" gắn với reranker (đã thấy ở đo B lần 2), không chỉ do bỏ vòng nhắc.
- B3: tra trước chính sách không bù được: vẫn trượt SC-GEN-07.
- Cấu hình bật cờ nhất quán giảm lượt > 3 s (≈ 44–49 so với 57–70) và p95 thấp hơn router 0,3–1,0 s, nhưng TSR thấp hơn 0–5 điểm tùy lần; với 1–2 lần chạy mỗi cấu hình chưa tách được khỏi nhiễu.

## Kế hoạch 4 bước (17/11) — bước 0–1

- **Bước 0:** tra trước chính sách mặc định không chờ (`POLICY_PREFETCH_WAIT_S=0`). Cấu hình nền B1r = B1 nhưng giữ router (bỏ reranker: SC-GEN-07, cần GPU, không tái lập).
- **Bước 1:** `TOOL_FIRST_PROMPT` — quy tắc gọi tool ngay vòng đầu. Đo 1 cặp cùng giờ (runs/ab_toolfirst_1117, ~12k VND), 36 kịch bản:

| | router | B1r + TOOL_FIRST_PROMPT |
|---|---|---|
| TSR | 97,2 | 94,4 (thêm trượt SC-TV-05/call_3) |
| HR giá/KM % | 13,3 | 18,8 |
| TTFT p50 / p95 (s) | 1,68 / 5,02 | 1,78 / 5,33 |
| Lượt > 3 s | 56 | 56 |
| Lượt bị nhắc | 21 | 20 |
| Total p95 (s) | 6,68 | 6,87 |

- **Không đạt** (tiêu chí: lượt bị nhắc ≤ 11). LLM gần như không làm theo quy tắc (21 → 20). Bỏ hướng này (cờ giữ tắt). Theo kế hoạch: sang bước 2 (yêu cầu song song bắt buộc gọi tool) — cần duyệt.
- B1r (giữ router) không giảm lượt > 3 s như B1 có reranker (56 vs 44–49): phần giảm ở B1 chủ yếu đến từ reranker làm lượt chính sách nhanh hơn.

## Bước 2 — PARALLEL_REQUIRED_TOOLS (17/11, duyệt) — runs/ab_required_1117, 1 cặp cùng giờ, chi ~14,5k VND

So 38 kịch bản (router chạm trần 6.000; bên thử dùng 8.492 VND, trần 9.000).

| | router | B1r + yêu cầu song song |
|---|---|---|
| TSR | 89,5 | 86,8 |
| HR giá/KM % | 23,5 | 14,3 |
| TTFT p50 / p95 (s) | 2,11 / 6,05 | 1,92 / 5,47 |
| Lượt > 3 s | 70 | 67 |
| Lượt ≥ 2 vòng LLM trước token | 17 | **3** |
| Total p95 (s) | 7,69 | 7,72 |
| Chi phí cho cùng số kịch bản | ~6,0k | ~8,5k (+~40 %) |

- **Cơ chế chạy đúng:** lượt ≥ 2 vòng 17 → 3 (vòng nhắc được thay bằng lời gọi tool song song). p95 giảm ~0,6 s.
- **Nhưng lượt > 3 s gần như không đổi (70 → 67):** lượt từng bị nhắc giờ còn 1 vòng tool + vòng trả lời ≈ 3,2–4 s, vẫn trên ngưỡng.
- TSR −1 cuộc (trượt thêm SC-TV-16, SC-ULTRA-01; đạt thêm SC-GEN-13) — ở mức nhiễu, chưa kết luận.
- Hôm nay API chậm hơn (router p95 6,05 s so với ~5,4 s các lần trước).
- **Tiêu chí bước 2:** lượt bị nhắc thật ≤ 5 → đạt (≈ 3); TSR giữ nguyên → chưa chắc (−1 cuộc). p95 vẫn ~5,5 s: muốn ≤ 3 s phải rút ngắn chính vòng tool (bước 4, model nhanh hơn).

## Bước 4 — đo thử model (17/11, duyệt) — runs/model_probe_1117, chi ~8,3k VND

Đổi `LLM_MODEL` cho cả hệ thống (LLM chính, bộ đọc, router), 10 kịch bản, chạy cùng giờ với gpt-4o-mini, trần 2.000 VND mỗi model. Model chưa có giá trong bảng bị tính theo giá mặc định nên chỉ chạy được 10–15 lượt; so trên các lượt chung.

| Model | Lượt chung | Vòng LLM p50 / p95 (s) | Vòng / lượt | TTFT p50 (s) | TTFT lớn nhất (s) |
|---|---|---|---|---|---|
| gpt-4o-mini (mốc) | 10–15 | 2,0–2,1 / 2,74 | 1,67–1,77 | 3,4 | 4,6–6,8 |
| gpt-4.1-mini | 15 | 1,70 / 2,41 | 2,00 | 3,17 | 6,0 |
| gpt-5.4-mini (reasoning none) | 11 | 1,54 / 2,07 | 2,12 | 2,66 | 8,3 |
| gpt-5.4-nano (reasoning none) | 10 | 1,53 / 2,12 | 2,50 | 3,28 | 10,1 |
| gpt-6-astra | — | — | — | — | không chạy được: không nhận reasoning_effort=none (chỉ low trở lên) |

- Mỗi vòng nhanh hơn ~20–25 %, **không model nào đạt ~0,7 s/vòng**.
- Các model mới gọi nhiều vòng hơn mỗi lượt (2,0–2,5 so với 1,7), nên TTFT chỉ cải thiện ít; lượt chậm nhất còn tệ hơn.
- Mẫu rất nhỏ (10–15 lượt), chưa đo TSR. Bộ đọc gpt-5.4-nano đã biết kém đúng hơn (18/34).
- **Kết luận:** đổi model không đưa được TTFT p95 về ≤ 3 s.

### Bước 4b — gpt-5.4-mini trên bộ 40 kịch bản (17/11) — runs/ab_54mini_1117, sổ ~18k VND (tiền thật ≤ sổ)

Cả hệ thống đổi model (LLM chính, bộ đọc, router), reasoning none. Sổ chi phí tính gpt-5.4-mini theo giá mặc định (cao) nên chạm trần 12.000 sau 13 kịch bản; so trên 13 kịch bản chung (~80 lượt).

| | gpt-4o-mini | gpt-5.4-mini |
|---|---|---|
| TSR | 92,3 | 84,6 (thêm trượt SC-ULTRA-01/call_4) |
| HR giá/KM % | 30,8 | 16,7 |
| TTFT p50 / p95 (s) | 2,82 / 6,51 | 3,47 / 6,99 |
| Lượt > 3 s | 38 | 44 |
| Vòng LLM p50 (s) | 2,05 | 1,69 |
| Vòng / lượt | 1,52 | 1,82 |
| Total p95 (s) | 9,49 | 8,22 |

- Mỗi vòng nhanh hơn ~0,35 s nhưng gọi nhiều vòng hơn → TTFT **chậm hơn**, TSR thấp hơn. Không dùng.
- Mẫu 13 kịch bản; hôm nay API chậm (gpt-4o-mini p50 2,82 s).

### Bước 4c — gpt-5.4-mini + reranker thay router (17/11) — runs/ab_54mini_rr_1117, sổ ~21k VND (tiền thật ≤ sổ)

So 17 kịch bản chung (99 lượt mỗi bên; bên thử chạm trần sổ 15.000 do giá mặc định).

| | gpt-4o-mini + router | gpt-5.4-mini + reranker |
|---|---|---|
| TSR | 88,2 | 88,2 |
| HR giá/KM % | 20,0 | 10,0 |
| TTFT p50 (s) | 2,04 | 2,47 |
| TTFT p95 (s) | 12,45* | 5,31 |
| Lượt > 3 s | 32 | 35 |
| Lượt 0 / 1 / ≥ 2 vòng tool trước token | 43 / 28 / 8 | 27 / 32 / 19 |
| Vòng LLM p50 (s) | 2,09 | 1,56 |
| search_policy: số lần / ms mỗi lần | 9 / 1.248 | 22 / 520 |
| Total p95 (s) | 14,07* | 7,71 |

\* Bên router có 6 lượt API treo 12,5–18,7 s trong lần chạy này → p95 không dùng để so được.

- Reranker cắt thời gian mỗi lần tra chính sách 1,25 → 0,52 s, nhưng gpt-5.4-mini vẫn tra nhiều gấp ~2,4 lần và có nhiều lượt ≥ 2 vòng hơn (19 so với 8). TTFT p50 chậm hơn 0,43 s, lượt > 3 s không ít hơn.
- TSR ngang nhau; HR thấp hơn (mẫu nhỏ).
- **Kết luận:** gpt-5.4-mini kể cả có reranker không cải thiện TTFT so với gpt-4o-mini + router.

### Bước 4d — gpt-5.4-mini + reranker + cờ cắt vòng (17/11, duyệt) — runs/ab_54mini_rr2_1117, chi 32.082 VND (giá gpt-5.4-mini thật, d62fc68)

Thử = gpt-5.4-mini reasoning none + reranker (lời khách, mọi phiên bản) + SHORTLIST_FULL_QUOTE, POLICY_TOOL_NO_PROMO, LOOKUP_BUNDLE, POLICY_PREFETCH, READER_PARALLEL_DRAFT (HEAD 9787141). Mốc = gpt-4o-mini + router. 1 cặp cùng giờ; cả hai chạm trần (6.000 / 26.000) → so 35 kịch bản.

| | gpt-4o-mini + router | gpt-5.4-mini + reranker + cờ |
|---|---|---|
| TSR | 91,4 (32/35) | 88,6 (31/35) |
| HR giá/KM % | 12,5 | 5,3 |
| TTFT p50 / p95 (s) | 2,02 / 6,22 | 2,31 / 4,68 |
| Total p95 (s) | 8,21 | 5,98 |
| Lượt > 3 s (208 lượt) | 75 | 63 |
| Lượt ≥ 2 vòng | 19 | 19 |
| search_policy do LLM gọi | 23 | 42 |
| Chi phí cùng 35 kịch bản (VND) | 3.181 | 12.907 (×4) |

Trên 17 kịch bản chung với bước 4c: ≥ 2 vòng 19 → 14, search_policy 22 → 17, lượt > 3 s 35 → 30 (mốc 4o lần này 35).

- Các cờ cắt vòng có tác dụng một phần (≥ 2 vòng −5, search_policy −5 trên cùng 17 kịch bản), lượt > 3 s −12 trên 35 kịch bản; p95 4,68 s vẫn > 3 s.
- **SAMPLE-07 (mẫu BTC, chính sách cũ) trượt do POLICY_ALL_VERSIONS:** top-3 của "đổi trả 14 ngày" là [DT-OLD-01, DT-02, DT-OLD-02] — bản hết hiệu lực chiếm chỗ [DT-01] "7 ngày", agent không nói được 7 ngày. Rủi ro phiên bản đã thành lỗi thật trên đúng loại ca khó BTC có trong bộ ẩn.
- Các cuộc trượt khác chỉ bên thử: SC-GEN-06, SC-GEN-13 (order.create), SC-ULTRA-01/call_4 (order.status); bên mốc trượt riêng SAMPLE-01/call_2, SC-ULTRA-04/call_4, SC-ULTRA-07/call_4 → TSR trong nhiễu.
- Chi phí gấp ~4 lần gpt-4o-mini với giá thật.
- **Kết luận:** chưa thay số nộp. Nếu đi tiếp hướng này: bỏ POLICY_ALL_VERSIONS (hoặc chỉ trả bản cũ khi có ngày mua), và cần duyệt chi phí ×4.

### Sửa lỗi hướng gpt-5.4-mini (17/11) — runs/rerun_54mini_fails_1117, chi ~12k VND

Cấu hình như bước 4d, mỗi phép đo 3 lần.
- **SAMPLE-07 (9a6adec):** POLICY_ALL_VERSIONS giờ giữ top_k bản hiện hành, bản cũ chỉ nối thêm (tối đa 2). Đạt 3/3.
- **SC-GEN-06 (quà tặng thành đơn):** bộ đọc gpt-5.4-mini gán "túi trữ sữa" (quà) thành sản phẩm đơn. Quy tắc trong prompt không đủ (vẫn trượt 3/3). `READER_MODEL=gpt-4o-mini` (1917caf): lỗi quà tặng không còn lần nào; đạt 2/3, lần trượt còn lại là lỗi khác — lượt 1 không tra sản phẩm, đơn ra SKU-AP-X (chưa phân tích).
- **SC-ULTRA-01:** đạt 2/3 lần với READER_MODEL; lần trượt: call_4 LLM trả lời theo chính sách mà không gọi order.status (hành vi gpt-5.4-mini, chưa sửa).

### Bước 4e — đo lại 40 kịch bản sau sửa (17/11) — runs/ab_54mini_rr3_1117 (chạy 2 phần: full.jsonl + full2.jsonl, bỏ kịch bản dở), ~25k VND

Thử = bước 4d + 9a6adec (bản hiện hành giữ top-3) + READER_MODEL=gpt-4o-mini. So 39 kịch bản chung.

| | gpt-4o-mini + router | gpt-5.4-mini + reranker + cờ + sửa |
|---|---|---|
| TSR | 94,9 (2 trượt) | 92,3 (3 trượt) |
| HR giá/KM % | 23,5 | 9,5 |
| TTFT p50 / p95 (s) | 1,61 / 6,79 | 2,39 / 4,91 |
| Total p95 (s) | 8,33 | 6,68 |
| Lượt > 3 s | 62 | 72 |
| Lượt ≥ 2 vòng | 16 | 21 |
| search_policy do LLM gọi | 26 | 45 |

- SAMPLE-07, SC-GEN-06, SC-GEN-13 đạt; SC-ULTRA-01 đạt (mốc trượt). Trượt riêng bên thử: SC-TV-05/call_3, SC-ULTRA-07/call_3 (mốc cũng từng trượt 2 cuộc này ở lần khác) → TSR trong nhiễu.
- p95 thấp hơn ~1,9 s nhưng p50 chậm hơn 0,8 s và **lượt > 3 s nhiều hơn (72 vs 62)**: p95 thấp do mốc có đuôi API treo, không phải vì thử nhanh hơn đều. Vẫn chưa ≤ 3 s.
- **Kết luận:** sửa lỗi đã giữ TSR, nhưng hướng gpt-5.4-mini không cải thiện TTFT toàn hệ thống. Đóng hướng này.

## Fast mode (17/11, duyệt) — runs/fastmode_1117, ~4k VND tiền thật

`LLM_SERVICE_TIER=fast` (mặc định trống) gửi `service_tier` cho mọi lời gọi (LLM chính, bộ đọc, router). gpt-4o-mini nhận Fast mode (API trả tier `priority`) dù tài liệu không liệt kê. Giá ×2; sổ chi phí KHÔNG nhân nên trần trên sổ đặt một nửa. 10 kịch bản, chạy cùng giờ, cấu hình mặc định.

| (34 lượt chung) | gpt-4o-mini thường | gpt-4o-mini fast |
|---|---|---|
| Vòng LLM p50 / p95 (s) | 1,94 / 2,43 | **1,30 / 1,67** |
| Vòng cuối → token đầu p50 (s) | 0,89 | 0,81 |
| TTFT p50 / p95 (s) | 1,93 / 5,43 | 1,87 / **3,60** |
| Lượt > 3 s | 12 | **5** |
| Vòng / lượt | 1,61 | 1,53 |

- gpt-6-luna fast (reasoning none): vòng 1,26 s nhưng 2,7 vòng/lượt → TTFT tệ hơn (22 lượt chung: p95 7,1 s, 12 lượt > 3 s so với 8 của 4o thường). gpt-6-astra: Chat Completions không cho tool kèm reasoning, cần Responses API → không đo.
- Fast mode rút ngắn chủ yếu vòng gọi tool (−33 %), ít ở vòng cuối ra token. Trace chưa ghi được tier trả về (service_tier = None trong trace) — hiệu lực xác nhận qua lời gọi thử và độ trễ.
- Mẫu nhỏ (34 lượt), chưa đo TSR. **Bước tiếp:** A/B 40 kịch bản 4o thường vs 4o fast.

### gpt-5.6-luna fast vs gpt-4o-mini fast (17/11) — runs/fastmode3_1117, ~5k VND tiền thật (giá luna thêm ở 452f501)

| (50 lượt chung, 8 kịch bản) | gpt-4o-mini fast | gpt-5.6-luna fast |
|---|---|---|
| Vòng LLM p50 / p95 (s) | 1,36 / 1,76 | 1,41 / 1,90 |
| Vòng / lượt | 1,75 | 2,07 |
| TTFT p50 / p95 (s) | 2,22 / 5,30 | 2,84 / 7,46 |
| Lượt > 3 s | 14 | 25 |
| TSR (8 kịch bản, gồm 1 dở của luna) | 75,0 | 100,0 |

- gpt-5.6-luna: mỗi vòng không nhanh hơn, gọi nhiều vòng hơn → TTFT tệ hơn. Loại.
- gpt-4o-mini fast lần này p95 5,30 s (lần trước 3,60 s trên 34 lượt): mức lợi của Fast mode dao động mạnh giữa các lần → A/B 40 kịch bản phải chạy fast cùng giờ với bản thường.

### A/B Fast mode, 40 kịch bản (17/11, duyệt) — runs/ab_fast_1117, cấu hình mặc định, cùng giờ

So 36 kịch bản chung (~213 lượt mỗi bên). Bên fast chạy trước bản sửa bảng giá (301ac9f) nên sổ tính giá thường; tiền thật ≈ sổ × 1,67.

| | gpt-4o-mini thường | gpt-4o-mini fast |
|---|---|---|
| TSR | 94,4 | 94,4 |
| HR giá/KM % | 12,5 | 5,9 |
| TTFT p50 / p90 / p95 (s) | 2,45 / 5,69 / 6,62 | **1,79 / 3,97 / 4,89** |
| TTFT lớn nhất (s) | 15,1 | 11,3 |
| Lượt > 3 s | 78 | **47** |
| Vòng LLM p50 / p95 (s) | 1,86 / 4,47 | **1,35 / 1,83** |
| Vòng cuối → token đầu p50 (s) | 0,94 | 0,86 |
| Vòng / lượt | 1,63 | 1,55 |
| Total p95 (s) | 9,44 | **6,09** |
| Chi phí 36 kịch bản (VND thật) | ~3.360 | ~5.320 (×1,6) |

- **Fast mode là hướng đầu tiên cải thiện rõ mà không mất TSR:** p95 −1,7 s, lượt > 3 s −40 %, Total p95 −3,4 s; chủ yếu nhờ cắt đuôi vòng LLM (p95 vòng 4,47 → 1,83 s). Hành vi không đổi (cùng model, số vòng gần như nhau).
- Trượt: thường SAMPLE-01, SC-ULTRA-09; fast SC-GEN-06, SC-ULTRA-07 — đều là cuộc từng trượt ở các lần khác → nhiễu.
- Vẫn chưa ≤ 3 s (p95 4,89 s). Hôm nay API chậm (bên thường p95 6,62 s so với 5,4–6,2 s các lần trước).

### A/B Fast vs Fast + PARALLEL_REQUIRED_TOOLS (18/11, duyệt) — runs/ab_fastreq_1117, ~24k VND thật

Cả hai `LLM_SERVICE_TIER=fast` (sổ giá fast), cấu hình còn lại mặc định. 38 kịch bản chung, 226 lượt mỗi bên. Hai bên chạm trần 10.000 / 14.000 ở cùng chỗ → yêu cầu song song tốn thêm ~40 % (chi phí yêu cầu song song ghi ngoài llm_cost của lượt).

| | Fast | Fast + yêu cầu song song |
|---|---|---|
| TSR | 94,7 | 97,4 |
| HR giá/KM % | 23,5 | 12,5 |
| TTFT p50 / p95 (s) | 1,33 / 4,29 | 1,17 / **4,06** |
| Lượt > 3 s | 38 | 33 |
| Lượt ≥ 2 vòng | 21 | 6 |
| Total p95 (s) | 5,21 | 5,13 |

- Cộng dồn được nhưng ít: p95 −0,23 s, lượt > 3 s −5. Đêm nay API nhanh hơn (Fast p95 4,29 so với 4,89 s ở lần trước).
- **35 lượt > 3 s còn lại (bên thử, 239 lượt):** 19 tra chính sách (tool 1,2–2,9 s — router LLM), 7 chuyển máy (tool 1–2 s — bước kiểm duyệt LLM), 6 tra sản phẩm, 3 khác. Vòng LLM giờ chỉ ~0,9–1,7 s; nút thắt chuyển sang **thời gian tool có LLM bên trong**.
- Ước tính offline thay router bằng reranker (0,45 s/lần tra): p95 4,06 → ~3,5 s, lượt > 3 s 35 → 29 (cần ≤ 11 để p95 ≤ 3 s).
