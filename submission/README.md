# Harness Agent Call Center E-commerce (Telesale) — Sudo Code 2026, Vòng 1

Agent hỗ trợ nhân viên telesale: nhớ khách qua nhiều cuộc gọi và nhiều kênh (hotline / Zalo / Fanpage), không hỏi lại điều khách đã nói,
báo giá/khuyến mãi bằng số liệu tool thật, chỉ tạo đơn khi khách đã đồng ý rõ ràng.

Bộ hồ sơ nộp (thư mục `submission/`):

| Tài liệu | Nội dung |
|---|---|
| [README.md](README.md) | file này: cài đặt, chạy, cấu trúc mã |
| [ARCHITECTURE.md](ARCHITECTURE.md) | sơ đồ hệ thống, vòng lặp harness, vì sao MCP / không A2A |
| [DATASET.md](DATASET.md) | dataset: cách sinh, phân bố, hạn chế, xử lý thông tin cá nhân |
| [EVALUATION_REPORT.md](EVALUATION_REPORT.md) | bảng chỉ số, so baseline, trước/sau cải tiến, 14 ca hệ thống làm sai, chi phí, tác động kinh doanh |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | kịch bản video demo 5–8 phút (2 cuộc gọi cùng một khách) |
| [slides.html](slides.html) | 15 slide (mở bằng trình duyệt, ←/→ để chuyển, in ra PDF được) |

> **Trung thực về phạm vi:** số liệu chính thức là bước 15 giai đoạn 2 (22 kịch bản, 3 seed, 1 mẫu mỗi seed). Dataset mới đạt khoảng một phần tư ngưỡng
> bảng C.1; ASR mới đo trên 4 file TTS; chưa có LLM-judge (bước 14b); **video demo chưa quay** (chỉ có kịch bản). Mục "Chưa làm" ở cuối nêu đủ.

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
# mẫu BTC cố định (7 kịch bản) — baseline và hệ thống, 3 seed, trần chi phí cứng
python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/public_sample --config both --out-dir runs/my/sample --seed 42 --repeats 3 --max-cost-vnd 7000
# bộ sinh (15 kịch bản) — khách mô phỏng trả lời order gate
python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/generated_m1 --config both --out-dir runs/my/gen --seed 42 --repeats 3 --gate-assist --max-cost-vnd 7500
# báo cáo 5 chỉ số, mean ± std qua seed, đối chiếu ngưỡng
python scripts/gd2_report.py --root runs/my
```

`--max-cost-vnd` là trần cứng (kiểm trước mỗi lần gọi API, gồm cả router chính sách); chạm trần thì dừng và giữ trace đã chạy.
Chấm lại từ trace không tốn LLM: `python -m evaluation --trace runs/my/sample/full.r1.jsonl`.

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
docs/ CHECKING.md      kế hoạch, nhật ký từng bước (số liệu, lỗi, quyết định)
```

## 5. Đóng gói nộp

```bash
python scripts/package_submission.py        # ../Code_submission.zip; loại .env và backup_*/, quét chuỗi giống khóa API (thoát mã 1 và xóa gói nếu thấy)
```

## 6. Chưa làm / hạn chế đã biết

- **Dataset** 31 cuộc / 22 kịch bản so với ngưỡng ≥ 120 cuộc; audio 4 file (≈ 2,5 phút) so với ≥ 40 cuộc / ≥ 1 giờ. Chi tiết: [DATASET.md](DATASET.md).
- **ASR**: WER chỉ đo trên 4 file TTS sạch giọng Bắc; chưa có số riêng cho số tiền/SĐT trên ≥ 20 file.
- **Chỉ số chưa đạt ngưỡng:** HR giá/KM 6,0% (ngưỡng ≤ 5%; phần còn lại là sự thật kịch bản lệch tool, chờ BTC), TTFT p95 6,7–7,3 s ở seed sạch (ngưỡng ≤ 3 s).
- **TSR của 7 mẫu BTC cố định** chỉ 14,3% vì order gate chặn tạo đơn khi lời khách không trả lời câu hỏi của gate (thiết kế; xem báo cáo).
- Chưa có LLM-judge 12 tiêu chí (14b) và chưa điền file chấm tay 20 lượt (người chấm).
- Chưa quay video demo; slide ở dạng HTML (chưa xuất `.pptx`).
- Giao diện web dựng tay (HTML/JS thuần), **không** sinh bằng W&B OpenUI như kế hoạch ban đầu.
- Order gate nằm trong orchestrator, chưa ở `mcp-crm`; API chạy MỘT worker, phiên đồng thời xen kẽ theo lượt.
