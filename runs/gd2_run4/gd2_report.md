# Bước 15 GĐ2 — 3 seed, 22 kịch bản (7 mẫu BTC + 15 sinh), 92 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 72.7 ± 0.0 | 71.2 ± 2.6 |
| RQR (%) | 2.07 ± 3.58 | 12.17 ± 3.4 |
| CCR (%) | 52.4 ± 2.08 | 3.6 ± 0.0 |
| HR giá/KM (%) | 6.0 ± 0.17 | 33.93 ± 5.81 |
| Total p95 (ms) | 27414.33 ± 32475.72 | 9730 ± 1015.5 |

- TTFT p95 (full): 26177 ± 33247.42 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.12 ± 0.0; lượt/cuộc: 2.95 ± 0.02; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 76.5% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: ĐẠT · HR giá/KM ≤ 5%: CHƯA ĐẠT · TSR hơn baseline: có

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 72.7 | 14.3 | 100.0 | 0.0 | 53.6 | 5.9 |
| 2 | 72.7 | 14.3 | 100.0 | 6.2 | 50.0 | 5.9 |
| 3 | 72.7 | 14.3 | 100.0 | 0.0 | 53.6 | 6.2 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
