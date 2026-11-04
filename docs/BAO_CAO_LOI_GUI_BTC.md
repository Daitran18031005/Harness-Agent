# Báo cáo gửi Ban tổ chức: các điểm bất thường trong gói dữ liệu Vòng 1

**Gửi:** Ban tổ chức Sudo Code 2026 · **Từ:** nhóm Harness Agent Call Center · **Ngày:** 2026-11-04

Kính gửi Ban tổ chức,

Trong quá trình dựng và kiểm thử hệ thống, nhóm đối chiếu từng kịch bản, schema và `mock_tools.py` trong gói `BTC-Data-Vong1-TEAMS` với nhau. Chúng tôi tìm thấy 8 điểm bất thường và 1 câu hỏi về cách chấm, nêu dưới đây kèm cách tái hiện. **Chúng tôi không sửa bất kỳ file nào của BTC;** hệ thống vẫn được đo theo bản gốc. Rất mong BTC xác nhận hoặc chỉnh lại các điểm này. Điểm 1 và 2 ảnh hưởng trực tiếp đến đáp án, điểm 3 đến cách tính tiền.

Mọi lệnh bên dưới chạy trong thư mục `BTC-Data-Vong1-TEAMS/eval` (Python 3).

## Nhóm A. Có thể ảnh hưởng đáp án hoặc kết quả chấm

**1. `SAMPLE-01`: `budget_vnd` trong đáp án lệch lời khách.**
- Đáp án: `calls.call_1.facts_established.budget_vnd = 5700000`.
- Lời khách cùng cuộc: "Nhà chị có bé nhỏ, **ngân sách tầm 5 triệu** thôi em." (không có con số 5,7 triệu ở chỗ nào trong lời khách).
- Hệ quả: slot ngân sách đúng theo lời khách (5.000.000) bị tính là sai khi đối chiếu đáp án.
- Câu hỏi: 5,7 triệu lấy từ đâu? Nếu là lỗi nhập, xin BTC cập nhật thành 5.000.000.

**2. `mock_tools`: khuyến mãi AIR-2ND-50 áp −50% cho cả hai máy giống nhau.**
`dieu-khoan-khuyen-mai.md` ghi "giảm 50% **máy rẻ hơn**". Khi hai máy cùng SKU, `percent_second_item` dùng điều kiện `base <= min(others)`, đúng với cả hai máy nên cả hai cùng được giảm. Tái hiện:
```python
import mock_tools as m
m.pricing_get_quote("SKU-AP-PRO", on="2026-10-15", basket_skus=["SKU-AP-PRO"])
# final_price_vnd = 3995000, applied_promos có AIR-2ND-50 discount_vnd = 3995000
m.order_create("0900000001", "SKU-AP-PRO", 2, None, None, "COD", "Hà Nội", "2026-10-15", basket_skus=["SKU-AP-PRO"])
# status = created, total_vnd = 7990000   (= 2 x 3.995.000)
m.order_create("0900000001", "SKU-AP-PRO", 2, None, None, "COD", "Hà Nội", "2026-10-15")
# error = cod_limit_exceeded, total_vnd = 15380000   (AIR-2ND-50 không áp khi không truyền basket_skus)
```
Cùng một đơn 2 máy AirPure Pro ngày 15/10 ra **ba** tổng khác nhau. Theo cách chúng tôi hiểu KM-03/KM-04 (chọn chương trình lợi nhất cho từng máy; AIR-OCT −300.000 cho máy 1, AIR-2ND-50 cho máy rẻ hơn) thì tổng phải là 7.690.000 + 3.995.000 = **11.685.000**. Xin BTC cho biết đáp án đúng. Kịch bản `SC-GEN-02` của nhóm (COD vượt hạn mức) vì thế không dùng tổng tiền làm tiêu chí chấm.

**3. `schemas/tools.schema.json`: `order.create` không có `basket_skus`, trong khi `pricing.get_quote` có.**
- Schema `order.create` chỉ có: `customer_phone, sku, qty, price_vnd, promo_code, payment, address`.
- `pricing.get_quote` có `basket_skus` ("xét AIR-2ND-50"), và hàm `mock_tools.order_create` cũng nhận `basket_skus` (khớp điểm 2) nhưng schema không công bố.
- Hệ quả: theo schema, khách mua 2 máy lọc không khí không thể tạo đơn với đúng giá có khuyến mãi (đơn trả `price_mismatch`). Hệ thống của nhóm đang chuyển ca này cho nhân viên.
- Đề nghị: thêm `basket_skus` (hoặc danh sách dòng hàng) vào schema `order.create`, hoặc nêu rõ cách tạo đơn nhiều máy.

**4. Chưa rõ luật AIR-2ND-50 và AIR-OCT trong các tình huống biên.**
- Mua từ 3 máy lọc không khí: máy thứ 3, thứ 4 có được giảm không?
- Khi máy 2 nhận AIR-2ND-50, máy 1 có còn nhận AIR-OCT không (tổng 11.685.000 hay 11.985.000 với hai máy Pro)?
- `mock_tools` hiện không trả lời được hai câu này. Xin BTC bổ sung vào `dieu-khoan-khuyen-mai.md`.

## Nhóm B. Thiếu file / không khớp mô tả

**5. `README.md` gói BTC liệt kê `eval/validate_scenarios.py` ("BTC chạy sau mỗi lần sửa") nhưng gói không có file này.** `ls eval/` chỉ có `huong-dan-do-latency.md, llm_judge_rubric.json, make_example_trace.py, mock_tools.py, reference_eval.py`. Nhóm đã tự viết công cụ kiểm tra thay thế. Xin BTC gửi file gốc để chúng tôi kiểm bằng đúng công cụ của BTC.

**6. `asr/ground_truth.json`: mô tả nói D01–D04 "kèm audio" nhưng gói nhận được không có file audio.** Các file `D01–D04.mp3` hiện có trong `asr/audio/` là **do nhóm tự tạo bằng TTS** từ transcript để chạy thử pipeline. Mô tả cũng nói giọng Bắc/Nam/Trung và có nhiễu, nhưng TTS của nhóm chỉ có một giọng sạch. Mọi con số WER của nhóm vì thế được ghi rõ "TTS sạch, giọng Bắc, n = 4 file". Xin BTC xác nhận audio chính thức của D01–D04 có được cấp trước ngày chấm không.

**7. `SAMPLE-06` call_2: `channel: "zalo_oa"` nhưng thiếu `channel_identity`.** Các kịch bản dùng kênh Zalo/Fanpage khác đều có trường này để nối danh tính. Nếu có chủ ý (khách phải đọc SĐT), xin BTC xác nhận để chúng tôi xử lý đúng.

## Nhóm C. Câu hỏi về cách chấm

**8. Cách chấm 7 kịch bản mẫu có lời khách cố định.**
- Hệ thống của nhóm có bước xác nhận đơn: hỏi đủ tên người nhận, địa chỉ, thanh toán, đọc lại đơn, chỉ tạo đơn khi khách đồng ý rõ ràng.
- Lời khách cố định trong các mẫu BTC không trả lời các câu hỏi đó (ví dụ SAMPLE-01: "giao về địa chỉ cũ nhé" mà không nêu địa chỉ), nên hệ thống không tạo đơn và TSR trên 7 mẫu chỉ còn 14,3% (cả baseline).
- Xin BTC cho biết khi chấm chính thức có dùng khách mô phỏng trả lời tiếp không, hay chấm đúng theo lời khách cố định? Nếu là loại sau, xin BTC xác nhận cách tính "tạo đơn sau khi khách xác nhận" có được coi là đạt `order.create` hay không.

## Điểm đã được BTC xử lý (không cần làm gì thêm)
`SAMPLE-03`: mã đơn `OD682761` mà `mock_tools` không thể sinh ra. Script chấm cập nhật ngày 2026-10-20 đã chấp nhận mã do `order.create` trả về. Cảm ơn BTC.

Xin chân thành cảm ơn Ban tổ chức. Nếu cần thêm log hoặc script tái hiện, nhóm sẵn sàng gửi ngay.

*Nhóm Harness Agent Call Center*
