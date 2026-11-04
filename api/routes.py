"""Các endpoint của API (bước 17). Handler là hàm đồng bộ (FastAPI chạy chúng trong threadpool); mọi lượt đi qua `pipeline.lock` nên các phiên đồng thời
được xử lý TUẦN TỰ — đánh đổi có chủ ý: giao dịch theo lượt của bộ nhớ (`begin_turn` … `commit_turn`) là MỘT cho cả kho (CHECKING § 11.x), nên hai lượt xen kẽ
sẽ chốt/xóa nhật ký ghi của nhau. Hai phiên chạy "song song" nghĩa là xen kẽ theo lượt, không lẫn dữ liệu; lượt dài (LLM) của phiên này làm phiên kia chờ."""
import logging
import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse

from src.channels.normalizer import InputChannel
from src.common.dates import normalize_call_date
from monitoring.metrics import observe_turn
from src.llm.cost_tracker import BudgetExceeded

from .schemas import (ASRResponse, CallBriefResponse, ChatRequest, ChatResponse, EndResponse, OrdersResponse, SessionCreate, SessionInfo,
                      TimelineResponse, ToolLogResponse)
from .scrub import scrub
from .sessions import ORDER_TOOLS, Session, slim_trace, tool_entry

logger = logging.getLogger("harness.api")
router = APIRouter()

# Thiếu model ASR thì trả lỗi, KHÔNG tải: faster-whisper (đường dự phòng) sẽ tải model từ Hugging Face nếu chưa có trong cache. Muốn cho phép: HF_HUB_OFFLINE=0.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
ASR_MAX_BYTES = 25 * 1024 * 1024
ASR_SUFFIXES = (".wav", ".mp3")


def _pipeline(request: Request):
    return request.app.state.pipeline


def _session(request: Request, session_id: str) -> Session:
    s = request.app.state.sessions.get(session_id)
    if s is None:
        raise HTTPException(404, f"Không có phiên '{session_id}'")
    return s


def _channel(s: Session) -> InputChannel:
    return InputChannel(s.channel)


def _open_session(request: Request, body: SessionCreate) -> Session:
    try:
        InputChannel(body.channel)
    except ValueError:
        raise HTTPException(422, f"channel phải thuộc {[c.value for c in InputChannel]}")
    call_date = normalize_call_date(body.call_date) if body.call_date else date.today().isoformat()
    if call_date is None:
        raise HTTPException(422, "call_date không hợp lệ (cần YYYY-MM-DD)")
    p, store = _pipeline(request), request.app.state.sessions
    contact = (body.contact_id or "").strip() or f"anon-{uuid.uuid4().hex[:12]}"
    with p.lock:
        old = store.active_for(contact)
        if old is not None:                          # một liên hệ chỉ có MỘT cuộc mở: phiên mới chốt phiên cũ (pipeline cũng chỉ giữ một cuộc mở cho mỗi liên hệ)
            p.end_call(contact, trigger="end")
            old.ended = True
        identity, brief = p.preview_brief(contact, InputChannel(body.channel), call_date)
        s = store.create(contact, body.channel, call_date, previous_calls=brief.previous_calls_count)
        s.customer_id = identity.customer_id
    return s


@router.get("/health")
def health(request: Request) -> Dict[str, Any]:
    llm = _pipeline(request).llm_client
    tracker = getattr(llm, "cost_tracker", None)
    return {"status": "ok", "llm": bool(getattr(llm, "available", False)),
            "spent_vnd": round(tracker.spent_vnd(), 1) if tracker else None, "cap_vnd": getattr(tracker, "hard_cap_vnd", None)}


@router.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request):
    """Số đo cho Prometheus/Grafana (monitoring/): độ trễ, chi phí, tool, guardrail, order gate của các lượt đã chạy qua API này."""
    reg = request.app.state.metrics
    tracker = getattr(_pipeline(request).llm_client, "cost_tracker", None)
    if tracker is not None:
        reg.set("llm_spent_vnd", round(tracker.spent_vnd(), 2))
        if getattr(tracker, "hard_cap_vnd", None) is not None:
            reg.set("llm_cap_vnd", tracker.hard_cap_vnd)
    return PlainTextResponse(reg.render(), media_type="text/plain; version=0.0.4")


@router.post("/sessions", response_model=SessionInfo)
def create_session(body: SessionCreate, request: Request):
    return _open_session(request, body).info()


@router.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session(session_id: str, request: Request):
    return _session(request, session_id).info()


@router.post("/sessions/{session_id}/end", response_model=EndResponse)
def end_session(session_id: str, request: Request):
    """Kết thúc cuộc gọi: chốt bộ nhớ (episode, rào cản, phản đối) như nút "Kết thúc cuộc gọi" của UI."""
    s, p = _session(request, session_id), _pipeline(request)
    with p.lock:
        if s.ended:
            return {"session_id": s.session_id, "finalized": False, "reason": "phiên đã kết thúc", "memory_writes": []}
        start = len(p.mcp_gateway.audit_log)
        res = p.end_call(s.contact_id, trigger="end")
        s.ended = True
        s.tool_log += [tool_entry(a) for a in p.mcp_gateway.audit_log[start:]]
    return {"session_id": s.session_id, "finalized": res["finalized"], "reason": res.get("reason"),
            "memory_writes": [{"key": w.get("key"), "op": w.get("op"), "source": w.get("source")} for w in res.get("memory_writes", [])]}


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request):
    """Một lượt của khách. Không có `session_id` = mở phiên mới. API cấp call_name/turn_num; trace trả về là bản rút gọn đã che PII."""
    p = _pipeline(request)
    s = _session(request, body.session_id) if body.session_id else _open_session(request, body)
    with p.lock:
        if s.ended:
            raise HTTPException(409, "Phiên đã kết thúc — mở phiên mới (POST /sessions)")
        start = len(p.mcp_gateway.audit_log)
        try:
            result = p.handle_incoming_request(body.message, s.contact_id, _channel(s), is_audio=body.is_audio, call_date=s.call_date,
                                               scenario_id="API-SESSION", call_name=s.call_name, turn_num=s.turn_num + 1)
        except BudgetExceeded:                       # trần chi phí cứng (API_MAX_COST_VND): BaseException nên không rơi vào nhánh dưới
            raise HTTPException(402, "Đã chạm trần chi phí LLM của máy chủ demo — lượt không được ghi vào bộ nhớ")
        except Exception as e:                       # chi tiết (có thể chứa PII) chỉ vào log máy chủ, không vào phản hồi
            logger.exception("[api] lượt %s#%s lỗi", s.call_name, s.turn_num + 1)
            raise HTTPException(500, f"Pipeline lỗi ({type(e).__name__}) — lượt không được ghi vào bộ nhớ")
        s.turn_num += 1
        s.customer_id = result.get("customer_id") or s.customer_id
        s.tool_log += [tool_entry(a) for a in p.mcp_gateway.audit_log[start:]]
        try:
            observe_turn(request.app.state.metrics, result["trace"], source="api", config="full")
        except Exception:                            # giám sát không bao giờ được làm hỏng một lượt chat
            logger.warning("[api] không ghi được số đo giám sát", exc_info=True)
        return {"session_id": s.session_id, "call_name": s.call_name, "turn_num": s.turn_num, "customer_id": s.customer_id,
                "answer": result["answer"], "trace": slim_trace(result["trace"])}


@router.get("/call-brief", response_model=CallBriefResponse)
def call_brief(request: Request, session_id: str = Query(...)):
    s = _session(request, session_id)
    _, brief = _pipeline(request).preview_brief(s.contact_id, _channel(s), s.call_date)
    return {"session_id": s.session_id, "customer_id": brief.customer_id, "call_brief": scrub(brief.to_dict())}


@router.get("/memory/timeline", response_model=TimelineResponse)
def memory_timeline(request: Request, session_id: str = Query(...)):
    s = _session(request, session_id)
    tl = _pipeline(request).timeline(s.customer_id)
    return {"session_id": s.session_id, "customer_id": s.customer_id,
            "episodes": [scrub(asdict(e)) for e in tl["episodes"]],
            "versions": {k: [scrub(asdict(f)) for f in facts] for k, facts in tl["versions"].items()}}


@router.get("/tools/log", response_model=ToolLogResponse)
def tools_log(request: Request, session_id: str = Query(...), limit: int = Query(200, ge=1, le=1000)):
    s = _session(request, session_id)
    return {"session_id": s.session_id, "entries": s.tool_log[-limit:]}


@router.get("/orders", response_model=OrdersResponse)
def orders(request: Request, session_id: str = Query(...)):
    """Đơn hàng / lịch gọi lại đã tạo trong phiên (từ nhật ký tool): order.create, order.update, schedule.callback."""
    s = _session(request, session_id)
    found = [e for e in s.tool_log if e["tool"] in ORDER_TOOLS]
    return {"session_id": s.session_id, "orders": found, "latest": found[-1] if found else None}


@router.post("/asr", response_model=ASRResponse)
def asr(file: UploadFile = File(...)):
    """Audio (.wav/.mp3) → transcript bằng src/channels/offline_asr.py. Chỉ dùng model đã có trên máy; thiếu model → 503, không tải."""
    from src.channels import offline_asr
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in ASR_SUFFIXES:
        raise HTTPException(415, f"Chỉ nhận {'/'.join(ASR_SUFFIXES)}")
    data = file.file.read(ASR_MAX_BYTES + 1)
    if len(data) > ASR_MAX_BYTES:
        raise HTTPException(413, f"File quá lớn (tối đa {ASR_MAX_BYTES // 1024 // 1024} MB)")
    if not offline_asr.is_available():
        raise HTTPException(503, "ASR không khả dụng: thiếu model/thư viện (xem README § ASR). API không tự tải model — hãy đặt model vào model_ASR/ hoặc nhập tay.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
    try:
        text = offline_asr.transcribe_audio(tmp.name)
    finally:
        os.unlink(tmp.name)
    if not text:
        raise HTTPException(422, "Không nhận ra lời nói trong file (hoặc ASR lỗi) — hãy nhập tay.")
    return {"text": text, "backend": offline_asr._backend_name()}
