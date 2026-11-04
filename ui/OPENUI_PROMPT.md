# Đề bài sinh giao diện bằng W&B OpenUI (chuẩn bị 2026-11-04)

Dán nguyên văn khối "Prompt" vào OpenUI (chọn framework **HTML + Tailwind**, hoặc React nếu muốn), sinh xong lưu thành `ui/openui/index.html`, rồi nối API như mục "Ghép với backend". Giao diện hiện tại `ui/index.html` (dựng tay) vẫn là bản dự phòng.

## Prompt

Thiết kế một trang web một trang, tiếng Việt, giao diện sáng/tối theo hệ thống, dùng cho nhân viên telesale thương mại điện tử. Bố cục hai cột trên desktop, một cột trên điện thoại.

**Thanh trên cùng:** tên "Harness Agent — Call Center Telesale"; chỉ báo trạng thái máy chủ (xanh/đỏ), chi phí LLM đã tiêu so với trần (ví dụ "123 / 5.000 VND").

**Hàng điều khiển cuộc gọi:** ô SĐT/ID khách, chọn kênh (hotline, zalo, fanpage, web_chat), chọn ngày cuộc gọi, nút "Bắt đầu cuộc gọi" và nút "Kết thúc cuộc gọi" (nút kết thúc bị khóa khi chưa có phiên). Hiển thị mã phiên, "call_2" và số lượt.

**Cột trái — khung hội thoại:** danh sách tin nhắn dạng bong bóng (khách bên phải, agent bên trái, có giờ), ô nhập tin, nút Gửi (Enter để gửi), nút tải file ghi âm (.wav/.mp3) để nhận dạng giọng nói và nút micro. Có trạng thái "agent đang trả lời…" và thông báo lỗi rõ ràng (402 hết hạn mức, 500 lỗi hệ thống).

**Cột phải — 5 tab:**
1. **Call Brief:** thẻ tóm tắt khách gọi lại: tên/xưng hô, câu mở đầu gợi ý, danh sách "không được hỏi lại" (chip), "cần mang sang", cảnh báo khuyến mãi hết hạn (nền vàng), số cuộc trước.
2. **Dòng thời gian bộ nhớ:** các cuộc trước theo thứ tự thời gian và các fact (khóa, giá trị, nguồn, hiệu lực); fact bị thay thế gạch ngang và có nhãn "đã thay".
3. **Nhật ký tool:** bảng tên tool, thời gian (ms), kết quả (nhãn ok/lỗi), bấm để mở JSON.
4. **Đơn hàng:** thẻ đơn đã tạo/cập nhật và lịch gọi lại (mã đơn, sản phẩm, tổng tiền VND định dạng 4.890.000đ, thanh toán, dự kiến giao).
5. **Trace:** TTFT/Total (ms) từng lượt, số vòng LLM, chi phí lượt, số câu hỏi/claims.

Phong cách: gọn, dày thông tin, màu nhấn xanh dương; mọi chuỗi từ máy chủ phải được hiển thị bằng textContent (không innerHTML).

## Hợp đồng API (cùng origin, `uvicorn api.app:app`)

| Việc | Gọi | Dữ liệu |
|---|---|---|
| trạng thái + chi phí | `GET /health` | `{status, llm, spent_vnd, cap_vnd}` |
| mở phiên | `POST /sessions` | `{contact_id?, channel, call_date?}` → `{session_id, call_name, turn_num, ...}` |
| một lượt | `POST /chat` | `{session_id, message, is_audio?}` → `{answer, turn_num, trace{latency{ttft_ms,total_ms}, tool_calls[], llm_cost, questions, claims, ...}}` |
| Call Brief | `GET /call-brief?session_id=` | `{call_brief{...}}` |
| bộ nhớ | `GET /memory/timeline?session_id=` | `{episodes[], versions{khóa:[fact]}}` |
| nhật ký tool | `GET /tools/log?session_id=` | `{entries[{tool, duration_ms, result, ...}]}` |
| đơn hàng | `GET /orders?session_id=` | `{orders[], latest}` |
| kết thúc | `POST /sessions/{id}/end` | `{finalized, memory_writes[]}` |
| giọng nói | `POST /asr` (multipart `file`) | `{text, backend}` |

Lỗi: 402 (chạm trần chi phí), 404 (không có phiên), 409 (phiên đã kết thúc), 422 (tham số sai), 503 (ASR không khả dụng).

## Ghép với backend (sau khi sinh)
1. Thay mọi dữ liệu mẫu/hard-code bằng `fetch` tới các endpoint trên; sau mỗi lượt `/chat` gọi lại 4 endpoint của các tab.
2. Đặt file tại `ui/openui/index.html`; API đang phục vụ thư mục `ui/` ở `/ui/` nên mở `http://127.0.0.1:8000/ui/openui/`.
3. Thêm vào `tests/test_api.py` hai test tương tự test của `/ui/` (trang `/ui/openui/` tải được, có các endpoint trên, và không chứa `innerHTML`), rồi chạy thử theo `submission/DEMO_SCRIPT.md`.
