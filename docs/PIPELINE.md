# PIPELINE.md — kiến trúc runtime thực tế (cập nhật 2026-10-27)

> Thay cho `backup_2026-10-21/PIPELINE.md` (mô tả TRƯỚC các bản sửa, còn gọi "A2A" và gateway giả). Mọi mục dưới đây đối chiếu được với mã; chỗ chưa làm ghi ở cuối. Nhật ký: [CHECKING.md § 11](../CHECKING.md) · kế hoạch: [PLAN.md](PLAN.md).

## 1. Luồng một lượt (`pipeline.py::CallCenterHarnessPipeline._process`)

```
Khách (hotline / Zalo / Fanpage / audio) ──► ① RequestNormalizer ──► ② IdentityResolver ──► ③ CallBriefBuilder
                                                                                              │
        ⑦ TurnTracer (JSONL) ◄── ⑥ GuardrailAndFallback ◄── ⑤ order gate ◄── ④ HarnessOrchestrator (LLM + tool)
```

| # | Thành phần | File | Việc làm |
|---|---|---|---|
| ① | RequestNormalizer | `src/channels/normalizer.py` | sửa lỗi ASR/teencode, ITN (số tiền, SĐT, ngày), **che PII** (token `<PHONE_n>`, `<ADDR_n>`, `<ID_n>`; bảng token chỉ trong bộ nhớ tiến trình) |
| ② | IdentityResolver | `src/identity/` | nhận diện khách theo SĐT/Zalo/FB qua `mcp-crm`; nối định danh nhiều kênh; SĐT dùng chung → bước xác minh |
| ③ | CallBriefBuilder | `src/harness/call_brief.py` | gom hồ sơ + lịch sử + lịch sử kênh → `must_not_ask`, `must_carry_over`, câu mở đầu tiếp nối |
| ④ | HarnessOrchestrator | `src/harness/orchestrator.py` | gọi LLM (function-calling, ≤ 6 vòng) với system prompt tĩnh + Call Brief; tool chạy qua MCP; sửa SKU 4 tầng; chống gọi lặp tool ghi; ghi nhớ sản phẩm đúng |
| ⑤ | **Order gate** (luôn bật) | `src/harness/order_gate.py` | trước `order.create`: kiểm checklist (sản phẩm/biến thể, số lượng, tên & SĐT nhận, địa chỉ, thanh toán) → hỏi/xác nhận → ĐỌC LẠI ĐƠN → chỉ tạo đơn khi lượt sau khách đồng ý rõ ràng |
| ⑥ | GuardrailAndFallback | `src/harness/guardrail.py` | số tiền/phí trong lời agent phải có trong kết quả tool; chặn "đã lên đơn" khi chưa gọi tool; **lời báo hết hàng phải khớp `inventory.check`** (mới); chặn lộ giá vốn, tự nhận người thật; che CCCD/số tài khoản |
| ⑦ | TurnTracer | `src/tracing/tracer.py` | ghi trace theo schema BTC: latency đo thật (`perf_counter`, TTFT từ stream), `claims`/`questions` do `src/harness/extractor.py` trích từ câu khách nghe, `memory_writes`, `order_gate`, `llm_cost` |

Sau lượt: `commit_turn` chốt giao dịch bộ nhớ. Cuộc gọi kết thúc (nút UI, timeout, chuyển máy) → `CallFinalizer` ghi episode và chạy bộ trích slot khó bằng LLM (≤ 1 lần mỗi thời điểm kích hoạt; baseline không chạy).

## 2. Ba MCP server thật (`mcp_servers/`, SDK `mcp` — `MCPServer`, giao thức MCP qua stdio)

| Server | Tool | Quyền |
|---|---|---|
| `mcp-catalog` | `catalog.search`, `inventory.check`, `pricing.get_quote`, `product.shortlist` | chỉ đọc |
| `mcp-crm` | `crm.get_customer`, `order.*`, `schedule.callback`, `handoff.transfer` | tool ghi chỉ cho lõi điều phối |
| **`mcp-memory`** | 19 tool `memory.*` (giao dịch theo lượt, working/episodic/profile, chính sách, liên kết định danh, xóa khách) | **nơi ghi duy nhất** của bộ nhớ khách; phân quyền theo caller ở `config/mcp_permissions.json` (mặc định từ chối) |

Vận chuyển bộ nhớ: `MEMORY_TRANSPORT=stdio` (mặc định của app) | `inproc` | `local` (mặc định của test). Kết quả tool được lọc mọi field bắt đầu bằng `_` (giá sàn nội bộ) trước khi tới LLM/trace.

## 3. Bộ nhớ 4 tầng (`src/memory/`)

Working (theo phiên) · Profile (fact có TTL, supersede, provenance `source_call/turn/channel`) · Episodic (tóm tắt cuộc gọi) · Semantic KB (99 chunk chính sách, TF-IDF, lọc ngày + public). SQLite `data/harness_memory.db` (WAL, giao dịch theo lượt, UNIQUE, xóa khách trọn vẹn). Slot dễ → regex mỗi lượt (không LLM); slot khó → LLM ở 3 thời điểm.

## 4. Nhánh dự phòng khi mất LLM

Khi không có khóa/hết credit/lỗi API (và chưa có tool ghi nào chạy), orchestrator rơi về nhánh rule-based **tối giản**: báo giá bằng `pricing.get_quote`, nêu tên sản phẩm lấy từ catalog (không nói mã SKU thô), chỉ nhắc quà tặng/thông số có trong catalog hoặc kết quả tool, và vẫn đi qua order gate + guardrail. Đây KHÔNG phải chế độ được chấm. Nếu lỗi xảy ra sau khi đã có tool ghi chạy thì trả lời an toàn dựa trên tool đã chạy, không chạy nhánh này (tránh tạo đơn trùng). Module `src/agents/specialists.py` (tên "A2A" là lịch sử) **chạy trong cùng tiến trình, không dùng giao thức Agent-to-Agent**; chỉ phục vụ nhánh này.

## 5. Đánh giá, ASR, giao diện

- `run_eval.py --scenarios --config full|baseline_no_memory|both --out-dir --seed --repeats [--gate-assist] --max-cost-vnd` (trần chi phí cứng luôn bật, gồm cả chi phí router chính sách) → `BTC-Data-Vong1-TEAMS/eval/reference_eval.py`; `scripts/gd2_report.py` gộp 7 mẫu BTC + 15 kịch bản sinh, mean ± std theo seed. Chấm lại từ trace không tốn LLM: `python -m evaluation --trace …`.
- ASR local: Gipformer 1.5 68M (mặc định) / faster-whisper (dự phòng), VAD Silero + năng lượng — xem README mục ASR.
- **Backend API** (`api/`, bước 17) và **giao diện web** (`ui/index.html`, bước 18, phục vụ cùng origin): `python scripts/run_demo.py` → `http://127.0.0.1:8000/` (Call Brief, dòng thời gian bộ nhớ, nhật ký tool, đơn hàng, ASR). Streamlit `ui_app.py` còn dùng làm trang quản trị.
- Dataset: `src/dataset/`, `scripts/generate_dataset_text.py` (trần tích lũy 10.000 VND bằng mã) — đang tạm dừng.

## 6. Chưa làm / hạn chế (đối chiếu PLAN.md)

- Số đo chính thức: bước 15 giai đoạn 2 (CHECKING § 11.87–11.95). Chưa đạt: HR giá/KM ≤ 5 % (phần còn lại là sự thật kịch bản lệch tool), TTFT p95 ≤ 3 s.
- Order gate nằm trong orchestrator, chưa ở `mcp-crm` (gọi thẳng MCP vẫn tạo được đơn, chỉ bị chặn bởi phân quyền caller).
- API một worker: phiên đồng thời xen kẽ theo lượt (khóa pipeline); kho phiên trong RAM.
- Router chính sách (bước 11): chi phí/độ trễ vào trace (`policy_route`) và trần chi phí; chưa cải thiện truy hồi multi-hop và từ chối câu ngoài tài liệu (đo ở § 11.82).
- Chưa có LLM-judge (14b), chưa làm vòng cải tiến/ASR ≥ 20 file (16, 16a GĐ2). Giao diện dựng tay, không sinh bằng W&B OpenUI.
- `src/eval/{evaluator,simulator,human_gate,improvement}.py` (dead code) đã gỡ ở 14a; chấm lại từ trace do package `evaluation/` (process riêng).
