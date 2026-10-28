"""Chuẩn hóa ngày cuộc gọi nhập tay trên UI: "2026-11-1" → "2026-11-01"; ngày không tồn tại ("2026-15-10") → None (UI báo lỗi, không chạy pipeline)."""
import re
from datetime import datetime
from typing import Optional


def normalize_call_date(text: str) -> Optional[str]:
    m = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})\s*", text or "")
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None
