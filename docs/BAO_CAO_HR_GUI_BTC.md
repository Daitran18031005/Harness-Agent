# Gửi BTC — Hallucination Rate giá/KM khi một cuộc gọi nhắc nhiều sản phẩm

Kính gửi BTC,

Nhóm xin hỏi về cách `eval/reference_eval.py` (bản 08/11) tính Hallucination Rate giá & khuyến mãi.

**Hiện tượng.** Hàm `hallucination_rate` so MỌI claim có `field = "price_vnd"` trong một cuộc gọi với MỘT giá trị `ground_truth_facts.price_vnd` của cuộc gọi đó. Khi cuộc gọi nhắc từ hai sản phẩm trở lên (khách hỏi sản phẩm A rồi chuyển sang B, khách hỏi combo và từng món lẻ, khách mua 2 máy có khuyến mãi "máy thứ 2"), giá ĐÚNG của sản phẩm không nằm trong đáp án vẫn bị tính là bịa.

**Số liệu của nhóm** (277 kịch bản = 7 mẫu BTC + 270 kịch bản nhóm tự viết theo đúng định dạng BTC; gpt-4o-mini; chấm bằng `reference_eval.py`):

| | Số claim giá/KM kiểm chứng được | Bị tính sai | HR giá & KM |
|---|---|---|---|
| Theo script | 180 | 26 | 14,4% |
| Chỉ tính claim KHÁC giá của `mock_tools.py` | 180 | 1 | 0,6% |

Nhóm đối chiếu từng claim trong 26 claim đó với `mock_tools.pricing_get_quote` / `pricing_quote_order` đúng ngày gọi:

- 23 claim: đúng bằng `final_price_vnd` của một sản phẩm KHÁC sản phẩm trong đáp án. Ví dụ: khách hỏi quạt Panasonic F-409 trước, agent báo 2.450.000 (đúng theo mock); đáp án ghi 590.000 là giá quạt Senko mà khách chốt ở lượt sau.
- 1 claim: đúng giá của một BIẾN THỂ khác (size 43 có phụ thu, 1.740.000) trong khi đáp án là size 41 (1.521.000).
- 1 claim: đúng giá máy thứ hai sau AIR-2ND-50 theo `pricing.quote_order` (3.245.000) trong khi đáp án là giá máy thứ nhất (6.490.000).
- 1 claim: sai thật — agent báo giá niêm yết 7.990.000 cho mẫu đang giảm còn 7.690.000 (nhóm đã sửa).

Danh sách đầy đủ 26 claim (kịch bản, lượt, giá agent nói, giá đáp án, SKU khớp trong mock): `runs/m1_final/hr_price_check.json`.

**Câu hỏi.** Bộ test ẩn có các ca "đổi sản phẩm hoàn chênh lệch", "cuộc gọi 16 lượt 4 sản phẩm", "2 máy lọc không khí". Với các ca đó:

1. Giá đúng của sản phẩm không phải sản phẩm trong `ground_truth_facts` có bị tính là hallucination không?
2. Nếu có, nhóm nên ghi claim thế nào để không bị tính sai: thêm trường `sku` vào từng claim, hay dùng tên field riêng (nhóm đang dùng `alt_price_vnd` cho giá của mẫu được gợi ý thêm)?

Nhóm đề xuất: script chỉ so claim `price_vnd` với đáp án khi claim mang `sku` trùng sản phẩm của đáp án (hoặc claim không có `sku`), để chỉ số phản ánh đúng việc bịa giá.

Trân trọng.
