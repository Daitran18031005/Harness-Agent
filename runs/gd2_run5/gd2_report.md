# Bước 15 GĐ2 — 3 seed, 21 kịch bản (7 mẫu BTC + 14 sinh), 89 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 69.83 ± 2.71 | 69.83 ± 2.71 |
| RQR (%) | 0.0 ± 0.0 | 4.8 ± 3.47 |
| CCR (%) | 53.6 ± 0.0 | 3.6 ± 0.0 |
| HR giá/KM (%) | 1.87 ± 3.23 | 16.13 ± 1.33 |
| Total p95 (ms) | 8175.33 ± 450.29 | 8666 ± 297.94 |

- TTFT p95 (full): 6536 ± 323.69 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.15 ± 0.02; lượt/cuộc: 2.92 ± 0.04; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 100.0% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: CHƯA ĐẠT · HR giá/KM ≤ 5%: ĐẠT · TSR hơn baseline: không

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 66.7 | 14.3 | 92.9 | 0.0 | 53.6 | 0.0 |
| 2 | 71.4 | 14.3 | 100.0 | 0.0 | 53.6 | 5.6 |
| 3 | 71.4 | 14.3 | 100.0 | 0.0 | 53.6 | 0.0 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
