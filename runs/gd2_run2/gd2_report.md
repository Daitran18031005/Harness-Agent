# Bước 15 GĐ2 — 3 seed, 22 kịch bản (7 mẫu BTC + 15 sinh), 91 lượt/seed (cấu hình full)

| Chỉ số | full (mean ± std) | baseline (mean ± std) |
|---|---:|---:|
| TSR (%) | 68.2 ± 0.0 | 66.67 ± 2.66 |
| RQR (%) | 7.3 ± 6.51 | 13.8 ± 2.88 |
| CCR (%) | 53.6 ± 0.0 | 3.6 ± 0.0 |
| HR giá/KM (%) | 6.17 ± 0.46 | 42.23 ± 2.54 |
| Total p95 (ms) | 9953 ± 1162.94 | 9720.67 ± 285.81 |

- TTFT p95 (full): 8343 ± 684.32 ms (mục tiêu ≤ 3000 ms); cuộc gọi tới chốt: 1.12 ± 0.0; lượt/cuộc: 2.94 ± 0.0; vi phạm guardrail: 0 ± 0.0
- RQR giảm so với baseline: 50.6% (ngưỡng ≥ 40%) → ĐẠT
- TSR ≥ 70%: CHƯA ĐẠT · HR giá/KM ≤ 5%: CHƯA ĐẠT · TSR hơn baseline: có

## Theo từng seed (full)

| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 68.2 | 14.3 | 93.3 | 9.4 | 53.6 | 5.9 |
| 2 | 68.2 | 14.3 | 93.3 | 0.0 | 53.6 | 5.9 |
| 3 | 68.2 | 14.3 | 93.3 | 12.5 | 53.6 | 6.7 |

> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'.
