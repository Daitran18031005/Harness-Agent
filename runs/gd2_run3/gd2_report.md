# Bước 15 GĐ2 — 3 seed, 22 kịch bản (7 mẫu BTC + 15 sinh), 92 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 71.2 ± 2.6 | 69.7 ± 2.6 |
| RQR (%) | 2.23 ± 3.87 | 15.0 ± 7.83 |
| CCR (%) | 52.4 ± 2.08 | 3.6 ± 0.0 |
| HR giá/KM (%) | 9.5 ± 6.24 | 40.97 ± 12.02 |
| Total p95 (ms) | 14647.67 ± 3677.17 | 13110.67 ± 722.52 |

- TTFT p95 (full): 13953.33 ± 3242.77 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.12 ± 0.0; lượt/cuộc: 2.96 ± 0.02; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 87.3% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: ĐẠT · HR giá/KM ≤ 5%: CHƯA ĐẠT · TSR hơn baseline: có

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 68.2 | 14.3 | 93.3 | 0.0 | 53.6 | 16.7 |
| 2 | 72.7 | 14.3 | 100.0 | 0.0 | 50.0 | 5.9 |
| 3 | 72.7 | 14.3 | 100.0 | 6.7 | 53.6 | 5.9 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
