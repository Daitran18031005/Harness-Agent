"""
Khách hợp tác với ORDER GATE (CHỈ để đánh giá — cờ `run_eval.py --gate-assist`).

Kịch bản BTC có lời khách CỐ ĐỊNH (2–4 lượt) nên không thể trả lời các câu hỏi/xác nhận/đọc lại đơn của order gate → không đơn nào được tạo. Để đo gate
trên LLM thật mà không sửa kịch bản BTC, runner chèn thêm lượt khách mô phỏng NGAY SAU lượt bị chặn (trước lượt kịch bản kế tiếp): trả lời đúng điều
gate hỏi bằng dữ liệu mẫu cố định, hoặc đồng ý rõ ràng khi agent đọc lại đơn. Lượt chèn được gắn `_injected: true` trong trace và KHÔNG phải số liệu nộp.
"""
from typing import Any, Dict, Optional

SAMPLE_ADDRESS = "giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội"
MAX_INJECTED_PER_CALL = 6


def assist_reply(event: Optional[Dict[str, Any]], recipient_name: str = "") -> Optional[str]:
    """Lời khách mô phỏng cho sự kiện gate `event` (None = không chèn)."""
    if not event or event.get("allow"):
        return None
    action = event.get("action")
    if action == "readback":
        return "Ok em, đồng ý nhé."
    missing, to_confirm = set(event.get("missing") or []), set(event.get("to_confirm") or [])
    parts = []
    if "recipient_name" in missing:
        if not recipient_name:
            return None
        parts.append(f"Tên người nhận là {recipient_name}")
    if "address" in missing:
        parts.append(SAMPLE_ADDRESS)
    if "payment" in missing:
        parts.append("thanh toán COD")
    if missing - {"recipient_name", "address", "payment"}:
        return None                                   # thiếu size/màu/SĐT nhận…: không có dữ liệu mẫu → dừng chèn
    if not parts and to_confirm:
        return "Đúng rồi em."
    if not parts:
        return None
    return ("Đúng rồi, " if to_confirm else "") + ", ".join(parts) + "."
