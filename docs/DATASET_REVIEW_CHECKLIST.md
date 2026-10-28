# DATASET_REVIEW_CHECKLIST.md — checklist duyệt tay kịch bản (15%)

> Người duyệt chính: **chủ dự án**. Người đối chiếu: **Kiệt** (3–4 kịch bản, chọn trong số đã duyệt, ghi "đồng ý / khác ở mục nào").
> Căn cứ: [DATASET_PLAN.md § 9](DATASET_PLAN.md), luật máy P1–P5 (`src/dataset/rules.py`) và S1–S14 ([DATASET_TEXT_PLAN.md § 5](DATASET_TEXT_PLAN.md)). **Máy đã kiểm cú pháp/luật; người duyệt chỉ kiểm cái máy không kiểm được: có giống người thật, có đúng nghiệp vụ không.** Mỗi kịch bản ~15–20 phút.

## 0. Chọn kịch bản để duyệt (~13, theo thứ tự ưu tiên)

1. Mọi kịch bản **validator gắn lỗi hoặc cảnh báo** (kể cả đã sinh lại).
2. **Ca khó** — ít nhất 1 kịch bản mỗi nhãn: `doi_y_giua_cuoc`, `mau_thuan_phien_truoc` (cả hai loại: giá khác kênh / thông tin khác lưu), `khuyen_mai_het_han`, `hoi_ngoai_tai_lieu_*`, `mac_ca`, `tu_choi_giua_gate`, `hoan_giua_gate`, `het_hang_bien_the`, `tu_nhan_khach_cu_chua_sdt`, `so_noi_bang_chu`.
3. **Đa kênh** — ít nhất 3 kịch bản (1 loại 3 kênh).
4. Còn lại: lấy ngẫu nhiên (seed ghi lại) cho đủ 15% và đủ 3 ngành, cả giọng miền Bắc/Nam.
5. **Trong số duyệt: tối thiểu 60% là tập dev, ≥ 1 kịch bản held-out** để kiểm chia tập; held-out chỉ đọc, **không chỉnh luật/prompt dựa trên held-out**.

Ghi vào bảng ở cuối: id, người duyệt, kết quả (✔ giữ / ✎ sửa khung / ✘ loại + sinh lại), ghi chú.

## 1. Mỗi kịch bản — hỏi 8 mục (tick từng mục)

**A. Tình huống có thật không**
- [ ] Khách nói như người gọi điện/nhắn tin thật (không quá lịch sự, đều đều, lặp mẫu câu; có ngập ngừng/ngắt lời/cộc lốc đúng persona).
- [ ] Tình huống hợp lý với ngành hàng (nhu cầu, giá, phụ kiện đúng loại hàng; không nhầm sản phẩm).
- [ ] Hotline là lời nói chuẩn; teencode/viết tắt **chỉ** ở kênh chat (P4).

**B. Đúng nghiệp vụ**
- [ ] Mọi giá, khuyến mãi, tồn kho, phí, ngày giao trong lời **agent** khớp tình huống (số do code điền — kiểm có ô trống thừa/lệch không).
- [ ] Agent trả lời **đủ** câu khách vừa hỏi (P2) và không hứa thứ chính sách không cho (đổi trả, giảm giá, hoàn tiền).
- [ ] Lời khách **không tiết lộ** thông tin ngoài cốt truyện (P1) — nhất là SĐT, ngân sách, size, giá đối thủ.

**C. Đúng nhãn và đáp án** (đối chiếu với khung/`ground_truth_facts`)
- [ ] `hard_case` đúng loại thật sự xảy ra trong lời thoại (không gắn nhãn cho kịch bản không có tình huống đó).
- [ ] `facts_established` của từng cuộc **xuất hiện trong lời khách** cuộc đó (S3); `must_carry_over`/`must_not_ask` hợp lý (S6).
- [ ] `success_if` chấm được bằng trace: đúng tool, đúng SKU/giá, `forbidden_claims` đúng chỗ.

**D. Order gate** (kịch bản có đơn)
- [ ] Khách trả lời được câu hỏi/xác nhận của gate; có bước **đọc lại đơn** rồi khách **đồng ý rõ ràng ở lượt ngay sau** (P5). Khách từ chối/hoãn thì **không** có `order.create`.

**E. Nối nhiều phiên / nhiều kênh**
- [ ] Ngày các cuộc tăng dần, khoảng cách ngày hợp lý với KM/đơn hàng.
- [ ] Đổi kênh: có lượt khách đọc SĐT để nối danh tính (S8); **khách tự nhận khách cũ nhưng chưa có SĐT** thì không được nối theo lời khai.
- [ ] Khách **mâu thuẫn**: thông tin mới thật sự khác thông tin đã lưu, và agent phải xử lý (xin xác nhận / cập nhật) thay vì hỏi lại từ đầu.

**F. Riêng từng loại ca khó**
- [ ] `mac_ca`: giá khách đề nghị khác bảng giá; không có đơn ở giá khách đòi.
- [ ] `het_hang_bien_the`: tồn kho trong khung đúng biến thể (size/màu); lời agent không nói "hết hàng" khi biến thể còn.
- [ ] `so_noi_bang_chu`: SĐT/số tiền đọc bằng chữ đúng, ITN trả lại đúng số; không còn chữ số trong `text_spoken` (S12).
- [ ] `hoi_ngoai_tai_lieu_*`: tài liệu **thật sự** không có câu trả lời; agent không bịa.

**G. Quyền riêng tư**
- [ ] SĐT/địa chỉ/tên thuộc dải giả (S9); không trùng người thật nào bạn biết; không số thẻ/CCCD thật.

**H. Quyết định**
- [ ] ✔ Giữ nguyên · ✎ Sửa **khung/luật** rồi sinh lại (không sửa tay lời thoại để "đẹp" — mọi chỉnh sửa phải tái lập bằng code) · ✘ Loại.

## 2. Quy tắc để duyệt không làm hỏng dữ liệu

1. **Không sửa tay file lời thoại.** Muốn đổi → sửa khung hoặc luật (`src/dataset/`) rồi sinh lại đúng kịch bản (`--ids`), ghi lý do vào `docs/DATASET_CHANGELOG.md`.
2. Sửa luật sau khi xem một kịch bản thì **chạy lại validator cho cả bộ**, báo số lỗi trước/sau.
3. Mỗi lần sinh lại tính vào **trần cứng 10.000 VND**; ghi chi phí.
4. Kiệt đối chiếu **độc lập** trước khi xem ghi chú của người duyệt chính; chỗ hai người khác nhau ghi riêng, tính tỷ lệ đồng ý (nếu < 80% thì xem lại tiêu chí trước khi duyệt tiếp).

## 3. Bảng ghi kết quả

| Kịch bản | Tập (dev/held-out) | Loại ca | Người duyệt | A | B | C | D | E | F | G | Kết quả | Ghi chú / lỗi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | | |
