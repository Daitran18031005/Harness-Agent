# Bước 15 GĐ2 — 3 seed, 22 kịch bản (7 mẫu BTC + 15 sinh), 89 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 50.0 ± 4.5 | 53.03 ± 6.92 |
| RQR (%) | 0.0 ± 0.0 | 7.8 ± 3.12 |
| CCR (%) | 53.6 ± 0.0 | 3.6 ± 0.0 |
| HR giá/KM (%) | 31.1 ± 7.24 | 42.1 ± 5.14 |
| Total p95 (ms) | 14635 ± 5850.76 | 15058.33 ± 4448.57 |

- TTFT p95 (full): 12935.33 ± 6315.42 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.13 ± 0.01; lượt/cuộc: 2.89 ± 0.04; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 100.0% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: CHƯA ĐẠT · HR giá/KM ≤ 5%: CHƯA ĐẠT · TSR hơn baseline: không

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 45.5 | 14.3 | 60.0 | 0.0 | 53.6 | 25.0 |
| 2 | 54.5 | 14.3 | 73.3 | 0.0 | 53.6 | 29.2 |
| 3 | 50.0 | 14.3 | 66.7 | 0.0 | 53.6 | 39.1 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
