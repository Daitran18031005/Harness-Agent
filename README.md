# Harness Agent Call Center E-commerce — hướng dẫn chạy nhanh

> Tài liệu tổng quan hệ thống: [../README.md](../README.md) · kế hoạch: [docs/PLAN.md](docs/PLAN.md) · nhật ký làm việc: [CHECKING.md](CHECKING.md).
> **Hồ sơ nộp:** [submission/README.md](submission/README.md) · **giao diện demo:** `python scripts/run_demo.py` → http://127.0.0.1:8000/

## Cài đặt

```bash
conda activate nlp_env            # Python 3.12; mọi lệnh dưới đây chạy trong env này
pip install -r requirements.txt
cp .env.example .env              # điền OPENAI_API_KEY (file .env KHÔNG được đưa vào gói nộp)
python -m unittest discover -s tests -t .
```

## Dữ liệu và bộ kịch bản (sắp xếp 2026-11-04)

- `BTC-Data-Vong1-TEAMS/test_set/public_sample/` (7 kịch bản BTC, không sửa) + `team_eval/` (42 kịch bản nhóm, gộp từ `generated_m1` và `custom_test_45`; đã đối chiếu `mock_tools`) = **bộ đánh giá hằng ngày 49 kịch bản**. Chi tiết gộp và lỗi đã sửa: `test_set/team_eval/README.md`.
- `dataset/`: `frames/` (khung kịch bản), `agent_eval/` (bộ đánh giá agent sinh bằng LLM), `asr/` (lời thoại để sinh audio và đo ASR), `reports/` (sổ cái chi phí). Xem `dataset/README.md`.
- Lỗi/nghi vấn của gói BTC và thư gửi BTC: `docs/BTC_DATA_ISSUES.md`, `docs/BAO_CAO_LOI_GUI_BTC.md`.

## Giám sát (Prometheus + Grafana)

API phát `GET /metrics`; `python -m monitoring.trace_exporter --host 0.0.0.0` phát số từ trace các lần đo; `docker compose up -d` trong `monitoring/` dựng Prometheus + Grafana với dashboard nạp sẵn (TTFT/Total/Call Brief so ngưỡng BTC, chi phí, tool, guardrail, order gate). Xem `monitoring/README.md`.

## Order gate và cách đo (quyết định 2026-10-22)

- **Order gate luôn bật ở mọi cấu hình** (demo, UI, eval): trước khi tạo đơn, code kiểm checklist (sản phẩm/biến thể, số lượng, tên & SĐT nhận, địa chỉ, thanh toán) → hỏi/xác nhận → đọc lại đơn một lần → chỉ tạo đơn khi lượt sau khách đồng ý rõ ràng. Không có cờ/biến môi trường để tắt (`OrderGate.enabled` chỉ đọc; chỉ test đơn vị mới gọi được `disable_for_unit_tests`, có test quét mã nguồn).
- **Hai loại đo, báo cáo riêng** (`src/eval/gate_metrics.py`, `scripts/gate_report.py`; `run_eval.py` và `analyze_run.py` tự in):
  1. **TSR tương tác (TSR chính)** — khách mô phỏng trả lời được gate (`run_eval.py --gate-assist`; lượt chèn gắn `_injected` trong trace); cuộc tạo đơn đạt khi `order.create` đúng SKU/giá **sau khi khách xác nhận**. Dùng cho 54 kịch bản mới (luật P5 đảm bảo lời khách có đáp án cho gate).
  2. **Kiểm tra kịch bản cố định (7 mẫu BTC)** — KHÔNG tính vào TSR chính; đạt = không tạo đơn sớm + đã tới bước đọc lại đơn. `--gate-assist` bị từ chối với kịch bản BTC.
- **Phát lại lỗi UI bằng LLM thật**: `python scripts/ui_replay.py` (lời khách chép từ ảnh chụp UI, trần 400 VND trong mã) — chạy sau mỗi thay đổi hội thoại; test đơn vị không thay được.
- **Trần chi phí cứng luôn bật**: `run_eval.py` mặc định 20.000 VND (đủ cho bộ ẩn BTC 41 kịch bản × 2 cấu hình; chạy thử nên đặt thấp hơn) (`--max-cost-vnd` để đổi, phải > 0); client kiểm trước MỖI lần gọi API (kể cả vòng giữa lượt) và dừng khi chạm trần (`BudgetExceeded` kế thừa `BaseException` để không bị `except Exception` nuốt). Run chẩn đoán nhiều seed: `scripts/diagnose_seeds.py` (trần 3.000 VND nằm trong mã).

## Kiến trúc MCP — 3 server thật (`mcp_servers/`)

| Server | Tool | Ghi chú |
|---|---|---|
| `mcp-catalog` | `catalog.search`, `inventory.check`, `pricing.get_quote`, `product.shortlist` | chỉ đọc |
| `mcp-crm` | `crm.get_customer`, `order.*`, `schedule.callback`, `handoff.transfer` | tool ghi chỉ cho lõi điều phối |
| **`mcp-memory`** | `memory.*` (19 tool: giao dịch theo lượt, working/episodic/profile, chính sách, liên kết định danh, xóa khách) | **nơi ghi duy nhất** của bộ nhớ khách hàng |

- **Một nơi ghi duy nhất**: chỉ tiến trình `mcp-memory` giữ `MemoryService` và mở file SQLite (mỗi file DB đúng một `MemoryService`, nhiều client dùng chung theo đếm tham chiếu). Orchestrator, Call Brief, IdentityResolver, UI, bộ chạy đánh giá chỉ là client (`src/memory/remote.py::RemoteMemoryService`, giao diện y hệt `MemoryService`).
- **Phân quyền theo caller** (`config/mcp_permissions.json`, mặc định từ chối, kiểm ở phía server): `memory.as_caller("CallBriefBuilder")` và `"StreamlitUI"` chỉ đọc; `IdentityResolver` chỉ ghi fact kênh/xưng hô, gộp hồ sơ, liên kết định danh; `HarnessCore` mở/đóng kho và giao dịch lượt; xóa khách chỉ `Operator`.
- **Vận chuyển** `MEMORY_TRANSPORT`: `stdio` (server là tiến trình riêng — mặc định của `main.py`, UI, `run_eval.py`), `inproc` (cùng giao thức MCP trong một tiến trình), `local` (không qua MCP — mặc định của test). Chạy cả bộ test qua MCP: `MEMORY_TRANSPORT=inproc python -m unittest discover -s tests -t .`.
- Đo chi phí tăng thêm: `python scripts/bench_memory.py`. Script `seed_demo_db.py` chạy độc lập mở DB bằng `MemoryService` cục bộ — chỉ chạy khi không có server nào đang giữ cùng file DB.

## ASR (nhận dạng giọng nói, chạy local, không tốn API)

Hai backend, chọn bằng biến môi trường `ASR_BACKEND`:

| `ASR_BACKEND` | Model | Ghi chú |
|---|---|---|
| `gipformer` (**mặc định từ 2026-10-21**) | **Gipformer 1.5 68M RNN-T** (G-Group AI Lab, MIT), Zipformer transducer, ONNX int8, qua `sherpa-onnx` | cần model (≈ 73 MB) trong `model_ASR/` |
| `whisper` (dự phòng) | faster-whisper, `ASR_MODEL=base` | không đặt `ASR_BACKEND` mà Gipformer không nạp được (thiếu/sai model) thì **tự rơi về whisper** kèm cảnh báo; đặt rõ `ASR_BACKEND=gipformer` mà lỗi thì không đổi ngầm |

Luật quay lại whisper (ghi ở [docs/PLAN.md](docs/PLAN.md) bước 16a): khi đo trên **≥ 20 file** mà Gipformer kém whisper về WER hoặc entity accuracy thì đổi mặc định lại và báo nhóm.

### Tải model

Model **không nằm trong git** (`model_ASR/` và `models/` đã có trong `.gitignore`); **gói nộp thì kèm model** (xem cuối mục). Nguồn: Hugging Face `g-group-ai-lab/gipformer1.5-68M-rnnt`.

```bash
pip install -U huggingface_hub
huggingface-cli download g-group-ai-lab/gipformer1.5-68M-rnnt --local-dir model_ASR
```

Khi nạp, mã kiểm SHA-256 (16 ký tự đầu) và báo rõ file thiếu/sai:

| File | SHA-256 (16 ký tự đầu) |
|---|---|
| `encoder.int8.onnx` | `b528768939c7711a` |
| `decoder.int8.onnx` | `e0a156b5454722a5` |
| `joiner.int8.onnx` | `12636559d135315f` |
| `tokens.txt` | `f536d03c2e95ebd2` |
| `bpe.model` | `289dbb44527c13c4` |

### VAD (bỏ khoảng lặng/ồn trước khi nhận dạng)

Gipformer luôn in ra chữ kể cả khi chỉ có tiếng ồn, nên mã luôn chạy VAD và cắt đoạn ≤ 20 giây. Chọn bằng `ASR_VAD=silero|energy|auto` (mặc định `auto` = Silero nếu có model, ngược lại VAD năng lượng):

- **Silero VAD** (khuyến nghị — bền hơn khi nhiễu lớn, xem [CHECKING.md § 11.24](CHECKING.md)): tải file `silero_vad.onnx` **chỉ từ release chính thức** `asr-models` của `k2-fsa/sherpa-onnx` vào `model_ASR/`:
  ```bash
  curl -L -o model_ASR/silero_vad.onnx https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx
  ```
  Dung lượng **643.854 byte**; SHA-256 `9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6` (đã ghi và được mã kiểm khi nạp; kiểm URL bằng `curl -I` ngày 2026-10-21: HTTP 302 → 200).
- **VAD năng lượng**: không cần model, là phương án dự phòng; bỏ sót khi nhiễu trắng lớn (SNR ≤ 5 dB). Ngược lại Silero bỏ sót khi có kênh điện thoại + tạp âm — vì vậy mặc định `auto` dùng hợp cả hai. **Các kết luận VAD chỉ trên nhiễu giả lập, cần kiểm lại trên ghi âm điện thoại thật.**
- `ASR_VAD=silero` mà thiếu file → báo lỗi rõ, không âm thầm đổi sang VAD khác.

Biến môi trường khác: `GIPFORMER_MODEL_DIR` (thư mục model), `ASR_NUM_THREADS`, `ASR_MAX_CHUNK_S` (mặc định 20), `ASR_VAD_MODEL` (đường dẫn Silero khác).

### Lệnh tái lập

```bash
python eval_asr.py                                                         # WER/CER trên D01–D04 (backend mặc định)
python scripts/compare_asr.py                                              # gipformer(silero) / gipformer(energy) / whisper-base
python scripts/compare_asr.py --noise white@10,phone,phone+codec,phone+babble@10,phone+street@10,phone+cafe@10
python scripts/compare_asr.py --backends whisper:small                     # whisper cỡ khác (lần đầu tự tải model)
python scripts/export_hypotheses.py                                        # asr/hypotheses.json + chấm bằng wer_cer của BTC
python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --asr runs/asr_hypotheses/gipformer
```

### Điều cần biết

- Đầu ra Gipformer là **CHỮ HOA, không chữ số, không dấu câu**; được đổi về chữ thường (giữ dấu) rồi qua `RequestNormalizer` (ITN số tiền/SĐT/ngày, che PII) như đường chat.
- Bảng WER trong model card của tác giả (tele-medium, tele-hard-*, …) là **số do tác giả công bố trên bộ dữ liệu riêng của họ, không phải số đo của dự án này**. Mọi số của dự án ghi rõ phạm vi: hiện là **"trên audio TTS sạch, giọng Bắc, n = 4 file"**; nhiễu và kênh điện thoại trong `compare_asr.py` là **mô phỏng** (`src/channels/audio_sim.py`), không thay cho ghi âm thật.
- `turns[].idx` trong `hypotheses.json` lấy từ `<id>.segments.json` cạnh file audio do khâu tạo audio ghi lại; **không có file đó thì không xuất `turns`**.
- Entity accuracy 100% trên D01–D04 là **trong tập phát triển (D01–D04), luật viết sau khi xem dữ liệu**; luật được khóa ở `config/asr_rules.lock.json` (`python scripts/lock_asr_rules.py --check`), số trên audio mới phải báo riêng.
- Thực thể trong `hypotheses.json` (sku, color, promo_expiry, payment, in_stock, blocker, size, số tiền, SĐT, mã đơn…) do `src/channels/asr_entities.py` + `asr_postprocess.py` trích; bảng cách đọc tên sản phẩm ở `config/product_aliases.json`.

### Đóng gói nộp bài

```bash
python scripts/package_submission.py             # MẶC ĐỊNH kèm model_ASR/ (kiểm SHA-256; có LICENSE MIT, README của tác giả, NOTICE.md, Silero VAD)
python scripts/package_submission.py --no-model  # gói nhẹ, không kèm model
```

Gói luôn loại `.env` và `backup_*/` và quét không còn chuỗi giống API key. Repo Git không chứa model (`.gitignore`). **Gói bị chặn nếu `model_ASR/LICENSE` vẫn là bản nhóm dựng** (tác giả không phát hành file LICENSE; tải bản gốc từ trang của tác giả rồi đổi `LICENSE_STATUS: upstream` trong `model_ASR/NOTICE.md`).
