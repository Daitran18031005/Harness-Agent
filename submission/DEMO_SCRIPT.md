# Kịch bản video demo (5–8 phút) — một khách, hai cuộc gọi

> **Trạng thái:** video **chưa quay**. Kịch bản đã **chạy thử một lần với LLM thật** (2026-10-28, `gpt-4o-mini`, qua giao diện, trần 500 VND; tốn **168 VND** cho cả hai cuộc, 10 lượt). Cột "điểm cần chỉ ra" dưới đây là điều quan sát được ở lần chạy thử đó; câu chữ của agent thay đổi mỗi lần nên khi quay hãy dựa vào nội dung (tool, số liệu, thứ tự), không dựa vào từng chữ. Không có `OPENAI_API_KEY` thì chỉ chạy được nhánh rule-based.

## Chuẩn bị

```bash
python scripts/run_demo.py --reset --max-cost-vnd 500     # DB demo sạch, mở http://127.0.0.1:8000/ ; trần chi phí cứng, chi phí hiện ở đầu trang
```

Mở trình duyệt toàn màn hình, tab **Call Brief** ở bên phải. Bảng bên dưới là thứ tự quay.

## Cảnh 0 — Giới thiệu (0:00–0:30)

Nói: bài toán (khách gọi lại mà agent quên hết), ba thứ hệ thống làm: *nhớ qua cuộc và kênh*, *không hỏi lại*, *không bịa giá và không tạo đơn khi khách chưa đồng ý*. Chỉ nhanh vào khung chat, Call Brief, dòng thời gian bộ nhớ.

## Cảnh 1 — Cuộc gọi 1 (0:30–2:45): khách mới, chưa chốt

Chọn mẫu **Khách mới (cuộc 1)** (SĐT `0911222333`, hotline, 15/10) → **Bắt đầu cuộc gọi**. Call Brief: chưa biết khách, câu mở đầu chung.

| Lượt | Lời khách (gõ) | Điểm cần chỉ ra |
|---|---|---|
| 1 | `Chị tên Lan, chị hỏi máy lọc không khí cho phòng 25m2, nhà có bé nhỏ` | tab *Lượt vừa rồi*: tool `product.shortlist`; agent giới thiệu AirPure Y (khóa an toàn trẻ em, hợp 25 m²) và hỏi ngân sách; "Đã ghi bộ nhớ": tên, xưng hô, diện tích, có trẻ nhỏ, sản phẩm |
| 2 | `AirPure Y giá bao nhiêu, có khuyến mãi gì không em?` | `pricing.get_quote` → 5.200.000 đ, tặng màng lọc, miễn phí vận chuyển — khớp tool; ghi `price_quoted_vnd`, `promo_code`; TTFT ≈ 4–5 s |
| 3 | `Giá cao quá, để chị hỏi ông xã đã rồi gọi lại nhé` | không gọi tool; agent hẹn lại, không ép; ghi `blocker` và `objection` |

Bấm **Kết thúc cuộc gọi** → "Đã kết thúc và chốt bộ nhớ". Mở tab **Dòng thời gian bộ nhớ**: một episode `hen_goi_lai` (AirPure Y, 5.200.000 đ, rào cản "can hoi chong") và các sự thật hồ sơ (tên Lan, chị, 25 m², có trẻ nhỏ, KM GIFT-FILTER, phản đối "Giá cao quá") kèm nguồn `call_1#lượt`.

## Cảnh 2 — Cuộc gọi 2 (2:45–6:00): cùng khách, hai ngày sau

Đổi **Ngày cuộc gọi** thành 17/10, giữ nguyên SĐT `0911222333` → **Bắt đầu cuộc gọi**. **Trước khi khách nói gì**, chỉ vào Call Brief:

- "Số cuộc gọi trước: 1", sản phẩm đã tư vấn, giá đã báo, rào cản "cần hỏi chồng";
- danh sách **Không được hỏi lại** (diện tích, trẻ nhỏ…) và **Phải mang sang**;
- **Số liệu code đã tra sẵn hôm nay** (tồn kho, giá cuối, ưu đãi đang áp);
- **Câu mở đầu gợi ý** tiếp nối ("hôm 15/10 bên em có tư vấn…"). Quan sát khi chạy thử: "Số cuộc gọi trước: 1", "Không được hỏi lại: diện tích, trẻ nhỏ, sản phẩm", còn hàng 15, giá cuối 5.200.000 đ, bảo hành 24 tháng.

| Lượt | Lời khách | Điểm cần chỉ ra |
|---|---|---|
| 1 | `Alo em, chị gọi lại đây` | agent chào đúng câu tiếp nối của Call Brief (chị Lan, 15/10, AirPure Y, còn hàng, giá 5.200.000 đ, quà, bảo hành 24 tháng), **không hỏi lại** diện tích/trẻ nhỏ; không gọi tool vì số liệu đã tra sẵn |
| 2 | `Giá vẫn như hôm trước đúng không em?` | trả lời đúng 5.200.000 đ từ số liệu hôm nay (17/10), không hỏi lại sản phẩm; nếu khuyến mãi đã đổi, agent nói theo tool, không theo trí nhớ |
| 3 | `Ok chị lấy, lên đơn cho chị nhé` | **order gate** mở bằng code: agent xác nhận tên và SĐT nhận, xin địa chỉ và hình thức thanh toán; **chưa tạo đơn**, tab *Đơn hàng* còn trống |
| 4 | `Giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, thanh toán COD` | agent **đọc lại đơn** (1 AirPure Y, 5.200.000 đ, giao cho Lan, SĐT, địa chỉ, COD) và xin xác nhận; vẫn chưa có đơn. **Giữ nguyên chữ "đường", "quận"**: lần chạy thử đầu gõ "số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội" thì bộ nhận diện địa chỉ không nhận ra, agent hỏi lại địa chỉ rồi báo "chưa ghi nhận được" (hạn chế đã biết, xem cuối file) |
| 5 | `Ok đúng rồi, đồng ý` | `order.create` chạy (`price_vnd` 5.200.000, COD); tab *Đơn hàng* hiện đơn OD600001; agent báo mã đơn, tổng, ngày giao dự kiến và "nhân viên sẽ gọi xác nhận" (đơn COD trên 2 triệu) |

Nhấn mạnh: tại lượt 3–4 hệ thống **cố ý chưa tạo đơn** cho tới khi khách đồng ý rõ ràng. Độ trễ quan sát được: TTFT 2–6 s mỗi lượt (lượt đầu mỗi cuộc chậm nhất) — **chưa đạt mục tiêu 3 s**, đừng nói là đạt.

## Cảnh 3 — Kết quả đo và giới hạn (6:00–7:30)

Chiếu slide 9–14 hoặc `EVALUATION_REPORT.md` (277 kịch bản, 2 cấu hình, 1 seed): TSR 76,5 % so với baseline 66,8 %; CCR 57,2 % so với 10,7 %; khách gọi 4–5 lần: 67 % so với 40 %. Chạy trực tiếp một lệnh chấm để thấy bảng in ra: `python scripts/m1_final_report.py --root runs/m1_final2` (chấm lại từ trace, không tốn LLM). **Nói rõ chưa đạt**: RQR mới giảm 30 % (cần 40 %), Hallucination giá 14,6 % theo script (25/26 claim là giá đúng của sản phẩm khác đáp án), TTFT p95 7,5 s, guardrail kém baseline, audio/ASR mới 4 file.

## Cảnh 4 — Kết (7:30–8:00)

Ba MCP server thật, bộ nhớ có TTL và lịch sử phiên bản, order gate, guardrail; việc còn lại (dataset, ASR nhiều giọng, LLM-judge).

## Mẹo quay

- Nếu một lượt chậm (mạng), cắt bớt khi dựng; giữ nguyên `TTFT` hiển thị để không che số đo.
- Muốn quay lại từ đầu: dừng máy chủ, chạy lại `python scripts/run_demo.py --reset` (số cuộc `call_n` đếm trong tiến trình).
- Cuộc gọi 2 có thể thay bằng mẫu **Hoa quay lại — cuộc 2 (17/10)** (khách Hoa C001 có sẵn cuộc 1 trong DB demo; AirPure Y, 5.200.000đ, rào cản hỏi chồng) nếu muốn bỏ cảnh 1.

## Hạn chế thấy khi chạy thử (nên biết trước khi quay)

- **Địa chỉ viết thiếu "đường/phường/quận"** (vd "Giao cho Lan, số 12 Nguyễn Trãi, Thanh Xuân, Hà Nội") ở lần chạy thử không được nhận ra là địa chỉ: agent hỏi lại và có lần trả lời "chưa ghi nhận được địa chỉ". Đã sửa ở `src/privacy/pii_vault.py` (§ 11.100 CHECKING; có test offline, **chưa chạy lại với LLM thật**). Vẫn chỉ nhận khi địa chỉ có dấu phẩy và kết thúc bằng tên tỉnh/thành; câu demo vẫn giữ "đường", "quận" cho chắc.
- Mở lại cùng SĐT trong cùng tiến trình thì số `call_n` tăng tiếp — khởi động lại bằng `--reset` để quay lại từ đầu.
- Mới chạy trên trình duyệt tích hợp của công cụ làm việc, bằng cách gõ tự động; chưa thử trên điện thoại hay trình duyệt khác.
