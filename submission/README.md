# Harness Agent Call Center E-commerce (Telesale) — Sudo Code 2026, Vòng 1

Agent hỗ trợ nhân viên telesale: nhớ khách qua nhiều cuộc gọi và nhiều kênh (hotline / Zalo / Fanpage), không hỏi lại điều khách đã nói,
báo giá/khuyến mãi bằng số liệu tool thật, chỉ tạo đơn khi khách đã đồng ý rõ ràng.

Bộ hồ sơ nộp (thư mục `submission/`):

| Tài liệu | Nội dung |
|---|---|
| [README.md](README.md) | file này: cài đặt, chạy, cấu trúc mã |
| [ARCHITECTURE.md](ARCHITECTURE.md) | sơ đồ hệ thống, vòng lặp harness, vì sao MCP / không A2A |
| [DATASET.md](DATASET.md) | dataset: cách sinh, phân bố, hạn chế, xử lý thông tin cá nhân |
| [EVALUATION_REPORT.md](EVALUATION_REPORT.md) | bảng chỉ số, so baseline, trước/sau cải tiến, 12 ca hệ thống làm sai, chi phí, tác động kinh doanh |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | kịch bản video demo 5–8 phút (2 cuộc gọi cùng một khách) |
| [slides.html](slides.html) | 15 slide (mở bằng trình duyệt, ←/→ để chuyển, in ra PDF được) |

> **Trung thực về phạm vi:** số liệu chính thức là lần đo 2026-11-11 trên 277 kịch bản (7 mẫu BTC + 270 của nhóm), 2 cấu hình, **1 seed**
> (`runs/m1_final2/`). Chưa đạt: Hallucination giá ≤ 5 % (theo script), RQR giảm ≥ 40 %, TTFT p95 ≤ 3 s, guardrail. Audio/ASR mới có 4 file TTS;
> chưa có LLM-judge; **video demo chưa quay**. Mục 6 nêu đủ.

## 1. Cài đặt

```bash
conda activate nlp_env              # Python 3.12
pip install -r requirements.txt
cp .env.example .env                # điền OPENAI_API_KEY (không đưa .env vào gói nộp)
python -m unittest discover -s tests -t .      # 900+ test offline, không gọi LLM thật
```

ASR chạy local (không tốn API): tải model theo mục "ASR" của [README gốc](../README.md) (`model_ASR/`, ≈ 73 MB; gói nộp có kèm model).

## 2. Chạy giao diện demo (không cần khóa API)

```bash
python scripts/run_demo.py --reset      # seed khách demo Hoa (đã có cuộc 1 ngày 15/10) → http://127.0.0.1:8000/
```

Mở `http://127.0.0.1:8000/`: khung hội thoại, **Call Brief** hiện ngay khi mở cuộc gọi, **dòng thời gian bộ nhớ**, nhật ký tool, đơn hàng,
nhận dạng giọng nói từ file `.wav/.mp3`. Không có `OPENAI_API_KEY` → nhánh dự phòng rule-based (giao diện vẫn chạy, câu trả lời tối giản).
Có khóa → agent LLM đầy đủ. Dùng DB riêng `data/demo.db`, không đụng DB thật.

Cùng máy chủ cung cấp REST API (`/docs`): `POST /sessions`, `POST /chat`, `GET /call-brief`, `/memory/timeline`, `/tools/log`, `/orders`, `POST /asr`.

## 3. Chạy đánh giá bằng một lệnh

```bash
# Lệnh chuẩn BTC — một cấu hình, một file trace (thay <dir> bằng thư mục kịch bản, kể cả bộ ẩn)
python run_eval.py --scenarios <dir> --config full --out full.jsonl
python run_eval.py --scenarios <dir> --config baseline_no_memory --out baseline.jsonl
python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --scenarios <dir> --trace full.jsonl --baseline baseline.jsonl

# Hoặc cả hai cấu hình + in bảng A.6 bằng một lệnh
python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/public_sample --config both --out-dir runs/my/sample --seed 42

# Tái lập số trong báo cáo (277 kịch bản; ≈ 63.000 VND với gpt-4o-mini): chạy public_sample và team_eval vào runs/my/{sample,s1}, rồi gộp + chấm
python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/team_eval --config both --out-dir runs/my/s1 --seed 42 --no-report --max-cost-vnd 70000
python scripts/m1_final_report.py --root runs/my
```

Theo hướng dẫn của BTC (11/2026), sau lượt khách cuối của mỗi cuộc gọi agent được một lượt chốt (`customer_text` rỗng trong trace) để đọc lại đơn và gọi
`order.create`; bộ chạy tự thêm lượt này khi đơn đang chờ. `tool_calls[].result` luôn được ghi vào trace.

`--max-cost-vnd` là trần cứng (mặc định 20.000 VND; kiểm trước mỗi lần gọi API, gồm cả router chính sách); chạm trần thì dừng và giữ trace đã chạy.
Chấm lại từ trace không tốn LLM: `python -m evaluation --trace runs/my/sample/full.jsonl`.

Khởi tạo dữ liệu: catalog/chính sách/CRM đọc thẳng từ `BTC-Data-Vong1-TEAMS/`; `python scripts/seed_demo_db.py` (hoặc `run_demo.py --reset`) tạo DB demo `data/demo.db`.
Vòng cải tiến (Knowledge Gap Loop): `python scripts/knowledge_gap.py collect --trace <trace>` → người duyệt `data/knowledge_gaps.json` → `python scripts/knowledge_gap.py apply`.

## 4. Cấu trúc mã

```
pipeline.py            một lượt: chuẩn hóa → nhận diện → Call Brief → điều phối (LLM + tool) → guardrail → trace
src/channels/          RequestNormalizer (ITN, che PII), ASR (Gipformer / whisper)
src/identity/          nhận diện khách đa kênh qua mcp-crm
src/harness/           CallBriefBuilder, orchestrator, order gate, guardrail, reply reader, extractor claims/questions
src/memory/            4 tầng nhớ (working / profile có TTL / episodic / chính sách + router), client MCP
mcp_servers/           3 MCP server thật: mcp-catalog, mcp-crm, mcp-memory (nơi ghi duy nhất)
api/  ui/              FastAPI (bước 17) + giao diện web một trang (bước 18)
evaluation/            chấm lại từ trace bằng reference_eval của BTC (process riêng, không import pipeline)
scripts/               run_eval phụ trợ, gd2_report, run_demo, seed_demo_db, package_submission, eval_policy_router…
tests/                 bộ test offline
monitoring/            Prometheus + Grafana: /metrics của API, exporter trace, dashboard (docker compose)
docs/ CHECKING.md      kế hoạch, nhật ký từng bước (số liệu, lỗi, quyết định)
```

## 5. Đóng gói nộp

```bash
python scripts/package_submission.py        # ../Code_submission.zip; loại .env và backup_*/, quét chuỗi giống khóa API (thoát mã 1 và xóa gói nếu thấy)
```

## 6. Chưa làm / hạn chế đã biết

- **Chỉ số chưa đạt ngưỡng** (lần đo 277 kịch bản): Hallucination giá & KM 14,6 % theo script (≤ 5 %; 25/26 claim bị tính sai là giá đúng của sản phẩm khác đáp án — xem báo cáo mục 4); RQR giảm 30 % (≥ 40 %); TTFT p95 7,5 s (≤ 3 s); Total p95 8,9 s (≤ 8 s); guardrail 10 ca so với baseline 6.
- **Một seed**, chưa có độ lệch chuẩn. Sáu sửa lỗi sau lần đo mới kiểm trên 17 kịch bản, chưa đo lại cả bộ.
- **Audio / ASR**: 4 file TTS giọng Bắc (≈ 2,5 phút) so với ≥ 40 cuộc / ≥ 1 giờ; WER chưa đo trên ≥ 20 file. Chi tiết: [DATASET.md](DATASET.md).
- **Vòng cải tiến**: Knowledge Gap Loop đã có mã và 9 thiếu sót vòng 0; chưa có mục nào được người duyệt nên chưa có số vòng 1.
- Chưa có LLM-judge 12 tiêu chí và chưa điền file chấm tay 20 lượt.
- Chưa quay video demo; slide ở dạng HTML (in ra PDF từ trình duyệt).
- Order gate nằm trong orchestrator, chưa ở `mcp-crm`; API chạy MỘT worker, phiên đồng thời xen kẽ theo lượt.
