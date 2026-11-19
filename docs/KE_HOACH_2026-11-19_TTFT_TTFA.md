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
  - Giới hạn: bộ 40 kịch bản từng lạc quan hơn cả bộ 277 (18/11: mốc 3,25 s vs 4,0 s cả bộ); lần này mốc 3,60 s. Cần đo 277 kịch bản trước khi nhận "đạt ≤ 3 s". Tool search_policy vẫn ~0,55 s — không phải do GIL của product_mentions; chỗ cắt tiếp theo.

Nguồn: [LiveKit — preemptive generation](https://docs.livekit.io/agents/build/speech/), [Voice agent latency playbook](https://huggingface.co/blog/dvalle08/voice-agent-latency-playbook), [Groq/Cerebras TTFT theo vùng](https://dev.to/max_bob/fastest-ai-inference-api-in-2026-30-days-of-latency-data-for-groq-cerebras-sambanova-and-43-386k), [Artificial Analysis — gpt-4o-mini providers](https://artificialanalysis.ai/models/gpt-4o-mini/providers), [OpenAI Chat Completions — allowed_tools](https://developers.openai.com/api/reference/resources/chat/subresources/completions).
