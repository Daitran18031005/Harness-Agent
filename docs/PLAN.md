# PLAN.md — Kế hoạch 20 bước sửa hệ thống Harness Agent Call Center

> **Dự án**: Sudo Code 2026 — Vòng 1, Harness Agent hỗ trợ Call Center E-commerce (Telesale).
> **Cập nhật lần cuối**: 2026-10-21 (xong cụm 0–10, **bước 15 giai đoạn 1 đã chạy 3 lần (A, B, chạy lại C)** — kết quả và đo lường công bằng ở [CHECKING.md § 11.20–11.22](../CHECKING.md); **471 test xanh**; kế tiếp: chờ bạn trả lời 5 câu ở [DATASET_PLAN.md § 9](DATASET_PLAN.md) rồi mới sinh dữ liệu) · **Nguồn lỗi**: [CHECKING.md](../CHECKING.md) (mã B/A/V/K/D), lỗi mới N1–N15 (kiểm tra 2026-10-20), nhiệm vụ từ cuộc họp team 2026-10-14 (NV1–NV5).
> **Nhật ký thực hiện chi tiết** (đã làm gì / chưa làm gì) nằm ở [CHECKING.md § 11](../CHECKING.md). File này là kế hoạch; mỗi bước xong phải ghi vào CHECKING.md.
> **Cập nhật 2026-10-24 (dataset):** 5 câu ở [DATASET_PLAN.md § 9](DATASET_PLAN.md) đã được trả lời; đã viết mã (0 VND) cho 12 khung đổi, nhãn ca khó "tái hiện lỗi demo", `--batch 10` và trần tích lũy 10.000 VND bằng mã — xem [CHECKING.md § 11.33](../CHECKING.md). Bước [4] DATASET vẫn **chưa sinh lời thoại**, chờ duyệt cụm sửa lỗi demo và 10 khung đầu.

---

**Thuật ngữ:** **P0 / P1 / P2** = nhóm ưu tiên của kế hoạch này (P0 làm trước, P2 = vận hành doanh nghiệp, để sau). **M1 / M2** = hai *mốc* của Ban tổ chức (M2 yêu cầu thêm LLM-judge, simulator, voice…) — "để M2" ở bước 14b là đúng nghĩa *hoãn tới mốc M2*, không phải lỗi gõ của "P2".

---

## 1. Quy tắc làm việc

1. **Làm nhóm P0 trước** (bước 0–10, rồi bước 15 giai đoạn 1). Chưa vào P1/P2 khi chưa có số liệu hợp lệ.
2. **Dừng để duyệt sau mỗi cụm**: `0–3` → `4–8` → `9–10` → đo kết quả (bước 15 giai đoạn 1). Không viết code cụm tiếp theo khi chưa có xác nhận. Đầu P1 có 3 việc độc lập (19 MCP thật, 14a, 16a ASR M1) — vẫn duyệt trước khi bắt đầu.
3. **Tiết kiệm credit**: chỉ một khóa OpenAI, credit hạn chế. Mọi bước đều kiểm bằng test offline (`unittest`, không gọi API); chỉ bước 9 (bộ trích bộ nhớ, ở thời điểm kích hoạt), 11, 13 (khi đo), 15, 16, 16a (nếu dùng ASR API) mới tốn API. **Test cụm 9–10 dùng client LLM giả, không gọi API.**
4. **Không đo giữa chừng**: số liệu offline sau bước 3 không dùng để đánh giá. Chỉ đo ở bước 15.
5. **`full_oracle` chỉ để tham chiếu nội bộ** (trần điểm khi nạp đáp án `facts_established`). **Không đưa vào bảng so sánh A.6, không đưa vào báo cáo/gói nộp**; bảng A.6 chỉ gồm `full` và `baseline_no_memory`.
6. **Đo lường công bằng giữa full và baseline** (duyệt 2026-10-21): (i) claims của CẢ HAI cấu hình được trích bằng CÙNG một bộ trích, báo HR trước/sau mỗi lần sửa bộ trích kèm lý do; (ii) CCR chỉ tính fact **có sẵn lúc đầu cuộc gọi**, agent **dùng thật**, **chưa hỏi mở lại** slot đó và khách **chưa tự nhắc lại** trong cuộc gọi — báo cả cách cũ (công thức BTC trên `facts_used` của trace) và cách mới; (iii) không sửa ground truth của BTC — nghi vấn ghi ở [BTC_DATA_ISSUES.md](BTC_DATA_ISSUES.md); (iv) mỗi lần chạy LLM thật có trần chi phí cứng `--max-cost-vnd`.
7. **Chạy bằng conda env `nlp_env`** (Python 3.12, có scikit-learn): `C:\Users\GIGA\anaconda3\envs\nlp_env\python.exe`. Lệnh `python` mặc định (3.14) thiếu scikit-learn.

---

## 2. Quyết định đã chốt

| Chủ đề | Quyết định |
|---|---|
| Thứ tự | P0 trước; duyệt từng cụm |
| "OpenUI" | **OpenUI của W&B** (`wandb/openui`, sinh mã UI từ mô tả) — dùng để *sinh* giao diện, ghép với backend FastAPI (bước 17) |
| "Tránh call quá nhiều" | **Cả hai**: giảm số cuộc gọi đến khi chốt đơn *và* giảm số tool/lần gọi LLM mỗi lượt (đều phải đo) |
| "Nhận biết nền tảng đã hỏi" | **Đủ 3 phần**: (a) **slot đã hỏi/đã biết** (không hỏi lại, tôn trọng `must_not_ask`); (b) **lịch sử kênh** khách đã liên hệ (Zalo/FB/hotline — `channels_seen`, bước 8); (c) **dữ liệu khách theo từng nền tảng** (khách đã nói/được báo gì ở kênh nào — nhờ provenance `source_channel` của bước 9, để Call Brief nói được "bên Facebook em đã báo chị giá …") |
| MCP | **MCP server thật** (Python MCP SDK / FastMCP), không chỉ mô tả. **M1 bắt buộc ≥ 2 MCP server, trong đó có `mcp-memory`** (tiêu chí 3 — 15% điểm); và **số đo chính thức (bước 15 GĐ2) phải chạy trên kiến trúc MCP** → bước 19 làm ở đầu P1 |
| Model judge (14b, để M2) | **`gpt-6-luna`** (chữ thường). **Đã xác minh 2026-10-21** bằng 1 lệnh `GET /v1/models` (miễn phí): id có trong danh sách của tài khoản (kèm `gpt-5.6-luna`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6.1-sol`) → **tài khoản có quyền thấy model**. *Chưa xác minh*: tham số được hỗ trợ và giá (endpoint này không cho biết) — client tự bỏ `temperature`, dùng `max_completion_tokens` (bước 2b); giá đã điền tạm vào `config/pricing.yaml` (**$0.10 input / $0.50 output mỗi 1M token, nguồn OpenRouter ngày 2026-10-20 — cần đối chiếu giá OpenAI chính thức**). Judge **không được trùng** model agent (có kiểm tra, báo lỗi). Độ ổn định: **cố định seed + `reasoning_effort`** (không dùng temperature) |
| Model router (bước 11) | Cùng model với agent (`gpt-4o-mini`) |
| Mã đơn SAMPLE-03 | **Đã được BTC giải quyết** (script chấm mới chấp nhận mã do `order.create` trả về ở call trước) → giữ mã thật, không cần hỏi |
| Bộ trích bộ nhớ (bước 9) | **Slot dễ → regex, chạy mỗi lượt, không gọi LLM.** **Slot khó → LLM trích, chỉ chạy ở 3 thời điểm**: (1) cuối cuộc gọi, (2) khi chuyển máy/escalate, (3) khi cuộc gọi bị ngắt/timeout — **≤ 1 lần mỗi thời điểm kích hoạt**; nếu đã trích lúc chuyển máy thì lúc cuối cuộc chỉ trích **phần hội thoại mới** sau đó. **Baseline không chạy bộ trích.** Không bao giờ gọi LLM trích mỗi lượt (NV4) |
| PII → LLM (bước 7) | `CURRENT_CUSTOMER` **chỉ** dùng cho số người đang gọi. Số khác khách đọc ra → `<PHONE_n>`; địa chỉ → `<ADDR_n>`; CCCD → `<ID_n>`. Bảng token **chỉ nằm trong bộ nhớ process** (không ghi DB/trace/log). Chỉ mở token cho tool trong danh sách cho phép; kết quả tool bị che lại trước khi trả cho LLM. `<ID_n>` không bao giờ được mở |
| Khóa OpenAI | Tệp chưa gửi cho ai nên **không cần xoay key**. Khi đóng gói nộp bài: loại `.env` và `backup_2026-10-21/` bằng `scripts/package_submission.py` (tự quét chuỗi giống API key trong gói) |

---

## 3. Bảng kế hoạch 20 bước

Trạng thái: ✅ xong · ◐ xong một phần · ⏳ chưa làm · 🔜 để sau (M2/P1/P2).
Cột *Có API*: bước có tốn lệnh gọi LLM thật hay không.

| Bước | TT | Nội dung | Mục tiêu | Lỗi xử lý | File chính | Tiêu chí hoàn thành | Có API |
|---|:-:|---|---|---|---|---|---|
| **0** | ✅ | **An toàn và sao lưu**: sao lưu `data/`, `runs/`; tạo `.env.example`, `.gitignore`; kiểm tra `../Code.rar` có chứa `.env` không; thêm `scripts/package_submission.py` tạo gói nộp đã loại `.env` + `backup_*/` và quét chuỗi giống API key | Không lộ key trong gói nộp, có điểm khôi phục trước khi sửa | K7, N14 | `.env.example`, `.gitignore`, `backup_2026-10-21/`, `scripts/package_submission.py` | Có bản sao lưu; gói nộp tạo bằng script, không có `.env`/`backup_*`, không có chuỗi giống key (có test) | Không |
| **1** | ✅ | **Bộ test offline**: chuyển 14 ca kiểm tra + Phụ lục B của CHECKING thành test; báo lỗi ngay khi thiếu `scikit-learn` | Có lưới an toàn kiểm từng bước mà không tốn API | N12; nền cho mọi bước | `tests/`, `src/env_check.py`, `src/memory/vector_rag.py` | Test chạy được; ban đầu các test lỗi đều đỏ; thiếu sklearn thì báo rõ | Không |
| **2** | ✅ | **Trace đúng thực tế**: ghi tham số tool đã thực sự chạy (có `on`, SKU sau sửa); đo latency thật bằng `perf_counter` và `stream=True` cho TTFT; bỏ `random.randint`, hằng 380 và 115; thêm `call_brief_latency_ms`, `memory_writes`, `customer_input_mode` | Số liệu hiệu năng và trace hợp lệ theo schema BTC | B1, B8, N3, N12 (UI) | `src/llm/client.py`, `src/harness/orchestrator.py`, `src/tracing/tracer.py`, `src/eval/runner.py`, `pipeline.py` | Không còn latency cố định/ngẫu nhiên; trace đủ field tùy chọn; `args` trong trace khớp lệnh tool thật | Không |
| **3** | ✅ | **Runner và CLI chuẩn BTC**: `run_eval.py --scenarios --config --out --seed --repeats`; baseline dùng bộ nhớ mới mỗi call; bỏ bơm `facts_established` (giữ cấu hình `full_oracle` chỉ để tham chiếu nội bộ — **không** đưa vào bảng A.6/báo cáo nộp); đọc `channel`, `channel_identity`, `seed_history`, `input_mode`; reset `mock_tools` mỗi kịch bản; `main.py` ghi ra `runs/demo.jsonl` | Phép so sánh baseline ↔ hệ thống hợp lệ (Phụ lục A.6); BTC chạy được bộ ẩn | B2, B3, B5, B10, A9, K5, N8, N9 | `run_eval.py`, `src/eval/runner.py`, `main.py` | Lệnh chuẩn BTC chạy được; Call Brief call_2 của baseline rỗng; mã đơn không phụ thuộc thứ tự chạy; `main.py` không đụng `runs/full.jsonl` | Không |
| **HOTFIX N15** | ✅ | **Lọc field nội bộ**: `strip_internal()` loại đệ quy mọi field bắt đầu bằng `_` (vd `_internal_price_floor_vnd`) khỏi kết quả tool ngay trong `MCPToolGateway.execute_tool` — trước khi vào LLM, trace và audit log | Giá sàn nội bộ không bao giờ tới LLM/khách/trace | N15 | `src/tools/mcp_gateway.py` | Test: không còn field `_*` trong kết quả gateway, audit, và tool_calls của nhánh LLM; bản gốc không bị sửa | Không |
| **2b** | ✅ | **Client đa nhà cung cấp/đa dòng model**: hồ sơ tham số theo model (`src/llm/model_profiles.py`); tự bỏ `temperature` với model suy luận (`gpt-6-luna`, o-series, gpt-5*); dùng `max_completion_tokens` thay `max_tokens`; **tự học** tham số bị API từ chối ("unsupported parameter") rồi thử lại; ghi `reasoning_tokens` vào `llm_cost`; `assert_distinct_judge()` báo lỗi nếu judge trùng model agent; `LLM_UNSUPPORTED_PARAMS` khai báo thủ công | Đổi model/nhà cung cấp không làm vỡ pipeline; chuẩn bị cho judge `gpt-6-luna` (14b) | — (nền cho 14b) | `src/llm/client.py`, `src/llm/model_profiles.py` | Test với client giả: bỏ tham số trước khi gọi, học từ lỗi và thử lại, đổi tham số token, ghi reasoning_tokens, ném `JudgeModelConflict` | Không |
| **4** | ✅ | **Tool ghi an toàn**: chống gọi lặp theo khóa `(order_id, action, variant)` trong mỗi cuộc gọi; vượt số vòng thì giữ trace các tool đã chạy và **không** chạy nhánh rule-based (tránh tạo đơn trùng); bộ nhớ cuộc gọi lưu tóm tắt kết quả tool; giới hạn kích thước prompt | Không phát sinh phí hoặc đơn trùng; lời agent khớp trạng thái đơn | A2, A10, N4, N6 | `src/harness/orchestrator.py`, `src/llm/client.py`, `src/tools/mcp_gateway.py` | `order.update` gọi lặp bị chặn; ca vượt 6 vòng không có `order.create` thứ hai; SAMPLE-03 chỉ có 1 lần đổi size | Không |
| **5** | ✅ | **Ghi nhớ sản phẩm đúng**: chỉ ghi `product_advised` khi `order.create` thành công (hoặc LLM xác nhận qua tool); quà tặng/phụ kiện không ghi đè sản phẩm chính; biến thể (`SKU-SN-CAS-39-DEN`) ghi sản phẩm cha + `variant_sku` | Call sau mang đúng sản phẩm đã tư vấn | A1, D3 | `src/harness/orchestrator.py`, `src/memory/profile.py` | SAMPLE-01: call_2 đặt `SKU-AP-Y` 5.200.000đ, không đặt màng lọc 690.000đ | Không |
| **6** | ✅ | **Guardrail**: bỏ "mã đơn" khỏi cụm câu báo đã lên đơn; không thay câu sau khi tool đã chạy; đối chiếu số tiền/phí/tồn kho trong lời LLM với kết quả tool; chặn "giá vốn", không chặn nhầm "quy định đổi trả"; chặn "em là nhân viên thật"; cho phép SĐT 10 số; (lọc `_*` khỏi kết quả tool đã làm ở HOTFIX N15); luật "em là trợ lý AI", không bình luận đối thủ, quy trình xóa dữ liệu | Không bịa giá, không lộ thông tin nội bộ, không chặn nhầm | A7, A8, V5, N1, N2, N15 | `src/harness/guardrail.py`, `src/harness/orchestrator.py` (system prompt), `src/tools/mcp_gateway.py` | 9 ca guardrail đúng cả hai chiều; context LLM không còn `_internal_price_floor_vnd`; câu có "mã đơn" không bị thay | Không |
| **7** | ✅ | **Normalizer và PII**: sửa khóa `"k"` trùng; bỏ `"sai"`, `"a"`, `"c"`, `"e"` khỏi từ điển thay thế tuyệt đối; ITN số tiền tổng quát (triệu/nghìn/trăm/mươi/lẻ/rưỡi); ITN SĐT đọc bằng chữ, ngày giờ tương đối; **chỉ đưa text đã che PII vào LLM, trace, bộ nhớ**; **token PII**: `CURRENT_CUSTOMER` chỉ cho số người gọi, số khác `<PHONE_n>`, địa chỉ `<ADDR_n>`, CCCD `<ID_n>`; bảng token chỉ trong bộ nhớ process; chỉ mở token cho tool trong danh sách cho phép (`customer_phone`/`address` của `order.create`, `order.status`, `pricing.get_quote`, `schedule.callback`, `handoff.transfer`; `<ID_n>` không bao giờ được mở); kết quả tool che lại trước khi trả cho LLM; lời agent mở token trước khi nói với khách (trừ `<ID_n>`); prompt không chứa SĐT thô và toàn bộ `profile_facts` | Hiểu đúng tiếng Việt; tuân thủ PII (NĐ 13/2023) | V1, V2, V3, V4, N13 | `src/channels/normalizer.py`, `src/harness/orchestrator.py`, `src/tools/mcp_gateway.py` | 13 ca normalizer xanh; regex PII của BTC không bắt được gì trong trace; `test_phone_token_substituted` xanh; test ca "giao cho người khác, số khác" (SĐT/địa chỉ khác người gọi → token riêng, tool nhận đúng giá trị thật, kết quả tool không lộ giá trị thật cho LLM) | Không |
| **8** | ✅ | **Định danh đa kênh**: map đúng tên kênh; nối FB/Zalo với SĐT khi khách cung cấp SĐT (`link_identities`) và **gộp bộ nhớ**; SĐT dùng chung có bước xác minh tên, không dùng chung mã `AMBIGUOUS`; bỏ mặc định "Hoa"/"chị", xưng hô lấy từ CRM/hội thoại; **Call Brief ghi lịch sử kênh** (nền cho "nhận biết nền tảng đã hỏi") | Một khách một mã xuyên kênh; xưng hô đúng | A3, A6, A11, N7 | `src/identity/resolver.py`, `src/identity/identity_map.py`, `src/harness/call_brief.py`, `src/channels/normalizer.py` | SAMPLE-04 và SC-GEN-06: call_1 (Fanpage) và call_2 (Hotline) cùng `customer_id`; số lạ không bị chào "chị Hoa"; SC-GEN-04 có bước xác minh | Không |
| **9** | ✅ | **Bộ nhớ và DB (D-P0)**: **bộ trích bộ nhớ 2 tầng** (thay cho việc nạp đáp án): *slot dễ* (diện tích, trẻ nhỏ, size, màu, SĐT/ngày...) trích bằng **regex mỗi lượt, không gọi LLM**; *slot khó* (`blocker`, ngân sách, giá đối thủ, ý định...) trích bằng **LLM ở 3 thời điểm: cuối cuộc gọi, khi chuyển máy/escalate, khi cuộc gọi bị ngắt/timeout**; tự ghi episode ở cả 3 thời điểm; áp TTL khi đọc; sửa `intent`/`last_intent`; xóa nhất quán mọi tầng/bảng; UNIQUE cho fact và episode (sắp theo `call_date`); provenance (`source_call`, `source_turn`, **`source_channel`**); đường dẫn DB tuyệt đối; checkpoint WAL khi thoát; ghi theo giao dịch; kiểm tra `order_id` còn tồn tại; script seed demo idempotent | Bộ nhớ do hệ thống tự ghi, đúng, bền, xóa được trọn vẹn | A4, A5, N5, N11, K6, D1, D2, D4–D9, D13–D15 | `src/memory/*.py`, `src/memory/memory_extractor.py` (mới), `src/memory/sqlite_store.py`, `scripts/seed_demo_db.py` (mới) | Mỗi cặp (khách, key) chỉ 1 dòng active; fact `ttl_days=0` hết hiệu lực; chỉ copy file `.db` vẫn đủ dữ liệu; `blocker` được tự ghi khi không nạp đáp án; cuộc gọi bị ngắt/chuyển máy vẫn có episode; fact có provenance đủ 3 trường (`source_call`, `source_turn`, `source_channel`); xóa khách xóa trọn vẹn (profile, episode, working, identity link) có test từng bảng; Call Brief demo báo đúng 1 cuộc gọi trước | **Có** (≤ 1 lần mỗi thời điểm kích hoạt; nếu đã trích lúc chuyển máy thì cuối cuộc chỉ trích phần mới; cùng model agent; **baseline không chạy bộ trích**; test dùng client LLM giả) |
| **10** | ✅ | **Bộ trích `claims`/`questions` ở runtime**: trích claim từ lời agent (số tiền/phí/ngày giao/bảo hành), đặt tên field khớp đáp án BTC (`final_price_vnd`, `list_price_vnd`, `total_vnd`, `exchange_fee_vnd`, `promo_*`, `delivery_days`, `warranty_months`…); phân loại mọi câu hỏi theo slot và open/confirm; ghi rõ cách trích trong tài liệu | HR và RQR đo đúng, chịu được việc BTC chấm tay 20 lượt | B6, B7, N10 | `src/harness/extractor.py` (mới), `src/harness/orchestrator.py` | Số claim kiểm chứng được tăng rõ so với 11; câu "không mất phí" khi tool báo 60.000đ bị tính sai; RQR có mẫu số > 0 | Không |
| **11** ★NV2 | ◐ mã + test ✅; **§ 11.96 (2026-10-28): chi phí/quyết định router vào trace + trần chi phí**; còn mở: multi-hop, từ chối câu ngoài tài liệu (cần đo LLM thật) | **Chọn policy bằng LLM, 2 tầng**: mục lục 11 file public (tên, mô tả, ngày hiệu lực); router (`gpt-4o-mini`, `temperature=0`, JSON) trả `{files[], as_of_date, answerable}`; TF-IDF chỉ tìm trong file đã chọn; chọn phiên bản chính sách theo ngày mua; `answerable=false` → "chưa có thông tin" (PB-05); router lỗi → quay về TF-IDF toàn bộ. Baseline và hệ thống dùng cùng router | Không đưa hết tài liệu cho LLM; truy hồi chính xác hơn | NV2; RAG yếu (multi-hop, abstain 0%, chính sách cũ) | `src/memory/policy_router.py` (mới), `src/memory/semantic_rag.py`, `scripts/eval_policy_router.py` (mới), `tests/test_policy_router.py` (mới) | `--rag` 60 câu: Recall@5 ≥ 81.4%; multi-hop full recall và tỷ lệ từ chối tăng; SAMPLE-07 đạt; có báo cáo độ trễ + chi phí thêm | **Có** (~1 lần gọi gpt-4o-mini mỗi câu hỏi chính sách; **đã đo LLM thật 2026-10-28 với mã LAI (2 kết quả đầu từ file chọn + bù từ toàn bộ): Recall@3/@5 = 81,4/88,1 (ĐẠT ≥ 81,4%; TF-IDF 76,3/81,4; strict chỉ 74,6); multi-hop full @3/@5 = 8,3/25,0 (chưa tăng); từ chối unanswerable 0%, restricted 60%, từ chối nhầm 2,1%; 465 VND/60 câu, 1.087 ms và 7,76 VND/lần; k=2 chọn trên chính 60 câu; SAMPLE-07 chưa kiểm; 864 test xanh** — CHECKING § 11.82) |
| **12** ★NV3 ⬆ *sớm trong P1* | ◐ **mã + test ✅ (§ 11.26); đã đo LLM thật 1 lần — chạy D, § 11.29: 7/7 TSR, 0 kịch bản tụt so với C, SAMPLE-01 đúng; gọi LLM/lượt 2,46 → 2,59 (chưa đạt tiêu chí "không tăng"); nhánh hai lựa chọn chưa gặp ca nào** | **Schema slot + ProductRetriever + shortlist trả SKU chuẩn — làm SỚM trong P1 (song song 19 và 14a), KHÔNG vá prompt riêng cho từng kịch bản.** `slot_schema` là **dữ liệu** (không hard-code theo tên sản phẩm): mỗi luật = (slot khách nêu → thuộc tính THẬT trong catalog, phép so `eq/gte/lte/contains`, trọng số, cứng/mềm, từ khóa/đồng nghĩa), vd `has_children → child_safe_lock` (cứng/ưu tiên cao), `room_area_m2 → room_area_m2` (diện tích phủ ≥ phòng), `budget_vnd → giá` (vượt ngân sách bị trừ điểm theo mức nhưng **không loại** sản phẩm duy nhất đáp ứng ràng buộc an toàn), `warranty/stages/material/max_weight_kg/volume_ml…` theo thuộc tính có trong từng danh mục; luật chỉ áp dụng ở danh mục CÓ thuộc tính đó (không có thì trung tính). `ProductRetriever` chấm điểm mọi SKU bằng các luật này, trả top-k **kèm lý do chấm**; tool nội bộ `product.shortlist` trả **variant_sku chuẩn** (hết lỗi `unknown_sku`, bớt vòng gọi LLM) và agent **chốt 1 sản phẩm**; `ClarificationPolicy` if-else (slot đã biết/đã hỏi, chọn 1 slot phân biệt tốt nhất, ≤ 1–2 câu/lượt, tôn trọng `must_not_ask`, dùng lịch sử kênh và dữ liệu theo nền tảng) | Chốt đúng sản phẩm theo ràng buộc của khách bằng **luật chung**; hỏi ít mà trúng | NV3; lỗi chọn sản phẩm (SAMPLE-01, bước 15 GĐ1: chọn AirPure X thay vì Y có khóa trẻ em) | `src/catalog/slot_schema.py` (+ file dữ liệu luật), `retriever.py`, `clarification.py` (mới), `src/channels/normalizer.py`, `src/harness/orchestrator.py` | **Test trên nhiều sản phẩm/ngành, không chỉ AirPure** (catalog hiện có thuộc tính: máy lọc không khí `child_safe_lock`/`room_area_m2`; máy lọc nước `stages`; giày `material`/`return_days`; mẹ & bé `max_weight_kg`/`volume_ml`; hầu hết có `warranty_months`): (1) ≥ 8 sản phẩm thuộc ≥ 3 danh mục, mỗi luật có test dương và test âm; (2) hoán đổi thứ tự/tên sản phẩm, thêm sản phẩm giả vào catalog thử → kết quả đổi đúng theo thuộc tính; (3) có trẻ nhỏ + ngân sách vượt nhẹ → chọn sản phẩm có khóa trẻ em, ngược lại khi catalog thử không có sản phẩm nào có khóa → chọn theo giá; (4) **SAMPLE-01 đạt mà trong mã/prompt không có tên SAMPLE-01/AirPure**; (5) shortlist luôn trả SKU hợp lệ (0 `unknown_sku`); (6) số lần gọi LLM/lượt không tăng; (7) chạy lại 7 kịch bản: không kịch bản nào tụt so với trước | Không |
| **13** ★NV4 | ◐ mã + test ✅ (§ 11.85, 875 test); chờ đo LLM thật; ngày giao chưa tra sẵn | **Chủ động đưa thông tin** *(cũng là cách giảm TTFT số (a), xem § 3.1)*: kiểm tra giá/tồn kho/KM bằng tool lúc nhận diện khách → vào Call Brief (`precomputed_parts`), tính vào `call_brief_latency_ms`; gom giá cuối + KM + tồn kho + ngày giao (tính ngày nghỉ) + bảo hành vào một câu; đọc lại đơn một lần trước `order.create` (PB-09); nhắc tối đa 2 thông tin cũ (PB-01); LLM không tra lại những gì đã kiểm tra | Giảm số lượt, số cuộc đến chốt, số tool/lần gọi LLM mỗi lượt | NV4, A10, rubric J01 | `src/harness/call_brief.py`, `src/harness/orchestrator.py`, system prompt | So với trước khi sửa: số lượt/cuộc (3), số cuộc đến chốt (1.83), tool/lượt (1.54), `llm_calls`/lượt đều giảm; TSR và HR không tụt | Có (khi đo) |
| **12b** | ✅ mã + test (CHECKING § 11.30); đã đo LLM thật (run D→I) | **Order gate bằng code (người dùng yêu cầu 2026-10-21)** — checklist sản phẩm/biến thể, số lượng, tên & SĐT nhận, địa chỉ, thanh toán; trường có sẵn → câu xác nhận, thiếu → hỏi; đủ → đọc lại đơn 1 lần → chỉ tạo đơn khi lượt sau khách đồng ý rõ ràng; ghi `order_gate` vào trace; bộ điều khiển bằng code chuyển tiếp các lượt trả lời gate; + xưng hô theo khách tự xưng, slot `competitor_price_vnd` bằng regex, liệt kê đủ mẫu khi khách hỏi "có các mẫu nào" | Không tạo đơn thiếu thông tin / chưa được khách đồng ý | Lỗi đặt đơn trên UI | `src/harness/order_gate.py`, `orchestrator.py`, `src/catalog/textmatch.py` | `tests/test_order_gate.py` (31), `test_catalog_listing`, `test_pii_vault`; chạy lại 7 kịch bản: TSR 100% → 14,3% với lời khách kịch bản cố định (0 đơn), 85,7% với khách mô phỏng hợp tác; **cần quyết định về cách BTC chấm** | Có (6.556 VND, vượt trần "một lần chạy") |
| **14a** ★NV1 | ✅ **xong, không tốn credit (CHECKING § 11.81): `python -m evaluation --trace runs/X/full.jsonl` → report.json, failures.txt, manual_review.csv (20 lượt); dead code `src/eval/{evaluator,simulator,human_gate,improvement}.py` đã gỡ; còn lại: điền tay file 20 lượt (người chấm)** | **Pipeline đánh giá tách riêng, chỉ dùng code**: package `evaluation/` chạy process riêng, chỉ đọc trace + kịch bản, không import pipeline; gọi `reference_eval.py`; công cụ liệt kê ca sai; kiểm tra "đọc vẹt" bằng luật (≤ 2 fact cũ trong câu chào); file mẫu chấm tay 20 lượt; dọn dead code `src/eval/` | Đánh giá độc lập runtime, không tốn credit | NV1 (phần không LLM), dead code `evaluator/simulator/human_gate/improvement` | `evaluation/` (mới: `scoring`, `failures`, `parrot`, `sheet`), `src/eval/*` | Chỉ cần trace là chấm lại được; có báo cáo ca sai; có bảng 20 lượt chấm tay | Không |
| **14b** ★NV1 | 🔜 (M2) | **LLM-judge + simulator**: judge 12 tiêu chí đúng prompt BTC; simulator LLM theo 8 quy tắc, 3 seed, không lộ đáp án; Cohen's kappa. Model: **`gpt-6-luna`** (id đã xác minh có trong tài khoản; còn phải xác nhận giá + tham số, xem § 2); judge phải khác model agent (`assert_distinct_judge`). Thiết kế đổi được nhà cung cấp: interface `JudgeClient`, cấu hình `EVAL_LLM_PROVIDER/MODEL/API_KEY`, tự validate JSON schema, lưu provider/model/output thô; judge không biết trace thuộc cấu hình nào; che PII trước khi gửi | Đáp ứng M2, đánh giá khách quan, đổi nhà cung cấp được | NV1 (phần LLM) | `evaluation/judge.py`, `evaluation/judge_clients/`, `evaluation/simulator.py` | Kappa với người ≥ ngưỡng trên 20 mẫu; **cố định seed + `reasoning_effort`; chấm 2 lần trên 20 trace, tỷ lệ trùng ≥ 90%; nếu thấp hơn thì chấm 3 lần lấy đa số**; độ lệch TSR giữa 3 seed ≤ 10 điểm; đổi nhà cung cấp có bảng so sánh cũ/mới. Giá model nằm trong `config/pricing.yaml`. **Chốt 2026-10-21 (người duyệt): model sinh lời khách của dataset = model judge (`gpt-6-luna`) → rủi ro chấm "cùng họ" được kiểm soát bằng kappa với người trên 20 mẫu; nếu kappa thấp thì đổi judge sang `gpt-6.1-sol` (batch) hoặc nhà cung cấp khác (interface `JudgeClient` cho phép đổi, không sửa pipeline)** | **Có** (ước tính **~$0.5/vòng, batch ~$0.3**; giá gpt-6-luna $0.10 / $0.50 mỗi 1M token input/output — nguồn OpenRouter 2026-10-20, **cần đối chiếu giá OpenAI chính thức**) |
| **15** | ◐ GĐ1 ✅ · GĐ2 ✅ đã chạy (xem CHECKING §11.87, chạy lại §11.90: RQR đạt; TSR 68,2% (sinh 93,3%), HR giá/KM 6,2%, TTFT p95 8,3 s — chưa đạt TSR, HR, TTFT; chạy lại §11.92: TSR 71,2% ĐẠT (sinh 93–100%), RQR giảm 87,3% ĐẠT, HR giá/KM 9,5% (seed 2–3: 5,9% = GEN-01 lệch sự thật; seed 1 dính lỗi mạng), TTFT p95 14 s do lỗi kết nối — chưa đạt HR, TTFT; chạy lại §11.94: TSR 72,7% (sinh 100% 3/3), RQR giảm 76,5%, HR giá/KM 6,0% (chỉ còn GEN-01 lệch sự thật), TTFT p95 6,7–7,3 s ở seed không bị API đứng — chưa đạt HR, TTFT) | **Chạy đánh giá thật**, `temperature=0`, cố định seed. **Giai đoạn 1** (sau P0): 7 kịch bản public × 2 cấu hình × 1 seed (~80 lượt) để kiểm tra các bản sửa. **Giai đoạn 2** (sau 4–13, 14a, 16a **và bước 19 — chạy trên kiến trúc MCP**): 22 kịch bản × 2 cấu hình × 3 seed, ≥ 100 lượt, bỏ 3 lượt warm-up; báo cáo mean ± std; phân tích ≥ 10 ca sai | Có số liệu chính thức, hợp lệ để nộp | B4, B9, K4 | `run_eval.py`, `evaluation/`, `runs/` | Bảng A.6 mean ± std; **RQR giảm ≥ 40%, TSR ≥ 70%, HR giá/KM ≤ 5%, hệ thống tốt hơn baseline**; giai đoạn 1: hệ thống ≥ baseline ở TSR và CCR, HR giảm | **Có** (GĐ1 **thực tế 4.648 VND tổng cộng 3 lần: A 939 + B 2.240 + chạy lại C 1.469**, mỗi lần dưới trần 5.000 riêng; chi phí/lượt giảm từ ~28 còn ~19 VND nhờ prompt caching + prompt gọn; GĐ2 trên bộ 135 cuộc ≈ **25 nghìn VND/seed**, 3 seed ≈ 75 nghìn — xem [DATASET_PLAN.md § 6](DATASET_PLAN.md)) |
| **16** | 🔜 | **Vòng cải tiến, ASR và RAG**: nối `ImprovementLoop` (Knowledge Gap + Exemplar Bank) với danh sách ca sai (từ 14a; dùng judge khi có 14b); `HumanReviewGate` thành CLI duyệt có rollback; ASR thử model lớn hơn hoặc PhoWhisper, ≥ 20 file; xuất `asr/hypotheses.json` (có `turns[].idx`) và `rag_results.json` để chạy `--asr`, `--rag` | Đáp ứng tiêu chí 5 (tự cải tiến), đo ASR/RAG theo chuẩn BTC | K3, V6 | `evaluation/improvement.py`, `evaluation/human_gate.py`, `eval_asr.py`, `src/channels/offline_asr.py` | Số liệu vòng 0 → vòng 1 trên cùng bộ test, không tụt chỉ số; `reference_eval --asr --rag` chạy được | **Có** |
| **16a** | ◐ **GĐ1 ✅ (tích hợp + đo trên 4 file TTS)** · GĐ2 🔜 (≥ 20 file, Nam/Trung, nhiễu thật) | **Đo ASR chuẩn M1 — tách khỏi bước 16, làm ngay đầu P1.** *(2026-10-21: nhóm chọn model **Gipformer 1.5 68M RNN-T**, ONNX int8, qua `sherpa-onnx==1.13.8`; **đã duyệt đổi `ASR_BACKEND` mặc định sang `gipformer`, whisper là dự phòng**)*. **Luật quay lại (nhóm duyệt):** khi đo trên **≥ 20 file** mà gipformer kém whisper về **WER hoặc entity accuracy** thì **đổi mặc định lại về whisper và báo nhóm** (không đợi hỏi). Mặc định hiện không đặt `ASR_BACKEND` → gipformer; nếu model không nạp được thì tự rơi về whisper kèm cảnh báo. **GĐ1 đã làm:** `GipformerASR` trong `src/channels/offline_asr.py` (kiểm SHA-256, báo rõ file thiếu); chữ HOA → thường → `RequestNormalizer`; **VAD** `ASR_VAD=silero\|energy\|auto` (Silero từ release chính thức k2-fsa/sherpa-onnx; `auto` = hợp Silero + năng lượng vì mỗi cái bỏ sót ca của cái kia), cắt đoạn ≤ 20 s; mô phỏng kênh điện thoại + nhiễu môi trường (`audio_sim.py`); mốc lượt → `turns[].idx` chỉ khi có `<id>.segments.json`; trích **đủ** thực thể theo định nghĩa của BTC (sku, color, promo_expiry, payment, in_stock, blocker, size, số tiền, SĐT, mã đơn; `config/product_aliases.json`); xuất `hypotheses.json` và chấm bằng `wer_cer` của BTC; `scripts/compare_asr.py`; gói nộp **kèm model mặc định** + LICENSE MIT + README tác giả. **Số liệu (đều là "trên audio TTS sạch, giọng Bắc, n = 4 file"; nhiễu/kênh điện thoại là mô phỏng):** gipformer(auto, `ASR_VAD=auto` = mặc định đã chốt) WER thô **8,4%**, ITN 2 vế 9,4%, entity số tiền 90,9%, SĐT 100% (n=1), RTF ≈ 0,04–0,05, RAM đỉnh ~0,6 GB; whisper-base 43,0% / 37,5% / 27,3% / 0%; whisper-small 32,6% / 24,9% / 54,5% / 0%, RTF ≈ 0,75, nạp 17 s. **Entity accuracy chính thức** (`reference_eval --asr`): **100% (29/29) — trong tập phát triển (D01–D04), luật viết sau khi xem dữ liệu** (không phải khả năng khái quát; luật ITN + bảng cách đọc SKU đã **KHÓA** ở `config/asr_rules.lock.json` phiên bản `asr-rules-v1-2026-10-21`, test đỏ nếu đổi; khi có audio mới thì đo trên tập CHƯA THẤY và báo riêng; trên lời khách của 7 kịch bản public chưa dùng để viết luật: 11/11 trường có trong lời khách; chưa có số ngoài-tập cho lời agent). **GĐ2 (còn lại):** đo lại trên **≥ 20 file** sau khi có dataset (giọng Nam/Trung tự thu, nhiễu thật) rồi áp luật quay lại; mốc lượt cho audio mới; đổi số→chữ nếu cần nộp whisper; mở rộng/kiểm bảng cách đọc tên sản phẩm ngoài D01–D04. **Kết quả VAD (Silero hỏng ở kênh điện thoại + tạp âm; VAD năng lượng hỏng ở nhiễu trắng ≤ 5 dB) chỉ trên NHIỄU GIẢ LẬP — cần kiểm lại trên ghi âm điện thoại thật.** **ASR đã CHỐT, không tinh chỉnh thêm cho tới khi có audio mới.** *Bảng WER trong model card Gipformer là số do tác giả công bố trên bộ riêng, KHÔNG phải số của dự án.* | Đáp ứng yêu cầu M1 về ASR sớm, không phụ thuộc vòng cải tiến | K3, V6 (phần đo) | `eval_asr.py`, `src/channels/{offline_asr,audio_vad,audio_sim,asr_postprocess,asr_entities,asr_hypotheses}.py`, `scripts/{compare_asr,export_hypotheses}.py`, `config/product_aliases.json` | Báo cáo WER/CER + entity accuracy (tiền, SĐT) trên đúng số file thực có và nêu rõ còn thiếu bao nhiêu so với 20; `reference_eval --asr` chạy được (**đã chạy được cho D01–D04, chưa có `turns`**) | Không (ASR local, không gọi API) |
| **17** ★NV5 | ✅ **xong, không gọi LLM (CHECKING § 11.83): `uvicorn api.app:app`; 6 endpoint + `/sessions`; API tự cấp `call_name`/`turn_num`; các lượt chạy tuần tự bằng khóa pipeline (đánh đổi: phiên đồng thời xen kẽ theo lượt, không chạy song song thật); trace rút gọn đã che PII; `tests/test_api.py` 17 test** | **Backend API (FastAPI)**: `/chat` (session id, nhiều phiên), `/call-brief`, `/memory/timeline`, `/tools/log`, `/orders`, `/asr`; sửa `call_name` luôn `call_1` và đếm lượt UI | Tách UI khỏi pipeline; ≥ 2 phiên đồng thời | NV5 (nền), UI dùng chung 1 pipeline | `api/` (mới), `pipeline.py` | 2 phiên chạy song song không lẫn bộ nhớ; mọi endpoint có test | Không |
| **18** ★NV5 | ✅ **giao diện web `ui/index.html` + `scripts/run_demo.py` (CHECKING § 11.97; dựng tay, KHÔNG dùng W&B OpenUI; chưa kiểm với LLM thật)** | **Giao diện bằng W&B OpenUI**: sinh mã UI (HTML/React) từ mô tả — chat, Call Brief, dòng thời gian bộ nhớ, audio → ASR — ghép với backend bước 17; giữ Streamlit làm trang quản trị/đánh giá tới khi UI mới đủ. OpenUI cần một LLM sinh giao diện: có thể dùng Ollama chạy local để không tốn credit | UI tối thiểu M1 của mentor | NV5 | `ui/` (mới), `ui_app.py` | Demo đầu-cuối khách gọi lại: Call Brief hiện đúng, dòng thời gian bộ nhớ đúng | Có (khi demo) |
| **19** ⬆ *đầu P1* | ◐ **3 MCP server thật (`mcp-catalog`, `mcp-crm`, `mcp-memory` — nơi ghi duy nhất) + client + phân quyền + test ✅ (CHECKING § 11.27, 11.32); còn A2A, tài liệu, chạy `run_eval` thật trên MCP** | **MCP thật và tài liệu — làm ĐẦU P1, song song với 14a, BẮT BUỘC xong TRƯỚC 15-GĐ2** (M1 bắt buộc ≥ 2 MCP server, chiếm 15% điểm; số đo chính thức phải chạy trên kiến trúc MCP): dựng MCP server bằng FastMCP — **`mcp-memory`** (đọc/ghi bộ nhớ khách, bắt buộc, có phân quyền ghi), **`mcp-catalog`** (`catalog.search`, `inventory.check`, `pricing.get_quote`) và **`mcp-crm`** (`crm.get_customer`; tạm gồm `order.*`, `schedule.callback`, `handoff.transfer`, tách `mcp-order` ở M2); kết quả của `mock_tools.py` giữ nguyên; agent làm MCP client qua stdio; mỗi tool có danh sách caller được phép; đo độ trễ tăng thêm; thay `MCPToolGateway` (giữ nguyên hành vi lọc `_*`, token PII, chống gọi lặp); bỏ/nối các agent A2A chỉ có trên danh nghĩa; cập nhật `PIPELINE.md`, `CHECKING.md` (N1–N15, NV1–NV5) | ≥ 2 MCP server thật; số đo chính thức chạy trên kiến trúc MCP; tài liệu khớp code | K1, K2 | `mcp_servers/` (mới), `src/tools/mcp_gateway.py` (thành client), `src/agents/specialists.py`, `PIPELINE.md`, `CHECKING.md` | ≥ 2 server khởi động được và agent gọi qua giao thức MCP (có `mcp-memory`); toàn bộ test hiện có vẫn xanh trên đường MCP (N15, token PII, chống gọi lặp không bị mất); độ trễ tăng thêm được đo; mọi số liệu trong tài liệu tái lập được từ `runs/` | Không |

### 3.1. Giảm TTFT p95 (hiện 4,9 s trên 39 lượt; mục tiêu M1 ≤ 3 s — cần ≥ 100 lượt để kết luận)

**Chẩn đoán (đã đo ở bước 15 GĐ1):** mỗi lượt có ~2,5 lần gọi LLM tuần tự (tối đa 4) và prompt ~6.400 token; TTFT = thời gian các vòng tool xong **trước** + chờ token đầu của vòng cuối. Từ lần chạy lại, trace ghi `latency_detail` (số vòng LLM **trước** token đầu, thời gian từng vòng, thời gian tool, chờ token đầu của vòng cuối, `cached_tokens`) để biết đòn bẩy nào đáng làm.

| Cách giảm | Mô tả | Trạng thái | Tác động kỳ vọng / cách kiểm |
|---|---|---|---|
| **(a)** Tra sẵn giá/KM/tồn kho vào Call Brief (bước 13) | Lúc nhận diện khách đã gọi `pricing/inventory` cho sản phẩm trong hồ sơ và đưa kết quả vào Call Brief → lượt đầu của call_2/call_3 không cần vòng tool; LLM không tra lại thứ đã kiểm | 🔜 bước 13 | Giảm `rounds_before_first_token` ở lượt có tool; đo `call_brief_latency_ms` tăng bao nhiêu |
| **(b)** Phần tĩnh của system prompt lên đầu để tận dụng prompt caching | **Đã làm:** thứ tự `[system tĩnh] [lịch sử — chỉ nối thêm cuối] [ngữ cảnh Call Brief — đổi theo lượt] [lời khách]` (trước đây ngữ cảnh đứng trước lịch sử nên mỗi lần nó đổi thì mất cache phần lịch sử); schema tool đứng trước trong tiền tố nên phải ổn định trong cuộc gọi; có test tiền tố ổn định giữa các khách/lượt | ✅ (mã + test); hiệu quả thật xem `cached_tokens` ở lần chạy lại | Tỉ lệ token prompt được cache; giá cache tính riêng trong `config/pricing.yaml` (cần đối chiếu giá OpenAI) |
| **(c)** Cho phép gọi tool song song | Khi LLM trả nhiều tool_call trong cùng một vòng, chạy các tool **chỉ-đọc** (catalog/pricing/inventory/order.status) song song (luồng); tool **ghi** vẫn tuần tự và vẫn chống gọi lặp; có thể thêm `parallel_tool_calls` rõ ràng ở API | 🔜 (làm cùng/ sau bước 12) | Giảm `tool_ms` và số vòng; bước 12 (shortlist) cũng giảm vòng vì bỏ lỗi `unknown_sku` |
| (d) *(đề xuất thêm)* | Rút ngắn prompt (bỏ lặp), model nhỏ hơn cho vòng chọn tool | 💤 cân nhắc sau khi có số đo | — |

**Tiêu chí hoàn thành:** TTFT p95 ≤ 3.000 ms và Total p95 ≤ 8.000 ms trên **≥ 100 lượt** (bước 15 GĐ2), số liệu từ `latency_detail`, không chỉ từ ước tính.

> Bước 14 tách thành **14a** (làm đầu P1, không tốn API) và **14b** (để M2 vì credit hạn chế); **16a** (ASR M1) tách khỏi bước 16 để làm đầu P1; **19** (MCP thật) chuyển lên đầu P1. Tổng 20 bước đánh số 0–19 (+ 2b, 14a/b, 16a, HOTFIX N15).

---

## 4. Thứ tự và phụ thuộc

```
P0:  ✅ bước 0–10 (mã + test) · 15 GĐ1 ✅ (7 kịch bản × 2 cấu hình; đã chạy 3 lần: A, B, và lần chạy lại C sau các bản sửa)
P1 — thứ tự đã duyệt 2026-10-21:
     [1] đo lường công bằng (HR cả 2 cấu hình, CCR chặt, danh sách nghi lỗi dữ liệu BTC)         ✅
  →  [2] 3(b) prompt caching + đo vòng LLM trước token đầu                                        ✅
  →  [3] chạy lại 7 × 2 để xác nhận các bản sửa (trần 5.000 VND)                                   ✅
  →  [4] DATASET (sinh dữ liệu — CHỜ bạn trả lời 5 câu ở DATASET_PLAN § 9)                         ⏳
  →  [5] [ 19 MCP thật ◐ 3 server xong (có mcp-memory), còn A2A + tài liệu  ‖  12 slot schema + ProductRetriever ◐ mã xong, chờ đo LLM  ‖  14a ]   (16a ASR chạy sau khi có audio ở [4])
  →  [6] 13 (tra sẵn giá/KM/tồn kho vào Call Brief)
  →  [7] 15 GĐ2 (chạy trên kiến trúc MCP, bộ dataset mới)  →  16
M2:  14b
```

- **Bước 4, 5, 6, 7 cùng sửa `orchestrator.py`** (7 và 4/6 còn chạm gateway) → làm **tuần tự**, không song song (đã xong).
- Bước 8 (nối kênh) phải nằm trong P0 vì bước 3 đã cho runner đọc kênh thật — nếu chưa nối Fanpage↔Hotline, SAMPLE-04 và SC-GEN-06 tách thành hai khách (đã xong).
- Bước 9 phải có trước khi đo, vì bỏ nạp đáp án (bước 3) làm `full` thiếu bộ nhớ cho tới khi có bộ trích.
- **Bước 19 (MCP thật) đứng đầu P1, song song với 14a và 16a, và BẮT BUỘC xong trước 15-GĐ2**: M1 bắt buộc ≥ 2 MCP server (tiêu chí 3, 15% điểm) và số đo chính thức phải chạy trên kiến trúc MCP. Bước 19 thay lớp thực thi tool nên **xong trước 12 và 13** (cùng sửa `orchestrator.py`); 11 và 17 độc lập, có thể song song với 19.
- **16a (ASR M1)** không phụ thuộc bước nào khác (đo trên audio đã có) → làm đầu P1, không đợi bước 16.
- **Bước 12 được đưa lên sớm trong P1** (song song với 19 và 14a, sau khi có dataset): lỗi chọn sản phẩm là lỗi lớn nhất còn lại của TSR và phải sửa bằng luật chung theo thuộc tính, không vá riêng từng kịch bản. Bước 11, 14a, 17 chạm file khác nhau → có thể làm song song. Bước 13 cần 4, 12 và 19 xong. Bước 18 cần 17. Bước 12 và 19 cùng chạm phần thực thi tool/orchestrator → thống nhất giao diện `ToolGateway` trước khi viết.
- Bước 15 GĐ2 chạy sau 4–13, 14a, 16a **và 19**; sau đó 16.
- **P0 (bước 0–10) đã xong về mã nguồn và test offline**; chưa có số liệu hợp lệ nào cho tới khi chạy bước 15 GĐ1 (LLM thật).

---

## 5. Test theo bước (kiểm chứng offline)

Chạy: `python -m unittest discover -s tests -t .` (conda env `nlp_env`).

| File test | Bước |
|---|---|
| `test_runner.py`, `test_llm_client.py` (gồm 2b, N15) | 2, 2b, 3, N15 |
| `test_package_submission.py` | 0 |
| `test_pii_vault.py` | 7 (token PII, ca "giao cho người khác, số khác") |
| `test_cluster_4_8.py` | 4, 6, 7, 8 (tool ghi an toàn, guardrail trong luồng, tiền, ITN, định danh/kênh) |
| `test_orchestrator.py` | 2, 4, 5, 7 |
| `test_guardrail.py` | 6 |
| `test_normalizer.py` | 7 |
| `test_identity_brief.py` | 8 |
| `test_memory.py` | 9 |
| `test_extractor.py` | 10 (claims/questions) |
| `test_cluster_9_10.py` | 9, 10 (provenance, TTL, giao dịch, migration, xóa từng bảng, bộ trích 2 tầng, chốt cuộc gọi 3 thời điểm, runner/baseline, pipeline) |
| `test_environment.py` | 1 |

Trạng thái test hiện tại ghi ở [CHECKING.md § 11](../CHECKING.md) (cập nhật sau mỗi cụm; **sau cụm 9–10: toàn bộ xanh, 0 đỏ** — số test cụ thể ở § 11.14). Mỗi bước xong phải làm xanh test tương ứng mà không làm đỏ test khác.

---

## 6. Sản phẩm nộp M1 (đối chiếu đề bài, mục C.1/C.4/C.6/F)

> Số liệu **đếm thực tế ngày 2026-10-21** từ `BTC-Data-Vong1-TEAMS/test_set/{public_sample,generated_m1}` (7 kịch bản BTC + 15 kịch bản sinh bởi `generate_dataset.py`), `asr/audio`, `catalog`, `simulator`. **Chỉ đếm và báo cáo — chưa sinh dữ liệu mới.** Ngưỡng lấy từ đề bài (bảng C.1, C.3, C.4, C.6, mục F). Trạng thái: ✔ đạt · ◐ một phần · ✗ chưa đạt · ⏳ chưa kiểm.

### 6.1. Dataset (bảng C.1)

| Hạng mục | Ngưỡng M1 | Thực tế đếm được | TT |
|---|---|---|:-:|
| Số cuộc hội thoại (transcript) | ≥ 120 | **31 cuộc** (22 kịch bản; 74 lượt khách) — ~26% | ✗ |
| Trong đó có audio | ≥ 40 cuộc / ≥ 1 giờ | **4 file** (D01–D04, TTS), tổng **148,4 giây (~2,5 phút)** — 10% số cuộc, 4% thời lượng. Ngoài ra 2 cuộc có `customer_turns_asr` (text ASR giả lập, không phải audio) | ✗ |
| Khách đa phiên (≥ 2 cuộc cùng 1 khách) | ≥ 30 khách | **9 khách** (9 kịch bản có 2 cuộc); không có kịch bản 3 cuộc (M2 yêu cầu có khách ≥ 3 phiên) | ✗ |
| Khách có cả cuộc gọi + chat (đa kênh) | ≥ 10 khách | **3 khách** (SAMPLE-04 Fanpage→Hotline, SAMPLE-06 Hotline→Zalo, SC-GEN-06 Fanpage→Hotline) | ✗ |
| Ngành hàng · giọng vùng miền | 1 ngành · 2 miền | Catalog 3 nhóm (gia dụng 22 SKU, mẹ & bé 10, thời trang 8) ✔; CRM 3 miền (Bắc 15 / Trung 18 / Nam 17 khách) nhưng **audio TTS chỉ 1 giọng** nên chưa có dữ liệu giọng 2 miền | ◐ |
| Catalog sản phẩm + chính sách | ≥ 30 SKU | **40 SKU cha + 96 biến thể (136 SKU bán được)**; 11 file chính sách public | ✔ |
| Persona (≥ 3: dự người nhà · so giá · đã mua đổi size/khiếu nại) | ≥ 3 | `simulator/personas.json` có **12** persona; kịch bản dùng 15 nhãn persona, gồm đủ 3 loại bắt buộc (`khach_do_du_hoi_nguoi_nha` ×2, `khach_so_gia` ×3, `khach_da_mua_doi_size`/`khach_doi_size`/`khiếu nại`) | ✔ |

### 6.2. Bộ test (C.4)

| Hạng mục | Ngưỡng M1 | Thực tế đếm được | TT |
|---|---|---|:-:|
| Kịch bản đa phiên (2–3 cuộc cùng 1 khách) | ≥ 20 | **9** (22 kịch bản tổng; 13 kịch bản chỉ có 1 cuộc) | ✗ |
| Kịch bản khó thuộc 4 loại: đổi ý · mâu thuẫn với phiên trước · KM hết hạn · hỏi ngoài tài liệu | ≥ 5 | **5 nếu tính rộng**: đổi ý 1 (SC-GEN-09, chưa gắn `hard_case`), mâu thuẫn với phiên trước **0**, KM hết hạn 2 (SAMPLE-05, SC-GEN-01), hỏi ngoài tài liệu 2 (SAMPLE-07 chính sách bản cũ, SC-GEN-08 câu hỏi y tế). Có 11 kịch bản gắn `hard_case`, 6 ca còn lại thuộc loại khác (COD vượt hạn mức ×2, SĐT dùng chung, đổi size phụ thu, trade-in, SKU ngừng bán, ASR/teencode). **Thiếu hẳn loại "mâu thuẫn với phiên trước"** | ◐ |
| 5 chỉ số + script 1 lệnh + baseline | bắt buộc | Script 1 lệnh ✔ (bước 3); 5 chỉ số tính được ✔; **số liệu hợp lệ chưa có** (chờ bước 15) | ◐ |

### 6.3. Pipeline xử lý tiếng Việt / ASR (C.1)

| Hạng mục | Ngưỡng M1 | Thực tế | TT |
|---|---|---|:-:|
| WER/CER trên file chuẩn hóa số | ≥ 20 file | **4 file** — WER 42,6% / CER 32,5% (faster-whisper `base`, audio TTS, đo 2026-10-10) | ✗ |
| Entity accuracy riêng cho **số tiền** và **SĐT** | bắt buộc | Chỉ đo thực thể dạng số chung; **chưa tách số tiền / SĐT**; chưa xuất `asr/hypotheses.json` | ✗ |
| → Xử lý | — | **Tách thành bước 16a, làm ở đầu P1** (không đợi bước 16) | 🔜 |

### 6.4. Kiến trúc (C.3 — 15% điểm)

| Hạng mục | Ngưỡng M1 | Thực tế | TT |
|---|---|---|:-:|
| MCP server | ≥ 2 server, bắt buộc có `mcp-memory`; server còn lại `mcp-catalog` hoặc `mcp-crm` | **3 server thật** (`mcp-catalog`, `mcp-crm`, `mcp-memory`; CHECKING § 11.27, 11.32) | ✔ |

### 6.5. Chi phí và tác động kinh doanh (tiêu chí 6, 7)

| Hạng mục | Yêu cầu | Thực tế | TT |
|---|---|---|:-:|
| Ước tính chi phí mỗi cuộc gọi | có | Có cơ chế đo thật (`cost_tracker`, `llm_cost` trong trace, `config/pricing.yaml`). Số gần nhất: ~22–27 VND/lượt, ~68 VND/cuộc 3 lượt (gpt-4o-mini, trace 2026-10-11) — **đã cũ** vì prompt/luồng đã đổi; phải đo lại ở bước 15 | ◐ |
| Ước lượng tác động kinh doanh (vd giảm câu hỏi lặp → rút ngắn thời gian xử lý, tăng tỉ lệ chốt, giảm hoàn COD) | có | **Chưa có** — cần số RQR/Calls-to-Close hợp lệ từ bước 15 | ✗ |

> **Kế hoạch đạt ngưỡng dataset:** [DATASET_PLAN.md](DATASET_PLAN.md) (cơ cấu 86 kịch bản / 135 cuộc, audio 48 cuộc ~68 phút, ca khó 4 loại; ước tính chi phí; **chưa sinh dữ liệu**).

### 6.6. Hồ sơ nộp (mục F)

| Hạng mục | Yêu cầu | Thực tế | TT |
|---|---|---|:-:|
| Mã nguồn | Repo có README, hướng dẫn cài đặt/chạy, script khởi tạo dữ liệu | `submission/README.md` (2026-10-28): cài đặt, chạy demo, đánh giá một lệnh, cấu trúc mã; `scripts/package_submission.py` ✔ | ✔ |
| Dataset + mô tả ngắn | cách sinh, phân bố, hạn chế, xử lý thông tin cá nhân | `submission/DATASET.md` (cách sinh, phân bố, hạn chế, PII); dataset vẫn dưới ngưỡng C.1 | ◐ |
| Tài liệu kiến trúc | sơ đồ hệ thống + vòng lặp harness + lý do chọn MCP/A2A | `submission/ARCHITECTURE.md` + `docs/PIPELINE.md` (cập nhật 2026-10-28): sơ đồ, vòng lặp, MCP, vì sao không A2A | ✔ |
| Báo cáo đánh giá | bảng chỉ số, so baseline, trước/sau cải tiến, **≥ 10 ca hệ thống làm sai** | `submission/EVALUATION_REPORT.md`: số liệu run 4, so baseline, trước/sau, 14 ca sai, chi phí, tác động (giả định); thiếu LLM-judge và chấm tay | ◐ |
| Video demo 5–8 phút | bắt buộc có kịch bản 2 cuộc gọi (C.6) | `submission/DEMO_SCRIPT.md` (kịch bản); **video chưa quay** | ✗ |
| Website (giao diện) | khung hội thoại, Call Brief khi khách gọi lại, dòng thời gian bộ nhớ | `ui/index.html` + `scripts/run_demo.py` (bước 18): chat, Call Brief, dòng thời gian bộ nhớ; kiểm bằng trình duyệt, chưa kiểm với LLM thật | ✔ |
| Slide | tối đa 15 slide | `submission/slides.html` (15 slide, HTML; chưa có `.pptx`) | ◐ |

---

## 7. Chưa đưa vào kế hoạch

- Schema DB bản 2 (D10, D11, D12, D16) và nhóm P2 (vận hành doanh nghiệp: tổng đài thật, RBAC, retention, chống cuộc gọi rác NĐ 91/2020…): để sau khi bước 15 có số liệu hợp lệ.

---

## 8. Việc chủ dự án phải tự làm

1. **Khi đóng gói nộp bài, loại `.env` và `backup_2026-10-21/`** — chạy `python scripts/package_submission.py` (tự loại hai thứ này và kiểm tra gói không còn chuỗi giống API key; thoát mã 1 và xóa gói nếu phát hiện).
2. **Đối chiếu giá chính thức của `gpt-6-luna` trên OpenAI** với giá tạm trong `config/pricing.yaml` ($0.10 / $0.50 mỗi 1M token, nguồn OpenRouter 2026-10-20) trước khi làm bước 14b (id/quyền truy cập đã xác minh).
3. Khi BTC chốt định dạng `seed_history` trong kịch bản, báo để chỉnh runner (hiện nhận `list[dict]` theo trường `EpisodeRecord` + `facts`).

---

## 9. Mục tiêu BTC cần đạt (đo ở bước 15)

| Chỉ số | Ngưỡng |
|---|---|
| Repeat-Question Rate | giảm ≥ 40% tương đối so với baseline |
| Task Success Rate | ≥ 70% |
| Hallucination Rate giá & KM | ≤ 5% |
| Context Carryover Rate | cao hơn baseline |
| Call Brief / TTFT p95 / Total p95 | ≤ 5 s / ≤ 3 s / ≤ 8 s (≥ 100 lượt, bỏ 3 lượt warm-up) |
| Vi phạm guardrail | 0 |
