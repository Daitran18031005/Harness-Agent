# monitoring/ — giám sát bằng Prometheus + Grafana

Hai nguồn số đo, cùng một mã tính (`monitoring/metrics.py::observe_turn`, đọc đúng dòng trace của mỗi lượt):

| Nguồn | Cách chạy | Địa chỉ |
|---|---|---|
| **Máy chủ trực tiếp** — mỗi lượt qua API được ghi ngay | `uvicorn api.app:app --host 0.0.0.0 --port 8000` | `http://localhost:8000/metrics` |
| **Kết quả các lần đo** — đọc file trace JSONL (`runs/gd2_run*/**`) | `python -m monitoring.trace_exporter --host 0.0.0.0` | `http://localhost:9108/metrics` |

**Hai tiến trình trên phải nghe `0.0.0.0`** (không phải 127.0.0.1) thì container Prometheus mới lấy được số; Windows có thể hỏi cho phép tường lửa. `scripts/run_demo.py --host 0.0.0.0` cũng được (mặc định chỉ nghe 127.0.0.1).

Prometheus + Grafana chạy bằng Docker (cần Docker Desktop):

```bash
cd monitoring
docker compose up -d          # Grafana http://localhost:3000 (admin / admin — chỉ dùng trên máy local), Prometheus http://localhost:9090
docker compose down
```

Dashboard **"Harness Agent — giám sát"** được nạp sẵn (`grafana/dashboards/harness.json`), bộ lọc: nguồn / lần chạy / cấu hình.

| Nhóm panel | Số đo | Ngưỡng BTC (đỏ khi vượt) |
|---|---|---|
| Độ trễ | TTFT p95, Total p95, Call Brief p95; TTFT theo thời gian; TTFT p95 theo lần chạy | 3 s / 8 s / 5 s |
| TTFT đến từ đâu | TTFT trung bình, vòng LLM cuối, thời gian tool, số vòng LLM trước token đầu | — |
| Chi phí | VND tích lũy, VND/lượt, tỉ lệ prompt cache, đã tiêu vs trần cứng của máy chủ | trần `API_MAX_COST_VND` |
| An toàn | vi phạm guardrail (theo loại), tool lỗi, hành động order gate, tool theo tên | guardrail = 0 |

Ghi chú:
- Số đo **không chứa PII**: chỉ có đếm, thời gian và tên tool/loại sự kiện, không có lời khách, SĐT hay địa chỉ.
- Các panel p95/chi phí là **tích lũy** trong phạm vi bộ lọc (lần chạy đánh giá là dữ liệu tĩnh nên không dùng `rate`); chỉ biểu đồ "TTFT theo thời gian" dùng cửa sổ 5 phút và chỉ có số khi API đang nhận lượt.
- `llm_cap_vnd`/`llm_spent_vnd` chỉ có khi máy chủ đặt `API_MAX_COST_VND`.
- Trace mới có thêm hai trường tùy chọn (không nằm trong schema BTC): `latency_detail` (phân rã TTFT theo vòng LLM) và `guardrail` (chỉ khi bị chặn). Các lần đo cũ thiếu `guardrail` được tính là "approved".
- Chưa có cảnh báo (Alertmanager) và chưa chạy nhiều worker (registry nằm trong tiến trình API).
