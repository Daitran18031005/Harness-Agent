"""
CallCenterHarnessPipeline: Điểm tập hợp toàn bộ pipeline runtime
Khởi tạo và kết nối:
- RequestNormalizer (Audio/Text -> Normalized Text & Entities)
- IdentityResolver (Gọi CRM qua MCP)
- CallBriefBuilder (Profile + Episodic -> Call Brief)
- MCPToolGateway (CRM, Catalog/Pricing, Order)
- Bộ nhớ (Working, Episodic, Profile, Semantic RAG) qua MCP server `mcp-memory` — nơi ghi duy nhất; mỗi thành phần có view với tên caller riêng
- A2AAgentNetwork: các module chuyên biệt CHẠY TRONG CÙNG TIẾN TRÌNH (tên "A2A" là lịch sử; KHÔNG dùng giao thức Agent-to-Agent) — chỉ phục vụ nhánh dự phòng khi mất LLM
- GuardrailAndFallback (Policy & Price check)
- HarnessOrchestrator (Core State Machine)
- TurnTracer (Trace JSONL logging)
"""
from typing import Dict, Any, Optional
import logging
import os
import threading
import time
from dotenv import load_dotenv
from src.channels.normalizer import RequestNormalizer, InputChannel, NormalizedTurn
from src.identity.resolver import IdentityResolver, ResolvedIdentity
from src.tools.mcp_gateway import MCPToolGateway, CRMTool, CatalogPricingTool, OrderCallbackTool
from src.memory.remote import create_memory_service
from src.memory.episodic import EpisodeRecord
from src.harness.call_brief import CallBriefBuilder, CallBrief
from src.agents.specialists import A2AAgentNetwork
from src.harness.guardrail import GuardrailAndFallback
from src.harness.orchestrator import HarnessOrchestrator
from src.llm.client import LLMClient
from src.tracing.tracer import TurnTracer, measure_latency, monitoring_extras

load_dotenv()

logger = logging.getLogger("harness.pipeline")


class CallCenterHarnessPipeline:
    def __init__(self, trace_file: str = "runs/ui_session.jsonl", db_path: Optional[str] = None):
        # db_path=None -> DB mặc định (UI/production); demo (main.py) truyền DB riêng data/demo.db
        # Chạy thật: bộ nhớ nằm trong MCP server `mcp-memory` (tiến trình riêng, nơi ghi duy nhất). MEMORY_TRANSPORT=local|inproc để chạy cùng tiến trình (debug).
        # `self.memory` là view của LÕI điều phối (mở/đóng kho, giao dịch theo lượt, xóa khách); các thành phần khác nhận view riêng — server kiểm quyền theo tên caller.
        self.memory = create_memory_service(db_path=db_path, transport=os.environ.get("MEMORY_TRANSPORT") or "stdio", caller="HarnessCore")
        # Lõi dùng tool thấp (mở/hủy lượt, liên kết định danh); mọi việc đọc/ghi bộ nhớ của cuộc gọi đi qua 6 tool cao dưới tên caller của từng thành phần.
        # Ghi bối cảnh định danh (kênh, xưng hô, gộp hồ sơ) cũng là ghi bộ nhớ của lượt nên đi qua view HarnessOrchestrator (commit_turn chỉ cấp cho caller này).
        orchestrator_memory = self.memory.as_caller("HarnessOrchestrator")
        self.identity_memory = orchestrator_memory
        self.normalizer = RequestNormalizer()
        self.crm_tool = CRMTool()
        self.catalog_tool = CatalogPricingTool()
        self.order_tool = OrderCallbackTool()

        # Chạy thật: mỗi MCP server là MỘT tiến trình riêng (stdio). Đặt MCP_TRANSPORT=inproc để chạy cùng tiến trình (debug).
        self.mcp_gateway = MCPToolGateway(transport=os.environ.get("MCP_TRANSPORT") or "stdio")
        self.identity_resolver = IdentityResolver(self.mcp_gateway, identity_backend=self.memory.backend)
        self.call_brief_builder = CallBriefBuilder(self.memory.as_caller("CallBriefBuilder"), tool_gateway=self.mcp_gateway)   # thiếu → câu chào đọc mã SKU rút gọn thay tên sản phẩm
        self.a2a_network = A2AAgentNetwork(orchestrator_memory)
        self.guardrail = GuardrailAndFallback()
        self.llm_client = LLMClient()
        self.orchestrator = HarnessOrchestrator(
            self.mcp_gateway, orchestrator_memory, self.a2a_network, self.guardrail, llm_client=self.llm_client
        )
        self.tracer = TurnTracer(trace_file=trace_file)
        self._open_calls: Dict[str, tuple] = {}   # contact_id -> (customer_id, call_date, call_name, channel) của cuộc gọi đang mở
        # Một pipeline được dùng chung cho nhiều phiên UI (mỗi phiên một luồng) và cho bộ quét nền: giao dịch theo lượt (begin_turn … commit) của bộ nhớ là MỘT
        # cho cả kho, nên các lượt phải chạy lần lượt — nếu xen kẽ thì lượt này chốt/xóa nhật ký ghi của lượt kia.
        self._lock = threading.RLock()
        self._sweeper: Optional[threading.Thread] = None
        self._sweeper_stop = threading.Event()
        self._closed = False

    def handle_incoming_request(self, raw_input: str, contact_id: str, channel: InputChannel = InputChannel.HOTLINE,
                                is_audio: bool = False, call_date: str = "2026-10-15",
                                scenario_id: str = "PROD-LIVE", call_name: str = "call_1", turn_num: int = 1) -> Dict[str, Any]:
        """
        Xử lý 1 request từ lúc nhận input đến khi trả về Answer và lưu Trace
        """
        # Giao dịch DB theo lượt: begin_turn (lõi) mở, orchestrator.commit_turn() chốt; lỗi giữa chừng -> abort_turn hủy các ghi của lượt.
        with self._lock:
            # Cùng khách mà đổi ngày/số cuộc gọi = BẮT ĐẦU cuộc gọi mới: chốt cuộc cũ trước (episode, blocker, slot khó), không để nó mở treo tới khi quá hạn.
            prev = self._open_calls.get(contact_id)
            if prev and (prev[1] != call_date or prev[2] != call_name):
                self.end_call(contact_id, trigger="end")
            self.memory.begin_turn(f"{call_name}#turn{turn_num}", call_date=call_date, channel=channel.value)
            try:
                return self._process(raw_input, contact_id, channel, is_audio, call_date, scenario_id, call_name, turn_num)
            except Exception:
                self.memory.abort_turn()
                raise

    def _process(self, raw_input, contact_id, channel, is_audio, call_date, scenario_id, call_name, turn_num) -> Dict[str, Any]:
        t_start = time.perf_counter()

        # Bước 1: Tiếp nhận & Chuẩn hóa
        turn: NormalizedTurn = self.normalizer.normalize(
            raw_text=raw_input,
            channel=channel,
            contact_id=contact_id,
            is_audio=is_audio,
            reference_date=call_date
        )

        # Bước 2–3: Identity Resolution + Call Brief (đo từ lúc nhận diện khách tới khi Brief sẵn sàng)
        t_brief = time.perf_counter()
        identity: ResolvedIdentity = self.identity_resolver.resolve(turn, memory=self.identity_memory)
        brief: CallBrief = self.call_brief_builder.build(identity, current_call_date=call_date)
        brief_ms = int(round((time.perf_counter() - t_brief) * 1000))

        # Bước 4: Harness Orchestrator (LLM + tool qua MCP -> order gate -> guardrail -> bộ nhớ)
        final_answer, tool_calls, meta = self.orchestrator.process_turn(
            turn=turn,
            brief=brief,
            current_date=call_date,
            call_name=call_name
        )
        if identity.customer_id and not identity.is_ambiguous:
            self._open_calls[contact_id] = (identity.customer_id, call_date, call_name, channel.value)
        lat = measure_latency(t_start, time.perf_counter(), meta.get("llm_timing"))

        # Bước 5: Ghi nhận Turn Trace
        trace_record = self.tracer.log(
            run_id="RUN-LIVE-001",
            config="full",
            scenario_id=scenario_id,
            call=call_name,
            turn=turn_num,
            customer_text=turn.normalized_text,
            agent_text=final_answer,
            questions=meta["questions"],
            claims=meta["claims"],
            facts_used=meta["facts_used"],
            tool_calls=tool_calls,
            ttft_ms=lat["ttft_ms"],
            total_ms=lat["total_ms"],
            llm_cost=meta.get("llm_usage"),
            call_brief_latency_ms=brief_ms if (turn_num == 1 and call_name != "call_1") else None,
            memory_writes=self.orchestrator.commit_turn(),
            customer_input_mode="asr_transcript" if is_audio else "clean",
            extra={k: v for k, v in (("memory_extractor", meta.get("memory_extraction")), ("order_gate", meta.get("order_gate")), ("reply_reading", meta.get("reply_reading")), ("gate_open", meta.get("gate_open")), ("handoff_check", meta.get("handoff_check")), ("precomputed", meta.get("precomputed"))) if v} | monitoring_extras(meta) or None
        )

        return {
            "customer_id": identity.customer_id,
            "normalized_input": turn.normalized_text,
            "call_brief": brief.to_dict(),
            "answer": final_answer,
            "tool_calls": tool_calls,
            "trace": trace_record
        }

    # ------------------------------------------------------------------ truy vấn chỉ-đọc cho API (bước 17)
    @property
    def lock(self) -> threading.RLock:
        """Khóa lượt của pipeline: API giữ khóa quanh [đọc nhật ký tool → chạy lượt → đọc lại] để tách chính xác nhật ký tool của từng phiên."""
        return self._lock

    def preview_brief(self, contact_id: str, channel: InputChannel = InputChannel.HOTLINE, call_date: str = "2026-10-15"):
        """Nhận diện khách + dựng Call Brief mà KHÔNG bắt đầu lượt (như tab Call Brief của UI). Trả (ResolvedIdentity, CallBrief)."""
        with self._lock:
            turn = self.normalizer.normalize(raw_text="", channel=channel, contact_id=contact_id, reference_date=call_date)
            identity = self.identity_resolver.resolve(turn)
            return identity, self.call_brief_builder.build(identity, current_call_date=call_date)

    def timeline(self, customer_id: str) -> Dict[str, Any]:
        """Dòng thời gian bộ nhớ của khách: {"episodes": [...], "versions": {key: [ProfileFact]}} (chỉ đọc, qua view `Operator`)."""
        with self._lock:
            return self.memory.as_caller("Operator").timeline(customer_id)

    # ------------------------------------------------------------------ kết thúc cuộc gọi (bước 9)
    def end_call(self, contact_id: str, trigger: str = "end") -> Dict[str, Any]:
        """Chốt cuộc gọi đang mở của contact: trigger 'end' (khách/agent kết thúc) hoặc 'timeout' (cuộc gọi bị ngắt).
        Ghi episode + trích slot khó bằng LLM (≤ 1 lần, chỉ phần hội thoại mới). 'handoff' tự chạy trong process_turn."""
        with self._lock:
            info = self._open_calls.pop(contact_id, None)
            if info is None:
                return {"finalized": False, "reason": "không có cuộc gọi đang mở"}
            customer_id, call_date, call_name, channel = info
            self.memory.begin_turn(f"{call_name}#{trigger}", call_date=call_date, channel=channel)
            try:
                result = self.orchestrator.finalize_call(customer_id, call_date, call_name, channel, trigger=trigger)
                writes = self.orchestrator.commit_turn()
            except Exception:
                self.memory.abort_turn()
                raise
            return {"finalized": True, "trigger": trigger, "llm_called": result.llm_called, "llm_cost": result.usage,
                    "episode": result.episode, "memory_writes": writes}

    def sweep_idle(self, idle_seconds: float = 1800.0, now: Optional[float] = None) -> int:
        """Chốt (timeout) các cuộc gọi không có lượt mới quá idle_seconds. Trả về số cuộc gọi đã chốt.
        Mỗi cuộc gọi mở được chốt qua `end_call(trigger="timeout")` — có giao dịch riêng và provenance đúng cuộc gọi đó (không ghi tự do ngoài giao dịch)."""
        now = time.monotonic() if now is None else now
        done = 0
        with self._lock:
            for contact, (cid, date, _, _) in list(self._open_calls.items()):
                last = self.orchestrator.last_activity(f"SESS-{cid}-{date}")
                if last is None or now - last >= idle_seconds:
                    self.end_call(contact, trigger="timeout")
                    done += 1
            done += len(self.orchestrator.sweep_idle(now=now, idle_seconds=idle_seconds))      # phiên không nằm trong _open_calls (vd khách chưa xác minh danh tính)
        return done

    def start_idle_sweeper(self, idle_seconds: float = 1800.0, interval_s: float = 60.0) -> threading.Thread:
        """Bật luồng nền định kỳ gọi `sweep_idle`. Khách đóng tab giữa chừng thì không còn lời gọi nào của họ nữa — chỉ một bộ quét nền mới chốt được cuộc gọi
        (episode `ngat_cuoc`, trích slot khó, giải phóng bảng token PII). Gọi nhiều lần chỉ có MỘT luồng; dừng khi `close()`."""
        with self._lock:
            if self._sweeper is not None and self._sweeper.is_alive():
                return self._sweeper

            def loop() -> None:
                while not self._sweeper_stop.wait(interval_s):
                    try:
                        self.sweep_idle(idle_seconds=idle_seconds)
                    except Exception:                                     # một lần quét lỗi không được giết bộ quét
                        logger.exception("[pipeline] sweep_idle lỗi — thử lại ở lần quét sau")

            self._sweeper_stop.clear()
            self._sweeper = threading.Thread(target=loop, name="idle-sweeper", daemon=True)
            self._sweeper.start()
            return self._sweeper

    def close(self) -> None:
        """Dừng bộ quét nền, đóng DB (chốt giao dịch + checkpoint WAL) và đóng cổng MCP (kết thúc các tiến trình MCP server con). Gọi nhiều lần không lỗi."""
        if self._closed:
            return
        self._sweeper_stop.set()
        sweeper = self._sweeper
        if sweeper is not None and sweeper is not threading.current_thread():
            sweeper.join(timeout=10)
        with self._lock:
            self._closed = True
            self.memory.close()
            self.mcp_gateway.close()
