# CHECKING.md — Báo cáo kiểm tra toàn bộ hệ thống Harness Agent Call Center

> **Đề tài**: Sudo Code 2026 — Vòng 1: *Harness Agent hỗ trợ Call Center E-commerce (Telesale)* — duy trì ngữ cảnh liên tục qua nhiều phiên & nhiều kênh, tự đánh giá và cải tiến theo thời gian.
> **Ngày kiểm tra**: 2026-10-14 · **Phạm vi**: toàn bộ thư mục `Code/` (mã nguồn, dữ liệu BTC, trace `runs/`, DB `data/`), đối chiếu với đề bài PDF, `DIEU-CHINH-DE.md`, `GIAI-DAP-MENTOR.md`.
> **Vai trò kiểm tra**: Senior Tester · Chief Architect · Senior Developer · Senior AI Engineer.
> **Nguyên tắc**: chỉ ghi những gì **đo/đọc/chạy được**; mỗi kết luận có bằng chứng (file:dòng, lệnh, số liệu). Không thiên về khen hay chê.
> **Cập nhật 2026-10-27:** các mục 0–10 bên dưới là kết quả kiểm tra ngày 2026-10-14 (đã cũ). **Tình trạng hiện tại và việc chưa làm: xem [§ 12 — Tổng hợp tiến độ](#12-tổng-hợp-tiến-độ-2026-10-27).**

---

## Trạng thái hiện tại (cập nhật 2026-11-04, sau § 11.108)

> **Đọc phần này trước.** §§ 0–10 là **ảnh chụp kiểm tra ban đầu (2026-10-11 → 10-21)**; nhiều kết luận trong đó (hệ thống thua baseline, 1/3 ngưỡng, latency giả, MCP/A2A hình thức, 864 test…) **đã lỗi thời** và được giữ để đối chiếu. Trạng thái hiện hành: **§ 12** (tổng hợp) và nhật ký **§ 11** (chi tiết từng việc, đánh số theo thời gian; § 11.43+ nằm SAU § 12 trong file).

| Hạng mục | Hiện tại (2026-11-04) |
|---|---|
| Mã | Pipeline đầu-cuối + 3 MCP server thật, API FastAPI, giao diện `ui/`, order gate, bộ đọc lời khách bằng LLM, `price_basket` (giá báo == giá đơn). **977 test offline, 0 đỏ** (`runs/_unittest_monitoring.txt`; chạy trong conda `nlp_env`, `MCP_TRANSPORT=inproc MEMORY_TRANSPORT=local`). Thêm 2026-11-04: bộ kịch bản `team_eval` gộp (§ 11.107), sửa ITN "5 triệu rưỡi", giám sát Prometheus + Grafana (§ 11.108) |
| Số đo mới nhất (bước 15 GĐ2, lần 6, `runs/gd2_run6/`, 22 kịch bản × 2 cấu hình × 3 seed, LLM thật) | TSR **66,7** (ngưỡng ≥ 70 → **chưa đạt**; baseline 68,2 → **chưa hơn baseline**) · RQR **0,0** (đạt) · HR giá/KM **0,0** (đạt) · CCR 53,6 · TTFT p95 **7,7 s** (ngưỡng ≤ 3 s → **chưa đạt**) · guardrail 0 vi phạm |
| Chi phí LLM đã tiêu | dataset 2.076,3 / 10.000 VND (sổ cái trong mã); GĐ2 mỗi lần 10,7–13,6 nghìn VND (lần 6: 13.387,5); chạy thử UI/ui_replay: vài trăm VND mỗi lần |
| Dữ liệu | từ 2026-11-04 bộ đo là 49 kịch bản (7 BTC + 42 `team_eval`, § 11.107; lần 1–6 đo trên bộ cũ 22 kịch bản, đáp án GEN-01/02/05 đã sửa — lỗi do nhóm, không phải BTC); dataset mới mới có lô đại diện, còn 44 khung chưa sinh; audio ≥ 40 cuộc chưa có |
| **Chặn đo mới** | **Khóa `OPENAI_API_KEY` trong `.env` đã hết hạn (HTTP 401 `expired_secret_key`, kiểm 2026-11-04)** nên chưa chạy được lần đo trên bộ 49 kịch bản, chưa đo TTFT mới, chưa sinh UI bằng OpenUI. Cần chủ dự án tạo khóa mới |
| Việc chặn nộp M1 | TSR chưa đạt, TTFT chưa đạt, `submission/` còn số của lần 4, video + slide `.pptx` chưa có, dataset/audio thiếu, duyệt tay 15% chưa làm |
| Giám sát / UI | Grafana: **xong, đã chạy thật** (`monitoring/`, dashboard 19 panel). OpenUI (W&B): **chưa** — không tải được từ github.com/ghcr.io ở thời điểm kiểm và chưa có LLM; đề bài đã viết sẵn ở `ui/OPENUI_PROMPT.md` |
| Thư gửi BTC | đã soạn (`docs/BAO_CAO_LOI_GUI_BTC.md`) và **chủ dự án đã gửi** (2026-11-04); chờ phản hồi mục 2–4, 8 |
| Điều cần quyết | tiêu chí chấm SC-GEN-02; trần chi phí cho lần chạy xác nhận (≈ 13.400 VND); có sinh tiếp dataset không; 5 đề nghị gửi BTC (§ 12.2) |

---

## 0. Phương pháp kiểm tra & tóm tắt kết luận (ẢNH CHỤP 2026-10-11 → 10-21 — đã lỗi thời, xem "Trạng thái hiện tại" ở trên)

### 0.1. Đã làm gì

| # | Hoạt động | Cách làm | Ghi chú |
|---|---|---|---|
| 1 | Đọc toàn bộ mã nguồn | 34 file Python trong `src/`, 7 entrypoint, `PIPELINE.md`, `README.md` gốc | đối chiếu mô tả ↔ code thật |
| 2 | Đọc yêu cầu BTC | đề bài PDF (Phụ lục A/B), `DIEU-CHINH-DE.md`, `GIAI-DAP-MENTOR.md`, `schemas/`, `reference_eval.py` | lấy công thức & ngưỡng chính thức |
| 3 | Chấm lại trace LLM có sẵn | `reference_eval.py` trên `runs/full.jsonl` + `runs/baseline.jsonl` (chạy 2026-10-11) | tái lập **khớp 100%** `runs/report.json` |
| 4 | Chạy đánh giá offline (không LLM) | `ScenarioRunner` với `OPENAI_API_KEY=""` → nhánh rule-based, trên 7 kịch bản public + 15 kịch bản `generated_m1` | không tốn API |
| 5 | Kiểm thử đơn vị thủ công | Normalizer (13 ca), Guardrail (9 ca), Identity (4 ca), TTL/supersede, rò bộ nhớ baseline, latency phần không-LLM | script `audit_offline.py` (scratchpad) |
| 6 | Đo RAG | Recall@3/@5 + abstain trên `rag/qa_labeled.json` (60 câu) bằng backend TF-IDF thật của hệ thống, chấm bằng `reference_eval.py --rag` | |
| 7 | Phân tích chi phí & hành vi LLM | đọc `llm_cost`, `tool_calls` trong 3 file trace + SQLite `data/harness_memory.db` (read-only) | |

**Không làm**: không gọi OpenAI API (tránh tốn chi phí của chủ dự án) → **độ trễ LLM thật chưa được đo**; không sửa mã nguồn; `runs/` và `data/` được kiểm tra mtime trước/sau — **không thay đổi**.

### 0.2. Kết luận nhanh

| Hạng mục | Kết luận | Mức tin cậy |
|---|---|---|
| Pipeline runtime (normalize → identity → brief → LLM + tool → guardrail → trace) | **Chạy được đầu-cuối**, có fallback ở mọi tầng | Cao |
| Session Continuity (nhận diện khách gọi lại + Call Brief + câu mở đầu tiếp nối) | **Có**, nhưng Call Brief dựa nhiều vào template cứng ("chị Hoa", "anh nhà") | Cao |
| Số liệu đánh giá trong `PIPELINE.md` cũ | **Không tái lập được** (trace 2026-10-10 đã bị ghi đè); lần chạy mới nhất (2026-10-11) cho **hệ thống thua baseline** ở TSR và HR | Cao |
| Latency trong trace/báo cáo | **Không phải số đo thật** — `random.randint(350, 750)` / hằng số 380ms / `call_brief_ms = 115` | Cao (đã chứng minh) |
| Baseline "không bộ nhớ" | **Không thật sự stateless** — profile từ call_1 vẫn mang sang call_2 | Cao (đã chứng minh) |
| Cấu hình full khi chấm | **Bơm đáp án** `facts_established` của kịch bản vào bộ nhớ sau mỗi call | Cao |
| Đạt ngưỡng BTC (RQR giảm ≥40%, TSR ≥70%, HR giá ≤5%) | Lần chạy mới nhất: **1/3 ngưỡng** (chỉ TSR 71.4%) | Cao |
| MCP / A2A / Vòng cải tiến | Phần lớn **mang tính hình thức** hoặc **chưa được gọi** (dead code) | Cao |
| Database `data/harness_memory.db` (SQLite) | **Chạy được và toàn vẹn về kỹ thuật** (`integrity_check = ok`, WAL, truy vấn có tham số), nhưng **chưa chuẩn về mô hình dữ liệu**: 134 dòng "active" cho 42 fact thật, cùng 1 khách lưu dưới 3 mã, mỗi khách chỉ có 1 ô sản phẩm/đơn hàng nên thông tin bị ghi đè qua lại, xóa dữ liệu không hết, 35% dữ liệu chỉ nằm trong file `-wal` (xem § 10) | Cao (đã truy vấn trực tiếp) |
| Sẵn sàng cho doanh nghiệp telesale thật | **Chưa** — mức prototype/PoC | Cao |

---

## 1. Sơ đồ kiến trúc hệ thống (có màu & chuyển động)

### 1.1. Sơ đồ tổng thể (SVG động — mở được trong mọi trình xem Markdown/trình duyệt)

![Kiến trúc thực tế có chuyển động](docs/architecture_animated.svg)

> File: [docs/architecture_animated.svg](docs/architecture_animated.svg). Mỗi luồng một màu, nét đứt chạy theo hướng dữ liệu, chấm tròn di chuyển mô phỏng request. Ký hiệu trạng thái: **✔** chạy thật đúng mục đích · **◐** có nhưng hạn chế/hình thức · **✖** chưa nối hoặc sai. Đường đỏ chấm-chấm = **rò đáp án** từ bộ test vào bộ nhớ (chỉ khi chạy eval).

### 1.2. Sơ đồ theo từng luồng module (Mermaid — màu + cạnh động)

> Cạnh động dùng cú pháp `e1@{ animate: true }` của **Mermaid ≥ 11.6** (GitHub, Mermaid Live, VS Code + extension Mermaid mới). Trình xem Mermaid cũ hơn có thể không vẽ được → dùng sơ đồ SVG ở 1.1.

#### Luồng ① Tiếp nhận → Chuẩn hóa → Định danh → Call Brief

```mermaid
flowchart LR
    U["👤 Khách<br/>Hotline/Zalo/Fanpage/Web"] e1@--> N["RequestNormalizer<br/>ASR-fix · teencode · ITN · PII*"]
    N e2@--> I["IdentityResolver"]
    I e3@-->|crm.get_customer| CRM[("BTC mock_tools<br/>crm_seed.json (50 khách)")]
    CRM e4@--> I
    I e5@-->|"found"| CB["CallBriefBuilder"]
    I e6@-->|"SĐT chung"| AMB["Brief AMBIGUOUS<br/>(customer_id dùng chung!)"]
    I e7@-->|"không có trong CRM"| ANON["SHA-256 + salt<br/>→ CUST-ANON-xxxx"]
    ANON e8@--> CB
    MEM[("Profile + Episodic")] e9@--> CB
    CB e10@--> OUT["must_not_ask · must_carry_over<br/>câu mở đầu tiếp nối (template)"]
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    classDef input fill:#eff6ff,stroke:#2563eb,color:#0f172a
    classDef ident fill:#f5f3ff,stroke:#7c3aed,color:#0f172a
    classDef tool fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef mem fill:#f0fdfa,stroke:#0d9488,color:#0f172a
    classDef warn fill:#fef2f2,stroke:#dc2626,color:#7f1d1d
    class U,N input
    class I,CB,OUT,ANON ident
    class CRM tool
    class MEM mem
    class AMB warn
    linkStyle 0,1 stroke:#2563eb,stroke-width:2px
    linkStyle 2,3 stroke:#16a34a,stroke-width:2px
    linkStyle 4,6,7,9 stroke:#7c3aed,stroke-width:2px
    linkStyle 5 stroke:#dc2626,stroke-width:2px
    linkStyle 8 stroke:#0d9488,stroke-width:2px
```

#### Luồng ② Điều phối LLM + Tool + Phân giải SKU 4 tầng

```mermaid
flowchart TB
    T["Turn + Call Brief"] e1@--> P["Dựng prompt<br/>system prompt ~2.2k ký tự + brief + 20 msg lịch sử"]
    P e2@--> L{"LLM gpt-4o-mini<br/>function-calling<br/>≤ 6 vòng"}
    L e3@-->|tool_call| X["_tool_executor<br/>tiêm on = ngày gọi"]
    X e4@--> G["MCPToolGateway.execute_tool<br/>→ mock_tools.py"]
    G e5@-->|"unknown_sku"| R["Tầng 2: khớp size/màu NFKD<br/>Tầng 3: difflib ≥ 0.8<br/>Tầng 4: trả variant thật"]
    R e6@--> G
    G e7@-->|kết quả| L
    L e8@-->|"không gọi tool vòng đầu"| NU["Nudge 1 lần"]
    NU e9@--> L
    L e10@-->|text cuối| OUT["proposal_text + tool_calls"]
    L e11@-.->|"lỗi / hết key / > 6 vòng"| FB["Fallback rule-based<br/>(mặc định SKU-AP-Y)"]
    FB e12@-.-> OUT
    E1["Tầng 1: enum variant_sku thật<br/>(khi đã biết product_advised)"] e13@-.-> L
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    e11@{ animate: true }
    e12@{ animate: true }
    e13@{ animate: true }
    classDef llm fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef tool fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef warn fill:#fef2f2,stroke:#dc2626,color:#7f1d1d
    class T,P,L,NU,OUT,E1 llm
    class X,G,R tool
    class FB warn
    linkStyle 0,1,7,8,9,12 stroke:#ea580c,stroke-width:2px
    linkStyle 2,3,4,5,6 stroke:#16a34a,stroke-width:2px
    linkStyle 10,11 stroke:#dc2626,stroke-width:2px
```

#### Luồng ③ Bộ nhớ: đọc / ghi / bền vững

```mermaid
flowchart LR
    O["Orchestrator<br/>(sau mỗi lượt)"] e1@-->|"set_working(session = customer+ngày)"| W[("Working")]
    O e2@-->|"_persist_tool_grounded_facts<br/>order.create / order.update / pricing.get_quote"| PR[("Profile<br/>supersede; TTL lưu nhưng KHÔNG áp")]
    O e3@-->|"room_area_m2 / has_children<br/>(regex normalizer)"| PR
    RUN["ScenarioRunner<br/>(chỉ config full)"] e4@-->|"seed facts_established = ĐÁP ÁN"| PR
    RUN e5@-->|"add_episode"| EP[("Episodic")]
    MAIN["main.py (demo)"] e6@-->|"seed cứng khách Hoa ×3 id<br/>mỗi lần chạy thêm 1 bản"| EP
    W e7@--> DB[("SQLite<br/>data/harness_memory.db")]
    PR e8@--> DB
    EP e9@--> DB
    KB[("Semantic KB<br/>99 chunk policy · TF-IDF")] e10@-->|"search_policy (lọc ngày + public)"| O
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    classDef mem fill:#f0fdfa,stroke:#0d9488,color:#0f172a
    classDef llm fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef warn fill:#fef2f2,stroke:#dc2626,color:#7f1d1d
    class W,PR,EP,DB,KB mem
    class O llm
    class RUN,MAIN warn
    linkStyle 0,1,2,6,7,8,9 stroke:#0d9488,stroke-width:2px
    linkStyle 3,4,5 stroke:#dc2626,stroke-width:2px
```

> ⚠️ **Không có** bộ tóm tắt episodic tự động ở cuối cuộc gọi trong luồng production (`main.py`/`ui_app.py`): episode chỉ được ghi bởi runner (từ kịch bản) hoặc `main.py` (seed cứng).

#### Luồng ④ Guardrail → Phản hồi → Trace

```mermaid
flowchart LR
    PRO["proposal_text<br/>(LLM hoặc rule)"] e1@--> GR{"GuardrailAndFallback"}
    GR e2@-->|"'đã lên đơn' nhưng không có order.create"| B1["Thay câu: 'em xin phép thao tác…'"]
    GR e3@-->|"chứa 'giá nhập/nội bộ/nhà cung cấp'"| B2["Thay câu bảo mật"]
    GR e4@-->|"so giá với tool<br/>(CHỈ ở nhánh rule-based)"| B3["Chặn lệch giá"]
    GR e5@-->|"OK"| M["Mask số 9–14 chữ số"]
    M e6@--> RESP["Câu trả lời cho khách"]
    B1 e7@--> RESP
    B2 e8@--> RESP
    RESP e9@--> TR["TurnTracer JSONL<br/>claims = từ KẾT QUẢ TOOL<br/>questions = regex nhãn slot<br/>latency = GIẢ"]
    TR e10@--> EV["reference_eval.py"]
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    classDef guard fill:#fef2f2,stroke:#dc2626,color:#0f172a
    classDef trace fill:#f8fafc,stroke:#475569,color:#0f172a
    class PRO,GR,B1,B2,B3,M,RESP guard
    class TR,EV trace
    linkStyle 0,1,2,3,4,5,6,7 stroke:#dc2626,stroke-width:2px
    linkStyle 8,9 stroke:#475569,stroke-width:2px
```

### 1.3. Bảng trạng thái module (đối chiếu mô tả ↔ thực tế)

| Module | File | Mô tả trong PIPELINE.md cũ | Thực tế kiểm tra |
|---|---|---|---|
| Normalizer | `src/channels/normalizer.py` | ASR repair, teencode, ITN, mask PII trước khi đưa ra ngoài | ASR-fix 9 cụm; teencode dict có **khóa `"k"` trùng** (`"không"` bị ghi đè thành `"nghìn"`, dòng 34 & 38); `"sai"→"size"`, `"a"→"anh"`; ITN chỉ 6 số tiền viết cứng + regex `Ntr/Nk` (ra `249000`, không phải `249.000đ`); **không có ITN SĐT/ngày giờ**; `pii_masked_text` tính ra nhưng **không được dùng** — bản chưa mask được gửi lên OpenAI và ghi vào trace |
| Identity | `src/identity/resolver.py`, `identity_map.py` | Nhận diện SĐT/Zalo/FB, ca mơ hồ | Đúng: Zalo/FB → tìm ra `C001`; SĐT chung C034/C035 → `ambiguous`. Hạn chế: mọi ca mơ hồ dùng chung `customer_id="AMBIGUOUS"`; không có bước xác minh tên để thoát trạng thái mơ hồ; `link_identities` chưa được gọi |
| Call Brief | `src/harness/call_brief.py` | Tự nạp, must_not_ask, opening tiếp nối | Chạy; nhưng **mặc định "Hoa"/"chị"** khi thiếu tên (dòng 78–79) — số lạ cũng được chào "chị Hoa"; câu "anh nhà" viết cứng (dòng 115); không kiểm tra tồn kho/KM mới lúc nhận diện; không đo latency; không có `precomputed_parts` |
| Memory 4 tầng | `src/memory/*` | Working/Episodic/Profile/Semantic, supersede, TTL | Working ✔; Profile supersede ✔ nhưng **TTL không được áp dụng** khi đọc; lịch sử superseded bị mất trong store in-memory (chỉ SQLite giữ); Episodic **không có writer tự động**; Semantic TF-IDF ✔ (99 chunk, lọc ngày + public) |
| MCP Gateway | `src/tools/mcp_gateway.py` | Auth, phân quyền, audit tập trung | Là **class Python định tuyến** sang `mock_tools.py` của BTC; **không có auth/phân quyền**, không timeout/retry, audit log chỉ in-memory; **không phải MCP server** (không dùng giao thức MCP, không có `mcp-memory`) |
| A2A Agents | `src/agents/specialists.py` | 4 agent chuyên biệt | `SalesAdvisor` = câu template ("HEPA H13…"), kết quả bị bỏ qua ở chế độ LLM; `PolicyCompliance` chỉ chạy ở fallback; `ContextAgent`, `QAEvaluatorAgent` **không được gọi ở đâu** |
| Guardrail | `src/harness/guardrail.py` | Chặn bịa giá, lộ nội bộ, mask PII, kiểm handoff 9 trường | Chặn "nói đã lên đơn mà không gọi tool" ✔; chặn lệch giá **bị tắt ở chế độ LLM** (`orchestrator.py:249-255` truyền `None`); keyword nội bộ có false-positive/false-negative; kiểm handoff brief **không bao giờ kích hoạt** (không có `action_type="handoff"`); không chặn "tự nhận là người thật" |
| Tracer | `src/tracing/tracer.py` | Trace chuẩn 100% schema BTC | Đủ field *required*; **latency giả**; thiếu `memory_writes`, `call_brief_latency_ms` (đặt sai chỗ: `latency.call_brief_ms`), `customer_input_mode` |
| Eval Runner | `src/eval/runner.py`, `run_eval.py` | 1 lệnh, 2 cấu hình | 1 lệnh ✔; **không có CLI** `--scenarios/--config/--out` mà BTC yêu cầu; chỉ chạy `public_sample`; kênh luôn HOTLINE; baseline rò profile; full bơm đáp án |
| Evaluator / Human gate / Improvement / Simulator | `src/eval/*.py` | Đầy đủ vòng cải tiến | **Dead code** — chỉ được import trong `__init__.py`, không entrypoint nào gọi |
| ASR | `src/channels/offline_asr.py`, `eval_asr.py` | faster-whisper local | Chạy được (CPU fallback); 4 file audio TTS; WER 42.6%; không xuất `hypotheses.json` theo định dạng BTC |
| UI | `ui_app.py` | 7 khu vực | Có 6 tab (chat+audio, brief, timeline, tool log, đơn/lịch, eval) ✔; 1 pipeline dùng chung, không đa phiên |

---

## 2. Quy trình đánh giá hệ thống

### 2.1. Quy trình hiện tại (thực tế trong code)

```mermaid
flowchart TB
    A["python run_eval.py<br/>(không nhận tham số)"] e1@--> B["ScenarioRunner.load_scenarios<br/>test_set/public_sample (7 kịch bản, cứng)"]
    B e2@--> C1["Config FULL"]
    B e3@--> C2["Config BASELINE_NO_MEMORY"]
    C1 e4@--> S["Mỗi kịch bản: MemoryService mới (không SQLite)<br/>call_1 → call_2 (→ call_3)<br/>mỗi lượt: normalize → identity → brief → orchestrator(LLM)"]
    C2 e5@--> S
    S e6@-->|"FULL: sau mỗi call seed facts_established + episode"| S
    S e7@--> T1["runs/full.jsonl"]
    S e8@--> T2["runs/baseline.jsonl"]
    T1 e9@--> R["BTC reference_eval.py<br/>--scenarios --trace --baseline --out"]
    T2 e10@--> R
    R e11@--> REP["runs/report.json + bảng A.6 in ra stdout"]
    REP e12@--> UI["Tab Evaluation (Streamlit)"]
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    e11@{ animate: true }
    e12@{ animate: true }
    classDef run fill:#fff1f2,stroke:#e11d48,color:#0f172a
    classDef cfg fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef out fill:#f8fafc,stroke:#475569,color:#0f172a
    class A,B,S run
    class C1,C2 cfg
    class T1,T2,R,REP,UI out
    linkStyle 0,1,2,3,4,5 stroke:#e11d48,stroke-width:2px
    linkStyle 6,7,8,9,10,11 stroke:#475569,stroke-width:2px
```

### 2.2. Quy trình chấm chính thức của BTC (ngày chấm) và độ khớp

| Bước BTC | Yêu cầu | Hệ thống hiện tại |
|---|---|---|
| 1. Chạy hệ thống | `python run_eval.py --scenarios <dir> --config full\|baseline_no_memory --out trace.jsonl` | ❌ `run_eval.py` không có argparse; đường dẫn cứng `public_sample` (`run_eval.py:33`). BTC sẽ **không chạy được bộ ẩn 41 kịch bản** theo đúng lệnh |
| 2. Chấm | `reference_eval.py --scenarios --trace --baseline --asr` | ✔ định dạng trace đọc được; ❌ không có `asr/hypotheses.json` |
| 3. Kiểm extractor | BTC chấm tay 20 lượt xem `questions[]/claims[]` có bỏ sót | ⚠️ rủi ro cao: claims chỉ lấy từ kết quả tool, questions chỉ giữ câu có từ khóa slot (39 lượt chỉ ra **1** câu hỏi) |
| 4. Latency | đo tại ranh giới harness, ≥100 lượt, bỏ 3 lượt warm-up | ❌ giá trị giả; 39 lượt (< 100) |
| 5. Baseline | cùng model/tham số, **chỉ khác** có nạp bộ nhớ phiên trước | ❌ baseline vẫn mang profile sang call sau; full được bơm đáp án |

### 2.3. Quy trình đánh giá đề xuất (đúng chuẩn, lặp lại được)

```mermaid
flowchart LR
    D["Bộ test cố định<br/>public 7 + generated 15 + tự sinh ≥ 20"] e1@--> RUN["run_eval.py --scenarios --config --out --seed"]
    RUN e2@--> F["FULL: chỉ dùng bộ nhớ do hệ thống TỰ ghi"]
    RUN e3@--> BL["BASELINE: memory reset mỗi call<br/>(cùng model, temperature=0)"]
    F e4@--> TR["Trace + latency đo thật (perf_counter, TTFT streaming)<br/>+ memory_writes + call_brief_latency_ms"]
    BL e5@--> TR
    TR e6@--> REF["reference_eval.py (+ --asr, --rag)"]
    REF e7@--> X3["Lặp 3 seed → mean ± std"]
    X3 e8@--> ERR["Phân tích ≥ 10 ca sai"]
    ERR e9@--> IMP["Improvement (KB gap / exemplar)"]
    IMP e10@--> HG{"Human gate<br/>không tụt chỉ số?"}
    HG e11@-->|duyệt| RUN
    HG e12@-.->|từ chối| RB["Rollback"]
    e1@{ animate: true }
    e2@{ animate: true }
    e3@{ animate: true }
    e4@{ animate: true }
    e5@{ animate: true }
    e6@{ animate: true }
    e7@{ animate: true }
    e8@{ animate: true }
    e9@{ animate: true }
    e10@{ animate: true }
    e11@{ animate: true }
    e12@{ animate: true }
    classDef ok fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef loop fill:#fdf2f8,stroke:#db2777,color:#0f172a
    class D,RUN,F,BL,TR,REF,X3 ok
    class ERR,IMP,HG,RB loop
    linkStyle 0,1,2,3,4,5,6 stroke:#16a34a,stroke-width:2px
    linkStyle 7,8,9,10,11 stroke:#db2777,stroke-width:2px
```

---

## 3. Lý thuyết các metric của Ban tổ chức Sudo Code

Nguồn: đề bài PDF (mục C.4, Phụ lục A), `DIEU-CHINH-DE.md`, `GIAI-DAP-MENTOR.md`, cài đặt trong `BTC-Data-Vong1-TEAMS/eval/reference_eval.py`.

### 3.1. Năm chỉ số bắt buộc M1

| Chỉ số | Công thức | Cách script BTC tính | Ngưỡng | Ý nghĩa nghiệp vụ |
|---|---|---|---|---|
| **Repeat-Question Rate (RQR)** ★ KPI số 1 | `số câu hỏi thừa / tổng câu hỏi agent × 100%` | Chỉ xét call có `must_not_ask`. Thừa = câu **mở** về slot trong `must_not_ask`, **hoặc** câu **xác nhận lần ≥2** cùng slot trong cùng call. Mức giảm so baseline = `(RQR_b − RQR_s)/RQR_b` | Giảm **≥ 40% tương đối** so baseline | Đo nỗi đau Case 1: khách bị hỏi lại thông tin đã cung cấp |
| **Context Carryover Rate (CCR)** | `số fact dùng đúng / số fact bắt buộc mang sang × 100%` | Mỗi call có `must_carry_over`: fact được tính nếu nằm trong `facts_used` của trace **hoặc là tên tham số** của một tool call (`reference_eval.py` dòng `seen.update(k for k in tc["args"].keys())`) | Càng cao càng tốt (không có ngưỡng) | Đối trọng của RQR: agent im lặng có RQR = 0 nhưng vô dụng |
| **Task Success Rate (TSR)** | `số kịch bản đạt / tổng kịch bản × 100%` | Nhị phân bằng assertion theo `success_if`: `tool_called` + `args_match`, `also_ordered`, `total_match_vnd`, `brief_must_contain`, `must_say_any`, `agent_must_say`, `must_not_call_tools`, `forbidden_claims`, `trace_must_not_match`, `max_agent_questions`. Kịch bản đạt khi **mọi** call có `success_if` đều đạt. Báo thêm **TSR riêng ca khó** | **≥ 70%** | Tỷ lệ chốt đơn/hoàn thành nghiệp vụ; `chuyen_may` tính đạt khi gọi `handoff.transfer` với brief đủ trường |
| **Hallucination Rate (HR)** | `số claim sai / tổng claim kiểm chứng được × 100%` | Đối chiếu `claims[].field` với `ground_truth_facts` của call; tách riêng HR giá & KM (field bắt đầu `price`/`promo`/`list_price`) | HR giá & KM **≤ 5%** | Sai giá/KM gây thiệt hại tiền thật và mất uy tín |
| **WER / CER + Entity Accuracy** | `WER = (S+D+I)/N`; CER tương tự trên ký tự; `Entity Acc = số thực thể đúng hoàn toàn / tổng` | Chuẩn hóa: lowercase, NFC, bỏ dấu câu, gộp khoảng trắng; entity so exact-match sau ITN; đọc `asr/hypotheses.json` | Báo cáo (không ngưỡng); ≥ 20 file của team + 12 hội thoại BTC | Một chữ số sai trong SĐT/số tiền làm hỏng đơn → Entity Accuracy quan trọng hơn WER |

### 3.2. Chỉ số hiệu năng (bảng điều chỉnh C.2)

| Chỉ tiêu | M1 | M2 | Cách đo thống nhất |
|---|---|---|---|
| Thời gian nạp Call Brief | ≤ 5 s | ≤ 3 s | Từ sự kiện nhận diện SĐT tới khi CallBrief sẵn sàng (gồm DB + LLM + kiểm tra tính mới); ghi `call_brief_latency_ms` ở turn 1 call_2/call_3 |
| TTFT p95 | ≤ 3 s | — | Từ lúc gửi lượt chat đến token đầu tiên |
| Total latency p95 | ≤ 8 s | — | Đến khi sinh xong toàn bộ câu trả lời |
| TTFA p95 | — | ≤ 2.5 s | Voice: từ lúc dừng nói đến audio đầu tiên |
| Phiên đồng thời | 1 | ≥ 2 | |
| Điều kiện | ≥ 100 lượt (bộ ẩn ~170), bỏ 3 lượt warm-up, đo tại ranh giới backend, cùng phần cứng/API/model cho baseline và hệ thống | | |

### 3.3. Chỉ số bổ sung / M2

| Chỉ số | Định nghĩa |
|---|---|
| `guardrail_violations` | Đếm trên toàn trace: PII (CCCD 12 số, STK 10–14 số; SĐT 10 số bắt đầu 0 được phép) trong `agent_text`/`memory_writes`, chuyển máy thừa, claim `is_human=true`, khớp mẫu cấm `trace_must_not_match` (lộ giá nhập…) — mỗi vi phạm trừ trực tiếp tiêu chí 2 và 8 |
| Calls-to-Close | Số cuộc gọi trung bình đến khi `order.create` (chỉ tính kịch bản có chốt) |
| Số lượt TB / cuộc | Trung bình số lượt agent mỗi call |
| Tool-Call Accuracy | Tỷ lệ tool call đúng tên + tham số (M2) |
| Recall@k (k=3, 5) | Có ít nhất một chunk đúng trong top-k; thêm full-recall multi-hop, abstain rate cho câu `unanswerable`/`restricted`, false-abstain rate |
| LLM-as-a-judge | 12 tiêu chí PASS/FAIL (`llm_judge_rubric.json`), đồng thuận với người ≥ 20 mẫu (Cohen's kappa) |
| Customer simulator | 12 persona, 3 seed, độ lệch TSR giữa 3 seed ≤ 10 điểm |
| Chi phí ước tính / cuộc gọi | Tiêu chí 7 |

---

## 4. Ý nghĩa các scripts trong hệ thống

| Script | Chức năng | Đầu vào → Đầu ra | Tác dụng phụ cần biết |
|---|---|---|---|
| `main.py` | Demo 1 request (khách Hoa gọi lại call_2, ngày 2026-10-17) qua toàn pipeline, in từng bước | hard-code khách C001 → stdout + 1 dòng trace | **Ghi nối vào `runs/full.jsonl`** (file trace chấm điểm) và **seed thêm 1 episode/lần chạy** vào SQLite cho 3 id (`C001`, SĐT, `CUST-001`) — DB hiện có 4 bản trùng/khách → Call Brief báo "4 cuộc gọi trước" (sai) |
| `pipeline.py` | Lớp `CallCenterHarnessPipeline` gom toàn bộ module cho `main.py` và `ui_app.py` | raw text + contact → answer, trace | latency ghi cứng **380ms** (`pipeline.py:90`), `run_id` cố định |
| `run_eval.py` | Đánh giá 1 lệnh: chạy 7 kịch bản × 2 cấu hình bằng LLM thật rồi gọi `reference_eval.py` | → `runs/full.jsonl`, `runs/baseline.jsonl`, `runs/report.json` | ~78 lượt LLM thật (tốn API, kết quả dao động); không nhận tham số |
| `ui_app.py` | Dashboard Streamlit: chat (vai khách/agent), upload audio→ASR, Call Brief, Memory Timeline, Tool log, Đơn/Lịch gọi lại, nút chạy eval | tương tác → `runs/ui_session.jsonl`, SQLite | mọi phiên UI dùng chung 1 pipeline; `call_name` luôn `call_1` |
| `eval_asr.py` | Transcribe audio `asr/audio/D0x` bằng faster-whisper, tính WER/CER/entity (số) so `ground_truth.json` | audio → `runs/asr_report.json` | Không xuất `hypotheses.json` cho `reference_eval --asr` |
| `scripts/generate_test_audio.py` | Sinh audio thử D01–D04 bằng edge-tts/gTTS (cần mạng) | ground truth → `asr/audio/*.mp3` | Audio TTS, không phải giọng thật |
| `generate_dataset.py` | Sinh 15 kịch bản `SC-GEN-01..15` từ catalog/promo/CRM thật (8 ca khó) | → `test_set/generated_m1/` | Chưa được `run_eval.py` dùng |
| `BTC-Data-Vong1-TEAMS/eval/reference_eval.py` | Script chấm chính thức của BTC | scenarios + traces → bảng A.6 + JSON | Không sửa (đúng quy định) |
| `BTC-Data-Vong1-TEAMS/eval/mock_tools.py` | Logic tool tham chiếu (giá sau KM theo điều kiện, tồn kho theo ngày, COD limit, lịch nghỉ, SĐT chung) | — | Trạng thái toàn cục `_ORDERS/_TICKETS` dùng chung giữa các kịch bản trong 1 process |
| `BTC-Data-Vong1-TEAMS/eval/make_example_trace.py` | Sinh trace ví dụ của BTC | — | tham khảo định dạng |
| `src/eval/evaluator.py`, `human_gate.py`, `improvement.py`, `simulator.py` | Bộ chấm nội bộ, cổng duyệt, vòng cải tiến, simulator | — | **Không được gọi** bởi entrypoint nào |
| `../Tools/extract_pdf_text.py` | Trích text từ PDF đề bài (không phụ thuộc thư viện) | PDF → text | Mất khoảng trắng với PDF này |
| `../generate_final_docs.py` | Sinh các file `.docx` báo cáo ("Giải thích", "Quy Trình Thực Hiện") | → `.docx` | Tài liệu, không thuộc pipeline |
| *(thiếu)* `eval/validate_scenarios.py` | README BTC nhắc tới nhưng **không có trong gói** | | |

---

## 5. Chỉ số đo hiện tại: Baseline vs Harness vs Mục tiêu BTC

> **Lỗi thời (ảnh chụp 2026-10-11).** Số đo hiện hành: § 12.1 (bảng lịch sử GĐ2 lần 1–6) và § 11.106.

### 5.1. Lần chạy LLM thật mới nhất (2026-10-11, `runs/report.json`, đã tái lập lại bằng `reference_eval.py` — khớp 100%)

7 kịch bản public · gpt-4o-mini · 39 lượt mỗi cấu hình.

| Chỉ số | Baseline (không bộ nhớ*) | Harness (full) | Mục tiêu BTC | Đạt? |
|---|---:|---:|---|:---:|
| Repeat-Question Rate | **N/A** (0 câu hỏi) | **0.0%** (0/1 câu) | giảm ≥ 40% so baseline | ❌ không tính được (`meets_rqr_threshold_40pct = false`) |
| Context Carryover Rate | 61.9% (13/21) | 61.9% (13/21) | càng cao càng tốt, phải > baseline | ❌ bằng baseline |
| Task Success Rate | **85.7%** (6/7) | 71.4% (5/7) | ≥ 70% | ✅ (nhưng **thấp hơn baseline**) |
| TSR ca khó | 100% (3/3) | 100% (3/3) | báo cáo | — |
| Hallucination Rate (giá & KM) | 9.1% (1/11) | **18.2%** (2/11) | ≤ 5% | ❌ |
| Hallucination Rate (mọi claim) | 7.1% (1/14) | 12.5% (2/16) | — | — |
| Số lượt TB / cuộc | 3 | 3 | — | — |
| Calls-to-Close | 1.83 | 1.83 | thấp hơn = tốt | bằng nhau |
| Vi phạm guardrail | 0 | 0 | 0 | ✅ (bộ public không có ca PII/nội bộ) |
| TTFT p50 / p95 | 282 / 364 ms | 282 / 364 ms | p95 ≤ 3 000 ms | ⚠️ **số giả** |
| Total p50 / p95 | 564 / 729 ms | 564 / 729 ms | p95 ≤ 8 000 ms | ⚠️ **số giả** |
| Call Brief latency | null | null | ≤ 5 000 ms | ❌ không được ghi đúng field |

\* Baseline thực tế **không stateless** (xem 8.1-B2).

**Nguyên nhân các ca sai (đọc trace):**
- `SAMPLE-01` (full) — **bán sai sản phẩm**: ở call_1 LLM báo giá thêm màng lọc quà tặng `SKU-AP-FLT-X`; `_persist_tool_grounded_facts` (`orchestrator.py:390-393`) lấy SKU của lần `pricing.get_quote` **cuối cùng** làm `product_advised` → call_2 tạo đơn màng lọc **690.000đ** thay vì máy `SKU-AP-Y` 5.200.000đ. Baseline (không có fact này) lại chốt đúng. Đây cũng là 2 claim sai giá của full.
- `SAMPLE-03` (cả hai) — `order.update` dùng `OD600003` (mã do mock sinh ở call_1) trong khi kịch bản kỳ vọng `OD682761` (mã trong `facts_established`). Ngoài ra agent gọi `order.update` **3 lần** trong 3 lượt (lần 2–3 mock tính phí 60.000đ) nhưng vẫn nói *"không phải thanh toán thêm phí"*, gọi khách là "chị" dù khách xưng "anh" — các lỗi này **không bị HR bắt** vì claims chỉ lấy từ kết quả `pricing`/`inventory`.

### 5.2. Số liệu trong `PIPELINE.md` cũ (2026-10-10) — **không tái lập được**

| Chỉ số | Baseline | Harness | Ghi chú |
|---|---:|---:|---|
| RQR | 0.0% | 0.0% | |
| CCR | 57.1% | 66.7% | |
| TSR | 42.9% | 71.4% | |
| HR giá & KM | 12.5% | 0.0% | |
| Total p95 | ~560 ms | 729 ms | trùng đúng con số giả của lần 10-11 (seed 42) |

Trace của lần chạy này đã bị ghi đè; tài liệu cũ tự ghi nhận đã quan sát TSR 42.9–71.4% và HR 0–33% giữa các lần chạy → **phương sai lớn, chưa có báo cáo mean ± std**.

### 5.3. Chạy offline nhánh rule-based (không LLM) — đo khả năng chịu lỗi khi mất LLM

| Bộ test | Cấu hình | RQR | CCR | TSR | TSR ca khó | HR giá & KM |
|---|---|---:|---:|---:|---:|---:|
| public (7) | baseline | N/A (0 câu) | 33.3% | 14.3% (1/7) | 0% | 85.7% |
| public (7) | full | 50.0% (3/6) | 61.9% | 14.3% (1/7) | 0% | 85.7% |
| generated_m1 (15, 14 có success_if) | baseline | N/A | 25.0% | 21.4% (3/14) | 25% | 100% |
| generated_m1 | full | N/A | 37.5% | 21.4% (3/14) | 25% | 100% |

→ Khi mất LLM, hệ thống **không dùng được** cho kinh doanh (fallback luôn báo giá `SKU-AP-Y`). Latency in ra vẫn là 282/364/564/729 ms — **giống hệt** lần chạy LLM dù xử lý thật chỉ < 1 ms → bằng chứng latency là số giả.

### 5.4. RAG (Semantic KB) — `reference_eval.py --rag`, 60 câu `qa_labeled.json`

| Chỉ số | Giá trị đo | Ghi chú |
|---|---:|---|
| Recall@3 | **76.3%** | backend TF-IDF char 2–4 gram |
| Recall@5 | **81.4%** | |
| Multi-hop full recall@3 / @5 | 16.7% / 25.0% | yếu ở câu cần ghép nhiều chunk |
| Recall@5 theo loại | single 88.0% · multi_hop 83.3% · version_conflict **100%** · numeric 75.0% | lọc theo ngày hiệu lực hoạt động tốt |
| Abstain rate (unanswerable / restricted) | **0% / 0%** | hệ thống không có cơ chế abstain ở tầng retrieval |
| False-abstain rate | 0% | |

> `search_policy` trong runtime trả **top-3 cố định** (`semantic_rag.py:46`). Không lấy được bản chính sách cũ khi khách hỏi về đơn mua trước ngày hiệu lực (bản cũ bị lọc hẳn theo ngày gọi).

### 5.5. ASR (faster-whisper `base`, CPU, audio TTS tự sinh)

| Chỉ số | Giá trị | Mục tiêu BTC |
|---|---:|---|
| Số file đo | 4 (D01–D04) | ≥ 20 file của team + 12 hội thoại BTC |
| WER trung bình | **42.6%** | báo cáo (không ngưỡng) |
| CER trung bình | **32.5%** | báo cáo |
| Entity Accuracy | chỉ kiểm entity dạng số; ví dụ D01: `room_area` đúng, `budget`/`price` sai | exact-match SĐT & số tiền |
| Định dạng cho `reference_eval --asr` | ❌ chưa có `hypotheses.json` | bắt buộc ngày chấm |

### 5.6. Hiệu năng & chi phí đo được

| Hạng mục | Giá trị | Nguồn |
|---|---:|---|
| Dựng Call Brief (resolve + build, không LLM) | p50 **0.05 ms**, max 0.07 ms | đo `perf_counter` 30 lần |
| 1 lượt orchestrator nhánh fallback | p50 **0.21 ms** | đo `perf_counter` |
| 1 lượt có LLM (TTFT / Total) | **chưa đo** | code không đo; ước lượng thô: 1–7 round-trip tuần tự tới OpenAI mỗi lượt |
| Token / lượt (eval) | median **~5 200**, max 10 753 (full) / 13 933 (baseline) | `llm_cost` trong trace |
| Tool call / lượt | TB 1.54, max 6 (eval); max **19** (UI) | trace |
| Chi phí / lượt | ~**22–27 VND** | gpt-4o-mini, tỷ giá trong `.env` |
| Chi phí / cuộc 3 lượt | ~**68 VND** | `runs/full.jsonl` |
| Phiên UI dài 50 lượt | ~**1 363 VND** | `runs/ui_session.jsonl` (prompt phình theo lịch sử) |

---

## 6. Giới hạn hiện tại so với vận hành thực tế cho doanh nghiệp telesale

| Khía cạnh | Doanh nghiệp thật cần | Hệ thống hiện tại |
|---|---|---|
| Kênh & tổng đài | Tích hợp tổng đài (SIP/VoIP, call center cloud), Zalo OA API, Facebook Messenger API, livestream | Chỉ text qua UI; audio = upload file; không có kết nối kênh nào |
| Hệ thống nghiệp vụ | CRM/OMS/ERP/kho thật, đồng bộ giá & KM theo thời gian thực | 100% `mock_tools.py` của BTC (dữ liệu tĩnh, trạng thái in-process) |
| Voice | Real-time ASR + TTS, barge-in, TTFA < 2.5 s | Không có voice real-time; ASR file `base` WER ~43% (trên TTS) |
| Quy mô | ~4 000 cuộc/ngày, hàng chục phiên đồng thời | 1 phiên Streamlit; SQLite 1 file; không queue, không worker |
| Độ trễ | Phản hồi < 3–5 s mỗi lượt | **Chưa đo**; prompt ~5k token + tối đa 7 lượt gọi API tuần tự mỗi lượt |
| Độ tin cậy LLM | Tái lập, kiểm soát hành vi | Không đặt `temperature`, không seed; TSR dao động 42.9–71.4%; > 6 vòng tool → ném lỗi → rơi về rule-based âm thầm |
| An toàn giao dịch | Idempotency, xác nhận trước khi tạo/đổi đơn | `order.update` có thể bị gọi lặp mỗi lượt (đã xảy ra, phát sinh phí) |
| Bảo vệ dữ liệu cá nhân (NĐ 13/2023/NĐ-CP) | Mask/tokenize PII trước khi gửi bên thứ ba, đồng ý của chủ thể, xóa theo yêu cầu, kiểm soát chuyển dữ liệu ra nước ngoài | Text **chưa mask** gửi lên OpenAI và ghi trace; có hàm `delete_customer` nhưng không có quy trình/giao diện; API key thật nằm trong `Code/.env` |
| Quy định telesale (chống cuộc gọi rác – NĐ 91/2020/NĐ-CP) | Danh sách không làm phiền, khung giờ gọi, ghi nhận đồng ý | Không có |
| Bàn giao cho người | Hàng đợi, routing theo kỹ năng, màn hình copilot cho nhân viên | `handoff.transfer` mock trả `ticket_id`; không có màn hình nhân viên nhận |
| Bảo mật & phân quyền | Auth, RBAC theo tool (ai được ghi đơn), audit bền vững | Không auth; audit chỉ in-memory |
| QA & cải tiến | Chấm 100% cuộc gọi, học từ kết quả chốt, A/B kịch bản | QA agent/Improvement loop chưa chạy |
| Vận hành | Logging tập trung, metrics, alert, backup, retention | Log ra stdout; DB không có retention; dữ liệu demo lẫn dữ liệu thật |
| Đa ngành/đa tenant | Thêm ngành/catalog không sửa code | Prompt, ITN, ASR-fix, template mở đầu viết cứng theo bộ dữ liệu mẫu (máy lọc không khí, "chị Hoa") |

---

## 7. Điểm tốt hiện tại (xét mục tiêu chạy thực tế và giải quyết bài toán doanh nghiệp)

1. **Kiến trúc module rõ ràng, dễ đọc, dễ thay thế**: tách normalizer / identity / call brief / memory / tool gateway / guardrail / tracer; `pipeline.py` gom lại; chú thích tiếng Việt giải thích *vì sao*. Đây là nền tốt để phát triển tiếp.
2. **Nguồn sự thật duy nhất cho giá/tồn kho/KM**: mọi số liệu đi qua `mock_tools.py` của BTC (giá sau KM theo điều kiện, tồn kho theo ngày, COD limit) → cùng cơ sở với bộ chấm; orchestrator **tự tiêm `on` = ngày cuộc gọi** (sửa bug thật LLM quên truyền ngày).
3. **LLM function-calling với schema tự sinh từ `tools.schema.json`**: parser micro-DSL (`client.py:_parse_dsl_type`) → thêm tool mới không phải viết tay schema; tên tool đổi `.`↔`__` an toàn.
4. **Phân giải SKU 4 tầng** (enum variant thật → khớp thuộc tính NFKD → difflib → trả danh sách variant cho LLM tự sửa): thiết kế tốt, tổng quát, giảm lỗi tự ghép SKU — rất hữu ích cho catalog nhiều biến thể size/màu.
5. **Guardrail "nói đã làm mà không làm"**: chặn câu "đã lên đơn/đã đổi size" khi chưa gọi `order.create/order.update` (kiểm chứng ✔) — đúng nỗi đau thực tế (hứa miệng, không có đơn).
6. **Working memory theo (khách, ngày)**: buộc LLM tra lại giá/tồn kho mỗi cuộc gọi mới thay vì tin hội thoại cũ — tránh báo giá đã hết hạn (Case 1/Case 4).
7. **RAG chính sách có phiên bản & phân quyền**: lọc ngày hiệu lực + loại tài liệu nội bộ khỏi truy hồi → Recall@5 81.4%, **version_conflict 100%**; tài liệu nội bộ (giá nhập) không bao giờ vào ngữ cảnh LLM.
8. **Định danh đa kênh hoạt động**: Zalo ID / FB ID tra ra đúng khách `C001`; phát hiện SĐT dùng chung (C034/C035); khách mới có `customer_id` ổn định bằng SHA-256 + salt, không lộ SĐT thô trong id.
9. **Suy giảm có kiểm soát (graceful degradation) ở mọi tầng**: thiếu key → rule-based; SQLite lỗi → in-memory; CUDA thiếu runtime → CPU; thiếu sklearn → substring; thiếu Streamlit → hướng dẫn cài. Hệ thống không crash.
10. **Chi phí LLM thấp và được đo thật**: ~68 VND/cuộc 3 lượt với gpt-4o-mini, có `CostTracker` cộng dồn theo token thật — đáp ứng tiêu chí 7 về ước tính chi phí.
11. **Trace tương thích script BTC**: đủ field required, `reference_eval.py` đọc được, số liệu tái lập được từ trace đang lưu.
12. **Có UI dùng thử được**: chat, upload audio→ASR, Call Brief, dòng thời gian bộ nhớ (hiện cả fact bị supersede), log tool, thẻ đơn hàng/lịch gọi lại, nút chạy eval.
13. **Dữ liệu test mở rộng bám dữ liệu thật**: 15 kịch bản sinh thêm (8 ca khó: KM hết hạn, COD vượt hạn mức, SĐT chung, SKU ngừng bán, trade-in…) dùng đúng số liệu catalog.
14. **Tài liệu cũ đã tự ghi nhận một phần hạn chế** (dao động kết quả, WER trên TTS, CUDA) — có văn hóa ghi nhận lỗi.

---

## 8. Điểm chưa tốt, cần cải thiện để dùng được thực tế

Mức độ: 🔴 nghiêm trọng (ảnh hưởng tính đúng của số liệu/khách hàng) · 🟠 cao · 🟡 trung bình.

### 8.1. Tính trung thực & hợp lệ của đánh giá

| # | Mức | Vấn đề | Bằng chứng | Hệ quả |
|---|---|---|---|---|
| B1 | 🔴 | **Latency là số giả** | `runner.py:138` `random.randint(350, 750)`; `pipeline.py:90` `380`; `tracer.py:33-35` `ttft = total//2`, `call_brief_ms = 115` | Bảng hiệu năng "ĐẠT" không có giá trị; BTC coi số liệu không tái lập là không có số liệu |
| B2 | 🔴 | **Baseline không stateless** | Test: sau 1 lượt call_1 ở baseline, Call Brief call_2 vẫn có `product_advised=SKU-AP-Y`, `must_carry_over=[product_advised, price_quoted_vnd]` (profile ghi từ tool không bị xóa giữa các call) | CCR baseline = full (61.9%); vi phạm điều kiện "chỉ khác ở việc nạp bộ nhớ" |
| B3 | 🔴 | **Full được bơm đáp án** | `runner.py:149-171` seed `facts_established` + episode từ file kịch bản | Bộ nhớ không phản ánh khả năng trích xuất thật; trong production không có bước này |
| B4 | 🔴 | **Kết quả mới nhất: hệ thống thua baseline** | TSR 71.4% vs 85.7%; HR giá 18.2% vs 9.1% | Chưa chứng minh được giá trị bộ nhớ bằng số |
| B5 | 🔴 | **`run_eval.py` không nhận tham số BTC** | không có argparse; `run_eval.py:33` cứng `public_sample` | BTC không chạy được bộ ẩn 41 kịch bản theo lệnh chuẩn |
| B6 | 🟠 | **Extractor `claims` chỉ lấy từ kết quả tool** | `orchestrator.py:341-352` | Lời LLM sai (VD "không mất phí" khi tool báo 60.000đ) không bị tính HR; báo giá phụ kiện bị tính như giá sản phẩm chính |
| B7 | 🟠 | **Extractor `questions` bỏ sót** | chỉ giữ câu kết thúc `?` có từ khóa slot (`orchestrator.py:354-368`); 39 lượt → 1 câu hỏi | RQR không có mẫu số → không tính được mức giảm; rủi ro bị BTC đánh giá "ăn gian" khi chấm tay 20 lượt |
| B8 | 🟡 | Không có `memory_writes`, `call_brief_latency_ms`, `customer_input_mode` trong trace | `tracer.py` | `memory_checks` của BTC không chạy; Call Brief latency = null |
| B9 | 🟡 | Kết quả không tái lập giữa các lần | không đặt `temperature`/seed; không lặp nhiều lần | Không báo được mean ± std |
| B10 | 🟡 | `main.py` ghi nối vào `runs/full.jsonl` | `main.py:29` | Có thể làm bẩn trace chấm nếu chạy demo sau eval |

### 8.2. Hành vi agent & bộ nhớ

| # | Mức | Vấn đề | Bằng chứng |
|---|---|---|---|
| A1 | 🔴 | **Đầu độc `product_advised`**: lần `pricing.get_quote` cuối cùng (kể cả quà tặng/phụ kiện) ghi đè sản phẩm đã tư vấn | SAMPLE-01 full chốt đơn màng lọc 690k thay vì máy 5.2tr |
| A2 | 🔴 | **Tool ghi không idempotent**: `order.update` gọi lặp mỗi lượt, phát sinh phí | SAMPLE-03: 3 lần `exchange_size`, lần 2–3 `fee_vnd=60000` |
| A3 | 🟠 | **Call Brief mặc định "chị Hoa"** cho khách không có tên | `call_brief.py:78-79`; test số lạ → "Hoa chị" |
| A4 | 🟠 | Không có **episodic writer** tự động cuối cuộc gọi (production) | chỉ runner/`main.py` gọi `add_episode` |
| A5 | 🟠 | **TTL không được áp dụng**; lịch sử supersede mất trong store in-memory | test `ttl_days=0` vẫn trả fact; `profile.py:39-72` |
| A6 | 🟠 | Ca SĐT chung: mọi người dùng chung `customer_id="AMBIGUOUS"`; không có luồng xác minh tên | `call_brief.py:45-63`; `resolver.py` |
| A7 | 🟠 | Guardrail lệch giá **tắt ở chế độ LLM**; keyword nội bộ sai cả hai chiều ("quy định nội bộ đổi trả 7 ngày" bị chặn, "giá vốn 3.2 triệu" lọt); không chặn "em là nhân viên thật" | test guardrail 9 ca; `orchestrator.py:249-255` |
| A8 | 🟠 | Không có prompt/luật trả lời "AI hay người", từ chối bình luận đối thủ, xóa dữ liệu theo yêu cầu (đều là ca khó trong bộ ẩn) | system prompt `orchestrator.py:296-324` |
| A9 | 🟡 | Kênh bị bỏ qua khi eval (luôn HOTLINE); `channel_identity`, `seed_history`, `input_mode` không được đọc | `runner.py:107` |
| A10 | 🟡 | Prompt ~5k token/lượt, không nén ngữ cảnh; > 6 vòng tool → exception → rule-based âm thầm | `client.py:166-245` |
| A11 | 🟡 | Xưng hô sai giới tính (khách "anh" bị gọi "chị") | trace SAMPLE-03 |

### 8.3. Xử lý tiếng Việt & PII

| # | Mức | Vấn đề | Bằng chứng (test) |
|---|---|---|---|
| V1 | 🟠 | Teencode `"k"` trùng khóa → "không" thành "nghìn" | `"sp nay co ship cod k a"` → `"sản phẩm nay có giao hàng COD nghìn anh"` |
| V2 | 🟠 | `"sai"→"size"` phá nghĩa | `"chị nói sai rồi em"` → `"chị nói size rồi em"` |
| V3 | 🟠 | ITN chỉ 6 số viết cứng; không ITN SĐT/ngày giờ tương đối | `"ba triệu chín trăm nghìn"` giữ nguyên |
| V4 | 🔴 | **PII chưa mask gửi lên OpenAI và ghi trace** (`customer_text`) | `"CCCD … 012345678901, stk …"` giữ nguyên trong `normalized_text`; `pii_masked_text` không dùng |
| V5 | 🟡 | Guardrail mask cả SĐT 10 số trong lời agent (BTC cho phép SĐT) → không đọc lại SĐT xác nhận được | `"0912345678"` → `"09****78"` |
| V6 | 🟡 | ASR `base` WER 42.6% (TTS), chỉ 4 file; không có từ điển sửa lỗi theo catalog ngoài 9 cụm | `runs/asr_report.json` |

### 8.4. Kiến trúc MCP / A2A / Cải tiến / Dữ liệu

| # | Mức | Vấn đề |
|---|---|---|
| K1 | 🟠 | "MCP Gateway" không phải MCP server; không có `mcp-memory` (đề M1 hướng MCP yêu cầu ≥ 2 MCP server, bắt buộc `mcp-memory`); không auth/phân quyền như mô tả |
| K2 | 🟠 | A2A hình thức: 2/4 agent không được gọi; Sales là template; không có tình huống chứng minh "tách agent tốt hơn" |
| K3 | 🔴 | **Vòng cải tiến chưa chạy**: `ImprovementLoop`, `HumanReviewGate` là dead code; không có số liệu vòng 0 → vòng 1 trên cùng bộ test (yêu cầu M1, tiêu chí 5 = 13%) |
| K4 | 🟠 | Dataset dưới chuẩn M1: 22 kịch bản (đủ ≥ 20) nhưng chỉ 7 được chạy; không có ≥ 120 hội thoại, ≥ 40 audio/≥ 1 giờ, ≥ 30 khách đa kênh |
| K5 | 🟡 | Trạng thái mock toàn cục làm mã đơn phụ thuộc thứ tự chạy; SAMPLE-03 kỳ vọng mã đơn từ `facts_established` → mâu thuẫn giữa "dùng mã đơn thật" và "khớp đáp án" (nên hỏi BTC) |
| K6 | 🟠 | Database chưa chuẩn (trùng dữ liệu, phân mảnh danh tính, mô hình 1 ô/khách, xóa không hết, không migration, phụ thuộc file `-wal`) — **đánh giá đầy đủ ở § 10** |
| K7 | 🟠 | **API key OpenAI thật nằm trong `Code/.env`**, thư mục không phải git repo và không có `.gitignore` → nguy cơ lộ khi nộp/chia sẻ |

---

## 9. Phương hướng cải tiến, chỉnh sửa (ưu tiên theo tác động)

### P0 — Sửa tính hợp lệ của số liệu (1–3 ngày, bắt buộc trước khi nộp)

1. **Đo latency thật**: bọc `time.perf_counter()` quanh `CallBriefBuilder.build` (+ kiểm tra tính mới) → ghi `call_brief_latency_ms` ở turn 1 call_2/3; bật `stream=True` để đo TTFT thật; ghi `total_ms` thật; xóa `random.randint` và hằng số 380/115. Chạy ≥ 100 lượt, bỏ 3 lượt warm-up.
2. **`run_eval.py` có CLI chuẩn BTC**: `--scenarios <dir> --config full|baseline_no_memory --out <trace.jsonl>` (+ `--seed`, `--repeats`), giữ chế độ không tham số chạy cả 2 cấu hình như hiện tại.
3. **Baseline đúng nghĩa**: khởi tạo `MemoryService` mới cho **mỗi call** (hoặc cờ `persist_across_calls=False`) — chỉ giữ working memory trong call.
4. **Bỏ seed `facts_established`** khỏi cấu hình full (hoặc tách thành cấu hình ablation `full_oracle_memory` để báo cáo riêng); thay bằng **bộ trích xuất bộ nhớ thật** cuối mỗi lượt/cuộc (LLM structured output → `memory_writes` có `op=set|supersede`, `source=call_n#turn_k`, đã mask PII) + **episodic summarizer** cuối cuộc gọi.
5. **Sửa `product_advised`**: chỉ ghi khi `order.create` thành công hoặc khi LLM gọi tool riêng `memory.propose(product_advised=…)`; bỏ cơ chế "quote cuối cùng thắng".
6. **Extractor trung thực**: `claims` trích từ **lời agent** (regex số tiền/phí/ngày giao/bảo hành + LLM extractor gán field) rồi đối chiếu với tool; `questions` phân loại mọi câu hỏi bằng LLM (slot + open/confirm). Ghi rõ cách trích trong báo cáo.
7. **Guardrail đối chiếu số trong lời LLM với kết quả tool** ở chế độ LLM (giá, phí, tồn kho); chặn/viết lại khi lệch.
8. **Mask PII trước khi gửi LLM và trước khi ghi trace** (dùng `pii_masked_text`, token hóa để nghiệp vụ vẫn dùng được); cho phép SĐT 10 số trong lời agent.
9. **Ổn định LLM**: `temperature=0`, cố định `seed`; chạy 3 lần → báo mean ± std; cập nhật bảng A.6.
10. **Gỡ API key khỏi `Code/.env` khi chia sẻ**, thêm `.env.example` + `.gitignore`; khi đóng gói nộp bài loại `.env` và `backup_*/` (đã có `scripts/package_submission.py`, xem § 11.6).
11. **Database — sửa lỗi dữ liệu** (chi tiết § 10.6, nhóm D-P0): làm sạch DB demo, chặn ghi trùng, một khách một mã, đường dẫn DB tuyệt đối, checkpoint WAL khi đóng.

### P1 — Chất lượng agent & đáp ứng đầy đủ M1 (1–2 tuần)

1. **Vòng cải tiến thật (tiêu chí 5)**: nối `ImprovementLoop` — Knowledge Gap (câu trả lời "chưa có thông tin"/RAG điểm thấp → danh sách gap → bổ sung KB → tự thêm vào bộ test) + Exemplar Bank (cuộc chốt đơn → few-shot); `HumanReviewGate` thành CLI duyệt; báo cáo vòng 0 vs vòng 1 trên cùng bộ test, có rollback.
2. **Idempotency tool ghi**: khóa theo `(order_id, action, new_variant_sku)` trong phiên; yêu cầu xác nhận khách trước `order.create/update`.
3. **Normalizer**: sửa khóa trùng `"k"`, bỏ `"sai"/"a"/"c"/"e"` khỏi dict tuyệt đối (dùng ngữ cảnh), viết ITN số tiếng Việt tổng quát (triệu/nghìn/trăm/mươi/lẻ/rưỡi), ITN SĐT đọc bằng chữ, ngày giờ tương đối ("chiều mai", "thứ 7 tuần sau").
4. **Call Brief**: bỏ mặc định "Hoa"/"chị", xưng hô từ CRM/hội thoại; kiểm tra tính mới (KM hết hạn, tồn kho, tương tác kênh khác) qua tool lúc nhận diện; `precomputed_parts`; template follow-up theo blocker thực tế.
5. **Identity**: luồng xác minh tên cho SĐT chung → chọn đúng `customer_id`; không dùng chung khóa "AMBIGUOUS"; dùng `link_identities` khi CRM xác nhận cùng người.
6. **Memory**: áp TTL khi đọc (địa chỉ > 180 ngày → cho phép hỏi lại); giữ lịch sử supersede trong store; trường `provenance`.
7. **Prompt/luật ca khó**: trả lời trung thực "em là trợ lý AI" (claim `is_human=false`), không bình luận đối thủ, quy trình xóa dữ liệu, chính sách cũ cho đơn cũ (truy hồi theo ngày mua chứ không chỉ ngày gọi), abstain khi RAG không đủ căn cứ.
8. **Eval đầy đủ**: chạy cả `generated_m1` + bộ tự sinh; đọc `channel/channel_identity/seed_history/input_mode`; reset trạng thái `mock_tools` mỗi kịch bản; xuất `asr/hypotheses.json` và `rag_results.json` để chạy `--asr`, `--rag`.
9. **MCP/A2A đúng nghĩa**: dựng `mcp-memory` + `mcp-catalog` bằng FastMCP/MCP SDK (đọc/ghi bộ nhớ có phân quyền); hoặc trình bày thật thà là "single-agent + tool router" và bỏ các agent hình thức; nếu giữ A2A, cho `ContextAgent` quyết định ghi nhớ và `QAEvaluator` chấm từng cuộc.
10. **ASR**: thử `small`/`medium` hoặc PhoWhisper, VAD + lọc nhiễu, từ điển hotword theo catalog; ≥ 20 file; Entity Accuracy cho SĐT/số tiền exact-match.
11. **Database — chuẩn hóa schema v2** (chi tiết § 10.6–10.7, nhóm D-P1): bảng khách/định danh/fact có trạng thái/cuộc gọi/sản phẩm quan tâm/đơn hàng tham chiếu, khóa ngoại, index, migration, xóa dữ liệu trọn vẹn.

### P2 — Hướng tới vận hành doanh nghiệp (sau Vòng 1)

1. **Hạ tầng**: FastAPI + worker, Postgres (profile/episodic) + pgvector/Qdrant, Redis cho working memory, multi-session; container hóa.
2. **Tích hợp thật**: tổng đài (SIP/call center cloud), Zalo OA, Messenger; CRM/OMS thật qua MCP server có auth, RBAC theo tool, audit log bền vững.
3. **Quan sát & chất lượng**: Langfuse/OpenTelemetry cho trace, dashboard latency/chi phí/tỷ lệ chốt; LLM-as-judge 12 tiêu chí + đối chiếu người (kappa); chấm 100% cuộc gọi.
4. **Tuân thủ**: quy trình đồng ý & xóa dữ liệu theo NĐ 13/2023/NĐ-CP, giới hạn chuyển dữ liệu ra nước ngoài (cân nhắc LLM local/endpoint trong nước cho dữ liệu nhạy cảm), danh sách không làm phiền & khung giờ gọi theo NĐ 91/2020/NĐ-CP.
5. **Copilot cho nhân viên** (M2): gợi ý câu trả lời, cảnh báo cam kết sai realtime, màn hình nhận handoff có brief.
6. **Tối ưu chi phí/độ trễ**: nén lịch sử, cache schema tool, prompt caching, định tuyến model nhỏ/lớn theo độ khó.

---

## 10. Đánh giá chuyên sâu Database (`Code/data/harness_memory.db`)

> Kiểm tra ngày 2026-10-14 bằng truy vấn **chỉ đọc** (`sqlite3 … ?mode=ro`) trên DB thật, kết hợp đọc `src/memory/sqlite_store.py`, `profile.py`, `episodic.py`, `working.py`, `identity_map.py`, `main.py`, `ui_app.py`. Không sửa DB.

### 10.1. Hiện trạng & vai trò

| Thuộc tính | Giá trị |
|---|---|
| Engine | SQLite 3, `journal_mode = WAL`, `page_size = 4096` |
| File | `harness_memory.db` (69 KB, sửa lần cuối 2026-10-10) + **`harness_memory.db-wal` (1.38 MB, sửa 2026-10-11)** + `-shm` |
| Toàn vẹn kỹ thuật | `PRAGMA integrity_check = ok` |
| Quản lý phiên bản schema | `PRAGMA user_version = 0` (không có migration) |
| Khóa ngoại | `PRAGMA foreign_keys = 0`, schema không khai báo FK nào |
| Index | chỉ 3 index tự sinh từ PRIMARY KEY; `episodic_records` **không có PK/index nào** |
| Ai ghi | `main.py` (seed cứng khách Hoa), `ui_app.py` (mọi lượt chat), `IdentityResolver` (khách mới) |
| Ai **không** dùng | `run_eval.py`/`ScenarioRunner` chạy `enable_persistence=False` → **tầng DB chưa từng được kiểm thử tự động** |

| Bảng | Số dòng | Vai trò (tầng bộ nhớ) | Khóa |
|---|---:|---|---|
| `customer_profiles` | 170 | Profile memory (fact bền vững, lịch sử supersede) | PK `(customer_id, key, observed_at)` |
| `episodic_records` | 12 | Episodic memory (tóm tắt cuộc gọi) | **không có** |
| `working_sessions` | 19 | Working memory (state JSON của phiên) | PK `session_id` |
| `identity_links` | 8 | Ánh xạ `contact_hash → CUST-ANON-…` cho khách ngoài CRM | PK `contact_hash` |

### 10.2. Schema hiện tại

```mermaid
erDiagram
    customer_profiles {
        TEXT customer_id PK "SĐT thô / C001 / CUST-001 / CUST-ANON"
        TEXT key PK
        TEXT observed_at PK "giờ máy, không phải ngày gọi"
        TEXT value "JSON"
        REAL confidence "luôn 1.0"
        TEXT source_session "luôn rỗng"
        INTEGER ttl_days "luôn NULL"
        INTEGER superseded
        TEXT superseded_by "str() thô, không phải JSON"
    }
    episodic_records {
        TEXT customer_id "không PK, không index"
        TEXT session_id
        INTEGER call_index
        TEXT call_date
        TEXT channel
        TEXT customer_goal
        TEXT product_advised "1 sản phẩm / cuộc"
        INTEGER price_quoted_vnd
        TEXT promo_code
        TEXT promo_expiry
        TEXT blocker
        TEXT outcome
        TEXT summary
        TEXT created_at "dùng để sắp xếp"
    }
    working_sessions {
        TEXT session_id PK "SESS-customer-ngày"
        TEXT state_json "toàn bộ lịch sử message"
        TEXT updated_at
    }
    identity_links {
        TEXT contact_hash PK "SHA-256 + salt"
        TEXT master_customer_id
        TEXT created_at
    }
```

Bốn bảng **độc lập hoàn toàn**: không có bảng khách hàng gốc, không có quan hệ/khóa ngoại; liên kết chỉ "ngầm" qua chuỗi `customer_id` (và nhúng trong chuỗi `session_id`).

### 10.3. Kết quả truy vấn dữ liệu thật

| Kiểm tra | Kết quả | Đánh giá |
|---|---|---|
| Fact "active" (`superseded = 0`) so với fact khác nhau thật | **134 dòng active cho 42 cặp (khách, key)** → 92 dòng thừa (~69%) | ✖ trùng lặp |
| Cặp có > 1 dòng active | 15+ cặp, ví dụ `C001.customer_name` ×4, `C001.promo_code` ×5 | ✖ (cùng giá trị, nhưng vi phạm "1 fact – 1 bản active") |
| Khách Hoa được lưu dưới | `C001` (55 dòng), `0984726714` (28), `CUST-001` (28) | ✖ phân mảnh danh tính; SĐT thô làm khóa |
| Lịch sử `C001.product_advised` (2 giờ test UI) | `SKU-AP-Y` → `SKU-SN-RUN2` (giày) → `SKU-AP-Y`; giá 5.200.000 → 1.521.000 → 1.690.000 → 5.200.000 | ✖ một ô bị ghi đè qua lại giữa các sản phẩm |
| `promo_code` của `C001` | `COD-0` (KM thanh toán) | ◐ ghi đè KM sản phẩm |
| `episodic_records` | 12 dòng = 3 id × **4 bản giống hệt** (`SESS-01`, call 1, 2026-10-15) | ✖ Call Brief báo "4 cuộc gọi trước" |
| `source_session` rỗng | **170/170** | ✖ không truy vết nguồn |
| `confidence` | 1.0 cho mọi dòng | ◐ trường vô nghĩa |
| `ttl_days` | NULL 170/170 | ✖ TTL không được dùng |
| Khoảng `observed_at` | 2026-10-10 → 2026-10-11 (giờ máy) trong khi ngày gọi nghiệp vụ 2026-10-15 → 2026-12-12 | ✖ lẫn 2 trục thời gian |
| `identity_links` không có dữ liệu đi kèm | 4/8 (`CUST-ANON-9be70d…`, `f4a680…`, `c26985…`, `1cebf6…`) | ◐ dữ liệu mồ côi |
| `working_sessions` theo định dạng khóa cũ | 7/19 (`SESS-C001`, `SESS-CUST-NEW-…` từ thời sinh UUID ngẫu nhiên) | ✖ không migration/dọn dẹp |
| Phiên làm việc lâu nhất | 18 message, 5.7 KB JSON; không có hạn sống | ◐ |
| PII dạng CCCD/SĐT trong `working_sessions` | 0 lần khớp regex | ✔ (dữ liệu test hiện tại) |
| **Chỉ mở file `.db` (không có `-wal`)** | còn 111/170 profile, 10/19 working, **0/8 identity_links** | ✖ ~35% profile và toàn bộ liên kết danh tính chỉ nằm trong WAL |

### 10.4. Điểm tốt của database

1. **Đúng hướng thiết kế tầng**: mỗi tầng bộ nhớ một bảng, tách rõ profile / episodic / working / identity — khớp mô hình 4 tầng của đề.
2. **An toàn kỹ thuật cơ bản**: mọi câu SQL dùng tham số `?` (không SQL injection); `integrity_check = ok`; bật WAL (đọc không chặn ghi).
3. **Lịch sử profile append-only**: dòng cũ không bị xóa mà đánh dấu `superseded` + `superseded_by` → có nền tảng cho audit và dòng thời gian bộ nhớ trên UI.
4. **Định danh khách mới không lộ SĐT**: `identity_links` lưu `SHA-256 + salt`, mã khách ổn định xuyên phiên.
5. **Suy giảm có kiểm soát**: lỗi mở/ghi DB → `available=False`, hệ thống chạy in-memory thay vì crash.
6. **Gọn nhẹ, không cần server**: phù hợp demo M1 một phiên, dễ mang theo.

### 10.5. Vấn đề phát hiện (nguyên nhân gốc trong code)

| # | Mức | Vấn đề | Nguyên nhân gốc | Hệ quả |
|---|---|---|---|---|
| D1 | 🔴 | **Fact trùng "active"** | `ProfileMemoryStore.set_fact` (`profile.py:39-67`) chỉ đánh dấu supersede khi giá trị **khác**; giá trị giống vẫn `INSERT` dòng mới với `observed_at` mới (nằm trong PK) → không có ràng buộc "mỗi (khách, key) chỉ 1 dòng active" | DB phình ~3×; đếm/timeline sai; tiền đề cho mâu thuẫn khi 2 tiến trình ghi song song |
| D2 | 🔴 | **Một khách – nhiều mã** | `main.py` seed cùng dữ liệu cho `C001`, SĐT và `CUST-001`; `CallBriefBuilder` đọc gộp profile theo SĐT **và** `customer_id`; không có bảng `customers` gốc | Dữ liệu lệch nhau giữa các bản; SĐT thô thành khóa chính (trái với thiết kế băm của `identity_map`); xóa theo 1 mã vẫn còn 2 mã kia |
| D3 | 🔴 | **Mô hình "1 ô / khách"** cho `product_advised`, `price_quoted_vnd`, `order_id`, `promo_code` | Profile là key–value phẳng; `_persist_tool_grounded_facts` ghi đè theo tool call cuối | Khách quan tâm nhiều sản phẩm/nhiều đơn bị mất thông tin (đã thấy AP-Y ↔ RUN2 lật qua lại); ca khó "16 lượt, 4 sản phẩm" không biểu diễn được; quà tặng/phụ kiện đè sản phẩm chính |
| D4 | 🔴 | **Tham chiếu đơn hàng không bền** | `order_id` lưu bền trong DB, nhưng hệ đơn (`mock_tools._ORDERS`) chỉ trong RAM, bộ đếm `OD600001…` khởi động lại từ đầu mỗi process | Sau restart, `C001.order_id = OD600001` trỏ tới đơn không tồn tại **hoặc trùng mã với đơn của khách khác** → đổi size/huỷ nhầm đơn |
| D5 | 🟠 | **Episode trùng & sai thứ tự** | `episodic_records` không có PK/UNIQUE `(customer_id, session_id)`; `main.py` mỗi lần chạy lại thêm 1 bản; `load_all_episodes` sắp theo `created_at` (giờ máy) | Call Brief "4 cuộc gọi trước" (thực tế 1); "cuộc gần nhất" sai nếu nạp lịch sử không theo thứ tự ngày gọi |
| D6 | 🟠 | **Lẫn trục thời gian, TTL vô hiệu** | `observed_at/created_at/updated_at = datetime.now()`; không có `valid_from/expires_at` theo ngày nghiệp vụ; `get_active_facts` không đọc `ttl_days` | Không tính được "fact đã hết hạn" (địa chỉ > 6 tháng, ý định đã nguội) — yêu cầu RQR/TTL của đề |
| D7 | 🟠 | **Không có provenance** | `set_profile_fact` gần như luôn gọi với `session_id=""`; không có cột `source_turn`, `actor` | Không trả lời được "fact này đến từ cuộc nào, lượt nào" (M2), không chống đầu độc bộ nhớ, không xuất được `memory_writes` cho trace BTC |
| D8 | 🟠 | **Dữ liệu nằm trong file WAL** | Không bao giờ `close()`/`PRAGMA wal_checkpoint`; WAL chỉ tự checkpoint ở ~1000 trang | Sao chép/nộp riêng `harness_memory.db` mất ~35% profile và 100% identity link |
| D9 | 🟠 | **Xóa dữ liệu không trọn vẹn** | `SQLiteStore.delete_customer` chỉ xóa `customer_profiles` + `episodic_records` | `working_sessions` (nguyên văn hội thoại) và `identity_links` còn lại → không đáp ứng "xóa toàn bộ dữ liệu 1 khách" (M2, NĐ 13/2023) |
| D10 | 🟡 | **Working session không hết hạn, không dọn** | Không có `expires_at`/job dọn; đổi định dạng khóa (`SESS-C001` → `SESS-C001-<ngày>`, bỏ `CUST-NEW-<uuid>`) không kèm migration | Dữ liệu rác tích lũy; state_json chứa toàn bộ message không giới hạn |
| D11 | 🟡 | **Không quản lý schema** | `user_version = 0`, `CREATE TABLE IF NOT EXISTS` — thêm cột sau này không tự áp vào DB cũ; không FK; `superseded_by` lưu `str(value)` trong khi `value` lưu JSON | Nâng cấp schema dễ hỏng âm thầm; kiểu dữ liệu không đồng nhất |
| D12 | 🟡 | **Nạp cả DB vào RAM** khi khởi tạo | `ProfileMemoryStore`/`EpisodicMemoryStore` gọi `load_all_*()` trong `__init__` | Chi phí khởi động và RAM tăng tuyến tính theo tổng số khách; không phù hợp ~4.000 cuộc/ngày |
| D13 | 🟡 | **Ghi không theo giao dịch, lỗi bị nuốt** | `commit()` sau từng câu lệnh; một kết nối `check_same_thread=False` không khóa; lỗi `sqlite3.Error` chỉ log warning | Một lượt hội thoại có thể ghi được một nửa; RAM và DB lệch nhau mà không ai biết |
| D14 | 🟡 | **Đường dẫn DB tương đối** | Mặc định `"data/harness_memory.db"` theo thư mục hiện hành | Chạy từ thư mục khác (vd `streamlit run Code/ui_app.py` ở thư mục gốc) tạo DB rỗng mới → "mất trí nhớ" âm thầm |
| D15 | 🟡 | **Dữ liệu demo, test và "thật" trộn chung một file** | Không có script seed/reset; `main.py` seed cứng; UI test với ngày 2026-12-12 | Demo cho BTC có thể hiện Call Brief sai (4 cuộc gọi, sản phẩm lật qua lại) |
| D16 | 🟡 | **PII lưu dạng rõ** | Tên khách plaintext, SĐT thô làm `customer_id`; không mã hóa at-rest; file DB nằm trong thư mục mã nguồn | Rủi ro lộ dữ liệu khi nộp repo/chia sẻ máy |

### 10.6. Hướng khắc phục

**D-P0 — sửa ngay (≤ 1 ngày, không đổi kiến trúc):**
1. **Làm sạch DB demo**: sao lưu, `PRAGMA wal_checkpoint(TRUNCATE)`, rồi tạo lại DB từ một script seed **idempotent** (`scripts/seed_demo_db.py`: chỉ `C001`, kiểm tra tồn tại trước khi ghi). Bỏ seed theo SĐT và `CUST-001` trong `main.py`.
2. **Chặn ghi trùng**: trong `set_fact`, nếu giá trị giống → chỉ cập nhật thời điểm xác nhận (`UPDATE`), không `INSERT`; thêm `CREATE UNIQUE INDEX … ON customer_profiles(customer_id, key) WHERE superseded = 0`.
3. **Episode**: thêm `UNIQUE(customer_id, session_id)` + `INSERT OR IGNORE`; sắp xếp theo `call_date` thay vì `created_at`.
4. **Đường dẫn tuyệt đối** tính từ `__file__` (cho phép ghi đè bằng biến môi trường `HARNESS_DB_PATH`); thêm `close()` + `PRAGMA wal_checkpoint(TRUNCATE)` qua `atexit`.
5. **Xóa trọn vẹn**: `delete_customer` xóa thêm `working_sessions` (theo `customer_id`) và `identity_links` trỏ tới khách; ghi nhật ký xóa không chứa PII.
6. **Giao dịch theo lượt**: gom các lệnh ghi của một lượt vào `with conn:`; lỗi ghi phải nổi lên trạng thái (cờ `persistence_degraded` hiển thị trên UI), không chỉ log.

**D-P1 — chuẩn hóa schema v2 (1 tuần):**
1. Thêm bảng `customers` làm gốc + `customer_identities` (phone/zalo/fb đã băm, cờ `shared` cho SĐT dùng chung) → một khách một mã, hết phân mảnh.
2. Tách `product_interests` (nhiều sản phẩm/khách, vai trò `main/accessory/gift`, trạng thái `advised/ordered/rejected`) và `order_refs` (mã đơn + hệ nguồn) khỏi profile key–value.
3. `profile_facts` có `status`, `valid_from`/`expires_at` theo **ngày nghiệp vụ**, `source_call_id`, `source_turn`, `superseded_by` là khóa ngoại; `get_active_facts` lọc `expires_at`.
4. Bảng `memory_writes` (audit) → xuất thẳng ra field `memory_writes` của trace BTC (phục vụ `memory_checks`).
5. `PRAGMA foreign_keys = ON`, `ON DELETE CASCADE`, migration theo `user_version`, index `(customer_id, call_date)`.
6. Đọc **theo khách** (lazy, truy vấn theo `customer_id`) thay vì nạp cả DB.
7. Đưa DB vào kiểm thử: một bộ test pytest chạy `enable_persistence=True` trên DB tạm, kiểm tra supersede/TTL/xóa/khởi động lại.

**D-P2 — vận hành thật:** PostgreSQL (+ pgvector cho KB), mã hóa cột PII, row-level security theo tenant, job hết hạn/dọn dữ liệu theo chính sách lưu trữ, backup định kỳ, Redis cho working memory.

### 10.7. Schema v2 đề xuất

```mermaid
erDiagram
    customers ||--o{ customer_identities : "định danh"
    customers ||--o{ calls : "cuộc gọi (episodic)"
    customers ||--o{ profile_facts : "fact bền vững"
    customers ||--o{ product_interests : "quan tâm"
    customers ||--o{ order_refs : "đơn hàng"
    customers ||--o{ working_sessions : "phiên"
    customers ||--o{ memory_writes : "audit"
    calls ||--o{ profile_facts : "nguồn"
    calls ||--o{ product_interests : "báo giá trong"
    calls ||--o| working_sessions : "phiên của"
    customers {
        TEXT customer_id PK
        TEXT crm_id UK
        TEXT display_name
        TEXT honorific
        TEXT deleted_at
    }
    customer_identities {
        TEXT identity_type PK "phone | zalo_id | fb_id"
        TEXT identity_hash PK "SHA-256 + salt"
        TEXT customer_id FK
        INTEGER shared "SĐT dùng chung"
        INTEGER verified
    }
    calls {
        TEXT call_id PK
        TEXT customer_id FK
        TEXT channel
        TEXT call_date "ngày nghiệp vụ"
        TEXT outcome
        TEXT blocker
        TEXT summary "đã mask PII"
    }
    profile_facts {
        INTEGER fact_id PK
        TEXT customer_id FK
        TEXT fact_key
        TEXT value_json
        TEXT status "active | superseded | expired"
        TEXT valid_from
        TEXT expires_at
        INTEGER superseded_by FK
        TEXT source_call_id FK
        INTEGER source_turn
    }
    product_interests {
        TEXT customer_id FK
        TEXT sku
        TEXT variant_sku
        INTEGER price_quoted_vnd
        TEXT promo_code
        TEXT role "main | accessory | gift"
        TEXT status "advised | ordered | rejected"
        TEXT source_call_id FK
    }
    order_refs {
        TEXT order_id PK
        TEXT customer_id FK
        TEXT source_system
        TEXT status
    }
    working_sessions {
        TEXT session_id PK
        TEXT customer_id FK
        TEXT call_id FK
        TEXT state_json
        TEXT expires_at
    }
    memory_writes {
        INTEGER write_id PK
        TEXT customer_id FK
        TEXT call_id
        INTEGER turn
        TEXT op "set | supersede | expire | delete"
        TEXT fact_key
        TEXT value_json
    }
```

Ràng buộc then chốt (SQLite, chuyển sang PostgreSQL gần như nguyên vẹn):

```sql
PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;
CREATE UNIQUE INDEX uq_active_fact ON profile_facts(customer_id, fact_key) WHERE status = 'active';
CREATE UNIQUE INDEX uq_identity ON customer_identities(identity_type, identity_hash) WHERE shared = 0;
CREATE INDEX idx_calls_customer_date ON calls(customer_id, call_date);
CREATE INDEX idx_interest_customer ON product_interests(customer_id, status);
-- Xóa 1 khách = DELETE FROM customers WHERE customer_id = ?  (CASCADE sang mọi bảng con)
```

### 10.8. Lệnh kiểm tra lại (chỉ đọc)

```bash
python -c "import sqlite3;c=sqlite3.connect('file:data/harness_memory.db?mode=ro',uri=True);print(c.execute('select count(*), count(distinct customer_id||key) from customer_profiles where superseded=0').fetchone())"
```

```bash
python -c "import sqlite3;c=sqlite3.connect('file:data/harness_memory.db?mode=ro',uri=True);print(c.execute('select customer_id, session_id, count(*) from episodic_records group by 1,2').fetchall())"
```

---

## Phụ lục A — Lệnh tái lập kiểm tra

```bash
cd Code
# 1) Chấm lại trace LLM có sẵn (không tốn API)
python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/public_sample --trace runs/full.jsonl --baseline runs/baseline.jsonl --out runs/report_recheck.json
```

```bash
# 2) Chạy nhánh rule-based (không LLM, không tốn API) — PowerShell: $env:OPENAI_API_KEY=""
OPENAI_API_KEY="" python run_eval.py
```

> Lệnh 2 **ghi đè** `runs/full.jsonl`, `runs/baseline.jsonl`, `runs/report.json`. Bản kiểm tra này đã chạy tương đương bằng script riêng ghi ra thư mục tạm để không đụng `runs/`.

## Phụ lục B — Kết quả kiểm thử đơn vị đã chạy

| Nhóm | Ca kiểm | Kết quả |
|---|---|---|
| Normalizer | `"hai trăm bốn chín k"` | `249.000` ✔ |
| | `"bốn triệu tám trăm chín mươi"` | `4.890.000` ✔ |
| | `"249k"` / `"5tr"` | `249000` / `5000000` (không định dạng) ◐ |
| | `"phòng 25m2 nhà có bé nhỏ"` | entity `room_area_m2=25`, `has_children=True` ✔ |
| | `"sai z eo màu đen"` / `"xiao mi 4 pro"` | `size L màu đen` / `Xiaomi 4 pro` ✔ |
| | `"sp nay co ship cod k a"` | `… COD nghìn anh` ✖ |
| | `"chị nói sai rồi em"` | `chị nói size rồi em` ✖ |
| | `"ba triệu chín trăm nghìn"` | không đổi ✖ |
| | CCCD/STK trong câu | không mask ở `normalized_text` ✖ |
| Guardrail | "đã lên đơn" không gọi tool / có gọi tool | chặn ✔ / cho qua ✔ |
| | "giá máy là 3.900.000đ" (không tool) | cho qua ✖ |
| | "giá vốn khoảng 3.2 triệu" | cho qua ✖ |
| | "quy định nội bộ về đổi trả 7 ngày" | chặn nhầm ✖ |
| | "em là nhân viên thật 100%" | cho qua ✖ |
| | CCCD 12 số trong lời agent | mask ✔ |
| Identity | Zalo ID / FB ID của C001 | tìm ra `C001` ✔ |
| | SĐT chung C034/C035 | `ambiguous=True` ✔, brief `customer_id=AMBIGUOUS` ◐ |
| | Số lạ | `CUST-ANON-…` ổn định ✔; brief chào "chị Hoa" ✖ |
| Memory | `ttl_days=0` | fact vẫn active ✖ |
| | đổi màu đen → trắng | chỉ còn "trắng" active ✔; lịch sử in-memory mất ◐ |
| Baseline | Brief call_2 sau 1 lượt call_1 | còn `product_advised` ✖ |
| Latency (không LLM) | Call Brief / lượt fallback | 0.05 ms / 0.21 ms |

---

## 11. Nhật ký thực hiện P0 (bắt đầu 2026-10-21)

> Mỗi bước ghi: **đã làm**, **cách kiểm chứng**, **chưa làm / còn tồn tại**. Mã lỗi theo § 8, § 10 và danh sách lỗi mới N1–N15 (kiểm tra 2026-10-20). Python dùng để chạy & kiểm thử: conda env `nlp_env` (`C:\Users\GIGA\anaconda3\envs\nlp_env\python.exe`, Python 3.12, có scikit-learn) — lệnh `python` mặc định (3.14) **không** có scikit-learn.

### 11.0. Ghi nhận thay đổi từ BTC (2026-10-20)

`BTC-Data-Vong1-TEAMS/eval/reference_eval.py` được BTC cập nhật (19:56 ngày 2026-10-20, so sánh với bản trong `../Code.rar`):
- `args_match` chấp nhận `order_id` là **mã do `order.create` trả về ở cuộc gọi trước của cùng kịch bản** (`created_order_ids`, "giải đáp câu 10"). → Vấn đề mã đơn SAMPLE-03 (`OD682761` không sinh được) **đã được BTC giải quyết**: dùng mã thật là đúng. Lưu ý: trace phải giữ `tool_calls[].result.order_id` của `order.create`.
- ASR: Entity Accuracy chấp nhận danh sách giá trị và thêm bản chấm theo từng lượt (`entity_accuracy_per_turn`, cần `turns[].idx` trong `hypotheses.json`).
- Chấm lại trace cũ 2026-10-11 bằng script mới: TSR **full 85.7% / baseline 100%** (trước đây 71.4% / 85.7%); RQR, CCR, HR không đổi.

### 11.1. Bước 0 — An toàn & sao lưu ✅

| Hạng mục | Kết quả |
|---|---|
| Sao lưu | `Code/backup_2026-10-21/` chứa bản sao `src/`, `scripts/`, các entrypoint `.py`, `PIPELINE.md`, `CHECKING.md`, `requirements.txt`, `data/` (DB + WAL), `runs/` — điểm khôi phục duy nhất vì thư mục không phải git repo |
| `.env.example` | Tạo mới, liệt kê biến (không chứa giá trị bí mật) gồm cả biến mới `LLM_TEMPERATURE`, `LLM_SEED`, `MEMORY_EXTRACTOR_LLM`, `HARNESS_DB_PATH` |
| `.gitignore` | Tạo mới: chặn `.env`, DB, WAL, `backup_*/`, trace demo/UI, `__pycache__` |
| `../Code.rar` | **Xác nhận có chứa `Code\.env`** (key thật) cùng `data/harness_memory.db*` và `runs/*.jsonl` (N14) |

**Ghi chú (cập nhật 2026-10-21):** file chưa được gửi cho ai nên **không cần xoay key**. Khi đóng gói nộp bài: loại `.env` và `backup_2026-10-21/` — dùng `scripts/package_submission.py` (xem § 11.6). `Code.rar` cũ ở thư mục cha vẫn chứa `.env`; đừng dùng nó để nộp.

### 11.2. Điều chỉnh kế hoạch đã áp dụng (2026-10-21, sau khi rà soát)

1. **SAMPLE-03 không cần hỏi BTC** — xem § 11.0. Runner giữ mã đơn thật; trace giữ `tool_calls[].result.order_id`.
2. **Bộ trích bộ nhớ LLM (bước 9) sẽ chạy 1 lần/cuộc gọi** (cùng lúc ghi episode), không chạy mỗi lượt — để không tăng số lần gọi LLM mỗi lượt (NV4). Regex cho slot dễ, LLM chỉ cho `blocker`/ngân sách/giá đối thủ.
3. **Không đo giữa chừng:** đã bỏ nạp đáp án (B3) nhưng chưa có bộ trích bộ nhớ (bước 9) nên CCR của `full` tạm thấp; chỉ đo ở bước 15 giai đoạn 1 sau khi xong 0–10.
4. **Bước 7:** SĐT sẽ được thay bằng token `CURRENT_CUSTOMER` trước khi vào LLM và gateway thay lại SĐT thật khi chạy tool (test `test_phone_token_substituted`). Bước 4/6 cũng sửa gateway/orchestrator → làm tuần tự.

### 11.3. Bước 1 — Bộ test offline ✅ (phần hạ tầng)

| Hạng mục | Kết quả |
|---|---|
| Test | `tests/` dùng `unittest` (không cần cài thêm pytest): `python -m unittest discover -s tests -t .` — không gọi OpenAI, không ghi `runs/`, `data/` |
| Môi trường (N12) | `src/env_check.py` + `vector_rag.py`: thiếu scikit-learn thì log mức ERROR/WARNING rõ ràng thay vì âm thầm rơi về so khớp chuỗi; `run_eval.py` in cảnh báo lúc khởi động |
| Số test | **63** (gồm 5 test LLMClient + latency mới ở bước 2). Hiện **27 xanh / 36 đỏ**; các test đỏ là bằng chứng lỗi chưa sửa của bước 4–10 (guardrail, normalizer, identity, bộ nhớ/DB, idempotency, extractor) và sẽ xanh dần |

**Chưa làm:** test cho tool `product.shortlist`/policy router (thuộc P1); chưa có test kết nối OpenAI thật (cố ý, tránh tốn credit).

### 11.4. Bước 2 — Trace đúng thực tế ✅ (B1, B8, N3)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| Latency thật | Bỏ `random.randint(350,750)`, hằng `380`, `call_brief_ms=115`, `ttft=total//2`. `src/tracing/tracer.py::measure_latency` quy đổi mốc `perf_counter` đo ở ranh giới harness (nhận lượt → có câu trả lời). Không còn giá trị mặc định nào | Chạy offline 39 lượt: total p50 **0 ms**, p95 **55 ms** (trước đó giả 282/364/564/729 ms); `test_latency_not_fake` |
| TTFT | `LLMClient` dùng `stream=True` (+ `include_usage`), gom `tool_calls` từ delta; TTFT = thời gian chuẩn bị trước LLM + tới token text đầu tiên của vòng trả lời cuối. Nhánh không-LLM: TTFT = Total (hướng dẫn BTC quy tắc 7) | `tests/test_llm_client.py` (client OpenAI **giả**) |
| `call_brief_latency_ms` | Đo từ lúc nhận diện khách tới khi Brief sẵn sàng; chỉ ghi ở turn 1 của call_2/call_3, còn lại `null` | `test_call_brief_latency_field`; field `latency.call_brief_ms` sai chỗ đã bỏ |
| `memory_writes` | `MemoryService.begin_turn/drain_writes`: mỗi thay đổi profile ghi `{customer_id,key,value,op: set/supersede,source:"call_2#turn1"}`; ghi trùng giá trị thì không log; chuỗi 9–14 chữ số bị che (SĐT 10 số giữ nguyên) | `test_write_log_ops` |
| `customer_input_mode` | `clean` / `asr_transcript` / `chat_teencode` lấy từ `input_mode` của kịch bản (hoặc `asr_transcript` nếu có `customer_turns_asr`) | `test_trace_has_memory_writes_and_mode` |
| Tham số tool thật (N3) | `tool_executor` trả `(kết quả, tham số đã chạy)`: trace ghi tham số **sau khi tiêm `on` và sửa SKU**, không phải tham số LLM gửi | `test_executed_args_logged_and_on_injected`; trace mẫu có `on` trong mọi tool call |
| Cấu hình ổn định | `LLM_TEMPERATURE` (mặc định 0) và `LLM_SEED` được truyền vào API; `llm_calls` (số vòng gọi API/lượt) được ghi vào `llm_cost` — nền đo NV4 | |

**Chưa làm / hạn chế (nói rõ để không hiểu nhầm):**
- **Chưa có số đo latency của LLM thật** — chưa gọi API; đường stream mới được kiểm bằng client giả. Phải xác nhận lại ở bước 15 giai đoạn 1.
- TTFT là của *mô hình*; guardrail chạy sau khi sinh xong nên nếu UI stream thật cho khách thì phải đệm token tới khi guardrail duyệt.
- UI (`ui_app.py`) vẫn dùng `call_name="call_1"` và đếm lượt sai (thuộc bước 17); `trace_file` mặc định của pipeline đã đổi sang `runs/ui_session.jsonl`.
- `memory_writes` mới ghi **profile**; ghi episode/working vào log thuộc bước 9.

### 11.5. Bước 3 — Runner & CLI chuẩn BTC ✅ (B2, B3, B5, B10, A9, N8, N9)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| CLI chuẩn BTC (B5) | `python run_eval.py --scenarios <dir> --config full\|baseline_no_memory --out trace.jsonl [--seed N] [--repeats N] [--only ID...]`. Không tham số = chạy cả `full` + `baseline` vào `runs/` rồi gọi `reference_eval.py`. `--help` chạy được kể cả thiếu thư viện | `test_cli_has_btc_flags`; chạy offline 7 kịch bản thành công |
| Baseline stateless thật (B2) | Bộ nhớ **mới ở mỗi call** (không còn xóa theo SĐT/`CUST-001` rồi để profile rò) | `test_baseline_has_no_cross_call_memory`; CCR offline baseline **28.6%** ≠ full 33.3% (trước đây hai cấu hình bằng nhau) |
| Bỏ bơm đáp án (B3) | `full` chỉ dùng bộ nhớ hệ thống tự ghi. Cấu hình mới `full_oracle` (nạp `facts_established`) chỉ để tham chiếu trần điểm; trace vẫn ghi `config:"full"` cho đúng schema, `run_id` mang hậu tố `FULL_ORACLE` | `test_full_does_not_seed_answers` |
| Đọc đúng kịch bản | `channel`, `channel_identity`, `input_mode`, `seed_history`, `call_date/days_later`; ánh xạ `InputChannel.from_scenario` (`chat_fanpage`→FANPAGE, `zalo_oa`→ZALO) | `test_scenario_channel_mapping` |
| Mock độc lập (N8) | `reset_mock_state()` xóa `_ORDERS/_TICKETS/_CALLBACKS/_ONCE_USED` trước mỗi kịch bản → mã đơn luôn bắt đầu `OD600001`, không phụ thuộc thứ tự chạy | trace SAMPLE-03: call_1 ra `OD600001` |
| `main.py` (B10) | Ghi `runs/demo.jsonl`, không đụng `runs/full.jsonl` | `.gitignore` đã chặn `runs/demo.jsonl` |
| Seed/lặp | `--seed` truyền vào LLM và `run_id`; `--repeats N` ghi `*.r1…rN.jsonl` để báo mean ± std ở bước 15 | |

Kết quả chạy offline (không LLM, 7 kịch bản, 39 lượt) sau bước 3 — **không phải số liệu để nộp**, chỉ kiểm tra hạ tầng: RQR N/A · CCR 28.6% (baseline) / 33.3% (full) · TSR 14.3% / 14.3% · HR giá&KM 85.7% / 85.7% · latency total p95 55 ms. `runs/full.jsonl`, `runs/baseline.jsonl` (trace LLM 2026-10-11) **không bị thay đổi**.

**Chưa làm / còn tồn tại:**
- **SAMPLE-04 / SC-GEN-06 vẫn bị tách thành 2 khách** vì runner giờ dùng kênh thật (Fanpage → Hotline) mà bước 8 (nối FB↔SĐT, N7) chưa làm → test `test_fanpage_linked_to_phone` đỏ. Đây là hệ quả dự kiến, sẽ xử lý ở cụm 4–8.
- `seed_history`: BTC chưa chốt định dạng; runner nhận `list[dict]` theo trường của `EpisodeRecord` (+ `facts`). Bộ public không có kịch bản nào dùng, chưa kiểm chứng với dữ liệu thật. TTL khi đọc thuộc bước 9.
- `full` chưa có episode tự ghi và chưa có bộ trích bộ nhớ → CCR/TSR của `full` tạm thấp hơn trước (bước 9).
- Chưa chạy bằng LLM thật (cố ý, tiết kiệm credit); chưa có báo cáo mean ± std (bước 15).
- Khi đóng gói nộp bài: dùng `scripts/package_submission.py` (loại `.env` và `backup_2026-10-21/`, quét chuỗi giống API key) — xem § 11.6.

### 11.6. Hotfix N15, bước 2b, gói nộp, xác minh model judge (2026-10-21)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| **HOTFIX N15** ✅ | `strip_internal()` trong `src/tools/mcp_gateway.py` loại đệ quy mọi field bắt đầu bằng `_` (vd `_internal_price_floor_vnd`) khỏi kết quả tool **trong gateway** → mọi đường tới LLM, trace và audit log đều sạch (cả nhánh rule-based) | `tests/test_llm_client.py::StripInternalTest` (3 test) + `test_guardrail.GatewaySanitizeTest` xanh |
| **Bước 2b** ✅ | `src/llm/model_profiles.py` + `LLMClient`: bỏ `temperature` với model suy luận (`gpt-6-luna`, o-series, gpt-5*), dùng `max_completion_tokens`, **tự học** tham số bị API từ chối rồi thử lại (tối đa 4 lần), ghi `reasoning_tokens` vào `llm_cost`; `assert_distinct_judge()` ném `JudgeModelConflict` khi judge trùng model agent | `MultiProviderTest` (9 test, client giả, không gọi mạng) |
| **Gói nộp** ✅ | `scripts/package_submission.py`: nén `Code/` đã loại `.env`, `.env.*` (giữ `.env.example`), `backup_*/`, `__pycache__`, `data/*.db*` (mặc định), `runs/demo.jsonl`, `runs/ui_session.jsonl`; quét **trước và sau khi nén** bằng mẫu `sk-…`, `KEY=<giá trị dài>`, AWS key, private key và **giá trị thật đọc từ `.env`**; phát hiện thì không tạo gói/xóa gói, thoát mã 1; không bao giờ in giá trị khóa | `tests/test_package_submission.py` (7 test); chạy thật trên `Code/` → 132 file, 1.1 MB, không có `.env`/`backup_*` |
| **Xác minh model judge** ✅ (một phần) | Đã gọi **1 lần** `GET /v1/models` (miễn phí, HTTP 200, 129 model): `gpt-6-luna` **có trong danh sách** của tài khoản (kèm `gpt-5.6-luna`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6.1-sol`) | Danh sách chỉ cho biết model tồn tại/được cấp quyền; **chưa biết** tham số được hỗ trợ và giá → `cost_tracker.py` chưa có giá `gpt-6-luna` (đang dùng giá mặc định + cảnh báo). Chưa gọi chat completion nào |

Số test sau hotfix: **82 test — 47 xanh, 35 đỏ** (trước đó 63 — 27 xanh, 36 đỏ). Đỏ còn lại thuộc bước 4–10: guardrail 10, bộ nhớ/DB 8, normalizer 6, identity 5, orchestrator 5, extractor 1.


### 11.7. Cụm 4–8 (2026-10-21) — tổng quan

Số test sau cụm 4–8: **124 test — 115 xanh, 9 đỏ**. 9 test đỏ còn lại **đều thuộc bước 9–10** (bộ nhớ/DB 8, extractor 1). Chạy: `python -m unittest discover -s tests -t .` (conda env `nlp_env`). Chưa gọi OpenAI lần nào trong cụm này; nhánh LLM được kiểm bằng LLM giả (`FakeLLM`, `RecordingLLM`, `ExplodingLLM`), **chưa kiểm với API thật**.

### 11.8. Bước 4 — Tool ghi an toàn ✅ (A2, A10, N4, N6)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| Chống gọi lặp | `orchestrator._write_key`: `order.update` theo `(đơn, hành động, biến thể)`, `order.create` theo `(SĐT, sku, qty)`, `schedule.callback`, `handoff.transfer`; cùng yêu cầu trong cùng cuộc gọi trả lại **kết quả cũ** (gắn `already_done`), không chạy lại tool. Chỉ cache khi thành công. Cuộc gọi khác ngày = phiên mới (đổi lần 2 ở cuộc gọi khác vẫn tính phí đúng) | `test_order_update_idempotent_within_call`, `test_no_duplicate_order_create_within_call`, `test_dedup_returns_original_result_flagged`, `test_new_call_new_day_allows_second_exchange_with_fee` |
| Vượt số vòng / lỗi giữa chừng | `LLMRoundLimit`; tool ĐÃ chạy luôn nằm trong trace; nếu đã có tool ghi chạy hoặc vượt vòng thì **không chạy nhánh rule-based** (không tạo đơn thứ hai), trả câu an toàn chỉ nói đúng điều tool đã làm (`_safe_summary`); lỗi trước khi có tool ghi vẫn rơi về rule-based | `test_round_limit_after_order_create_...`, `test_error_after_write_...`, `test_error_before_any_write_...` |
| Bộ nhớ cuộc gọi lưu kết quả tool | Sau mỗi lượt lưu **tóm tắt tool thật** (mã đơn, phí, giá…) vào lịch sử cho LLM, và lưu **đúng câu khách đã nghe** (sau guardrail) | `test_tool_summary_saved_in_working_memory_for_next_turn` |
| Giới hạn prompt | Lịch sử cắt theo ngân sách ký tự (12.000); kết quả tool gửi LLM cắt ở 6.000 ký tự (trace giữ nguyên bản) | `test_history_trimmed_to_budget` |
| `order.update` nhận `on` | Orchestrator tiêm ngày cuộc gọi cho cả `order.update` (kiểm tồn kho biến thể mới đúng ngày) | |

**Chưa làm / hạn chế:** `LLM_MAX_TOOL_CHARS`/`MAX_HISTORY_CHARS` là ngưỡng ước lượng, chưa tinh chỉnh bằng số đo thật. Cache ghi chỉ sống trong process (restart giữa cuộc gọi sẽ mất) — chấp nhận ở M1.

### 11.9. Bước 5 — Ghi nhớ sản phẩm đúng ✅ (A1, D3)

`product_advised` luôn là **SKU cha** của sản phẩm chính: loại quà tặng (`gift_sku` trong KM) và phụ kiện (danh mục `phu-kien`, đọc từ catalog); nếu còn nhiều sản phẩm thì ưu tiên sản phẩm được nhắc tên trong lời agent, nếu không thì báo giá cuối; đơn tạo thành công có ưu tiên cao nhất và ghi thêm `variant_sku`/`size`/`color`; `exchange_product` cập nhật sản phẩm cha. Giá và mã KM lấy từ đúng báo giá của sản phẩm chính. Test: `test_gift_quote_does_not_override_product` (SAMPLE-01), `test_variant_order_sets_parent_and_variant`.
**Chưa làm:** tool `memory.propose` (LLM tự xác nhận sản phẩm) — chưa cần vì quy tắc trên đã đủ cho bộ test hiện có.

### 11.10. Bước 6 — Guardrail ✅ (A7, A8, V5, N1, N2, N15)

| Hạng mục | Kết quả |
|---|---|
| "mã đơn" không còn là cụm báo đã lên đơn (N1) | Câu hỏi/nhắc "mã đơn OD…" không bị thay |
| Không thay câu khi tool đã chạy | Tính cả tool đã chạy ở **các lượt trước trong cùng cuộc gọi** (`call_tool_calls`) |
| Đối chiếu số tiền | Mọi số tiền trong lời agent (5.200.000đ, 5 triệu 2, 500k…) phải có trong kết quả tool của cuộc gọi (kể cả số trong chunk chính sách), hoặc là tổng/hiệu/bội số lượng của chúng, hoặc số khách/Call Brief đã nêu; "khoảng/tầm/gần" cho sai số 6%. Sai → `hallucination_price_mismatch` (`src/harness/money.py`) |
| Phí | Nói "không mất phí" khi `order.update` báo `fee_vnd`/`extra_payment_vnd` > 0 (kể cả ở lượt trước) → thay bằng câu đính chính đúng số tiền (`hallucination_fee_mismatch`) |
| Giá vốn | Chặn khi có "giá vốn/giá nhập/giá sàn/biên lợi nhuận" **kèm số**; lời từ chối không số được qua; "quy định nội bộ" không bị chặn nhầm |
| "Em là người thật" | Chặn, trả câu "em là trợ lý AI…" (`claims_human`) |
| PII | Chỉ che CCCD (12 số) và STK (9–14 số); **SĐT 10 số bắt đầu 0 được giữ** |
| Prompt | Thêm luật: là trợ lý AI, không bình luận đối thủ, quy trình xóa dữ liệu (ghi nhận + chuyển bộ phận, không hứa thời hạn), nói đúng phí, gọi `order.*` đúng 1 lần/cuộc |
| N15 | Đã xong ở hotfix (§ 11.6) |

Test: toàn bộ `tests/test_guardrail.py` (15) + `GuardrailInFlowTest` (4) xanh.
**Hạn chế:** quy tắc "mọi số tiền phải có căn cứ" có thể chặn nhầm một phép tính phức tạp của LLM (ngoài tổng/hiệu/bội số lượng) — lúc đó khách nghe câu "xin phép kiểm tra lại bảng giá" (an toàn nhưng làm mất 1 lượt). Cần đo tỉ lệ này ở bước 15. Chưa có luật chặn bình luận đối thủ ở tầng guardrail (mới nằm trong prompt).

### 11.11. Bước 7 — Normalizer và PII ✅ (V1–V4, N13)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| Teencode (V1, V2) | Bỏ khóa `"k"` trùng; `k` đứng riêng = "không", `5k/249k` = nghìn; bỏ `sai`, `ng`, `tam`; `a/c/e` chỉ đổi theo ngữ cảnh ("c có hỏi" → "chị có hỏi", "k a" → "không ạ"; không đổi "lọc y") | `test_teencode_k_means_khong`, `test_sai_is_not_size`, `test_pronoun_context` |
| ITN tổng quát (V3) | Số tiền đọc bằng chữ (triệu/nghìn/trăm/mươi/mười/lẻ/rưỡi, cách nói tắt "hai trăm bốn chín k"), `5tr`, `5tr2`, `2,5 triệu`, `1521k` → `1.521.000`; "ba mươi lăm mét vuông" → 35; chỉ đổi khi có từ chỉ bậc/đơn vị (không đổi "năm nay", "một cái") | `test_itn_*`, `ITNExtraTest` |
| SĐT đọc từng chữ số, ngày giờ tương đối | "không chín chín…" → `0994893949`; "ngày mai 3 giờ chiều" → gợi ý `{date, time}` (đưa vào ngữ cảnh LLM) | `test_spoken_phone`, `test_relative_date_hint` |
| PII → token (N13) | `src/privacy/pii_vault.py`. `CURRENT_CUSTOMER` **chỉ** cho số người gọi; số khác `<PHONE_n>`; địa chỉ `<ADDR_n>`; CCCD/STK `<ID_n>` (do normalizer gán, **không bao giờ mở**). Bảng token chỉ trong bộ nhớ process (pickle/copy/json bị chặn, `repr` không lộ giá trị). Chỉ mở token cho (tool, field) trong danh sách cho phép; kết quả tool che lại trước khi trả LLM; lời agent mở token trước khi nói với khách (trừ `<ID_n>`). Prompt LLM chỉ chứa whitelist fact, không còn SĐT thô/`profile_facts` đầy đủ | `tests/test_pii_vault.py` (14 test, gồm ca **giao cho người khác, số khác**: LLM không thấy số/địa chỉ/CCCD thật; tool nhận giá trị thật; `<ID_n>` không bao giờ được mở) |
| Trace | Args giữ SĐT (BTC cho phép SĐT 10 số), địa chỉ thay bằng token; kết quả tool trong trace đã che | `test_other_phone_and_address_masked_for_llm_but_real_for_tool` |

**Chưa làm / hạn chế:**
- Dò địa chỉ là **heuristic** (từ khóa "giao về/địa chỉ/nhà … ở" + dấu hiệu số nhà/đơn vị hành chính, hoặc "số 12 ngõ 5…"); địa chỉ viết không có dấu hiệu nào có thể lọt qua. Cần kiểm trên hội thoại thật.
- ITN chữ số không dấu chỉ nhận một số từ không gây nhầm (không nhận "sau/nam/tam"); "năm triệu" phải có dấu.
- Gợi ý ngày/giờ hẹn gọi lại mới là *gợi ý* cho LLM, chưa tự đặt lịch.
- `<ID_n>` mới gán theo từng lượt (không đánh số nhất quán giữa các lượt) — chấp nhận vì không bao giờ mở.
- Chưa kiểm với API thật (xem § 11.7).

### 11.12. Bước 8 — Định danh đa kênh ✅ (A3, A6, A11, N7)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| Nối kênh ↔ SĐT (N7) | Khách chat Fanpage/Zalo đọc SĐT → tra CRM theo SĐT, **nối** FB/Zalo id với mã đó (`IdentityLinkMap.link_contact`) và **gộp bộ nhớ** mã tạm vào mã chính (`MemoryService.merge_customer`; mã đã có thì thắng; mã tạm bị xóa). Khách chưa có trong CRM: mã ổn định theo SĐT | `test_fanpage_linked_to_phone` (SAMPLE-04), `test_anonymous_phone_linked_from_facebook_is_stable_across_channels`; chạy offline: SAMPLE-04 call_2 ra `C017` và mang theo sản phẩm/giá đã báo ở Fanpage |
| Tên kênh | `InputChannel.from_scenario`; kênh Zalo với contact là SĐT (SAMPLE-06) vẫn tra theo SĐT | `test_zalo_channel_with_phone_contact` |
| SĐT dùng chung (A6) | Không dùng chung `AMBIGUOUS`: brief có mã riêng `AMB-<băm SĐT>` (không lộ SĐT); khách nêu tên khớp đúng 1 ứng viên (so khớp không dấu) → xác định và giữ trong phiên; tên sai → vẫn mơ hồ | `test_shared_phone_*` |
| Xưng hô (A3, A11) | Bỏ mặc định "Hoa"/"chị": tên/xưng hô lấy từ bộ nhớ → CRM → lời khách tự xưng ("anh muốn…") → mặc định trung tính "anh/chị"; câu mở đầu không còn "anh nhà" cứng; `CallBrief.addressing()` | `test_unknown_number_not_greeted_as_hoa`, `test_honorific_from_crm` (SAMPLE-03 "anh Khoa"), `test_self_honorific_...` |
| Lịch sử kênh | Mỗi lượt ghi fact `channels_seen`; `CallBrief.channels_seen` và prompt LLM có "kênh khách đã liên hệ" (nền cho yêu cầu "nhận biết kênh đã hỏi") | `test_channels_seen_in_brief_after_fanpage_then_hotline` → `["fanpage","hotline"]` |

**Chưa làm / hạn chế:**
- SĐT dùng chung mà khách không nêu tên: vẫn ở trạng thái mơ hồ (brief yêu cầu xác nhận tên); chưa có cách xác minh thứ hai.
- Liên kết FB↔SĐT lưu trong `identity_links` (SQLite khi bật persistence) nhưng **SĐT của liên kết chỉ nhớ trong process** — restart giữa chừng thì lượt Fanpage sau đó biết mã khách nhưng chưa biết SĐT người gọi (LLM thấy "SĐT người gọi: chưa xác định").
- Tên/xưng hô CRM được ghi vào bộ nhớ như fact (`customer_name`, `honorific`) — làm `memory_writes` dài hơn; cần xem lại khi làm bước 9 (provenance).
- Chưa tự ghi episode (bước 9) nên câu mở đầu "hôm … bên em có tư vấn…" chỉ xuất hiện khi có episode; `full` hiện mang thông tin qua profile fact.

### 11.13. Việc tồn đọng sau cụm 4–8

- 9 test đỏ: bước 9 (bộ nhớ/DB: TTL, `get_history`, `close()`, UNIQUE, episode có thứ tự, xóa trọn vẹn, đường dẫn DB tuyệt đối) và bước 10 (`src/harness/extractor.py` chưa tồn tại).
- Chưa đo bằng LLM thật; số offline (RQR N/A · CCR 28.6%/33.3% · TSR 14.3%/14.3%) chỉ là kiểm tra hạ tầng, **không dùng đánh giá** (xem § 11.2).


### 11.14. Cụm 9–10 (2026-10-21) — tổng quan và kết quả test

Lệnh: `python -m unittest discover -s tests -t .` (conda env `nlp_env`) → **231 test, 0 lỗi, 0 đỏ** (chạy 3 lần liên tiếp đều xanh). Trước cụm này: 124 test, 115 xanh, 9 đỏ.

| File test | Số test | Ghi chú |
|---|---:|---|
| `test_cluster_9_10.py` | 70 | mới — bước 9, 10 |
| `test_cluster_4_8.py` | 28 | |
| `test_extractor.py` | **28** | trước đây **1 lỗi ImportError** (module chưa có); nay chạy 11 test gốc + **17 test hồi quy mới** |
| `test_llm_client.py` | 27 | +5 `complete_json`, +5 giá/`reasoning_effort` |
| `test_guardrail.py` | 15 | |
| `test_pii_vault.py` | 14 | |
| `test_normalizer.py` | 11 | |
| `test_memory.py` | 10 | cả 10 xanh (trước: 8 đỏ) |
| `test_identity_brief.py` | 7 | |
| `test_package_submission.py` | 7 | |
| `test_orchestrator.py` | 6 | |
| `test_runner.py` | 6 | |
| `test_environment.py` | 2 | |
| **Tổng** | **231** | |

**Ghi chú xử lý yêu cầu duyệt:**
- **Ưu tiên `test_delete_customer_everything`**: xanh; thêm `DeleteEverythingTest` kiểm **từng bảng** (`customer_profiles` kể cả lịch sử phiên bản, `episodic_records`, `working_sessions`, `identity_links`), kiểm khách khác (`C10`) không bị xóa lây khi xóa `C1`, nội dung hội thoại không còn trong file `.db` sau khi xóa (secure_delete + checkpoint), và trạng thái RAM của orchestrator/resolver cũng bị xóa.
- **`ResourceWarning` ở `tests/test_runner.py`** (dòng 22–23): đã sửa bằng `with open`. Còn một số `ResourceWarning` đến từ `BTC-Data-Vong1-TEAMS/eval/mock_tools.py` (file của BTC, không sửa).
- Phát hiện khi làm: `test_latency_not_fake` chập chờn khi chạy cả bộ (lượt đầu khởi động nguội > 300 ms) → đổi sang so **trung vị** (< 300 ms; số giả cũ có trung vị ≥ 350). Và lỗi thật: hai lần ghi liên tiếp trên Windows có thể trùng `observed_at` (một phần khóa chính) làm mất 1 phiên bản lịch sử → thêm số thứ tự đơn điệu vào dấu thời gian (`ProfileFact`), có test 50 lần ghi liên tiếp.

### 11.15. Bước 9 — Bộ nhớ và DB ✅ (A4, A5, N5, N11, K6, D1, D2, D4–D9, D13–D15)

| Hạng mục | Đã làm | Kiểm chứng |
|---|---|---|
| **Bộ trích bộ nhớ 2 tầng** (thay nạp đáp án) | *Tầng 1 — slot dễ, regex, mỗi lượt, KHÔNG gọi LLM*: diện tích, trẻ nhỏ, ngân sách (chỉ khi có từ khóa ngân sách/dưới/tối đa — "giảm 500.000" không bị nhầm), size, màu (không dấu, thống nhất với màu parse từ SKU), hẹn gọi lại. *Tầng 2 — slot khó, LLM, 3 thời điểm* (`CallFinalizer`): `end`, `handoff` (tự chạy khi `handoff.transfer` thành công), `timeout` (`sweep_idle`/`pipeline.end_call(trigger="timeout")`). **≤ 1 lần mỗi thời điểm; sau chuyển máy thì cuối cuộc chỉ trích phần hội thoại mới; không có tin mới thì không gọi LLM**. Giá trị LLM trả về được kiểm chứng (số tiền phải xuất hiện trong lời khách), che PII, kiểm kiểu. **Baseline không chạy bộ trích** | `EasySlotsTest`, `HardSlotValidationTest`, `CallFinalizerTest` (13), `OrchestratorFinalizeTest`, `RunnerExtractionTest` — toàn bộ dùng LLM giả |
| Episode tự ghi | Mỗi thời điểm kích hoạt upsert 1 episode/cuộc gọi (dựng từ fact thật + tool đã chạy): outcome `chot_don`/`chuyen_may`/`ngat_cuoc`/`hen_goi_lai`; ghi vào `memory_writes` của trace | `test_outcomes_by_trigger_and_tools`, `test_handoff_and_end_share_one_episode` |
| TTL khi đọc (A5) | Hết hạn khi `ngày gọi ≥ observed_on + ttl_days` (`ttl_days=0` hết ngay); Call Brief và orchestrator đọc theo ngày cuộc gọi; xác nhận lại cùng giá trị thì gia hạn, không thêm dòng | `test_ttl_*`, `test_ttl_applied_to_brief` |
| `intent` (N5) | `WorkingMemoryStore.update` báo lỗi với trường lạ (trước đây `last_intent` bị bỏ qua âm thầm); orchestrator lưu `intent` | `test_orchestrator_saves_intent` |
| Xóa nhất quán (D9, N11) | `delete_customer_data` xóa profile (cả lịch sử), episode, working session, identity link (DB + RAM) và trạng thái các thành phần đã đăng ký (orchestrator, resolver) trong 1 giao dịch, rồi `wal_checkpoint` + `secure_delete` | `DeleteEverythingTest` |
| UNIQUE (D1, D5) | Index duy nhất một phần: mỗi (khách, key) chỉ 1 dòng active; episode UNIQUE (khách, session); đọc episode theo ngày gọi (không theo giờ máy) | `test_no_duplicate_active_rows`, `test_episode_unique_and_ordered`, `EpisodeTest` |
| Provenance (D7) | `source_call`, `source_turn`, **`source_channel`** (+ `observed_on` theo ngày nghiệp vụ) trong DB và trong `memory_writes` của trace; `facts_by_channel` → Call Brief ("khách đã nói/được báo gì ở kênh nào") | `ProvenanceAndTTLTest`, `test_facts_by_channel_in_brief`, `test_writes_have_channel_provenance_in_trace` |
| Đường dẫn DB tuyệt đối (D14) | `default_db_path()` (hoặc `HARNESS_DB_PATH`), không phụ thuộc thư mục hiện hành | `WorkingAndPathTest` |
| Checkpoint WAL (D8) | `close()` + tự chạy khi thoát process; chỉ cần copy `.db` | `test_data_in_main_db_after_close` |
| Giao dịch theo lượt (D13) | `begin_turn` mở, `drain_writes` chốt, `abort_turn` hủy (pipeline hủy khi lượt lỗi); có khóa luồng; lỗi ghi được đếm (`write_errors`) và log mức ERROR | `TransactionTest`, `test_failed_turn_rolls_back_db_writes_and_reraises` |
| `order_id` còn tồn tại (D4) | Call Brief kiểm `order.status` trước khi dùng; đơn không còn → bỏ khỏi brief + cảnh báo | `test_missing_order_id_is_dropped_with_warning` |
| Một khách một mã (D2) | Call Brief không còn đọc gộp theo SĐT thô | `test_facts_under_raw_phone_key_are_ignored` |
| Seed demo idempotent (D15) | `scripts/seed_demo_db.py` (chạy lại không nhân bản; `--reset`); `main.py` dùng nó, chỉ ghi dưới `C001`, ghi `runs/demo.jsonl`, kết thúc bằng `end_call` + `close` | `SeedScriptTest`; chạy `main.py` 2 lần trên DB thử: không nhân bản, không còn file `-wal` |
| Migration DB cũ (D11 một phần) | Tự nâng schema v2: thêm cột provenance, fact active trùng → superseded (không xóa), episode trùng gộp (có sao lưu `.pre_v2.bak`), `user_version=2` | `MigrationTest` (4); **thử trên BẢN SAO `data/harness_memory.db` thật**: fact active 136 → **42**, tổng dòng 173 → 173 (không mất dòng nào), episode 12 → 3, có `.pre_v2.bak`, không còn `-wal` |

**Chưa làm / hạn chế (nói rõ):**
- **LLM trích slot khó chỉ được kiểm bằng LLM giả** (và `complete_json` bằng OpenAI client giả). Chưa gọi model thật nên chưa biết chất lượng trích và định dạng JSON thật của `gpt-4o-mini`; phải kiểm ở bước 15 GĐ1.
- **DB thật của bạn (`data/harness_memory.db`) CHƯA được migrate** — mới thử trên bản sao; sẽ tự migrate (có sao lưu) lần đầu app mở DB đó. Trong DB đó vẫn còn 3 mã cũ của cùng một khách demo (`C001`, `0984726714`, `CUST-001`, mỗi mã 1 episode) — bản chất dữ liệu demo cũ (D2); chưa xóa vì là dữ liệu của bạn.
- **`main.py` giờ reset khách demo `C001` trong DB mặc định mỗi lần chạy** (để demo tái lập đúng). Muốn giữ dữ liệu `C001`, chạy bằng `HARNESS_DB_PATH` trỏ DB khác.
- `abort_turn` hủy ghi trong DB nhưng **bản in-memory không tự hoàn tác**.
- Chưa làm (ngoài phạm vi D-P0): D3 (mô hình "1 ô/khách" cho sản phẩm/đơn), D10 (working session chưa tự hết hạn/dọn), D12 (nạp cả DB vào RAM), D16 (PII lưu rõ, chưa mã hóa at-rest), phần còn lại của D11 (chưa có migration framework tổng quát).
- Cuộc gọi bị ngắt (`timeout`) cần tầng vận hành gọi `sweep_idle()`/`end_call(trigger="timeout")`; chưa có tiến trình nền tự gọi (UI/tổng đài thật ở bước 17).

### 11.16. Bước 10 — Bộ trích claims/questions ✅ (B6, B7, N10)

| Hạng mục | Đã làm |
|---|---|
| Claims từ **lời agent** (`src/harness/extractor.py`) | Tên field khớp `ground_truth_facts` BTC: `price_vnd`, `list_price_vnd`, `final_price_vnd`, `discount_vnd`, `total_vnd`, `in_stock`, `new_size_in_stock`, `restock_date`, `delivery_days`, `freeship`, `return_days`, `exchange_window_days`, `exchange_fee_vnd`, `warranty_months`, `promo_active`, `promo_<MÃ>_active`, `promo_code`, `cod_limit_vnd`, `discontinued`, `is_human`. Số tiền được gán vai trò theo kết quả tool trước, rồi theo từ khóa gần nhất; quà tặng "trị giá…", phụ kiện không thành claim; câu mâu thuẫn (vừa còn vừa hết hàng) và khoảng ("2–3 ngày") bị bỏ qua thay vì đoán. Trích từ **đúng câu khách nghe (sau guardrail)** |
| Questions | Mọi câu hỏi được đếm (kết thúc `?` hoặc đuôi nghi vấn "… không ạ"); slot 'other' khi không gán được; `confirm` khi có dấu hiệu xác nhận lại ("đúng không", "vẫn là"…), còn lại `open` |
| Cách trích | Được mô tả trong docstring đầu `src/harness/extractor.py` (yêu cầu của `trace_log.schema.json`: "nhóm tự mô tả cách trích") |

**Kiểm chứng trên lời agent THẬT của trace LLM cũ (`runs/*.jsonl`, 2026-10-11 — chạy offline, không gọi API mới):**

| | Trước (claim lấy từ kết quả tool) | Sau (claim từ lời agent) |
|---|---:|---:|
| `full`: số claim / số câu hỏi | 29 / 4 | **78 / 29** |
| `baseline`: số claim / số câu hỏi | 26 / 3 | **71 / 32** |
| claim kiểm chứng được (có trong GT) — full / baseline | — | 23 / 17 |
| trong đó sai so với GT — full / baseline | — | 3 / 3 |

Cả 6 claim "sai" đều là **lỗi thật của agent** (đã đọc từng câu): bán/báo giá nhầm màng lọc 690.000đ thay vì máy 5.200.000đ (SAMPLE-01, ×2 ở full — chính là lỗi A1 đã sửa ở bước 5), báo 5,2 triệu thay vì 5,49 triệu (SAMPLE-06), báo 1.690.000đ thay vì 1.521.000đ (SAMPLE-04), nói KM đã hết trong khi còn hiệu lực (SAMPLE-04). Quá trình này còn phát hiện và sửa **2 dương tính giả của bộ trích** (khuyến mãi "đã hết hạn" bị hiểu là hết hàng; "giảm giá 500.000đ" bị hiểu là giá bán) — hiện có test hồi quy. **Lưu ý:** tỉ lệ sai ở bảng trên tính trên trace cũ (trước các bản sửa bước 4–9), **không phải số liệu hợp lệ của hệ thống hiện tại**.

Hệ quả cho đo lường: RQR không còn "None" — chạy offline có 12 câu hỏi (mẫu số > 0); số claim kiểm chứng được tăng so với 11 trước đây.

**Chưa làm / hạn chế:** bộ trích claim dựa vào mẫu câu tiếng Việt cố định — câu diễn đạt lạ có thể không ra claim (thiếu sót thì không bị tính HR nhưng BTC có thể chấm tay 20 lượt để tìm bỏ sót); chưa trích claim về chính sách phức tạp (multi-hop), tên sản phẩm cuối (`final_product_advised`), `policy_version`.

### 11.17. Số liệu offline sau cụm 9–10 (rule-based, KHÔNG LLM — chỉ kiểm hạ tầng, không dùng đánh giá)

7 kịch bản public, 39 lượt: RQR **0.0%** (có mẫu số, trước đây N/A) · CCR baseline 28.6% / full **57.1%** (trước cụm 9: 33.3%) · TSR 14.3% / 14.3% · HR giá&KM 85.7% / 85.7% · latency total p95 83 ms. Full giờ tự có episode ở cuối mỗi cuộc gọi (13 episode / 13 cuộc) và SAMPLE-04 call_2 mang đúng sản phẩm + giá đã báo ở Fanpage. TSR/HR chưa cải thiện vì nhánh rule-based (không LLM) luôn báo `SKU-AP-Y` — **phải đo bằng LLM thật ở bước 15 GĐ1**. `runs/full.jsonl`, `runs/baseline.jsonl`, `data/harness_memory.db` không bị thay đổi.

### 11.18. Việc tiếp theo

Chờ duyệt cụm 9–10. Sau đó: **bước 15 giai đoạn 1** (7 kịch bản public × 2 cấu hình × 1 seed, LLM thật, ~2–3 nghìn VND) để biết P0 có hiệu quả hay không — trước khi sang P1 (19 MCP thật ‖ 14a ‖ 16a).


### 11.19. Chuẩn bị bước 15 giai đoạn 1 (2026-10-21)

**Hai quyết định về DB (đã duyệt):**
1. **Gộp 3 mã trùng của khách demo** — đã sao lưu trước vào `backup_2026-10-21/db_before_merge/` (`.db`, `-wal`, `-shm`), thêm bản sao tự động `data/harness_memory.db.pre_v2.bak` do migration tạo. `0984726714` và `CUST-001` (dữ liệu y hệt `C001`) được gộp vào **`C001`** bằng `merge_customer` (dst thắng; episode cùng `session_id` gộp thành 1). Kết quả: còn **1 episode** cho 1 khách (`C001`, trước đó 3 mã × 1), fact `C001` đủ, không còn dữ liệu ở 2 mã cũ, DB đã lên schema v2. Các mã khác (`C007`, 4 mã `CUST-ANON-*`) **không đụng tới**. Còn lại một fact cũ `order_id=OD600001` trong `C001` trỏ tới đơn không còn tồn tại — Call Brief tự bỏ nó kèm cảnh báo (D4), chưa xóa vì là dữ liệu của bạn.
2. **`main.py` dùng DB riêng `data/demo.db`** (ghi đè bằng `HARNESS_DB_PATH`); `scripts/seed_demo_db.py` mặc định cũng dùng `demo.db`. **DB mặc định `data/harness_memory.db` không bao giờ bị reset**: `seed_demo(reset=True)` ném lỗi và CLI `--reset` trả mã 2 (từ chối trước khi mở DB) nếu đích là DB mặc định; `main.py` tự bỏ reset nếu đích là DB mặc định. Có test (`DemoDbSafetyTest`): chạy `main()` không làm thay đổi DB mặc định (so mtime/kích thước trước-sau).

**Hàng rào chi phí cứng:** `run_eval.py --max-cost-vnd N` — một `LLMClient` dùng chung cho mọi cấu hình nên bộ đếm là TỔNG (gồm cả bộ trích slot khó); kiểm tra sau mỗi lượt và sau mỗi bước chốt cuộc gọi; vượt ngưỡng thì dừng ngay, giữ trace đã chạy, mã thoát 3. Có test (stub, CLI).

**Bước A (2 kịch bản SAMPLE-01, SAMPLE-04; `gpt-4o-mini`, seed 42): tiêu 939 VND.** Không có lỗi chạy: đường gọi LLM thật hoạt động đầu-cuối (stream, tool, token PII, guardrail, chống gọi lặp, bộ trích slot khó, nối Fanpage→Hotline ra `C017`, episode). Đọc trace phát hiện **4 lỗi về đo lường/chất lượng** — đã sửa trước khi chạy B, mỗi lỗi có test hồi quy:

| # | Lỗi | Sửa |
|---|---|---|
| 1 | Lệnh chấm khi dùng `--only` vẫn tính cả 7 kịch bản ⇒ bảng A.6 của lần chạy con bị lệch (TSR hiện 28,6% — sai; đúng là 100% vs 50%) | `run_eval.py` chấm trên thư mục tạm chỉ gồm kịch bản đã chạy |
| 2 | Bộ trích claims gán nhầm tên sản phẩm rút gọn (`AP-Y`, `SN-RUN2`) thành `promo_code` | mã KM phải đứng ngay sau từ chỉ khuyến mãi, không ngay sau "mẫu/sản phẩm/máy/giày/SKU" |
| 3 | LLM trích nhầm **giá hệ thống đã báo (1.521.000đ) thành ngân sách của khách** (slot khó `budget_vnd`) — kiểm "số có trong lời khách" không bắt được lỗi ngữ nghĩa | bỏ `budget_vnd` nếu trùng giá hệ thống đã báo và khách không nói kèm từ khóa ngân sách |
| 4 | Câu mở đầu Call Brief không tự nhiên: "mẫu AP-Y", "hôm 2026-10-15", "phòng 25.0m²" | dùng tên sản phẩm từ catalog, "hôm 15/10", "25m²" |

Sau sửa: **249 test, 0 đỏ**.


### 11.20. Kết quả bước 15 giai đoạn 1 (2026-10-21) — LLM thật

> **⚠ Đây chỉ là KIỂM TRA CÁC BẢN SỬA trên mẫu nhỏ — KHÔNG phải số liệu nộp.** 7 kịch bản · 39 lượt/cấu hình · 1 seed (42) · chưa có mean ± std · < 100 lượt nên p95 không có ý nghĩa thống kê. Một kịch bản đổi kết quả (đạt/trượt) làm TSR lệch 14 điểm %. Model `gpt-4o-mini`, temperature 0, seed 42. Lệnh: `python run_eval.py --seed 42 --out-dir runs/buoc15_B --max-cost-vnd 4000`; phân tích tái lập: `python scripts/analyze_run.py runs/buoc15_B` (kết quả lưu ở `runs/buoc15_B/analysis.txt`, `report.json`).

**Chi phí thực tế (VND, đo từ `llm_cost` của trace):** bước A (2 kịch bản) **939**; bước B (7 kịch bản) **2.240** (full 1.098 gồm 39 cho bộ trích slot khó; baseline 1.142). **Tổng 3.179 VND** (trần 5.000). `runs/full.jsonl`, `runs/baseline.jsonl` cũ không bị đụng tới (kết quả mới ở `runs/buoc15_A`, `runs/buoc15_B`).

**1. Bảng A.6 (7 kịch bản; số liệu đúng như lúc chạy)**

| Chỉ số | Baseline | Hệ thống (full) | Ghi chú |
|---|---:|---:|---|
| Repeat-Question Rate | 26,7% (4/15 câu) | **0,0%** (0/18 câu) | giảm 100% tương đối (ngưỡng ≥ 40%) — mẫu 15–18 câu |
| Context Carryover Rate | 66,7% (14/21) | **71,4%** (15/21) | hơn baseline 1 fact — chưa đủ để kết luận |
| Task Success Rate | 71,4% (5/7) | **85,7%** (6/7) | đạt ngưỡng ≥ 70%; ca khó 100% |
| Hallucination giá & KM | 66,7% (20/30 claim) | **18,2%** (2/11 claim) | **chưa đạt ≤ 5%**. Sau khi sửa lỗi bộ trích claims (xem 11.21), trích lại từ lời agent trong trace: **10,0% (1/10)**; baseline 66,7% (20/30). Baseline cao vì hay liệt kê nhiều sản phẩm một lượt |
| Số lượt TB / cuộc | 3 | 3 | |
| Vi phạm guardrail | 0 | 0 | |

**2. Số lần gọi, tool, độ trễ, chi phí**

| | Baseline | Full |
|---|---:|---:|
| Số lần gọi LLM / lượt (TB · trung vị · tối đa) | 2,67 · 3 · 4 | 2,54 · 2 · 4 |
| + gọi LLM trích slot khó | 0 | 13 (đúng 1/cuộc gọi, cuối cuộc) |
| Tool / lượt (TB · tối đa) | 1,92 · 15 | 1,15 · 3 |
| Tool báo lỗi (`unknown_sku`: LLM truyền tên sản phẩm thay vì mã SKU) | 18 (16) | 2 (2) |
| Token / lượt (trung vị) | 6.347 | 6.406 |
| **Chi phí / lượt** | 29,3 VND | 28,2 VND (gồm bộ trích) |
| TTFT p50 / p95 | 3.205 / 6.666 ms | 3.035 / 4.871 ms |
| Total p50 / p95 | 4.019 / 8.552 ms | 3.842 / 6.488 ms |
| Call Brief p50 / p95 | 0 / 0 ms (n = 6) | 1 / 1 ms (n = 6) |

So với mục tiêu M1: TTFT p95 ≤ 3.000 ms **chưa đạt** (4.871 ms); Total p95 ≤ 8.000 ms đạt với full (6.488) nhưng **không** với baseline (8.552); Call Brief ≤ 5.000 ms đạt (không gọi LLM). Nguyên nhân chính của độ trễ: 2–4 vòng gọi LLM tuần tự mỗi lượt, prompt ~6.400 token. **Chưa đủ 100 lượt** nên p95 chỉ mang tính tham khảo.

**3. Chất lượng trích slot với model thật (so với `facts_established`; chỉ full)**

| Nhóm | Slot | Đúng | Sai | Bỏ sót | Thừa* | Nhận xét |
|---|---|---:|---:|---:|---:|---|
| **Khó — LLM** | blocker | 3 | 0 | 0 | 0 | "can hoi chong" (SAMPLE-01), "so sanh gia" (SAMPLE-02), "can hoi vo" (SAMPLE-06) đều đúng |
| | competitor_price_vnd | 1 | 0 | 0 | 0 | 4.590.000 (SAMPLE-02) đúng |
| | budget_vnd | 0 | 0 | 2 | 0 | cả 2 ngân sách đã được **tầng regex** ghi trước (LLM không có gì thêm); GT SAMPLE-01 ghi 5.700.000 nhưng khách nói "tầm 5 triệu" → hệ thống ghi 5.000.000 **đúng lời khách, GT lệch** |
| | objection | 0 | 0 | 1 | 1 | SAMPLE-02: GT `dat_qua` ("sao bên em đắt hơn?") — LLM đưa vào `blocker=so sanh gia` + `competitor_price`, không có `objection` (lệch cách phân loại). SAMPLE-05 call_2: ghi "Sao hôm trước em bảo giảm 500.000 mà?" — hợp lý nhưng GT không có |
| **Dễ — regex** | room_area_m2 | 2 | 0 | 0 | 0 | |
| | has_children | 1 | 0 | 0 | 0 | |
| | color | 1 | 0 | 0 | 1* | "đen" ở SAMPLE-04 call_2 đúng lời khách, GT không liệt kê |
| | size | 1 | 0 | 0 | 3* | 2 cái đúng lời khách (40, 41); **1 cái SAI THẬT**: `size=20` ở SAMPLE-07 ("phí đổi size 20 nghìn" bị hiểu là cỡ giày) → đã sửa (11.21) |
| | budget_vnd | 1 | 1† | 0 | 0 | †GT lệch (xem trên) |
| **Từ tool** | product_advised | 5 | **1** | 0 | 0 | SAMPLE-01: hệ thống ghi `SKU-AP-X`, GT `SKU-AP-Y` (agent tư vấn nhầm — xem mục 4) |
| | price_quoted_vnd | 5 | 1 | 0 | 1 | cùng nguyên nhân SAMPLE-01 |
| | **promo_code** | **0** | **3** | 0 | 3 | **lỗi thật**: luôn ghi `COD-0` (KM miễn phí COD chung đứng đầu danh sách) thay vì KM thật (`GIFT-FILTER`, `RUN-10`, `AP-SEP`) → đã sửa (11.21) |

\* "Thừa" = hệ thống ghi mà `facts_established` của kịch bản không liệt kê (không nhất thiết sai). Mẫu rất nhỏ (3 blocker, 1 giá đối thủ…): **chưa đủ để nói tỉ lệ đúng của bộ trích LLM**; chỉ cho thấy nó hoạt động và không bịa trên mẫu này. Bộ lọc chống bịa có tác dụng: ở bước A, LLM từng trích nhầm giá đã báo (1.521.000đ) thành ngân sách — bị chặn ở bước B.

**4. Kịch bản full THUA baseline ở ít nhất một chỉ số: 2/7**

| Kịch bản | Thua ở | Số liệu | Nguyên nhân thật |
|---|---|---|---|
| **SAMPLE-01** | HR | TSR cả hai **trượt** (0/1 vs 0/1); HR full 1/1 claim sai vs baseline 12/14 | **Lỗi lựa chọn sản phẩm của agent, dùng chung cho cả hai cấu hình**: ở call_1 khách nói có bé nhỏ + ngân sách ~5 triệu, GT đáp án là AirPure Y 5.200.000đ (có khóa trẻ em, hơi vượt ngân sách) nhưng LLM chọn AirPure X 4.890.000đ (đúng ngân sách, không có khóa) dù prompt ưu tiên khóa trẻ em và liệt kê 2 sản phẩm thay vì chốt 1. Bộ nhớ sau đó **mang đúng** sản phẩm sai sang call_2 và agent đặt X → trượt `order.create` args_match. "Thua HR" chỉ là hiệu ứng mẫu nhỏ: full chỉ có 1 claim bị chấm (sai), baseline có 14 claim (12 sai) — số tuyệt đối full 1 vs baseline 12. **Không phải lỗi bộ nhớ** mà là lỗi tư vấn |
| **SAMPLE-03** | CCR (1/4 vs 2/4), HR (1/4 vs 0/1) | TSR cả hai **đạt** | **Cả hai là lỗi ĐO LƯỜNG, không phải lỗi hành vi**: (a) CCR thấp giả vì brief không đánh dấu `order_id/variant_sku/size/color` là cần mang sang nên `facts_used` không bao giờ ghi nhận agent đã dùng chúng, và so khớp có dấu ("den" ≠ "đen"); (b) claim sai `price_vnd=50000` là bộ trích claims đọc nhầm câu "size 43 giá sẽ nhích lên 50.000đ" (phần chênh lệch). Hành vi thật tốt hơn baseline: đổi size đúng 1 lần, phí 0đ nói đúng, chống gọi lặp hoạt động ở lượt 3 (baseline cần 8 tool call, có `order_not_found`). Cả hai lỗi đo lường đã sửa (11.21) |

Các kịch bản còn lại (SAMPLE-02, 04, 05, 06, 07) full **không thua** ở chỉ số nào; SAMPLE-04 full đạt còn baseline trượt (nhờ nối Fanpage→Hotline ra cùng khách `C017`).

**Điểm yếu còn lại (chưa sửa):** (1) tư vấn chốt nhầm sản phẩm khi có trẻ nhỏ + vượt ngân sách nhẹ và liệt kê nhiều sản phẩm một lượt; (2) LLM hay truyền tên sản phẩm thay vì SKU (`unknown_sku`) → tốn thêm vòng gọi (bộ tự sửa SKU xử lý được); (3) độ trễ TTFT p95 4,9 s; (4) `blocker` không bao giờ được tính là "đã dùng" trong CCR vì agent diễn đạt khác chuỗi đã lưu; (5) `GT` của SAMPLE-01 (`budget_vnd` 5.700.000) mâu thuẫn với lời khách (5 triệu).

### 11.21. Sửa lỗi phát hiện từ bước 15 (sau khi đã chạy) — CHƯA đo lại bằng LLM thật

Chạy lại sẽ vượt trần 5.000 VND (đã tiêu 3.179), nên các bản sửa dưới đây được kiểm bằng test + chấm lại **offline trên trace đã có** và **chưa** xác nhận bằng một lần chạy LLM mới.

| Lỗi | Phát hiện ở | Sửa | Kiểm chứng |
|---|---|---|---|
| `--only` làm bảng A.6 lệch (chấm cả kịch bản không chạy) | A | chấm trên thư mục kịch bản con | test; A chấm lại: TSR 100% vs 50% |
| `promo_code` ← tên sản phẩm rút gọn (`AP-Y`) | A | mã KM phải đứng sau từ chỉ khuyến mãi | test hồi quy |
| Giá đã báo bị LLM trích thành ngân sách | A | bỏ nếu trùng giá hệ thống mà khách không nói kèm từ khóa ngân sách | test; không tái diễn ở B |
| Câu mở đầu "mẫu AP-Y / hôm 2026-10-15 / 25.0m²" | A | tên sản phẩm thật, "hôm 15/10", "25m²" | test |
| `price_vnd=50000` ← phần chênh lệch size | B | role mới `variant_price_delta_vnd` | test; trích lại trace B: **HR full 18,2% → 10,0%** |
| `facts_used` bỏ sót `order_id/size/màu` và so khớp có dấu | B | brief mang thêm `order_id, variant_sku, size, color`; so khớp không dấu | test (chưa đo lại CCR bằng LLM) |
| `promo_code` luôn `COD-0` | B | chọn KM giảm giá > quà tặng > KM chung | test; suy ra từ trace: sẽ ghi đúng GT ở **3/3** ca có GT |
| `size=20` ← "phí đổi size 20 nghìn" | B | không nhận số có dấu phân cách nghìn/đơn vị tiền, chỉ nhận cỡ 18–50 | test |

Số test: **257, 0 đỏ**.


### 11.22. Đo lường công bằng + chạy lại C (2026-10-21) — LLM thật, 7 kịch bản × 2 cấu hình × 1 seed (seed 42)

**Mẫu nhỏ (7 kịch bản / 39 lượt / 1 seed) và LLM không tất định ngay cả khi `temperature=0` + seed — chênh lệch giữa B và C KHÔNG thể quy hết cho các bản sửa. Chỉ dùng để kiểm tra lỗi, không phải số liệu nộp bài.**

**Đã làm**
- `src/harness/fact_usage.py` + `scripts/fair_rescore.py` + `scripts/scan_btc_data.py` + `scripts/analyze_run.py` (phần 2b: độ trễ phân rã, tỉ lệ token prompt được cache).
- **HR công bằng:** claims của CẢ HAI cấu hình được trích lại bằng cùng một bộ trích. Thay đổi duy nhất trên B là lỗi "chênh lệch giá size đọc thành giá bán" → full 18,2% → 10,0%; baseline không đổi (66,7%). Trên C: **không claim nào đổi** (baseline 74,3%, full 30,0%). Tiền không có căn cứ tool: 0/64 (baseline), 0/36 (full) — tức không bịa số, các claim sai là *số thật nhưng của sản phẩm/giá sai*.
- **CCR chặt** (fact tính khi có từ đầu cuộc gọi + agent dùng thật + chưa hỏi mở lại + khách chưa nhắc lại; câu hỏi "đã trao đổi với gia đình chưa" không phải hỏi lại; blocker nay được tính):

| | cách cũ B | cách mới B | cách cũ C* | cách mới C |
|---|---|---|---|---|
| baseline | 66,7% (14/21) | 38,1% (8/21) | 14,3% (3/21) | 38,1% (8/21) |
| full | 71,4% (15/21) | 71,4% (15/21) | 52,4% (11/21) | 47,6% (10/21) |

\* "Cách cũ" = công thức BTC trên `facts_used` ghi trong trace; ở C `facts_used` lúc chạy đã là bản chặt nên không so được với B cùng cột. Cột "cách mới" là phát lại bộ nhớ của từng cấu hình bằng cùng một luật → so được.
- **GT BTC không sửa.** SAMPLE-01 `budget_vnd` 5,7tr vs khách "5 triệu" ghi ở `docs/BTC_DATA_ISSUES.md` #1.
- **Prompt caching (3b):** token prompt được cache **baseline 80,8% (214.144/264.980), full 72,0% (177.152/246.021)**; chi phí/lượt ~28 → **18,7–18,9 VND**. Vòng LLM trước token đầu (full): TB 1,46, phân bố {1:24, 2:12, 3:3} (baseline 1,67). TTFT full p50/p95 **2.823/4.637 ms** (B: 4,9 s p95), baseline 2.855/7.915; Total full 3.765/6.546. Giá cache của gpt-4o-mini (0,075 USD/1M) **cần đối chiếu giá chính thức**.
- Chi phí chạy C: **1.469 VND** (trần 5.000). Tổng A+B+C = 4.648 VND.
- Kết quả A.6 (C): RQR 17,6% → **7,7%**; CCR 14,3% → 52,4% (định nghĩa chặt lúc chạy); TSR 57,1% → **71,4%**; HR giá & KM 74,3% → **30,0%**; guardrail 0 vi phạm; tool error full 5 (4 `unknown_sku`) vs baseline 17.

**Kịch bản full thua baseline ở C (3/7) — nguyên nhân thật**
| Kịch bản | Nguyên nhân | Loại |
|---|---|---|
| SAMPLE-05 (TSR + HR) | LLM gọi `pricing.get_quote` với `basket_skus=["SKU-AP-X"]` (chính SKU đang báo giá, trong khi tham số này nghĩa là *các SKU khác trong đơn*) → mock áp KM "máy thứ 2 giảm 50%" → báo **2.445.000** thay vì 4.890.000; `order.create` sau đó bị `price_mismatch`. Ở B không xảy ra (LLM không truyền tham số này). | **Lỗi thật của agent, không tất định** |
| SAMPLE-01 (HR) | Vẫn chốt nhầm AirPure X (4,89tr) thay vì Y có khóa trẻ em (5,2tr); cả hai cấu hình đều trượt TSR. "Thua HR" vì baseline liệt kê nhiều sản phẩm nên có nhiều claim khác nhau | **Lỗi chọn sản phẩm — chờ bước 12** (không vá prompt) |
| SAMPLE-03 (HR) | full 0/2 sai, baseline 0/0 claim đo được (baseline không đổi được size: `order.update` báo không tìm thấy đơn, chỉ xin lỗi) → "thua" chỉ do tỉ lệ 0/0; TSR full **đạt**, baseline **trượt** | Lỗi đo lường |

**Sửa sau C (mã + test, CHƯA đo lại bằng LLM):** `Orchestrator._sanitize_basket` bỏ SKU trùng SKU chính khỏi `basket_skus` của `pricing.get_quote`/`order.create` (luật chung, không riêng AirPure) + 2 test; `scripts/seed_demo_db.py` ép stdout UTF-8 (test CLI vỡ khi chạy qua pipe trên console cp1252). Số test: **283, 0 đỏ**.

**Chưa làm:** bước 12 (chọn sản phẩm theo luật thuộc tính), 3(a) pre-fetch ở bước 13, 3(c) gọi tool chỉ-đọc song song, sinh dataset (chờ 5 câu § 9), bước 19 MCP thật, 14a. Chưa chạy lại LLM sau `_sanitize_basket` (cần bạn duyệt trần chi phí).


### 11.23. Bước 16a giai đoạn 1 — tích hợp Gipformer 1.5 68M RNN-T + so sánh với whisper (2026-10-21) — KHÔNG gọi API

**Đã làm**
- Model đặt ở `model_ASR/` (5 file); **5 hash SHA-256 (16 ký tự đầu) khớp đúng giá trị nhóm cung cấp**. `sherpa-onnx==1.13.8` thêm vào `requirements.txt` (+ `numpy>=2.0` ghi rõ vì mã import trực tiếp). `.gitignore`: `model_ASR/`, `models/`, `asr/audio_real/consent.csv`. `Code/README.md` (mới) ghi cách tải model, hash, biến môi trường, lệnh tái lập.
- `src/channels/offline_asr.py`: giao diện backend chung (`ASRResult`, `WhisperASR`, `GipformerASR`, `get_backend`), chọn bằng `ASR_BACKEND=gipformer|whisper` (**mặc định vẫn `whisper`**). `transcribe_audio`/`is_available` giữ chữ ký cũ, không bao giờ raise. Nạp model kiểm SHA-256, thiếu/sai file → `ASRModelError` nêu từng file + lệnh `huggingface-cli download`.
- `src/channels/audio_vad.py`: nạp mp3/wav → 16 kHz (PyAV), **VAD năng lượng thích nghi** (nền = phân vị 10%, loại bỏ đoạn phẳng/ồn dừng), Silero qua sherpa-onnx (**chưa có `silero_vad.onnx` nên đường Silero CHƯA được chạy thử**), cắt đoạn ≤ 20 s tại điểm năng lượng thấp nhất. Audio chỉ có nhiễu → transcript rỗng (test trên mô hình thật + nhiễu trắng ở 3 mức + nhiễu dao động chậm + im lặng số).
- `src/channels/asr_postprocess.py`: chữ HOA → chữ thường (giữ dấu) → `RequestNormalizer` (ITN/PII). Test: "BỐN TRIỆU TÁM TRĂM CHÍN MƯƠI NGHÌN" → 4.890.000; "KHÔNG CHÍN TÁM HAI…" → SĐT 10 số và bị `PiiVault` che thành `<PHONE_n>`; "NĂM TRĂM K" → 500.000. Trích thực thể từ giả thuyết (số tiền theo vai trò, diện tích, ngân sách, SĐT, mã đơn "ô đê/ô d …", bảo hành/giao/đổi trả với số chữ nhỏ); khi nhắc nhiều lần lấy lần cuối (đúng cách BTC tạo `entities` cấp hội thoại).
- `src/channels/asr_hypotheses.py` + `scripts/export_hypotheses.py`: xuất `hypotheses.json` đúng định dạng BTC rồi chạy `reference_eval.wer_cer` nguyên bản. **`turns[].idx` chỉ được điền khi có `<id>.segments.json` cạnh audio** (cùng định dạng BTC dùng cho diarization, thêm `idx`); D01–D04 hiện là MỘT giọng đọc liền nên **không có `turns`** (không giả lập). Yêu cầu này đã ghi vào `docs/DATASET_PLAN.md` § 3 cho khâu tạo audio. Test đường ống gán lượt dùng mốc từ thật của model nhưng mốc lượt dựng tạm từ GT (chỉ trong test).
- `scripts/compare_asr.py`: mỗi backend một tiến trình riêng (đo RAM/nạp model công bằng), WER/CER **thô (đúng chuẩn hóa BTC)** và **sau ITN cả hai vế**, entity số tiền/SĐT theo từng lượt, entity kiểu BTC, RTF, nhóm theo nguồn/miền/nhiễu (nhóm chưa có dữ liệu được in rõ là chưa có).
- `scripts/package_submission.py`: mặc định **không kèm** `model_ASR/`; `--include-model` kèm (kiểm SHA-256 trước, bỏ quét khóa trên file nhị phân). Đã thử: gói không model 1,4 MB, có model 53,5 MB.
- Số test: **319, 0 đỏ** (+34 ASR, +2 đóng gói).

**Cách `reference_eval.py --asr` chuẩn hóa (đọc nguyên văn, không sửa):** `lowercase` → NFC → `re.sub(r"[^\w\s]", " ")` → gộp khoảng trắng; **không đổi số↔chữ**. Transcript chuẩn viết số bằng CHỮ ("năm triệu hai trăm nghìn"), nên Gipformer (ra chữ) so trực tiếp được; model ra chữ số (whisper) bị phạt vì khác dạng → báo cả hai: **WER thô** và **WER ITN 2 vế** (cả vế chuẩn lẫn giả thuyết qua ITN của dự án rồi bỏ dấu phân cách nghìn). Entity BTC so exact `str(giá trị)` và dùng `entities` cấp hội thoại (= giá trị ghi sau cùng).

**Kết quả** (`python scripts/compare_asr.py --add-noise-snr 10`; 4 file TTS D01–D04 = 148 giây, một giọng `vi-VN-HoaiMyNeural` cho cả hai phía; bản nhiễu = trộn Gaussian trắng SNR 10 dB + 1,5 s chỉ-có-nhiễu hai đầu — **nhiễu tổng hợp, không phải nhiễu đường truyền thật**; CPU 2 luồng cùng máy; whisper `base` int8 trên CPU):

| nhóm | backend | WER thô | WER ITN 2 vế | CER thô | entity số tiền | entity SĐT | entity BTC (khóa có trích) | RTF |
|---|---|---|---|---|---|---|---|---|
| TTS giọng Bắc, không nhiễu (4 file) | gipformer | 8,4% | 9,4% | 2,9% | 90,9% (10/11) † | 100% (1/1) † | 70,6% (12/17) † | 0,03–0,05 |
| | whisper | 43,0% | 37,5% | 32,7% | 27,3% | 0% | 35,3% | 0,17–0,28 |
| TTS + nhiễu tổng hợp (4 file) | gipformer | 8,6% | 9,6% | 3,4% | 90,9% | 100% | 70,6% | 0,03–0,05 |
| | whisper | 50,5% | 47,6% | 39,2% | 27,3% | 0% | 23,5% | 0,17–0,28 |
| nhóm tự thu Nam / Trung / có nhiễu thật | cả hai | **chưa có dữ liệu** | | | | | | |

- `reference_eval.py --asr runs/asr_hypotheses/gipformer` (script chính thức): WER **8,4%**, CER **2,9%**, entity accuracy **41,4%** (12/29 khóa, gồm cả khóa chưa trích: `sku`, `promo_expiry`, `blocker`, `payment`, `color`, `in_stock`, `size_*` — **chưa làm**; còn sai ở khóa có trích: giá thứ hai trong lượt "mẫu X là bốn triệu…" không có từ "giá" nên không gán vai trò, `competitor_price_vnd`, `min_free_ship_vnd`, `bulky_fee_vnd` ở D03, `room_area_m2` ở D02). `entity_accuracy_per_turn` và diarization = null vì không có `turns`.
- Nạp model: gipformer ~1,6 s (gồm băm SHA-256 71 MB), whisper ~1,8 s. **RAM đỉnh: gipformer ~0,5 GB, whisper ~0,37 GB** (trước khi sửa cách giải mã: ~1,15 GB — xem dưới). RTF dao động giữa các lần chạy (máy dùng chung): gipformer 0,03–0,05, whisper 0,17–0,29.

**Phát hiện trong lúc làm (đã xử lý)**
1. `decode_streams` theo lô làm RAM đỉnh ~1,15 GB và chậm hơn; giải mã tuần tự từng đoạn: ~0,5 GB, RTF bằng/ hơn → dùng tuần tự. Độ dài đoạn mặc định **20 s** (25 s: 985 MB; 12–16 s: ~710 MB, WER không đổi trong sai số 4 file); đổi bằng `ASR_MAX_CHUNK_S`.
2. **Backend whisper cũ làm tiến trình thoát với "OMP: Error #15"** ở lần nhận dạng đầu trong env `nlp_env` (3 bản `libiomp5md.dll`: ctranslate2, torch, MKL) — tức `ASR_BACKEND=whisper` mặc định hiện KHÔNG chạy được trong env này nếu không có workaround. Đã đặt `KMP_DUPLICATE_LIB_OK=TRUE` (setdefault) ngay trước khi nạp faster-whisper; WER whisper sau đó (43,0% micro, trên 4 file) khớp báo cáo cũ 2026-10-10 (42,6% trung bình theo file), nên coi như không đổi kết quả. Báo cáo cũ giữ ở `runs/asr_report_whisper_2026-10-10.json`.
3. `eval_asr.py` kiểm entity bằng `substring` trên văn bản **chưa ITN** (docstring nói có ITN nhưng mã không làm) → model ra chữ luôn bị chấm sai; đã sửa dùng `normalize_transcript` (lưu ý: kiểm này vẫn là khớp chuỗi lỏng, số bé như "2" dễ trùng; số liệu entity ở bảng trên dùng bản chặt trong `compare_asr.py`).
4. Hai lỗi do viết mã (ký tự `\b` bị đổi thành ký tự điều khiển trong regex) đã tìm và sửa; đã quét không còn ký tự điều khiển trong các file mới.

**Quyết định backend (PLAN 16a) — ĐÃ THAY bởi § 11.24 (nhóm duyệt đổi mặc định sang gipformer):** trên số liệu hiện có gipformer **vượt xa** whisper-base ở WER và entity, nên đủ tiêu chí "không kém"; **chưa đổi mặc định** vì mẫu chỉ 4 file/1 giọng TTS, chưa có Nam/Trung và nhiễu thật. Chờ chạy lại trên ≥ 20 file hoặc bạn duyệt đổi ngay. So với whisper-base là so với model yếu nhất của họ; chưa thử `small/medium` nên không kết luận "gipformer hơn whisper" nói chung.

**Chưa làm / hạn chế:** đo trên ≥ 20 file; giọng Nam/Trung; nhiễu thật; `turns` cho audio mới (cần khâu tạo audio ghi mốc lượt); trích `sku`/`promo_expiry`/`blocker`/`payment`/`color`/`in_stock` cho entity BTC; đổi số→chữ để nộp whisper; Silero VAD (chưa có file model — cần bạn cho phép tải); ASR_FIXES chưa có từ điển cho đầu ra Gipformer (vd "EPX", "EPI" cho "AirPure X/Y").

**Tái lập**
```
conda activate nlp_env && pip install -r requirements.txt
python -m unittest discover -s tests -t .
python scripts/compare_asr.py --add-noise-snr 10        # -> runs/asr_compare/report.md
python scripts/export_hypotheses.py --backend gipformer  # -> runs/asr_hypotheses/gipformer/ + wer_cer của BTC
python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --asr runs/asr_hypotheses/gipformer
```


### 11.24. Bước 16a (tiếp) — duyệt đổi mặc định, Silero VAD, nhiễu sát thực tế, entity đủ khóa, whisper-small (2026-10-21) — KHÔNG gọi API

> **Phạm vi mọi số WER dưới đây: "trên audio TTS sạch, giọng Bắc, n = 4 file" (D01–D04, 148 s, một giọng `vi-VN-HoaiMyNeural` cho cả hai phía).** Các điều kiện nhiễu/kênh điện thoại là **mô phỏng** (nguồn tiếng nói vẫn là 4 file đó). Đo lại sau khi có dataset ≥ 20 file (có giọng Nam/Trung và nhiễu thật). Bảng WER trong model card Gipformer là số do tác giả công bố trên bộ riêng, không phải số của dự án.

**Quyết định của nhóm đã thực hiện**
1. **`ASR_BACKEND` mặc định = `gipformer`**; whisper là dự phòng (không đặt `ASR_BACKEND` mà Gipformer không nạp được → rơi về whisper kèm cảnh báo; đặt rõ `gipformer` mà lỗi → trả rỗng, KHÔNG đổi ngầm). **Luật quay lại** ghi ở PLAN 16a: đo trên ≥ 20 file mà gipformer kém whisper về WER hoặc entity accuracy → đổi lại và báo nhóm. Test: mặc định, rơi về dự phòng, không đổi ngầm khi đặt rõ.
2. **Gói nộp kèm model mặc định** (`--no-model` để bỏ): kiểm SHA-256 5 file + Silero, bắt buộc có `LICENSE`, `README.md` (model card), `NOTICE.md`. Đã chạy thử: 217 file, 54,1 MB, có đủ 9 file trong `model_ASR/`, không `.env`, không `backup_*`. Repo Git không chứa model (`.gitignore`). **`LICENSE`:** tác giả không phát hành file LICENSE (đã kiểm repo GitHub `ggroup-ai-lab/gipformer`, commit `0cac5b18`, 2026-09-17: không có file; liên kết LICENSE trong README của họ 404) nhưng tuyên bố MIT ở README, `pyproject.toml` (`license = { text = "MIT" }`) và model card HF (`license: mit`). `model_ASR/LICENSE` là mẫu MIT chuẩn dựng theo tuyên bố đó ("Copyright (c) 2026 G-Group AI Lab"); `NOTICE.md` ghi rõ nguồn, commit và ngày kiểm tra 2026-10-21. Script đóng gói không chặn theo nội dung nhưng vẫn bắt buộc có `LICENSE`, `README.md`, `NOTICE.md`.
3. **Silero VAD**: URL kiểm bằng `curl -I` (HTTP 302 → 200) trên release `asr-models` của `k2-fsa/sherpa-onnx`; tải `silero_vad.onnx` = **643.854 byte, SHA-256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6`** (ghi trong README, mã kiểm khi nạp). `ASR_VAD=silero|energy|auto`.
4. **Nhiễu sát thực tế** (`src/channels/audio_sim.py`, cú pháp `phone+codec+babble@10`): kênh điện thoại (lọc 300–3400 Hz, hạ 8 kHz rồi nâng 16 kHz), nén µ-law 8-bit, và tạp âm môi trường tổng hợp: nhiễu trắng, *babble* (5 lời nói khác đảo ngược), *street* (nhiễu nâu + xe chạy qua + còi), *cafe* (babble + lách cách). SNR đo theo công suất đoạn CÓ tiếng nói (test kiểm sai số < 0,5 dB); hai đầu đệm 1,5 s chỉ-có-nhiễu.
5. **Entity đủ khóa** theo định dạng giá trị của ground truth/BTC (`src/channels/asr_entities.py`, `config/product_aliases.json`): `sku` (SKU cha, khớp mờ cách đọc tên sản phẩm), `color` (không dấu), `promo_expiry` (ISO), `payment` (COD|bank|momo|zalopay theo `tools.schema.json`), `in_stock`, `blocker` (`can hoi chong|can hoi vo|so sanh gia`), `size_old/size_new`, cộng vai trò số tiền theo cụm từ (giá sau "mẫu … là", giá đối thủ, ngưỡng freeship, phụ thu hàng cồng kềnh) và diện tích "phòng … mét". Nhắc nhiều lần → lấy lần cuối (đúng cách BTC tạo `entities` cấp hội thoại).
6. Mục "Phát hiện thêm" bên dưới (libiomp5md.dll).
7. **whisper-small** đã thử trên cùng 4 file (xem bảng).

**Entity accuracy chính thức** (`reference_eval.py --asr runs/asr_hypotheses/gipformer`, script BTC nguyên bản): WER **8,4%**, CER **2,9%**, **entity_accuracy 100% (29/29) — trong tập phát triển (D01–D04), luật viết sau khi xem dữ liệu** (trước đó 41,4%). **Đây là số TRONG-TẬP:** bảng alias và các luật được viết khi đã thấy ground truth + giả thuyết của D01–D04, nên 100% không nói lên khả năng khái quát. Kiểm chứng ngoài-tập duy nhất làm được: lời khách của 7 kịch bản public (không dùng khi viết luật) → 11/14 khóa; 3 khóa sai là **1 lỗi dữ liệu BTC đã ghi** (`budget_vnd` 5,7 triệu vs lời khách 5 triệu — BTC_DATA_ISSUES #1) và **2 `promo_expiry` do agent nói, không có trong lời khách** → thực chất 11/11 khóa có trong lời khách. Chưa có số ngoài-tập cho lời agent (sku/giá/ngày KM) và cho 28/32 SKU mà bảng cách đọc do nhóm tự đoán. `entity_accuracy_per_turn` và diarization vẫn null vì D01–D04 không có mốc lượt.

**Kết quả WER (thô theo chuẩn hóa BTC / sau ITN hai vế), trên audio TTS sạch giọng Bắc n = 4 file + điều kiện mô phỏng** — lệnh: `python scripts/compare_asr.py --backends gipformer:silero,gipformer:energy,gipformer:auto,whisper:base,whisper:small --noise white@10,phone,phone+codec,phone+babble@10,phone+street@10,phone+cafe@10` và `--noise white@0,white@5` (đủ 14 điều kiện × 5 backend ở `runs/asr_compare/report.md`, `runs/asr_compare_lowsnr/report.md`):

| điều kiện (mô phỏng, nguồn D01–D04) | gipformer silero | gipformer năng lượng | **gipformer auto (hợp)** | whisper-base | whisper-small |
|---|---|---|---|---|---|
| sạch | 8,1 / 9,1 | 8,4 / 9,4 | **8,4 / 9,4** | 43,0 / 37,5 | 32,6 / 24,9 |
| trắng SNR 10 dB | 8,7 / 9,8 | 8,1 / 9,1 | 8,6 / 9,6 | 52,2 / 49,3 | 38,9 / 31,4 |
| trắng SNR 5 dB | 10,4 / 11,8 | **100 (VAD bỏ hết)** | 10,1 / 11,3 | — | — |
| trắng SNR 0 dB | 12,6 / 14,1 | **100 (VAD bỏ hết)** | 11,7 / 13,1 | — | — |
| điện thoại (300–3400 Hz, 8 kHz) | 10,0 / 11,1 | 9,0 / 10,1 | 9,0 / 10,1 | 47,0 / 41,1 | 36,6 / 27,2 |
| điện thoại + µ-law | 9,0 / 10,1 | 8,7 / 9,8 | 8,9 / 9,9 | 48,8 / 43,0 | 37,7 / 29,6 |
| điện thoại + babble 10 dB | **100 (VAD bỏ hết)** | 14,6 / 16,2 | 11,4 / 12,7 | 89,7 / 90,4 | 51,6 / 45,5 |
| điện thoại + đường phố 10 dB | **91,9 (VAD bỏ gần hết)** | 9,7 / 10,8 | 9,5 / 10,6 | 51,2 / 47,2 | 38,9 / 31,4 |
| điện thoại + quán 10 dB | **100 (VAD bỏ hết)** | 14,0 / 15,9 | 12,8 / 14,5 | 93,9 / 93,0 | 56,4 / 50,5 |

**So 2 VAD trên file có nhiễu — phát hiện chính:** hai VAD hỏng ở hai vùng KHÁC NHAU. **Silero** (model ONNX của sherpa) thắng ở nhiễu trắng lớn (SNR ≤ 5 dB) nhưng **bỏ sót gần như toàn bộ tiếng nói khi có kênh điện thoại + tạp âm giống tiếng người/đường phố** (WER 92–100%; kiểm với ngưỡng 0,1–0,5, chuẩn hóa biên độ, tăng gain: không khỏi — "phone" một mình và "white/babble/street" không qua kênh điện thoại thì Silero vẫn bắt được). **VAD năng lượng** ngược lại: tốt với kênh điện thoại + tạp âm, nhưng **bỏ hết ở nhiễu trắng SNR ≤ 5 dB**. Vì vậy `auto` = **hợp** hai VAD (`UnionVAD`) — không tệ hơn VAD tốt hơn ở mọi điều kiện đã thử (±0,6 điểm WER) và vẫn rỗng khi chỉ có nhiễu dừng. Đây là kết quả trên nhiễu MÔ PHỎNG; cần kiểm lại trên ghi âm điện thoại thật trước khi kết luận Silero kém trên điện thoại thật (có thể do cách mô phỏng băng thông cắt cứng).

**Gipformer vs whisper:** gipformer(auto) tốt hơn whisper-**small** ở mọi điều kiện đã đo (8,4% vs 32,6% sạch; 9,5% vs 38,9% đường phố; 11,4% vs 51,6% babble). Whisper-small tốt hơn base ~10 điểm nhưng **chậm ~16 lần** gipformer (RTF 0,75 vs 0,045; nạp 17 s vs 1,7 s; RAM đỉnh 788 MB vs ~615 MB) → kết luận "gipformer tốt hơn whisper" không còn bị phản bác bằng "so với model yếu nhất". `Systran/faster-whisper-small` (464 MB) được faster-whisper tải về bộ nhớ đệm HF của máy (không nằm trong repo/gói nộp).

**Phát hiện thêm**
- **Nguồn gốc 3 bản `libiomp5md.dll` trong `nlp_env`:** (1) `site-packages/ctranslate2/libiomp5md.dll` — wheel `ctranslate2 4.8.2` (pip, kéo theo bởi faster-whisper) tự đóng gói OpenMP của Intel; (2) `site-packages/torch/lib/libiomp5md.dll` — wheel `torch 2.5.1+cu121` (pip; `Required-by: torchvision`), **không file nào trong `Code/` import torch/torchvision** → gói thừa; (3) `Library/bin/libiomp5md.dll` — gói conda `intel-openmp 2025.0.0`, phụ thuộc của `mkl 2025.0.0` mà `numpy 2.5.2` bản conda (py312h9606935_0) liên kết. **Cơ chế gây lỗi (đã tái hiện):** import `ctranslate2` nạp bản (1); bản (3) chỉ được nạp **lười** ở lần gọi BLAS đầu tiên của numpy (`a @ a`) → hai bản cùng tên trong một tiến trình → "OMP: Error #15" ở lần nhận dạng whisper đầu tiên (bản (2) chỉ nạp khi import torch, không nằm trên đường chạy của dự án). **Cách xử lý gốc (CHƯA làm, vì whisper chỉ còn là dự phòng):** (a) `pip uninstall torch torchvision` (gói thừa, bỏ bản 2); (b) cho numpy không dùng MKL — cài `numpy` bản pip (OpenBLAS) thay bản conda-MKL, hoặc `conda install nomkl` — để chỉ còn bản của ctranslate2. `KMP_DUPLICATE_LIB_OK=TRUE` (đang đặt trong `_get_model`) chỉ là cách tạm Intel ghi là không được hỗ trợ.
- **Ba lỗi nhỏ đã sửa:** Silero cần `max_speech_duration` bằng độ dài đoạn tối đa; cửa sổ khớp tên sản phẩm 4 từ không đủ cho "xiao mi smart bốn pờ rô" (nâng lên 7); khớp mờ trên alias ≤ 6 ký tự gây nhận nhầm "chị chờ" → "Chicco" (ép khớp tuyệt đối).
- Bản cũ của § 11.23 ghi "mặc định whisper, Silero chưa thử" — đã được thay bằng các quyết định ở trên.

**Chưa làm / hạn chế:** đo ≥ 20 file; giọng Nam/Trung; nhiễu/điện thoại **thật**; kiểm entity ngoài-tập cho lời agent; `turns` cho audio mới (khâu tạo audio phải ghi `<id>.segments.json`);  sửa gốc libiomp5md; RTF dao động giữa các lần chạy do máy dùng chung (gipformer 0,04–0,05, whisper-base 0,25–0,30).

**Số test: 354, 0 đỏ** (+35 so với § 11.23: entity, mô phỏng nhiễu, chọn VAD, mặc định/dự phòng, đóng gói).

**Tái lập**
```
python -m unittest discover -s tests -t .
python scripts/compare_asr.py --backends gipformer:silero,gipformer:energy,gipformer:auto,whisper:base,whisper:small --noise white@10,phone,phone+codec,phone+babble@10,phone+street@10,phone+cafe@10
python scripts/compare_asr.py --backends gipformer:silero,gipformer:energy,gipformer:auto --noise white@0,white@5 --out runs/asr_compare_lowsnr
python scripts/export_hypotheses.py && python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --asr runs/asr_hypotheses/gipformer
python scripts/package_submission.py          # kèm model + LICENSE + README tác giả + Silero
```


### 11.25. Chốt phần ASR (2026-10-21) — không tinh chỉnh thêm cho tới khi có audio mới

Nhóm duyệt 7 mục của § 11.24 và yêu cầu **dừng tinh chỉnh ASR**. Việc đã làm để chốt:
1. **`ASR_VAD=auto` là mặc định.** Mọi kết luận về VAD (Silero hỏng ở kênh điện thoại + tạp âm; VAD năng lượng hỏng ở nhiễu trắng SNR ≤ 5 dB; hợp hai VAD không tệ hơn VAD tốt hơn quá 0,5 điểm WER) **chỉ dựa trên nhiễu GIẢ LẬP; cần kiểm lại trên ghi âm điện thoại thật.** Dòng này cũng in ở đầu `runs/asr_compare/report.md`.
2. **Đóng gói BỊ CHẶN cho tới khi `LICENSE` là bản gốc.** Kiểm HF 2026-10-21: https://huggingface.co/g-group-ai-lab/gipformer1.5-68M-rnnt/tree/main/LICENSE trả 404 ("LICENSE does not exist on main"); GitHub `ggroup-ai-lab/gipformer` (commit `0cac5b18`) cũng không có file → cả hai đã ghi trong `model_ASR/NOTICE.md`. **[ĐÃ THAY bằng § 11.28 mục 1: tác giả KHÔNG có LICENSE gốc (GitHub và HF đều 404) nên `upstream` không bao giờ đạt được; script nay chấp nhận `LICENSE_STATUS: derived-from-author-declaration` khi NOTICE.md có đủ bằng chứng.]**
3. **Entity accuracy luôn kèm "trong tập phát triển (D01–D04), luật viết sau khi xem dữ liệu".** Báo cáo `compare_asr.py` tách dòng "[tập phát triển]" và "TẬP CHƯA THẤY (báo riêng)"; `export_hypotheses.py` in cảnh báo. † ở bảng § 11.24 = cùng nghĩa. **Khóa luật:** `config/asr_rules.lock.json` (phiên bản `asr-rules-v1-2026-10-21`) ghi SHA-256 của `config/product_aliases.json`, `src/channels/asr_entities.py`, `src/channels/asr_postprocess.py` và phần ITN/ASR_FIXES của `normalizer.py` (hash của mã nguồn các hàm ITN + từ vựng số, không băm cả file); `tests/test_asr_rules_lock.py` đỏ nếu đổi mà chưa chạy `python scripts/lock_asr_rules.py --update --version … --reason …`.
4. **libiomp5md.dll:** để nguyên (không đổi numpy, không gỡ torch). Cách xử lý gốc đã ghi ở § 11.24.

Không chạy lại benchmark ở bước này (không đổi mã nhận dạng). Số test: **360, 0 đỏ**.


### 11.26. Bước 12 — schema slot + ProductRetriever + chặn câu hỏi lặp (2026-10-21) — mã + test, CHƯA đo bằng LLM thật

**Đã làm** (không gọi API):
- `config/slot_rules.json` (**dữ liệu**, phiên bản `slot-rules-v1-2026-10-21`): 9 luật nối slot → thuộc tính THẬT của catalog (`has_children→child_safe_lock`, `room_area_m2→room_area_m2 (≥, ưu tiên sát nhu cầu)`, `budget_vnd→list_price_vnd (vượt thì trừ theo mức vượt)`, `child_weight_kg→max_weight_kg`, `volume_ml`, `min_warranty_months→warranty_months`, `min_stages→stages`, `material→material`, `min_return_days→return_days`). Luật chỉ áp dụng khi slot đã biết **và** sản phẩm có thuộc tính đó (thiếu thì trung tính); **không luật nào loại sản phẩm** (sản phẩm duy nhất có khóa trẻ em vẫn đứng đầu dù vượt ngân sách, mức vượt được nêu rõ); vi phạm một phần bị trừ nhẹ hơn vi phạm hoàn toàn. Thêm ngành/thuộc tính mới = thêm một dòng JSON.
- `src/catalog/`: `slot_schema.py` (nạp + kiểm luật, phát hiện luật chết/sai kiểu), `retriever.py` (`ProductRetriever.shortlist` → top-k kèm `matched/violated/unknown`, `recommendation`, slot còn thiếu đáng hỏi `ask_next`; loại hàng ngừng bán, phụ kiện/combo trừ khi hỏi đích danh; hết hàng chỉ bị hạ hạng), `clarification.py` (`ClarificationPolicy`: if/else, ≤ 1 câu/lượt, không hỏi slot đã biết/đã hỏi/`must_not_ask`, bỏ slot không làm đổi kết quả; `strip_repeated_questions` gỡ câu hỏi mở lặp khỏi lời agent, câu về `blocker` luôn được phép, không bao giờ để trả lời rỗng).
- Tích hợp orchestrator: tool nội bộ **`product.shortlist`** (LLM thấy trong tools; slot = hồ sơ đã nhớ < tham số LLM < lời khách lượt này) — nay chạy ở `mcp-catalog` (§ 11.27); **mẹo riêng thuộc tính `child_safe_lock` trong system prompt đã GỠ**, thay bằng hướng dẫn chung "gọi product.shortlist rồi chốt đúng 1 sản phẩm đứng đầu"; sau guardrail, câu hỏi mở lặp bị gỡ (`metadata.repeat_questions_removed`).
- **31 test mới** (`tests/test_slot_retriever.py`): ≥ 8 sản phẩm thuộc ≥ 3 danh mục (lọc không khí, lọc nước, quạt, giày, xe đẩy…) mỗi luật có ca dương/âm; hoán đổi thứ tự/tên sản phẩm → thứ hạng không đổi, thêm sản phẩm giả → kết quả đổi đúng theo thuộc tính; catalog thử không có sản phẩm nào có khóa trẻ em → chọn theo giá/ngân sách; sản phẩm an toàn duy nhất giữ dù vượt ngân sách xa; 300 tổ hợp slot ngẫu nhiên → mọi SKU trả về tồn tại thật và `mock_tools` chấp nhận (không `unknown_sku`); trong mã/luật không có tên AirPure/SKU/SAMPLE-01. Với slot của SAMPLE-01 (25 m², có bé, ngân sách 5 triệu) shortlist đứng đầu = SKU-AP-Y mà **không có tên sản phẩm nào trong mã/prompt**.

**Chưa làm:** (6) "số lần gọi LLM/lượt không tăng" và (7) "chạy lại 7 kịch bản, không kịch bản nào tụt" cần LLM thật (ước tính ~1.500 VND, trần 5.000) — **chờ bạn duyệt**; chưa đo `unknown_sku` trên LLM thật; `ClarificationPolicy` chưa dùng `channel` (hỏi theo nền tảng); chưa có luật cho thuộc tính chữ ngoài `material` (vd `features`).

### 11.27. Bước 19 (một phần) — MCP thật: 2 server + client + phân quyền (2026-10-21)

**Đã làm:**
- Cài `mcp==2.3.0` (SDK MCP; từ 2.x `FastMCP` → `MCPServer`), ghi vào `requirements.txt`. Kéo thêm: `mcp-types`, `pyjwt`, `cryptography`, `sse-starlette` (không nâng cấp gói nào có sẵn).
- **2 MCP server thật** (`mcp_servers/`, chạy riêng được: `python -m mcp_servers.catalog_server` / `crm_server`): **`mcp-catalog`** (`catalog.search`, `inventory.check`, `pricing.get_quote`, `product.shortlist`) và **`mcp-crm`** (`crm.get_customer`, `order.create/status/update`, `schedule.callback`, `handoff.transfer`; `mcp-order` tách ở M2) + tool quản trị `admin.reset_state`/`admin.audit`. Kết quả `mock_tools.py` giữ nguyên (test so khớp từng lời gọi với gọi trực tiếp).
- **Client**: `MCPToolGateway` (`src/tools/mcp_gateway.py`) thay cổng cũ — cùng giao diện `execute_tool(tool, args, caller)`, vòng lặp asyncio nền, kết nối một lần dùng lại. Transport: `stdio` (mỗi server là **tiến trình riêng**, mặc định của `main.py`/UI/`run_eval.py`), `inproc` (cùng giao thức MCP qua luồng bộ nhớ, mặc định của test để đọc được trạng thái mock), `local` (`LocalToolGateway`, chỉ để so độ trễ). Nghiệp vụ tool chuyển sang `src/tools/tool_impl.py`; `mcp_gateway.py` vẫn re-export tên cũ.
- **Phân quyền theo caller** (`config/mcp_permissions.json`, **mặc định từ chối**, kiểm ở PHÍA SERVER qua `_meta.caller`): tool ghi chỉ cho lõi điều phối; `CallBriefBuilder`/`SkuResolver`/`IdentityResolver` chỉ đọc; `admin.*` chỉ `TestHarness`/`EvalRunner`; gọi không caller hoặc caller lạ → `{error: forbidden}` và **không ghi gì** (test kiểm `mock_tools._ORDERS` rỗng). Nhật ký kiểm toán server-side (caller, tool, ok, ms) **không chứa tham số** (test: SĐT không xuất hiện).
- Giữ nguyên hành vi: loại field `_*` ở server **và** client (N15), lỗi tool → `{error}`, nhật ký kiểm toán tập trung của gateway (thêm `transport`, `duration_ms`), PII token/chống gọi lặp (ở orchestrator, không đổi). `ScenarioRunner` dùng MỘT cổng cho cả tiến trình và `reset_state()` qua MCP mỗi kịch bản.
- **Độ trễ tăng thêm** (`python scripts/bench_mcp.py`, 200 lần/tool, `runs/mcp_overhead.json`): trực tiếp 0,01–1,0 ms → MCP cùng tiến trình ~1,2–2,4 ms → **MCP stdio ~1,8–3,6 ms (p50), p95 ≤ 6,2 ms; khởi động 2,9 s một lần** — tức **+2–3 ms/lần gọi tool**, so với ~1.000 ms mỗi vòng LLM.
- **Test**: 18 test MCP (`tests/test_mcp_servers.py`: danh sách tool của ≥ 2 server, kết quả y hệt gọi trực tiếp, mặc định từ chối, lỗi có cấu trúc, đường stdio có 2 tiến trình riêng, đóng cổng thì tiến trình con biến mất) + toàn bộ test cũ vẫn xanh trên đường MCP (**409 test, 0 đỏ**); `test_runner`/`test_orchestrator`/`test_identity_brief` cũng xanh khi chạy với `MCP_TRANSPORT=stdio`. Test đổi: hai test gọi `execute_tool` không caller nay truyền `caller="HarnessOrchestrator"` (vì mặc định từ chối).

**Chưa làm (chờ quyết định):** **`mcp-memory`** — PLAN yêu cầu server bộ nhớ có phân quyền ghi. Khó ở chỗ `MemoryService` giữ giao dịch SQLite theo lượt (`begin_turn` … `drain_writes`) và nhật ký ghi trong tiến trình; hai tiến trình cùng ghi một DB sẽ chặn nhau → muốn làm thật phải theo kiểu **một nơi ghi duy nhất** (server giữ `MemoryService`, orchestrator/brief/resolver truy cập MỌI thứ qua MCP, kể cả `begin_turn/drain_writes/working memory`), cần proxy ~20 phương thức + chuyển đổi dữ liệu + chạy lại toàn bộ test bộ nhớ trên proxy. Chưa làm: bỏ/nối các agent A2A chỉ có trên danh nghĩa (`src/agents/specialists.py`), cập nhật tài liệu luồng (file PIPELINE.md hiện nằm trong `backup_2026-10-21/`), chạy `run_eval.py` thật trên kiến trúc MCP (cần LLM).


### 11.28. Sửa luật đóng gói + bước 12 (ngân sách 20%, xác nhận thay vì gỡ) + dataset văn bản: bộ kiểm và 10 kịch bản mẫu (2026-10-21)

**1. Đóng gói / LICENSE (sửa theo chỉ đạo).** Tác giả không có LICENSE gốc (GitHub `ggroup-ai-lab/gipformer` commit `0cac5b18` và HF đều 404) → `upstream` không bao giờ đạt được. `scripts/package_submission.py` giờ **chấp nhận `LICENSE_STATUS: derived-from-author-declaration`** (hoặc `upstream` nếu sau này có) và **chỉ chặn** khi: NOTICE.md thiếu dòng trạng thái / trạng thái khác (vd `derived` cũ); NOTICE.md thiếu bằng chứng (kết quả kiểm GitHub + HF + 404 + 3 nguồn tuyên bố MIT: README GitHub, `pyproject.toml`, model card HF); `LICENSE` không phải văn bản MIT; thiếu `LICENSE`/`README.md`/`NOTICE.md`/`silero_vad.onnx`. `NOTICE.md` cập nhật theo. Đã thử: gói có đủ model, 54 MB. 10 test đóng gói (thêm: có bằng chứng → chấp nhận, thiếu bằng chứng → chặn, trạng thái cũ → chặn, thiếu LICENSE/README → chặn, LICENSE không phải MIT → chặn, NOTICE thật của dự án hợp lệ).

**2. Bước 12 — hai điểm sửa (mã + test, CHƯA đo bằng LLM thật).**
- *Luật ngân sách* (`config/slot_rules.json` v2, `settings.budget_tolerance = 0.20`): sản phẩm đứng đầu vượt ngân sách **≤ 20%** → vẫn chốt 1 sản phẩm và nêu mức vượt (`decision.mode = "single"`, `overage_pct`); **> 20%** → `decision.mode = "two_options"`: đứng đầu + **sản phẩm điểm cao nhất TRONG ngân sách** (`alternative`); không có sản phẩm nào trong ngân sách → vẫn `single` kèm cờ `no_in_budget_alternative`. System prompt hướng dẫn theo `decision`. 7 test (≤ 20%, đúng 20%, > 20%, không có phương án trong ngân sách, không ngân sách, ngưỡng là cài đặt chứ không phải mã, catalog thật).
- *Câu hỏi lặp → câu XÁC NHẬN, không gỡ* (`ClarificationPolicy.rewrite_repeated_questions`): câu hỏi mở về slot đã biết/`must_not_ask` được đổi thành "Phòng nhà mình vẫn khoảng 25m² đúng không ạ?" (mẫu trong `confirm_templates` của luật dữ liệu); **chỉ xác nhận một lần cho mỗi slot trong cuộc gọi** — lặp lần thứ hai thì mới gỡ câu đó (xác nhận mãi mỗi lượt là làm phiền; nêu rõ để bạn quyết nếu muốn khác); slot chưa biết giá trị thì giữ nguyên; không bao giờ để trả lời rỗng. Câu xác nhận được extractor phân loại `confirm` nên **không bị tính là hỏi lặp (RQR) và được tính là DÙNG fact (CCR)** — test cũ `test_open_question_disqualifies_slot…` đổi thành chạy với `clarifier=None` và thêm test cho hành vi mới. Metadata: `repeat_questions_rewritten`, `repeat_questions_dropped`. 7 test (từng mẫu slot, giữ phần còn lại của câu, một lần/slot, không làm rỗng, blocker, giá trị chưa biết) + 3 test tích hợp orchestrator.

**3. Dataset văn bản — bộ kiểm + 10 kịch bản mẫu** (`docs/DATASET_TEXT_PLAN.md`; **dừng để bạn xem**).
- `scripts/validate_scenarios.py` (luật S1–S14, `src/dataset/validate.py`) chạy trên 22 kịch bản hiện có: **tái lập đúng số "hiện có"** (31 cuộc / 9 khách đa phiên / 0 khách ≥ 3 phiên / 3 đa kênh / ca khó: đổi ý 0, mâu thuẫn 0, KM hết hạn 2, ngoài tài liệu 2). **Tìm ra 4 LỖI thật + 2 cảnh báo trong dữ liệu hiện có** (chưa sửa — sửa sẽ làm các lần chạy cũ không so được): SAMPLE-01 `budget_vnd` 5,7 triệu vs lời khách 5 triệu (đã ghi BTC_DATA_ISSUES #1); **SC-GEN-05** call_2 `must_carry_over: order_id` nhưng call_1 không có `order_id` trong `facts_established`; **SC-GEN-06** call_2 `promo_active: true` nhưng PUMP-GIFT đã hết hạn 13/10 (cuộc gọi ngày 15/10) — lỗi của file do nhóm sinh; **SC-GEN-11** call_1 có `must_not_ask` không có `seed_history`. (BTC cho phép bỏ `expected_outcome` ở cuộc sau và `channel_identity` — không coi là lỗi/chỉ cảnh báo.)
- Khung xác định (`src/dataset/specs.py` + `truth.py`): 10 kịch bản (A: 3, B: 2, C: 5; 17 cuộc; 3 kênh; 4 loại ca khó + COD vượt hạn mức + teencode). **Mọi đáp án do code tính từ `mock_tools`** (giá sau KM theo ngày, tồn kho, mã đơn OD600001 trên trạng thái sạch, phụ thu đổi size 219.000đ = 1.690.000 + 50.000 − 1.521.000, hạn mức COD, trạng thái KM). LLM không thấy giá thật (chỉ thấy tên ô trống) — test kiểm prompt không rò số.
- `spoken_form` ("ITN ngược", `src/dataset/spoken.py`): số/tiền/ngày/SĐT/mã đơn/mã model/tên hãng → chữ theo quy ước BTC; 10 test. Mã đơn đọc **từng chữ số** vì ITN đã khóa của normalizer đọc sai "sáu trăm nghìn lẻ một" → **600.100** (lỗi ITN thật, **chưa sửa** vì luật ASR đang khóa; ảnh hưởng cả đường chat khi khách đọc số có "lẻ" sau hàng nghìn).
- Sinh bằng **gpt-6-luna** (`reasoning_effort=low`, seed 42), lời agent dùng ô trống `{price}`… do code điền; lời thoại từng lượt cả hai phía + `text_spoken` + `entities` gắn từ khung; kịch bản ghép đúng định dạng BTC (`dataset/scenarios/`), lời thoại ở `dataset/dialogues/`. **Chi phí thật: 470,7 VND tổng 3 lần chạy (361,1 + 81,2 + 28,4; trần 500)**, tổng 49 lần gọi LLM (38 + 8 + 3), trung bình ~9,6 VND/lần. Lần 1 tốn nhiều vì **lỗi của bộ kiểm** (cấm chữ số trong tên model "RunLite 2 Pro"/size khách vừa nói; ITN đọc sai mã đơn; cùng một địa chỉ ở mọi kịch bản làm trùng câu) — đã sửa mã rồi dựng lại các cuộc cũ (không tốn LLM) và chỉ sinh lại cuộc còn lỗi. Kết quả: **0 LỖI, 1 CẢNH BÁO** (S12 C04: "mười triệu một đơn" bị ITN đã khóa hiểu thành 10.000.001 — nhập nhằng của ITN, không phải lỗi dữ liệu).
- **Lỗi nội dung phát hiện khi ĐỌC và sửa:** agent nói địa chỉ TRƯỚC khi khách đọc (B01 call_2) → luật mới `after` (ô trống chỉ dùng sau khi khách nói fact) + sinh lại; LLM tự viết teencode ở C05 → sửa lời dặn + sinh lại (teencode do mã làm); "Máy lọc không khí Máy lọc không khí AirPure Y" → gộp cụm lặp bằng mã; `forbidden_claims` của C02 có cụm "chữa được" trùng với câu từ chối đúng → đổi cụm; `spoken` "tsmười sáu"/"smột" (mã model chữ+số) → đọc từng chữ cái ("ti ét mười sáu", "ét một").
- **Điểm còn yếu bạn nên xem:** A03 call_1 khách tự thêm "chỗ khác báo giá thấp hơn" ngoài dàn ý (hợp persona nhưng thêm một blocker); A02 call_1 khách hỏi "còn hàng không" mà agent chỉ trả lời giá (chưa có ô trống tồn kho); văn phong còn lịch sự đều, ít ngập ngừng/lặp ý (đã dự đoán ở rủi ro).
- **Lựa chọn model (câu 4):** dùng gpt-6-luna, không có lý do kỹ thuật chặn (gọi được, JSON ổn, `reasoning_effort=low` được nhận; khác model agent gpt-4o-mini). Hai lưu ý: (1) giá Luna 0,10/0,50 USD/1M **chưa đối chiếu giá OpenAI chính thức** (token suy luận chiếm ~35–40% token ra, nên "rẻ hơn" chỉ đúng nếu giá đó đúng); (2) Luna cũng là model judge dự kiến (bước 14b) → judge sẽ chấm văn bản do chính nó viết (thiên vị cùng-model) — nên cân nhắc judge khác hoặc held-out do người duyệt. Chưa sinh thử bằng gpt-4o-mini để so sánh (còn ~29 VND trong trần).
- Test: **471 test, 0 đỏ** (+ `tests/test_dataset_spoken.py` 10, `tests/test_dataset_pipeline.py` 33 gồm trần chi phí/sinh lại/ô trống/các luật S1–S13; `test_slot_retriever` 46).

**Chưa làm (theo thứ tự bạn chốt, đang chờ bạn xem 10 mẫu):** chạy LLM thật 7 kịch bản × 2 cấu hình sau khi sửa bước 12 (trần 5.000 VND) → `mcp-memory` → bỏ agent A2A trên danh nghĩa + chép/cập nhật `PIPELINE.md` về `docs/`.



### 11.29. ITN v2, dataset v2, luật sinh lời thoại P1–P4, chạy D (2026-10-21) — LLM thật 1.520 VND (trần 5.000)

**1. ITN v2 (lỗi chung của tiếng Việt, không chỉnh theo tập test).** (a) `lẻ/không` sau hàng nghìn/triệu là chữ số đơn vị theo nghĩa đen: "sáu trăm nghìn lẻ một" → 600.001 (trước: 600.100); "sáu trăm lẻ một nghìn" → 601.000 (không đổi). (b) Số đếm đứng trước danh từ đơn vị (đơn, chiếc, cái, máy, bộ, đôi, …) không thuộc số tiền: "mười triệu một đơn" → 10.000.000 + "một đơn" (trước: 10.100.000); chỉ áp khi có bậc nghìn/triệu và đúng MỘT từ số cuối. Dạng chữ số ("10tr 1 đơn", "5tr2 máy") theo cùng luật; "5tr2" đứng một mình vẫn là 5.200.000. Test dương + âm (`ITNLiteralZeroAndCountNounTest`, 6 test). Khóa luật nâng `asr-rules-v1-2026-10-21` → **`asr-rules-v2-2026-10-21`** (lý do ghi trong lock; bản v1 ở `runs/asr_rules_v1/`).
**Chấm lại từ giả thuyết đã lưu** (`scripts/rescore_asr.py` → `runs/asr_rules_v2/rescore_v1_vs_v2.md`): **0 dòng đổi** — WER ITN, entity số tiền/SĐT/BTC giống hệt v1 ở cả 5 biến thể × 7 điều kiện. Nghĩa là 4 file D01–D04 không chứa hai mẫu câu này; v2 sửa lỗi thật nhưng **không chứng minh được cải thiện số đo ASR**. (Phạm vi mọi số WER: trên audio TTS sạch, giọng Bắc, n = 4 file; nhiễu/điện thoại là mô phỏng; entity 100% là trong tập phát triển D01–D04.)

**2. Dataset v1 → v2** (`docs/DATASET_CHANGELOG.md`, bản cũ đóng băng ở `generated_m1_v1/`): sửa đáp án SC-GEN-05 (bỏ `order_id` khỏi `must_carry_over`, mã đơn do mock sinh lúc chạy), SC-GEN-06 (`promo_active` false vì PUMP-GIFT hết hạn 13/10; thêm lượt khách hỏi quà), SC-GEN-11 (thêm `facts_established`, đáp án SKU-SS-AX40 6.490.000 = +8% ngân sách; `success_if.must_say_any`). Validator siết S4 (giá trong `facts_established` so với mock) và S6 (cuộc 1). `validate_scenarios`: 22 kịch bản còn **1 lỗi = SAMPLE-01 của BTC (không sửa)**. **Chấm lại trace cũ bằng GT v2:** trace A/B/C chỉ chứa SAMPLE-01…07 → số **không đổi** (báo cáo chấm lại trùng khớp `runs/buoc15_C/report.json`). Lưu ý đo: nếu đưa SC-GEN-* chưa có trace vào thư mục kịch bản, `reference_eval` tính chúng là trượt và mẫu số đổi — phải chấm trên tập kịch bản có trace.

**3. PLAN 14b** ghi: model sinh lời khách = model judge (gpt-6-luna), kiểm soát bằng kappa với người trên 20 mẫu; kappa thấp thì đổi judge sang gpt-6.1-sol (batch) hoặc nhà cung cấp khác.

**4. Luật sinh lời thoại mới** (`src/dataset/rules.py`, `scripts/check_dialogue_rules.py`, 22 test `tests/test_dataset_rules.py`; prompt `writer.RULES` + `phong_cach_hoi_thoai`; kiểm trong `write_call`/`record_errors`, lỗi được đưa lại cho LLM khi sinh lại): **P1** khách không nói thông tin ngoài cốt truyện (đối thủ, trẻ nhỏ, diện tích, ngân sách, size, màu, SĐT, số tiền lạ; tính cả fact các cuộc trước); **P2** agent trả lời ĐỦ mọi câu hỏi trong lượt khách (giá/còn hàng/khuyến mãi/bảo hành/đổi trả/giao hàng/thanh toán; câu trả lời "còn hàng" lấy từ ô `{stock}` tự thêm vào khung từ `inventory_check`, không để LLM bịa; từ chối/chuyển nhân viên hợp lệ cũng tính là trả lời); **P3** 5 hồ sơ phong cách theo persona/số cuộc (cộc lốc, ngập ngừng, chen ngang–đổi chủ đề, nhờ nhắc lại — agent phải nhắc lại cùng thông tin, cuộc ≥ 3 hết kiên nhẫn) + chung: ≥ 25% lượt khách ≤ 6 từ, tỉ lệ lượt lịch sự có trần; **P4** teencode chỉ ở kênh chat, hotline không viết tắt kiểu chat/không có `text_asr`.
**Áp lên 10 mẫu hiện có (chưa sinh lại, 0 VND):** 17/17 cuộc vi phạm ≥ 1 luật — chủ yếu P3 (33 lỗi: lời khách đều dài, quá lịch sự, thiếu ngập ngừng — đúng nhận xét "quá đều"); P1 2 (A03 call_1 "chỗ khác báo giá thấp hơn", C01 call_1 "bên khác báo mềm hơn"); P2 2 (A02 call_1/call_2 khách hỏi còn hàng không được trả lời). Hai ca báo nhầm lúc đầu ("còn nhớ" bị đọc là "con nhỏ"; "Giá đã gồm quà tặng…?" bị tính là hỏi giá) đã sửa luật + test. **Chạy lại `generate_dataset_text.py` sẽ sinh lại các cuộc này (tốn tiền) — chưa chạy; còn ~29 VND quota mẫu.** Heuristic từ khóa nên có thể báo nhầm/bỏ sót; kết quả cuối vẫn do người đọc.

**5. Chạy D (bước 12 + ITN v2 + dataset v2; 7 kịch bản × 2 cấu hình × 1 seed 42, stdio MCP) — chi phí 1.520 VND** (`runs/buoc15_D/`):

| Chỉ số (A.6) | Baseline | Hệ thống | (C: base → hệ thống) |
|---|---|---|---|
| RQR | 6,7% (1/15) | **0,0%** (0/17) | 17,6% → 7,7% |
| CCR (BTC) | 9,5% | **71,4%** (15/21) | 14,3% → 52,4% |
| TSR | 71,4% (5/7) | **100%** (7/7) | 57,1% → 71,4% |
| HR giá & KM | 37,5% (3/8) | **0,0%** (0/8) | 74,3% → 30,0% |
| Guardrail | 0 | 0 | 0 |
CCR chặt (`fair_rescore`): baseline 33,3%, full 66,7% (C: 38,1% / 47,6%). HR trích lại: không claim nào đổi.
- **Số lần gọi LLM/lượt:** full **2,59** (C: 2,46; không tính trích slot cuối cuộc: 13 lần như C), tối đa 4; baseline 2,72. Vòng LLM trước token đầu TB 1,59 (C 1,46). Chi phí/lượt 20,8 VND (C 18,7) — tăng nhẹ, **chưa đạt tiêu chí "số lần gọi LLM/lượt không tăng"** của bước 12 (2,46 → 2,59); chênh nằm trong nhiễu của 1 seed nhưng không được coi là "không tăng".
- **Kịch bản tụt so với C: 0/7.** full thua baseline: 0/7 (C: 3/7). SAMPLE-01 nay chốt đúng AirPure Y (khóa trẻ em; `product.shortlist` gọi 2 lần, cả hai `decision.mode = single`) mà trong mã/prompt không có tên SAMPLE-01/AirPure; SAMPLE-05 hết lỗi `basket_skus`. Tool error full 2 (`unknown_sku`) vs C 5; baseline 7 vs 17.
- **Nhánh hai lựa chọn (vượt ngân sách > 20%): không kịch bản nào rơi vào** (0/2 lần shortlist ở chế độ `two_options`) → nhánh này **chưa được đo bằng LLM thật**, chỉ có test đơn vị.
- Còn sai: budget_vnd bỏ sót ở SAMPLE-01/06 (slot LLM cuối cuộc), SAMPLE-01 GT 5,7tr của BTC (không sửa); objection SAMPLE-02 ghi 'cân nhắc thêm' thay 'dat_qua'.
- **Giới hạn:** 7 kịch bản / 39 lượt / 1 seed; baseline cũng dao động mạnh giữa C và D (HR 74,3% → 37,5%, RQR 17,6% → 6,7%) dù không đổi mã → chênh lệch này không phải số nộp bài, chỉ xác nhận không có hồi quy và bước 12 hoạt động trên 7 mẫu công khai.
- Test: **500 test, 0 đỏ** (tăng từ 471: +6 ITN, +22 luật dataset, +1 khác); 3 test `WriterTest` phải sửa lời thoại mẫu cho khớp luật phong cách mới.

**Dừng theo chỉ đạo.** Tiếp theo (chờ bạn): sinh 54 kịch bản (cần khung cho 54 kịch bản + trần 5.000 VND) → `mcp-memory` → gỡ A2A + `PIPELINE.md`.



### 11.30. Order gate, xưng hô, giá đối thủ, liệt kê mẫu + sinh lại 10 mẫu + khung 54 kịch bản (2026-10-21)

**Run D (§ 11.29) = 7 kịch bản × 1 seed, 39 lượt: chỉ chứng minh KHÔNG HỒI QUY, không phải số nộp bài.**

**1. Order gate (mới — trước đó KHÔNG có; lỗi đặt đơn bạn thấy trên UI là có thật).** `src/harness/order_gate.py` + nối vào `HarnessOrchestrator` (đứng TRƯỚC MCP; chỉ có 2 chỗ gọi `order.create` trong orchestrator và đều qua gate — có test đếm).
- Checklist: sản phẩm + biến thể (size/màu nếu có), số lượng, tên người nhận, SĐT nhận, địa chỉ, thanh toán. Mỗi trường: `stated` (khách NÓI trong cuộc gọi — đối chiếu với lời khách, giá trị LLM tự điền mà khách chưa nói KHÔNG được tính) · `confirmed` · `known` (có sẵn trong bộ nhớ/CRM/số đang gọi nhưng chưa xác nhận → câu XÁC NHẬN) · `missing` (→ câu HỎI, tối đa 2 mục/lượt).
- Đủ checklist → ĐỌC LẠI ĐƠN một lần → chỉ tạo đơn khi lượt NGAY SAU khách đồng ý RÕ RÀNG (`is_explicit_consent`: có từ đồng ý, không phủ định/do dự/câu hỏi/điều kiện, ≤ 14 từ) và lời gọi khớp đúng đơn đã đọc lại. Khách sửa gì → đọc lại lần nữa; không đồng ý ở lượt ngay sau → bản đọc lại hết hiệu lực; "ok" trước khi được đọc lại đơn không tạo đơn.
- Lời gọi bị chặn KHÔNG nằm trong `tool_calls` của trace (để không bị tính là đã tạo đơn); ghi ở khóa trace `order_gate` (hành động, trường thiếu/cần xác nhận, câu cần nói). Tham số `recipient_name`/`recipient_phone` chỉ ở phía LLM/gate (gỡ trước MCP và trước trace) — schema BTC của `order.create` không có trường người nhận. Địa chỉ/tên/SĐT nhận/thanh toán được lưu vào bộ nhớ sau khi tạo đơn (`shipping_address`, `recipient_name`, `recipient_phone`, `payment_method`; PII: giá trị KHÔNG vào `memory_writes` của trace, xóa được bằng `delete_customer`) → lần sau chỉ cần XÁC NHẬN.
- **Bộ điều khiển bằng code (phát hiện từ run F):** khi khách đang trả lời câu hỏi/xác nhận/đọc lại của gate, CODE cập nhật đơn nháp (địa chỉ/SĐT/thanh toán/tên khách vừa nói), chạy lại gate và tạo đơn khi khách đồng ý — LLM không cần (và không được tin) để chuyển tiếp từng bước (ở run F, LLM không gọi lại `order.create` sau khi khách trả lời → chỉ 2/6 đơn hoàn tất). Khách hỏi chen/đổi sản phẩm → LLM xử lý, code nối bước kế tiếp của gate. COD vượt hạn mức → giải thích rồi chuyển khoản → đọc lại → chốt. SKU LLM truyền là TÊN sản phẩm ("AirPure Y") được chuẩn hóa ngay khi gate nhận đơn nháp. Địa chỉ không còn nuốt cụm "thanh toán COD" đi kèm.
- **Test** (`tests/test_order_gate.py`, 31): khách mới đủ luồng; khách cũ có địa chỉ lưu (chỉ xác nhận); "ok" trước khi đọc lại; giao cho người khác (SĐT nhận đọc lại); đổi size/đổi ý sau khi nghe đọc lại; không đi theo lời đồng ý muộn/kèm điều kiện; LLM bịa tên/địa chỉ không được tính; lời "đã lên đơn" khi bị chặn bị thay; nhánh rule-based không né được gate; COD vượt hạn mức; trợ lý đánh giá. Cổng có cờ `enabled` CHỈ để test đơn vị các cơ chế khác (runner/UI/main luôn bật); helper test mặc định tắt.
- **Lưu ý về chỗ đặt cổng:** bạn yêu cầu "Gateway chặn order.create"; cổng nằm trong orchestrator, đứng trước `MCPToolGateway` (điểm gọi duy nhất, có test). Server `mcp-crm` KHÔNG tự kiểm gate (ai gọi thẳng MCP vẫn tạo được đơn, chỉ bị chặn bởi phân quyền caller) — nếu muốn chặn cả ở phía server thì đó là việc thêm.

**2. Xưng hô** theo cách khách TỰ xưng ("anh muốn hỏi…", "cho chị hỏi…"; "em" chỉ nhận với động từ không thể là lời gọi nhân viên), ưu tiên hơn CRM, lưu vào bộ nhớ (`honorific`). Khách xưng "em" → nhân viên gọi "bạn" (tránh trùng ngôi). **3. Giá nơi khác** ("bên shop kia có 300k") ghi slot `competitor_price_vnd` bằng regex mỗi lượt; "rẻ hơn 500k" là mức chênh, không phải giá. **4. Liệt kê mẫu:** `catalog.search`/`product.shortlist` trả 0 mẫu với câu tự nhiên ("các mẫu máy lọc nước nào", "xe đẩy em bé"; mock BTC đòi MỌI từ nằm trong tên/hãng/danh mục) và cắt ở 3 mẫu → so khớp chịu câu tự nhiên (`src/catalog/textmatch.py`: bỏ từ đệm, không dấu, ≥ 60% từ) + `list_all` do CODE nhận ra ý định liệt kê (không để LLM tự bật: lần đầu để LLM bật làm nó liệt kê cả khi khách chỉ hỏi tư vấn — hồi quy ở SAMPLE-01 run E) + hướng dẫn "nêu đủ mọi mẫu" chỉ nằm trong KẾT QUẢ tool khi khách hỏi liệt kê (để system prompt không đổi hành vi tư vấn thường). Test: mọi danh mục × 6 cách hỏi → đúng tập mẫu theo `products.json`; câu về hàng không có → 0 mẫu.

**5. Đo 7 kịch bản × 2 cấu hình (LLM thật, seed 42; 1 seed, 7 kịch bản — chỉ là kiểm tra, không phải số nộp):**

| run | cách chạy | TSR full (base) | đơn tạo được | lượt | gọi LLM/lượt full | VND |
|---|---|---|---|---|---|---|
| D (trước gate) | lời khách kịch bản | **100%** (71,4%) | 6 | 39 | 2,59 | 1.520 |
| E (gate, tập lệnh cố định) | lời khách kịch bản | **14,3%** (14,3%) | **0** — 6/6 lần `order.create` đầu bị chặn | 39 (không đổi) | 2,51 | 1.728 |
| F (gate, `--gate-assist`, LLM chuyển tiếp) | + khách mô phỏng | 42,9% (28,6%) | 2/6 | 47 | 2,47 | 2.095 |
| G (gate + bộ điều khiển code, `--gate-assist`) | + khách mô phỏng | **71,4%** (57,1%) | 4/6 (base 5/6) | 49 | **2,04** (10 lượt không cần LLM) | 1.696 |
| I (bản cuối; chỉ cấu hình full) | + khách mô phỏng | **85,7%** | **6/6** | 51 | **1,94** (12 lượt không cần LLM) | 857 |

(+ chạy riêng SAMPLE-01 sau khi sửa SKU: 180 VND — đơn tạo được.)
- **Số đơn bị gate chặn:** mỗi đơn bị chặn đúng 2 lần trước khi tạo: 1 lần HỎI/XÁC NHẬN (thiếu địa chỉ, thanh toán; SĐT nhận/tên cần xác nhận) + 1 lần ĐỌC LẠI ĐƠN (run I: 6 ask_confirm + 6 readback + 6 allow). **Lượt tăng thêm: +2 lượt khách mỗi đơn** (run I: 51 − 39 = 12 lượt khách mô phỏng cho 6 đơn); lượt bị chặn dùng câu do code dựng nên **không tăng số lần gọi LLM** (1,94/lượt, thấp hơn run D 2,59).
- **TSR thay đổi?** Có — và phải đọc đúng: lời khách của kịch bản BTC là CỐ ĐỊNH (2–4 lượt) nên không thể trả lời câu hỏi/đọc lại đơn của gate → **TSR 100% → 14,3% khi chạy nguyên văn kịch bản** (0 đơn tạo được; đó là bản chất của quy trình "hỏi–đọc lại–đồng ý" của bạn, không phải lỗi). Với khách mô phỏng hợp tác (**không phải số liệu nộp**; lượt chèn gắn `_injected` trong trace; dữ liệu mẫu cố định: địa chỉ mẫu + COD + "đúng rồi/ok em") TSR trở lại 85,7% (6/7); 1 kịch bản trượt là SAMPLE-01 (LLM chọn AirPure X thay vì Y — lỗi chọn sản phẩm đã biết, dao động theo lần chạy, không liên quan gate). **Nếu BTC chấm bằng lời khách cố định, order gate sẽ làm TSR của mọi kịch bản có đặt đơn về 0 — cần bạn quyết định có chấp nhận đánh đổi này không** (chấm BTC thật cần một "khách mô phỏng" hợp tác, nếu không gate phải có chế độ tắt).
- **CCR giảm** (run D 71,4% → G 52,4% → I 47,6%) và **HR run I 15,4% (2/13)**: chưa tìm đủ nguyên nhân; ở SAMPLE-01 call_1 LLM đôi khi truyền tên sản phẩm làm SKU nên `product_advised` không được ghi (đã sửa chuẩn hóa SKU), còn lại là dao động 1 seed + prompt đổi — **cần chạy ≥ 3 seed mới kết luận**.
- **Chi phí cả mục này: 6.556 VND** (E 1.728 + F 2.095 + G 1.696 + SAMPLE-01 180 + I 857) — **vượt trần 5.000 bạn duyệt cho "một lần chạy"** (mỗi lần riêng đều dưới trần; F và G là chẩn đoán lỗi tôi phát hiện khi chạy).
- Chưa chạy lại cấu hình baseline ở bản cuối (chỉ run G có baseline với gate).

**6. Sinh lại 10 mẫu (gpt-6-luna, seed 42): 999,7 / 1.000 VND** (672,3 lần 1 + 327,4 lần 2 chỉ sinh lại cuộc còn lỗi). Luật P1–P5 (P5 = order gate: hỏi/xác nhận → đọc lại đơn → khách đồng ý rõ ràng ở lượt ngay sau → mới chốt; khung có `{readback_total}`, `{payment_label}`, `{recipient_name}`, `{caller_phone}`). **Vi phạm luật: trước 17/17 cuộc (45 lỗi: P3 33, P5 8, P2 2, P1 2) → sau 1/17 cuộc (1 lỗi P3 ở SC-B01 call_3)**; còn **1 lỗi kiểm tra kịch bản**: S3 SC-C03 (fact `blocker` gắn nhãn nhưng khách không nói đúng giá trị). 0 vi phạm P5. Sửa sau khi đọc kết quả lần 1: lượt ĐỒNG Ý ngắn lặp giữa kịch bản không còn bị S10 coi là trùng; persona "gọi lần 3" chỉ cạn kiên nhẫn từ cuộc 3; mô tả persona "nhắc giá đối thủ" không còn khiến LLM tự thêm lời so giá (P1). Lỗi còn thấy khi đọc: "còn hàng hiện còn hàng" (LLM viết "còn hàng" trước ô `{stock}`) — chưa sửa. Bản cũ: `dataset_v1/` (+ `rules_report_before.txt`); bản sau lần 1: `dataset_regen1/`; **bản mới nhất: `dataset/`** (`dataset/review/sample10.md`; báo cáo luật: `dataset/reports/rules_report_after.txt`).

**7. Khung 54 kịch bản (CHƯA sinh lời thoại, 0 VND; chờ bạn duyệt):** `src/dataset/frames54.py` (14 kiểu × tham số, đáp án do mock + `ProductRetriever` tính), `scripts/frames54_report.py` → `dataset/review/frames54_distribution.md` (bảng phân bố: nhóm/số cuộc/persona/ca khó/kênh/ngành/miền/kiểu) + `frames54_random5.md` (5 khung ngẫu nhiên seed 42) + `dataset/frames54/SC-Dxx.frame.json` (đủ 54). 54 kịch bản = A 13 + B 10 + C 31 → **87 cuộc** (+17 mẫu +31 hiện có = **135 cuộc**, đúng cơ cấu đã duyệt); **4 ca vượt ngân sách > 20% (nhánh hai lựa chọn; yêu cầu ≥ 3)** và **3 khách cũ có sẵn địa chỉ (gate chỉ xác nhận; yêu cầu ≥ 2)**; 45 cuộc có tạo đơn đều đi qua gate. 10 test (`tests/test_frames54.py`). Hạn chế: 10/12 persona BTC (thiếu `hai_nguoi_chung_sdt`, `khach_da_kenh_mau_thuan`); 3 cuộc teencode; ca "đổi size" SC-D14 có phụ thu 219.000đ (gồm mất KM RUN-10 `once_per_customer` + phụ thu biến thể — đúng hành vi mock).

**Dừng theo thứ tự bạn chốt:** chờ bạn đọc `dataset/review/sample10.md` (bản MỚI) và duyệt khung 54 → sinh 54 → mcp-memory → gỡ A2A + PIPELINE.md.


### 11.31. Quyết định về order gate, tách hai loại đo, run chẩn đoán 3 seed, trần chi phí cứng + sửa 6 lỗi người dùng thấy trên UI (2026-10-22)

**A. Quyết định của người dùng (đã làm):** order gate **luôn bật ở mọi cấu hình** (demo, UI, eval). `OrderGate.enabled` chỉ đọc; chỉ `tests/_helpers.py` gọi được `disable_for_unit_tests()`; có test quét mã nguồn (không cờ/biến môi trường/hàm tắt nào ngoài tests/) và test mọi entrypoint (`ScenarioRunner._new_stack`, `CallCenterHarnessPipeline`) dựng cổng ở trạng thái bật.
**Đo lường TÁCH HAI LOẠI** (`src/eval/gate_metrics.py`, `scripts/gate_report.py`; `run_eval.py` và `analyze_run.py` tự in, kèm lưu ý ở dòng TSR của reference_eval): **[1] TSR tương tác (TSR chính)** — khách mô phỏng (`--gate-assist`, lượt chèn `_injected`), đạt = `order.create` đúng SKU/giá SAU khi khách xác nhận (lượt ngay trước có bước đọc lại + lượt tạo đơn là lời đồng ý rõ ràng); dùng cho 54 kịch bản mới (chưa sinh). **[2] Kiểm tra kịch bản cố định (7 mẫu BTC)** — KHÔNG tính vào TSR chính; đạt = không tạo đơn sớm + đã tới bước đọc lại đơn. `run_eval.py --gate-assist` bị **từ chối** với kịch bản BTC (các run F/G/I trước đó là chẩn đoán, không phải số báo cáo). 13 test (`tests/test_gate_metrics.py`).
**Kết quả loại [2] trên 7 mẫu BTC chạy nguyên văn (3 seed, cấu hình full):** đạt **0/5** cuộc có tạo đơn: **0 đơn tạo sớm (5/5 đúng)**, **5/5 đã vào bước hỏi/xác nhận của gate, 0/5 tới bước đọc lại đơn** — vì lời khách của BTC không bao giờ trả lời câu hỏi của gate. Đây là số trung thực theo đúng điều kiện bạn đặt; nó không phải lỗi mà là bản chất của kịch bản cố định.
**Trần chi phí CỨNG trong mã:** `CostTracker.hard_cap_vnd` kiểm TRƯỚC MỖI lần gọi API (kể cả vòng giữa lượt — chi phí các vòng chưa ghi được cộng tạm), `BudgetExceeded` kế thừa `BaseException` (không bị `except Exception` của orchestrator/bộ trích nuốt rồi chạy tiếp), runner ghi nốt dòng trace đang chờ rồi dừng. `run_eval.py` luôn bật trần (mặc định 1.500 VND, phải > 0 — **không còn chế độ chạy không trần**); `scripts/diagnose_seeds.py` có trần 3.000 VND làm hằng số trong mã (chạm trần thì dừng, giữ trace, báo phần đã có); `scripts/ui_replay.py` trần 400 VND. 8 test (`tests/test_cost_cap.py`). Tìm ra thêm 1 lỗi: `run_eval --repeats` dùng chung 1 `LLMClient` nên **seed LLM không đổi giữa các lần lặp** — đã sửa (`run_all` đặt `llm_client.seed = seed`).

**B. Run chẩn đoán 3 seed (42, 43, 44; cấu hình full; 7 mẫu BTC; KHÔNG chèn lượt; tổng 2.344,8 VND < trần 3.000).** `runs/diag_3seeds/diagnosis.md`.
| lần chạy | lượt | RQR | CCR (BTC) | CCR chặt | HR giá&KM | VND |
|---|---|---|---|---|---|---|
| D (trước gate) | 39 | 0,0% | 71,4% | 66,7% | 0% (0/8) | 772 |
| I (gate + khách mô phỏng) | 51 | 3,7% | 47,6% | 47,6% | 15,4% (2/13) | 816 |
| s42 / s43 / s44 | 39 | 4,0 / 4,2 / 4,2% | 61,9 / 61,9 / 61,9% | 57,1% | **0% (0/10, 0/11, 0/10)** | 763 / 771 / 701 |
- **Hai claim sai của HR (run I, SAMPLE-01/call_2 lượt 2 và 4):** cả hai là **giá 4.890.000đ (AirPure X)** trong khi đáp án 5.200.000đ (AirPure Y) — agent **chọn nhầm sản phẩm** (lượt 4 là câu đọc lại đơn "1 Máy lọc không khí AirPure X, giá 4.890.000đ" — giá ĐÚNG của X, có căn cứ `pricing.get_quote`); không phải bịa giá (0/38 claim tiền không có căn cứ tool). **3 seed sau không còn claim sai nào** → là dao động chọn sản phẩm (lỗi đã biết của SAMPLE-01), không phải lỗi giá. (Bộ phân loại ban đầu ghi lượt 2 là "bịa/nhầm số" vì không đọc giá nằm trong kết quả `catalog.search`; đã sửa bộ phân loại.)
- **CCR 71,4% → 47,6% (run I) — nguyên nhân từng slot** (so D với I; bảng đầy đủ ở diagnosis.md § 3): **4 slot**: (1–2) SAMPLE-01 `product_advised` + `price_quoted_vnd` — ở cuộc 1 LLM gọi `pricing.get_quote` bằng **tên sản phẩm** ("AirPure Y") → `unknown_sku`, không có báo giá nên không có gì để ghi nhớ; D tự hồi phục (gọi lại bằng SKU), I không. **Đã sửa** (chuẩn hóa SKU cho `pricing.get_quote`/`inventory.check` + `order.create`): cả 3 seed sau ✔ ở cả hai slot. (3) SAMPLE-01 `blocker`: "khách đã nhắc lại" — dao động (I ✗, 3 seed ✔). (4) SAMPLE-04 `promo_code`: agent không nhắc KM — ✔ ở D, **✗ ở cả 4 lần chạy sau khi thêm gate/prompt** (có thể do đoạn quy trình đặt đơn thêm vào system prompt; chưa xác minh). Cộng thêm khi chạy **kịch bản cố định** (s42–44 = 61,9%): SAMPLE-03 `order_id` + `variant_sku` ✗ vì gate chặn tạo đơn ở cuộc 1 (kịch bản không trả lời được) nên cuộc 2 **không có mã đơn để mang sang** — hệ quả trực tiếp của gate trên lời khách cố định, không phải lỗi bộ nhớ. 7 slot ✗ ở MỌI lần chạy kể cả D (SAMPLE-02 product/competitor/objection, SAMPLE-03 size, SAMPLE-05 price/promo…) là lỗi/giới hạn cũ, không liên quan thay đổi gần đây.

**C. Sáu lỗi trên UI demo — nguyên nhân và vì sao test không bắt được.** Ảnh chụp 2026-10-22 (SĐT 0986886113 hotline, và Zalo → hotline). Test xanh là vì test viết **lời khách chuẩn do chính mã viết ra** (viết hoa, đủ cụm "Tên người nhận là Lan"), LLM giả theo kịch bản, và chỉ kiểm cơ chế riêng lẻ; chưa có test hội thoại gõ tay thật nào. Chạy kịch bản BTC/khách mô phỏng cũng không phát hiện vì lời khách cố định không chứa các tình huống này.
1. **"Chưa nhận biết tên người mua" + 4. "lặp câu"** — (a) `extract_recipient_name` đòi tên **viết hoa** và đứng sau cụm dẫn; khách gõ "đại, COD", "đại", hoặc đặt tên cuối câu địa chỉ ("…hồ chí minh, Đại") nên không nhận → gate hỏi lại tên 3 lần; (b) địa chỉ nuốt luôn ", Đại"; (c) **tên khách tự nói ("tôi tên Đại") không hề được lưu** — chỉ có tên CRM, nên Call Brief vẫn "Quý khách"; (d) gate **không có chống lặp**.
2. **"Không cập nhật blocker"** — blocker/objection là "slot khó" chỉ được LLM trích ở **cuối cuộc gọi**, mà UI không có nút/đường nào kết thúc cuộc gọi → dashboard luôn "Không có".
3. **"Không hiểu mặc cả"** — LLM gọi `order.create` với giá khách đề nghị (6.800.000) → gate coi là đơn bình thường, hỏi địa chỉ; sau khi khách từ chối ("không, mắc quá…", "chưa cần, sẽ gọi lại sau") **đơn nháp vẫn mở** nên mọi lượt sau bị nối câu "cho em xin địa chỉ…" (cũng là nguồn của lỗi lặp câu). Không có luật mặc cả nào trong prompt.
5. **"Không chuyển thông tin xưng hô"** — khách chỉ nói "tôi" (không lộ giới tính); LLM tự đoán "anh Đại" từ tên rồi lượt sau lại "anh/chị" vì xưng hô đoán **không được lưu**; tên cũng không được lưu (mục 1c).
6. **"Chuyển kênh không nhận ra khách"** — thiết kế nhận diện nối kênh **chỉ qua SĐT**: phiên Zalo để trống ô SĐT nên là khách ẩn danh; sang hotline với SĐT khác thì hệ thống không có căn cứ nối (không được nối theo tên/lời khai vì sẽ lộ dữ liệu người khác). Lỗi thật là **agent không hỏi SĐT/tài khoản đã dùng**.
Lỗi phụ phát hiện khi xem ảnh và phát lại: agent báo **"hết hàng"** cho 38 đen (còn 5) và vẫn xin địa chỉ — `catalog.search("38 đen")` trả rỗng (mock đòi mọi từ khớp tên) và LLM hiểu rỗng = hết hàng; **`_strip_diacritics` không tách "đ" nên "đen" không bao giờ khớp màu "den"** của catalog (lỗi tiềm ẩn ở tầng 2 của bộ sửa SKU từ lâu); LLM chỉ truyền SKU cha dù khách đã nói size/màu → gate hỏi lại "chọn size và màu nào"; màu hiện "den" không dấu; câu "ạ ạ?" và câu bị nối lặp "xác nhận lại… xác nhận lại…"; "ừ" bị nhận là TÊN (lỗi do chính test mới phát hiện); UI nhận ngày "2026-15-10"/"2026-11-1" không báo lỗi và luôn dùng `call_1`.
**Đã sửa (mỗi mục có test hồi quy dựng từ lời khách trong ảnh — `tests/test_ui_regressions.py`, 28 test):** nhận tên viết thường/cuối câu/cạnh thanh toán (loại từ đệm, số, địa chỉ, từ thanh toán), tách tên khỏi địa chỉ, **lưu `customer_name` khách tự nói** (không ghi đè tên CRM; "tôi là vị khách…" không bị nhận nhầm); **chống lặp** (lần hỏi lại đổi cách nói + ví dụ định dạng; lần 3 bỏ đơn nháp lịch sự); **khách từ chối/mặc cả/hẹn lại hủy đơn nháp** (không nối câu hỏi nữa); **giá khách đề nghị ≠ bảng giá → chặn `price_mismatch`, nói giá thật, không mở đơn** (LLM chỉ nhầm giá thì tự sửa theo báo giá); **hết hàng → chặn trước khi hỏi địa chỉ**; luật MẶC CẢ + XƯNG HÔ (không đoán giới tính từ tên; chỉnh "anh Đại"/"anh" trần về "anh/chị…" khi chưa rõ) + NHẬN DIỆN KHÁCH (hỏi SĐT/tài khoản đã dùng khi khách nói đã liên hệ mà hồ sơ trống; xin SĐT ở kênh chat) trong prompt/ngữ cảnh; **blocker/objection bằng regex mỗi lượt** (Call Brief cập nhật ngay) + nút **"Kết thúc cuộc gọi"** trên UI (chốt bộ nhớ, tăng số cuộc) + kiểm ngày YYYY-MM-DD; `catalog.search` rỗng → tra lại biến thể bằng size/màu khách nói, trả danh sách **không rỗng** kèm tồn kho thật (hoặc liệt kê size/màu thật), sửa lỗi "đ"; biến thể lấy từ lời khách (lần nhắc gần nhất thắng); màu có dấu; câu hỏi của gate dựng lại gọn.
**Phát lại bằng LLM thật** (`scripts/ui_replay.py`, lời khách chép từ ảnh, trần 400 VND; lần cuối 107,6 VND cho cuộc A): mặc cả → agent nói giá thật và đề nghị nhân viên, không xin địa chỉ; từ chối → không nối câu hỏi; `blocker='de suy nghi'`, `objection='gia cao'`, `customer_name='Đại'` có ngay trong bộ nhớ; khách đã liên hệ kênh khác → agent hỏi SĐT/tài khoản đã dùng; cuộc A: tên cuối câu địa chỉ + "đại, COD" nhận đúng, **đọc lại đơn đúng (38, màu đen, giao cho Đại, địa chỉ không dính tên, COD)**. **Còn lỗi (LLM):** ở cuộc A agent đôi khi vẫn **nói "không có sẵn" cho 38 đen** dù kết quả tool ghi `in_stock=True` (LLM bám câu trả lời "hết hàng" ở các lượt trước trong lịch sử) — chưa có kiểm tra tất định lời nói-so-với-tồn kho; **liên thông kênh Zalo ẩn danh → hotline bằng SĐT khác vẫn không tự nhận ra** (chủ ý, không nối theo lời khai).

**Test:** 614 test, 0 đỏ (tăng từ 560: +13 đo lường gate, +8 trần chi phí, +28 hồi quy UI, +các test gate/đo mới).


### 11.32. Bước 19 (tiếp) — `mcp-memory`: MCP server thứ 3, nơi ghi duy nhất của bộ nhớ (2026-10-22) — KHÔNG gọi API

**Kiến trúc "một nơi ghi duy nhất" (đúng phương án đã chốt ở § 11.27).** Chỉ tiến trình `mcp-memory` (`mcp_servers/memory_server.py`) giữ `MemoryService` và mở SQLite; orchestrator, Call Brief, IdentityResolver, UI, bộ chạy đánh giá là CLIENT (`src/memory/remote.py::RemoteMemoryService`, cùng giao diện `MemoryService`, nên các thành phần gần như không đổi). Mỗi file DB có đúng MỘT `MemoryService` trong server (nhiều client cùng đường dẫn dùng chung, đếm tham chiếu) → không có hai bên tranh nhau ghi, không có bản cache lệch. Giao dịch theo lượt (`begin_turn` … `drain_writes`/`abort_turn`) nằm trong server; `close` ở tham chiếu cuối chốt giao dịch + checkpoint WAL.
- **19 tool**: `memory.open/close/begin_turn/drain_writes/abort_turn/working_get/working_set/profile_set/profile_get/facts_by_channel/profile_versions/episode_add/episodes_get/merge_customer/delete_customer/query_policy/identity_links_load/identity_link_save/admin_audit`. Tool là `async def` gọi thẳng mã đồng bộ trên một vòng lặp → mọi lời gọi tuần tự, SQLite chỉ bị đụng từ một luồng. Kết quả **không** qua `strip_internal` (`Guarded(strip=False)`): khóa dữ liệu bắt đầu bằng `_` là dữ liệu, kết quả không đi tới LLM; tham số của mỗi tool gói vào một dict để `None` là giá trị hợp lệ (vd `value=None`).
- **Phân quyền theo caller** (`config/mcp_permissions.json` v2, mặc định từ chối, kiểm ở server): mỗi thành phần có view riêng (`memory.as_caller("CallBriefBuilder")`…). `CallBriefBuilder`, `StreamlitUI` chỉ đọc; `HarnessOrchestrator` đọc/ghi bộ nhớ cuộc gọi nhưng không xóa khách/gộp hồ sơ/mở–đóng kho; `IdentityResolver` chỉ ghi fact kênh/xưng hô, gộp hồ sơ, liên kết định danh; `HarnessCore` (pipeline) mở/đóng kho và giao dịch lượt; **xóa khách chỉ `Operator`** (+ `SeedScript`, `EvalRunner`, `TestHarness`; test: caller khác bị từ chối, khách khác không bị đụng); `SeedScript` nạp demo; `EvalRunner`/`TestHarness` toàn quyền. Nhật ký kiểm toán server không chứa tham số (test: SĐT/địa chỉ không xuất hiện), có ghi lượt bị từ chối.
- **Nối vào**: `pipeline.py` (mặc định `stdio`), `ScenarioRunner._new_stack` (đóng kho sau mỗi kịch bản và khi dừng giữa chừng, kể cả trần chi phí), `run_eval.py`/`diagnose_seeds.py` đặt `MEMORY_TRANSPORT=stdio` mặc định, `main.py` (seed qua view `SeedScript`), `ui_app.py` (view `StreamlitUI`; timeline dùng `profile_versions` — mã cũ lặp `profile._store.items()` là danh sách phiên bản nên sẽ lỗi), `tests/_helpers.py`. `MEMORY_TRANSPORT`: `stdio` (tiến trình riêng) | `inproc` | `local` (mặc định của test).
- **Khác biệt so với bản cục bộ (chủ ý)**: dữ liệu trả về là BẢN SAO (đổi phải qua `set_working`/`add_episode`; orchestrator vốn đã làm vậy); tên trường working lạ → `MemoryServerError` thay vì `TypeError`; listener xóa khách chạy phía client sau khi server xóa.
- **Lỗi tìm ra khi viết test**: cờ "đã đóng" của kho được đặt TRƯỚC khi server chấp nhận nên caller bị từ chối quyền vẫn làm kho bị đánh dấu đóng (và caller sau đóng được) — đã sửa (đặt sau khi thành công).

**Test**: `tests/test_mcp_memory.py` 24 test (đủ 19 tool; một chuỗi thao tác cho kết quả Y HỆT bộ nhớ cục bộ, cả qua `inproc` lẫn `stdio` là tiến trình riêng, pid khác; phân quyền Call Brief/UI/Orchestrator/IdentityResolver/caller lạ; hai client cùng DB dùng chung một người ghi + đếm tham chiếu; commit/rollback theo lượt trong server; dữ liệu còn sau khi mở lại + WAL checkpoint; xóa khách sạch ba bảng + listener; link định danh lưu qua server; chạy kịch bản BTC SAMPLE-01/04 qua runner: trace `agent_text`/`memory_writes`/`facts_used`/`claims`/`questions`/`_brief_*` giống hệt `local` vs `inproc`; không rò kho khi chạy baseline). **Toàn bộ bộ test cũ vẫn xanh trên cả hai đường: `local` 614/614; `MEMORY_TRANSPORT=inproc` 638/638 (614 + 24 mới; test pipeline luôn đi qua `stdio`).** Test cũ đổi: `test_permissions_file_covers_every_tool…` tính thêm 19 tool `memory.*`.

**Chi phí MCP** (`python scripts/bench_memory.py`, 200 lần/thao tác, `runs/memory_overhead.json`; máy dev, nhánh không-LLM): mỗi lời gọi bộ nhớ qua **stdio p50 1,7–1,9 ms (p95 ≤ 2,8 ms)**, inproc ~0,5–0,7 ms, cục bộ ~0; khởi động server một lần **4,3 s** (stdio). Trên 13 lượt của SAMPLE-01/04: **15,5 lời gọi bộ nhớ/lượt, ~45 ms/lượt trong MCP (stdio)**, so với ~1.000 ms mỗi vòng LLM (~2,5 vòng/lượt) → ≈ 2% độ trễ lượt. Một phần (đọc fact/working trước khi gọi LLM) cộng vào TTFT.

**Chưa làm / hạn chế**
- **Chưa chạy `run_eval.py` thật (LLM) trên kiến trúc MCP đầy đủ** — cần bạn duyệt trần chi phí; test ở trên dùng nhánh không-LLM.
- **Hai phiên đồng thời trên cùng DB**: các client cùng file DB dùng chung một `MemoryService` nên ngữ cảnh lượt (`begin_turn`) và nhật ký ghi bị trộn nếu chạy xen kẽ — UI hiện một phiên nên chưa vướng; bước 17 (≥ 2 phiên) cần ngữ cảnh lượt theo phiên.
- `scripts/seed_demo_db.py` chạy độc lập vẫn mở DB bằng `MemoryService` cục bộ — không chạy khi có server đang giữ cùng file DB (`main.py` đã seed qua server).
- Còn lại của bước 19: bỏ/nối agent A2A chỉ có trên danh nghĩa (`src/agents/specialists.py`, `src/eval/{improvement,human_gate}.py`), chép/cập nhật `PIPELINE.md` về `docs/`.


### 11.33. Sửa 3 phát hiện đầu của audit (2026-10-24) — mỗi cái có test THẤT BẠI trước khi sửa — KHÔNG gọi API

Quy trình: viết test → chạy thấy đỏ → sửa → chạy thấy xanh (mỗi nhóm chạy riêng; chạy lẫn nhóm làm lộ một phụ thuộc thứ tự có sẵn giữa `test_cost_cap` và `test_cluster_4_8`, không phải do các bản sửa).

**#1 Trần chi phí cứng bị trừ hụt khi một lượt hỏng** (`cost_tracker.py`, `client.py`). Trước: 3 vòng đã trả tiền (82,3 VND) rồi lượt hỏng → lượt sau `record_turn` đặt ước tính tạm về 0 → tổng còn 27,4 VND. Test (`FailedTurnCostTest`, 6 test) đỏ 6/6 trước khi sửa: lỗi mạng sau 1 vòng, vượt 6 vòng, chạm trần giữa lượt, lượt sau không được xóa lượt hỏng, `spent_vnd` của runner, và `complete_json` nhận phản hồi đã trả tiền nhưng JSON hỏng (cùng loại lỗi, tìm thêm khi viết test). Sửa: `CostTracker.commit_inflight()` (chuyển ước tính tạm vào tổng); `chat_with_tools` bọc `_chat_with_tools` và gọi nó khi ném bất kỳ lỗi nào, kể cả `BudgetExceeded`; `complete_json` ghi chi phí TRƯỚC khi phân tích JSON.

**#2 Câu than phiền bị coi là "đồng ý chốt đơn"** (`order_gate.py`). Trước: "Dạ đắt thật đấy", "Dạ nhiều tiền thế", "Dạ chị đang bận lắm" → `is_explicit_consent` = True (đã chạy thử). Sửa: "dạ/vâng/ừ/có/được/đúng" chỉ là lời đáp lại (`_ACK`) — chỉ tính là đồng ý khi câu không còn gì khác ngoài chúng và từ đệm (`_FILLER`: ạ, nhé, em, anh, chị, cũng, rồi…); các cụm mạnh ("đồng ý", "chốt", "ok", "đúng rồi", "lên đơn"…) giữ như cũ. Test đỏ trước: `test_complaints_with_a_polite_particle_are_not_consent` (8 câu); test đối chứng xanh cả trước lẫn sau: các lời đồng ý trơn vẫn được chấp nhận (12 câu).
- **Hồi quy phát hiện khi chạy cả bộ và đã sửa:** bước XÁC NHẬN THÔNG TIN ĐÃ LƯU của gate dùng cùng hàm với câu dài ≤ 40 từ ("đúng sdt, 45/1 đường 10 …, Đại" — vừa xác nhận SĐT vừa nói địa chỉ và tên) nên bản chặt làm hỏng `test_name_at_the_end_of_the_address_is_understood_and_not_asked_again`. Thêm `lenient=True` CHỈ cho bước xác nhận thông tin đã lưu (sau đó còn bước đọc lại đơn nên rủi ro thấp); chốt đơn luôn dùng bản chặt. Test mới `test_confirming_stored_info_may_carry_new_info_but_order_consent_may_not`.

**#3 Chống gọi lặp chặn đơn mới** (`orchestrator.py`). **Lưu ý cải chính audit:** ví dụ "huỷ rồi đặt lại" trong báo cáo audit SAI so với hợp đồng — `tools.schema.json` chỉ có `exchange_size|exchange_product|return|update_address`, KHÔNG có action huỷ đơn, và mock không đổi `status` của đơn. Biến thể thật có thể tái hiện: sau `order.update action=return`, mục chống-lặp `order.create` vẫn trỏ tới đơn đã trả → đặt lại đúng sản phẩm trong cùng cuộc gọi/ngày nhận "đơn này em đã lên rồi, mã X" (mã của đơn đã trả), không có đơn mới. Test `test_new_order_after_the_first_was_returned_is_not_swallowed_by_dedup` đỏ trước khi sửa; test đối chứng `test_same_order_requested_twice_is_still_deduplicated` (LLM lặp vòng vẫn KHÔNG tạo đơn thứ hai) xanh cả trước lẫn sau. Sửa: `_forget_returned_order` xóa các mục `order.create` trỏ tới đơn vừa trả. Mức độ thực tế thấp (trả hàng rồi đặt lại ngay trong cùng cuộc gọi hiếm) — ghi nhận để người duyệt cân nhắc.

**Bộ test cuối (tuần tự, từng chế độ):** `MEMORY_TRANSPORT=local` **656/656 xanh**; `MEMORY_TRANSPORT=inproc` **656/656 xanh** (645 + 11 test mới: 6 chi phí, 3 đồng ý chốt đơn, 2 chống gọi lặp). Chi phí API: 0.

**Sửa test cũ do thiết kế mcp-memory hai tầng (không phải do 3 bản sửa):** `DeleteEverythingTest` nay xóa khách bằng view `Operator` (chỉ `Operator` được `memory.delete_customer`). Đây là lỗi test lộ ra lần đầu khi chạy bộ test qua `inproc` sau khi đổi thiết kế (lần chạy trước bị dừng giữa chừng).

**Phát hiện môi trường:** khi chạy hai bộ test song song gặp `WinError 1455` (paging file too small, 4 test lỗi do không spawn được tiến trình). Lúc đó có **131 tiến trình `mcp_servers.catalog_server`/`crm_server`, ~8 GB** đang sống: mọi `CallCenterHarnessPipeline` trong test (và mỗi phiên UI) tạo cổng MCP riêng và `pipeline.close()` không đóng nó (đúng phát hiện #5 của audit), nên các server chỉ biến mất khi tiến trình cha thoát. Kiểm lại sau khi các lần chạy kết thúc: chỉ còn 1 tiến trình python, 7 MB — tức không rò vĩnh viễn, chỉ tích lũy trong đời một tiến trình test/UI. Việc ép dừng tiến trình bị chặn quyền nên tôi không dọn; cách chạy an toàn: chạy các bộ test tuần tự (đã làm cho 656/656 ở trên).

### 11.33. Dataset: đổi 12 khung (giữ 86), nhãn ca khó "tái hiện lỗi demo", `--batch`, trần tích lũy 10.000 VND bằng mã (2026-10-24) — KHÔNG gọi API, chưa sinh lời thoại

**Quyết định của người dùng** (DATASET_PLAN § 9, § 9.1): chấp nhận cơ cấu 86 kịch bản / 135 cuộc; thêm ≥ 2 khung "mâu thuẫn phiên trước" với persona `khach_da_kenh_mau_thuan` và 5 kiểu khung tái hiện lỗi demo; model `gpt-6-luna`; trần cứng 10.000 VND bằng mã, sinh từng lô 10 khung; giọng Nam = Đại, Trung = Hậu (làm sau cùng); duyệt tay: chủ dự án + Kiệt (checklist ở `docs/DATASET_REVIEW_CHECKLIST.md`).

**Đã làm (mã + test; 0 VND):**
- **12 khung đổi, tổng không đổi** (A 13 / B 10 / C 31, 87 cuộc → 135): D03, D04 → mâu thuẫn phiên trước (D03 giá khác giữa kênh: AirPure X, KM `AP-SEP` còn hạn ở cuộc chat 25/9, hết hạn ở cuộc hotline 5/10 → 4.390.000đ vs 4.890.000đ; D04 thông tin khác đã lưu: phòng 25m²/5,5 triệu → 38m²/7 triệu, sản phẩm do `ProductRetriever` đổi AirPure Y → Samsung AX40); D25, D30 mặc cả (mua / không mua); D26 từ chối, D28 hoãn sau khi nghe đọc lại đơn; D24, D27 tồn kho theo biến thể (D24: "38 đen" CÒN hàng — tái hiện lỗi báo hết hàng nhầm; D27: M đen HẾT, nhận M be); D47, D48 tự nhận khách cũ khi chưa có SĐT; D51, D52 số/SĐT nói bằng chữ. **Lệch so với đề xuất:** D24 đổi ngành quạt → giày vì chỉ giày và áo khoác có biến thể trong catalog.
- **Ca khó sau khi đổi** (khung D + 22 cũ + 10 mẫu): đổi ý 5, mâu thuẫn 6, KM hết hạn 6, ngoài tài liệu 10 → 27 ca của 4 loại (mỗi loại ≥ 5; kém bảng § 2 mỗi loại đổi ý/KM 1 ca) + 10 khung "tái hiện lỗi demo". Số "22 cũ" lấy từ PLAN § 2 và đếm nhãn, "đổi ý" tính cả SC-GEN-09 chưa gắn nhãn.
- **Validator** (S7): 6 nhãn mới khớp CHÍNH XÁC (chuỗi `het_hang_bien_the` chứa `het_han` — nhánh cũ `"het_han" in hc` sẽ báo nhầm lỗi KM hết hạn; có test). `scenario_from` xuất `customer_turns_asr` + `input_mode=asr_transcript` cho kiểu `spoken`.
- **`generate_dataset_text.py`**: `--set`, `--batch` (mặc định 10), `--dry-run`; **`src/dataset/budget.py`: trần tích lũy 10.000 VND là hằng số**, đọc từ sổ cái `dataset/reports/generation_runs.jsonl` (đã tiêu 1.470,4 → còn 8.529,6), kẹp trần mỗi lần chạy, trừ biên 100 VND vì client chỉ kiểm trần TRƯỚC mỗi lần gọi, hết trần → thoát mã 4 trước khi tạo LLM client, luôn ghi nốt sổ cái (`finally`).
- **Test:** `tests/test_dataset_extra_frames.py` (39 test cùng `test_frames54`); toàn bộ bộ test offline `MEMORY_TRANSPORT=local`: **693 test, 0 đỏ** (`runs/_unittest_full8.txt`). Lần kiểm tra đầu phiên này (655 test) có 1 đỏ ở `test_ui_regressions` (`readback` ≠ `confirm`); lần chạy này không còn đỏ, **chưa xác định nguyên nhân** (các file `order_gate.py`, `orchestrator.py` đang được sửa đúng lúc chạy lần đó). Chưa chạy `MEMORY_TRANSPORT=inproc` sau các thay đổi 24/10.

**Chưa làm / hạn chế:** chưa sinh lời thoại (cổng: người dùng duyệt cụm sửa lỗi demo + 10 khung đầu); chưa có luật lời thoại P-rule riêng cho 6 nhãn mới (P5 chỉ áp cho cuộc có `order.create`, nên cuộc từ chối/hoãn chưa có luật máy bắt lỗi "khách lỡ đồng ý"); kiểu `claims_returning` giả định khách KHÔNG có trong CRM mock (kiểm bằng test) — chưa có biến thể khách có trong CRM; lô mặc định là SC-D01…D10 (chủ yếu nhóm A), muốn lô đại diện thì dùng `--ids`; sổ cái chỉ gồm các lần chạy sinh trong `dataset/reports/` — chi phí của `dataset_v1`/`dataset_regen1` (thư mục thử cũ) không nằm trong sổ cái; chi phí 87 cuộc ~3,4–5,1 nghìn VND vẫn là ngoại suy từ 17 cuộc.


### 11.34. Sửa phát hiện 5 và 6 của audit — vòng đời pipeline (2026-10-24) — mỗi cái có test THẤT BẠI trước khi sửa — KHÔNG gọi API

Người duyệt giữ bản sửa hẹp của phát hiện 3 (§ 11.33). Test mới: `tests/test_pipeline_lifecycle.py` (8 test), chạy riêng từng nhóm TRƯỚC khi sửa.

**#5 Pipeline UI không đóng cổng MCP** (`pipeline.py`, `ui_app.py`). Test đỏ trước khi sửa:
- `test_close_closes_the_mcp_gateway`: sau `pipeline.close()` cổng vẫn mở (`_closed` = False).
- `test_close_ends_the_mcp_server_processes` (stdio thật, đo bằng `psutil`): sau `close()` còn **2 tiến trình mồ côi** (`catalog_server`, `crm_server`).
- `test_turns_from_different_threads_never_overlap`: 4 luồng cùng gọi → **4 lượt chạy chồng nhau** (kỳ vọng 1). Giao dịch lượt (`begin_turn` … `commit`) của bộ nhớ là MỘT cho cả kho, nên lượt này chốt/xóa nhật ký ghi của lượt kia khi dùng chung pipeline (phát hiện #4 của audit, phần pipeline).
- `test_ui_shares_one_pipeline_across_sessions_and_starts_the_sweeper` (Streamlit `AppTest`, 2 phiên): dựng **2 pipeline** (kỳ vọng 1).
Sửa: `close()` dừng bộ quét nền, đóng bộ nhớ, **đóng cổng MCP** (gọi nhiều lần không lỗi); mọi điểm vào (`handle_incoming_request`, `end_call`, `sweep_idle`) chạy dưới một `RLock` để các lượt từ nhiều phiên được xếp hàng; `ui_app.py` dùng `@st.cache_resource get_pipeline()` → MỘT pipeline cho cả server Streamlit thay vì mỗi phiên trình duyệt một cái (mỗi cái trước đây mở thêm 2 tiến trình MCP, không bao giờ đóng).
- **Đánh đổi cần biết:** các lượt của mọi phiên UI nay chạy lần lượt (khóa), nên 2 người dùng cùng lúc chờ nhau trong lúc LLM trả lời (~1–3 s/lượt). Đó là giá của việc dùng chung một kho bộ nhớ có giao dịch theo lượt; muốn song song thật cần ngữ cảnh lượt theo phiên (bước 17).
- Pipeline dùng chung không được đóng khi server Streamlit tắt (chỉ có `atexit` của cổng MCP/bộ nhớ) — chấp nhận ở M1.

**#6 `sweep_idle` chưa được gọi** (`pipeline.py`, `orchestrator.py`, `ui_app.py`). Test đỏ trước khi sửa:
- `test_background_sweeper_finalizes_an_abandoned_call`, `test_an_active_call_is_not_swept`, `test_sweeper_is_idempotent_and_stops_on_close`: không có `start_idle_sweeper` (AttributeError).
- `test_timeout_finalization_runs_inside_its_own_turn_transaction`: chốt timeout **không có `begin_turn` riêng** (danh sách lời gọi rỗng, kỳ vọng `["call_1#timeout"]`) → ghi tự do ngoài giao dịch, provenance lấy của lượt cuối của BẤT KỲ khách nào.
Sửa: `CallCenterHarnessPipeline.start_idle_sweeper(idle_seconds=1800, interval_s=60)` (luồng nền daemon, idempotent, dừng khi `close()`, một lần quét lỗi không giết bộ quét); `sweep_idle` nay chốt từng cuộc gọi mở qua `end_call(trigger="timeout")` (giao dịch + provenance đúng cuộc gọi) rồi để `orchestrator.sweep_idle` xử lý các phiên không nằm trong `_open_calls` (khách chưa xác minh danh tính); thêm `orchestrator.last_activity(sid)`. UI bật bộ quét khi dựng pipeline (`IDLE_TIMEOUT_S`, mặc định 1800 s). Trường hợp thực tế đã kiểm: khách đóng tab sau 1 lượt → episode `ngat_cuoc` được ghi và `orchestrator._vaults` (SĐT/địa chỉ thật) được giải phóng, không cần thêm lời gọi nào.
- Bộ quét có thể gọi LLM (bộ trích slot khó, ≤ 1 lần/cuộc) → tốn API khi chạy với key thật; chạy nền nên không nằm trong ngân sách của một lần `run_eval`.

**Bộ test cuối (tuần tự, từng chế độ):** `MEMORY_TRANSPORT=local` **664/664 xanh** (656 + 8 mới); `MEMORY_TRANSPORT=inproc` **693/693 xanh**. Chênh 29 test là do một file test KHÔNG phải của tôi, `tests/test_dataset_extra_frames.py` (tạo lúc 11:21, giữa hai lần chạy), có mặt trong lần chạy `inproc` mà không có trong lần chạy `local`; lệnh khám phá test hiện tại đếm 693 ở cả hai chế độ. Đã chạy riêng file đó ở chế độ `local`: 29/29 xanh (664 + 29 = 693, khớp). Chi phí API: 0.


### 11.34. Dataset: lô đại diện đầu tiên — 10 khung SC-D03, D04, D24, D25, D26, D27, D28, D31, D47, D51 (2026-10-27) — LLM thật, DỪNG để người dùng xem

**Lệnh:** `generate_dataset_text.py --set frames54 --batch 10 --ids … --max-cost-vnd 1500` (model `gpt-6-luna`, seed 42). **Chi phí 442,3 VND** (12 cuộc, 26 lần gọi sinh; 36,9 VND/cuộc, ~17 VND/lần), trần lần chạy 1.500; **sổ cái 1.912,7 / 10.000 VND**. Không sinh thêm sau lô này.

**Kết quả:** 7/12 cuộc đạt kiểm tra khi sinh (D03 ×2, D04 call_2, D24, D26, D27, D31), **5/12 chưa đạt sau 3 lần sinh** (D04 call_1, D25, D28, D47, D51). `validate_all`: 11 LỖI (1 là lỗi cũ SC-C03/S3 `blocker`). File: `dataset/dialogues/SC-D*.json`, `dataset/scenarios/SC-D*.json` (cả khung có cuộc chưa đạt — cần loại/sinh lại), `dataset/review/frames54_dialogues.md`, console `runs/dataset_batch1_console.txt`.

**Nguyên nhân các cuộc chưa đạt (phân loại theo chỗ phải sửa):**
- *Lỗi của mã/khung (sửa bằng mã, không phải chất lượng LLM):* (1) tên "Xiaomi 4.5L" → `spoken_form` để lại chữ số ("4 5l") nên S12 báo lỗi và fact `product_asked` không khớp (D25, D47); (2) bảng địa chỉ chỉ 6 mục nên D04 và D28 dùng chung một địa chỉ → S10 trùng câu; (3) agent_plot của cuộc từ chối/hoãn viết "thanh toán {payment_label}" trong khi nhãn đã bắt đầu bằng "thanh toán" → lời agent bị lặp "thanh toán thanh toán khi nhận hàng (COD)" (thấy ở D26, D28); (4) D51: LLM viết SĐT bằng chữ trong bản VIẾT nên fact `phone_provided` không khớp (prompt chưa nói bản viết phải là chữ số, bản đọc do mã đổi); (5) D04 call_1 trùng ≥ 85% một câu khai slot ("Phòng khoảng 25m², nhà có bé…, ngân sách…") với SC-A01 vì cùng gợi ý fact.
- *Luật phong cách P3:* hồ sơ `interrupting`/`hesitant` đòi ≥ 25% lượt khách ≤ 6 từ; LLM không đạt sau 3 lần ở D04 call_1, D25, D28, D51.
- Lỗi cũ chưa sửa: "hiện hiện còn hàng" (LLM viết "hiện" trước ô `{stock}` đã có "hiện").

**Đọc nội dung các ca đặc biệt:** D26 (từ chối) đúng thiết kế: khách trả lời gate, nghe đọc lại đơn rồi nói "Thôi anh không lấy nữa", agent không tạo đơn/không nêu mã đơn. D28 (hoãn) đúng: hoãn sau khi đọc lại đơn ("để chị hỏi chồng đã"), không đơn — nhưng khách đã hoãn sớm từ lượt 3 và cuộc chưa qua S10/P3. D51: SĐT khách đọc từng chữ số, agent nhắc lại đúng 0900020051, nhưng sản phẩm Xiaomi Smart 4 Pro đang HẾT hàng (ghi trong khung) nên agent nói hết hàng, ngân sách 4,5 triệu thấp hơn giá 5,49 triệu.

### 11.35. Sửa lỗi mã/khung sau lô đại diện đầu (2026-10-27) — KHÔNG gọi API, chưa sinh lại

Sửa 5 lỗi ở § 11.34, mỗi lỗi có test hồi quy (`BatchFixesTest` + 1 test ở `GenerateScriptTest`); toàn bộ bộ test offline **702 test, 0 đỏ** (`runs/_unittest_full9.txt`).
1. **`spoken_form` "4.5L"**: thêm luật dung tích (`4.5L`/`6.2L`/`4L`/`4,5 lít` → "bốn phẩy năm lít") trước các luật số; `checks.fact_present` chuẩn hóa `4.5L` → `4.5 lít` trước khi khớp alias nên fact `product_asked` nhận ra tên có dung tích. (Không sửa `asr_entities`/bảng alias vì đó là mã chạy của hệ thống và luật ASR đã khóa.)
2. **Bảng địa chỉ**: từ vòng thứ 2 của bảng 6 mục đổi số nhà (+2/vòng) nên địa chỉ duy nhất theo khung; `ADDR_LEGACY` giữ nguyên địa chỉ của 6 khung đã có lời thoại đạt (D03, D04, D24, D26, D27, D31); khung khác trùng địa chỉ của chúng thì +1. Còn trùng duy nhất: D03 và D27 (cùng đã đạt S10, không sinh lại).
3. **"thanh toán thanh toán"**: agent_plot cuộc từ chối/hoãn dùng "hình thức {payment_label}" (như luật P5).
4. **D51**: gợi ý fact SĐT bỏ "từng chữ số"; plot nói rõ lời VIẾT phải là chữ số liền, hệ thống tự đổi thành lời đọc.
5. **D04**: slot cuộc 1 đổi 25m²/5,5 triệu → 22m²/5,8 triệu (vẫn ra AirPure Y, vẫn đổi sang Samsung AX40 ở cuộc 2) kèm gợi ý riêng ("phòng ngủ cỡ 22 mét vuông", "nhà đang có con nhỏ", "ngân sách khoảng 5,8 triệu") để lời khai không trùng SC-A01.
6. **Phát hiện thêm khi kiểm không-LLM**: tiền kiểm của `generate_dataset_text.py` coi lời khách của cuộc CHƯA ĐẠT (sắp bị sinh lại) là "cuộc khác" khi kiểm trùng S10 → làm D04 call_2 (đã đạt) bị đánh dấu sinh lại oan. Sửa bằng `customer_lines()` chỉ tính cuộc đạt.

**Kiểm không-LLM trên bản sao `dataset/dialogues` (thư mục tạm):** sau sửa, D47 call_1 **tự đạt** (không cần sinh lại), D04 call_2 giữ được. Còn **4 cuộc cần sinh lại**: D04 call_1, D25 call_1, D28 call_1, D51 call_1. Sổ cái vẫn 1.912,7/10.000 VND.

**Rủi ro còn lại:** cả 4 cuộc đều từng trượt luật P3 (hồ sơ `hesitant`/`interrupting` đòi ≥ 25% lượt khách ≤ 6 từ; LLM viết 0–1 lượt ngắn sau 3 lần) — các sửa ở trên KHÔNG đụng P3 nên nhiều khả năng vẫn trượt nếu sinh lại nguyên trạng.

### 11.36. P3: prompt sinh lời thoại yêu cầu rõ số lượt khách ngắn tối thiểu (2026-10-27) — KHÔNG gọi API, chưa sinh lại

**Vấn đề (§ 11.34–11.35):** 4 cuộc còn lại (D04 call_1, D25, D28, D51) cùng trượt P3 (0–1 lượt khách ≤ 6 từ) sau 3 lần sinh vì prompt chỉ có câu chung "ít nhất 1/4 số lượt khách ≤ 6 từ".
**Sửa (không nới ngưỡng):** `rules.min_short_turns(profile, n_turns)` tính số lượt ngắn cần yêu cầu = ceil(`short_share` × số lượt khách tối đa), +1 biên nhưng không vượt (số lượt khách tối thiểu − 1) để còn lượt dài mang fact; `writer.build_prompt` thêm khóa `yeu_cau_luot_khach_ngan`: "BẮT BUỘC có ÍT NHẤT N lượt khách chỉ 1–4 từ (ví dụ 'Ừ.', 'COD nhé.'…)…". Yêu cầu "1–4 từ" chặt hơn ngưỡng luật (≤ 6 từ) để có biên. `PROFILES[*].short_share` giữ nguyên (có test khóa giá trị). Với 4 cuộc trên: D04 c1 = 2, D25 = 3, D28 = 3, D51 = 3.
**Test:** `ShortTurnPromptTest` (5 test: ngưỡng không đổi; N đạt luật với mọi số lượt khách có thể có và không vượt số lượt khách tối thiểu cho 5 hồ sơ × 8 khoảng số lượt; biên; prompt của mọi cuộc trong 54 khung có yêu cầu; lượt ≤ 4 từ qua `check_style`). Toàn bộ bộ test offline: **707 test, 0 đỏ** (`runs/_unittest_full10.txt`).
**Chưa kiểm chứng:** hiệu quả thật trên LLM (cần sinh lại); đây là thay đổi prompt dùng chung cho MỌI khung — các cuộc đã đạt không bị sinh lại nên không đổi, nhưng 44 khung chưa sinh sẽ dùng prompt mới.

### 11.37. Dataset: sinh lại 4 cuộc chưa đạt của lô đại diện (2026-10-27) — LLM thật, DỪNG để người dùng xem

**Lệnh:** cùng `--ids` của lô đại diện, `--max-cost-vnd 600`; tiền kiểm không-LLM chọn đúng 4 cuộc: D04 call_1, D25, D28, D51. **Kết quả: cả 4 đạt ở lần sinh thứ 2** (prompt P3 mới có tác dụng ở 4/4 cuộc, nhưng cỡ mẫu nhỏ). **Chi phí 147,8 VND** (trần 600); **sổ cái 2.060,5 / 10.000 VND**. `validate_all`: 1 LỖI, là lỗi cũ SC-C03/S3 `blocker` (không thuộc lô này). Console: `runs/dataset_batch1_regen_console.txt`.

**Trạng thái lô 10 khung / 12 cuộc:** 12/12 cuộc đạt kiểm tra tự động (D47 call_1 tự đạt sau sửa mã, không tốn LLM). Tổng chi phí lô: 442,3 + 147,8 = 590,1 VND.

**Điểm validator KHÔNG bắt được, thấy khi đọc (cần người duyệt xem):**
- D28 (hoãn): khách hoãn sau khi nghe đọc lại đơn ("để chị hỏi chồng đã… chưa chốt lúc này") đúng thiết kế và không có đơn; nhưng cuộc **kết thúc ở lượt khách — agent không đáp lại việc hoãn** (kịch bản đòi ghi nhận lý do và hẹn gọi lại; không có luật máy bắt lỗi này).
- Lỗi cũ "hiện hiện còn hàng" xuất hiện ở D04, D25, D28, D51 (LLM viết "hiện" trước ô `{stock}` đã có "hiện") — chưa sửa.
- D51: sản phẩm Xiaomi Smart 4 Pro đang HẾT hàng và giá 5,49 triệu > ngân sách 4,5 triệu (từ khung `inquiry_only`); SĐT viết bằng chữ số, bản đọc `text_spoken` là từng chữ số bằng chữ — đúng thiết kế.

### 11.38. Luật P6: cuộc từ chối/hoãn phải được agent đáp lại (2026-10-27) — KHÔNG gọi API, chưa sinh lại

**Vấn đề (§ 11.37):** D28 (hoãn) kết thúc ở lượt khách, agent không đáp lại; không luật máy nào bắt (P5 chỉ áp cho cuộc có `order.create`). **D26 đã có lượt agent cuối → đạt.**
**Luật mới `rules.check_decline_flow` (P6)**, chỉ áp cho cuộc `is_gate_decline_call` (có ô `readback_total`, không phải cuộc tạo đơn, cấm `order.create` — hiện D26, D28): (1) có lượt agent ĐỌC LẠI ĐƠN; (2) lượt khách ngay sau KHÔNG phải lời đồng ý (đóng khoảng trống "khách lỡ đồng ý" ghi ở § 11.34); (3) cuộc KHÔNG kết thúc ở lượt khách — agent phải đáp lại; (4) lời đáp không nói đã lên đơn/mã đơn; (5) cuộc hoãn (`hen_goi_lai`) thì lời đáp phải ghi nhận và hẹn quay lại/gọi lại. Nối vào `plot_rule_errors` nên lỗi P6 cũng được đưa lại cho LLM ở lần sinh thử kế tiếp. Prompt kịch bản agent của D26/D28 nói rõ "BẮT BUỘC có một lượt agent CUỐI CÙNG đáp lại".
**Test:** `DeclineFlowRuleTest` (9 test; có ca tái hiện đúng lỗi D28, ca đạt, hoãn thiếu hẹn gọi lại, nói "đã lên đơn", khách đồng ý, thiếu đọc lại đơn, chỉ áp cho cuộc từ chối/hoãn, D26 thật đạt). Bộ test offline: **716 test, 0 đỏ** (`runs/_unittest_full11.txt`).
**Kiểm không-LLM trên bản sao `dataset/dialogues`:** chỉ **D28 call_1** bị đánh dấu sinh lại (1 lỗi P6); D26 và 10 cuộc còn lại giữ nguyên. Sổ cái 2.060,5 / 10.000 VND, chưa đổi.
**Hạn chế:** lời đáp chỉ kiểm bằng từ khóa (`ghi nhận|gọi lại|liên hệ lại|nhắn lại|khi nào|tiếp tục|quay lại`) nên vẫn cần người đọc; luật chưa áp cho cuộc "khách rời đi" khác (vd mặc cả `leave` D30 — cuộc đó kết thúc ở lượt agent nên chưa bị phát hiện thiếu).

### 11.39. Dataset: sinh lại D28 call_1 sau luật P6 (2026-10-27) — LLM thật, DỪNG để người dùng xem

**Lệnh:** cùng `--ids` của lô đại diện, `--max-cost-vnd 300`; tiền kiểm chọn đúng 1 cuộc (D28 call_1). **Đạt ngay ở lần sinh đầu, 15,9 VND**; sổ cái **2.076,3 / 10.000 VND**. `validate_all`: 1 LỖI, là lỗi cũ SC-C03/S3 `blocker`. Console: `runs/dataset_batch1_d28_console.txt`.
**Nội dung:** khách hoãn sau khi nghe đọc lại đơn ("để chị hỏi chồng đã, giờ chị chưa chốt nhé"); lượt 12 là agent đáp lại ("em ghi nhận chị Vân muốn trao đổi với chồng trước… sẽ liên hệ lại") — không đơn, không mã đơn. Lỗi cũ "hiện hiện còn hàng" vẫn còn; khách nhắc lo ngại an toàn ở lượt 1 và 5 nhưng agent chỉ nói sẽ kiểm tra lại (đúng luật không bịa, nhưng không có câu trả lời).
**Trạng thái lô đại diện:** 12/12 cuộc đạt kiểm tra tự động; tổng chi phí lô 442,3 + 147,8 + 15,9 = 606,0 VND. Không sinh thêm.

### 11.40. Sửa lỗi hệ thống sau khi tạm dừng dataset (2026-10-27) — KHÔNG gọi API

**Khảo sát (không LLM):** 716 test xanh ở `local` và `inproc`; `main.py` (không khóa API) và UI Streamlit (`AppTest`, 5 lượt chat + nút kết thúc cuộc gọi) chạy không exception; `test_ui_regressions` từng đỏ 1 lần đầu phiên nhưng chạy lại 8 lần đều xanh (nghi do file đang được sửa lúc chạy). Chưa thấy lỗi làm sập hệ thống.
**Đã sửa:**
1. Nhánh dự phòng khi mất LLM (`orchestrator.py`, `specialists.py`): bỏ mã SKU thô trong lời nói với khách (dùng `product_name` từ catalog); `SalesAdvisorAgent` chỉ nêu thông số có trong catalog (trước đây gắn cứng "HEPA H13"/"khóa trẻ em"/phòng 25m² cho mọi sản phẩm); quà tặng chỉ nhắc khi `pricing.get_quote` báo đang áp dụng (trước đây gắn cứng "quà tặng bộ lọc"). Test `tests/test_fallback_honesty.py` (4).
2. Guardrail 2b (`guardrail.py`): lời báo "hết hàng/không có sẵn" mâu thuẫn với mọi `inventory.check` của cuộc gọi (đúng một biến thể, đều còn hàng) → thay đúng câu đó bằng câu "còn hàng" theo tool, giữ phần còn lại; có biến thể hết hàng hoặc không có bằng chứng thì không can thiệp; `violation_type=stock_claim_mismatch`. Đóng lỗi ghi ở § 11.31 ("chưa có kiểm tra tất định lời nói-so-với-tồn kho"). Test `tests/test_stock_claim_guard.py` (7).
3. `ui_app.py`: `use_container_width=True` → `width="stretch"` (tham số cũ đã quá hạn gỡ 2025-12-31).
4. `docs/PIPELINE.md` viết mới theo mã thực tế (thay bản backup); sửa chữ "A2A" trong docstring `pipeline.py`, `main.py`, `orchestrator.py`, `guardrail.py` (module chạy trong tiến trình, không phải giao thức A2A). Ghi chú: server dùng `MCPServer` của `mcp 2.x` (trước là `FastMCP` ở 1.x); `requirements.txt` đã ghim `mcp==2.3.0`.
**Kiểm tra sau sửa:** `MEMORY_TRANSPORT=local` **727 test, 0 đỏ** (`runs/_unittest_full12.txt`). Lượt `inproc` (`runs/_unittest_inproc2.txt`) chạy nền, chưa có kết quả khi ghi.
**Chưa làm:** chạy LLM thật (`scripts/ui_replay.py`, cần duyệt trần chi phí) để kiểm 2 sửa chính; gỡ A2A/`src/eval/*` chưa được gọi (đổi chữ ký orchestrator); order gate ở server `mcp-crm`; run_eval thật trên MCP; bước 11/13/14a/17/18.

### 11.41. ui_replay với LLM thật sau các sửa § 11.40 (2026-10-27) — 247,0 VND (trần cứng 400)

`scripts/ui_replay.py` (3 hội thoại chép từ ảnh UI), kết quả `runs/ui_replay_5.txt`.
- **A (order gate):** đúng cả luồng — hỏi/xác nhận SĐT → địa chỉ + tên "Đại" nhận đúng (địa chỉ không dính tên) → COD → đọc lại đơn đúng (38, đen, 1.521.000đ) → "ok chốt" → `order.create` 1 lần, mã OD600001. Agent nói đúng 38 xám hết, 38 đen còn.
- **B:** mặc cả 6tr8 và "giảm thêm 90k" → agent giữ giá 6.890.000đ, không tạo đơn, đề nghị chuyển nhân viên; bộ nhớ có `blocker`, `objection`, `customer_name`. Lỗi còn: sau "tôi tên Đại" agent lặp nguyên câu xin SĐT lần thứ hai.
- **C:** khách nói đã liên hệ kênh khác → agent hỏi SĐT/tài khoản đã dùng (đúng thiết kế).
- **LỖI DO CHÍNH GUARDRAIL 2b (§ 11.40) GÂY RA, phát hiện nhờ lần chạy này:** `inventory.check` trên SKU CHA ("còn hàng") bị coi là bằng chứng nên guard chèn nhầm câu "hiện còn hàng" vào lời đúng của agent ở A lượt 2 (37 xám, không có size 37) và lượt 3 (câu "còn hàng" mâu thuẫn ngay cạnh câu "38 xám hết hàng"). **Đã sửa:** chỉ biến thể cụ thể mới là bằng chứng, và bỏ qua câu nhắc size/màu khác biến thể đã tra; test hồi quy thêm vào `test_stock_claim_guard.py` (27 test liên quan xanh). **Chưa chạy lại LLM thật sau bản sửa này.**
- Ghi nhận khác: lượt 1 của A dùng markdown `**…**` trong lời agent (chưa xử lý).

### 11.40. Tạm dừng dataset; khảo sát và sửa lỗi hệ thống (2026-10-27) — KHÔNG gọi API

**Khảo sát (không tốn API):** `compileall` sạch; import 6 entrypoint (`pipeline`, `run_eval`, `main`, `ui_app`, `eval_asr`, `generate_dataset`) không lỗi; `main.py` chạy hết 7 bước ở nhánh rule-based; `streamlit.testing.AppTest` chạy `ui_app.py` + 5 lượt chat + nút "Kết thúc cuộc gọi" **không có exception**; test offline xanh trên cả `MEMORY_TRANSPORT=local` và `inproc`. Ca `test_ui_regressions` từng đỏ ở đầu phiên **không tái hiện** (8/8 lần chạy lặp xanh; nhiều khả năng do file đang được sửa đúng lúc chạy).

**Lỗi tìm ra và đã sửa:**
1. **Rò tiến trình MCP trong bộ test (nặng nhất).** `run_eval.main()` gọi `os.environ.setdefault("MCP_TRANSPORT"/"MEMORY_TRANSPORT", "stdio")` trên cả tiến trình; test nào gọi nó trước thì MỌI test sau (mỗi `build_components`) sinh thêm 2 tiến trình `catalog_server`/`crm_server` không bao giờ đóng (probe từng module: 8 module rò, `test_order_gate` +54, `test_ui_regressions` +50, tổng 188 tiến trình). Hậu quả: bộ test **2.411 s thay vì ~490 s**, máy chậm. **Sửa:** `tests/_helpers.py` đặt `MCP_TRANSPORT=inproc`, `MEMORY_TRANSPORT=local` (bằng `setdefault`, tôn trọng biến người dùng đặt) trước mọi test; test cần stdio vẫn tự đặt. Kết quả: probe **0 tiến trình rò**; bộ 728 test chạy **73,5 s**.
2. **Nhánh dự phòng khi mất LLM nói điều không có căn cứ.** `SalesAdvisorAgent` gắn cứng "HEPA H13" và "khoá an toàn cho trẻ nhỏ" cho MỌI sản phẩm, mặc định phòng 25m²; câu xác nhận giá hứa "quà tặng kèm bộ lọc" kể cả khi khuyến mãi đã hết; lời gửi khách nêu mã `SKU-AP-Y` thô. **Sửa:** `catalog_product()`/`product_name()` trong `src/agents/specialists.py` (catalog thật; biến thể → sản phẩm cha; không bịa tên); lời tư vấn chỉ nêu thuộc tính có trong catalog (`features`, `room_area_m2` phủ đủ, `child_safe_lock`); quà chỉ nhắc khi `pricing.get_quote` báo `gift` đang áp dụng; dùng tên sản phẩm thay mã SKU. Nhánh này vẫn là "tối giản", không mở rộng keyword.
3. **Lời báo hết hàng mâu thuẫn tool (lỗi UI đã ghi ở § 11.31, "chưa có kiểm tra tất định").** Guardrail 2b (`GuardrailAndFallback._fix_stock_claims`): nếu mọi kết quả `inventory.check` của cuộc gọi (đúng một biến thể) ghi còn hàng mà lời agent báo "hết hàng/không còn size/không có sẵn" thì thay câu sai bằng câu đúng với tool ("…size 38 màu đen hiện còn hàng ạ."), giữ phần còn lại; ghi `violation_type=stock_claim_mismatch`. Không can thiệp khi có biến thể hết hàng, khi chưa tra kho, khi nói "hết hạn"/"chưa hết hàng". 
4. **`use_container_width` của Streamlit** (đã quá hạn gỡ 2025-12-31, in cảnh báo mỗi lần chạy) → `width="stretch"` (3 chỗ trong `ui_app.py`).
5. **Tài liệu:** `docs/PIPELINE.md` mới (kiến trúc thực tế, thay bản trong `backup_2026-10-21/` còn gọi "A2A" và gateway giả); chú thích "A2A" ở `pipeline.py`, `main.py`, `orchestrator.py`, `guardrail.py` sửa thành "module trong tiến trình, không phải giao thức A2A". **Chưa gỡ lớp `A2AAgentNetwork`** (đổi chữ ký orchestrator ở nhiều nơi, không có lợi ích chức năng).

**Test mới:** `tests/test_stock_claim_guard.py` (7), `tests/test_fallback_honesty.py` (4). **Bộ test: 728 test, 0 đỏ** (`runs/_unittest_full14.txt`, local, 73,5 s); `inproc`: 727 test, 0 đỏ (`runs/_unittest_inproc3.txt`, 452 s).

**Chưa kiểm chứng / còn lại:** (a) guardrail 2b và nhánh dự phòng mới chỉ được kiểm bằng test đơn vị — chưa chạy với LLM thật (`scripts/ui_replay.py`, trần 400 VND, cần bạn duyệt chi phí); (b) liên thông kênh Zalo ẩn danh → hotline bằng SĐT khác vẫn không tự nhận ra (chủ ý, không nối theo lời khai); (c) lỗi "hiện hiện còn hàng" của dataset chưa sửa (dataset đang tạm dừng); (d) chưa chạy `run_eval.py` thật trên kiến trúc MCP; (e) một lần chạy test (`_unittest_full13.txt`) dừng giữa chừng không rõ lý do, chạy lại thì xanh.

### 11.42. Tầng đầu ra (hỏi lại, markdown), số nói bằng chữ, đổi ngày = cuộc mới, tên khách + ui_replay lần 2 (2026-10-27) — LLM thật 361,0 VND (trần cứng 400)

**Mã mới/sửa:** `src/harness/reask.py` (`strip_markdown`, `rewrite_reasks`) nối vào `orchestrator.py` sau clarifier — hỏi mở LẠI cùng slot (SĐT/tên/địa chỉ/…) ở lượt liền sau khi khách chưa trả lời: lần 2 đổi thành câu ghi nhận điều đã nghe + cho phép bỏ qua (không còn dấu hỏi), lần 3 gỡ; khách đưa SĐT/tên thì reset; lượt do order gate nói được bỏ qua (gate có chống lặp riêng). Markdown (`**`, `#`, gạch đầu dòng) bị bỏ ở lời gửi khách và ở lịch sử cho LLM. `normalizer.itn_small_numbers` (hàm RIÊNG, không nằm trong phần ITN đã khóa): "mười lõi"→"10 lõi", "mười lăm tháng mười"→"15 tháng 10", "hai mươi mét vuông"→"20 mét vuông", "size ba tám"→"size 38"; không đụng "thứ hai", "năm ngoái". `pipeline.handle_incoming_request`: cùng khách đổi ngày/số cuộc → TỰ chốt cuộc cũ (`end_call`) rồi bắt đầu cuộc mới; `ui_app.py` đổi ngày/SĐT giữa chừng → chốt cuộc cũ, xóa khung chat, tăng số cuộc. `extract_customer_name`: tên dừng ở dấu câu đầu tiên ("Chị tên Lan, chị hỏi…" từng ra "Lan Chị" → Call Brief "chị Lan Chị"; lỗi phát hiện khi viết test cuộc 2).
**Test:** `test_output_layer.py` (10), `test_call_continuity.py` (8, chạy pipeline thật không LLM). **Toàn bộ bộ test: 745 test, 0 đỏ ở CẢ `MEMORY_TRANSPORT=local` và `inproc`** (`runs/_unittest_full13.txt`, `runs/_unittest_inproc4.txt`).
**ui_replay (`runs/ui_replay_6.txt`):** thêm hội thoại D (số nói bằng chữ) và E (đổi ngày; dòng `@ngày` = cuộc mới). Kết quả theo mục — xem báo cáo trong phiên. **Còn lỗi thấy trong lần chạy này:** (1) hội thoại A: LLM chỉ gọi `catalog.search` (không `inventory.check`) rồi nói "38 xám/38 đen không có sẵn" ở 4 lượt liên tiếp dù 38 đen còn 5 → guardrail 2b không có bằng chứng nên không can thiệp (lần chạy trước LLM có gọi `inventory.check` nên đúng; LLM không tất định); (2) B lượt 2: LLM gọi `handoff.transfer` khi khách chưa đồng ý chuyển máy (bị chặn `brief_invalid`, không chuyển thật); (3) lời LLM lộ mã "SKU-AP-FLT-X" (E lượt 2) và Call Brief mở đầu bằng mã ngắn "chị AP-X"; (4) D lượt 2: LLM gợi ý "Máy lọc nước UF" cho "phòng 20 mét vuông, bé 3 tuổi" (lẫn danh mục); (5) lỗi lặp SĐT của B không tái hiện trong lần chạy này (LLM không hỏi SĐT), chỉ có bằng chứng từ test.


## 12. Tổng hợp tiến độ (2026-10-27; cập nhật 2026-10-28 sau § 11.43–11.84; cập nhật lại 2026-11-04 sau § 11.85–11.106)

> Tóm tắt toàn bộ kế hoạch ([docs/PLAN.md](docs/PLAN.md)) đã làm và chưa làm. Chi tiết từng việc nằm ở § 11.x; kiến trúc hiện tại ở [docs/PIPELINE.md](docs/PIPELINE.md). Mọi số liệu dưới đây đọc từ nhật ký/lệnh đã chạy, không ước lượng thêm.

### 12.1. Đã làm (mã + test; trạng thái đo ghi riêng)

| Nhóm | Việc | Trạng thái | Nhật ký |
|---|---|---|---|
| **P0** | Bước 0–10: an toàn/sao lưu, bộ test offline, trace đúng thực tế (latency đo thật), runner + CLI chuẩn BTC, tool ghi an toàn, ghi nhớ sản phẩm đúng, guardrail, normalizer + PII token, định danh đa kênh, bộ nhớ/DB (bộ trích 2 tầng), bộ trích `claims/questions` | ✅ mã + test | § 11.1–11.17 |
| | HOTFIX N15 (lọc field `_*`), bước 2b (client đa model, trần chi phí cứng) | ✅ | § 11.6, 11.31 |
| **Đo** | Bước 15 GĐ1: 7 kịch bản × 2 cấu hình, đo lường công bằng (HR hai phía, CCR chặt), nhiều lần chạy A–I | ✅ chạy LLM thật; **chưa phải số nộp** | § 11.20–11.22, 11.29–11.31 |
| **ASR** | 16a GĐ1: Gipformer mặc định, Silero + VAD năng lượng, entity accuracy, luật ASR khóa; WER thô 8,4% trên **4 file TTS giọng Bắc** | ✅ GĐ1 | § 11.23–11.25 |
| **Sản phẩm** | Bước 12 (schema slot + ProductRetriever + chặn hỏi lặp): mã + test; đo LLM thật 1 lần | ◐ chưa đạt tiêu chí "không tăng số lần gọi LLM" | § 11.26, 11.29 |
| | 12b Order gate bằng code, luôn bật, đo tách 2 loại (TSR tương tác / kiểm tra kịch bản cố định) | ✅ mã + test; **TSR kịch bản BTC cố định về 0 đơn là hệ quả chủ ý** | § 11.30–11.31 |
| **MCP** | Bước 19: 3 MCP server thật (`mcp-catalog`, `mcp-crm`, `mcp-memory` — nơi ghi duy nhất), client + phân quyền theo caller, overhead đo (~1,8 ms/lời gọi stdio) | ◐ xong server/client/test; chưa chạy `run_eval` thật trên MCP | § 11.27, 11.32 |
| **Dataset** | Khung xác định 54 kịch bản, 10 mẫu sinh bằng `gpt-6-luna`, bộ kiểm S1–S14 + luật lời thoại P1–P6, `spoken_form` | ✅ | § 11.28–11.30 |
| | 12 khung đổi (mâu thuẫn phiên trước + 5 kiểu "tái hiện lỗi demo") giữ tổng 86; nhãn `hard_case` mới trong validator | ✅ | § 11.33 |
| | Trần chi phí tích lũy 10.000 VND bằng mã, `--batch`, `--dry-run`; **lô đại diện 10 khung / 12 cuộc đã sinh và đạt kiểm tra tự động** (606,0 VND + D28 sinh lại) | ✅ | § 11.34–11.39 |
| **Sửa hệ thống** | Nhánh dự phòng không bịa thông số/quà/SKU thô; guardrail "hết hàng" khớp `inventory.check`; tầng đầu ra: không lặp câu hỏi cùng slot, bỏ markdown; số nói bằng chữ ("mười lõi", "mười lăm tháng mười"); đổi ngày = cuộc mới, tự chốt cuộc cũ; sửa tên "Lan Chị"; Streamlit `width="stretch"`; viết `docs/PIPELINE.md` | ✅ | § 11.40–11.42 |
| **Kiểm** | Bộ test offline **963 test, 0 đỏ** (2026-11-02, `runs/_unittest_basket_sync2.txt`; 864 ở 2026-10-28); `ui_replay.py` 10 hội thoại A–J (trần cứng 550 VND) là bộ hồi quy LLM thật. **Chạy test: conda `nlp_env` (Python 3.12) + `MCP_TRANSPORT=inproc MEMORY_TRANSPORT=local`; Python hệ thống thiếu `sklearn` làm test treo** | ✅ | § 11.41–11.42, 11.75–11.78, 11.103–11.106 |
| **Hiểu lời khách (LLM-first)** | `reply_reader` (LLM + trích dẫn nguyên văn, code chỉ kiểm chứng), chốt đồng ý `verify` 2 lớp độc lập, cổng mở đơn bằng code (6 lớp tín hiệu, đọc muộn, SKU đơn, chống mơ hồ, hết hạn nháp), hỏi SĐT lần trước (C), reply `no_basis` do code dựng (D), `product_advised` từ shortlist (E), che mã SKU | ✅ mã + test; **LLM thật A–F: 5/6 đạt** (§ 11.75); chưa đo trên câu khách thật | § 11.43–11.75 |
| **Chuyển máy** | `handoff.transfer` chốt theo LÝ DO: ca ngoài phạm vi/an toàn → chuyển ngay (chốt độc lập + trích dẫn); mặc cả → cần khách yêu cầu/đồng ý; ép chuyển ca khiếu nại đơn đã đặt (code); brief do code điền trường thiếu; episode giữa cuộc không bị đếm là "cuộc trước"; khách CRM không bị xin lại SĐT | ✅ mã + test; **LLM thật B, G, H, I, J đạt** (một lần/ca) | § 11.76–11.80 |
| **Bước 14a** | Package `evaluation/` chấm lại từ trace, ca sai, đọc vẹt, bảng 20 lượt; gỡ 4 file dead code `src/eval/` | ✅ không LLM; bảng chấm tay chưa có người điền | § 11.81 |
| **Bước 11** | Router chọn policy 2 tầng + phương án lai (2 kết quả đầu từ file chọn, bù từ toàn bộ đã lọc ngày) | ◐ đo LLM thật: router thuần 74,6% < 81,4% (không đạt); hybrid k=2 88,1% chỉ tính OFFLINE (quá khớp), chưa đo lại; chi phí/độ trễ router chưa vào trace/trần | § 11.82 |
| **Bước 17** | Backend FastAPI `api/` (6 endpoint + sessions/health), tự cấp `call_name`/`turn_num`, trace rút gọn + che PII | ✅ 17 test, chạy thử uvicorn không LLM; phiên xen kẽ THEO LƯỢT (khóa pipeline), chưa song song thật | § 11.83 |
| **Bước 13** | Chủ động đưa thông tin: tra sẵn giá/tồn kho/KM/bảo hành lúc nhận diện khách (mã + test); chạy chung trong GĐ2 từ lần 2, **chưa A/B riêng** | ◐ | § 11.85 |
| **Bước 11** | Chi phí + quyết định router chính sách vào trace và trần chi phí (đã tính trong chi phí GĐ2 từ lần 5); chất lượng router: thuần 74,6% < 81,4%, hybrid 88,1% chỉ OFFLINE | ◐ | § 11.82, 11.96 |
| **Bước 18** | Giao diện web `ui/index.html` (dựng tay, **không dùng W&B OpenUI**) + `scripts/run_demo.py`; chạy thử LLM thật theo DEMO_SCRIPT (168 VND); nhận địa chỉ không cần đường/quận (§ 11.100); khách đổi sang sản phẩm khác giữa cuộc (§ 11.102, 302 VND) | ✅ mã + test; chưa kiểm điện thoại/Safari | § 11.97, 11.99, 11.100, 11.102 |
| **Hồ sơ nộp** | `submission/` (README, ARCHITECTURE, DATASET, EVALUATION_REPORT, DEMO_SCRIPT, slides.html). **Số liệu trong đó là của lần 4 (HR đã chấm lại = 0,0 sau sửa đáp án); chưa cập nhật theo lần 6 (TSR 66,7)** | ◐ | § 11.98, 11.103a |
| **Bước 15 GĐ2** (22 kịch bản × 2 cấu hình × 3 seed, LLM thật, trên MCP) | **6 lần chạy** (bảng dưới). Lần 6 là mới nhất, 22 kịch bản, đáp án đã sửa | ◐ **chưa đạt TSR ≥ 70 và TTFT ≤ 3 s** | § 11.87–11.94, 11.103b, 11.106 |
| **Dọn dự án** | Chuyển file/thư mục không dùng sang `Harness_Agent/NotRelated/` (không xóa); `.gitignore` loại `runs/*` trừ báo cáo `gd2_run*` | ✅ | § 11.101 |
| **Đáp án kịch bản sinh** | `SC-GEN-01` (RUN-10 bị bỏ sót), `SC-GEN-05` (RUN2-SALE), `SC-GEN-02` (AIR-OCT + AIR-2ND-50 → **11.685.000**, suy từ chính sách, BTC chưa xác nhận) — **lỗi của nhóm, không phải BTC**; sửa trong `generate_dataset.py` + `generated_m1/` | ✅ | § 11.103a, 11.104 |
| **Giá báo == giá đơn** | `src/harness/basket.py::price_basket` (nơi duy nhất tính tiền giỏ) dùng cho `get_quote`, đọc lại đơn và chốt cuối trước `order.create`; lệch ⇒ KHÔNG tạo đơn, code chuyển nhân viên; hạn mức COD/ngưỡng xác nhận tính trên tổng giỏ; `correct_basket_totals` sửa số LLM tự nhân (sửa này **chưa đo LLM thật**) | ✅ mã + test; ◐ đo | § 11.104–11.106 |

**Lịch sử bước 15 GĐ2 (cấu hình full; chi phí thật VND):**

| Lần | Thay đổi chính | TSR | RQR | HR giá/KM | TTFT p95 | Chi phí |
|---|---|---:|---:|---:|---:|---:|
| 1 (§ 11.87) | chạy đầu | 50,0 | 0,0 | 31,1 | 12,9 s | 10.716,5 |
| 2 (§ 11.90) | sửa theo § 11.89 (gate điền `price_vnd`…) | 68,2 | 7,3 | 6,2 | 8,3 s | 11.330,8 |
| 3 (§ 11.92) | sửa theo § 11.91 | 71,2 | 2,2 | 9,5 | 14,0 s | 11.706,8 |
| 4 (§ 11.94) | nhánh dự phòng mất LLM | **72,7** | 2,1 | 6,0 (0,0 sau sửa đáp án GEN-01) | 26,2 s (3 lượt API treo) | 11.638,9 |
| 5 (§ 11.103b) | timeout + thử lại; **21 kịch bản** (GEN-02 thiếu lúc chạy) | 69,8 | 0,0 | 1,9 | 6,5 s | 13.638,1 |
| 6 (§ 11.106) | `price_basket`, đáp án GEN đã sửa; 22 kịch bản | **66,7** | 0,0 | 0,0 | 7,7 s | 13.387,5 |

Lần 6 so lần 4: TSR giảm do SC-GEN-02 (3 seed; order gate chặn trước `order.create` khi tổng đúng vượt hạn mức COD — xung đột với tiêu chí chấm `tool_called: order.create`, không phải lỗi hành vi) và SC-GEN-13 seed 2 (LLM hỏi lại thay vì gọi `order.create`). Các lần không cùng cơ sở (đáp án/kịch bản đổi giữa chừng) — chỉ so sánh có điều kiện.

**Chi phí đã tiêu (đo, VND):** dataset 2.076,3 / 10.000 (trần tích lũy trong mã, còn 7.923,7); bước 15 GĐ2 sáu lần: 10.716,5 · 11.330,8 · 11.706,8 · 11.638,9 · 13.638,1 · 13.387,5 (≈ 72.400 tổng; mỗi lần dưới trần 7.000 + 7.500); `ui_replay` 247,0 + 361,0; chạy thử UI 168; phát lại đổi sản phẩm 302; các lần chạy GĐ1 ghi ở § 11.20–11.31 (riêng § 11.30 vượt trần "một lần chạy" 5.000 → 6.556). Giá `gpt-6-luna` trong `config/pricing.yaml` vẫn là giá tạm OpenRouter, **chưa đối chiếu giá OpenAI**.

### 12.2. Chưa làm (2026-11-04)

| Hạng mục | Vì sao còn thiếu / điều kiện |
|---|---|
| **Số đo chính thức đạt ngưỡng** (TSR ≥ 70 và hơn baseline; TTFT p95 ≤ 3 s) | lần 6: TSR 66,7, TTFT 7,7 s. Cần: quyết tiêu chí chấm SC-GEN-02; chạy lại sau `correct_basket_totals` (≈ 13.400 VND, **cần duyệt trần**); tối ưu token/TTFT (thứ tự chủ dự án chốt: sau end-to-end) |
| Cập nhật `submission/` theo số lần 6 (EVALUATION_REPORT, README, DEMO_SCRIPT, slides) | hiện vẫn là số lần 4 (TSR 72,7 "đạt") — **không còn đúng** |
| **Dataset còn 44 khung** + audio ≥ 40 cuộc / ≥ 1 giờ + ghi âm Nam (Đại) / Trung (Hậu) có giấy đồng ý + 16a GĐ2 (≥ 20 file, luật quay lại whisper) | **tạm dừng** theo yêu cầu 2026-10-27; M1 cần ≥ 30 khách đa phiên (đếm 2026-10-21: 9; chưa đếm lại với lô dataset mới) |
| Duyệt tay 15% (checklist [docs/DATASET_REVIEW_CHECKLIST.md](docs/DATASET_REVIEW_CHECKLIST.md)), điền `manual_review.csv`, chia dev/held-out | cần người duyệt |
| Bước 14b (LLM-judge + simulator, M2), bước 16 (vòng cải tiến) | chưa bắt đầu |
| Đo chốt đồng ý / cổng mở đơn trên **câu khách thật** (`eval_consent_guard.py --cases`, `eval_gate_open.py --cases`) | chờ file JSONL từ chủ dự án + trần chi phí |
| Order gate ở `mcp-crm`; hai phiên SONG SONG thật trên cùng DB | cần ngữ cảnh lượt theo phiên trong `MemoryService`/mcp-memory |
| Gỡ `src/agents` "A2A" | đổi chữ ký orchestrator; chờ quyết định |
| **Hồ sơ nộp M1:** video demo 5–8 phút, slide `.pptx` (thiếu `python-pptx`), điền tay `manual_review.csv`, cập nhật README gốc | chưa có |
| Đối chiếu giá `gpt-6-luna` với OpenAI | việc của chủ dự án |
| **Đề nghị gửi BTC** (không tự lách): (1) `order.create` nhận `basket_skus` hoặc nhiều dòng giá; (2) AIR-2ND-50 với từ 3 máy ("máy thứ 4 có giảm không?"); (3) AIR-OCT có áp cho máy 1 khi máy 2 hưởng AIR-2ND-50 (11.685.000 hay 11.985.000); (4) xác nhận đáp án GEN-02; (5) cách chấm kịch bản có order gate (mẫu BTC cố định TSR 14,3%) | § 11.105 |

### 12.3. Lỗi đã biết còn lại (2026-11-04)

1. **TSR bộ mẫu BTC cố định 14,3%** (cả baseline): lời khách cố định không trả lời câu hỏi của order gate ⇒ không có đơn — hệ quả chủ ý (§ 11.31); TSR chính là cột "sinh (tương tác)".
2. **SC-GEN-02**: tiêu chí chấm `tool_called: order.create` mâu thuẫn với bất biến "không thử khi biết chắc sẽ sai" (§ 11.106) ⇒ trượt 3/3 seed dù hành vi đúng. Cần đổi `success_if` hoặc bỏ ca.
3. **Biến thiên LLM**: có lúc hỏi lại "chị có muốn em lên đơn không?" thay vì gọi `order.create` (SC-GEN-13 seed 2 lần 6; SC-GEN-15 lần 5); SAMPLE-03 hỏi lại mã đơn (mã OD682761 của BTC không có trong mock). Mỗi seed một mẫu, std ±2,7.
4. **Tổng nhiều máy**: LLM tự nhân giá × qty và nói số khác `total_vnd` (GEN-02 lượt 1, lần 6) — đã sửa bằng `correct_basket_totals`, **chưa đo LLM thật**; số làm tròn ("khoảng 15,4 triệu") không bắt được.
5. **Giới hạn thiết kế `price_basket`**: chỉ áp KM "máy thứ 2" cho đúng 2 máy cùng SKU; ≥ 3 máy và giỏ nhiều SKU có KM giỏ ⇒ không áp giảm / chuyển nhân viên vì `order.create` không nhận `basket_skus`. Đơn 2 máy cùng loại giờ KHÔNG đặt được ngay (chuyển nhân viên) ⇒ TSR nhóm ca này giảm. Không kiểm lại sau khi đơn đã tạo.
6. **CCR**: SAMPLE-02/03/04/05 và SC-GEN-05/06 vẫn "chưa mang sang" một số trường (product_advised, competitor_price_vnd, promo_code, size…) — chưa phân tích sâu; `blocker` không tính là "đã dùng".
7. **TTFT p95 7,7 s** (trung vị khoảng 3,5 s); timeout + thử lại đã loại các lượt treo 60–128 s.
8. **Liên thông kênh** Zalo ẩn danh → hotline bằng SĐT khác không tự nhận ra (chủ ý).
9. **Quy trình**: `generated_m1/` và `generate_dataset.py` bị hai phiên sửa song song trong lần chạy 5 (SC-GEN-02 từng vắng khi chạy ⇒ 21 kịch bản); khi chạy đo phải chốt bộ kịch bản trước. Router chính sách: multi-hop full recall @3 = 8,3%; từ chối câu `unanswerable` 0%.

### 12.4. Thứ tự đề xuất tiếp theo (2026-11-04)
1. **Chủ dự án quyết:** tiêu chí chấm SC-GEN-02; trần cho lần chạy xác nhận (≈ 13.400 VND). 2. Chạy lại GĐ2 trên bộ 22 kịch bản đã chốt → số chính thức; cập nhật `submission/` (đừng giữ số lần 4). 3. Gửi BTC 5 đề nghị (§ 12.2). 4. Tối ưu token/TTFT (mục tiêu ≤ 3 s). 5. Duyệt lô dataset kế tiếp (hoặc để tạm dừng) → audio, 16a GĐ2, chia dev/held-out; duyệt tay 15%. 6. Đo chốt đồng ý/cổng mở đơn bằng câu khách thật. 7. Hồ sơ nộp: video, slide `.pptx`, README gốc; sau M1: 14b, 16.

### 11.43. Sửa "hết hàng sai": code tự tra `inventory.check` cho biến thể khách nêu (2026-10-27) — KHÔNG gọi API, chưa chạy lại LLM thật

**Lỗi (§ 12.3 mục 1):** khách hỏi "38 đen", LLM chỉ gọi `catalog.search` rồi nói "không có sẵn" dù còn 5; guardrail 2b không có bằng chứng tồn kho nên không can thiệp.
**Sửa (`orchestrator.py`, `guardrail.py`):**
1. `_check_named_variants`: khách nêu ĐỦ size + màu (khớp nguyên từ, không dấu) của sản phẩm đang bàn (đã tư vấn, hoặc có trong `catalog.search`/`inventory.check`/`pricing.get_quote`/`order.create` của cuộc gọi) → CODE chạy `inventory.check` đúng biến thể đó; lần nhắc gần nhất thắng, tối đa 4 biến thể, bỏ qua biến thể LLM đã tra trong lượt. Chạy **hai lần**: TRƯỚC khi gọi LLM (sản phẩm đã biết → thêm dòng ngữ cảnh "đã tra tồn kho THẬT: …, nói đúng theo kết quả, không đọc mã SKU") và SAU khi LLM trả (sản phẩm chỉ lộ ra trong `catalog.search` của chính lượt đó). Kết quả vào `tool_calls` của trace và là bằng chứng cho guardrail.
2. Guardrail 2b xét **từng câu**: câu báo hết hàng chỉ bị thay khi mọi biến thể đã tra mà câu có thể nói tới đều còn hàng. Trước đây cần đúng 1 biến thể làm bằng chứng nên ca thật "38 xám hết, 38 đen còn" (2 biến thể) bị bỏ qua.
**Test:** `tests/test_stock_probe.py` (8) + 1 ở `test_stock_claim_guard.py`. Tắt `_check_named_variants` thì 5/8 test mới đỏ (đã thử). **754 test, 0 đỏ** (`runs/_unittest_full15.txt`, `MEMORY_TRANSPORT=local`, môi trường `nlp_env`; `inproc` chưa chạy lại).
**Tác dụng phụ:** trace có thêm lời gọi `inventory.check` do code chạy (không có trong lời LLM); chưa đo ảnh hưởng lên số lượt/độ trễ — mỗi lần ~2 ms (stdio).
**Chưa kiểm chứng:** hiệu quả với LLM thật (cần `scripts/ui_replay.py`, trần 400 VND, chờ duyệt). Khách chỉ nêu size hoặc chỉ màu, hoặc size không có trong catalog (vd 37) thì không tra — chủ ý.
**Lưu ý môi trường:** `python` mặc định của máy là 3.14 không có `sklearn`; phải chạy test bằng `C:\Users\GIGA\anaconda3\envs\nlp_env\python.exe`.

### 11.44. Chạy lại `ui_replay.py` hội thoại A với LLM thật sau sửa "hết hàng sai" (2026-10-28)

**Chạy:** `ui_replay.py --only A` (nlp_env, stdio), trần duyệt 400 VND, **chi phí thực 111,0 VND**. Log: `runs/ui_replay_7.txt`.
**Kết quả:** lỗi đã hết. "thế 38 đen có không?" → "còn hàng với số lượng 5 đôi" (trước: "không có sẵn"); trace có `inventory.check SKU-SN-RUN2-38-DEN → True`. "38 xám" vẫn đúng là hết hàng; "xám 37" báo không có (size 37 không tồn tại). Lượt "ok lấy 38 đen" hỏi đủ tên/địa chỉ/thanh toán, cuối cuộc readback 1.521.000đ đúng.
**Quan sát (chưa sửa):**
1. Lượt 3 và 4 có 2 lần `inventory.check` cùng SKU: code tra trước LLM, LLM lại tra. Chỉ trùng trace/~2 ms, không sai nội dung. Bước "sau LLM" đã bỏ qua trùng, bước "trước LLM" thì chưa.
2. Lượt 6 ("đúng sdt, 45/1 …, Đại") và lượt 7 ("đại, COD"): agent hỏi lại "số điện thoại 0986886113, đúng không ạ?" dù khách đã nói "đúng sdt"; lượt 7 lặp đúng câu đó và không nhận COD. Order gate đi `ask_confirm` → `confirm` → `readback` hợp lệ, nhưng lời thoại lặp. Không do bản sửa này (không liên quan tồn kho); chưa điều tra nguyên nhân.
3. Chưa chạy B–E nên không có số đo hồi quy cho các hội thoại khác.

### 11.45. Điều tra + sửa: hỏi lặp xác nhận SĐT ở hội thoại A lượt 6–7 (2026-10-28) — KHÔNG gọi LLM

**Nguyên nhân gốc (dựng lại offline, không cần LLM):** ở lượt 5 chính LLM hỏi "số điện thoại (nếu khác số đang gọi)", khách đáp lượt 6 "đúng sdt, 45/1 …, Đại". Lúc đó gate CHƯA hỏi lần nào nên `pending_confirm` chưa có; gate chạy lần đầu ở lượt 6, thấy SĐT đang gọi là `known` → hỏi xác nhận lại. Lượt 7 "đại, COD" không phải lời đồng ý (`is_explicit_consent` = False) nên `pending_confirm` bị bỏ → hỏi lại đúng câu đó. Chỉ lượt 8 "ok chốt" mới xác nhận. Gate chạy đúng thiết kế; thiếu sót là không nhận lời khẳng định đi TRƯỚC câu hỏi của gate.
**Sửa (`order_gate.py`):** `GateState.phone_ok`; `begin_turn` đặt cờ khi lời khách có "đúng sdt / đúng số này / số này đúng…" và không kèm phủ định (không, sai, khác, nhầm, chưa); `_fields` coi SĐT đang gọi (nhánh `known`) là `confirmed` khi cờ bật. Khách đưa số khác thì đi nhánh `stated`, không bị ảnh hưởng.
**Test:** `PhoneAffirmedBeforeAskedTest` (2) trong `tests/test_ui_regressions.py`; gỡ dòng sửa thì test đỏ. Toàn bộ bộ test OK (`runs/_unittest_full16.txt`).
**Chưa làm / chưa kiểm chứng:** chưa chạy lại LLM thật (ui_replay A). Câu "xác nhận lại SĐT" vẫn xuất hiện nếu khách KHÔNG nói gì về số; cụm khẳng định chỉ nhận vài mẫu ("đúng sdt", "đúng số này", "số này đúng"), các cách nói khác (vd "vẫn số này nhé" có "van"; "số đó đúng") chỉ phủ một phần.

### 11.46. Đổi hướng: HIỂU lời khách bằng LLM + trích dẫn nguyên văn (2026-10-28) — chưa gọi LLM thật

**Nguyên tắc người dùng chốt:** mọi chỗ hiểu ngữ nghĩa lời khách nghĩ trước tiên theo hướng LLM trích xuất có cấu trúc kèm đoạn trích nguyên văn; code chỉ kiểm chứng + giữ máy trạng thái an toàn; regex chỉ là dự phòng offline. Tối ưu token/TTFT/total_time để SAU khi pipeline end-to-end hoàn chỉnh (lượt nào cũng đang gọi thêm 1 lần đọc — chủ ý, chưa tối ưu).
**Đã làm:** `src/harness/reply_reader.py` (`read_reply` qua `LLMClient.complete_json`, bản đã che PII; `verify` bỏ mọi kết luận không có trích dẫn nguyên văn trong lời khách; giá trị ngoài danh sách bị bỏ). Đọc: stance (agree/decline/other), only_answers, affirmed (tên/SĐT/địa chỉ/thanh toán khách xác nhận đúng), tên người nhận, thanh toán. `orchestrator.process_turn` đọc trước `begin_turn`; `OrderGate.begin_turn(reading)` dùng cho đồng ý/từ chối/xác nhận; `_driver_merge` và `_order_driver` dùng cho tên/thanh toán/"chỉ trả lời gate". Không có LLM hoặc LLM lỗi → `reading=None` → bộ regex cũ (fail-closed như trước). Máy trạng thái (khi nào được tạo đơn) giữ nguyên là code.
**Test:** `tests/test_reply_reader.py` (6; LLM GIẢ → chỉ kiểm chứng phần code: trích dẫn bịa bị bỏ, đồng ý bịa không tạo đơn, LLM lỗi → regex). Toàn bộ 762 test OK (`runs/_unittest_full17.txt`).
**CHƯA kiểm chứng (quan trọng):** LLM thật có hiểu đúng lời khách đa dạng hay không. `scripts/eval_reply_reader.py` (30 câu, kể cả cách nói không có từ khóa quen thuộc, trần cứng 100 VND) đã viết, CHƯA chạy — chờ duyệt chi phí.
**Còn regex hiểu lời khách ở chỗ khác (chưa đổi):** `extract_easy_slots`, `detect_self_honorific`, `detect_bargain`, `extract_amounts`, bộ trích thực thể ở `normalizer`, `is_pure_gate_reply`/`extract_recipient_name`/`detect_payment` (chỉ còn là dự phòng trong gate). Phần dataset/eval vẫn dùng `is_explicit_consent` để kiểm tra dữ liệu, không phải runtime.

### 11.47. Đo bộ đọc lời khách bằng LLM thật (2026-10-28)
`scripts/eval_reply_reader.py`, 30 câu, log `runs/eval_reply_reader_1.txt`. **Đúng 23/30 theo nhãn tự đặt.** Chi phí 101,8 VND (≈3,4 VND/lần đọc) — vượt trần 100 một chút vì trần chỉ kiểm TRƯỚC mỗi lần gọi.
**Lỗi nghiêm trọng:** (a) "ừm" → agree (đồng ý giả; nếu rơi vào lượt ngay sau đọc lại đơn sẽ tạo đơn). (b) "không phải, gửi qua số 0912345678 nhé" → decline (khách đang SỬA số, nhưng gate sẽ hủy đơn nháp).
**Lỗi khác:** "đại" / "đại, COD" không nhận ra là tên (2); "cứ giao số máy này thôi, người nhận là chị Hoa" không nhận xác nhận SĐT, tên kèm "chị"; "Trần Quang Minh ạ" only_answers=False; "số này luôn nha. giao về…" stance=agree thay vì affirmed phone (gate vẫn xác nhận được SĐT); "quét mã qr được không em" (câu hỏi) → payment=None, nhãn có thể sai.
**Chưa sửa prompt, chưa chạy lại.**

### 11.48. Sửa prompt bộ đọc lời khách theo lỗi đã đo (2026-10-28) — CHƯA chạy lại
Thêm quy tắc tổng quát vào `reply_reader.PROMPT` (không chép câu mẫu): tiếng đệm đơn thuần ≠ đồng ý; sửa/phủ định thông tin ≠ từ chối; câu ngắn giống tên khi vừa hỏi tên = tên (bỏ danh xưng); "số này/số máy này" = xác nhận SĐT; only_answers khi trả lời đúng điều được hỏi; hỏi về một hình thức thanh toán ≠ chọn nó. `eval_reply_reader.py` thêm 4 câu (35 câu), và kiểm stance cho câu sửa số. 6 test của reply_reader vẫn xanh (LLM giả). Hiệu quả CHƯA đo.

### 11.49. Rào chắn cấu trúc chống tạo đơn do đọc nhầm "đồng ý" + prompt theo nguyên tắc (2026-10-28) — chưa đo bằng LLM thật
**Phản hồi người dùng:** sửa theo từng câu sai là vá; (1) chặn rủi ro bằng CẤU TRÚC, (2) quy tắc prompt viết theo ngữ nghĩa, vẫn đúng khi xóa hết ví dụ.
**Prompt (`reply_reader.PROMPT`):** viết lại thành 8 nguyên tắc, KHÔNG còn từ/câu ví dụ; bỏ các quy tắc chép từ câu sai (tiếng đệm cụ thể, "số này"…). Thêm trường `confidence`.
**Rào chắn (`reply_reader.apply_guard`, env `CONSENT_GUARD`):** chỉ ở lượt NGAY SAU đọc lại đơn (stage = readback); "agree" không qua chốt → hạ về "other" → gate không chuyển `consented`, đơn được đọc lại, KHÔNG tạo. Ba chế độ: `none` (đối chứng), `confidence` (≥ 0,85, thiếu = thấp; không gọi thêm LLM), `verify` (lớp LLM thứ hai độc lập: prompt khác, không thấy kết luận lớp một, phải kèm trích dẫn nguyên văn; lỗi/thiếu → không cho). Mặc định TẠM `verify` (an toàn nhất), chọn chính thức sau khi đo.
**Test:** `ConsentGuardTest` (4) trong `tests/test_reply_reader.py` (LLM giả: cần cả hai lớp, lớp hai không thấy kết luận lớp một, confidence không gọi thêm, chỉ áp dụng ở bước sau đọc lại). 766 test OK (`runs/_unittest_full18.txt`).
**Đo (chưa chạy):** `scripts/eval_consent_guard.py` — 36 câu (10 nên tạo, 26 không), so `none` / `confidence` ở 3 ngưỡng / `verify` / `verify+confidence` theo: tạo nhầm, bỏ sót, +ms/lượt, +VND/lượt. Bộ câu do người viết code tự nghĩ → nhận `--cases file.jsonl` để thêm câu khách thật. Trần cứng 170 VND.
**Chưa làm:** bước xác nhận cuối riêng (hỏi lại lần nữa) và yêu cầu trích dẫn đủ dài — chưa cài, vì "verify" đã là lớp độc lập thứ hai; cân nhắc sau khi có số đo.

### 11.50. Đo rào chắn đồng ý bằng LLM thật (2026-10-28) — CHƯA ĐỦ bộ câu
`scripts/eval_consent_guard.py`, log `runs/eval_consent_guard_1.txt`. Dừng ở câu 33/36 vì chi phí 174 VND vượt trần 170 (ước ~4 VND/câu kể cả lớp hai) → script khi đó chưa in bảng (đã sửa: giờ in bảng cả khi dừng giữa chừng). Bảng dưới tính TAY từ log, trên 33 câu (10 nên tạo, 23 không); độ trễ/chi phí từng lớp KHÔNG có số.
| rào | tạo nhầm | bỏ sót |
|---|---|---|
| none | 4/23 | 0/10 |
| confidence ≥0,7 | 4/23 | 0/10 |
| confidence ≥0,85 | 2/23 | 0/10 |
| confidence ≥0,95 | 1/23 | 2/10 |
| verify (lớp hai độc lập) | 0/23 | 3/10 |
| verify + conf ≥0,85 | 0/23 | 3/10 |
Tạo nhầm khi không rào: "ừm" (conf 0,9), "được nhưng giao trước thứ sáu nhé" (0,8), "cũng được" (1,0), "tạm được" (0,8). Bỏ sót của verify: "thôi cũng được, lấy luôn", "chuẩn rồi, em làm giúp chị nhé", "ờ thì cứ vậy đi".
Nhận xét: confidence không đủ (mô hình tự tin sai: "cũng được" = 1,0); verify chặn hết ca sai nhưng khắt khe (mất 3/10 đồng ý thật → phải hỏi lại thêm một lượt). Mẫu nhỏ, câu tự nghĩ → chưa kết luận thống kê.

### 11.51. Phân việc LLM / code + bỏ lần đọc ở lượt khám phá (2026-10-28)
Người dùng: linh hoạt với LLM-first — phần nào máy trạng thái/regex/trường trạng thái làm được mà vẫn đúng thực tế và tiết kiệm lần gọi thì dùng code; phải tách "chia việc ngay từ thiết kế" khỏi "tối ưu sau khi end-to-end xong". Bảng quyết định đầy đủ: `docs/LLM_VS_CODE.md`.
**Đã làm:** `orchestrator.process_turn` chỉ gọi `read_reply` khi đã vào ngữ cảnh MUA (gate có đơn nháp, hoặc `_call_log` có order.create/pricing.get_quote/inventory.check trên một biến thể SKU) → bỏ 1 lần gọi LLM ở các lượt khám phá. Test `test_reader_is_skipped_until_a_concrete_variant_is_in_play`. Toàn bộ test: `runs/_unittest_full19.txt`.
**Giới hạn:** lượt ĐẦU nhắc biến thể và đồng ý ngay trong cùng lượt (chưa có tra cứu nào trước đó) sẽ không qua bộ đọc (dùng regex dự phòng). Chưa đo bao nhiêu lần gọi được tiết kiệm trên hội thoại thật.
**Chưa làm:** nối `detect_bargain` vào `reading.declines`; đo `extract_easy_slots`/`detect_self_honorific` trên câu khách thật; chạy `ui_replay` A–E (chờ duyệt chi phí).

### 11.52. ui_replay A–E, LLM thật, sau toàn bộ thay đổi phiên 2026-10-28
Log `runs/ui_replay_8.txt`, **chi phí 374,0 VND** (trần nâng 400→450). So với `ui_replay_6`:
**A (tốt, hoàn chỉnh):** "38 đen" → còn hàng; địa chỉ + "đúng sdt" + tên Đại → gate chỉ hỏi thanh toán (hết lặp SĐT); "đại, COD" → đọc lại đơn đúng; "ok chốt" → tạo đơn OD600001. Còn trùng `inventory.check` ở lượt 3 (code tra trước + LLM tra).
**B:** vẫn gọi `handoff.transfer` khi khách chưa đồng ý (2 lần `brief_invalid`, tệ hơn lần trước 1 lần) rồi xin SĐT trên kênh zalo. Mặc cả giữ đúng giá; blocker/objection lưu đúng. (lỗi cũ § 12.3, không do thay đổi phiên.)
**C:** vẫn không trả lời "còn hàng không", hỏi lại SĐT (giống ui_replay_6). **D:** "Máy lọc nước UF Sunhouse" cho phòng 20m² có bé 3 tuổi (nhầm danh mục, lỗi cũ). **E:** vẫn lộ mã "(SKU-AP-FLT-X)" và "chị AP-X" (lỗi cũ).
**KHÔNG biết được:** bộ đọc LLM / rào verify có thật sự chạy trong A hay gate rơi về regex — trace chưa ghi `reading`/`guard`. Số lần gọi LLM đọc thêm và độ trễ không đo được. Cần ghi `reading` + `guard` + usage vào trace trước khi kết luận.

### 11.53. Trace ghi bộ đọc lời khách (2026-10-28) — KHÔNG gọi LLM
`process_turn` thêm `metadata["reply_reading"]` → `pipeline` đưa vào `extra` của trace (cùng cấp `order_gate`). Giá trị: `{"source": "skipped"}` (máy trạng thái bỏ qua, chưa vào ngữ cảnh mua) | `{"source": "regex_fallback"}` (không có LLM/LLM lỗi) | `{"source": "llm", stance, confidence, only_answers, affirmed, recipient_name, payment, evidence (trích dẫn đã kiểm chứng), guard ({mode, raw_stance, passed, confidence} khi có chốt), llm_calls, vnd_cost, latency_ms}` (tổng cả lớp một và lớp chốt). `scripts/ui_replay.py` in dòng `[reader: …]` mỗi lượt. Test trong `test_reply_reader.py`; toàn bộ 767 OK (`runs/_unittest_full20.txt`). Lần chạy ui_replay kế tiếp sẽ cho biết bộ đọc/verify có thật sự chạy và tốn bao nhiêu.

### 11.54. ui_replay A với trace bộ đọc (LLM thật, 2026-10-28)
Log `runs/ui_replay_9.txt`, **149,7 VND** (trần lần này 200; thêm `--max-cost`). Bộ đọc CÓ chạy: lượt 1–3 `skipped` (chưa có biến thể được tra); từ lượt 4 (sau khi 38 xám/38 đen được tra) `llm`, mỗi lượt 1 lần gọi ≈ 4,5–5,2 VND, ≈ 1,7–1,9 s. Lượt "ok chốt" (sau đọc lại đơn): 2 lần gọi (đọc + chốt verify), 6,2 VND, 2,9 s, guard {mode: verify, passed: true} → tạo đơn OD600001.
Đọc đúng: "ok lấy 38 đen" agree 1.0; "đúng sdt, 45/1…, Đại" affirmed [phone, address, name] + name=Đại; "đại, COD" pay=COD + agree 0.9 (chưa ở bước đọc lại nên không bị chặn).
**Bất thường lượt 6:** reader trả only_answers=False và LLM chính không gọi `order.create`; trả lời "Nếu anh/chị chưa tiện cho em địa chỉ… (COD, chuyển khoản, Momo, ZaloPay)" (kém hơn ui_replay_8 lượt này); gate không chạy lượt đó, nhưng lượt sau vẫn đi tiếp đúng. Nguyên nhân CHƯA điều tra (nghi: LLM chính không gọi order.create khi không có `_gate_retry_args`; chưa chứng minh).
**Độ trễ:** bộ đọc chạy TRƯỚC LLM chính nên cộng thẳng vào TTFT các lượt mua (+1,7–2,9 s). Chưa tối ưu (theo thứ tự đã chốt).

### 11.55. Điều tra + sửa câu lạ ở lượt 6 hội thoại A (2026-10-28) — KHÔNG gọi LLM
**Nguyên nhân (dựng lại offline):** câu "Nếu anh/chị chưa tiện cho em địa chỉ thì không sao…" do `reask.rewrite_reasks` sinh ra, không phải LLM. Lượt 5 agent hỏi địa chỉ; lượt 6 khách đưa địa chỉ nhưng LLM chính không gọi `order.create` (nên gate không chạy) và lại hỏi địa chỉ → reask coi địa chỉ là "khách chưa trả lời" (tập `answered` chỉ tính slot từ `extract_easy_slots` + SĐT; không có `delivery_address` trong easy slot) → đổi câu hỏi thành lời "không sao nếu chưa tiện" — sai sự thật vì khách vừa đưa địa chỉ. Bộ đọc lời khách KHÔNG gây ra (nó chỉ báo only_answers=False và driver không có đơn nháp để xử lý).
**Sửa (`orchestrator.py`):** `answered` thêm tín hiệu có cấu trúc: token `<ADDR_n>` của khách trong lượt → `delivery_address`; tên do bộ đọc LLM trích → `customer_name`. Test `ReaskIgnoresInfoGivenThisTurnTest` (2: sửa đúng; vẫn làm mềm khi khách thật sự không trả lời). Toàn bộ test: `runs/_unittest_full21.txt`.
**Còn lại (chưa sửa):** LLM chính vẫn có thể hỏi lại địa chỉ khách vừa đưa, và không gọi `order.create` ở lượt đó (nghi do lượt trước không có đơn nháp trong gate nên không có gì ép chạy gate). Câu hỏi lặp đó nay giữ nguyên (không còn lời sai) nhưng vẫn thừa. Chưa kiểm chứng bằng LLM thật.

### 11.56. Mở order gate bằng CODE khi khách cam kết mua (2026-10-28) — chưa chạy LLM thật
**Vấn đề:** gate chỉ chạy nếu LLM chính tình cờ gọi `order.create`; ui_replay_9 lượt 6 LLM không gọi → không gate, hỏi lặp. Không phải do trạng thái `skipped` (lượt 6 bộ đọc đã chạy).
**Thiết kế (theo đề xuất của người dùng, lớp 1+2+4, thêm lớp 5, bỏ lớp 3):** `orchestrator._maybe_open_gate` chạy khi `_order_driver` không có đơn nháp.
1. Ý định: trường mới `order_intent` + `intent_quote` (trích dẫn nguyên văn đã kiểm chứng) và `asks_question` trong lần đọc đang có (không thêm lần gọi).
2. Đối tượng (code): `_check_named_variants` tra tồn kho biến thể khách nêu; đúng 1 biến thể còn hàng → mở với SKU đó; 1 biến thể hết hàng → không mở; 0 hoặc nhiều biến thể → mở ở bước HỎI size/màu bằng SKU cha (lớp 5).
4. Loại trừ: `decline`, `asks_question`, đơn đã tạo, đã có đơn nháp, gate vừa chặn lệch giá/hết hàng/give_up ở lượt trước.
Gate vẫn là bên hỏi/đọc lại/chốt; mở nhầm chỉ làm agent hỏi thông tin giao hàng sớm, KHÔNG tạo đơn (test khẳng định). Lượt mở do code trả lời, LLM chính không chạy (tiết kiệm 1 lần gọi).
**Rào sau:** đơn nháp hết hạn sau `DRAFT_TTL_TURNS = 4` lượt im lặng (tự rút lui); trace `gate_open` ghi lý do từng lượt (`opened/reason/intent/object/exclusions`), `ui_replay` in dòng `[gate_open: …]` khi có ý định.
**Test:** `tests/test_gate_open.py` (7; LLM giả). Tắt `_maybe_open_gate` thì 5/7 đỏ (đã thử). 776 test OK (`runs/_unittest_full22.txt`).
**Chưa làm / chưa biết:** (a) bộ đọc thật có trả `order_intent` đúng không (chưa đo); (b) bộ cảnh nhãn "gate nên mở / không" để đo mở nhầm và bỏ sót — chờ câu khách thật; (c) lớp 3 (lượt trước agent đề nghị/hỏi đặt hàng, từ `extract_questions`) chưa cài; (d) lượt đầu nhắc biến thể + cam kết ngay (bộ đọc bị `skipped`) vẫn không mở gate.

### 11.57. Đọc muộn khi có tín hiệu (2026-10-28) — chưa chạy LLM thật
Khắc phục lỗ hổng § 11.56(d): lượt ĐẦU nhắc biến thể và cam kết ngay (bộ đọc `skipped` vì chưa có biến thể nào được tra). **Tín hiệu (do code):** `_check_named_variants` thấy khách nêu đủ size+màu của sản phẩm đang bàn ở lượt này → đọc MUỘN (1 lần gọi, `reply_reading.late = true`), rồi `_maybe_open_gate` dùng chính kết quả tra kho đó (không tra lại). Không có tín hiệu thì không đọc (lượt khám phá vẫn 0 lần gọi). SĐT khách xác nhận trong lần đọc muộn cũng được ghi (`phone_ok`).
**Test:** `LateReadTest` (3) trong `tests/test_gate_open.py`: mở gate ở lượt đầu, không biến thể thì không đọc, chỉ hỏi giá thì đọc 1 lần và không mở. Tắt khối đọc muộn thì test mở-gate đỏ (đã thử). Toàn bộ: `runs/_unittest_full23.txt`.
**Giới hạn:** nếu `product_advised`/lịch sử tra chưa cho biết sản phẩm cha, `_check_named_variants` không tìm được biến thể → không có tín hiệu (lượt đó do LLM chính xử lý như cũ). Đọc muộn thêm 1 lần gọi LLM ở đúng lượt lần đầu nhắc biến thể (≈ 4–5 VND, ≈ 1,8 s theo ui_replay_9) — chưa đo trên hội thoại thật.

### 11.58. ui_replay A–E (LLM thật) sau mở-gate-bằng-code + đọc muộn (2026-10-28)
Log `runs/ui_replay_10.txt`, **338,8 VND** (trần 450). **A trọn vẹn và đúng thiết kế:** lượt 3 "38 xám" (lần đầu nêu biến thể) → đọc muộn; lượt 5 "ok lấy 38 đen" → `[gate_open: opened]` (đúng 1 biến thể còn hàng, `SKU-SN-RUN2-38-DEN: True`), gate hỏi SĐT/địa chỉ/tên do CODE trả lời (LLM chính không chạy); lượt 6 chỉ còn hỏi thanh toán (hết câu lạ ở lượt 6 của ui_replay_9); lượt 7 đọc lại đơn; lượt 8 chốt `verify` đạt → OD600001. Mỗi lần đọc ≈ 5,3–5,6 VND, 1,9–2,5 s; lượt chốt 2 lần gọi 6,98 VND, 3,1 s.
**Lỗ hổng cấu trúc phát hiện:** B (máy lọc nước RO10, sản phẩm KHÔNG có biến thể) — bộ đọc `skipped` ở CẢ 5 lượt vì "ngữ cảnh mua" hiện chỉ tính khi đã tra/báo giá một BIẾN THỂ (SKU size+màu) và tín hiệu đọc muộn cũng chỉ là biến thể. Hệ quả: "6tr8 lấy luôn", "hiện tại chưa cần, sẽ gọi lại sau" không bao giờ được đọc bằng LLM; sản phẩm không biến thể không bao giờ mở gate bằng code. Chưa sửa.
**Chưa rõ:** dòng `[reader]` chưa in `order_intent` nên không biết lượt 3 "vậy cho tôi 38 xám đi" được đọc là commit hay không (không mở gate do hết hàng, đúng kết quả cuối).
**Lỗi cũ không đổi / dao động của LLM chính:** B vẫn gọi `handoff.transfer` (1 lần `brief_invalid`); C hỏi lại SĐT và không trả lời còn hàng; D "Máy lọc nước UF Sunhouse"; E lượt này LLM không gọi `pricing.get_quote` nên `product_advised` không lưu → Call Brief cuộc 2 mất sản phẩm, mở đầu chung chung (ui_replay_8 có) — dao động của LLM, chưa chứng minh liên quan thay đổi phiên.

### 11.59. Mở rộng ngữ cảnh mua cho sản phẩm KHÔNG có biến thể + `order_intent` trong dòng [reader] (2026-10-28) — chưa gọi LLM thật
Lỗ hổng § 11.58 (B: RO10 không biến thể → bộ đọc `skipped` cả hội thoại). **Sửa (`orchestrator.py`):** `_simple_product_in_play` — sản phẩm được tra/báo giá/đặt gần nhất, hoặc `catalog.search` ra đúng 1 sản phẩm, hoặc sản phẩm đã tư vấn, mà `_fetch_variants` rỗng → vào ngữ cảnh mua (bộ đọc chạy từ lượt sau, không còn `skipped`). `_maybe_open_gate`: khi cam kết mà không nêu biến thể nào, với SKU đơn code tự `inventory.check` đúng SKU đó (hết hàng → không mở; không tra được → `stock_unknown`, để LLM chính xử lý) rồi mở gate. `ui_replay` in thêm `intent=` và `asks=` trong dòng `[reader]`.
**Giới hạn thật:** "tín hiệu đọc muộn" cho SKU đơn KHÔNG có đối tượng để code phát hiện trước LLM (khác biến thể "38 đen" có thể khớp từ catalog); nên chỉ phủ khi sản phẩm đã vào cuộc (được báo giá/tư vấn/search ra 1 sản phẩm). Lượt ĐẦU vừa nêu sản phẩm đơn vừa cam kết vẫn do LLM chính xử lý. Bàn sản phẩm có biến thể thì vẫn cần nêu biến thể mới đọc.
**Test:** `SimpleProductTest` (3) trong `tests/test_gate_open.py`; vô hiệu hóa `_simple_product_in_play` thì test đỏ (đã thử). Toàn bộ: `runs/_unittest_full24.txt`.

### 11.60. ui_replay B (LLM thật) sau mở rộng ngữ cảnh mua cho SKU đơn (2026-10-28)
Log `runs/ui_replay_11.txt`, **125,2 VND** (trần 150). Bộ đọc chạy từ lượt 2 (không còn `skipped` cả hội thoại): "mắc quá vậy? 6tr8 lấy luôn" → stance=decline conf 0,8, intent=other, asks=True → KHÔNG mở gate (đúng: mặc cả, không phải cam kết); "không, mắc quá… giảm thêm 90k" → decline 1,0; "hiện tại chưa cần, sẽ gọi lại sau" → decline 1,0; "tôi tên Đại" → name=Đại. Mỗi lần đọc 5,5–5,7 VND, 1,9–2,3 s. Không mở gate nhầm lượt nào (0/4). Lần này LLM chính không gọi `handoff.transfer`.
**Chưa quan sát được:** đường MỞ gate cho SKU đơn bằng LLM thật (B không có lượt cam kết thật). Lượt cuối agent vẫn nói "Nếu anh/chị chưa tiện cho em số điện thoại thì không sao" (lời làm mềm của `reask`) sau khi khách chỉ nói tên; chưa điều tra vì sao đếm là hỏi lặp.

### 11.61. ui_replay F (sản phẩm không biến thể, LLM thật) (2026-10-28)
Thêm hội thoại F vào `ui_replay.py` (RO10: hỏi giá → "ok lấy luôn" → địa chỉ+tên → COD → chốt). Log `runs/ui_replay_12.txt`, **44,7 VND** (trần 100). Lượt 1 `skipped` (chưa có sản phẩm trước lượt); lượt 2 "ok lấy luôn": stance agree 1,0, **intent=commit**, `gate_open: opened` (code tự `inventory.check SKU-WF-RO10 → True` rồi mở gate; LLM chính không chạy), gate hỏi xác nhận SĐT + địa chỉ + tên; lượt 3 tên=Đại, xác nhận SĐT → chỉ hỏi thanh toán; lượt 4 COD → đọc lại đơn 6.890.000đ; lượt 5 chốt, `verify` đạt → OD600001. Mỗi lần đọc 5,2–5,6 VND, 1,7–2,1 s; lượt chốt 2 lần gọi 6,94 VND, 2,8 s. Quan sát: lượt 4 "COD" intent=other (đúng, không phải cam kết mới); lượt 5 "ok chốt" intent=commit nhưng gate đã có đơn nháp nên không mở lại (loại trừ `draft_already_open`).
Một lần chạy, chưa đo độ ổn định; chưa có ca khó (cam kết nhập nhằng, hai sản phẩm).

### 11.62. Bộ cảnh có nhãn đo "mở gate nhầm / bỏ sót" (2026-10-28) — chưa gọi LLM thật
`scripts/eval_gate_open.py`. **Phần A (cần `--llm`, chưa chạy):** 35 cảnh (câu cuối của agent, lời khách, nên mở?) nhóm theo bản chất: cam kết rõ (8, nên mở), cam kết nhập nhằng/có điều kiện (7), so sánh/hỏi (6), "ok" sau câu không liên quan mua hàng (6), mặc cả (3), từ chối (3), sửa thông tin (2) — dự đoán mở = bộ đọc `commit` ∧ ¬decline ∧ ¬asks; báo bỏ sót (lỗi gốc) và mở nhầm theo từng nhóm; nhận thêm cảnh thật qua `--cases` (JSONL `agent_last,text,open,kind`). Trần mặc định 300 VND (ước ~190 VND). **Phần B (offline, đã chạy):** 7 cảnh tầng ĐỐI TƯỢNG với bộ đọc giả luôn "cam kết".
**Kết quả B: 5/7 đúng sau khi sửa nhãn cảnh 5** (nhãn cũ của tôi sai: khi khách chưa nêu size/màu thiết kế là mở ở bước HỎI size/màu bằng SKU cha, không chọn biến thể LLM từng tra). **2 lỗi thật:** (1) hai sản phẩm đơn cùng được báo giá, khách "ok em lấy" không nói cái nào → code mở gate trên sản phẩm báo giá GẦN NHẤT (SKU-AP-X) — có thể sai sản phẩm; (2) một sản phẩm đơn, sau đó search ra nhiều kết quả (khách đang xem danh sách), "lấy" → mở trên sản phẩm cũ (SKU-WF-RO10). Gate đọc lại đơn nêu tên sản phẩm nên khách còn cơ hội sửa, nhưng "ok chốt" nhanh vẫn có thể đặt nhầm. Chưa sửa. Đề xuất: nếu cuộc gọi có >1 sản phẩm đơn được bàn gần đây (hoặc vừa có danh sách nhiều kết quả) → không mở (hoặc mở hỏi "mình lấy sản phẩm nào").

### 11.63. Không mở gate khi nhiều sản phẩm đang bàn (2026-10-28) — chưa gọi LLM thật
Sửa 2 lỗi § 11.62 (B). `orchestrator._products_in_play`: các sản phẩm CHA được bàn trong `RECENT_CALLS = 6` lời gọi tool cuối (tra/báo giá/đặt, hoặc `catalog.search` ra đúng 1 sản phẩm) + cờ "danh sách nhiều kết quả CHƯA chốt" (`catalog.search` ra >1 sản phẩm và sau đó chưa có lời gọi tra/báo giá/đặt). `_maybe_open_gate`: khi khách không nêu biến thể nào mà có >1 sản phẩm hoặc danh sách chưa chốt → KHÔNG mở, trace `gate_open.reason = "ambiguous_product"` + `object {products, listing}`; LLM chính xử lý (hỏi lại). Khách nêu rõ biến thể thì không bao giờ coi là mơ hồ.
**Kết quả:** `eval_gate_open.py` phần B **7/7** (trước 5/7). Test `AmbiguousProductTest` (4) — gỡ điều kiện thì 2 test đỏ (đã thử). Toàn bộ 786 test OK (`runs/_unittest_full25.txt`).
**Giới hạn:** "gần đây" = 6 lời gọi tool cuối (call_log không ghi lượt) — shortcut có chú thích; khách bàn sản phẩm A sớm rồi chuyển hẳn sang B vẫn bị coi là mơ hồ (an toàn, LLM chính hỏi lại, không tạo đơn). Cảnh 7 (đơn + biến thể, "lấy") vẫn "đúng" nhờ bộ đọc `skipped`, không nhờ lớp mới. Chưa đo bằng LLM thật.

### 11.64. Đo tầng Ý ĐỊNH của việc mở gate bằng LLM thật (2026-10-28)
`scripts/eval_gate_open.py --llm --max-cost 250`, log `runs/eval_gate_open_1.txt`, **185,6 VND**, 35 cảnh. (Lần chạy đầu thoát sớm vì phần B xóa khóa API khỏi môi trường → đã đổi chạy phần A trước.)
**Bỏ sót mở (lỗi gốc): 0/8. Mở nhầm: 4/27 (≈15%).** Theo nhóm (sai/tổng): cam_ket_ro 0/8, so_sanh_hoi 0/6, mac_ca 0/3, tu_choi 0/3, sua_thong_tin 0/2, ok_khong_lien_quan 1/6, nhap_nhang 3/7.
Mở nhầm: "chắc cũng lấy", "lấy thì lấy mà giá cao quá", "cũng được" (đều sau câu hỏi "có muốn đặt không?"), "được rồi" (sau thông tin giao hàng). Cả bốn là nhãn BIÊN: đọc theo nghĩa thông thường ba câu đầu nghiêng về đồng ý; mở nhầm chỉ khiến agent hỏi thông tin giao hàng sớm, gate vẫn phải đọc lại đơn + chốt verify mới tạo đơn. "ok/ừ/dạ vâng" sau câu không liên quan mua hàng: 5/6 đúng (intent=other dù stance=agree).
Giới hạn: câu do người viết code tự nghĩ, một lần chạy, nhãn biên có thể bàn; cần câu khách thật.

### 11.65. ui_replay A–F (LLM thật) — kiểm tra end-to-end cuối loạt thay đổi 2026-10-28
Log `runs/ui_replay_13.txt`, **414,5 VND** (trần 500; F riêng ≈ 45 VND, A–E ≈ 370 VND so với 374 ở `ui_replay_8` và 339 ở `ui_replay_10`).
**A:** gate mở bằng code ở "ok lấy 38 đen", hỏi đủ, đọc lại đơn, `verify` đạt → OD600001 (giống ui_replay_10; ui_replay_8 là LLM chính tự chuyển). Còn 2 `inventory.check` trùng lượt 4; lượt 3 LLM tự gọi SKU sai `SN-RUN2-38-XAM` → `unknown_sku` (vô hại, đã có tra đúng bằng code). **F:** mở gate cho SKU đơn, chốt `verify` đạt → OD600002. **B:** bộ đọc chạy từ lượt 2, mặc cả/hoãn = decline, không mở nhầm; lần này không gọi `handoff.transfer`, không còn câu "chưa tiện cho em số điện thoại" lạ.
**Không đổi / chưa sửa:** C hỏi lại SĐT, không trả lời còn hàng; D "Máy lọc nước UF Sunhouse" cho phòng 20 m² có bé 3 tuổi; E: 2 lần chạy liên tiếp (10, 13) LLM chính chỉ gọi `product.shortlist` nên `product_advised` không lưu → Call Brief cuộc 2 mở đầu chung chung (ui_replay_8 có sản phẩm); nghi do LLM dao động, chưa chứng minh. Lộ mã SKU (§ 12.3) không thấy lần này (E chỉ gọi shortlist).
**Độ trễ thêm:** bộ đọc 1,6–2,3 s mỗi lượt mua (có lượt 3,5 s), lượt chốt 2 lần gọi 2,5–4,9 s. Chưa tối ưu.

### 11.66. Hội thoại E mất `product_advised` — nguyên nhân + sửa (2026-10-28) — KHÔNG gọi LLM
**Nguyên nhân (dựng lại offline):** `_persist_tool_grounded_facts` chỉ ghi `product_advised`/`price_quoted_vnd` từ `order.create`, `order.update`, `pricing.get_quote`. Khi LLM chỉ gọi `product.shortlist` rồi nêu tên + giá niêm yết một sản phẩm (E ở ui_replay_10 và _13), không có gì được ghi → Call Brief cuộc 2 mất sản phẩm, mở đầu chung chung. Không phải hồi quy do thay đổi phiên: logic này không đổi; ui_replay_8 có sản phẩm vì lần đó LLM còn gọi thêm `pricing.get_quote` (LLM dao động). Test dựng lại: trước sửa `product_advised = None`.
**Sửa:** khi không có báo giá, nếu lời agent nêu tên ĐÚNG MỘT sản phẩm có trong kết quả `product.shortlist` của lượt → ghi `product_advised` (không ghi giá: shortlist chỉ có giá niêm yết, chưa qua khuyến mãi). Nêu nhiều sản phẩm hoặc không nêu → không ghi. Test `tests/test_advised_from_shortlist.py` (2). Toàn bộ: `runs/_unittest_full26.txt`.
**Giới hạn:** so khớp bằng TÊN sản phẩm trong lời agent (chuỗi con không phân biệt hoa thường): tên là chuỗi con của tên khác (vd "AirPure X" trong "AirPure X Pro") → coi là nhiều sản phẩm → không ghi (an toàn). Chưa kiểm chứng bằng LLM thật.

### 11.67. ui_replay E (LLM thật) sau sửa `product_advised` từ shortlist (2026-10-28)
Log `runs/ui_replay_14.txt`, **71,1 VND** (trần 100). Lượt 2 agent nêu "AirPure X" từ shortlist → bộ nhớ sau cuộc E: `product_advised = SKU-AP-X` (trước: thiếu). Call Brief cuộc 2: blocker=can hoi chong, tên=Lan, xưng hô=chị, mở đầu "…hôm 15/10 bên em có tư vấn chị AP-X cho phòng 20m²…" (có sản phẩm, so với mở đầu chung chung ở ui_replay_10/13). Sửa đã có tác dụng, một lần chạy.
**Lỗi cũ còn lộ rõ khi có sản phẩm:** (a) mở đầu Call Brief đọc mã rút gọn "chị AP-X" cho khách; (b) LLM nói "tặng kèm bộ lọc SKU-AP-FLT-X" (lộ mã SKU, § 12.3). **Tác dụng phụ ghi nhận:** lượt đầu cuộc 2 ("alo em, chị gọi lại đây") bộ đọc chạy (5,13 VND, 1,9 s) vì sản phẩm đơn đã tư vấn từ cuộc trước → vào ngữ cảnh mua; không cần cho câu chào, chưa tối ưu.

### 11.68. Lỗi lộ mã SKU — sửa bằng cấu trúc (2026-10-28) — KHÔNG gọi LLM
**Nguyên nhân (2):** (1) `pipeline.py` dựng `CallBriefBuilder` KHÔNG truyền `tool_gateway` (chỉ `tests/_helpers` có) → `_product_name` không tra được catalog và luôn rơi về mã rút gọn → câu chào "tư vấn chị AP-X"; (2) LLM tự nêu mã trong lời nói ("tặng kèm bộ lọc SKU-AP-FLT-X").
**Sửa:** `pipeline.py` truyền `tool_gateway=self.mcp_gateway`; `call_brief._product_name` không còn dùng mã làm tên (fallback "sản phẩm mình quan tâm"); `orchestrator._mask_sku_codes` ở tầng đầu ra: mọi `SKU-...` trong lời gửi khách → TÊN sản phẩm từ catalog (biến thể: "…size X màu Y"; mã không có trong catalog: "sản phẩm này"); thay trước `strip_markdown` nên lịch sử lưu bản đã làm sạch.
**Test:** `tests/test_sku_leak.py` (5). Gỡ truyền gateway hoặc gỡ bước thay thì test đỏ (đã thử). Toàn bộ: `runs/_unittest_full27.txt`.
**Giới hạn:** chỉ bắt mã dạng `SKU-…` viết hoa; mã viết tắt do LLM tự đặt ("AP-X" không có "SKU-") không bị bắt (nguyên nhân chính của "AP-X" đã gỡ ở nguồn). Quà tặng đọc ra tên catalog ("bộ lọc Bộ lọc …" có thể lặp từ). Chưa kiểm chứng bằng LLM thật.

### 11.69. ui_replay E (LLM thật) sau sửa lộ mã SKU (2026-10-28)
Log `runs/ui_replay_15.txt`, **84,7 VND** (trần 100). Không còn mã SKU/"AP-X" trong lời agent (0/3 lượt). Bộ nhớ: `product_advised = SKU-AP-X`. Mở đầu Call Brief cuộc 2: "Dạ em chào chị Lan, hôm 15/10 bên em có tư vấn chị Máy lọc không khí AirPure X cho phòng 20m². Chị đã trao đổi lại với gia đình chưa ạ…" (trước: "tư vấn chị AP-X"). Lời LLM cuộc 2 tự nêu "tặng kèm bộ lọc không khí AirPure X" — LLM tự viết tên, nên lần này chưa chứng minh được bước thay mã chạy trên LLM thật (đã chạy trong test); tên catalog của quà là "Màng lọc thay thế AirPure X/Y" nên nếu LLM nêu mã thì sẽ ra "bộ lọc Màng lọc thay thế AirPure X/Y".
**Còn lệch:** khuôn câu chào "có tư vấn {xưng hô} {tên sản phẩm}" đọc gượng khi có tên đầy đủ ("tư vấn chị Máy lọc không khí AirPure X"). Chưa sửa.

### 11.70. Khuôn câu chào Call Brief bỏ xưng hô trước tên sản phẩm (2026-10-28) — KHÔNG gọi LLM
`call_brief.py`: "…bên em có tư vấn {honorific} {prod_name}" → "…bên em có tư vấn {prod_name}" (đọc gượng "tư vấn chị Máy lọc không khí AirPure X" khi có tên đầy đủ). Test: `test_cluster_9_10.OpeningSentenceTest` kiểm "bên em có tư vấn Máy lọc không khí AirPure Y" và không có xưng hô ngay sau "tư vấn". Các test khác về câu chào (xưng hô/tên khách "chị Lan") không đổi. Toàn bộ: `runs/_unittest_full28.txt`.

### 11.71. Điều tra + sửa C và D (2026-10-28) — KHÔNG gọi LLM
**C (khách nói đã liên hệ trước, agent chỉ hỏi SĐT, bỏ câu "còn hàng không"):** gốc là CHÍNH chỉ dẫn của hệ thống: prompt + một dòng ngữ cảnh (kích hoạt bằng regex từ khóa "hôm trước/lần trước/đã gọi…") đều bảo "hỏi MỘT câu xin SĐT… KHÔNG đoán", không dặn vẫn phải trả lời câu hỏi hiện tại → LLM chỉ gọi `crm.get_customer` rồi hỏi SĐT. **Sửa:** bỏ dòng regex; thêm vào Call Brief trạng thái `số cuộc gọi trước: N` (code ghi, không dò từ khóa); chỉ dẫn trong system prompt (cache được) nay nói rõ: (1) TRẢ LỜI câu hỏi hiện tại bằng tool ngay lượt này, (2) rồi hỏi MỘT câu xin SĐT/tài khoản. **Giới hạn thật:** vẫn là chỉ dẫn cho LLM, không có chốt cấu trúc bắt buộc phải trả lời; hiệu quả CHƯA đo.
**D ("Máy lọc nước UF Sunhouse phù hợp phòng 20m², an toàn cho trẻ nhỏ"):** gốc là KHÔNG CÓ CĂN CỨ: khách đang hỏi máy lọc nước, LLM gọi `product.shortlist` với category máy lọc nước; các luật diện tích phòng/trẻ em không áp dụng cho nhóm này → cả 3 sản phẩm điểm 0, `matched = []`, sản phẩm đứng đầu chỉ do giá thấp nhất, nhưng kết quả vẫn có `decision.primary` như một đề xuất → LLM khẳng định phù hợp. (Lời khách "phòng 20m², có bé" nghe giống nhu cầu máy lọc KHÔNG KHÍ — không đoán thay khách.) **Sửa (`_run_shortlist`):** nếu khách có nêu slot mà KHÔNG sản phẩm nào có tiêu chí khớp → kết quả có `no_basis: true`, `decision = {mode: no_basis}` (bỏ `primary`) và chỉ dẫn: không được nói "phù hợp/an toàn/đáp ứng", nói rõ thông tin đó chưa dùng để chọn sản phẩm trong nhóm này và hỏi khách đang cần loại nào. Không gắn cờ khi khách chưa nêu slot nào. **Giới hạn:** vẫn dựa vào LLM làm theo chỉ dẫn trong kết quả tool (không có chốt guardrail theo cấu trúc cho câu "phù hợp"); hiệu quả CHƯA đo.
**Test:** `ShortlistNoBasisTest` (3) + cập nhật `CrossChannelHintsTest`. Gỡ điều kiện `no_basis` thì test đỏ (đã thử). Toàn bộ: `runs/_unittest_full29.txt`.

### 11.72. ui_replay C, D (LLM thật) sau sửa § 11.71
Log `runs/ui_replay_16.txt`, **70,7 VND** (trần 120). **C: đỡ một phần.** Agent trả lời ngay "Máy lọc nước RO Kangaroo 10 lõi hiện còn hàng với số lượng 12 chiếc" (`catalog.search` + `inventory.check`, SKU-WF-RO10 True) thay vì chỉ hỏi SĐT; nhưng bỏ luôn bước (2) hỏi SĐT/tài khoản lần trước → chưa nối được hồ sơ cũ. **D: đỡ một phần.** Có `no_basis` tác dụng: agent nói "không có tiêu chí nào cụ thể để chọn sản phẩm an toàn cho trẻ nhỏ trong nhóm này", liệt kê 3 sản phẩm theo giá, hỏi ngân sách; nhưng câu mở vẫn nói "máy lọc nước phù hợp với phòng 20 mét vuông và có bé 3 tuổi" (tự mâu thuẫn) và không hỏi khách cần loại sản phẩm nào. Một lần chạy mỗi hội thoại. Cả hai cải thiện dựa vào chỉ dẫn cho LLM, chưa có chốt cấu trúc.

### 11.73. Chốt CẤU TRÚC cho C và D (2026-10-28) — chưa gọi LLM thật
Sau § 11.72 (cả hai chỉ đỡ một phần vì dựa vào chỉ dẫn cho LLM).
**C (khách nói đã liên hệ, hệ thống chưa có lịch sử):** bộ đọc thêm `claims_prior_contact` + `prior_contact_quote` (trích dẫn nguyên văn đã kiểm chứng). Khách MỚI (số cuộc gọi trước = 0) được đọc ở 2 lượt đầu (`new_customer_early`; chi phí: +1 lần gọi ≈ 5 VND/1,9 s mỗi lượt đó, chủ ý chưa tối ưu). Sau khi có lời agent, `_ensure_prior_contact_question`: nếu khách nói đã liên hệ mà lời agent chưa có câu xin SĐT (kiểm bằng `extract_questions` slot phone) → CODE nối "Để em tra lại lịch sử, {xưng hô} cho em xin số điện thoại hoặc tài khoản mà mình đã dùng ở lần liên hệ trước ạ?"; đúng MỘT lần/cuộc (`_prior_asked`); LLM đã tự hỏi thì giữ nguyên; trích dẫn bịa hoặc khách đã có lịch sử thì không làm gì.
**D (shortlist `no_basis`):** `_no_basis_reply`: lượt CHỈ gọi `product.shortlist` mà kết quả `no_basis` → CODE dựng lời: "Dạ em chưa có tiêu chí nào để chọn sản phẩm trong nhóm này theo {nhãn slot} {xưng hô} vừa nói ạ. Em xin giới thiệu theo giá niêm yết: {tên + giá từ tool}. {Xưng hô} đang cần loại sản phẩm nào…?" — thay hẳn lời LLM, không dò từ khóa "phù hợp". Có tool khác chạy cùng lượt, hoặc luật có áp dụng → giữ lời LLM.
**Test:** `tests/test_structural_guards.py` (8); gỡ hai chốt thì test đỏ (đã thử). Các test về "bộ đọc bỏ qua ở lượt khám phá" phải thêm bước `burn_early` (cửa sổ đọc 2 lượt đầu của khách mới) — đổi hành vi có chủ ý. Toàn bộ: `runs/_unittest_full30.txt`.
**Giới hạn:** (1) C: kiểm "đã hỏi SĐT chưa" bằng `extract_questions` (danh sách từ khóa) — thất bại thì chỉ nối thừa một câu; (2) D: thay cả lời LLM nên mất phần khác khách hỏi cùng lượt (chỉ làm khi lượt chỉ có shortlist); (3) LLM thật có điền `claims_prior_contact` đúng không: CHƯA đo.

### 11.74. ui_replay C, D (LLM thật) sau chốt cấu trúc § 11.73
Log `runs/ui_replay_17.txt`, **82,8 VND** (trần 150). **C: đạt cả hai bước.** Agent trả lời "Máy lọc nước RO Kangaroo 10 lõi hiện còn hàng với số lượng 12 chiếc" (tool: catalog.search + inventory.check True) VÀ có câu "Để em tra lại lịch sử, anh/chị cho em xin số điện thoại hoặc tài khoản mà mình đã dùng ở lần liên hệ trước ạ?" — đúng khuôn câu do CODE nối (LLM không tự hỏi). **D: hết khẳng định không căn cứ.** Lời do code dựng từ tool: "chưa có tiêu chí nào để chọn sản phẩm trong nhóm này theo diện tích phòng, trẻ nhỏ…", 3 sản phẩm + giá niêm yết đúng tool, hỏi "loại sản phẩm nào" (không còn "phù hợp phòng 20m² / an toàn cho trẻ"). Bộ đọc chạy ở lượt 1 của khách mới (5,6–6,1 VND, 2–3,6 s) đúng thiết kế. Một lần chạy mỗi hội thoại. `ui_replay` in thêm `prior=` trong dòng [reader].
Còn: C hai câu hỏi liền nhau ("Anh có muốn biết thêm…? Để em tra lại…") và xưng hô lẫn "anh/chị … Anh" (lỗi cũ); D câu "theo diện tích phòng, trẻ nhỏ trong nhà anh/chị vừa nói" đọc hơi gượng.

### 11.75. ui_replay A–F (LLM thật) — kiểm tra tổng cuối, so với ui_replay_13 (2026-10-28)
Log `runs/ui_replay_18.txt`, **500,5 VND** (trần cứng nâng 500→550; ui_replay_13: 414,5). Chênh +86 VND chủ yếu do bộ đọc nay chạy cả lượt 1–2 của khách mới (≈ 5,6–6,1 VND/lần, 1,5–2,9 s).
**Giữ/ tốt hơn 13:** A (gate mở bằng code → OD600001), F (OD600002), C (trả lời "còn hàng 12 chiếc" + code nối câu xin SĐT lần trước, `prior=True`), D (lời do code dựng, không còn "phù hợp/an toàn" không căn cứ), E (lưu `product_advised`, mở đầu cuộc 2 nêu tên "Máy lọc không khí AirPure X", khuôn câu hết xưng hô gượng, không lộ mã SKU).
**Tệ hơn 13 — B:** LLM chính tự gọi `handoff.transfer` khi khách chưa đồng ý, lượt 2 (3 lời gọi: 2 `brief_invalid` rồi 1 chạy được) và lượt 3 (1 chạy được), nói "Em sẽ chuyển máy cho nhân viên"; ui_replay_13 không có handoff. Hệ quả phụ: handoff chốt episode ngay trong cuộc → lượt cuối ("tôi tên Đại") agent dùng câu chào Call Brief kiểu quay lại ("Hôm 15/10 bên em có tư vấn… Anh đã trao đổi với người nhà chưa ạ?") giữa cuộc gọi. Lỗi cũ (§ 12.3) chưa có chốt cấu trúc; LLM dao động giữa các lần chạy.
**Còn:** A lượt 3–4 còn `inventory.check` trùng; C hai câu hỏi liền nhau; xưng hô lẫn "anh/chị … Anh" (C, B).

### 11.76. Chốt cấu trúc cho `handoff.transfer` (2026-10-28, chưa gọi LLM thật)
**Lỗi:** ui_replay_18 B — LLM chính tự chuyển máy khi khách mới mặc cả; chỉ dẫn prompt "chỉ chuyển khi khách đồng ý" đã có sẵn nhưng LLM không theo (§ 12.3).
**Phương án đã cân nhắc:** (1) thêm trường `handoff` vào bộ đọc chạy mọi lượt — tốn một lần LLM/lượt dù chuyển máy hiếm; (2) regex "cho gặp nhân viên" — bị loại (nguyên tắc LLM-first); (3) **chốt theo yêu cầu** — chỉ khi LLM chính định gọi `handoff.transfer` mới gọi một lần LLM hẹp (độc lập, prompt riêng, không thấy lập luận của LLM chính). Chọn (3): không tốn gì ở lượt thường.
**Cài đặt:** `reply_reader.authorize_handoff` + `HANDOFF_PROMPT`: chỉ hai căn cứ — `asked` (khách tự yêu cầu người/bộ phận khác) hoặc `accepted_offer` (câu cuối của nhân viên có đề nghị chuyển, khách chấp nhận không điều kiện); bắt buộc trích dẫn nguyên văn (cùng `_quoted`), thiếu/bịa/lỗi/không có LLM → không cho chuyển. `_tool_executor` chặn `handoff.transfer` bằng kết quả `handoff_blocked` (kèm chỉ dẫn "tiếp tục trả lời, hỏi MỘT câu khách có muốn nhờ nhân viên không"), chốt một lần/lượt dù LLM thử nhiều lần, lời gọi bị chặn không vào `tool_calls` và không chốt episode. Trace thêm `handoff_check` (authorized/basis/quote/vnd_cost), `ui_replay.py` in `[handoff_check: …]`. Prompt: xóa dữ liệu cá nhân nay phải hỏi khách đồng ý chuyển rồi mới gọi tool.
**Sửa phụ (nguyên nhân câu chào "gọi lại" giữa cuộc):** `CallBriefBuilder.build` bỏ episode có `session_id == SESS-{cid}-{ngày}` (episode do handoff chốt giữa cuộc là của CHÍNH cuộc này, không phải cuộc trước).
**Kiểm chứng:** `tests/test_handoff_guard.py` (7 test: trích dẫn bịa/căn cứ sai/lỗi/không LLM; chặn khi khách mới mặc cả, chỉ một lần chốt/lượt, không chốt episode; cho chạy khi khách yêu cầu; không chốt khi LLM không thử chuyển; brief không đếm episode của chính cuộc, ngày khác thì đếm). Sửa `test_cluster_9_10` (kịch bản handoff nay cần khách tự yêu cầu + 1 câu JSON chốt). Toàn bộ: **811 test OK** (`runs/_unittest_full31.txt`).
**Chưa làm/rủi ro:** chưa đo bằng LLM thật (B kỳ vọng `handoff_check.authorized=False` ở lượt 2–3); LLM chính vẫn có thể *nói* "em chuyển máy" dù tool bị chặn (chỉ dẫn trong kết quả tool, chưa có chốt đầu ra); kịch bản dataset "giao trễ → chuyển máy" nay cần khách đồng ý trước nên có thể chậm một lượt.

### 11.77. Chuyển máy tách theo lý do + chạy LLM thật B, G (2026-10-28)
**Yêu cầu:** thay một chốt chung (§ 11.76) bằng hai ca: ngoài phạm vi/an toàn → chuyển ngay, không cần khách yêu cầu, nhưng chốt độc lập phải xác nhận khách thật sự thuộc loại này kèm trích dẫn nguyên văn; thương lượng giá/mặc cả → giữ chốt cũ (khách yêu cầu hoặc đồng ý).
**Cài đặt:** `HANDOFF_PROMPT` mới (một lần gọi độc lập, trả `category` + `category_quote` + `authorized/basis/quote`): loại A `scope_safety` (y tế/thuốc/an toàn trẻ nhỏ/pháp lý/sự cố đơn/dữ liệu cá nhân — khớp PB-06 playbook), prompt nói rõ giá/mặc cả/chê đắt KHÔNG thuộc A. Code: `category=scope_safety` + trích dẫn kiểm chứng được → cho chuyển (`basis=scope_safety`); trích dẫn bịa/thiếu → rơi về ca B (cần `asked`/`accepted_offer` kèm trích dẫn). Trace `handoff_check` thêm `category`; prompt hệ thống tách hai ca.
**Lỗi phát hiện khi chạy thật và đã sửa:** G lượt 2 chốt cho chuyển nhưng tool trả `brief_invalid` (LLM thiếu trường bắt buộc của hợp đồng handoff) → agent nói đã chuyển mà chưa chuyển, và không chốt episode. Nay `_complete_handoff_brief` điền các trường LLM thiếu từ dữ kiện code biết (Call Brief, lời khách đã kiểm chứng, ngày); trường LLM đã điền được giữ.
**LLM thật:** `runs/ui_replay_19.txt` (B+G, 205,0 VND — tôi tự đặt trần 200 vì chưa có trần được duyệt; chạm trần chỉ vượt 5 VND do kiểm tra trước mỗi lần gọi) rồi `runs/ui_replay_20.txt` (G sau sửa brief, 52,5 VND).
- **B:** không có handoff nào chạy cả 5 lượt; lượt 2–3 `handoff_check authorized=False category=other` (chặn đúng), agent trả giá niêm yết và hỏi "có muốn nhờ nhân viên không". Không còn câu chào "gọi lại" giữa cuộc.
- **G:** lượt 1 (hỏi khóa trẻ em) không chuyển; lượt 2 (bé uống thuốc hen) `authorized=True category=scope_safety` quote nguyên văn cả câu, `handoff.transfer` chạy thành công, bộ nhớ ghi `blocker=an toan cho tre`, lời agent nói chuyển máy khớp thực tế.
**Test:** `tests/test_handoff_guard.py` 11 test (thêm: scope_safety cần trích dẫn thật, mặc cả bị gắn nhầm scope_safety với trích dẫn bịa vẫn bị chặn, brief được điền). Toàn bộ **815 test** — xem `runs/_unittest_full33.txt`.
**Chưa làm/rủi ro:** mỗi ca chỉ chạy một lần (LLM dao động); chưa thử ca "giao trễ/xóa dữ liệu" và ca khách mặc cả rồi đồng ý chuyển (`accepted_offer`) bằng LLM thật; ca A phụ thuộc phán đoán của LLM chốt nên chưa đo tỉ lệ gắn nhầm "mặc cả" thành A; LLM chính có thể vẫn *nói* chuyển máy khi ca B bị chặn (chưa có chốt đầu ra). Dòng thử "ui_replay G" thêm vào script (hội thoại G).

### 11.78. ui_replay H, I, J (LLM thật) — chuyển máy theo lý do (2026-10-28)
Thêm 3 hội thoại vào `scripts/ui_replay.py`: H (xóa dữ liệu cá nhân), I (khách C032 Tâm, đơn OD301177 đang shipping từ 03/10, hỏi sao chưa nhận hàng; gọi ngày 25/10), J (mặc cả rồi đồng ý chuyển, 2 lượt). Log `runs/ui_replay_21.txt`, **112,2 VND** (trần 120; chạy theo thứ tự J, H, I để nếu chạm trần thì cụt ca ít quan trọng nhất — không chạm).
- **J — đúng:** lượt 1 (mặc cả 6tr8) LLM chính không thử chuyển máy; lượt 2 ("ừ, nhờ nhân viên hỗ trợ giá giúp tôi") `handoff_check authorized=True category=other basis=accepted_offer`, quote nguyên văn, `handoff.transfer` chạy, bộ nhớ ghi blocker/objection/product_advised. Lưu ý: lượt 1 agent KHÔNG hề đề nghị chuyển máy, nên nhãn `accepted_offer` thực chất là khách tự yêu cầu (`asked`) — vô hại, cùng yêu cầu bằng chứng.
- **H — đúng:** `authorized=True category=scope_safety basis=scope_safety`, quote cả câu; chuyển máy chạy (ticket HT0002), agent nói "đã chuyển bộ phận phụ trách".
- **I — chốt không được thử:** LLM chính không gọi `handoff.transfer`; chỉ `order.status` rồi trả "đang giao hàng, mã vận đơn GHN7781234" dù đơn đặt 22 ngày chưa tới. Chốt chỉ CHẶN, không ÉP chuyển; có chuyển hay không do LLM chính quyết (hiện bỏ sót ca khiếu nại này).
- **Lỗi mới thấy ở I:** bộ đọc đánh `prior=True` (khách nhắc "đơn của tôi đặt từ hôm 3/10") và code nối câu "Để em tra lại lịch sử, chị cho em xin số điện thoại…" dù khách gọi từ SĐT có sẵn trong CRM (đã nhận ra tên Tâm, xưng "chị") — điều kiện nối câu dùng `previous_calls_count == 0` mà khách CRM chỉ có đơn, chưa có episode.
**Chưa làm:** quyết định có ÉP chuyển ở ca khiếu nại đơn (code tự kích bằng chốt phân loại?) hay để LLM chính; sửa điều kiện nối câu xin SĐT cho khách đã biết qua CRM.

### 11.79. Không xin lại SĐT lần trước với khách đã biết qua CRM (2026-10-28, chưa gọi LLM thật)
**Lỗi (ui_replay_21 ca I):** khách Tâm gọi từ SĐT có hồ sơ CRM (tên + đơn OD301177) nhưng chưa có episode → `previous_calls_count == 0`; bộ đọc đánh `prior=True` và code nối "Để em tra lại lịch sử, chị cho em xin số điện thoại…" dù đã nhận ra khách.
**Sửa:** `CallBrief.crm_known` (mới) = SĐT khớp hồ sơ CRM `found` có tên hoặc đơn (lấy từ `identity.customer_profile`, KHÔNG dùng tên vừa nghe trong cuộc — ca C khách mới tự xưng tên vẫn bị hỏi). `_ensure_prior_contact_question` bỏ qua khi `crm_known`; `new_customer_early` cũng tắt khi `crm_known` (khách CRM không tốn lần đọc "đã liên hệ trước" ở lượt 1–2, ≈ 6 VND/lần); prompt "NHẬN DIỆN KHÁCH" và dòng Call Brief thêm điều kiện/nhãn "khách đã có trong CRM".
**Test:** `tests/test_structural_guards.py` +2 (khách CRM: brief `crm_known`, không đọc/không nối câu, lớp nối câu chặn riêng; tên nghe trong cuộc ≠ CRM). Toàn bộ test xem `runs/_unittest_full34.txt`.
**Chưa kiểm:** chưa chạy lại ca I bằng LLM thật; khách CRM thật có nhắc "đã liên hệ" nhưng bằng SĐT KHÁC sẽ không được xin lại SĐT (chấp nhận: đã nhận ra bằng SĐT đang gọi).

**Chạy LLM thật (`runs/ui_replay_22.txt`, I + C, 47,7 VND, trần 60):**
- **I:** `reader: skipped` (không tốn lần đọc), không còn câu xin SĐT; agent trả trạng thái đơn OD301177 "đang giao hàng" + mã vận đơn. Vẫn không gọi `handoff.transfer` (đơn 22 ngày chưa tới, quyết định ép chuyển chưa làm).
- **C:** khách mới tự xưng Đại: `prior=True`, trả lời "còn hàng 12 chiếc" rồi vẫn có câu "Để em tra lại lịch sử… xin số điện thoại hoặc tài khoản…". Còn hai câu hỏi liền nhau và "anh/chị … Anh" (đã ghi từ § 11.75).

### 11.80. Ép chuyển máy ca khiếu nại đơn (phương án B) + dọn lỗi nhỏ (2026-10-28, chưa gọi LLM thật)
**1B — khiếu nại đơn đã đặt:** lượt nào LLM gọi `order.status` (có đơn trả về) mà không tự chuyển máy → CODE gọi `authorize_handoff` kèm "Dữ kiện hệ thống" (hôm nay + id/trạng thái/ngày đặt/dự kiến giao/vận đơn của đơn). Prompt chốt loại A nay nêu "sự cố/khiếu nại đơn đã đặt — trễ, sai, hỏng, mất; chỉ hỏi tình trạng bình thường thì KHÔNG". Nếu `scope_safety` + trích dẫn nguyên văn đúng → code chạy `handoff.transfer` (brief do code điền), nối câu "Em đã chuyển thông tin đơn cho nhân viên phụ trách kiểm tra, nhân viên sẽ liên hệ lại {xưng hô} ạ." Chi phí thêm: một lần LLM (~2,7 VND) CHỈ ở lượt có tra đơn.
**2a — C:** `_ensure_prior_contact_question` bỏ câu hỏi xã giao cuối lượt của LLM khi nối câu xin SĐT (chỉ còn MỘT dấu "?"); `_fix_addressing` đổi cả "Anh/Chị" đầu câu về "Anh/chị" khi chưa biết xưng hô.
**2b — A:** `inventory.check` mà code đã tra đầu lượt (pre_stock) được trả từ kết quả đó (`already_checked_this_turn`), không gọi tool lần hai và không vào trace.
**Test:** `tests/test_oct28_followups.py` (chuyển máy khi chốt thấy khiếu nại + thấy dữ kiện đơn; câu hỏi tình trạng thường không chuyển; trích dẫn bịa không chuyển; không chốt thừa khi không tra đơn; một câu hỏi/xưng hô đầu câu; không tra trùng). Toàn bộ **832 test OK** (`runs/_unittest_full35.txt`).
**Chưa kiểm bằng LLM thật:** ca I (kỳ vọng chuyển + câu báo), C (một câu hỏi), A (không `inventory.check` trùng). Rủi ro: trigger chỉ khi LLM có gọi `order.status` — khách khiếu nại mà LLM không tra đơn thì không có chốt; chốt dựa phán đoán LLM nên có thể gắn nhầm hỏi-thăm-đơn thành sự cố.
**Chưa làm (cần đầu vào từ bạn):** đo trên câu khách thật (cần file JSONL), tối ưu token/TTFT (cần chạy đo với LLM thật + trần), bước 13/15 GĐ2, dataset, hồ sơ nộp (quyết định riêng).

**Chạy LLM thật (`runs/ui_replay_23.txt`, A C I, trần 120 → DỪNG, 126 VND):** hội thoại A một mình đã tốn ≈ 126 VND nên trần 120 cạn ở lượt 7 của A; **C và I chưa chạy**.
- **A (lượt 1–7):** không còn `inventory.check` trùng — lượt 3 (38 xám) và lượt 4 (38 đen) mỗi lượt đúng MỘT `inventory.check`; gate mở bằng code (`variant_out_of_stock`, rồi `opened`), tiến trình hỏi SĐT → thanh toán → đọc lại đơn như cũ. Lượt 2 vẫn có `inventory.check` với SKU cha `SKU-SN-RUN2` (LLM tự gọi, trả in_stock=True — kỳ lạ nhưng không trùng). Lượt 5 câu của gate có chỗ nối vụng: "…đúng không ạ? mình cho em xin địa chỉ…" (chưa điều tra).
- **C, I:** chưa có kết quả; cần chạy lại với trần riêng (≈ 70 VND cho hai ca).

**Chạy LLM thật (`runs/ui_replay_24.txt`, I + C, 44,8 VND, trần 70):**
- **I — có chuyển + có câu báo:** LLM chính chỉ gọi `order.status` (trả "đang giao hàng", mã vận đơn GHN7781234); CODE gọi chốt (3,08 VND) → `authorized=True category=scope_safety`, trích dẫn nguyên câu, chạy `handoff.transfer` và nối "Em đã chuyển thông tin đơn cho nhân viên phụ trách kiểm tra, nhân viên sẽ liên hệ lại chị ạ." Không còn câu xin SĐT; `reader: skipped`. Lưu ý: câu LLM vẫn nói "Nếu chị cần thêm thông tin gì khác…" trước câu báo (không mâu thuẫn). Bộ nhớ ghi `objection=chưa nhận được hàng`.
- **C — còn MỘT câu hỏi:** "…còn hàng với số lượng 12 chiếc ạ. Để em tra lại lịch sử, anh/chị cho em xin số điện thoại…" — câu xã giao cuối của LLM bị thay; xưng hô thống nhất "anh/chị".
- Phần A (không `inventory.check` trùng) xem ui_replay_23.

### 11.81. Bước 14a — pipeline đánh giá tách riêng `evaluation/` + dọn dead code (2026-10-28, KHÔNG gọi LLM)
**Làm:** package `evaluation/` chạy process riêng (`python -m evaluation --trace runs/X/full.jsonl [--baseline …] [--scenarios DIR] [--out-dir DIR]`), chỉ đọc trace JSONL + kịch bản, không import `src.*`/pipeline/run_eval (test AST kiểm). `scoring.py` nạp `BTC-Data-Vong1-TEAMS/eval/reference_eval.py` theo đường dẫn file và gọi `evaluate()` (báo cáo cùng cấu trúc `system/baseline/comparison`); `failures.py` liệt kê ca sai (kịch bản, cuộc gọi, lượt, chỉ số: `tsr`/`ccr`/`rqr`/`hr`/`guardrail`/`missing_trace`/`parrot`) bằng cách gọi lại hàm chấm của BTC từng kịch bản một (không chép lại logic); `parrot.py` kiểm "đọc vẹt" bằng luật: lượt 1 của cuộc gọi thứ 2 trở đi nhắc > 2 fact cũ (`--max-old-facts`; rubric J01 của BTC cho tới 3); `sheet.py` chọn 20 lượt xen kẽ giữa kịch bản, ưu tiên lượt đã bị đánh dấu sai, ghi `manual_review.csv` (UTF-8 BOM, cột chấm tay: đúng sản phẩm / không hỏi lại / không đọc vẹt / không bịa số / xưng hô tự nhiên / ghi chú).
**Ví dụ (từ `runs/buoc15_I/full.jsonl`, kết quả ở `runs/eval14a_buoc15_I/`):** TSR 85,7 · RQR 3,7 · CCR 47,6 · HR giá/KM 15,4 · guardrail 0 — trùng `runs/buoc15_I/report.json`; 10 ca sai (SAMPLE-01 call_2 trượt TSR + hỏi lại sản phẩm + 2 claim giá 4.890.000 ≠ 5.200.000; 5 ca CCR chưa mang sang; SAMPLE-06 call_2 câu chào đọc vẹt 3 fact: sản phẩm, diện tích, giá).
**Dead code:** grep toàn repo (trừ `backup_*`, `runs/`) — `ReferenceEvaluator`, `CustomerSimulator`, `HumanReviewGate`, `ImprovementLoop` chỉ được `src/eval/__init__.py` import, không script/test/entrypoint nào gọi → đã gỡ 4 file; `src/eval/__init__.py` chỉ còn `ScenarioRunner`. Bước 16 sẽ viết lại `improvement`/`human_gate` trong `evaluation/`.
**Test:** `tests/test_evaluation_pkg.py` (8, trace nhỏ tự dựng): khớp hàm BTC (kèm baseline), liệt kê từng loại ca sai, thiếu trace, luật đọc vẹt (ngưỡng 2/3, SKU tính qua `facts_used`), file 20 lượt tất định + đọc lại được, ưu tiên lượt sai, CLI đầu-cuối, độc lập runtime. Toàn bộ `unittest discover` = 832 test OK .
**Chưa làm / giới hạn:** (1) file 20 lượt chưa có người điền (cần chấm tay để lấy tỷ lệ đồng thuận với judge ở 14b); (2) luật đọc vẹt so giá trị số theo số nguyên nên "15" trong "hôm 15/10" có thể tính nhầm một fact (đã ghi `shortcut:` trong mã); (3) chưa chạy trên trace bộ 135 cuộc (dataset) — chỉ kiểm trên runs/buoc15_I; (4) không có judge (14b).

### 11.82. Bước 11 — chọn policy 2 tầng: router LLM → TF-IDF (2026-10-28, KHÔNG gọi LLM thật)
**Làm gì:** `src/memory/policy_router.py` (mới). Mục lục = các file chính sách **public** (nội bộ không bao giờ vào prompt): tên, phiên bản, hiệu lực từ→đến, các mục `mã + tiêu đề` (dựng tự động từ chunk đã nạp, không viết tay). Router = `LLMClient` cùng model agent (`POLICY_ROUTER_MODEL` nếu muốn model riêng), `temperature=0`, `complete_json`, trả `{files[], as_of_date, as_of_evidence, answerable}`. `SemanticKBStore.search` (chữ ký `MemoryService.query_policy` giữ nguyên, orchestrator không đổi): router chọn file → lọc theo **ngày mua** (`as_of_date`, không có thì ngày cuộc gọi như cũ) → TF-IDF chỉ xếp hạng trong file đã chọn. `answerable=false` → trả duy nhất `[PB-05]` ("chưa có thông tin…", kèm `answerable: false`). Thêm tham số `top_k=3` cho `search` (script đo cần top-5).
**Kiểm chứng bằng code (không tin LLM):** tên file không có trong mục lục bị bỏ (ghi `last_route.dropped_files`; bỏ hết → không giới hạn file); `as_of_date` chỉ nhận khi là ngày ISO hợp lệ **và** `as_of_evidence` là đoạn có thật trong câu hỏi (không thì dùng ngày cuộc gọi, ghi `date_dropped`); `answerable`/`files` sai kiểu → coi router hỏng. Router lỗi (mạng, JSON hỏng, thiếu API key, `POLICY_ROUTER=off`) → `route()` trả `None` → TF-IDF toàn bộ y như trước. Nếu file đã chọn mà TF-IDF không ra kết quả → thử lại toàn bộ (`last_route.fallback_all`). `BudgetExceeded` không bị nuốt.
**Test:** `tests/test_policy_router.py` 13 test, toàn bằng LLM GIẢ: đúng đường router (chỉ file đã chọn; mục lục không có tài liệu nội bộ); tên bịa bị bỏ; `answerable=false` → PB-05; 5 kiểu router hỏng/không LLM/`POLICY_ROUTER=off` → kết quả y hệt TF-IDF toàn bộ; ngày mua chọn bản chính sách cũ (không ngày → bản cũ không bao giờ trả); ngày thiếu trích dẫn/sai định dạng bị bỏ; script đo chạy được với router giả. Toàn bộ **845 test** xanh (832 cũ + 13 mới) — chạy với `OPENAI_API_KEY` giả + `OPENAI_BASE_URL` trỏ cổng chết nên không thể gọi LLM thật; xem `runs/_unittest_step11b.txt`.
**Script đo (CHƯA CHẠY):** `scripts/eval_policy_router.py` — 60 câu `qa_labeled.json`, chấm bằng `rag_eval` của BTC. Không cờ → chỉ TF-IDF offline; `--llm [--cap-vnd 700]` mới gọi router thật (trần cứng). Xuất Recall@3/@5, multi-hop full recall, tỉ lệ từ chối (unanswerable/restricted) và từ chối nhầm, độ phủ file (file router chọn có chứa đủ chunk nhãn), số tên bịa/ngày bị bỏ, độ trễ và chi phí trung bình/câu. Hai biến thể: `router` (truy hồi, bỏ qua abstain, so được với 81,4% của TF-IDF) và `router_served` (đúng thứ hệ thống trả: câu abstain chỉ còn `[PB-05]`, nên Recall của câu unanswerable/restricted giảm theo).
**Ước tính chi phí để duyệt trần:** prompt ≈ 5.100 ký tự (mục lục 12 file/90 mục ≈ 3.600 + hướng dẫn ≈ 1.500) ≈ 2.000 token vào + ~80 token ra ≈ **9 VND/lần gọi gpt-4o-mini** (chưa tính prompt cache) → 60 câu ≈ **540 VND**; trần mặc định của script 700 VND. Chạy thật mỗi câu chính sách thêm ~9 VND và 1 lần gọi LLM tuần tự trước TF-IDF (độ trễ chưa đo — số đo sẽ do `--llm` ghi).
**Chưa làm / rủi ro:** (1) chưa đo bằng LLM thật nên chưa biết Recall@5 có ≥ 81,4%, tỉ lệ từ chối và từ chối nhầm; prompt chọn `answerable=false` thận trọng (mặc định true) nhưng chưa kiểm. (2) Chi phí/độ trễ của router **chưa vào trace và chưa tính vào trần chi phí của orchestrator** (router có `LLMClient` riêng; `PolicyRouter.drain_usage()` đã sẵn để phiên bước 13 gộp vào `cost` của lượt). (3) Mục lục có 12 file public (không phải 11 như PLAN: 14 file − 2 nội bộ), tính cả bản cũ hết hiệu lực. (4) Khi chạy qua MCP/`RemoteMemoryService` router chạy phía server memory (cần `OPENAI_API_KEY` trong môi trường server). (5) `query` mà LLM chính gửi vào `search_policy` có thể đã viết lại và làm mất ngày mua khách nói; router chỉ thấy câu tra cứu đó.

### 11.83. Bước 17 — Backend API FastAPI `api/` (2026-10-28, KHÔNG gọi LLM)
**Chạy:** `uvicorn api.app:app --host 127.0.0.1 --port 8000` (từ `Code/`, MỘT worker; tài liệu tương tác ở `/docs`). Pipeline thật dựng lúc khởi động (kèm bộ quét nền `IDLE_TIMEOUT_S`) và đóng lúc tắt. Đã thử chạy thật bằng uvicorn + MCP stdio (không LLM): `/health`, hai lượt `/chat`, 4 GET, `/asr`, `/sessions/{id}/end` đều trả đúng.
**Thêm:** `api/{app,routes,schemas,sessions,scrub}.py`; `pipeline.py` thêm 3 thành phần chỉ-đọc, không đổi hành vi cũ (`lock`, `preview_brief`, `timeline`); `requirements.txt` + fastapi 0.162.0 (uvicorn/httpx/python-multipart đã có trong nlp_env — chỉ `pip install fastapi==0.162.0`).
**Endpoint:** `POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/end`, `POST /chat` (có `session_id` → tiếp phiên; không có → mở phiên mới), `GET /call-brief`, `/memory/timeline`, `/tools/log?limit=`, `/orders` (đều `?session_id=`), `POST /asr` (multipart .wav/.mp3), `GET /health`.
**Sửa lỗi UI cũ:** API tự cấp `call_name` (`call_{max(số cuộc trong bộ nhớ, số phiên đã mở trong tiến trình)+1}`) và `turn_num` (+1 mỗi lượt khách xử lý xong; lượt lỗi không làm tăng). UI cũ gửi `call_1` cố định và `turn_num = len(chat_messages)` (đếm cả tin của agent). Mở phiên mới cho liên hệ còn phiên mở → chốt phiên cũ (`end_call`), phiên cũ trả 409 — nếu không, hai phiên cùng liên hệ sẽ chốt lẫn nhau vì pipeline chỉ giữ MỘT cuộc mở cho mỗi liên hệ.
**Song song và ĐÁNH ĐỔI (quan trọng):** `MemoryService.begin_turn` dùng ngữ cảnh lượt dùng chung (§ 11.27/11.33) nên API GIỮ khóa của pipeline quanh mỗi lượt (`pipeline.lock`, cũng dùng để cắt đúng đoạn `audit_log` của cổng MCP cho từng phiên). Hệ quả: hai phiên "đồng thời" được xen kẽ THEO LƯỢT, không chạy song song thật — lượt dài (LLM ~vài giây) làm phiên kia chờ; thông lượng = 1 lượt tại một thời điểm. Muốn song song thật phải viết lại ngữ cảnh lượt theo phiên trong `MemoryService`/mcp-memory (ngoài phạm vi, không đụng orchestrator). Handler là hàm đồng bộ chạy trong threadpool của FastAPI nên không chặn vòng lặp sự kiện.
**PII:** trace trả về là bản rút gọn (`slim_trace`): số câu hỏi/claim, tên tool + cờ lỗi, khóa+op của bộ nhớ đã ghi, độ trễ, chi phí LLM — KHÔNG có lời khách/agent, args/kết quả tool, giá trị bộ nhớ. Mọi JSON trả ra (brief, timeline, tool log, orders) qua `scrub`: che theo tên khóa (phone/sdt/address/email/cccd/stk…), fact hồ sơ có `key` nhạy cảm, và mọi dãy 9–14 chữ số. Tên khách KHÔNG che (UI cần hiển thị). `answer` là lời nói với khách nên giữ nguyên. Lỗi pipeline → 500 chỉ có tên lớp lỗi (chi tiết ở log máy chủ).
**ASR:** dùng `offline_asr.is_available()/transcribe_audio()`; không khả dụng → 503 kèm hướng dẫn; đặt `HF_HUB_OFFLINE=1` (setdefault) để đường dự phòng faster-whisper KHÔNG tự tải model từ Hugging Face; đuôi khác .wav/.mp3 → 415, > 25 MB → 413, transcript rỗng → 422.
**Test:** `tests/test_api.py` 17 test (pipeline thật, không LLM): bộ đếm call_name/turn_num, phiên mới chốt phiên cũ (409), ẩn danh, 404/422, lượt lỗi → 500 không lộ SĐT và không tăng lượt, end idempotent; **hai phiên (hai luồng, rào chắn khởi động đồng thời) không lẫn tên/xưng hô/fact/nhật ký tool** (`call_id` không trùng, `source_call` đúng); không lộ SĐT/địa chỉ ở bất kỳ endpoint nào; `/orders` chỉ có đơn của phiên mình; `/asr` (thiếu model, thành công + xóa file tạm, 415/422/413); vòng đời app (tự đóng pipeline của mình, không đóng pipeline được truyền vào).
**Hạn chế / chưa làm:** (1) kho phiên nằm trong RAM, không giới hạn số phiên hay độ dài nhật ký tool, mất khi khởi động lại (bộ nhớ khách vẫn trong DB) — chỉ chạy MỘT worker; (2) chưa có xác thực/CORS (UI bước 18 chạy khác origin sẽ cần thêm CORS); (3) `/orders` không có LLM nên test dựng đơn bằng cách gọi `order.create` trong lượt — chưa thấy đơn do LLM thật tạo qua API; (4) gọi view bộ nhớ dưới tên caller `Operator` (đã có quyền `memory.timeline`, cũng có quyền xóa khách nhưng API không gọi) vì không sửa `config/mcp_permissions.json`; (5) `GET /call-brief` dựng lại brief mỗi lần như tab UI (thêm vài lời gọi CRM/catalog vào nhật ký cổng, không vào nhật ký của phiên); (6) UI Streamlit `ui_app.py` CHƯA chuyển sang gọi API (thuộc bước 18, không sửa ở đây).

**Đo bằng LLM thật (§ 11.82, `runs/policy_router_eval/`, gpt-4o-mini, 60 câu, 60 lần gọi, 465 VND — trần duyệt 700):**
| | TF-IDF toàn bộ | router (truy hồi) | router_served |
|---|---:|---:|---:|
| Recall@3 / @5 | 76,3 / 81,4 | 72,9 / **74,6** | 71,2 / 72,9 |
| Multi-hop full recall @3 / @5 | 16,7 / 25,0 | 0 / 16,7 | 0 / 16,7 |
| Recall@5: single / multi_hop / version_conflict / numeric | 88 / 83,3 / 100 / 75 | 84 / 83,3 / 83,3 / 50 | 80 / 83,3 / 83,3 / 50 |
| Từ chối: unanswerable / restricted | 0 / 0 | 0 / 60 | 0 / 60 |
| Từ chối nhầm | 0 | 2,1 (1 câu: Q08 "trả góp") | 2,1 |
Router: 0 lần lỗi, 0 tên file bịa, 0 ngày bị bỏ; độ phủ file 40/59 (router chọn thiếu file chứa chunk nhãn ở 19 câu); trung bình 2,18 file/câu; **độ trễ 1.034 ms, 7,76 VND mỗi lần gọi**.
**Kết luận: KHÔNG đạt tiêu chí "Recall@5 ≥ 81,4%"** khi TF-IDF chỉ tìm trong file router chọn (74,6%). Lý do chính là chọn sai file: mục lục chỉ có tên mục nên router chọn `faq.md`/`playbook-telesale.md` cho câu về xe đẩy, máy hút sữa, xóa dữ liệu, lịch nghỉ, COD (đáng lẽ `spec-thoi-trang-me-be.md`, `quy-trinh-cod-hoan-hang.md`, `thong-bao-lich-nghi.md`…). Đạt: ngày mua Q43 đúng (2026-09-28, bản cũ được chọn), Q42 đúng; restricted 3/5 từ chối đúng (NB-01, NB-03); không bịa tên file. Chưa đạt: unanswerable 0/8 từ chối (router luôn thấy file "gần đúng" nên trả true — cố ý thận trọng); Q55 router lấy "11/11" làm ngày mua (sai, vô hại ở câu này); Q24 lấy 2026-10-01 từ "tháng 10" không phải ngày đặt; SAMPLE-07 chưa kiểm.
**Mô phỏng OFFLINE (không LLM, dùng lại quyết định router đã lưu, cùng 60 câu nên có rủi ro quá khớp):** giữ k kết quả đầu từ file router chọn rồi bù phần còn lại từ toàn bộ tài liệu (đã lọc ngày): k=1 → Recall@3/@5 76,3/81,4; **k=2 → 81,4/88,1** (multi-hop full@5 25,0); k=3 → 72,9/89,8. Chưa cài vì lệch yêu cầu "TF-IDF chỉ tìm trong file đã chọn" — chờ quyết định của chủ dự án.

**Cài phương án LAI (theo quyết định của chủ dự án, 2026-10-28, KHÔNG gọi LLM):** `ROUTED_TOP_K = 2` (hằng số có tên trong `policy_router.py`). `SemanticKBStore.search`: khi router chọn file → lấy `ROUTED_TOP_K` kết quả đầu từ file đã chọn, phần còn lại đến `top_k` bù từ TOÀN BỘ tài liệu đã lọc theo ngày (ngày mua nếu có), bỏ trùng chunk. Không giới hạn file (router không chọn / lỗi) → như cũ. Giữ nguyên: kiểm chứng tên file/ngày bằng code, `answerable=false` → chỉ `[PB-05]`, router lỗi → TF-IDF toàn bộ, chữ ký `query_policy`. Bản chính sách cũ vẫn bị lọc theo ngày ở cả phần bù.
**Test:** `tests/test_policy_router.py` 15 test (+2: đúng 2 chunk đầu từ file chọn rồi bù từ toàn bộ, không trùng, `top_k` nhỏ không vượt; phần bù vẫn lọc bản cũ theo ngày, đơn cũ chỉ ra bản có hiệu lực ngày mua; test cũ chỉnh theo lai và smoke test script đo có `offline_variants`). Toàn bộ **864 test** xanh (`runs/_unittest_step11c.txt`, khóa giả + cổng chết).
**Kết quả hybrid tính OFFLINE** (`python scripts/eval_policy_router.py --offline-hybrid`, dùng lại quyết định router của lần đo thật, không gọi LLM; ghi `runs/policy_router_eval/offline_*_results.json`; lệnh này ghi đè `report.json` — bảng đo thật ở trên là bản lưu):
| | Recall@3 | Recall@5 | Multi-hop full @3 / @5 |
|---|---:|---:|---:|
| TF-IDF toàn bộ | 76,3 | 81,4 | 16,7 / 25,0 |
| router strict (đã đo thật) | 72,9 | 74,6 | 0 / 16,7 |
| hybrid k=1 | 76,3 | 81,4 | 16,7 / 33,3 |
| **hybrid k=2 (đang cài)** | **81,4** | **88,1** | 8,3 / 25,0 |
| hybrid k=3 | 72,9 | 89,8 | 0 / 25,0 |
Hybrid k=2 theo loại @5: single 92 · multi_hop 100 · version_conflict 100 · numeric 75; từ chối không đổi (unanswerable 0%, restricted 60%).
**Lưu ý:** (1) QUÁ KHỚP — k=2 chọn trên chính 60 câu đo nên số lạc quan; (2) chưa đo lại bằng LLM thật với mã đã cài; (3) multi-hop full recall @3 giảm (16,7 → 8,3) và @5 chỉ bằng TF-IDF (25,0) — tiêu chí "multi-hop full recall tăng" CHƯA đạt; (4) tỉ lệ từ chối unanswerable vẫn 0%.

### 11.84. Tách 3 việc độc lập sang 3 session + gộp kết quả (2026-10-28)
Bước 11, 14a, 17 chạy ở 3 session riêng, mỗi cái chỉ sửa file của mình (cấm `orchestrator.py`, `call_brief.py`; `pipeline.py` chỉ session 17). **Không có worktree riêng** vì `D:\Sudo_Code\Harness_Agent` không phải git repo → cả ba chia sẻ một thư mục với phiên chính (tách theo file, không theo nhánh; không có nhánh để gộp). Ghi nhận ở § 11.81 (14a), § 11.82 (11 + đo LLM thật 465 VND do chủ dự án duyệt trần 700 ở chính session đó + phương án lai), § 11.83 (17).
**Kiểm tra sau khi gộp (chạy ở thư mục chung):** `unittest discover` = **864 test OK** (`runs/_unittest_full37.txt`; các session báo lần lượt 832 (14a), 845→864 (11), 862 (17) — số đếm cộng dồn vì cùng chạy trên một thư mục). Phiên chính không bị đổi `orchestrator.py`/`call_brief.py`.
**Bài học:** muốn worktree thật cần `git init` (chưa làm: thư mục có `.env`/DB/audio, cần `.gitignore` trước). Tổng hợp tiến độ đã cập nhật ở § 12 (xem 12.1, 12.2, 12.4).

**Đo LẠI bằng LLM thật với mã LAI (§ 11.82, `runs/policy_router_eval/`, `runs/policy_router_eval_stdout2.txt`, gpt-4o-mini, 60 câu, 60 lần gọi, 465 VND — trần duyệt 700, 2026-10-28):**
| | TF-IDF toàn bộ | hybrid k=2 (truy hồi) | hybrid k=2 (router_served) |
|---|---:|---:|---:|
| Recall@3 / @5 | 76,3 / 81,4 | **81,4 / 88,1** | 79,7 / 86,4 |
| Multi-hop full recall @3 / @5 | 16,7 / 25,0 | 8,3 / 25,0 | 8,3 / 25,0 |
| Recall@5: single / multi_hop / version_conflict / numeric | 88 / 83,3 / 100 / 75 | 92 / 100 / 100 / 75 | 88 / 100 / 100 / 75 |
| Từ chối: unanswerable / restricted | 0 / 0 | 0 / 60 | 0 / 60 |
| Từ chối nhầm | 0 | 2,1 (Q08) | 2,1 |
Router: 0 lỗi, 0 tên file bịa, 0 ngày bị bỏ, độ phủ file 40/59, trung bình 2,2 file/câu; **độ trễ 1.087 ms, 7,76 VND/lần gọi**. Quyết định router (temperature 0) giống lần đo trước nên số đo thật **khớp** mô phỏng offline (81,4/88,1).
**Kết luận:** Recall@5 88,1% ≥ 81,4% (ĐẠT, +6,7 điểm); Recall@3 81,4% (+5,1). Chưa đạt: multi-hop full recall không tăng (@3 giảm 16,7 → 8,3, @5 bằng 25,0), từ chối câu unanswerable vẫn 0/8 (restricted 3/5), SAMPLE-07 chưa kiểm. Lưu ý k=2 chọn trên chính 60 câu này nên chưa có số trên bộ độc lập. `router_served` thấp hơn truy hồi 1,7 điểm vì câu bị từ chối nhầm (Q08) chỉ còn `[PB-05]`.

### 11.85. Bước 13 — chủ động đưa thông tin: tra sẵn giá/tồn kho/KM/bảo hành lúc nhận diện khách (2026-10-28, chưa gọi LLM thật)
**Yêu cầu (docs/PLAN.md bước 13):** kiểm tra giá/tồn kho/KM bằng tool lúc nhận diện khách → vào Call Brief, tính vào `call_brief_latency_ms`; gom giá cuối + KM + tồn kho + bảo hành vào MỘT câu; nhắc tối đa 2 thông tin cũ (PB-01); LLM không tra lại những gì đã kiểm tra; đọc lại đơn một lần trước `order.create` (PB-09).
**Cài đặt:**
- `CallBriefBuilder.precompute` ([src/harness/call_brief.py](src/harness/call_brief.py)): khách QUAY LẠI có sản phẩm đã tư vấn → CODE gọi `catalog.search` (tên, bảo hành), `inventory.check`, `pricing.get_quote` (kèm SĐT người gọi) cho đúng biến thể đã tư vấn (`variant_sku`) hoặc SKU cha tại ngày cuộc gọi; **một lần cho mỗi (khách, ngày)** (bộ nhớ đệm trong builder, các lượt sau không tra lại); lỗi tool → không có tra sẵn, brief vẫn dựng bình thường (`_product_name` cũng bắt lỗi cổng). Kết quả vào `CallBrief.precomputed` (`stock`, `price` gồm giá niêm yết/giá cuối/ưu đãi đã áp dụng/freeship, `warranty_months`, `calls` dạng trace với SĐT thay bằng token `CURRENT_CUSTOMER`, `latency_ms`). Thời gian tra nằm trong `build()` nên vào `call_brief_latency_ms` của lượt 1 cuộc gọi thứ 2+. Không dùng tool ghi.
- Quyền: `config/mcp_permissions.json` (v4) cho caller `CallBriefBuilder` thêm `inventory.check` và `pricing.get_quote` (chỉ đọc).
- Câu chào (`suggested_opening`): sản phẩm + MỘT câu "Em vừa kiểm tra hôm nay: còn hàng, giá X (ưu đãi…), bảo hành N tháng." (hết hàng thì nói hết hàng + ngày có lại). Nhắc cũ tối đa 2 thông tin (sản phẩm + giá; diện tích bỏ khỏi câu chào, vẫn ở bộ nhớ); không có tool thì giữ khuôn cũ nhưng cũng ≤ 2.
- Orchestrator ([src/harness/orchestrator.py](src/harness/orchestrator.py)): lượt đầu của cuộc ghi 3 lời gọi tra sẵn vào `tool_calls` của trace và nhật ký cuộc gọi (bằng chứng cho guardrail các lượt sau); `_precomputed_hit`: lời gọi `inventory.check`/`pricing.get_quote` của LLM trùng đúng yêu cầu (cùng SKU/ngày, qty 1, không địa chỉ/giỏ khác, SĐT là của người gọi) được trả từ kết quả tra sẵn, không gọi tool lần hai và không vào trace; đổi qty/địa chỉ/giỏ/SKU/ngày hoặc `order.create`/`order.update` thành công → hết hiệu lực/gọi tool thật. Ngữ cảnh LLM có dòng "Hệ thống ĐÃ kiểm tra THẬT đầu cuộc gọi hôm nay…" (không gọi lại, gom một câu, ≤ 2 thông tin cũ); system prompt sửa câu "PHẢI gọi lại tool" thành "trừ phần đã kiểm tra". Trace có `precomputed: {sku, latency_ms, served}` (pipeline đưa vào `extra`).
- Đã có sẵn từ trước, nay chỉ ghi nhận: PB-09 đọc lại đơn một lần trước `order.create` = bước `readback` của order gate (§ 11.30).
**Test:** `tests/test_step13.py` 11 test (tra một lần/cuộc, không SĐT thật trong trace, chỉ khách quay lại, câu chào một câu ≤ 2 thông tin cũ, hết hàng, lỗi tool, luật `_precomputed_hit`, orchestrator phục vụ lời gọi lặp và vẫn gọi tool thật khi đổi qty, dòng ngữ cảnh) + sửa `test_cluster_9_10.OpeningSentenceTest` theo khuôn mới. Toàn bộ **875 test OK** (`runs/_unittest_step13b.txt`).
**Chưa làm / rủi ro:**
1. **Chưa đo bằng LLM thật** — các tiêu chí của bước 13 (số lượt/cuộc, số cuộc đến chốt, tool/lượt, `llm_calls`/lượt đều giảm; TSR, HR không tụt) cần chạy `ui_replay` E (và A–J) / `run_eval` với trần được duyệt; lượt 1 cuộc 2+ nay có 3 tool của code nên tool/lượt tăng ở lượt đó, giảm ở các lượt sau nếu LLM không tra lại.
2. **Ngày giao dự kiến chưa tra sẵn:** `_eta` của mock chỉ chạy trong `order.create` và cần địa chỉ; không có tool riêng, không sao chép lại luật ngày nghỉ để khỏi lệch với tool thật → ngày giao vẫn lấy từ kết quả `order.create`.
3. Chỉ tra cho khách quay lại có sản phẩm; khách mới/giữa cuộc đổi sản phẩm thì LLM tra như cũ (kết quả tra sẵn chỉ khớp theo SKU).
4. Chi phí/độ trễ router bước 11 **chưa nối vào trace/trần chi phí**: router chạy phía server memory (MCP) nên cần đưa usage ra qua kết quả `search_policy` — việc riêng.
5. Câu chào dài hơn (thêm một câu) → TTFT lượt 1 cuộc 2+ có thể tăng nhẹ; cần đo.

**Đo LLM thật bước 13 (`runs/ui_replay_25.txt`, ui_replay E, 86,3 VND, trần 120; so với cuộc 2 của E trong `ui_replay_18` — số liệu lấy từ trace tạm của hai lần chạy):**
- **Câu chào cuộc 2 có dữ kiện tra sẵn:** có — "…hôm 15/10 bên em có tư vấn Máy lọc không khí AirPure X. Em vừa kiểm tra hôm nay: còn hàng, giá 4.890.000đ (tặng quà kèm, miễn phí vận chuyển), bảo hành 24 tháng. Chị đã trao đổi lại với gia đình chưa ạ…" — 2 thông tin cũ (sản phẩm, giá), không còn diện tích, không lộ mã SKU/mã KM.
- **LLM có gọi lại giá/tồn kho không:** không. `precomputed.served = []` và lượt 1 cuộc 2 trong trace chỉ có 3 lời gọi của CODE (`catalog.search`, `inventory.check`, `pricing.get_quote`); ui_replay_18 là 1 lời gọi `pricing.get_quote` do LLM.
- **Số tool/lượt (E):** 1 · 1 · **3** (ui_replay_18: 1 · 1 · 1). Lượt 1 cuộc 2: tool do LLM 1 → 0, nhưng tổng 1 → 3 vì code tra sẵn (đúng như dự báo ở rủi ro 1).
- **Chi phí LLM của lượt 1 cuộc 2:** 17,82 VND (2 lần gọi LLM, 7.076 token vào) so với 25,52 VND (3 lần, 9.921 token) — **−30%**; cả hội thoại E 86,3 VND (gồm bộ đọc ≈ 17,6) vs 84,7 ở ui_replay_15 (E một mình, trước bước 13) — gần như không đổi vì lượt 1–2 của cuộc 1 không thuộc phạm vi bước 13.
- **Độ trễ lượt 1 cuộc 2:** TTFT 6.111 ms / tổng 7.524 ms (ui_replay_18: 5.578 / 6.570) — **không cải thiện**, nằm trong dao động của các lần E trước (tổng 3,2–9,0 s); tra sẵn tốn 66 ms (`call_brief_latency_ms`), phần còn lại là sinh câu của LLM + bộ đọc (≈ 1,9 s). Bước 13 chưa giảm TTFT như PLAN kỳ vọng.
- **Giới hạn:** MỘT mẫu mỗi bên (LLM dao động); chưa đo số lượt/cuộc và số cuộc đến chốt (cần chạy bộ kịch bản/`run_eval`), chưa chạy lại A–J.
- Cùng ngày, session bước 11 tự đo lại hybrid bằng LLM thật (60 câu, 465,44 VND, trần 700 do chủ dự án duyệt ở session đó): Recall@3/@5 = 81,4/88,1 (đạt ngưỡng 81,4), multi-hop full @3/@5 = 8,3/25,0 — chi tiết ở § 11.82.

### 11.86. Bước 15 GĐ2 — chuẩn bị chạy (2026-10-28, chưa gọi LLM thật; chờ duyệt trần chi phí)
**Bộ kịch bản (22, đúng yêu cầu PLAN):** 7 mẫu BTC `public_sample` (13 cuộc, 39 lượt khách; lời khách cố định → KHÔNG dùng `--gate-assist`) + 15 kịch bản sinh `generated_m1` (18 cuộc, 36 lượt khách; tương tác → `--gate-assist`, 16 lượt chèn mô phỏng khách trả lời gate). `run_eval.py` từ chối `--gate-assist` với SAMPLE-* nên mỗi seed là HAI lần chạy; bản sao thư mục ở `runs/gd2/scen_{sample,gen,all}`. Mỗi cấu hình/seed = **91 lượt** → 91 × 2 cấu hình × 3 seed = 546 lượt (≥ 100 ✓; p95 có ý nghĩa).
**Chạy thử KHÔNG LLM trên kiến trúc MCP (stdio cho cả tool và bộ nhớ, `OPENAI_API_KEY` rỗng → nhánh rule-based):** `runs/gd2_dry_sample.txt`, `runs/gd2_dry_gen.txt` — hai bộ chạy trọn 2 cấu hình, trace đủ (39 + 52 lượt), `reference_eval` chấm được, báo cáo gate hai loại in đúng; lần này là lần đầu `run_eval` chạy thật qua MCP (mục "chưa làm" ở § 12.2). Số TSR/HR của lần chạy thử vô nghĩa (không LLM).
**Công cụ mới:** `scripts/gd2_report.py` — gộp trace `sample/` + `gen/` thành 22 kịch bản cho từng seed, chấm bằng `reference_eval` (qua `evaluation.scoring`), mean ± std qua seed, TSR tách (mẫu BTC / sinh tương tác), đối chiếu ngưỡng BTC (RQR giảm ≥ 40%, TSR ≥ 70%, HR giá/KM ≤ 5%, hơn baseline, TTFT p95 ≤ 3 s) → `gd2_report.{json,md}`; `tests/test_gd2_report.py` (3 test). Đã chạy thử trên trace không LLM.
**Ước tính chi phí LLM thật (dựa chi phí/lượt đo ở § 11.31 và các lần `ui_replay` ≈ 20–28 VND/lượt, lượt chèn do code ≈ 8 VND):** mẫu BTC ≈ 78 lượt-chạy/seed × 25 ≈ 1.950; sinh ≈ (72 lượt khách + 32 lượt chèn…) ≈ 2.100 → **≈ 4.100 VND/seed, ≈ 12.300 VND cho 3 seed** (khoảng 10.000–15.000). Thời gian ≈ 1 giờ (≈ 7–8 s/lượt).
**Lệnh dự kiến (sau khi chủ dự án duyệt trần):**
`python run_eval.py --scenarios runs/gd2/scen_sample --config both --out-dir runs/gd2_run/sample --seed 42 --repeats 3 --max-cost-vnd <trần 1>`
`python run_eval.py --scenarios runs/gd2/scen_gen --config both --out-dir runs/gd2_run/gen --seed 42 --repeats 3 --gate-assist --max-cost-vnd <trần 2>`
`python scripts/gd2_report.py --root runs/gd2_run`

### 11.87. Bước 15 GĐ2 — KẾT QUẢ chạy LLM thật (2026-10-28; trần 7.000 + 7.500 do chủ dự án duyệt)
**Chạy:** 22 kịch bản (7 mẫu BTC không `--gate-assist` + 15 sinh có `--gate-assist`), 3 seed, 2 cấu hình, `runs/gd2_run/` (`gd2_report.md/json`). Không chạm trần, không BudgetExceeded. **Chi phí thật: mẫu BTC 4.988,6 + sinh 5.727,9 = 10.716,5 VND** (ước tính 12.300). 89 lượt/seed (cấu hình full).
| Chỉ số | full (mean ± std) | baseline | Ngưỡng |
|---|---:|---:|---|
| TSR | 50,0 ± 4,5 | 53,0 ± 6,9 | ≥ 70 và hơn baseline → **CHƯA ĐẠT** |
| RQR | 0,0 | 7,8 | giảm ≥ 40% → ĐẠT (100%) |
| CCR | 53,6 | 3,6 | — |
| HR giá/KM | 31,1 ± 7,2 | 42,1 ± 5,1 | ≤ 5 → **CHƯA ĐẠT** (hơn baseline) |
| TTFT p95 | 12.935 ± 6.315 ms | — | ≤ 3.000 → **CHƯA ĐẠT** (total p95 14.635 ms) |
Guardrail: 0 vi phạm. Lượt/cuộc 2,89; cuộc tới chốt 1,13.
**Tách theo loại:** mẫu BTC cố định TSR 14,3% cả 3 seed (full = baseline, bị order gate chặn theo thiết kế § 11.31; HR giá/KM 0/0/25%); sinh tương tác TSR 60,0/73,3/66,7 (full) vs 60,0/73,3/80,0 (baseline) — full KHÔNG hơn baseline; HR giá/KM sinh 40,0/43,8/46,7 (baseline 30,0/11,1/40,0) — ở bộ sinh full thậm chí cao hơn baseline.
**Trượt lặp lại ở bộ sinh (seed 3):** SC-GEN-03 (tạo đơn không khớp args), SC-GEN-04 (thiếu bước xác nhận/hỏi tên), SC-GEN-08 (không nói "không có thông tin"), cộng SC-GEN-07 (bảo hành 30 ngày) và SC-GEN-15 (tạo đơn) ở full.
**Kết luận:** RQR đạt; TSR, HR giá/KM, TTFT chưa đạt, và full chưa vượt baseline trên TSR. Cần xem từng ca trượt/HR trước khi sửa (chưa phân tích nguyên nhân); mẫu BTC cố định không đo được TSR thật. 89 lượt nên p95 vẫn dưới 100 lượt/bộ riêng; mỗi seed một mẫu, std lớn (HR ±7).

### 11.88. Phân tích trace GĐ2 (2026-10-28, không gọi LLM; chi tiết lệnh: `runs/gd2_run/failures_gen.txt`)
**Ca trượt TSR bộ sinh (full; seed 1/2/3):** GEN-03 (3/3) · GEN-04 (3/3) · GEN-07 (3/3) · GEN-08 (3/3) · GEN-15 (seed 1, 3) · GEN-13 (seed 1). Baseline trượt cùng GEN-03/04/07(2/3)/08, thêm GEN-05, GEN-11 mỗi một lần.
1. **GEN-03 — lỗi của code:** `order.create` được tạo đúng nhưng args KHÔNG có `price_vnd` (BTC `tools.schema.json` đặt `price_vnd` là input; kịch bản đối chiếu `sku`+`price_vnd`). Gate chỉ gán `exec_args["price_vnd"]` ở nhánh lệch giá (`orchestrator.py` ~815). Cũng thiếu ở GEN-02/05/12 và làm `total_match_vnd` (tổng = price_vnd×qty, mặc định 0) sai. Sửa: nếu thiếu thì gán `int(unit)` từ báo giá. Còn thiếu: tool trả `needs_confirmation_call=true` nhưng lời báo "đã lên đơn" không nói sẽ có người gọi xác nhận.
2. **GEN-04 — thiếu chốt cấu trúc:** brief đúng (`blocker=ambiguous_identity`, câu mở xin xác nhận tên) nhưng chỉ nằm trong `suggested_opening`; khách mở đầu bằng câu hỏi giá nên LLM trả lời luôn, không hỏi tên (cả 3 seed). Sửa: như `_ensure_prior_contact_question`, nếu `brief.blocker == ambiguous_identity` mà trả lời chưa có câu xác nhận tên thì nối câu đó (giá/tính năng công khai vẫn trả lời, không nạp dữ liệu cá nhân).
3. **GEN-07 — truy hồi sai tài liệu (chỉ ở full):** LLM tìm "bảo hành máy lọc AirPure X" → chỉ BH-01/BH-03, không bao giờ ra DT-05 (đổi mới 1-1 trong 30 ngày với lỗi nhà sản xuất); baseline tìm "bảo hành và đổi trả" nên ra DT-05. Sửa: luật prompt khi khách báo sản phẩm lỗi → tìm cả bảo hành và đổi trả/lỗi nhà sản xuất; có thể bổ sung truy hồi chéo ở router.
4. **GEN-08 — lệch từ ngữ:** chuyển máy đúng (không tư vấn y tế) nhưng chấm cần cụm "không có thông tin/em chưa rõ/em không chắc". Sửa: câu chuyển máy ca ngoài phạm vi nói thật "phần này em chưa có thông tin chuyên môn nên chuyển nhân viên…".
5. **GEN-15 (seed 1, 3):** khách "lên đơn", LLM tự hỏi tên/PTTT (còn hỏi lại cả tên đã biết) mà KHÔNG gọi `order.create` → gate không vào → khách mô phỏng không chèn → hết cuộc, không có đơn. Seed 2 gọi tool nên đạt. Sửa: khi khách yêu cầu lên đơn mà lượt đó không có `order.create`, code vào gate với đơn nháp từ dữ kiện đã biết (hoặc luật prompt "gọi order.create, gate sẽ hỏi phần thiếu").
6. **GEN-13 seed 1:** khách xin AirPure Pro, LLM báo/đặt AirPure Y (không tìm sản phẩm; seed 2, 3 đúng Pro).
**HR giá/KM (full 25,0/29,2/39,1%):** phần lớn KHÔNG phải LLM bịa:
- A. **Claim đa sản phẩm do bộ trích tạo (`extractor.py` `extract_claims`):** GEN-11 liệt kê 6 mẫu với giá catalog đúng, bộ trích gán tất cả là `price_vnd` rồi so với sự thật 6.490.000 → 5–6 claim sai mỗi seed (≈ cả HR giá/KM seed 1–2). Baseline cũng dính khi liệt kê.
- B. **Sự thật kịch bản lệch tool:** GEN-01 call_2 (sự thật 1.690.000, tool trả 1.521.000 vì RUN-10 hiệu lực 12–25/10), GEN-05 (sự thật 50.000, tool `extra_payment_vnd` 40.000 vì RUN2-SALE), GEN-02 (sự thật tổng 15.980.000 = niêm yết×2, tool 15.380.000) — đủ cả 3 seed, cả 2 cấu hình. Cần hỏi BTC/mentor, không sửa agent theo.
- C. **Lỗi thật:** GEN-02 mất `qty=2` (báo "giá cuối cho 2 máy là 7.690.000" là giá 1 máy; lượt sau LLM gọi `get_quote qty=1`, tạo đơn qty 1 → né hạn mức COD 10 triệu; baseline giữ qty 2 và bị chặn đúng); GEN-13 seed 3 báo 7.690.000 vì lần `get_quote` sau bỏ `customer_phone` (mất TRADE-IN-AP, đúng 7.590.000); GEN-05 gọi `order.update` đổi size ngay lượt 1 rồi nói "đã hoàn tất" trước khi khách đồng ý.
- Loại A và B khỏi HR giá/KM (chỉ để chẩn đoán, KHÔNG phải số nộp): full 0,0/0,0/11,8%; baseline 31–33%. Số 11,8% seed 3 còn lại từ bộ mẫu BTC.
**Đề xuất làm theo thứ tự:** (1) gán `price_vnd` cho `order.create` + chèn `customer_phone` vào `pricing.get_quote` khi thiếu + giữ `qty` từ báo giá trước (lỗi code, test offline); (2) chốt xác nhận danh tính SĐT dùng chung; (3) ép vào gate khi khách yêu cầu lên đơn; (4) prompt DT-05 và câu chuyển máy; (5) sửa bộ trích: chỉ gán `price_vnd` cho SKU đang tư vấn/đề xuất chính; (6) gửi BTC 3 điểm lệch sự thật. Sau đó chạy lại GĐ2 (trần mới, cần duyệt). Bộ BTC cố định luôn 14,3% TSR nên TSR chung ≥ 70% chỉ đạt khi bộ sinh 15/15.

### 11.89. Sửa theo § 11.88, mục 1–5 (2026-10-28; test offline, CHƯA gọi LLM thật)
| Mục | Sửa (file) | Test |
|---|---|---|
| 1a | `_gate_order_create`: thiếu `price_vnd` thì gán `int(unit)` từ báo giá (giá sau KM của một sản phẩm) — `orchestrator.py` | `OrderArgsTest` |
| 1b | `_tool_executor`: `pricing.get_quote` thiếu `customer_phone` thì chèn SĐT người gọi (không chèn khi `brief.blocker` = SĐT dùng chung) | `QuotePhoneTest` |
| 1c | `_qty_in_play`: gate do code mở lấy `qty` từ lời gọi báo giá/đặt gần nhất cùng sản phẩm (trước đó cứng `qty=1`, làm mất "2 máy" ở GEN-02) | `QtyCarryTest` |
| 1d | `_driver_create`: đơn có `needs_confirmation_call` thì câu chốt đơn báo "nhân viên sẽ gọi xác nhận đơn trước khi giao" | `ConfirmationCallTest` |
| 2 | `_ensure_identity_question`: SĐT dùng chung → lời đáp luôn có câu xin xác nhận tên (một lần/cuộc; vẫn trả lời giá/tính năng; thay câu hỏi xã giao cuối lượt) | `IdentityQuestionTest` |
| 3 | `_maybe_open_gate`: chỉ loại trừ `open_question` (vừa hỏi vừa chốt mua) thì mở gate NGAY, LLM chính trả lời rồi `enforce_reply` nối bước gate (`reason=opened_after_answer`); các loại trừ khác giữ nguyên | `OpenQuestionGateTest`, `test_gate_open` (sửa 1 test cũ: `open_question` không còn là loại trừ) |
| 4 | System prompt: câu chuyển máy ngoài phạm vi nói thẳng "chưa có thông tin chuyên môn"; sản phẩm lỗi → tra cả bảo hành LẪN đổi trả/lỗi nhà sản xuất; `final_price_vnd` là giá MỘT sản phẩm (tổng = × qty); "lên đơn" → gọi `order.create` ngay, không tự hỏi thông tin giao hàng; báo `needs_confirmation_call` | `PromptTest` |
| 5 | `extractor.py`: giá của mẫu KHÁC sản phẩm chủ đề (chủ đề = `pricing.get_quote` cuối lượt, hoặc đầu `product.shortlist`; mẫu khác nhận ra nhờ tên trong kết quả tool nằm cùng mệnh đề) mang field `alt_price_vnd`/`alt_list_price_vnd` | `AltPriceClaimTest` (+ chạy lại trên trace thật GEN-11: 5–6 claim `price_vnd` → `alt_price_vnd`, giữ 6.490.000) |
**Test:** `tests/test_gd2_fixes.py` (18 test); toàn bộ **897 OK** (`runs/_unittest_gd2fixes.txt`).
**Không sửa / còn mở:** GEN-07 (luật prompt, chỉ đo được bằng LLM thật), GEN-13 sai sản phẩm (seed 1), GEN-05 `order.update` chạy trước khi khách đồng ý, GEN-02 câu "giá cuối cho 2 máy" (chỉ có luật prompt), ba điểm sự thật kịch bản lệch tool (gửi BTC). Mục 3 giả định GEN-15 bị loại vì `open_question` — suy ra từ lời khách, chưa kiểm chứng bằng trace (trace không ghi `gate_open`). Mục 5 là sửa cách GÁN NHÃN claim của chính nhóm; giá mẫu khác không còn bị đối chiếu với sự thật của sản phẩm chủ đề (không còn bắt được lỗi giá của mẫu phụ) — cần ghi trong tài liệu nộp. Sau khi duyệt trần mới, chạy lại GĐ2 để đo.

### 11.90. Bước 15 GĐ2 — chạy LẠI sau các sửa § 11.89 (2026-10-28; trần 7.000 + 7.500 do chủ dự án duyệt)
`runs/gd2_run2/` (`gd2_report.md/json`, `failures_gen.txt`). Lần chạy đầu của đợt này bị dừng ngay khi vỏ lệnh thoát (không tốn chi phí), chạy lại đúng cách. **Chi phí thật: mẫu BTC 5.352,7 + sinh 5.978,1 = 11.330,8 VND** (lần trước 10.716,5). Không chạm trần. 91 lượt/seed.
| Chỉ số (full) | Lần 1 (§11.87) | Lần 2 | Ngưỡng |
|---|---:|---:|---|
| TSR | 50,0 ± 4,5 | **68,2 ± 0,0** (baseline 66,7) | ≥ 70 → CHƯA ĐẠT (hơn baseline: CÓ, trước: không) |
| TSR bộ sinh | 60,0/73,3/66,7 | **93,3/93,3/93,3** | — |
| RQR | 0,0 | 7,3 ± 6,5 (baseline 13,8) | giảm 50,6% ≥ 40% → ĐẠT (trước 100%) |
| HR giá/KM | 31,1 ± 7,2 | **6,2 ± 0,5** (baseline 42,2) | ≤ 5 → CHƯA ĐẠT |
| TTFT p95 | 12.935 ms | 8.343 ± 684 ms | ≤ 3.000 → CHƯA ĐẠT (total p95 9.953 ms) |
Guardrail 0 vi phạm. CCR 53,6 (không đổi). TSR bộ mẫu BTC vẫn 14,3% (gate chặn theo thiết kế).
**Ca bộ sinh:** GEN-03, 04, 07, 13, 15 nay đạt ở cả 3 seed (full); GEN-02 giữ `qty=2`, đọc lại đơn 2 máy, tổng 15.380.000 và bị chặn COD đúng. **Còn trượt: GEN-08** (3/3): chuyển máy đúng nhưng LLM bỏ qua luật prompt mới, không nói "chưa có thông tin chuyên môn" — chỉ có luật prompt, cần chốt bằng code (ca chuyển máy `scope_safety` nối câu đó). Đạt GEN-08 thì TSR chung = 16/22 = 72,7% (≥ 70).
**HR giá/KM còn lại = đúng một claim mỗi seed: GEN-01 call_2** (sự thật kịch bản 1.690.000, tool 1.521.000 do RUN-10 hiệu lực 12–25/10) — không phải LLM bịa; chờ BTC xác nhận. Còn GEN-02 (tổng 15.380.000 vs 15.980.000) và GEN-05 (40.000 vs 50.000) lệch sự thật nhưng không thuộc "giá/KM" của công thức; cả 2 cấu hình đều dính.
**Tác dụng phụ cần xử lý (RQR 0 → 7,3):** (a) SAMPLE-05 call_2 seed 1, 3: khách vừa hỏi vừa chốt ("lấy cái AirPure X giảm 500.000 hôm trước nhé") → mục 3 mở gate NGAY lượt 1, lời trả lời cho câu hỏi giảm giá bị thay bằng câu xác nhận SĐT của gate (trace `runs/gd2_run2/sample/full.r1.jsonl`), lượt 3 BTC tính hỏi lại slot `phone`. Đây là hệ quả của mục 3 (khách hỏi về giá/KM mà gate lấn lời đáp) — cần chặn: khi câu hỏi liên quan giá/mặc cả không mở gate sớm, hoặc giữ nguyên câu trả lời của LLM trước câu gate. (b) SAMPLE-03 call_2 seed 1, 3: hỏi "mã đơn hàng" (đơn không tồn tại vì call_1 bị gate chặn) — chỉ khác cách diễn đạt so với lần 1 ("số đơn hàng" không khớp cue), là dao động LLM, không do sửa đổi.
**Giới hạn:** mỗi seed một mẫu; p95 theo số lượt 91 mỗi seed; so sánh hai lần chạy khác nhau nhiều thứ cùng lúc (5 sửa) nên không tách được đóng góp từng mục.

### 11.91. Sửa theo § 11.90 (2026-10-28; test offline, CHƯA gọi LLM thật)
1. **GEN-08 — câu chuyển máy ca `scope_safety` bằng code** (`orchestrator.py` `_ensure_scope_notice`): khi LLM chính gọi `handoff.transfer` THÀNH CÔNG và chốt độc lập phân loại `scope_safety` (có trích dẫn nguyên văn), lời agent luôn mở bằng "Dạ phần này em chưa có thông tin chuyên môn để tư vấn chính xác ạ." (bỏ "Dạ," đầu câu cũ, viết hoa lại; không nối nếu đã có "chưa có thông tin/không có thông tin/em chưa rõ/em không chắc"; bỏ qua ca B, ca bị chặn, và lượt có tool `order.*` — sự cố đơn đã đặt có câu báo riêng). Cụm này nằm trong `ABSTAIN_KW` của `reference_eval`. Lưu ý: ca xóa dữ liệu cá nhân (scope_safety) cũng nhận câu này — chấp nhận được nhưng hơi lệch ngữ cảnh.
2. **SAMPLE-05 — gate không lấn câu hỏi về giá/KM** (`reply_reader.py`, `orchestrator.py`): bộ đọc LLM thêm `asks_price_promo` + `price_promo_quote` (đoạn nguyên văn, code kiểm chứng như các trích dẫn khác; ghi vào trace `reply_reading.asks_price_promo`); `_maybe_open_gate` thêm loại trừ `price_topic` → khách vừa chốt vừa hỏi/chất vấn về giá hoặc khuyến mãi thì KHÔNG mở gate sớm (LLM trả lời giá trước; gate mở ở lượt sau như lần chạy 1). Khách hỏi chuyện khác (vd freeship) vẫn mở sau câu trả lời (mục 3 của § 11.89 giữ nguyên). Không thêm lượt gọi LLM (cùng một lần đọc); prompt đọc dài thêm hai khóa → tốn thêm vài chục token/lần đọc, chưa đo.
**Test:** `tests/test_gd2_fixes.py` thêm `PriceTopicGateTest` (3), `ScopeNoticeTest` (4) → 25 test; toàn bộ `runs/_unittest_gd2fixes2.txt`.
**Chưa đo:** bộ đọc có gắn đúng `asks_price_promo` cho câu SAMPLE-05 hay không chỉ biết sau chạy LLM thật (nếu gắn sót, lỗi cũ còn); GEN-08 phụ thuộc chốt độc lập gắn `scope_safety` như lần 2 (3/3).

### 11.92. Bước 15 GĐ2 — chạy lần 3 sau các sửa § 11.91 (2026-10-28; trần 7.000 + 7.500 do chủ dự án duyệt)
`runs/gd2_run3/` (`gd2_report.md/json`, `failures_all.txt`). **Chi phí thật: mẫu BTC 5.502,2 + sinh 6.204,6 = 11.706,8 VND** (lần 2: 11.330,8); không chạm trần. 92 lượt/seed.
| Chỉ số (full) | Lần 2 (§11.90) | Lần 3 | Ngưỡng |
|---|---:|---:|---|
| TSR | 68,2 ± 0,0 (baseline 66,7) | **71,2 ± 2,6** (baseline 69,7) | ≥ 70 → ĐẠT |
| TSR bộ sinh | 93,3/93,3/93,3 | 93,3/100/100 | — |
| RQR | 7,3 ± 6,5 (baseline 13,8) | **2,2 ± 3,9** (baseline 15,0) | giảm 87,3% ≥ 40% → ĐẠT |
| HR giá/KM | 6,2 ± 0,5 | 9,5 ± 6,2 (seed: 16,7 / 5,9 / 5,9) | ≤ 5 → CHƯA ĐẠT |
| TTFT p95 | 8.343 ± 684 ms | 13.953 ± 3.243 ms | ≤ 3.000 → CHƯA ĐẠT |
Guardrail 0 vi phạm. CCR 52,4 (lần 2: 53,6). TSR bộ mẫu BTC vẫn 14,3% (gate chặn theo thiết kế).
**Đã xác nhận bằng trace:** (1) GEN-08 đạt ở cả 3 seed (không còn trong danh sách trượt) → mục 1 §11.91 có tác dụng. (2) SAMPLE-05 call_2: lượt 1 giữ nguyên câu trả lời giá 4.890.000đ, không còn RQR hỏi lại SĐT → mục 2 §11.91 có tác dụng (RQR còn lại chỉ là SAMPLE-03 seed 3 hỏi "mã đơn hàng" — biến thiên LLM). Chưa đọc trực tiếp cờ `asks_price_promo` trong trace.
**Seed 1 bị lỗi mạng giữa lúc chạy:** `gen_console.txt` có 7 dòng "Connection error" ở đầu pha sinh (lần 2: 1 dòng; mẫu BTC lần 3: 0). Hậu quả: SC-GEN-06 call_1 seed 1 rơi vào nhánh dự phòng mất LLM và tư vấn máy lọc AirPure Y cho khách hỏi máy hút sữa → bộ nhớ ghi sai `product_advised` → call_2 chốt đơn nhầm SKU-AP-Y (5.200.000 vs 4.290.000): TSR GEN-06 trượt và 2 claim giá lệch → HR seed 1 = 16,7. Seed 2, 3 (không lỗi mạng): HR 5,9 = chỉ GEN-01 call_2 (sự thật kịch bản 1.690.000, tool 1.521.000) → chờ BTC. TTFT p95 cũng bị đuôi lỗi kết nối kéo lên (trung vị 4,1 → 4,5 s; tối đa 37 → 52 s).
**Lỗi thật lộ ra (chưa sửa):** `src/agents/specialists.py:51` — nhánh dự phòng mất LLM dùng mặc định cứng `"SKU-AP-Y"` khi brief chưa có `product_advised`, nên mất LLM ở lượt đầu sẽ chào một sản phẩm không liên quan. Nên đổi thành không gợi ý sản phẩm (hỏi nhu cầu) và/hoặc cho nhánh dự phòng nói "em xin phép gọi lại" thay vì bịa gợi ý; kèm test offline.
**Còn lại:** GEN-01 / GEN-02 / GEN-05 sự thật kịch bản lệch tool (gửi BTC); TTFT; GEN-05 order.update trước khi khách đồng ý. **Giới hạn:** mỗi seed một mẫu; lần 3 khác lần 2 hai sửa + biến thiên LLM/mạng; seed 1 không sạch.

### 11.93. Sửa nhánh dự phòng mất LLM (2026-10-28; test offline, CHƯA gọi LLM thật)
Theo § 11.92: nhánh dự phòng mất LLM không còn chọn cứng `SKU-AP-Y` (và giá mặc định 5.200.000).
- `src/agents/specialists.py` `SalesAdvisorAgent.advise`: brief chưa có `product_advised` → `suggested_sku=None`, không lời gợi ý.
- `src/harness/orchestrator.py` (nhánh rule-based): `target_sku` không còn mặc định; không có SKU → không gọi `pricing.get_quote`, không claim giá, không lên đơn; chỉ khi tool trả `final_price_vnd` mới báo giá / xác nhận giá / lên đơn (bỏ mặc định 5.200.000 khi tool lỗi). Không có giá → câu "hệ thống đang gián đoạn một chút, anh/chị cho em biết mình đang quan tâm sản phẩm nào để em hỗ trợ ạ?" (câu hỏi chính sách có căn cứ vẫn trả lời như cũ).
- Test: `tests/test_gd2_fixes.py` thêm `NoLLMFallbackTest` (3) → 28 test; toàn bộ: `runs/_unittest_gd2fixes3.txt`.
- **Chưa đo / giới hạn:** chỉ chặn nhánh dự phòng chọn bừa sản phẩm; lỗi mạng giữa cuộc gọi vẫn làm lượt đó không tư vấn được (đo bằng LLM thật khi chạy lại).
- **Kết quả test toàn bộ:** 907 test OK (`runs/_unittest_gd2fixes3.txt`). Lần chạy đầu có 6 test cũ trượt vì ngầm dựa vào sản phẩm mặc định SKU-AP-Y của nhánh dự phòng; đã sửa bằng helper `advisor_suggests` (`tests/_helpers.py`), test nào cần sản phẩm đã tư vấn thì nói rõ (test_api, test_call_continuity, test_cluster_4_8, test_fallback_honesty, test_order_gate).

### 11.94. Bước 15 GĐ2 — chạy lần 4 sau § 11.93 (2026-10-28; trần 7.000 + 7.500 như lần trước, chủ dự án duyệt "chạy LLM để đưa ra đánh giá")
`runs/gd2_run4/` (`gd2_report.md/json`, `failures_all.txt`). **Chi phí thật: mẫu BTC 5.540,1 + sinh 6.098,8 = 11.638,9 VND**; không chạm trần; 0 dòng "Connection error". 92 lượt/seed.
| Chỉ số (full) | Lần 2 | Lần 3 (§11.92) | Lần 4 | Ngưỡng |
|---|---:|---:|---:|---|
| TSR | 68,2 | 71,2 ± 2,6 | **72,7 ± 0,0** (baseline 71,2) | ≥ 70 → ĐẠT |
| TSR bộ sinh | 93,3 ×3 | 93,3/100/100 | **100 ×3** | — |
| RQR | 7,3 ± 6,5 | 2,2 ± 3,9 | **2,1 ± 3,6** (baseline 12,2) | giảm 76,5% ≥ 40% → ĐẠT |
| HR giá/KM | 6,2 ± 0,5 | 9,5 ± 6,2 | **6,0 ± 0,2** (baseline 33,9) | ≤ 5 → CHƯA ĐẠT |
| TTFT p95 | 8.343 | 13.953 | 26.177 ± 33.247 ms | ≤ 3.000 → CHƯA ĐẠT |
Guardrail 0 vi phạm. CCR 52,4. TSR bộ mẫu BTC vẫn 14,3% (gate chặn theo thiết kế). TSR chung 16/22 = 72,7% ở cả 3 seed: đây là lần đầu 3 seed cùng đạt ≥ 70%.
**HR giá/KM còn lại chỉ là GEN-01 call_2** (sự thật kịch bản 1.690.000, tool 1.521.000 do RUN-10 hiệu lực 12–25/10; seed 3 thêm một claim nên 6,2). Không phải LLM bịa; ngưỡng ≤ 5% chỉ đạt nếu BTC xác nhận sự thật của GEN-01 hoặc loại ca đó. GEN-02 (tổng 15.380.000 vs 15.980.000) và GEN-05 (40.000 vs 50.000) cũng lệch sự thật nhưng ngoài công thức "giá/KM".
**RQR còn lại:** SAMPLE-03 seed 2 hỏi "mã đơn hàng" (LLM biến thiên, 0/3 → 1/3 seed qua các lần).
**TTFT p95 không phản ánh hệ thống:** seed 1 có 3 lượt API đứng 68–128 s (SC-GEN-07, SC-GEN-02, SC-GEN-11), console không báo lỗi nào. Seed 2 và 3 p95 = 6,7 và 7,3 s, trung vị 3,6–3,7 s. Vẫn chưa đạt ≤ 3 s; cần tối ưu riêng (bước tối ưu token/TTFT sau khi hoàn thiện) và đặt timeout/hủy-thử-lại cho cuộc gọi LLM.
**Giới hạn:** mỗi seed một mẫu; chưa tách được đóng góp của từng sửa; sửa SKU mặc định (§11.93) chỉ có tác dụng khi mất LLM nên lần này (không lỗi mạng) không đo được.

### 11.95. Timeout + thử lại cuộc gọi LLM (2026-10-28; test offline, CHƯA gọi LLM thật)
Nguyên nhân từ § 11.94: lượt API đứng 68–128 s (seed 1) vì SDK mặc định timeout 600 s, không có lỗi trong console.
- `src/llm/client.py`: `OpenAI(timeout=LLM_TIMEOUT_S=20, max_retries=LLM_API_RETRIES=1)` — timeout tính theo KHOẢNG LẶNG giữa 2 gói dữ liệu (stream vẫn chạy thì không bị cắt; trung vị TTFT sạch 3,6–4,3 s, tối đa sạch 8,9 s). `_stream_round` thử lại cả vòng tối đa `LLM_STREAM_RETRIES=2` lần khi timeout/đứt kết nối (phần text nhận dở bị bỏ; tool chỉ chạy sau khi vòng đọc xong nên thử lại an toàn); lỗi khác và `BudgetExceeded` (BaseException) ném ngay, không thử lại. Biến mới ghi ở `.env.example`.
- Test: `tests/test_llm_timeout.py` (7). Toàn bộ test: `runs/_unittest_gd2fixes4.txt`.
- **Chưa đo / giới hạn:** chưa biết 20 s có cắt nhầm vòng suy luận dài hay không (chỉnh bằng `LLM_TIMEOUT_S`); thời gian xấu nhất của một vòng khi đứt liên tục ≈ 3 lần × 20 s + chờ; chi phí vòng bị cắt không được ghi (thấp hơn thật một chút); hiệu quả lên TTFT p95 chỉ biết khi chạy LLM thật.

### 11.96. Bước 11 — chi phí và quyết định của router chính sách vào trace và trần chi phí (2026-10-28; test offline, CHƯA gọi LLM thật)
Lỗ hổng tìm thấy khi rà bước 11: router chính sách (LLM thứ hai, chạy phía bộ nhớ, có `LLMClient` riêng) **không** được cộng vào tổng/trần chi phí của orchestrator và không có trong trace — mọi tổng chi phí đã báo ở § 11.87–11.94 thiếu phần router (≈ 8–9 VND/lần tra chính sách, cỡ một đến hai phần trăm mỗi lần chạy).
- `SemanticKBStore.search` giữ `last_usage` (các lần gọi router của chính lần tìm đó, không drain để script đo vẫn tự drain); `MemoryService.query_policy` đặt `last_policy_route = {route, usage}`; `mcp-memory` trả thêm khóa `route_info`; `RemoteMemoryService.query_policy` giữ lại vào cùng thuộc tính.
- `orchestrator._note_policy_route`: sau `search_policy`, cộng `usd_cost` vào `CostTracker.add_external_cost` (mới; vào tổng và trần cứng) và ghi `policy_route` vào trace lượt (`files`, `answerable`, `as_of_date`, `fallback_all`, `vnd_cost`, `latency_ms`); lượt không tra chính sách → `policy_route: null`.
- Test: `tests/test_policy_cost.py` (6): service, qua MCP inproc, trace, tổng, trần.
- **Còn mở của bước 11 (đo ở § 11.82, chưa cải thiện):** multi-hop full recall @3/@5 = 8,3/25,0 %; từ chối câu `unanswerable` 0 % (restricted 60 %). SAMPLE-07 đạt ở cả 3 seed lần 4 (không có trong danh sách ca sai). Cải thiện hai mục còn lại cần thêm lần đo LLM thật (~540 VND/lần, `scripts/eval_policy_router.py --llm`) — chờ duyệt trần.

### 11.97. Bước 18 — giao diện web `ui/` (2026-10-28; KHÔNG gọi LLM)
- `ui/index.html` (HTML/CSS/JS thuần, không thư viện ngoài, sáng/tối theo hệ thống): khung hội thoại (Enter gửi), **Call Brief** (hiện ngay khi mở cuộc gọi: câu mở đầu gợi ý, sản phẩm/giá đã tư vấn, rào cản, *không được hỏi lại*, *phải mang sang*, hồ sơ còn hiệu lực, số liệu code đã tra sẵn), **dòng thời gian bộ nhớ** (episode + các phiên bản sự thật, bản cũ gạch ngang), nhật ký tool, đơn hàng, thông số lượt vừa rồi (TTFT, tool, thông tin cũ đã dùng, chi phí), tải `.wav/.mp3` → `/asr` → điền ô chat. Ba mẫu: khách mới, Hoa quay lại (17/10), khách Fanpage. Dữ liệu từ máy chủ chỉ đưa vào DOM bằng node văn bản (không chèn HTML thô; có test).
- `api/app.py`: `/ui/` phục vụ thư mục `ui/` cùng origin (không cần CORS), `/` chuyển hướng sang `/ui/`. `scripts/run_demo.py [--reset] [--port]`: seed DB demo `data/demo.db` (idempotent) rồi chạy uvicorn một worker; không đụng DB thật.
- Kiểm bằng trình duyệt thật (không LLM, `OPENAI_API_KEY` rỗng): mẫu Hoa quay lại → mở cuộc → Call Brief đúng (chị Hoa, 1 cuộc trước 15/10, AirPure Y, 5.200.000 đ, rào cản "can hoi chong", không được hỏi lại diện tích/trẻ nhỏ/ngân sách, số liệu đã tra sẵn: còn hàng 15, giá cuối 5.200.000, tặng quà, miễn phí vận chuyển, bảo hành 24 tháng); gửi "giá vẫn như hôm trước đúng không em" → trả lời đúng giá từ tool (nhánh rule-based), tab *Lượt vừa rồi* và nhật ký tool điền đủ. Mở lại cuộc cùng SĐT trong cùng tiến trình tăng `call_n` (đúng ngữ nghĩa API; `--reset` + khởi động lại để demo tái lập).
- Test: `tests/test_api.py::UiTest` (2). **Chưa kiểm** với LLM thật (cần duyệt trần) và trên điện thoại/Safari; chỉ thử trên trình duyệt tích hợp.
- **Lệch kế hoạch:** PLAN ghi UI sinh bằng W&B OpenUI (cần LLM sinh giao diện hoặc Ollama, phải cài/tải thêm). Giao diện này do nhóm dựng tay; chưa dùng OpenUI. Hồ sơ nộp ghi đúng điều này.

### 11.99. Chạy thử giao diện với LLM thật theo DEMO_SCRIPT (2026-10-28; trần 500 VND do chủ dự án duyệt)
`python scripts/run_demo.py --reset --port 8766 --max-cost-vnd 500` (mới: `--max-cost-vnd` → `API_MAX_COST_VND` → trần cứng của máy chủ; chạm trần thì `/chat` trả 402 chứ không sập; `/health` trả thêm `spent_vnd`, `cap_vnd`; giao diện hiện "Chi phí LLM: x / y VND"). `gpt-4o-mini`, qua giao diện trong trình duyệt tích hợp. Test mới: `tests/test_api.py::BudgetTest` (2).
**Kết quả (10 lượt, 2 cuộc gọi, 168 VND, không chạm trần):** cuộc 1 (khách mới Lan, 15/10): tư vấn AirPure Y đúng, báo giá 5.200.000 khớp tool, "hỏi ông xã" → ghi `blocker` + `objection`; kết thúc → episode `hen_goi_lai`. Cuộc 2 (17/10, cùng SĐT): Call Brief hiện ngay trước lượt đầu đúng (chị Lan, 1 cuộc trước, AirPure Y, 5.200.000, blocker, không được hỏi lại diện tích/trẻ nhỏ/sản phẩm, đã tra sẵn còn hàng 15/giá cuối/quà/bảo hành 24 tháng); agent chào đúng câu tiếp nối, không hỏi lại; order gate xác nhận tên/SĐT, xin địa chỉ và thanh toán, **không tạo đơn trước khi khách đồng ý**; đọc lại đơn; sau "đồng ý" mới `order.create` (`price_vnd` 5.200.000, COD) → OD600001, nói nhân viên sẽ gọi xác nhận. TTFT 2–6,7 s (chưa đạt 3 s).
**Lệch kịch bản và xử lý:** câu địa chỉ trong kịch bản ("số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội", thiếu "đường/quận") không được `detect_addresses` nhận ra → agent hỏi lại rồi "chưa ghi nhận được địa chỉ"; đã đổi câu demo sang "Giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, thanh toán COD" (chạy tiếp đúng trong cùng phiên) và ghi hạn chế vào `DEMO_SCRIPT.md`; **chưa sửa mã** (bộ nhận địa chỉ là heuristic theo dấu hiệu hành chính, nên bàn trước khi sửa gốc). Cuộc 2 vì thế mất 7 lượt thay vì 5; kịch bản đã sửa **chưa chạy lại nguyên văn** (trần 500 VND không đủ cho lần thứ hai).
**Chưa kiểm:** chi phí router chính sách trong demo (không có câu hỏi chính sách), kịch bản đã sửa chạy nguyên văn, điện thoại/trình duyệt khác.

### 11.98. Hồ sơ nộp (mục F) — `submission/` (2026-10-28; không gọi LLM)
`submission/README.md` (cài đặt, chạy demo, đánh giá một lệnh, cấu trúc mã, hạn chế), `ARCHITECTURE.md` (sơ đồ mermaid, vòng lặp harness, bộ nhớ, vì sao MCP và vì sao không A2A, quyết định), `DATASET.md` (thành phần, cách sinh, phân bố, hạn chế, PII), `EVALUATION_REPORT.md` (bảng 5 chỉ số so baseline, trước/sau 4 lần chạy, 14 ca làm sai, độ trễ, chi phí ≈ 63 VND/cuộc, tác động kinh doanh có ghi rõ là giả định, giới hạn), `DEMO_SCRIPT.md` (kịch bản 8 phút, hai cuộc gọi), `slides.html` (15 slide). `docs/PIPELINE.md` § 5–6 cập nhật theo trạng thái hiện tại. `scripts/package_submission.py --no-model` chạy thử: 1.061 file, sạch (không `.env`, không `backup_*`, không chuỗi giống khóa), có `submission/` và `ui/`.
**Chưa có / cần người làm:** video demo (chưa quay), slide `.pptx` (chỉ HTML — thiếu `python-pptx`, chưa cài), điền tay `manual_review.csv`, gửi BTC 3 chỗ sự thật kịch bản lệch tool, rà lại số trong báo cáo sau mỗi lần chạy mới. Số liệu trong báo cáo lấy từ `runs/gd2_run4/`; chi phí ≈ 63 VND/cuộc tính chia đều 186 cuộc của hai cấu hình.

### 11.100. Bộ nhận diện địa chỉ chịu được câu không có đường/phường/quận (2026-10-28; test offline, CHƯA gọi LLM thật)
Theo § 11.99. Gốc lỗi: `detect_addresses` (`src/privacy/pii_vault.py`) chỉ nhận (a) đoạn sau cụm "giao về/địa chỉ/nhà … ở" có dấu hiệu hành chính, hoặc (b) "số N đường/phố/ngõ…". Câu "Giao **cho Lan**, số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội, thanh toán COD" không có "giao về" và không có từ hành chính nên không bị che thành `<ADDR_n>`; agent coi như khách chưa đưa địa chỉ. (Câu có "giao về số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội" thì **đã** nhận được từ trước nhờ "giao về" + số nhà.)
**Sửa:** thêm `_spans_by_province`: số nhà ("số 12" hoặc số trần) + các đoạn phân cách bằng dấu phẩy + **tỉnh/thành ở cuối** (dùng danh sách tỉnh/thành sẵn có, so khớp không dấu; "TP.HCM" = "tphcm"). Có "số" đứng trước thì viết thường vẫn nhận; số trần ("12 Nguyễn Trãi, …") phải mở đầu bằng chữ hoa. Dừng ở lời thanh toán, số điện thoại hoặc con số kế tiếp (giá tiền, "quận 1"). Gộp với các đoạn cũ; không đổi hành vi của các đường nhận diện cũ.
**Test:** `tests/test_pii_vault.py` thêm 2 (6 câu phải nhận đúng đoạn + mask `Giao cho Lan, <ADDR_1>, thanh toán COD`; 7 câu không được nhận nhầm: giá tiền, "lấy 2 cái ở Hà Nội", "chị 25 tuổi, phòng 25m2 ở Hà Nội", "giao Hà Nội", "số 5 trong Hà Nội"…). Toàn bộ: 926 test OK (`runs/_unittest_address.txt`).
**Giới hạn / chưa đo:** chỉ nhận khi có tỉnh/thành trong danh sách ở CUỐI địa chỉ và có dấu phẩy ("số 12 Nguyễn Trãi Thanh Xuân Hà Nội" không dấu phẩy vẫn không nhận); địa chỉ không nêu tỉnh/thành ("số 12 Nguyễn Trãi, Thanh Xuân") vẫn không nhận; heuristic vẫn có thể bắt nhầm một cụm lạ có số + dấu phẩy + tên tỉnh. Chưa chạy lại demo với LLM thật.

### 11.101. Dọn thư mục/file không cần cho dự án → `Harness_Agent/NotRelated/` (2026-10-28)
Chuyển (không xóa) 12 mục cấp thư mục/file và 34 file nháp trong `runs/`; danh sách đầy đủ + lý do + cách khôi phục: `../NotRelated/MANIFEST.md`. Cấp `Code/`: `backup_2026-10-21/`, `dataset_v1/`, `dataset_regen1/`, `docs/pipeline_dataflow.html`, nháp `runs/_*` và `runs/api_session.jsonl`, `runs/gd2_dry_report/` — chỉ những mục **không mã, test hay tài liệu nào nhắc tên** (đã grep). Cấp `Harness_Agent/`: `Papers/`, `Tools/`, `.archify/`, `generate_final_docs.py`, `Luồng xử lý phác thảo.md`, hai file `.docx.bak`, `__pycache__/`.
**Cố ý giữ lại:** `generated_m1_v1/` (DATASET_CHANGELOG ghi là bản đóng băng để so sánh), `docs/architecture_animated.svg` (CHECKING nhúng ảnh này), mọi `scripts/*` (đều có trong nhật ký/README), `ui_app.py` (trang quản trị), `buoc15_*`, `ui_replay_*`, `asr_*` trong `runs/` (bằng chứng các lần đo), `.vscode/`, `.agents/`, hai file `.docx` và PDF đề bài, `README.md` gốc (được `Code/README.md` dẫn tới).
**Không đẩy GitHub:** `Harness_Agent/.gitignore` (mới: `NotRelated/`, `.agents/`) và `Code/.gitignore` (thêm `NotRelated/`, `.vscode/`, `data/*.bak`; trước đó `data/*.bak` chưa được loại và sẽ bị đẩy lên). Chưa có repo git ở máy này nên chưa thử `git status`.
**Kiểm sau dọn:** 926 test OK (`runs/_unittest_after_cleanup.txt`); `package_submission.py --no-model` sạch (866 file).
**Còn lại cần bạn quyết:** `Code/runs/` (~30 MB, hàng trăm file trace/log) **không** nằm trong `.gitignore` nên sẽ bị đẩy lên GitHub nếu để nguyên.
**Cập nhật (2026-10-28, sau duyệt):** `Code/.gitignore` thêm `runs/*` nhưng giữ `runs/gd2_run*/gd2_report.md`, `gd2_report.json`, `failures_*.txt` (dùng `runs/*` rồi `!runs/gd2_run*/` rồi `runs/gd2_run*/*` rồi các dòng `!` — Git không cho bỏ ignore file khi thư mục cha bị ignore nguyên khối). Kiểm bằng `git check-ignore` / `git add -n` trên **repo tạm** (thư mục nháp, cùng `.gitignore` và cùng cấu trúc `runs/`): 12 trong 458 file của `runs/` sẽ được đẩy (báo cáo của `gd2_run`, `gd2_run2`, `gd2_run3`, `gd2_run4`); trace, console, `_merged`, `_unittest_*`, `asr_*` bị ignore; `src/` vẫn được theo dõi, `NotRelated/` bị ignore. **Hệ quả:** trên GitHub, các đường dẫn `runs/...` khác trong nhật ký sẽ không mở được, và không chạy lại `gd2_report.py` từ trace được vì trace không được đẩy (vẫn còn ở máy này).

### 11.102. Khách đổi sang sản phẩm khác giữa cuộc gọi — 4 điểm sửa (2026-10-28; test offline, CHƯA gọi LLM thật)
Nguồn: ảnh chụp giao diện + `runs/api_session.jsonl` (`call_3`, khách Warmly áo phao 1.490.000đ → "đổi sang áo khoác windbreaker"). Triệu chứng: agent đi tìm đơn để đổi; báo giá Windbreak 1.490.000đ (đúng 690.000đ); size L/màu be của áo phao áp sang món mới.
**Gốc (đã xác nhận bằng mã):** (a) Tầng 1 enum SKU (`_build_dynamic_tools`) khóa theo `brief.product_advised` lúc ĐẦU cuộc: `pricing.get_quote`/`inventory.check`/`order.*` chỉ cho phép 13 SKU `SKU-JK-DWN*`, không có SKU Windbreak → LLM không báo giá được sản phẩm mới nên lấy SKU áo phao rồi gọi tên Windbreak; `_check_named_variants`/`_repair_unknown_sku`/`_canonical_sku` cũng ưu tiên `product_advised`. (b) Prompt: "khách muốn đổi size/màu/sản phẩm → PHẢI gọi `order.update`", không phân biệt khi chưa có đơn; LLM còn tự bịa `order_id`. (c) Guardrail chỉ kiểm số tiền có trong kết quả tool, không kiểm tiền đó của sản phẩm nào. (d) Call Brief đưa `size/color/variant_sku` của sản phẩm cũ vào prompt không nhãn.
**Sửa:**
1. **Sản phẩm đang bàn**: `_discussed_parents` xếp MỚI NHẤT trước (sản phẩm đã tư vấn đứng sau, tối đa 3); enum SKU là HỢP các sản phẩm đang bàn và được **dựng lại mỗi vòng LLM** (`tools_override` nhận callable — `LLMClient._chat_with_tools`), nên sản phẩm vừa `catalog.search` ở vòng trước vào enum ngay vòng sau; `_check_named_variants`, `_canonical_sku`, `_repair_unknown_sku`, `_empty_search_fallback` dùng sản phẩm đang bàn thay vì `product_advised`.
2. **Đổi sản phẩm ≠ đổi đơn**: prompt chỉ cho `order.update` với đơn đã đặt; chưa có đơn mà "đổi sang/xem/lấy món khác" → chọn lại sản phẩm (tra + báo giá đúng SKU, KHÔNG `order.update`); `order.update` trả `order_not_found` giờ kèm `hint` để LLM tự quay sang `catalog.search`/`pricing.get_quote` ngay vòng sau.
3. **Tên sản phẩm ↔ SKU báo giá**: `_bind_price_to_product` — lời nói gọi tên đúng MỘT sản phẩm (không tính quà tặng), nêu số tiền trùng giá sản phẩm KHÁC trong lượt, và sản phẩm đó chưa được báo giá → CODE gọi `pricing.get_quote` đúng sản phẩm, dựng lại câu từ kết quả (lời gọi nằm trong trace); không báo giá được thì câu an toàn.
4. **Size/màu theo sản phẩm**: prompt có nhãn "size/màu chỉ cho sản phẩm đã tư vấn"; khi sản phẩm đang bàn khác sản phẩm đã tư vấn, `size/color/variant_sku` cũ bị bỏ khỏi prompt và có câu "khách ĐANG xem sản phẩm khác".
**Test:** `tests/test_product_switch.py` (11): thứ tự sản phẩm đang bàn, enum nhiều sản phẩm (và một sản phẩm vẫn như cũ), kiểm tồn kho biến thể trên sản phẩm vừa tra, tools dựng lại mỗi vòng, `order.update` có hint, prompt, giá bị thay đúng 690.000đ và trace có lời gọi sửa, câu nhất quán giữ nguyên, quà tặng không kích hoạt, size/màu ẩn/hiện. Toàn bộ: 937 test OK (`runs/_unittest_product_switch.txt`).
**Chưa kiểm / giới hạn:** chưa chạy hội thoại này với LLM thật (cần duyệt trần); (3) chỉ bắt được khi lời nói dùng ĐÚNG tên catalog ("Áo khoác gió Windbreak") — nói "áo windbreaker" thì không nhận ra; không xử lý so sánh nhiều sản phẩm trong một câu; (1) enum vẫn là danh sách đóng (3 sản phẩm): sản phẩm chưa từng được tra trong cuộc vẫn không báo giá được cho tới khi `catalog.search` (enum dựng lại vòng sau); (2) LLM có thể vẫn gọi `order.update` ở vòng đầu (chỉ giảm nhờ prompt + hint, không chặn bằng code).
**Chạy thử LLM thật (2026-10-28, trần 300 VND do chủ dự án duyệt; tốn ≈ 302 VND = 162,1 lần 1 + 139,8 lần 2, vượt trần 2 VND vì trần chỉ kiểm trước mỗi lần gọi API):** phát lại hội thoại `call_3` (khách 0797272046, bản sao DB demo, không đụng DB thật; 30/10, hotline).
- *Lần 1 (trước sửa prompt đích danh):* lượt 2 "đổi sang áo khoát windbreaker" **không còn gọi `order.update`** (gọi `product.shortlist`) nhưng agent nói "không có sản phẩm áo khoác windbreaker trong kho" — sai (shortlist theo nhu cầu không trả Windbreak; LLM không tra theo tên). Lượt 3 "cho xem giá": LLM vẫn báo giá `SKU-JK-DWN-L-BE` (enum chưa có Windbreak vì chưa tra), **chốt (3) bắt được**: code gọi `pricing.get_quote` `SKU-JK-WND` và câu cuối là "Áo khoác gió Windbreak hiện có giá 690.000đ" (đúng). Lượt 4 "cỡ M màu đen": `inventory.check`/`get_quote` `SKU-JK-WND-M-DEN` → 690.000đ, còn 4 — đúng sản phẩm đang bàn (nhờ (1)). Lượt 5 hỏi lại áo phao: 1.490.000đ, còn 56 — đúng.
- *Sửa thêm:* prompt "khách nêu ĐÍCH DANH một sản phẩm/mẫu → `catalog.search` theo tên, không dùng `product.shortlist`; không nói 'không có sản phẩm' khi chưa tra" (+ test).
- *Lần 2 (sau sửa; chạm trần ở lượt 4 → `/chat` trả 402, không sập):* lượt 2 tìm thấy Windbreak 690.000đ, còn hàng (nhưng vẫn qua `product.shortlist` lần này — LLM không luôn theo luật mới); lượt 3 báo 690.000đ ngay từ `get_quote` `SKU-JK-WND`, không cần chốt (3).
- **Kết luận:** 3 lỗi người dùng thấy (đi tìm đơn để đổi, giá sai 1.490.000 cho Windbreak, size/màu cũ áp sang món mới) **không tái hiện** ở hai lần chạy; nhưng một mẫu mỗi lần, LLM biến thiên (lượt 2 chạy 1 nói sai "không có", chạy 2 đúng) và **chưa kiểm** hết các cách khách diễn đạt; lượt 2 vẫn có thể dùng `shortlist` thay `catalog.search`.

### 11.103a. Sửa đáp án SC-GEN-01 / GEN-05 / GEN-02 (2026-11-02; KHÔNG gọi LLM)
Các ghi chú § 11.88–11.94 ("sự thật kịch bản lệch tool, chờ BTC") **sai hướng**: SC-GEN-01 do `generate_dataset.py` của nhóm sinh, không phải của BTC. Ngày call_2 (16/10) khuyến mãi `RUN-10` (giảm 10%, 12–25/10, áp cho `SKU-SN-RUN2`, `promotions.json`) đang hiệu lực; 1.690.000 × 0,9 = 1.521.000 = giá tool trả. Đáp án kịch bản chỉ tính `RUN2-SALE` hết hạn nên ghi 1.690.000.
**Sửa:** `ground_truth_facts.price_vnd` 1.690.000 → 1.521.000 trong `generate_dataset.py` và `test_set/generated_m1/SC-GEN-01.json` (+ `notes`). `EVALUATION_REPORT.md` mục 5 đính chính. **Chưa làm:** chấm lại trace `runs/gd2_run4` để có HR giá/KM mới; kiểm GEN-02 / GEN-05 xem có cùng nguyên nhân không. Trường `forbidden_claims promo_active=true` giữ nguyên: nó nói về `RUN2-SALE`, nhưng agent nói "giảm 10%" (RUN-10) có thể bị hiểu là `promo_active` — cần xem khi chấm lại.
**Chấm lại (2026-11-02, KHÔNG gọi LLM):** `python scripts/gd2_report.py --root runs/gd2_run4 --out-dir <thư mục tạm>` (không ghi đè `runs/gd2_run4/gd2_report.*`). Full: HR giá/KM **6,0 → 0,0** (ba seed 0,0); baseline 33,9 → 29,3; TSR, RQR, CCR, TTFT không đổi. HR ≤ 5% **ĐẠT** — lưu ý: đáp án sửa SAU khi thấy điểm; căn cứ là `promotions.json` (RUN-10), kiểm lại được độc lập. Các lần chạy 1–3 chưa chấm lại.
**GEN-02 / GEN-05 (đã kiểm, CHƯA sửa):** cả hai cũng là đáp án kịch bản sai, agent đúng theo tool. GEN-05 call_2 (25/09): RUN2-SALE −20% đang chạy → chênh thật 40.000 = 50.000 × 0,8 (tool `order_update` lấy giá mới − giá đơn đều đã giảm); `facts_established.price_quoted_vnd` 1.690.000 của call_1 (20/09) cũng bỏ sót RUN2-SALE (đúng 1.352.000). GEN-02 call_1 (15/10): AIR-OCT −300.000/máy → 2 × 7.690.000 = 15.380.000; nhưng AIR-2ND-50 (máy thứ 2 −50%, cùng đơn) cũng có thể áp (tổng 11.985.000) nên tổng đúng chưa rõ; mục đích ca (COD > 10.000.000) đúng với mọi cách tính. Hai ca này không nằm trong công thức HR giá/KM. Cần quyết: sửa đáp án hay bỏ trường `total_vnd`. Cập nhật `submission/` (EVALUATION_REPORT, README, DEMO_SCRIPT, slides).
**Sửa GEN-05 (2026-11-02, KHÔNG gọi LLM):** `variant_price_delta_vnd` 50.000 → 40.000 (call_2, 25/09, RUN2-SALE −20% đang chạy) và `facts_established.price_quoted_vnd` call_1 1.690.000 → 1.352.000 (20/09), cả `generate_dataset.py` và `generated_m1/SC-GEN-05.json` (+ `notes`). Chấm lại `gd2_run4`: chỉ số tổng không đổi (GEN-05 ngoài công thức HR giá/KM; HR full vẫn 0,0). `runs/gd2_run4/failures_all.txt` là bản cũ, chưa tạo lại. GEN-02 vẫn chưa sửa (tổng đúng chưa rõ: AIR-OCT hay AIR-2ND-50).
**Sửa GEN-02 (2026-11-02, KHÔNG gọi LLM):** `total_vnd` 15.980.000 → **11.985.000** (`generate_dataset.py` + `generated_m1/SC-GEN-02.json` + `notes`). Căn cứ: `products.json` (AirPure Pro 7.990.000) + `promotions.json` (ngày 15/10: AIR-2ND-50 −50% máy thứ 2, 05/10–04/11; AIR-OCT −300.000/máy) + KM-04 (chọn chương trình có lợi nhất; không cộng hai chương trình không stackable): 7.990.000 + 3.995.000 = 11.985.000 < 2 × 7.690.000 = 15.380.000. Mục đích ca (COD > 10.000.000) vẫn đúng. Giả định: coi AIR-OCT và AIR-2ND-50 không dùng chung được trên cùng đơn (KM-03/04); nếu BTC cho dùng AIR-OCT cho máy đầu thì đúng là 11.685.000.
> **Đính chính thứ tự (2026-11-04):** các đoạn về GEN-02 dưới đây do HAI phiên làm song song và thay nhau: 15.980.000 → 11.985.000 (phiên khác) → xóa file theo yêu cầu chủ dự án → tạo lại với 15.380.000 → **11.685.000 (HIỆN HÀNH, § 11.104)**; `SC-GEN-02.json` CÓ trong bộ (22 kịch bản). Mục này từng đánh số trùng § 11.103; nay là 11.103a (đáp án) và 11.103b (chạy lần 5).
**Lỗi agent lộ ra (CHƯA sửa lúc ghi; đã sửa ở § 11.105–11.106):** trace `gd2_run4` cho thấy agent gọi `pricing.get_quote(sku, qty=2)` KHÔNG truyền `basket_skus`, nên mock chỉ xét AIR-OCT (7.690.000/máy, 15.380.000) → agent báo khách cao hơn chính sách 3.395.000. Khi có `basket_skus` mock lại trả 3.995.000/máy (áp 50% cho CẢ hai máy, tổng 7.990.000 — lệch KM-05 nên không dùng được như hiện tại). Cần quyết: xử lý ở tầng agent (tự tính AIR-2ND-50 từ hai báo giá) hay báo BTC lỗi mock. Chấm lại gd2_run4: chỉ số tổng không đổi (total_vnd ngoài công thức HR giá/KM); GEN-02 nay bị `hr` lệch thật ở các lượt báo tổng.
**Xóa SC-GEN-02 (2026-11-02, theo yêu cầu chủ dự án):** xóa `generated_m1/SC-GEN-02.json` và khối tương ứng trong `generate_dataset.py` (không bị sinh lại); bản sao lưu ở thư mục tạm của phiên (scratchpad `SC-GEN-02.json.bak`, mất khi phiên dọn). Bộ còn 21 kịch bản (7 BTC + 14 sinh), 30 cuộc. Chấm lại `gd2_run4` (trace vẫn gồm GEN-02, bị bỏ qua khi chấm): **TSR 72,7 → 71,4** (15/21; baseline 71,2 → 69,8), RQR/CCR/HR/TTFT không đổi; vẫn ≥ 70 và hơn baseline, nhưng biên 70% hẹp hơn (thêm 1 ca trượt là rớt). `submission/` đã cập nhật số TSR và số lượng ở các chỗ chính; **chưa rà hết** mọi chỗ nhắc "22 kịch bản/15 sinh" (README, slides, bảng lịch sử các lần chạy). Lỗi agent báo tổng hai máy cao hơn chính sách (xem trên) còn nguyên nhưng không còn ca nào đo nó.
**Sửa GEN-02 (2026-11-02, KHÔNG gọi LLM):** `total_vnd` 15.980.000 → **15.380.000** (+ `notes`) trong `generate_dataset.py` và `generated_m1/SC-GEN-02.json`. Căn cứ: `AIR-OCT` −300.000/máy (`SKU-AP-PRO`, 05–30/10) đang chạy ngày 15/10 → 2 × 7.690.000; kiểm bằng `mock_tools.order_create(qty=2, COD, on=2026-10-15)` → `cod_limit_exceeded`, `total_vnd` 15.380.000. **Giới hạn:** `AIR-2ND-50` (máy thứ 2 −50%) chỉ được tool áp khi truyền `basket_skus` (khi đó 7.990.000 + 3.995.000 = 11.985.000, vẫn > 10.000.000); với `qty=2` cùng SKU tool không áp nên chọn 15.380.000 theo tool. **Sự cố:** `generated_m1/SC-GEN-02.json` bị XÓA khỏi thư mục lúc ~18:45 (không phải do tôi; bản cũ còn ở `generated_m1_v1/`); khi chấm lại `gd2_report` chỉ còn 21 kịch bản (TSR 71,4 — số sai). Đã tạo lại đúng file này từ `generate_dataset.py` (chỉ SC-GEN-02); chấm lại `gd2_run4` đủ 22 kịch bản: TSR 72,7, RQR 2,07, CCR 52,4, HR giá/KM 0,0 (không đổi).

### 11.103b. Bước 15 GĐ2 — chạy lần 5 (2026-11-02; trần 7.000 + 7.500 như lần trước, chủ dự án duyệt "đo lại bằng LLM thật")
`runs/gd2_run5/`. **Chi phí thật: mẫu BTC 6.335,2 + sinh 7.302,9 = 13.638,1 VND** (lần 4: 11.638,9; lần này đã gồm chi phí router chính sách), không chạm trần; 0 lỗi kết nối. Chạy trực tiếp trên `BTC-Data-Vong1-TEAMS/test_set/{public_sample,generated_m1}`.
**KHÔNG so sánh thẳng với lần 4:** trong lúc chạy, thư mục `generated_m1/` đang bị sửa (file đổi 2/11 18:30–18:49, `generate_dataset.py` cũng đổi — không phải do phiên này): `SC-GEN-01` (giá cuộc 2 1.690.000 → 1.521.000), `SC-GEN-05` (giá đã báo 1.352.000, chênh biến thể 50.000 → 40.000), `SC-GEN-02` (tổng 15.980.000 → 15.380.000) — đúng 3 chỗ sự thật lệch tool ở § 11.94. **Lúc chạy `SC-GEN-02` không có trong thư mục nên báo cáo chỉ có 21 kịch bản (14 sinh), 89–91 lượt/seed**; file này được ghi lại lúc 18:49, sau khi chạy.
| Chỉ số (full) | Lần 4 (22 kịch bản) | Lần 5 (21 kịch bản, GT đã sửa một phần) | Ngưỡng |
|---|---:|---:|---|
| TSR | 72,7 ± 0,0 (baseline 71,2) | 69,8 ± 2,7 (baseline **69,8**) | ≥ 70 → CHƯA ĐẠT; hơn baseline: không |
| TSR bộ sinh | 100 ×3 | 92,9 / 100 / 100 | — |
| RQR | 2,1 ± 3,6 (baseline 12,2) | **0,0 ± 0,0** (baseline 4,8) | giảm ≥ 40% → ĐẠT |
| HR giá/KM | 6,0 ± 0,2 (baseline 33,9) | **1,9 ± 3,2** (baseline 16,1) | ≤ 5% → ĐẠT (nhưng xem dưới) |
| CCR | 52,4 | 53,6 | — |
| TTFT p95 | 6,7–7,3 s (seed sạch) | **6,5 ± 0,3 s** (6,8 / 6,2 / 6,6; trung vị 3,5–3,9 s, tối đa 9,8–11,7 s) | ≤ 3 s → CHƯA ĐẠT |
Guardrail 0 vi phạm.
**Diễn giải:** (1) HR giảm do **sửa đáp án kịch bản** (GEN-01/05 nay khớp tool), không do hệ thống tốt lên; ca còn lại: seed 2 `SAMPLE-01` cuộc 2 nói 4.890.000 (giá AirPure X) trong khi sự thật 5.200.000. (2) TSR 69,8 là do bộ kịch bản có 21 chứ không phải 22 kịch bản (mỗi kịch bản = 4,8 điểm) cộng một ca mới trượt: seed 1 `SC-GEN-15` cuộc 1 (agent mở gate bằng lời LLM nhưng không có `order.create`; lần 4 đạt 3/3 — một mẫu, chưa rõ biến thiên hay lỗi mới). TSR full bằng baseline vì cả hai cùng 100% ở bộ sinh. (3) **TTFT không còn lượt đứng 60–128 s** (tối đa 9,8–11,7 s so với 64–128 s ở lần 4): timeout + thử lại có tác dụng; p95 vẫn gấp đôi mục tiêu. (4) Chi phí tăng khoảng 17%: một phần là chi phí router nay được tính; phần còn lại chưa tách.
**Cần làm để có số chính thức:** chốt bộ kịch bản (đủ 22, GT đã sửa) rồi chạy lại một lần (≈ 13.700 VND; trần nên nâng, vd 7.500 + 8.000), sau đó cập nhật `submission/EVALUATION_REPORT.md`, `slides.html`, PLAN. Số ở các tài liệu nộp hiện vẫn là của lần 4.

### 11.104. Báo giá từng máy khi mua 2 máy cùng SKU — KM "máy thứ 2" (2026-11-02; KHÔNG gọi LLM thật)
**Vấn đề:** `pricing.get_quote(sku, qty=2)` trả MỘT giá/đơn vị và chỉ xét AIR-OCT (7.690.000); KM `AIR-2ND-50` cần `basket_skus` = máy kia, mà `_sanitize_basket` (từ SAMPLE-05) bỏ chính SKU khỏi giỏ → với 2 máy cùng SKU KM này không bao giờ hiện, agent báo 15.380.000 (cao hơn chính sách). Truyền thẳng `basket_skus=[sku]` cho `qty=2` cũng sai: mock tính giá máy 2 (3.995.000) cho CẢ hai máy → `order.create` ra 7.990.000 (thấp hơn chính sách 3.695.000) — đã kiểm bằng `mock_tools.order_create`.
**Sửa (chủ dự án chọn "tách giá từng máy"):** `Orchestrator._per_unit_quote` — với `pricing.get_quote` có `qty == 2`, không giỏ, code báo giá riêng máy 1 (không giỏ) và máy 2 (giỏ = [chính SKU]); nếu máy 2 rẻ hơn nhờ KM `percent_second_item` thì kết quả có thêm `unit_prices_vnd`, `total_vnd` (= máy 1 + máy 2), `second_unit_promos`, `note`. `final_price_vnd` giữ nguyên (đơn vị 1) vì `order.create` kiểm giá theo nó; `_sanitize_basket` và `order.create` KHÔNG đổi. Test: `tests/test_cluster_4_8.py` (+2).
**GEN-02 đặt lại 11.685.000** (theo chủ dự án): máy 1 AIR-OCT 7.690.000 + máy 2 AIR-2ND-50 3.995.000 (KM-03/04: loại không cộng dồn trên CÙNG một sản phẩm → chọn lợi nhất cho từng máy). Thay các giá trị 15.980.000 → 15.380.000 → 11.985.000 ở các ghi chú trước (11.985.000 giả định AIR-OCT không áp cho máy 1). `generated_m1/SC-GEN-02.json` có lại trong bộ (ghi chú "Xóa SC-GEN-02" ở trên bị thay thế; bộ 22 kịch bản).
**Còn hở (cần quyết):** `order.create(qty=2)` vẫn tính `total = giá đơn vị 1 × 2` = 15.380.000, KHÔNG khớp `total_vnd` 11.685.000 đã báo; ca COD > 10.000.000 nhận `cod_limit_exceeded` với `total_vnd` 15.380.000 → nếu agent đọc lại số này sẽ lệch số đã báo. Mock không có cách đặt một đơn 2 máy khác giá; chỉ tách thành hai đơn hoặc báo BTC. **Chưa chạy lại LLM thật**; `gd2_run4`/`gd2_run5` là trước sửa này (GEN-02 trong chúng sẽ bị `hr` lệch với đáp án mới ở các lượt báo 15.380.000).

### 11.105. Giá báo == giá đơn khi mua nhiều máy: `price_basket` + chốt trước `order.create` (2026-11-02; KHÔNG gọi LLM thật)
**Nguyên nhân (§ 11.104 còn hở):** `_per_unit_quote` báo tổng đúng theo chính sách (AirPure Pro ×2 ngày 15/10 = 7.690.000 + 3.995.000 = 11.685.000) nhưng `order.create(qty=2)` ghi `final_price_vnd × qty` = 15.380.000; mỗi nơi (báo giá, đọc lại đơn của order gate, hạn mức COD của backend) tự tính tiền riêng. Kiểm thêm: `order.create` KHÔNG nhận `basket_skus` ở schema BTC (`tools.schema.json` chỉ có ở `pricing.get_quote`) và `create_order`/`crm_server` của nhóm không chuyển tham số này → với giỏ nhiều SKU khác nhau backend luôn ghi giá KHÔNG có KM giỏ (đã thấy `price_mismatch`: expected 4.890.000, given 2.445.000).
**Sửa:**
- `src/harness/basket.py::price_basket(quote, lines, on, phone, address)` — NƠI DUY NHẤT tính tiền giỏ. Mỗi dòng: giá theo chính sách (báo giá có `basket_skus` = SKU khác trong giỏ) và giá backend sẽ ghi (báo giá KHÔNG giỏ × qty); `qty == 2` cùng SKU: giá máy 2 từ báo giá `basket_skus=[sku]` khi có KM loại `percent_second_item` (đọc từ kết quả tool, không tên sản phẩm). Trả `total_vnd`, `order_total_vnd`, `synced`. **`qty ≥ 3` và dòng có giỏ khác: KHÔNG áp giảm thêm** (`shortcut:` trong mã — "máy thứ 4 có giảm không?" không rõ; KM-06 đơn ≥ 3 sản phẩm cùng loại do quản lý duyệt).
- Dùng cùng hàm ở: (a) kết quả `pricing.get_quote` cho LLM (thêm `unit_prices_vnd`, `total_vnd`, `order_total_vnd`, `price_synced`, `note` khi qty ≥ 2 hoặc có giỏ; 1 máy không giỏ: như cũ); (b) tổng "đọc lại đơn" của order gate (`_gate_order_create`); (c) chốt cuối `_sync_guard` ở CẢ HAI chỗ gọi `order.create` (đường LLM và `_driver_create`), chạy cả khi order gate tắt.
- **Bất biến:** `synced=False` → KHÔNG gọi `order.create`; CODE gọi `handoff.transfer` (brief do `_complete_handoff_brief` điền, lý do ghi cả hai con số; một phiếu cho mỗi phiên+SKU+qty) và dựng câu nói an toàn chỉ có MỘT con số (`total_vnd`); chuyển máy lỗi thì câu nói không khẳng định đã chuyển.
- **COD:** hạn mức 10.000.000 tính trên `total_vnd` đúng của CẢ giỏ ở order gate (chặn trước khi hỏi địa chỉ; không tách đơn để lách); ngưỡng "COD > 2.000.000 cần gọi xác nhận" tính trên tổng giỏ (`_basket_confirm_flag`). Hạn mức/ngưỡng là hằng số `COD_LIMIT_VND`/`COD_CONFIRM_VND` (`shortcut:` — lấy từ mock_tools/VC-03, chưa có file dữ liệu). Khi đúng ≤ 10.000.000 nhưng cách tính cũ > 10.000.000 (AP-Y ×2: 7.800.000 vs 10.400.000) KHÔNG nói "vượt hạn mức COD" (đơn không tạo vì lệch giá, chuyển nhân viên).
- Gỡ `_per_unit_quote` (§ 11.104). `_sanitize_basket` giữ nguyên (SAMPLE-05).
**Test:** `tests/test_basket_sync.py` (20: `price_basket` — 2 máy, 1 máy, giày ×2, 3 máy, 2 SKU khác nhau, SKU không có KM giỏ, SKU lỗi, ngưỡng COD; luồng orchestrator — không tạo đơn + một phiếu chuyển máy + nhắc lại không lặp phiếu, 1 máy tạo đơn, giày ×2 tổng báo == tổng đơn, 3 máy báo == đơn, giỏ 2 SKU có/không KM giỏ, COD trên tổng đúng, COD không chặn nhầm theo cách cũ, COD cả giỏ, cờ xác nhận theo giỏ, `_sanitize_basket`); `tests/test_cluster_4_8.py` sửa 1 test. `tests/test_order_gate.py` sửa 1 test (COD ×2 máy lọc không khí AX40 nay có tổng đúng 9.735.000 ≤ 10.000.000 nên đi nhánh chuyển nhân viên; test chuyển sang máy lọc nước RO10, không có KM cặp). Toàn bộ: 959 test, 0 lỗi (`runs/_unittest_basket_sync.txt`; lần chạy đầu có 1 lỗi ở test_order_gate nói trên).
**Giới hạn / chưa kiểm:** chưa chạy LLM thật, chưa đo gd2 (trace `gd2_run4/5` là TRƯỚC thay đổi này). Đáp án GEN-02 = 11.685.000 là SUY từ chính sách (KM-03/04/05 + mock), BTC chưa xác nhận — không phải số chính thức. Với AirPure ×2 hệ quả là khách KHÔNG đặt được đơn ngay mà được chuyển nhân viên (TSR các ca đặt 2 máy cùng loại giảm; đúng thiết kế an toàn). `order_total_vnd` cho giỏ nhiều SKU là tổng các dòng "giá không KM giỏ". Chỉ phát hiện lệch trong phạm vi `pricing.get_quote`; không kiểm lại sau khi đơn đã tạo (backend không có lệnh tính thử).
**Đề nghị gửi BTC (không tự lách):** (1) cho `order.create` nhận `basket_skus` (mock đã nhận nhưng schema công bố không có) hoặc nhận nhiều dòng giá; (2) quy tắc AIR-2ND-50 cho qty ≥ 3 ("máy thứ 4 có giảm không?"); (3) AIR-OCT có áp cho máy 1 khi máy 2 hưởng AIR-2ND-50 không (11.685.000 hay 11.985.000); (4) xác nhận đáp án GEN-02.

### 11.106. Bước 15 GĐ2 — chạy lần 6 sau § 11.105 (2026-11-02; trần 7.000 + 7.500 như lần trước, chủ dự án duyệt "chạy LLM thật để đo lại")
`runs/gd2_run6/` (`gd2_report.md/json`; ca trượt: `_ev1.._ev3/failures.txt`). **Chi phí thật: mẫu BTC 6.212,6 + sinh 7.174,9 = 13.387,5 VND**; không chạm trần. 22 kịch bản (GEN-01, 02, 05 đã sửa đáp án), 89 lượt/seed, 1 dòng "Connection error" (đã thử lại).
| Chỉ số (full) | Lần 4 (đáp án cũ) | Lần 6 | Ngưỡng |
|---|---:|---:|---|
| TSR | 72,7 ± 0,0 (baseline 71,2) | **66,7 ± 2,7** (baseline 68,2) | ≥ 70 và hơn baseline → **CHƯA ĐẠT** |
| TSR bộ sinh | 100 ×3 | 93,3 / 86,7 / 93,3 | — |
| RQR | 2,1 (baseline 12,2) | **0,0** (baseline 7,1) | giảm ≥ 40% → ĐẠT |
| CCR | 52,4 | 53,6 | — |
| HR giá/KM | 6,0 (0,0 sau sửa đáp án) | **0,0** (baseline 23,2) | ≤ 5 → ĐẠT |
| TTFT p95 | 26.177 ms (nhiễu mạng) | **7.718 ± 672 ms** (total p95 9.505) | ≤ 3.000 → CHƯA ĐẠT |
Guardrail 0 vi phạm; 1,15 cuộc tới chốt; 2,85 lượt/cuộc.
**Ca trượt TSR so với lần 4:** (1) **SC-GEN-02 (cả 3 seed) — do thiết kế § 11.105:** kịch bản chấm `tool_called: order.create`, nhưng khi tổng đúng 11.685.000 > hạn mức COD, order gate chặn TRƯỚC khi gọi `order.create` (câu code dựng: "vượt hạn mức COD (tổng 11.685.000)… chuyển khoản") nên không có lời gọi nào để chấm. Không phải lỗi hành vi; là xung đột giữa tiêu chí chấm của kịch bản (kỳ vọng một lần THỬ order.create) và bất biến "không thử khi biết chắc sẽ sai". (2) SC-GEN-13 seed 2: LLM hỏi "chị có muốn em lên đơn không?" thay vì gọi `order.create` (biến thiên LLM đã biết, qty=1, không liên quan thay đổi mới; seed 1, 3 đạt). Mẫu BTC cố định vẫn 14,3% (order gate, § 11.31). TSR full KHÔNG hơn baseline (66,7 vs 68,2) — baseline cũng trượt GEN-02 khác nguyên nhân; không kết luận được hơn kém khi std ±2,7.
**Lỗi thật lộ ra (chưa sửa lúc đo):** GEN-02 lượt 1 — agent nói "giá sau khuyến mãi cho 2 máy là 15.380.000" trong khi kết quả `get_quote` đã có `total_vnd` 11.685.000 (LLM tự nhân giá × 2; `derived_numbers` của guardrail cho phép `a × qty`), lượt 2 code dựng câu nói 11.685.000 → hai con số khác nhau trong cùng cuộc (đúng điều yêu cầu cấm). **Sửa sau đo (§ 11.106 tiếp):** `basket.correct_basket_totals` — số `final × qty` hoặc `order_total_vnd` khác `total_vnd` trong lời nói được thay bằng `total_vnd` (chỉ một SKU, qty ≥ 2, không giỏ khác); orchestrator gọi ngay sau `_bind_price_to_product`; test `CorrectTotalsTest` (4). **CHƯA đo lại bằng LLM thật** (chạy lần 6 là TRƯỚC sửa này). Giới hạn: chỉ thay được số viết đầy đủ ("15.380.000", "15,380,000"); số làm tròn ("khoảng 15,4 triệu") không bắt được.
**Test sau sửa:** toàn bộ bộ test offline xanh (`runs/_unittest_basket_sync2.txt`).
**Chưa kiểm:** đáp án GEN-02 = 11.685.000 là suy từ chính sách (BTC chưa xác nhận); tiêu chí chấm GEN-02 (cần quyết: đổi `success_if` thành "không tạo đơn COD + nói hạn mức" hay bỏ ca); TTFT vẫn 7,7 s > 3 s (cần tối ưu riêng).

### 11.107. Sửa success_if SC-GEN-02, gộp bộ kịch bản đánh giá, sắp xếp `dataset/`, rà lỗi BTC (2026-11-04) — KHÔNG gọi LLM, chưa đo lại

**Việc làm (theo yêu cầu chủ dự án):**
1. **SC-GEN-02**: `success_if` bỏ `tool_called: order.create`, theo đúng mô tả (COD vượt hạn mức 10.000.000đ → báo/đề xuất chuyển khoản, không tạo đơn COD): `forbidden_claims` [`order_created=true`, `cod_allowed=true`] + `must_say_any` ["10 triệu", "10.000.000", "hạn mức", "chuyển khoản", "thanh toán trước"]. Không còn phụ thuộc tổng tiền. Trước đây ca này trượt 3/3 seed dù hành vi đúng (§ 12.3 mục 2) — **chưa chạy lại** nên chưa biết TSR mới.
2. **`test_set/` gộp**: `generated_m1`, `generated_m1_v1`, `custom_test_45` → `team_eval/` (42 kịch bản / 63 cuộc); `public_sample/` giữ nguyên. Bảng gộp + từng lỗi đã sửa: `BTC-Data-Vong1-TEAMS/test_set/team_eval/README.md`. Bản gốc chuyển (không xóa) sang `NotRelated/truoc_khi_sap_xep_2026-11-04/test_set/`. `custom_test_45` có hàng chục chỗ giá/ngày KM/bảo hành/giá nhập lệch `mock_tools`; mọi `order.create` kỳ vọng đã được mô phỏng bằng mock (tạo được, giá khớp) và có test `tests/test_team_eval_set.py` (5 test).
3. **`dataset/` sắp xếp** còn 4 thư mục: `frames/` (64 khung), `agent_eval/` (20 kịch bản), `asr/` (29 lời thoại sinh audio + đo ASR), `reports/` (sổ cái chi phí + bản duyệt). `frames54/` (chép trùng, D26/D28 lỗi thời) và `rules_report_after.txt` chuyển vào `NotRelated/`. Sổ cái chi phí **nguyên vẹn** (2.076,3 VND, vẫn ở `dataset/reports/generation_runs.jsonl`). Cập nhật đường dẫn trong `scripts/{generate_dataset_text,frames54_report,check_dialogue_rules,validate_scenarios,gd2_report}.py`, `tests/{_helpers,test_dataset_extra_frames}.py`; `generate_dataset.py` lưu trữ.
4. **Validator** (`src/dataset/validate.py`): nhãn `het_hang_*` không còn bị coi là "KM hết hạn"; `pii_protection` được có CCCD/STK giả; `fact_in_text` thử lại sau ITN. `scripts/scan_btc_data.py` không còn sập khi SKU không có trong catalog.
5. **BTC**: `docs/BTC_DATA_ISSUES.md` viết lại thành bảng 9 mục kèm đề xuất xử lý **chờ duyệt**. Mục mới: mock AIR-2ND-50 cho **cả hai máy giống nhau** cùng −50% (`order_create(qty=2, basket_skus=[PRO])` → 7.990.000), nên tổng đơn 2 máy có 3 đáp án (15.380.000 / 7.990.000 / 11.685.000).

**Kiểm:** bộ test offline 968 test, 0 đỏ (`runs/_unittest_team_eval_merge.txt`, nlp_env, `MCP_TRANSPORT=inproc MEMORY_TRANSPORT=local`). `validate_scenarios` trên public_sample + team_eval: 0 lỗi ở team_eval; còn SAMPLE-01 (lỗi BTC) và 1 cảnh báo SAMPLE-06.
**Chưa làm / chưa kiểm:** chưa chạy `run_eval` LLM thật trên bộ 49 kịch bản (cần duyệt trần chi phí) nên chưa có TSR mới; số lần 1–6 không so sánh được với bộ mới. `submission/` vẫn mang số lần 4.
**Lỗi hệ thống mới thấy (chưa sửa):** `RequestNormalizer` đọc "5 triệu rưỡi" (viết số) thành `5.000.000 rưỡi` (mất nửa triệu); "năm triệu rưỡi" (chữ) thì đúng.

### 11.108. Giám sát Prometheus + Grafana (2026-11-04) — KHÔNG gọi LLM; đã chạy Docker thật

**Làm:** thư mục `monitoring/` — (1) `metrics.py`: registry tự viết (counter/gauge/histogram, định dạng văn bản Prometheus, không thêm phụ thuộc) + `observe_turn(row)` tính số đo từ đúng dòng trace; (2) API: `GET /metrics`, mỗi lượt `/chat` được ghi (lỗi giám sát không làm hỏng lượt); (3) `trace_exporter.py`: phát số từ file trace `runs/gd2_run*/**` (bỏ thư mục `_merged/_ev*` để khỏi đếm đôi); (4) `docker-compose.yml` (Prometheus v2.55.1 + Grafana 11.3.1), cấu hình scrape, provisioning datasource + dashboard `harness.json` (19 panel: TTFT/Total/Call Brief p95 so ngưỡng BTC, phân rã TTFT, chi phí, tool, guardrail, order gate). Trace thêm 2 trường tùy chọn qua `monitoring_extras` (`latency_detail`, `guardrail`) ở pipeline và runner.
**Kiểm:** `tests/test_monitoring.py` (8 test): định dạng văn bản hợp lệ, histogram tích lũy, số đo từ dòng trace, `/metrics` không lộ SĐT, lỗi giám sát không phá lượt chat, exporter bỏ dòng dở dang, và **mọi số đo dashboard dùng đều do mã phát ra**. Chạy thử exporter qua HTTP trên `runs/` thật (2.379 dòng, 24 chuỗi `turns_total`). `docker compose config` hợp lệ.
**Chạy thật (2026-11-04):** `docker compose up -d` (Docker Desktop, image `prom/prometheus:v2.55.1`, `grafana/grafana:11.3.1`): Prometheus lấy được job `harness-traces` (job `harness-api` báo `down` vì lúc đó API không chạy); Grafana nạp datasource + dashboard (19 panel); cả 22 truy vấn của dashboard chạy không lỗi (các panel "máy chủ trực tiếp" rỗng đúng như dự kiến khi API không chạy); xem giao diện trong trình duyệt: số liệu hiện đủ (3.258 lượt, TTFT p95 9,84 s đỏ, Total p95 12,0 s đỏ, Call Brief 84 ms, 0 vi phạm guardrail) — là tổng mọi lần đo GĐ2 và cả hai cấu hình, lọc theo lần chạy ở bộ lọc phía trên. **Lưu ý:** tiến trình phải nghe `0.0.0.0` (không phải 127.0.0.1) thì container mới lấy được số — đã ghi vào README/compose.
**Chưa làm / chưa kiểm:** chưa chạy luồng `harness-api` với lượt chat thật (cần khóa API hợp lệ hoặc nhánh dự phòng); không có Alertmanager; registry nằm trong tiến trình (API một worker).
**Quan sát từ trace GĐ2 lần 6 (để giảm TTFT):** chờ token đầu của vòng LLM cuối chỉ ≈ 1 s (p50) trong khi TTFT trung vị ≈ 4 s ⇒ phần lớn TTFT nằm ở các bước TRƯỚC vòng cuối (đọc ý khách bằng LLM, vòng LLM chọn tool, tool).

## 13. Hợp đồng tool BTC 11/2026 + lần đo cả bộ (2026-11-11)

**Thay đổi của BTC đã áp dụng:** `pricing.quote_order(lines)` (giá từng máy; AIR-2ND-50 đúng một máy/đơn), `order.create(lines=[{sku,qty,price_vnd}])` một đơn nhiều dòng, `sku` tùy chọn; `reference_eval.py` chấm theo từng dòng. Mã: `src/harness/basket.py` (`price_basket`, `order_args`), `orchestrator.py` (bỏ `_sync_guard`/`_sync_block`, thêm `_order_basket`, `_main_from_lines`, `_basket_in_play`), 2 MCP server, gateway, quyền, PII vault, runner (`call_1..call_9`, khách mô phỏng chỉ nói khi hết lời kịch bản). **979 test xanh** (`runs/_unittest_btc_update_after.txt`).

**Bộ kịch bản:** 7 mẫu BTC + `team_eval/` 270 (15 SC-GEN, 20 SC-TV, 15 SC-ULTRA, 220 TEST) = 277. Đã sửa đáp án TEST-189, TEST-13.

**Lần đo** (`runs/m1_final/`, gpt-4o-mini, 1 seed 42, 2 cấu hình, MCP stdio; `team_eval` có `--gate-assist`, 7 mẫu BTC không có vì lời khách cố định). Chấm bằng `reference_eval.py` mới: `python scripts/m1_final_report.py --root runs/m1_final` → `report.json`, `report.md`.

| Chỉ số | Baseline | Hệ thống |
|---|---|---|
| Repeat-Question Rate | 4,1% | 1,6% |
| Context Carryover Rate | 10,3% | 57,2% |
| Task Success Rate | 66,1% (183/277) | 76,5% (212/277) |
| Hallucination giá & KM | 19,1% | 16,3% |
| Số lượt TB / cuộc | 2,7 | 2,68 |
| Vi phạm guardrail (ca) | 7 | 8 |
| TTFT p50 / p95 (1.218 lượt) | — | 4,4 s / 7,6 s |

TSR theo nhóm (full / baseline): SAMPLE 1/7 / 1/7 · SC-GEN 13/15 / 12/15 · SC-TV 18/20 / 14/20 · SC-ULTRA 10/15 / 6/15 · TEST 170/220 / 150/220.

**Chi phí thật:** mẫu 2.251,8 + ba luồng 22.520,0 + 22.361,6 + 21.846,3 = 68.979,7 VND; cộng 2 lần chạy thử 2.629 = **71.609 VND** (trần duyệt 90.000). Không chạm trần.

**Chưa đạt / chưa làm:** (1) 7 mẫu BTC 1/7 — order gate hỏi địa chỉ + hình thức thanh toán mà lời khách cố định không trả lời tiếp (SAMPLE-01: khách nói "giao về địa chỉ cũ" vẫn bị hỏi lại địa chỉ); (2) 28 cuộc không có `order.create` khớp, 21 thiếu `must_say_any` (lịch nghỉ lễ 27/10, hạn đổi 7 ngày, phụ kiện tiêu hao), 9 handoff thiếu trường, 4 ca mẫu cấm "giá nhập/giá sàn" (agent lặp lại chữ của khách khi từ chối); (3) guardrail full 8 > baseline 7; (4) TTFT p95 7,6 s (mục tiêu ≤ 3 s); (5) `submission/` vẫn mang số lần 4; (6) chỉ 1 seed nên chưa có ± std.

### 13.1 Lượt chốt theo luật BTC (2026-11-11)

BTC trả lời: mỗi cuộc gọi được thêm MỘT lượt agent sau lượt khách cuối (`customer_text` rỗng) để đọc lại đơn và gọi `order.create`. Đã làm: `runner.py` chèn lượt đó khi `orchestrator.has_open_order()` (lượt khách cuối kết thúc bằng câu hỏi/xác nhận/đọc lại của order gate); `process_turn(closing=True)` → `_closing_driver` tạo đơn nháp bằng code, không gọi LLM; `OrderGate.evaluate` nhánh `closing`: dùng thông tin đã lưu, thanh toán chưa nói = COD, **thiếu địa chỉ/tên vẫn tạo đơn** và báo nhân viên gọi lại xác nhận (CRM của BTC không có địa chỉ cho khách mẫu, đáp án BTC chỉ đòi sku + giá); vẫn không tạo khi chưa rõ size/màu hoặc COD vượt hạn mức. `closing` chỉ do bộ chạy đánh giá bật, API/UI không đổi. Test: `tests/test_closing_turn.py` (3); cả bộ **982 xanh** (`runs/_unittest_closing_turn.txt`).

**Đo lại 7 mẫu BTC** (`runs/m1_closing/`, 1 seed, không khách mô phỏng, 2.285,6 VND): TSR **7/7** (baseline 4/7; trước đó 1/7 và 1/7) · CCR 57,1 vs 4,8 · hallucination 11,1 vs 44,4 · guardrail 0 vs 0 · số lượt/cuộc 3,54 vs 3,46 · **RQR 8,0 vs 4,2 (kém baseline)** · TTFT p95 6,8 s (46 lượt). Tổng chi tới nay 73.895 VND.

Chưa làm: đo lại `team_eval` (270) theo luật một lượt chốt thay cho khách mô phỏng; xem vì sao RQR full cao hơn baseline; `submission/`.

### 13.2 Nhóm việc không tốn LLM (2026-11-11)

- **Trần chi phí mặc định của `run_eval.py`: 1.500 → 20.000 VND.** Lệnh chuẩn của BTC không truyền `--max-cost-vnd`; bộ ẩn 41 kịch bản (≈ 170 lượt × ~34 VND × 2 cấu hình ≈ 12.000 VND) sẽ bị cắt ngang ở trần cũ.
- **Hallucination giá/KM — nguyên nhân chính là gán nhãn claim, không phải bịa giá.** Bộ trích lấy "sản phẩm đứng đầu `product.shortlist`" làm chủ đề dù cuộc gọi đang bàn sản phẩm khác (SAMPLE-06) → giá mẫu gợi ý thêm bị ghi `price_vnd`. Sửa: `extract_claims(..., focus_sku=)` nhận sản phẩm đang bàn từ các lượt trước. Chấm lại trace cũ bằng bộ trích mới (không gọi LLM): 7 mẫu BTC **11,1% → 0,0%** (0/8); `team_eval` 16,3% → 15,4% (28/182).
- **28 claim sai còn lại của `team_eval`:** 25 là giá ĐÚNG theo kết quả tool nhưng của sản phẩm khác sản phẩm trong đáp án — kịch bản dạng "khách hỏi A rồi chuyển sang B", `ground_truth_facts.price_vnd` là giá của B, agent báo đúng giá A ở lượt 1 (TEST-100, 128, 166, 216, 72…). 3 ca không khớp tool: TEST-02 (giá size 43 có phụ thu), TEST-181 (LLM tự nhân 2 × giá, bị gán `price_vnd`), TEST-84 (ngưỡng freeship 2.000.000 bị gán `price_vnd`). Chưa sửa đáp án/kịch bản (dữ liệu của nhóm, chờ quyết định).
- **RQR 7 mẫu BTC (2/25):** cả hai câu thừa ở SAMPLE-03 cuộc 2 — khách đồng ý ĐỔI size ("ừ em làm thủ tục đổi") nhưng cổng mở đơn bằng code hiểu là chốt MUA, mở đơn nháp thứ hai rồi hỏi địa chỉ/màu. Sửa: `_maybe_open_gate` thêm loại trừ `order_updated_in_call`; lượt chốt không tạo được đơn thì không hỏi nữa (nói rõ đơn chưa tạo). Chưa đo lại bằng LLM thật.
- Test: `tests/test_closing_turn.py` thêm 1 test + 1 kiểm; cả bộ **983 xanh** (`runs/_unittest_free_fixes.txt`).

### 13.3 Kiểm 26 claim giá, sửa claim sai, Knowledge Gap Loop (2026-11-11)

- **Kiểm 26 claim giá/KM bị tính sai của `team_eval`** (sau khi sửa bộ trích; đối chiếu từng claim với `mock_tools.pricing_get_quote` đúng ngày gọi, kết quả `runs/m1_final/hr_price_check.json`): 23 = giá `final` đúng của sản phẩm KHÁC sản phẩm đáp án; 1 = giá đúng của biến thể khác (TEST-02, size 43 có phụ thu); 1 = giá đúng của máy thứ hai sau AIR-2ND-50 (TEST-49); **1 sai thật** (TEST-184: báo giá niêm yết 7.990.000 của mẫu đang giảm còn 7.690.000). Tức 25/26 là agent đúng; script BTC so mọi claim `price_vnd` của cuộc gọi với MỘT giá đáp án. Thư hỏi BTC: `docs/BAO_CAO_HR_GUI_BTC.md`.
- **Sửa:** (a) `product.shortlist` gắn `final_price_vnd` (giá sau KM của ngày gọi) cho từng mẫu + dặn báo theo giá này (TEST-184); (b) bộ trích: "tổng giá …" là `total_vnd` (TEST-181), ngưỡng điều kiện "đơn từ 2.000.000đ trở lên" không phải giá (TEST-84 — câu của agent đúng theo [VC-02]), giá mẫu khác chủ đề thành `alt_price_vnd` cả khi số đó có trong kết quả tool. Chấm lại trace cũ: `team_eval` HR giá/KM 16,3% → **14,4%** (26/180); chỉ tính claim khác giá mock: 1/180 = 0,6%. (a) cần chạy lại LLM mới thấy.
- **Knowledge Gap Loop (C.5):** `scripts/knowledge_gap.py collect|apply` + `data/knowledge_gaps.json` + bộ nạp chính sách đọc thêm `data/kb_supplement/` + kịch bản hồi quy `test_set/knowledge_gap/KG-nn.json`. Chỉ mục có người đổi `status: approved` mới vào kho. Vòng 0 (trace `m1_final` + `m1_closing`, 1.264 lượt): **9 thiếu sót chờ duyệt** (lắp đặt máy lọc nước, tiết kiệm điện, PUMP-GIFT, GIFT-FILTER, NAM-SHIP0…; "giá sàn đại lý", "hoa hồng nội bộ" phải từ chối). Chưa có mục nào được duyệt, chưa đo vòng 1. Hai nguồn feedback dùng: điểm tự động của bộ chấm + câu khách hỏi không trả lời được.
- Test: `tests/test_knowledge_gap.py` (2); cả bộ **985 xanh** (`runs/_unittest_kg.txt`). `test_pipeline_lifecycle…sweeper` đỏ 1 lần trong 1 lần chạy cả bộ, xanh 3/3 khi chạy riêng (test phụ thuộc thời gian).

### 13.4 Đo lại cả bộ theo luật một lượt chốt (2026-11-11) — `runs/m1_final2/`

277 kịch bản (7 mẫu BTC + 270 `team_eval`), gpt-4o-mini, 1 seed 42, 2 cấu hình, MCP stdio, **không khách mô phỏng**; lượt chốt chỉ thêm khi order gate đang mở. Chấm: `python scripts/m1_final_report.py --root runs/m1_final2`.

| Chỉ số | Baseline | Hệ thống | Ngưỡng đề |
|---|---|---|---|
| Repeat-Question Rate | 4,7% | 3,3% (−30%) | giảm ≥ 40% ✗ |
| Context Carryover Rate | 10,7% | 57,2% | — |
| Task Success Rate | 66,8% (185/277) | **76,5% (212/277)** | ≥ 70% ✓ |
| TSR ca khó | — | 75,0% | — |
| Hallucination giá & KM | 22,3% | 14,6% | ≤ 5% ✗ (xem § 13.3: 25/26 claim là giá đúng của sản phẩm khác đáp án) |
| Số lượt TB / cuộc | 2,4 | 2,38 | — |
| Vi phạm guardrail | 6 | 10 (5 chuyển máy thừa + 5 mẫu cấm) | ✗ kém baseline |
| TTFT p50 / p95 (1.084 lượt) | — | 4,5 s / 7,5 s | ≤ 3 s ✗ |
| Total p95 | — | 8,9 s | ≤ 8 s ✗ |
| Call Brief p95 | — | 47 ms | ≤ 5 s ✓ |

TSR theo nhóm (full / baseline): SAMPLE 6/7 / 5/7 · SC-GEN 13/15 / 13/15 · SC-TV 18/20 / 14/20 · SC-ULTRA 10/15 / 6/15 · TEST 165/220 / 147/220.
Lý do trượt (full, theo cuộc gọi): 24 thiếu `must_say_any` · 21 không có `order.create` khớp · 8 handoff thiếu trường · 5 không có `order.update` · 5 mẫu cấm nội bộ · 2 không chuyển máy · 1 gọi tool cấm.
**Chi phí:** 2.237,3 + 20.445,0 + 20.311,3 + 20.397,0 = 63.390,6 VND; kiểm chứng sau sửa 4.014,7 + 450,7. Tổng trong trần 75.000: **67.856 VND**. Tổng dự án tới nay ≈ 141.750 VND.

**Lỗi tìm thấy từ lần đo này và đã sửa SAU khi đo (số ở bảng trên CHƯA gồm các sửa này):**
1. **Lượt chốt tạo đơn khi khách nói "khoan chốt… vội" (TEST-198)** — hậu quả của việc bỏ bước xác nhận. Thêm `reply_reader.authorize_closing`: lớp LLM độc lập đọc toàn bộ lời khách của cuộc gọi, phải có trích dẫn nguyên văn yêu cầu đặt đơn mới cho tạo; không LLM/lỗi → không tạo.
2. **Khách đồng ý ĐỔI size bị hiểu là chốt MUA** (SAMPLE-03, TEST-40 cuộc 2): code mở đơn nháp, LLM mất lượt gọi `order.update`. Sửa: `_maybe_open_gate` không tự mở khi khách đã có đơn đúng sản phẩm đó (`existing_order_same_product`) hoặc vừa `order.update` xong; prompt bộ đọc nói rõ commit = mua đơn MỚI.
3. **Hẹn gọi lại "Tết Dương lịch 01/01" bị điền năm đã qua** (2026-01-01 khi gọi ngày 15/10) → tool không dời lịch, agent không báo nghỉ lễ (5 ca thiếu "nghỉ | 27/10 | 02/01"). Sửa: `_future_callback` chuyển ngày đã qua sang lần kế tiếp.
4. Lượt chốt không tạo được đơn thì không hỏi thêm.

**Kiểm chứng LLM thật sau sửa:** 14 kịch bản (`runs/m1_check/`): 11/14 (trước sửa 10/14), TEST-198 không còn tạo đơn, hallucination giá 0,0%, guardrail 0; 3 kịch bản (`runs/m1_check2/`: SAMPLE-03, TEST-40, TEST-103) **3/3**, RQR 0. Test: **987 xanh** (`runs/_unittest_final3.txt`).

### 13.5 Hồ sơ nộp (2026-11-11, dở dang do hết hạn mức phiên làm việc)

- Đã cập nhật theo số `runs/m1_final2`: `submission/EVALUATION_REPORT.md` (bảng A.6, trước/sau, 12 ca sai), `README.md` (lệnh chuẩn BTC, hạn chế), `DATASET.md` (277 kịch bản/455 cuộc/908 lượt, phân bố), `ARCHITECTURE.md` (danh sách tool, lượt chốt, Knowledge Gap Loop).
- Sửa thêm: phiếu chuyển máy bù trường `null` + lấy sản phẩm khách nêu từ catalog (8 ca "handoff brief thiếu trường"); 987 test xanh (`runs/_unittest_handoff.txt`); chưa đo lại bằng LLM.
- **Chưa làm:** `DEMO_SCRIPT.md` và `slides.html` (còn số cũ); rà § 10 cơ sở dữ liệu; giao diện OpenUI; tạo repo git; video.
