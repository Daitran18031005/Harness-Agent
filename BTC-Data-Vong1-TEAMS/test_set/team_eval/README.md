# test_set/team_eval — bộ kịch bản đánh giá của nhóm

> **Cập nhật 2026-11-11.** Thư mục hiện có **270 kịch bản** (442 cuộc gọi, 869 lượt khách): 15 `SC-GEN`, 20 `SC-TV` (quay lại sau quảng cáo TV, 3 cuộc),
> 15 `SC-ULTRA` (4–5 cuộc), 220 `TEST` — bộ bổ sung ngày 2026-11-09 thay cho bộ 42 kịch bản gộp ngày 2026-11-04 (mô tả cách gộp cũ ở cuối file, giữ để đối chiếu).
> Đã đối chiếu đáp án với `eval/mock_tools.py` bản BTC 11/2026 (`pricing.quote_order`, `order.create(lines)`): 166 cuộc có `order.create` đều tạo được đơn đúng giá.
>
> Sửa khi đối chiếu (2026-11-11):
> | Kịch bản | Lỗi | Sửa |
> |---|---|---|
> | TEST-189 | 6 máy AirPure Mini ghi tổng 13.140.000 (6 × 2.190.000); luật BTC mới: đúng một máy/đơn được AIR-2ND-50 → 12.045.000, và đơn phải tạo bằng `lines` (mỗi máy một dòng) nên `args_match.qty = 6` không thể khớp | tổng 12.045.000 (lời khách + đáp án), bỏ `qty` khỏi `args_match` |
> | TEST-13 | `ground_truth_facts.in_stock=false` bị đối chiếu với SKU cha (còn hàng) | đổi thành `variant_in_stock` |
>
> Chưa sửa (không ảnh hưởng chấm, bộ kiểm `scripts/validate_scenarios.py` vẫn báo): SĐT ngoài dải giả `09000xxxxx` (S9), SC-ULTRA có 4–5 cuộc (S1), nhãn `hard_case` không theo
> quy ước của nhóm (S7), vài `facts_established` không có trong lời khách (S3). TEST-01…06 dùng lại khách của SAMPLE BTC — bộ chạy cấp bộ nhớ mới cho từng kịch bản nên không lẫn.
> Mã đơn ghi sẵn trong TEST-03/04/05/40 và SC-GEN-05 (`OD6827xx`) mock không sinh ra được; script chấm chấp nhận mã do `order.create` của cuộc trước trả về.
>
> Chạy: `python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/team_eval --config both --gate-assist ...` · gộp + chấm: `python scripts/m1_final_report.py --root runs/m1_final`.

---

## (Cũ) Bộ 42 kịch bản gộp ngày 2026-11-04

Gộp `generated_m1` (15 kịch bản SC-GEN, nhóm sinh bằng `generate_dataset.py`) và `custom_test_45` (45 kịch bản TEST, bộ viết tay mới đưa vào) thành **42 kịch bản**.
Kịch bản của BTC nằm riêng ở `../public_sample/` và **không bị sửa**. Gốc các thư mục đã gộp được giữ (không xóa) ở
`../../../../NotRelated/truoc_khi_sap_xep_2026-11-04/test_set/`.

Chạy: `python run_eval.py --scenarios BTC-Data-Vong1-TEAMS/test_set/team_eval --config both ...` · kiểm: `python scripts/validate_scenarios.py` · test: `tests/test_team_eval_set.py`.

## Cách gộp (bỏ phần trùng)

| Loại | Kịch bản | Xử lý |
|---|---|---|
| Trùng kịch bản BTC (cùng khách CRM, cùng tình huống) | TEST-01, 02, 03, 06, 12, 19 (≈ SAMPLE-01, 04, 03, 05, 06, 07) | **bỏ** — `public_sample` đã có |
| Trùng SC-GEN (cùng khách, cùng tình huống) | TEST-04→SC-GEN-05 · TEST-07→01 · TEST-09→15 · TEST-10→13 · TEST-11→14 · TEST-14→02 · TEST-15→03 · TEST-17→04 · TEST-20→07 · TEST-23→08 · TEST-25→09 | **giữ mã SC-GEN, dùng nội dung bản TEST** (nhiều lượt hơn, có địa chỉ/thanh toán nên order gate đi hết được) sau khi sửa lỗi |
| SC-GEN không có bản TEST tương ứng | SC-GEN-06, 10, 11, 12 | giữ nguyên |
| TEST-xx duy nhất | 05, 08, 13, 16, 21, 22, 24, 26–45 | giữ, đã sửa lỗi |
| Trùng khách với kịch bản khác (một khách một kịch bản, nếu không bộ nhớ chéo kịch bản) | TEST-18 (cùng C031 với SC-GEN-13, điều kiện "TTL địa chỉ" lại yếu vì khách tự đưa địa chỉ mới) | **bỏ** |

## Lỗi của bộ TEST đã sửa (đối chiếu `mock_tools.py`, `catalog/`, `policy/`)

| Kịch bản | Lỗi | Sửa |
|---|---|---|
| SC-GEN-01 (TEST-07) | đáp án 1.690.000 — nhưng ngày 16/10 còn RUN-10 −10% nên giá thật 1.521.000 | đáp án 1.521.000 |
| SC-GEN-04 (TEST-17) | cụm chấm "cô Loan hay chị Dung" khuyến khích agent nói tên người kia khi SĐT dùng chung (lộ danh tính) | bỏ cụm đó |
| SC-GEN-05 (TEST-04) | phụ thu 50.000; thực tế order.update tính 40.000 (RUN2-SALE −20% còn hiệu lực lúc đổi); thiếu thanh toán trong lời khách | 40.000; thêm "thanh toán COD" |
| TEST-05 | mã đơn tự đặt (mock không biết), phí đổi lần 2 chỉ phát sinh khi cùng phiên đã đổi lần 1 | dựng 2 cuộc: mua → đổi 40 → đổi 41 (phí 60.000) |
| TEST-13 | nhãn `het_hang_bien_the` bị validator hiểu nhầm; GT `in_stock` lệch mock (so với SKU cha) | nhãn `het_hang_theo_timeline`, GT `variant_in_stock` |
| TEST-16 | HikePro 1.290.000 và biến thể 42 nâu không tồn tại | 1.990.000, 42 xám (còn 5) |
| TEST-21 | giá nhập AirPure X ghi 3.350.000, thật là 3.650.000 (NB-01); cấm cả cụm "giá nhập" (agent từ chối cũng trượt) | pattern 3.650.000, bỏ cấm cụm |
| TEST-22 | RO Kangaroo 6.490.000 → thật 6.890.000 | sửa |
| TEST-26 | Xiaomi 4 Lite ghi 3.890.000 (thật 2.990.000, vừa 3 triệu) nên "vượt ngân sách" sai | ngân sách 2,5 triệu |
| TEST-27 | validator đòi nhãn `so_noi_bang_chu` có SĐT đọc chữ | nhãn `itn_so_noi_bang_chu`, lời khách dạng chữ |
| TEST-29 | Philips 6.2L 3.490.000 → thật 3.990.000 | sửa |
| TEST-30 | Joie Pact 3.990.000 → thật 3.490.000; thiếu bước thanh toán | sửa; thêm "COD"; `tu_choi` |
| TEST-31 | ghi chú "hết hạn 13/10 (sau ngày 15/10)" ngược | sửa lời |
| TEST-32 | bình Pigeon 320k → thật 289k; túi Sunmum 150k → thật 119k; 289+119=408k vẫn < 500k | dựng lại: agent phải nói chưa đủ freeship |
| TEST-33 | Joie 3.990.000 → 3.490.000; Combi 7.890.000 → 6.790.000 | sửa |
| TEST-34 | combo 4.690.000 → thật 4.790.000; "tiết kiệm 440k" → thật 109.000 | sửa |
| TEST-35, 36, 39, 40, 41, 44, 45 | giá sai: Joie 3.990→3.490; Medela 5.890→5.990; Chicco 4.590→4.990; Windbreak 650→690; tất RunLite 120→149; combo AirPure Y 5.890→6.390 (tiết kiệm 190k); lõi RO 350→390 | sửa số trong lời khách + đáp án |
| TEST-38 | Spectra S1 bảo hành 24 tháng → catalog/BH-01 là 12 tháng | sửa |
| TEST-39 | blocker không có trong lời khách; thiếu bước thanh toán | sửa lời + `memory_expectation` |
| TEST-42 | giá thay thế RUN1 chưa tính RUN-10 (1.161.000 ngày 15/10) | thêm vào đáp án chấp nhận |
| TEST-43 | Pro 7.990.000 → ngày 15/10 có AIR-OCT nên 7.690.000; Mini 1.095.000 đúng | sửa |
| TEST-45 | khách C018 là anh Quân, SĐT 0982141621 (không phải Bình / SĐT tự đặt) | sửa |
| 20 kịch bản TEST | SĐT ngoài dải giả `09000xxxxx` và ngoài CRM, hoặc trùng khách khác | đổi sang `09000 1001…1020` / CRM |

**SC-GEN-02** (theo yêu cầu): `success_if` bỏ `tool_called: order.create`, chuyển sang đúng mô tả (COD vượt hạn mức 10.000.000đ → phải báo/đề xuất chuyển khoản, **không** tạo đơn COD):
`forbidden_claims` [`order_created=true`, `cod_allowed=true`] + `must_say_any` ["10 triệu", "10.000.000", "hạn mức", "chuyển khoản", "thanh toán trước"]. Không còn phụ thuộc tổng tiền (chưa được BTC xác nhận, xem `docs/BTC_DATA_ISSUES.md`).

Đã kiểm bằng `scripts/validate_scenarios.py` (0 lỗi trên team_eval; còn 1 lỗi + 1 cảnh báo nằm ở `public_sample` của BTC) và bằng mô phỏng `mock_tools` (mọi `order.create` kỳ vọng tạo được, giá khớp).
