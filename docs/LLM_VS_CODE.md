# Chỗ nào dùng LLM, chỗ nào dùng code (quyết định 2026-10-28)

**Hai loại "tối ưu" phải tách bạch:**
1. **Chia việc ngay từ thiết kế (làm trong lúc dựng pipeline):** với mỗi điểm cần "hiểu" đầu vào, hỏi: *có thể giao cho máy trạng thái / định dạng cứng / trường trạng thái mà vẫn đúng thực tế không?* Nếu có → code, không gọi LLM. Nếu không → LLM kèm bằng chứng nguyên văn, code kiểm chứng.
2. **Tối ưu SAU khi pipeline end-to-end xong:** cache, hạ cỡ model, song song hóa, rút gọn prompt, gộp lần gọi. Không làm trước; mọi thay đổi phải đo trước/sau.

**Tiêu chí chọn code thay LLM (đủ cả ba):** (a) đầu vào có *định dạng* kiểm chứng được (số, SKU, token) hoặc quyết định *suy ra từ trạng thái* đã biết; (b) sai thì fail-closed, không gây hậu quả tiền bạc; (c) có thể test bằng dữ liệu đa dạng, không chỉ ca đẹp. **Từ khóa tiếng Việt về ý nghĩa KHÔNG đủ (a)** — luôn rơi vào LLM.

| Điểm hiểu đầu vào | Hiện tại | Quyết định | Lý do |
|---|---|---|---|
| Quyết định **khi nào tạo đơn** (đủ trường, đọc lại, 1 lượt sau) | `OrderGate` máy trạng thái | **Code** | Chốt an toàn tiền bạc, suy ra từ trạng thái |
| Lời khách: đồng ý / từ chối / xác nhận thông tin / tên / thanh toán / chỉ-trả-lời | `reply_reader` (LLM + trích dẫn) + rào `verify` | **LLM** | Ngữ nghĩa; đo thấy regex sai ca không từ khóa. Chạy **chỉ khi vào ngữ cảnh mua** (gate có nháp, hoặc đã tra/báo giá/đặt một biến thể) — máy trạng thái bỏ lần gọi ở lượt khám phá |
| SĐT, mã đơn, số tiền, size/màu→SKU, token PII | regex/bảng (`PHONE_RE`, `extract_amounts`, `_VARIANT_RE`, `PiiVault`) | **Code** | Có định dạng; chính là cơ chế chống ảo giác (đối chiếu số trong câu trả lời với kết quả tool) |
| Chuẩn hóa số nói bằng chữ, ASR, ITN | `normalizer`, `asr_postprocess` | **Code** | Luật khóa, đo được; cần chạy offline |
| Tồn kho biến thể khách nêu | `_check_named_variants` (gọi `inventory.check` bằng code) | **Code** | Sự thật lấy từ tool, không để LLM đoán (sửa lỗi "hết hàng sai") |
| Câu LLM nói "hết hàng"/giá/khuyến mãi có đúng tool | guardrail 2b + đối chiếu số | **Code** | Kiểm chứng đối chiếu bằng chứng tool |
| Chọn tool, sản phẩm, soạn câu trả lời | LLM function-calling | **LLM** | Lõi của agent |
| Slot dễ (tên khi tự xưng, ngân sách, thời hạn…) | `extract_easy_slots` (regex) | **Giữ code tạm, ĐO** | Chạy mỗi lượt, rẻ; nhưng là từ khóa. Việc cần làm: đo độ sót trên câu khách thật; chỗ sót → chuyển sang `HardSlotExtractor` (LLM, chạy cuối cuộc, đã có) |
| Slot khó (rào cản, phản đối, ý định) | `HardSlotExtractor` (LLM, cuối cuộc gọi) | **LLM** | Ngữ nghĩa, không cần thời gian thực |
| Khách đang mặc cả (`detect_bargain`) | regex | **ĐỔI sang tín hiệu `reading.declines`** khi có (không thêm lần gọi) | Cùng ngữ nghĩa với từ chối/thương lượng giá mà bộ đọc đã trả; regex giữ làm dự phòng offline |
| Xưng hô khách tự dùng (`detect_self_honorific`) | regex | **Giữ code tạm, ĐO** | Rẻ; sai thì chỉ xưng hô lệch, không hại tiền. Đo trên câu thật; nếu sót nhiều → thêm vào lần đọc LLM (không gọi riêng) |
| Ý định "xem danh sách mẫu" (`_LISTING_RE`) | regex | **Giữ tạm, ĐO** | Chỉ ảnh hưởng gợi ý, sai không hại |
| Ý định mua ở nhánh KHÔNG có LLM (`is_order_intent` từ khóa) | regex | **Giữ** | Chỉ là đường dự phòng offline |

**Việc kế tiếp theo bảng:** (1) đo `extract_easy_slots`/`detect_self_honorific`/`_LISTING_RE` trên câu khách thật (chưa có dữ liệu); (2) nối `detect_bargain` vào `reading.declines`; (3) tối ưu loại 2 sau khi end-to-end chạy ổn.
