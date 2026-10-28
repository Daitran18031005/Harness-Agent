"""Hợp đồng dữ liệu của API (pydantic)."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    contact_id: Optional[str] = Field(None, description="SĐT / Zalo ID / FB ID. Bỏ trống = khách ẩn danh (mã tạm theo phiên)")
    channel: str = Field("hotline", description="hotline | zalo | fanpage | web_chat")
    call_date: Optional[str] = Field(None, description="YYYY-MM-DD; bỏ trống = hôm nay")


class SessionInfo(BaseModel):
    session_id: str
    call_name: str
    turn_num: int                       # số lượt ĐÃ xử lý xong
    channel: str
    call_date: str
    customer_id: Optional[str] = None
    ended: bool = False


class ChatRequest(SessionCreate):
    session_id: Optional[str] = Field(None, description="Bỏ trống = mở phiên mới (dùng contact_id/channel/call_date của yêu cầu này)")
    message: str = Field(..., min_length=1)
    is_audio: bool = Field(False, description="Lời khách là transcript ASR (ghi customer_input_mode=asr_transcript)")


class ChatResponse(BaseModel):
    session_id: str
    call_name: str
    turn_num: int
    customer_id: Optional[str] = None
    answer: str
    trace: Dict[str, Any]               # bản rút gọn, đã che PII — xem api/sessions.py::slim_trace


class EndResponse(BaseModel):
    session_id: str
    finalized: bool
    reason: Optional[str] = None
    memory_writes: List[Dict[str, Any]] = []


class ToolLogResponse(BaseModel):
    session_id: str
    entries: List[Dict[str, Any]]


class OrdersResponse(BaseModel):
    session_id: str
    orders: List[Dict[str, Any]]
    latest: Optional[Dict[str, Any]] = None


class CallBriefResponse(BaseModel):
    session_id: str
    customer_id: Optional[str] = None
    call_brief: Dict[str, Any]


class TimelineResponse(BaseModel):
    session_id: str
    customer_id: Optional[str] = None
    episodes: List[Dict[str, Any]]
    versions: Dict[str, List[Dict[str, Any]]]


class ASRResponse(BaseModel):
    text: str
    backend: str
