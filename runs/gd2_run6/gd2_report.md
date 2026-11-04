# Bước 15 GĐ2 — 3 seed, 22 kịch bản (7 mẫu BTC + 15 sinh), 89 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 66.67 ± 2.66 | 68.2 ± 0.0 |
| RQR (%) | 0.0 ± 0.0 | 7.07 ± 1.77 |
| CCR (%) | 53.6 ± 0.0 | 1.2 ± 2.08 |
| HR giá/KM (%) | 0.0 ± 0.0 | 23.17 ± 11.99 |
| Total p95 (ms) | 9505 ± 937.16 | 9300.67 ± 584.62 |

- TTFT p95 (full): 7717.67 ± 671.92 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.15 ± 0.02; lượt/cuộc: 2.85 ± 0.03; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 100.0% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: CHƯA ĐẠT · HR giá/KM ≤ 5%: ĐẠT · TSR hơn baseline: không

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 68.2 | 14.3 | 93.3 | 0.0 | 53.6 | 0.0 |
| 2 | 63.6 | 14.3 | 86.7 | 0.0 | 53.6 | 0.0 |
| 3 | 68.2 | 14.3 | 93.3 | 0.0 | 53.6 | 0.0 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
