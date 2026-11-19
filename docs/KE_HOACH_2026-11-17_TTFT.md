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

### A/B Fast + yêu cầu song song: router vs reranker (18/11, duyệt) — runs/ab_fastreqrr_1118, ~27k VND thật, đủ 40 kịch bản

| | router | reranker (POLICY_NO_ROUTER, qwen_rerank, POLICY_QUERY_CONTEXT) | dự tính offline |
|---|---|---|---|
| TSR | 95,0 | 95,0 | — |
| HR giá/KM % | 12,5 | 15,0 | — |
| TTFT p50 / p95 (s) | 1,26 / 3,97 | 1,20 / **3,36** | p95 3,31 |
| Lượt > 3 s | 35 | **21** | 23 |
| Lượt chính sách > 3 s | 20 / 22 | 5 / 19 | 7 / 19 |
| search_policy mỗi lần (s) | 1,07 | 0,47 | 0,45 |
| Total p95 (s) | 5,02 | **4,35** | — |

- **Khớp dự tính.** TSR giữ (trượt SC-GEN-06, SC-ULTRA-07 bên reranker; SAMPLE-01, SC-ULTRA-07 bên router — nhiễu). SC-GEN-07 đạt.
- **Cấu hình tốt nhất tới nay:** gpt-4o-mini fast + PARALLEL_REQUIRED_TOOLS + reranker. Còn 21 lượt > 3 s / 239 (cần ≤ 11):
  5 chuyển máy (tool kiểm duyệt LLM 0,9–2,8 s), 5 chính sách (2 vòng LLM dài), 4 tra sản phẩm 1 vòng, 4 tra sản phẩm ≥ 2 vòng (chuỗi shortlist → báo giá), 3 khác.

### Phân tích 21 lượt > 3 s còn lại (18/11, offline, runs/ab_fastreqrr_1118 bên reranker)

- **Chuyển máy (5):** tool chờ `authorize_handoff` (1 lời gọi LLM, 0,9–2,8 s). Lời gọi chỉ cần lời khách + câu cuối nhân viên → có thể chạy sẵn song song từ đầu lượt. Ước tính gỡ 4 lượt (p95 3,36 → 3,12 s). Chưa cài.
- **Tra sản phẩm ≥ 2 vòng (4):** chuỗi catalog.search → get_quote; `LOOKUP_BUNDLE` (có sẵn) gắn giá vào kết quả tìm. Ước tính chỉ gỡ thêm 1 lượt (p95 → 3,12 s); các lượt còn lại có vòng cuối dài (SC-GEN-13: 3,9 s) hoặc LLM gọi sai SKU.
- **Còn ~16 lượt sau hai sửa (cần ≤ 11):** chính sách 2 vòng (5), shortlist 1 vòng nhưng mỗi vòng 1,8–2,3 s (2), tra sản phẩm 1 vòng (4)… — đều là 2 vòng LLM bình thường, mỗi vòng 1–2 s. Chỉ rút ngắn thêm thời gian mỗi vòng mới gỡ được.

### A/B HANDOFF_PREFETCH + LOOKUP_BUNDLE (18/11, duyệt) — runs/ab_handoffpf_1118, ~27k VND thật, chạy NỐI TIẾP (cả hai dùng GPU)

Nền cả hai bên: gpt-4o-mini fast + PARALLEL_REQUIRED_TOOLS + reranker. So 38 kịch bản chung (226 lượt).

| | mốc | thử (+ HANDOFF_PREFETCH + LOOKUP_BUNDLE) | mốc lần trước (ab_fastreqrr_1118) |
|---|---|---|---|
| TSR | 86,8 | 89,5 | 94,7 |
| TTFT p50 / p95 (s) | 1,23 / 3,31 | 1,37 / **3,26** | 1,20 / 3,24 |
| Lượt > 3 s | 23 | **19** | 20 |
| Lượt chuyển máy > 3 s | 7 / 9 | **2 / 9** | 4 / 7 |
| Total p95 (s) | 4,60 | 4,43 | 4,33 |

- Kiểm duyệt chạy sẵn **có tác dụng đúng chỗ** (lượt chuyển máy chậm 7 → 2), nhưng tổng chỉ −4 lượt > 3 s, p95 −0,05 s; dự tính ~3,1 s không đạt. p50 bên thử chậm hơn 0,14 s (chạy khác giờ; chưa tách được do giờ hay do tải thêm).
- Bên thử tốn hơn: chạm trần 14.000 trước khi xong 40 kịch bản (mốc 13.342 cho đủ 40).
- TSR dao động lớn giữa 2 lần chạy cùng cấu hình mốc (86,8 vs 94,7); SC-GEN-07 trượt lại ở mốc lần này (đã biết gắn với reranker).

## Nghiên cứu hướng mới sau cấu hình tốt nhất (18/11)

**Web (đọc tài liệu OpenAI + nghiên cứu):**
- **Ultrafast:** chỉ GPT-6 Astra / 6.1 Sol / 6.2, chỉ Responses API, giá bảng riêng (Astra Fast đã 20 / 100 USD mỗi 1M token ≈ 100× gpt-4o-mini). Một lần đo 40 kịch bản ước ~180k VND trở lên; prompt viết cho gpt-4o-mini, Astra hành vi chưa biết. **Không phù hợp.**
- **WebSocket mode / Responses API:** lợi chủ yếu cho chuỗi ≥ 20 lời gọi tool; mình 1–2 vòng → vài trăm ms tốt nhất, phải chuyển API. **Không đáng trước hạn.**
- **Prompt caching / cắt prompt:** đo trên trace: cache trúng 97 % (token chưa cache p50 131), tương quan token chưa cache ↔ TTFT = −0,01. **Không còn gì để lấy.**
- **Dự đoán lời gọi tool bằng model nhỏ** (SPORK, Speculate While You Reason): tăng tốc 1,09–1,18× trong mô phỏng, chưa chứng minh thực tế; tương tự PARALLEL_REQUIRED_TOOLS đã có. **Không đáng.**

**Phát hiện từ trace (ab_fastreqrr_1118, bên reranker):** thời gian ngoài LLM + tool trước token đầu p50 0,24 s, nhưng 9/21 lượt > 3 s có 0,6–1,6 s:
- chờ **bộ đọc chạy tuần tự** khi có đơn nháp (0,76–1,2 s) → `READER_PARALLEL_DRAFT` (có sẵn);
- chờ **yêu cầu bắt buộc gọi tool** (không stream) xong sau vòng thường.
Ước tính offline: + READER_PARALLEL_DRAFT → p95 3,14 s, 16 lượt > 3 s; + HANDOFF_PREFETCH → **p95 3,09 s, 13 lượt** (cần ≤ 11 / 239).

### A/B READER_PARALLEL_DRAFT + HANDOFF_PREFETCH (18/11, duyệt) — runs/ab_rpd_1118, ~27k VND thật, NỐI TIẾP (thử trước)

Nền: gpt-4o-mini fast + PARALLEL_REQUIRED_TOOLS + reranker. 37 kịch bản chung (~220 lượt).

| | mốc | thử | ước tính (trên trace mốc cũ) |
|---|---|---|---|
| TSR | 91,9 | 91,9 | — |
| HR giá/KM % | 16,7 | 11,1 | — |
| TTFT p50 / p95 (s) | 1,49 / 3,70 | 1,43 / **3,31** | p95 3,09 |
| Lượt > 3 s | 30 | **21** | 13 |
| Lượt chờ bộ đọc tuần tự | 10 | 4 | 0 |
| Total p95 (s) | 4,96 | 4,44 | — |

- So cùng lần: −9 lượt > 3 s, p95 −0,39 s, TSR giữ (trượt SC-GEN-07 bên thử — lỗi reranker đã biết; SC-GEN-06 bên mốc).
- Mức tuyệt đối kém ước tính vì API chậm hơn lúc chạy (mốc lần này p95 3,70 so với 3,36 s ở ab_fastreqrr_1118). Còn 4 lượt bộ đọc tuần tự (lượt chốt / closing — chưa kiểm).

### Kiểm giả định "stream yêu cầu bắt buộc gọi tool" (18/11, offline, runs/ab_rpd_1118 bên thử) — KHÔNG làm

- Lượt dùng yêu cầu song song (21): phần ngoài LLM + tool p50 0,38 s, so với 0,24 s ở lượt khác → chờ thêm chỉ ~0,15 s; trong 21 lượt > 3 s chỉ 4 lượt có phần ngoài > 0,5 s (0,53–1,49 s), lẫn với chờ bộ đọc.
- Stream không làm yêu cầu xong sớm hơn (lời gọi tool chỉ đủ khi stream kết thúc) → ước tính trước (gỡ 2–4 lượt) **sai**; không cài.
- 21 lượt > 3 s còn lại phần lớn là 2 vòng LLM bình thường (mỗi vòng 1,0–2,0 s) + tool. Phía code gần như hết chỗ gỡ.

### Hedging (18/11) — mô phỏng, lần đo ab_hedge_1118 đã DỪNG giữa chừng theo yêu cầu

Phân bố thời gian chờ chữ đầu mỗi vòng (564 vòng, cấu hình tốt nhất): p50 0,78 / p90 1,08 / p95 1,31 / p99 1,76 s — rất hẹp. Mô phỏng (bản sao cùng phân bố, độc lập): ngưỡng ≥ 0,4 s gần như không đổi p95 mỗi vòng (1,31–1,33 s); chỉ gửi 2 bản ngay (ngưỡng 0) mới còn 0,91 s, chi phí LLM ×2. Khi API nghẽn, hai bản chậm cùng lúc → thực tế kém hơn mô phỏng. Ngưỡng 1,2 s chọn theo cảm tính, không có cơ sở → dừng đo.

## Hướng tới p95 ≤ 2,9 s (18/11) — phân tích trace + nghiên cứu

**Trace cấu hình tốt nhất (138 lượt 2 vòng):** vòng gọi tool p50 1,23 s, tool p50 0,02 s, vòng trả lời tới chữ đầu p50 0,71 s, phần code ~0,24 s. Vòng 1 không phụ thuộc số lời gọi / độ dài tham số (tương quan −0,12 / 0,05); vòng 2 không phụ thuộc độ dài kết quả tool (−0,03). → Thời gian là **chi phí cố định mỗi lần gọi API**, không phải độ dài nội dung.

**Mạng:** curl tới api.openai.com: TCP 60–90 ms (biên Cloudflare gần), nhưng gói đầu của yêu cầu không gọi model 0,36–0,44 s (biên → trung tâm dữ liệu Mỹ). Mỗi vòng trả phần này; lượt 2 vòng trả 2 lần. Chưa đo tách bằng header `openai-processing-ms` (cần duyệt gọi API).

**Tài liệu đã xem, mức phù hợp:**
- AsyncLM (arXiv 2412.07017): giấu thời gian tool chạy lâu; tool của mình ~17 ms → không hợp.
- Endpoint khu vực OpenAI (jp.api.openai.com): theo một nguồn thứ cấp chỉ GPT-6 Luna + ZDR, phụ phí 10 % → không dùng được cho gpt-4o-mini.
- Azure OpenAI vùng gần (Japan East / Southeast Asia): có thể bớt phần mạng mỗi vòng, nhưng không có Fast mode (mất ~33 % đã thắng), cần tài khoản mới, không có số đo độ trễ công bố → rủi ro lỗ ròng.
- WebSocket mode (Responses API): OpenAI khuyên dùng chính vì "network overhead"; giữ kết nối tới máy chủ thay vì mỗi vòng một yêu cầu HTTP. Phải chuyển sang Responses API; mức lợi cho 2 vòng/lượt chưa có số.

**Đo tách mạng (18/11, duyệt, gpt-4o-mini, 1 token, bỏ lần đầu mở kết nối, 5 lời gọi mỗi bên):**

| | tổng p50 | OpenAI xử lý (`openai-processing-ms`) p50 | mạng + biên p50 |
|---|---|---|---|
| thường | 979 ms | 456 ms | 534 ms |
| fast | 808 ms | 426 ms | **275 ms** |

→ Với Fast mode, mỗi lần gọi API mất ~0,28 s ngoài thời gian xử lý của OpenAI; lượt 2 vòng trả ~0,55 s. Đây là phần còn lại lớn nhất có thể gỡ mà không đụng tới model (mẫu nhỏ, dao động 0,2–0,6 s).

### Thử WebSocket mode (18/11, duyệt) — scripts/probes/ws_probe.py, gpt-4o-mini fast, Responses API, 1 lượt 2 vòng × 4 lần mỗi bên

| | vòng 1 tới lời gọi tool p50 | vòng 2 tới chữ đầu p50 | cả lượt p50 | từng lượt (ms) |
|---|---|---|---|---|
| HTTP stream | 1.017 ms | 727 ms | 2.475 ms | 2.249 / 3.440 / 2.537 / 2.413 |
| WebSocket | **749 ms** | **586 ms** | **1.705 ms** | 1.568 / 1.874 / 1.759 / 1.651 |

- gpt-4o-mini chạy được qua WebSocket với Fast mode. Mỗi vòng bớt 0,14–0,27 s; lượt 2 vòng tới chữ đầu bớt ~0,41 s — khớp phần mạng đã đo (~0,28 s/lần gọi). Dao động giữa các lượt cũng hẹp hơn.
- Mẫu rất nhỏ (4 lượt mỗi bên), prompt nhỏ (không phải prompt ~12k token thật).
- Muốn dùng: chuyển `chat_with_tools` sang Responses API qua WebSocket (định dạng tool, input item, function_call_output, previous_response_id với store=false phải cùng kết nối); yêu cầu song song (PARALLEL_REQUIRED_TOOLS) cần lane riêng hoặc kết nối thứ hai. Ước 1 ngày công, sát hạn 20/11.

### LLM_WS trong hệ thống thật (18/11) — commit 98a65aa, runs/ws_smoke_1118 (3 kịch bản, 17 lượt mỗi bên, bỏ lượt đầu nạp reranker)

- **Sai sót phép thử trước:** bên HTTP dùng Responses API, không phải Chat Completions hệ thống đang chạy. Đo lại công bằng (Chat Completions HTTP vs Responses WS, 5 lượt): vòng 1 1.034 → 690 ms, vòng 2 809 → 645 ms, cả lượt 2.024 → 1.680 ms. Fast mode áp dụng qua WS (tier trả về `priority`).
- **Trong hệ thống thật, WS mất cache:** prompt ~12k chỉ trúng ~4k token (HTTP ~10,9k) → vòng chậm hơn (1,48 vs 1,29 s). Gửi kèm `prompt_cache_key` (PROMPT_CACHE_ORDER=on) sửa được:

| | cache trúng p50 | vòng p50 | TTFT p50 / p95 (16 lượt) |
|---|---|---|---|
| HTTP | 0,88 | 1,29 s | 1,58 / 2,98 s |
| WS | 0,73 | 1,48 s | 1,35 / 4,76 s |
| WS + PROMPT_CACHE_ORDER | 0,84 | **1,21 s** | **1,07** / 3,14 s |

- **Quy tắc:** LLM_WS phải đi kèm PROMPT_CACHE_ORDER. Bước tiếp: A/B 40 kịch bản (runs/ab_ws_1118, đã chuẩn bị, chưa chạy — chờ duyệt ~28k VND).

### A/B WebSocket, 40 kịch bản (18/11, duyệt) — runs/ab_ws_1118, ~27k VND, NỐI TIẾP; bỏ 3 lượt khởi động như BTC

| | mốc: tốt nhất + PROMPT_CACHE_ORDER (HTTP) | thử: + LLM_WS |
|---|---|---|
| TSR | 85,0 | 92,5 |
| HR giá/KM % | 13,3 | 13,3 |
| TTFT p50 / p95 (s) | 1,37 / **2,89** | 1,16 / 3,16 |
| Lượt > 2,9 s (cần ≤ 11) | **12** | 14 |
| Vòng LLM p50 / p95 (s) | 1,30 / 1,78 | 1,19 / 1,94 |
| Cache trúng p50 | **0,95** | 0,81 |
| Total p95 (s) | 4,19 | 4,15 |

- WebSocket nhanh hơn ở trung vị nhưng cache thấp hơn → p95 kém hơn. **Không dùng LLM_WS.**
- **Phát hiện chính: khóa cache (PROMPT_CACHE_ORDER) trên HTTP.** So với các lần cấu hình tốt nhất trước, cùng tốc độ API (vòng p50 1,25–1,32 s): cache 0,84–0,90 → 0,95, lượt > 2,9 s 23–25 → 12, p95 3,29–3,36 → **2,89 s**. Kết luận trước đó "cache không còn gì để lấy" là SAI: phân tích trước chỉ xét lượt 1 vòng (cache 97 %); lượt chậm là lượt cache trượt.
- TSR mốc 85,0: trượt SC-GEN-07 (reranker, đã biết), SC-GEN-13, SC-TV-16… — các cuộc từng trượt ở lần khác; 1 lần chạy chưa đủ kết luận.

### Kiểm tái lập cấu hình tốt nhất + PROMPT_CACHE_ORDER (18/11, duyệt) — runs/rep_cache_1118, ~13,6k VND

| | lần 1 (ab_ws_1118 mốc) | lần 2 (tái lập) |
|---|---|---|
| TSR | 85,0 | 87,5 |
| TTFT p50 / p95 (s) | 1,37 / 2,89 | 1,56 / **3,19** |
| Lượt > 2,9 s (cần ≤ 11) | 12 | **22** |
| Vòng LLM p50 / p95 (s) | 1,30 / 1,78 | 1,28 / 1,67 |
| Cache trúng p50 | 0,95 | 0,89 |
| Total p95 (s) | 4,19 | 4,44 |

- **Không tái lập.** Cùng cấu hình, API lần 2 còn nhanh hơn, nhưng cache trúng thấp hơn và p95 3,19 s. Tỉ lệ cache dao động giữa các lần chạy (phía máy chủ OpenAI), cờ không giữ được cố định.
- Tương quan token chưa cache ↔ TTFT chỉ 0,36–0,37, và bị lẫn với số vòng (token cộng dồn qua các vòng) → kết luận trước "khóa cache là nhân tố chính" **chưa chắc**; 2,89 s ở lần 1 nhiều khả năng một phần là may.
- Ước lượng thực tế cho cấu hình tốt nhất: **TTFT p95 khoảng 2,9–3,3 s tùy lần chạy**, Total p95 khoảng 4,2–4,6 s. TSR 85–92 (SC-GEN-07 trượt cả 2 lần — lỗi reranker).

### SC-GEN-07 trượt với reranker (18/11) — phân tích offline, cờ POLICY_QUERY_FULL

- Trượt ở cả hai lần chạy cấu hình tốt nhất: LLM tra `search_policy` bằng truy vấn trần ("bảo hành", "đổi trả"); reranker trả BH-*/DT-01/DT-07, không có **DT-05** (lỗi nhà sản xuất, đổi mới 1-1 trong 30 ngày) → agent nói "quá 7 ngày chỉ sửa".
- Không phải do nhóm ứng viên nhỏ: RERANK_POOL_N 5 → 10 → 15 vẫn không đưa DT-05 vào top-3, thời gian tra 0,23 → 0,73 s.
- Do **nội dung truy vấn**: mọi câu nêu đủ tình huống ("máy mua 12 ngày bị lỗi không lên nguồn có được đổi máy mới không", "đổi trả sản phẩm bị lỗi sau 12 ngày sử dụng"…) đều ra DT-05 trong top-3 (4/5 câu thử; câu chỉ nói "bảo hành …" thì không).
- Ghép lời khách (POLICY_QUERY_CONTEXT) **làm hỏng** truy vấn đầy đủ (kéo về BH-*: 3/4 câu mất DT-05) → dùng POLICY_QUERY_FULL thì tắt POLICY_QUERY_CONTEXT.
- Sửa: `POLICY_QUERY_FULL` (mặc định tắt) — mô tả tham số `query` của search_policy yêu cầu một câu đủ tình huống (tình trạng, số ngày, mong muốn) kèm ví dụ. Chưa đo online (cần duyệt).

**Đo online POLICY_QUERY_FULL (18/11, duyệt, ~1,2k VND) — runs/gen07_fix_1118, gen07_fix2_1118:**
- Ví dụ trong mô tả tool trùng tình huống SC-GEN-07 → đạt 3/3, nhưng LLM **chép nguyên câu ví dụ** → rò rỉ đáp án, không tính.
- Đổi sang ví dụ trung lập (giày đổi size) → **trượt 3/3**: LLM viết câu đủ tình huống nhưng không có chữ "lỗi" ("nhận 12 ngày, không bật nguồn, muốn đổi máy"); reranker trả BH-01/FAQ-04/FAQ-16, không suy ra "không lên nguồn" = lỗi nhà sản xuất. Router (LLM) suy ra được → điểm yếu thật của reranker.
- **Gỡ bỏ cờ POLICY_QUERY_FULL** (không hiệu quả). SC-GEN-07 với reranker vẫn trượt; muốn giữ phải dùng router cho tra chính sách (mất ~0,6 s mỗi lần tra) hoặc chấp nhận trượt.

## m1_final8 — 3×277 cấu hình tốt nhất (18/11, commit a31204e)
- Cả 3 shard của mỗi lượt chạm trần 14.000 VND → mỗi lượt chỉ xong 194/277 kịch bản (ước chi phí sai: thực tế ~14k cho ~64 kịch bản/shard). Đã chi ~133.000 VND.
- So cùng tập kịch bản (191–192 kịch bản hoàn chỉnh, 344–345 cuộc gọi) với m1_final7:
  - r1: TSR 93,3 vs 93,0 | TTFT p50 1558 vs 2095 | p95 3622 vs 6063 | >3 s 9,1 % vs 33,9 %
  - r2: TSR 92,7 vs 92,7 | p50 1551 vs 2155 | p95 3827 vs 5659 | >3 s 10,5 % vs 32,8 %
  - r3: TSR 92,5 vs 93,3 | p50 1549 vs 1889 | p95 3879 vs 5565 | >3 s 11,6 % vs 29,2 %
  - Total p95 (BTC, cả tập chạy) 4583 / 4607 / 4683 ms.
- Kết luận: TSR giữ nguyên, TTFT p95 giảm ~5,8 s → ~3,8 s nhưng CHƯA ≤ 3 s (số 40 kịch bản 2,89/3,19 lạc quan). Chưa thay số nộp.
- Chạy nốt 86/86/85 kịch bản (runs/m1_final8/launch_rest.sh, trần 22k/lượt, chi 16.358 + 15.821 + 15.509 VND). Gộp đủ 3×277 ở runs/m1_final8/cmp_full, chấm bằng reference_eval BTC:
  - TSR 89,2 / 87,4 / 87,4 (TB 88,0) vs m1_final7 88,1 / 87,7 / 89,9 (TB 88,6)
  - TTFT p50 1741 / 1722 / 1697 vs 2106 / 2109 / 1939 | TTFT p95 3997 / 3997 / 3997 vs 6063 / 5643 / 5565
  - Total p95 4772 / 4743 / 4788 vs 7828 / 7329 / 7223 | RQR 0,0 / 0,4 / 0,7
  - Tổng chi m1_final8 ≈ 181.000 VND (~60k/lượt thực tế theo sổ chi phí).

## Phân rã offline m1_final8 (18/11, không gọi LLM) — 3.241 lượt, 459 lượt > 3 s, cần còn ≤ 162
- Bộ đọc chạy NỐI TIẾP trước LLM chính ("đọc muộn" khi khách lần đầu nhắc biến thể, orchestrator `late_stock`): 92/102 lượt > 3 s.
- Bộ đọc song song nhưng tool có tác dụng phụ (order.update, schedule.callback…) phải chờ bộ đọc: nhóm order.update 95/135 lượt chậm, phần chờ p50 ~1,6 s. Bộ đọc p50 1,18 s / p90 1,62 s (prompt 2,8k token, đầu ra JSON có trích dẫn).
- Lượt code nhận (gate) không có EARLY_GATE_TAKEOVER: chờ LLM chính viết xong rồi bỏ → 29 lượt ~3,2 s.
- search_policy: tool_ms p50 621 / p90 1400 ms; đo riêng reranker trên RTX 4060: BM25 8 ms, embedding 46 ms, rerank cả nhóm 309 ms.
- Sàn cấu trúc: vòng 1 gọi tool p50 1,22 / p90 1,57 s + TTFT vòng cuối p50 0,80 / p90 0,98 s.
- Mô phỏng: đọc muộn song song → p95 3,71 s; + EARLY_GATE_TAKEOVER → 3,68; + reranker −300 ms → 3,61; + bộ đọc nhanh 30 % → 3,33; 50 % → 3,24 (7,5 % lượt > 3 s). Cận dưới xóa MỌI phần chờ/chuẩn bị: 3,17 s (7,1 %). → Không đạt ≤ 3 s nếu còn 2 vòng LLM nối tiếp ở ~1/3 số lượt.

## 3 sửa không tốn LLM (18/11, chưa commit, chưa đo bằng LLM)
- `LATE_READ_PARALLEL` (mặc định bật): bộ đọc muộn chạy song song LLM chính; sync_gate() mở gate với tồn kho code đã tra (`stock`). Test mới `LateReadTest.test_late_read_runs_alongside_the_main_llm`.
- `EARLY_GATE_TAKEOVER` mặc định bật.
- Reranker: gom tài liệu theo độ dài + lm_head chỉ ở token cuối. eval_rag_all offline: độ đúng y hệt (60 câu: R@3 88,1, R@5 89,8; 94 truy vấn thật: 67/94), độ trễ (từ khóa + lời khách) p50/p95 238/356 → 202/256 ms.
- Phát hiện: reranker rất nhạy tranh chấp GIL (hàng trăm lệnh GPU nhỏ): 236 ms rảnh → 3,9 s khi 2 luồng Python bận 50 %. `sys.setswitchinterval(0.0005)` khi tạo reranker: còn 0,43 s. Giải thích search_policy p50 621 ms trong m1_final8.
- 1121 test xanh.

### A/B 3 sửa (18/11, duyệt ≤ 28k) — runs/ab_fix3_1118, mốc 3a3a42c (worktree) vs bản sửa, nối tiếp, chi 13.424 + 12.848 VND
39 kịch bản chung (bỏ kịch bản cuối mỗi bên), tốc độ API ngang nhau (vòng 1 p50 1338 / 1338 ms).

| | mốc 3a3a42c | 3 sửa |
|---|---|---|
| TTFT p50 / p95 | 1331 / 3253 ms | 1277 / **2887 ms** |
| lượt > 3 s | 22 / 233 (9,4 %) | **8 / 231 (3,5 %)** |
| Total p95 | 4348 | 4179 |
| đọc muộn: TTFT p50 | 2275 (7 lượt) | 1835 (8 lượt) |
| tool lượt search_policy p50 | 456 | 422 |
| TSR (102 cuộc gọi chung) | 98/102 | 98/102 |

- Trượt chỉ ở bản sửa: SAMPLE-01/call_2 (m1_final8 trượt 3/3 — nhiễu), SC-GEN-06/call_2 (đơn thành quà tặng túi trữ sữa; m1_final8 đạt 3/3), SC-TV-16/call_3 (không tạo đơn; m1_final8 đạt 3/3). Trượt chỉ ở mốc: SC-GEN-07/call_1, SC-ULTRA-09/call_3, TEST-01/call_2.
- Một cặp trên 40 kịch bản; bộ này trước đây cho p95 thấp hơn cả bộ 277 (m1_final8 cả bộ 4,0 s, mốc ở đây 3,25 s).

## Điều tra 18/11 (offline, không gọi LLM)
**SC-GEN-06/call_2 và SC-TV-16/call_3 trượt ở bản 3 sửa — không do 3 sửa:** cả hai lượt hỏng đi đường bộ đọc song song khi có/không đơn nháp (không phải đọc muộn, không có code nhận lượt). Gốc: `product_sku` của bộ đọc dao động.
- SC-GEN-06 lượt 3 ("có tặng túi trữ sữa không"): bộ đọc gán SKU-MB-BAG (quà) dù prompt cấm → lượt chốt `_customer_named_product` lấy SKU bộ đọc của lời gần nhất → đơn túi trữ sữa 119k. Đã xảy ra ở m1_final7 r3.
- SC-TV-16 lượt 2 ("chuyển sang Combi Sugocal"): bộ đọc trả sku=None (3/16 lần chạy: m1_final7 r2, ab_ws router, bản sửa) → lời chắc chắn gần nhất là Joie Pact (lượt 1) → `product_conflict` hỏi lại, không tạo đơn.
**Tool có tác dụng phụ chờ bộ đọc:** khi bộ đọc song song, gần như không chờ (order.update −91 ms so với lượt chỉ tool đọc, schedule.callback +322, crm.get_customer +265). 87/87 lượt order.update chậm của m1_final8 là đọc muộn nối tiếp — đã gỡ bằng LATE_READ_PARALLEL.
**Vòng LLM bị order gate chặn:** 83 lượt chậm (3 lượt chạy) có 1 vòng mà LLM gọi order.* bị chặn (không vào trace), rồi gate hỏi thông tin; 35 lượt bộ đọc báo commit khi đã có đơn nháp.
**Tra trước chính sách (POLICY_PREFETCH) offline trên m1_final8 r1:** 77 lượt LLM gọi search_policy (34 lượt > 3 s); reranker theo lời khách điểm ≥ 0,9 ở 47 lượt, top-3 đều chứa đoạn LLM nhận được (24 lượt chậm); ≥ 0,8: 56 (29 chậm).

### A/B chung sửa gate (DRIVER_RECOMMIT) + POLICY_PREFETCH (18/11, duyệt) — runs/ab_gatepf_1118, cùng code, khác env, chi 13.373 + 12.990 VND
| | mốc (3 sửa, DRIVER_RECOMMIT=off) | thử (+ DRIVER_RECOMMIT + POLICY_PREFETCH) |
|---|---|---|
| TTFT p50 / p95 | 1374 / 3346 ms | 1438 / 3167 ms |
| lượt > 3 s | 18 / 233 (7,7 %) | 14 / 234 (6,0 %) |
| Total p95 | 4280 | 4171 |
| TSR (102 cuộc gọi chung) | 100/102 | 101/102 (trượt riêng SC-GEN-06/call_2 — lỗi bộ đọc quà tặng đã biết) |
| LLM gọi search_policy | 19 lượt | 18 lượt (+ 20 lượt chỉ có tra trước, 2 lượt cả hai) |
- **Tra trước chính sách gần như không bỏ được vòng search_policy:** đoạn điểm ≥ 0,9 rơi vào các lượt LLM vốn không tra; lượt cần tra thì không có tra trước (điểm thấp hoặc chưa kịp, WAIT 0). → giữ TẮT.
- DRIVER_RECOMMIT: bộ 40 kịch bản ít ca (lượt 1 vòng không tool hiển thị 5 / 6); lợi ích chỉ thấy được trên cả bộ.
- **Nhiễu lớn:** cùng cấu hình 3 sửa đo 2 lần: p95 2,89 s / 8 lượt > 3 s (ab_fix3) và 3,35 s / 18 lượt (ab_gatepf mốc). A/B 40 kịch bản 1 cặp không tách được thay đổi < ~10 lượt.

## Sửa lỗi mã sản phẩm của bộ đọc (18/11, chưa commit, chưa đo LLM)
- `_customer_named_product`: đơn nháp đang mở thì SKU bộ đọc của câu KHÔNG chốt không đổi sản phẩm đơn (SC-GEN-06: hỏi quà tặng → đơn túi trữ sữa). `_note_reader_sku` lưu kèm cờ chốt.
- Câu nhắc nhiều mẫu (exact_model_skus > 1) mà SKU LLM đặt là một trong số đó → theo LLM (SC-TV-16: "Joie Pact vẫn hết… chuyển sang Combi Sugocal", bộ đọc trả rỗng → hỏi lại, không tạo đơn).
- Test: 2 test mới (hỏng trên code cũ), sửa bộ đọc giả của test "combo đó" cho có ý định chốt như bộ đọc thật. 1127 test xanh.

## Kết quả m1_final9 (3×277, commit d11210c, 2026-11-18 18:08–20:54)

| Chỉ số | m1_final8 (số nộp) | m1_final9 |
|---|---|---|
| TSR r1/r2/r3 (TB) | 89,2 / 87,4 / 87,4 (88,0) | 87,7 / 88,8 / 87,0 (87,8) |
| TTFT p50 gộp | 1723 ms | 1783 ms |
| TTFT p95 gộp | 3997 ms | 3843 ms |
| Lượt > 3 s | 14,2 % | 17,1 % |
| Total p95 gộp | 4762 ms | 4915 ms |
| RQR / guardrail | 0,0–0,7 / 10–14 | 0,0–0,4 / 13–15 |
| Chi phí cấu hình full 3 lượt | 69.640 VND | 66.555 VND |

- SC-GEN-06/call_2 đạt 3/3; SC-TV-16/call_3 đạt 2/3.
- Trượt nhiều hơn m1_final8 (số lần trượt m8→m9): TEST-113 0→3 và TEST-66 0→2 (order.create không khớp args), TEST-20 1→3, TEST-174 1→3, TEST-08 0→2.
- Đỡ hơn: SC-ULTRA-08/call_4, TEST-114, TEST-12 (2→0), TEST-32 (3→1).
- Kết luận: p95 giảm ~150 ms nhưng tỉ lệ lượt > 3 s tăng; chưa đủ để thay số nộp. TEST-113/TEST-66 nghi do DRIVER_RECOMMIT hoặc sửa reader-sku, cần xem trace.

### A/B EARLY_GATE_TAKEOVER trên TEST-113 + TEST-66 (19/11, runs/ab_egt_1119, ~2.320 VND)

| | TEST-113 | TEST-66 |
|---|---|---|
| EGT bật ×3 | 2/3 đạt (r1: order.create qty 3, bank) | 3/3 |
| EGT tắt ×3 | 2/3 đạt (r3: order.create qty 3, bank) | 3/3 |

- EARLY_GATE_TAKEOVER không phải nguyên nhân. TEST-66 trượt 2/3 trong m1_final9 (LLM gọi handoff.transfer khi khách đọc CCCD/STK) không lặp lại ở 6 lần chạy → dao động của LLM.
- TEST-113: lỗi gốc có sẵn ở cả hai cấu hình — khách giảm 3 → 1 chiếc (và đổi lại COD) nhưng bộ đọc không ghi số lượng mới, đơn nháp giữ qty 3 từ lượt 1; đúng hay sai tùy LLM có báo giá lại qty 1 hay không. m1_final8 0/3 trượt là may.

### Sửa bộ đọc cho TEST-113 (19/11, chưa đo LLM thật)

- Trace lượt 2 của TEST-113 (5/5 lần trượt): bộ đọc ghi "giảm xuống lấy 1 chiếc" vào `price_promo_quote` (asks_price_promo), không ghi qty; 3/5 lần ghi payment = bank từ "chuyển khoản trước" mà khách đang ngại.
- Phần code đưa qty/payment của bộ đọc vào đơn nháp đã đúng (test `DraftQtyPaymentTest` qua cả trên code cũ) → chỉ sửa PROMPT (cả bản dài và bản rút gọn), quy tắc 7: cách trả khách chỉ nhắc lại/ngại không phải lựa chọn; tăng/giảm số lượng là qty mới, không phải chuyện giá.
- `scripts/eval_reply_reader.py` thêm 4 mẫu (cách nói khác TEST-113) + kiểm qty/price_topic. 1129 test offline OK.
- Đo LLM thật (eval_reply_reader, 398 VND): 26/38 đúng; câu kiểu TEST-113 vẫn sai (decline, không qty/payment, price_topic) → BỎ sửa prompt. Giữ test DraftQtyPaymentTest và 4 mẫu đo. Bộ đọc gần như không trích qty; 8 mẫu cũ sai (sửa thông tin bị đọc là decline, "số em đang gọi" không thành affirmed, QR) chưa biết có từ trước không.

## Bỏ vòng LLM chọn tool: chặn search_policy, bộ phân loại nhỏ (19/11, offline, không gọi LLM, trace m1_final9)

Không có router riêng: chính LLM chính chọn tool ở vòng 1 (p50 1,38 s / p90 1,81 s). 447/556 lượt > 3 s có đúng 1 vòng chọn tool rồi mới tới vòng trả lời (cần còn ≤ 163 lượt > 3 s).

**Mô phỏng bỏ trọn vòng 1** (TTFT − vòng 1 − tool): chính sách → p95 3,69 s; + tra sản phẩm → 3,64; + order.update → 3,35; mọi nhóm → 2,70 s. Chỉ bỏ ở gần như mọi lượt mới dưới 3 s.

**Bước 1 — chặn search_policy khi tra trước tự tin.** `POLICY_PREFETCH` chỉ thêm đoạn vào prompt, không bỏ tool; `PREFETCH_HIDE_TOOLS` chỉ ẩn catalog.search / inventory.check / pricing.get_quote → LLM vẫn tự gọi search_policy (giới hạn chưa đủ). Reranker chạy trên máy với 908 câu khách (~0,48 s/câu), so với đoạn LLM nhận được:

| ngưỡng điểm | LLM gọi, đoạn đầu có trong tra trước | tra trước khác (rủi ro) | bỏ được vòng 1 | p95 (không chờ) | p95 nếu chờ tra trước 150 ms mọi lượt |
|---|---:|---:|---:|---:|---:|
| 0,8 | 158 | 9 | 117 (80 lượt > 3 s) | 3,72 s | 3,86 s |
| 0,9 | 143 | 3 | 102 (71) | 3,76 s | 3,90 s |
| 0,95 | 111 | 1 | 74 (50) | 3,80 s | 3,95 s |

Điểm ≥ 0,8 ở cả 1.723 lượt LLM không cần chính sách → điểm reranker không dùng để phân loại "cần chính sách" được. Lợi tối đa ~0,1 s ở p95, và mất ngay nếu LLM phải chờ tra trước (đo 17/11: chờ 0,3 s làm mọi lượt chậm ~0,28 s). **Không làm.**

**Bước 2 — bộ phân loại nhỏ đoán nhóm tool vòng 1** (học m1_final8, kiểm m1_final9, chia theo kịch bản: ~1.130 lượt học / 1.095 lượt kiểm):

| | độ đúng | chính sách: precision / phủ lượt chậm (p ≥ 0,6) | tra sản phẩm | order |
|---|---:|---|---|---|
| TF-IDF ký tự + LR | 65 % | 0,84 / 23/60 | 0,71 / 14/67 | — |
| Qwen3-Embedding-0.6B + LR (~28 ms/câu theo lô) | 58 % | 0,77 / 23/60 | 0,80 / 0/67 | 0,84 / 41/51 |

LLM tự nhất quán: 93 % câu chọn cùng nhóm giữa r1 và r2 (89 % cả 3 lượt) → bài toán đoán được, bộ phân loại nhỏ thua vì quá ít dữ liệu (138 kịch bản). Lần đầu chia theo lần chạy được 91 % là rò dữ liệu (cùng lời khách). Nhóm order đoán khá nhưng là tool ghi. **Không dùng được trước hạn.**

Script: `scripts/probes/{clf_probe,clf_emb_probe,policy_prefetch_probe,policy_block_sim}.py` (chạy từ thư mục Code; clf_probe chạy từ runs/).
