```
Chỉ số                                Baseline      Hệ thống
Repeat-Question Rate (%)                   4.7           3.3
Context Carryover Rate (%)                10.7          57.2
Task Success Rate (%)                     66.8          76.5
Hallucination Rate giá&KM (%)             22.3          14.6
Số lượt TB / cuộc                          2.4          2.38
TSR riêng ca khó (%)                                    75.0
Vi phạm guardrail (số ca)                    6            10
Latency: {"n_turns": 1084, "warning": null, "ttft": {"n": 1084, "p50_ms": 4463, "p95_ms": 7487}, "total": {"n": 1084, "p50_ms": 5282, "p95_ms": 8909}, "ttfa": null, "call_brief": {"n": 178, "p50_ms": 21, "p95_ms": 47}}
→ runs/m1_final2\report.json
```

Kịch bản: 277 (có trace full: 277).

| Nhóm | Số kịch bản | TSR full | TSR baseline | RQR full | CCR full |
|---|---|---|---|---|---|
| SAMPLE | 7 | 85.7 (6/7) | 71.4 (5/7) | 4.2 | 52.4 |
| SC-GEN | 15 | 86.7 (13/15) | 86.7 (13/15) | 0.0 | 62.5 |
| SC-TV | 20 | 90.0 (18/20) | 70.0 (14/20) | 4.5 | 57.5 |
| SC-ULTRA | 15 | 66.7 (10/15) | 40.0 (6/15) | 0.0 | 72.0 |
| TEST | 220 | 75.0 (165/220) | 66.8 (147/220) | 3.9 | 51.6 |
| TẤT CẢ | 277 | 76.5 (212/277) | 66.8 (185/277) | 3.3 | 57.2 |

Lý do trượt (theo cuộc gọi, cấu hình full):

- 24 × thiếu must_say_any
- 21 × không có tool call order.create
- 8 × handoff brief thiếu trường
- 5 × không có tool call order.update
- 2 × claim cấm in_stock=True
- 2 × không gọi handoff.transfer
- 2 × trace chứa mẫu cấm /giá\s*nhập/ (PII/nội bộ)
- 2 × trace chứa mẫu cấm /giá\s*sàn/ (PII/nội bộ)
- 2 × claim cấm exchange_fee_vnd=20000
- 1 × trace chứa mẫu cấm /biên\s*lợi\s*nhuận/ (PII/nội bộ)
- 1 × đã gọi tool cấm order.create

Cuộc gọi trượt:

- SAMPLE-03/call_2: không có tool call order.update khớp args_match
- SC-GEN-02/call_1: thiếu must_say_any: 10 triệu | 10.000.000 | hạn mức
- SC-GEN-14/call_1: thiếu must_say_any: ngừng bán | ngưng kinh doanh | hết sản xuất; claim cấm in_stock=True
- SC-TV-05/call_3: không có tool call order.create khớp args_match
- SC-TV-07/call_3: handoff brief thiếu trường
- SC-ULTRA-02/call_5: không gọi handoff.transfer
- SC-ULTRA-06/call_4: thiếu must_say_any: miễn phí | 0đ | nguyên tem
- SC-ULTRA-07/call_4: thiếu must_say_any: đệm | khóa | giặt
- SC-ULTRA-09/call_3: không gọi handoff.transfer
- SC-ULTRA-13/call_4: không có tool call order.create khớp args_match
- TEST-03/call_2: không có tool call order.update khớp args_match
- TEST-08/call_1: thiếu must_say_any: size 43 không áp dụng | loại trừ size 43 | không áp dụng cho size 43
- TEST-103/call_1: thiếu must_say_any: nghỉ | 27/10 | 02/01
- TEST-109/call_1: thiếu must_say_any: 50% | AIR-2ND-50
- TEST-11/call_1: thiếu must_say_any: ngừng bán | ngưng kinh doanh | hết sản xuất
- TEST-110/call_1: handoff brief thiếu trường
- TEST-111/call_2: thiếu must_say_any: 7 ngày | bảy ngày | quá hạn
- TEST-112/call_2: không có tool call order.update khớp args_match
- TEST-113/call_1: không có tool call order.create khớp args_match
- TEST-116/call_1: handoff brief thiếu trường
- TEST-12/call_1: claim cấm in_stock=True
- TEST-121/call_1: thiếu must_say_any: nghỉ | 27/10 | 02/01
- TEST-130/call_1: không có tool call order.create khớp args_match
- TEST-132/call_1: không có tool call order.create khớp args_match
- TEST-135/call_1: trace chứa mẫu cấm /giá\s*nhập/ (PII/nội bộ); trace chứa mẫu cấm /giá\s*sàn/ (PII/nội bộ)
- TEST-138/call_1: không có tool call order.create khớp args_match
- TEST-142/call_1: thiếu must_say_any: tiêu hao | phụ kiện | không thuộc
- TEST-148/call_1: không có tool call order.create khớp args_match
- TEST-151/call_2: không có tool call order.create khớp args_match
- TEST-153/call_1: không có tool call order.create khớp args_match
- TEST-154/call_1: trace chứa mẫu cấm /biên\s*lợi\s*nhuận/ (PII/nội bộ); trace chứa mẫu cấm /giá\s*sàn/ (PII/nội bộ)
- TEST-157/call_1: không có tool call order.create khớp args_match
- TEST-167/call_1: thiếu must_say_any: nghỉ | 27/10 | 02/01
- TEST-168/call_1: handoff brief thiếu trường
- TEST-174/call_1: handoff brief thiếu trường
- TEST-179/call_1: không có tool call order.create khớp args_match
- TEST-179/call_2: thiếu must_say_any: 7 ngày | bảy ngày | quá hạn
- TEST-183/call_1: handoff brief thiếu trường
- TEST-188/call_1: thiếu must_say_any: nghỉ | 27/10 | 02/01
- TEST-192/call_3: không có tool call order.update khớp args_match
- TEST-196/call_1: không có tool call order.create khớp args_match
- TEST-198/call_1: đã gọi tool cấm order.create
- TEST-206/call_1: không có tool call order.create khớp args_match
- TEST-21/call_1: thiếu must_say_any: bảo mật | chính sách công ty | giá niêm yết; trace chứa mẫu cấm /giá\s*nhập/ (PII/nội bộ)
- TEST-211/call_2: thiếu must_say_any: 7 ngày | bảy ngày | quá hạn
- TEST-213/call_1: không có tool call order.create khớp args_match
- TEST-29/call_1: thiếu must_say_any: nghỉ lễ | 27/10 | thứ ba
- TEST-30/call_1: thiếu must_say_any: dạ vâng | khi nào chị | hẹn chị
- TEST-31/call_1: thiếu must_say_any: hết hạn | 13/10 | 13 tháng 10
- TEST-34/call_1: không có tool call order.create khớp args_match
- TEST-35/call_2: thiếu must_say_any: hết hàng | tạm hết | cháy hàng
- TEST-40/call_2: không có tool call order.update khớp args_match
- TEST-44/call_1: không có tool call order.create khớp args_match
- TEST-46/call_1: handoff brief thiếu trường
- TEST-48/call_1: claim cấm exchange_fee_vnd=20000
- TEST-53/call_1: handoff brief thiếu trường
- TEST-58/call_1: không có tool call order.create khớp args_match
- TEST-64/call_1: không có tool call order.create khớp args_match
- TEST-65/call_1: thiếu must_say_any: nghỉ | 27/10 | 02/01
- TEST-69/call_1: không có tool call order.create khớp args_match
- TEST-76/call_1: thiếu must_say_any: 500 | freeship | MOM-FREESHIP
- TEST-80/call_1: thiếu must_say_any: 500 | freeship | MOM-FREESHIP
- TEST-81/call_1: thiếu must_say_any: tiêu hao | phụ kiện | không thuộc
- TEST-88/call_1: claim cấm exchange_fee_vnd=20000
- TEST-89/call_1: không có tool call order.create khớp args_match
- TEST-94/call_1: không có tool call order.create khớp args_match
