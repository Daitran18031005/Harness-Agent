# Nhật ký phiên bản dataset kịch bản (`BTC-Data-Vong1-TEAMS/test_set/team_eval/`, trước 2026-11-04: `generated_m1/`)

Nguyên tắc: bản cũ được **đóng băng** (không sửa) để số liệu cũ còn so sánh được; `team_eval/` luôn là phiên bản mới nhất. Từ v3 các file JSON trong `team_eval/` là nguồn gốc (không còn sinh lại bằng `generate_dataset.py`, đã chuyển vào `NotRelated/truoc_khi_sap_xep_2026-11-04/`). Kịch bản của BTC (`public_sample/`) **không bao giờ sửa** (lỗi của BTC ghi ở [BTC_DATA_ISSUES.md](BTC_DATA_ISSUES.md)).

## v3 — 2026-11-04 (gộp `generated_m1` + `custom_test_45` → `team_eval`)

Chi tiết từng lỗi đã sửa và bảng gộp: [test_set/team_eval/README.md](../BTC-Data-Vong1-TEAMS/test_set/team_eval/README.md). Tóm tắt:
- 15 SC-GEN + 45 TEST → **42 kịch bản (63 cuộc)**: bỏ 6 TEST trùng `public_sample`, 1 TEST trùng khách (TEST-18); 11 TEST trùng SC-GEN được **gộp vào mã SC-GEN** (dùng nội dung giàu hơn của TEST sau khi sửa); 4 SC-GEN (06, 10, 11, 12) giữ nguyên; 27 TEST duy nhất giữ lại đã sửa.
- Sửa theo `mock_tools`/catalog/chính sách: hơn 20 kịch bản sai giá, ngày KM, bảo hành, giá nhập; 20 SĐT đổi về dải giả; SC-GEN-04 bỏ cụm lộ tên người dùng chung SĐT; SC-GEN-01 đáp án 1.521.000 (RUN-10 còn hiệu lực).
- **SC-GEN-02**: `success_if` đổi theo đúng mô tả — không đòi `order.create`; yêu cầu báo vượt hạn mức COD 10.000.000đ / đề xuất chuyển khoản và cấm `order_created`, `cod_allowed`.
- Validator: `het_hang_*` không còn bị nhận nhầm là "KM hết hạn"; ca `pii_protection` được phép có CCCD/STK giả; `fact_in_text` thử lại trên bản đã chuẩn hóa (số nói bằng chữ).
- Số liệu GĐ2 cũ (lần 1–6) đo trên 22 kịch bản của `generated_m1` + `public_sample`: **không so sánh trực tiếp** với bộ 49 kịch bản mới.

## v2 — 2026-10-21

Phát hiện bằng validator (`scripts/validate_scenarios.py`, luật S4/S6 được siết thêm cùng đợt). Chỉ **đáp án** (ground truth) đổi; lời thoại ban đầu không đổi, trừ một lượt khách thêm ở SC-GEN-06.

| Kịch bản | Lỗi ở v1 | Sửa ở v2 |
|---|---|---|
| SC-GEN-05 | cuộc 2 `must_carry_over` có `order_id` nhưng cuộc 1 không có fact `order_id` (mã đơn do mock sinh lúc chạy, không biết trước) | bỏ `order_id` khỏi `must_carry_over` |
| SC-GEN-06 | cuộc 2 (15/10) ghi `promo_active: true` trong khi PUMP-GIFT (quà tặng) hết hạn 13/10 | `promo_active: false`, thêm `promo_end_date: 2026-10-13`; thêm lượt khách hỏi "quà tặng còn không" để đáp án này được kiểm; giá 4.290.000 không đổi (KM là quà, không giảm giá) |
| SC-GEN-11 | cuộc 1 có `must_not_ask` [diện tích, ngân sách, có trẻ nhỏ] nhưng không có `facts_established` tương ứng, `success_if` và `ground_truth_facts` rỗng | thêm `facts_established` (40 m², 6 triệu, có trẻ nhỏ); `ground_truth_facts` = SKU-SS-AX40 (40 m², có khóa trẻ em, 6.490.000 = +8% ngân sách, trong ngưỡng ±20%; AirPure Pro 7.690.000 = +28% bị loại, AirPure Y 30 m² không đủ diện tích); `success_if.must_say_any` ["AX40"] |

Validator: `S6` giờ cấm `must_carry_over` ở cuộc 1 không có `seed_history`, và chỉ cho `must_not_ask` ở cuộc 1 khi slot đó nằm trong `facts_established` của chính cuộc; `S4` kiểm thêm `facts_established.price_quoted_vnd` với `mock_tools`.

### Chấm lại offline các trace cũ với đáp án v2
- Mọi trace đã có (`runs/buoc15_A|B|C`) chỉ gồm **SAMPLE-01…07** (kịch bản BTC, không đổi); không trace nào chứa SC-GEN-* → chấm lại bằng GT v2 cho **đúng số cũ** (đã kiểm: `reference_eval` trên `public_sample` cho báo cáo trùng khớp từng khóa với `runs/buoc15_C/report.json`, ngoại trừ latency).
- Lưu ý khi chấm chung: nếu đưa cả SC-GEN-* vào thư mục kịch bản mà không có trace, `reference_eval` tính chúng là trượt (RQR/CCR/TSR đổi vì mẫu số, không phải vì GT). Muốn so sánh v1 và v2 phải chấm trên tập kịch bản **có trace**.
- SAMPLE-01 (lỗi BTC: `budget_vnd` 5,7 triệu so với lời khách "5 triệu") **không sửa**.

## v1 — 2026-10 (ban đầu)
15 kịch bản SC-GEN-01…15 (31 cuộc), sinh bằng `generate_dataset.py` từ catalog/mock thật. Lưu ở `generated_m1_v1/`.
