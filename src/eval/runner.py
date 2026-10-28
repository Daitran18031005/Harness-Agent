"""
Scenario Runner: chạy bộ kịch bản BTC qua pipeline thật và ghi trace JSONL.

Cấu hình (chỉ khác nhau ở CÁCH NẠP BỘ NHỚ — cùng model/tham số/prompt, đúng Phụ lục A.6):
- 'full'               : bộ nhớ 4 tầng, giữ xuyên các call trong 1 kịch bản. Bộ nhớ CHỈ chứa những gì
                         hệ thống tự ghi (tool grounded, normalizer, ...) — KHÔNG nạp đáp án (B3).
- 'baseline_no_memory' : bộ nhớ mới hoàn toàn ở mỗi call (stateless thật, B2).
- 'full_oracle'        : như 'full' nhưng sau mỗi call nạp `facts_established` của kịch bản — chỉ để
                         THAM CHIẾU trần điểm số, KHÔNG dùng để nộp. Trace ghi config='full' cho đúng schema,
                         run_id mang hậu tố FULL_ORACLE.

Latency đo bằng perf_counter ở ranh giới harness (nhận lượt -> có câu trả lời); Call Brief đo từ lúc
nhận diện khách tới khi Brief sẵn sàng. Không có số ngẫu nhiên/hằng số nào (B1).
"""
import os
import json
import glob
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from src.channels.normalizer import RequestNormalizer, InputChannel
from src.identity.resolver import IdentityResolver
from src.memory.remote import create_memory_service
from src.memory.service import MemoryService
from src.memory.episodic import EpisodeRecord
from src.harness.call_brief import CallBriefBuilder
from src.agents.specialists import A2AAgentNetwork
from src.harness.guardrail import GuardrailAndFallback
from src.harness.orchestrator import HarnessOrchestrator
from src.llm.client import LLMClient
from src.tools.mcp_gateway import MCPToolGateway
from src.tracing.tracer import TurnTracer, measure_latency, INPUT_MODES

load_dotenv()

CONFIGS = ("full", "baseline_no_memory", "full_oracle")


from src.eval.gate_assist import MAX_INJECTED_PER_CALL, assist_reply

from src.llm.cost_tracker import BudgetExceeded           # noqa: E402  (định nghĩa ở cost_tracker: client cũng ném lỗi này khi chạm trần cứng)


def spent_vnd(llm_client) -> float:
    """Tổng chi phí (VND) đã tiêu của 1 LLMClient (cộng dồn mọi lượt gọi kể cả bộ trích slot khó)."""
    tracker = llm_client.cost_tracker
    return tracker.cumulative_usd_cost * tracker._vnd_rate()
CALL_NAMES = ("call_1", "call_2", "call_3")


class ScenarioRunner:
    def __init__(self, scenarios_dir: str):
        self.scenarios_dir = scenarios_dir

    def load_scenarios(self) -> Dict[str, Dict[str, Any]]:
        scenarios = {}
        pattern = os.path.join(self.scenarios_dir, "*.json")
        for f in sorted(glob.glob(pattern)):
            if os.path.basename(f).startswith("_"):
                continue
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                scenarios[data["scenario_id"]] = data
        return scenarios

    # ------------------------------------------------------------------ dựng stack
    _GATEWAY: Optional[MCPToolGateway] = None
    _live_stack: Optional[Dict[str, Any]] = None

    @classmethod
    def gateway(cls) -> MCPToolGateway:
        """MỘT cổng MCP dùng chung cho cả tiến trình (spawn server ~2 s/lần nên không dựng lại mỗi kịch bản). Transport theo
        `MCP_TRANSPORT` (run_eval.py đặt mặc định `stdio` = server là tiến trình riêng; test mặc định `inproc`)."""
        if cls._GATEWAY is None or cls._GATEWAY._closed:
            cls._GATEWAY = MCPToolGateway()
        return cls._GATEWAY

    @staticmethod
    def _new_stack(llm_client) -> Dict[str, Any]:
        """1 bộ thành phần runtime với bộ nhớ MỚI (không SQLite -> hermetic, không rò giữa các lần chạy)."""
        # Bộ nhớ theo `MEMORY_TRANSPORT` (run_eval.py đặt mặc định `stdio` = qua MCP server `mcp-memory`; test mặc định `local`). Mỗi thành phần có view
        # riêng với tên caller của nó — server kiểm quyền theo tên đó; chỉ bộ chạy (`memory`, caller EvalRunner) mới nạp lịch sử và mở/đóng giao dịch lượt.
        memory = create_memory_service(enable_persistence=False, caller="EvalRunner")
        orchestrator_memory = memory.as_caller("HarnessOrchestrator")
        mcp = ScenarioRunner.gateway()
        guardrail = GuardrailAndFallback()
        return {
            "memory": memory,
            "normalizer": RequestNormalizer(),
            "mcp": mcp,
            "resolver": IdentityResolver(mcp, identity_backend=memory.backend),
            "resolver_memory": orchestrator_memory,       # ghi bối cảnh định danh = ghi bộ nhớ của lượt -> view HarnessOrchestrator
            "brief": CallBriefBuilder(memory.as_caller("CallBriefBuilder"), tool_gateway=mcp),
            "orchestrator": HarnessOrchestrator(mcp, orchestrator_memory, A2AAgentNetwork(orchestrator_memory), guardrail, llm_client=llm_client),
        }

    @staticmethod
    def _close_stack(stack: Dict[str, Any]) -> None:
        """Đóng kho bộ nhớ của bộ thành phần (qua MCP thì giải phóng kho trong server; cục bộ thì không có gì để đóng)."""
        stack["memory"].close()

    @staticmethod
    def _call_date(call_spec: Dict[str, Any], prev_call_date: str) -> str:
        """Ngày của call_n = call_date nếu có, nếu không = ngày call trước + days_later
        (call_1 mặc định 2026-10-15) — đúng theo schemas/scenario_format.md."""
        if call_spec.get("call_date"):
            return call_spec["call_date"]
        days_later = call_spec.get("days_later", 0)
        return (datetime.strptime(prev_call_date, "%Y-%m-%d") + timedelta(days=days_later)).strftime("%Y-%m-%d")

    @staticmethod
    def _input_mode(call_spec: Dict[str, Any], has_asr: bool) -> str:
        mode = call_spec.get("input_mode")
        if mode in INPUT_MODES:
            return mode
        return "asr_transcript" if has_asr else "clean"

    @staticmethod
    def _apply_seed_history(memory: MemoryService, customer_id: str, sessions: Any) -> None:
        """Nạp phiên cũ (`seed_history`, 'từ CRM') vào bộ nhớ trước cuộc gọi — chỉ cho cấu hình có
        bộ nhớ. Định dạng BTC chưa chốt: nhận list[dict] với các trường của EpisodeRecord và tùy chọn
        `facts` (dict). Trường lạ bị bỏ qua."""
        if not sessions:
            return
        if isinstance(sessions, dict):
            sessions = [sessions]
        fields = set(EpisodeRecord.__dataclass_fields__)
        for i, sess in enumerate(sessions, start=1):
            if not isinstance(sess, dict):
                continue
            for key, value in (sess.get("facts") or {}).items():
                memory.set_profile_fact(customer_id, key, value, session_id=sess.get("session_id", f"SEED-{i}"))
            data = {k: v for k, v in sess.items() if k in fields}
            data.setdefault("session_id", f"SEED-{i}")
            data.setdefault("call_index", i)
            data.setdefault("call_date", "2026-01-01")
            data.setdefault("channel", "hotline")
            data.setdefault("customer_goal", "")
            memory.add_episode(customer_id, EpisodeRecord(**data))

    @staticmethod
    def _inject_oracle(memory: MemoryService, customer_id: str, call_name: str, call_date: str,
                       call_spec: Dict[str, Any]) -> None:
        """CHỈ cho 'full_oracle': nạp đáp án `facts_established` của kịch bản (không dùng để nộp)."""
        facts = call_spec.get("facts_established")
        if not facts:
            return
        real_facts = memory.get_profile_facts(customer_id)
        for fk, fv in facts.items():
            if fk not in real_facts:
                memory.set_profile_fact(customer_id, fk, fv, session_id=f"SESS-{call_name}")
        real_facts = memory.get_profile_facts(customer_id)
        memory.add_episode(customer_id, EpisodeRecord(
            session_id=f"SESS-{call_name}",
            call_index=CALL_NAMES.index(call_name) + 1,
            call_date=call_date,
            channel=call_spec.get("channel") or "hotline",
            customer_goal=call_spec.get("customer_goal", ""),
            product_advised=real_facts.get("product_advised", facts.get("product_advised")),
            price_quoted_vnd=real_facts.get("price_quoted_vnd", facts.get("price_quoted_vnd")),
            promo_code=real_facts.get("promo_code", facts.get("promo_code")),
            promo_expiry=facts.get("promo_expiry"),
            blocker=facts.get("blocker"),
            outcome=call_spec.get("expected_outcome", "hen_goi_lai"),
            summary=f"Cuộc gọi {call_name}"
        ))

    @staticmethod
    def _enforce_budget(llm_client, max_cost_vnd, flush) -> None:
        if max_cost_vnd is not None and spent_vnd(llm_client) > max_cost_vnd:
            flush()                                   # giữ lại trace của lượt vừa chạy
            raise BudgetExceeded(spent_vnd(llm_client), max_cost_vnd)

    # ------------------------------------------------------------------ chạy
    def run_all(self, *args, **kwargs) -> str:
        """Chạy toàn bộ kịch bản (xem `_run_all_inner`). Chạm trần chi phí CỨNG ở GIỮA lượt (client ném BudgetExceeded) thì vẫn ghi nốt dòng trace đang chờ rồi dừng."""
        self._flush_fn = None
        try:
            return self._run_all_inner(*args, **kwargs)
        except BudgetExceeded:
            if self._flush_fn is not None:
                self._flush_fn()
            raise
        finally:
            if self._live_stack is not None:           # dừng giữa chừng (trần chi phí, lỗi): vẫn trả kho bộ nhớ của kịch bản đang chạy
                self._close_stack(self._live_stack)
                self._live_stack = None

    def _run_all_inner(self, config: str = "full", output_trace_file: str = "runs/full.jsonl",
                       only: Optional[List[str]] = None, seed: Optional[int] = None,
                       llm_client: Optional[LLMClient] = None, max_cost_vnd: Optional[float] = None, gate_assist: bool = False) -> str:
        if config not in CONFIGS:
            raise ValueError(f"config phải thuộc {CONFIGS}, nhận '{config}'")
        scenarios = self.load_scenarios()
        if only:
            missing = [s for s in only if s not in scenarios]
            if missing:
                raise KeyError(f"Không có kịch bản: {missing}")
            scenarios = {sid: scenarios[sid] for sid in only}

        if os.path.exists(output_trace_file):
            os.remove(output_trace_file)
        tracer = TurnTracer(trace_file=output_trace_file)

        trace_config = "baseline_no_memory" if config == "baseline_no_memory" else "full"
        run_id = f"RUN-{config.upper()}" + (f"-s{seed}" if seed is not None else "")

        # 1 LLMClient dùng chung cho cả run: cùng model/temperature/seed cho mọi cấu hình.
        if llm_client is None:
            llm_client = LLMClient(seed=seed)
        elif seed is not None and hasattr(llm_client, "seed"):
            llm_client.seed = seed          # client dùng chung cho nhiều seed (--repeats, diagnose_seeds): seed của LLM PHẢI đổi theo từng lần chạy

        for sid, spec in scenarios.items():
            self.gateway().reset_state()  # mỗi kịch bản độc lập: mã đơn không phụ thuộc thứ tự chạy (qua MCP, caller TestHarness)
            phone = spec.get("customer_phone", "0984726714")
            calls = spec.get("calls", {})
            stack = self._live_stack = self._new_stack(llm_client)
            prev_call_date = "2026-10-15"

            for call_name in CALL_NAMES:
                if call_name not in calls:
                    continue
                call_spec = calls[call_name]
                if config == "baseline_no_memory":
                    # Stateless THẬT: bộ nhớ mới ở mỗi call (không còn profile rò từ call trước, B2).
                    self._close_stack(stack)
                    stack = self._live_stack = self._new_stack(llm_client)
                memory, normalizer = stack["memory"], stack["normalizer"]

                has_asr = bool(call_spec.get("customer_turns_asr"))
                turns_to_use = call_spec.get("customer_turns_asr") if has_asr else call_spec.get("customer_turns", [])
                input_mode = self._input_mode(call_spec, has_asr)
                call_date = self._call_date(call_spec, prev_call_date)
                prev_call_date = call_date

                channel = InputChannel.from_scenario(call_spec.get("channel"))
                contact_id = phone if channel == InputChannel.HOTLINE else (call_spec.get("channel_identity") or phone)

                identity = None
                pending: List[Dict[str, Any]] = []   # trace của lượt cuối đang chờ (để gắn kết quả bước chốt cuộc gọi)

                def flush(extra_writes=None, extractor_info=None):
                    if not pending:
                        return
                    row = pending.pop()
                    if extra_writes:
                        row["memory_writes"] = (row["memory_writes"] or []) + extra_writes
                    if extractor_info:
                        row["extra"]["memory_extractor"] = extractor_info
                    tracer.log(**row)

                self._flush_fn = flush
                queue = [(raw, False) for raw in turns_to_use]
                t_idx, n_injected = 0, 0
                while queue:
                    turn_raw, injected = queue.pop(0)
                    t_idx += 1
                    flush()
                    memory.begin_turn(f"{call_name}#turn{t_idx}", call_date=call_date, channel=channel.value)
                    t_start = time.perf_counter()

                    # 1. Normalize
                    turn = normalizer.normalize(raw_text=turn_raw, channel=channel, contact_id=contact_id,
                                                is_audio=has_asr and not injected, reference_date=call_date)
                    # 2–3. Identity + Call Brief (đo từ lúc nhận diện khách tới khi Brief sẵn sàng)
                    t_brief = time.perf_counter()
                    identity = stack["resolver"].resolve(turn, memory=stack["resolver_memory"])
                    if t_idx == 1 and config != "baseline_no_memory" and identity.customer_id:
                        self._apply_seed_history(memory, identity.customer_id, call_spec.get("seed_history"))
                    brief = stack["brief"].build(identity, current_call_date=call_date)
                    brief_ms = int(round((time.perf_counter() - t_brief) * 1000))

                    # 4. Orchestrator — dùng 100% output thật từ pipeline, không hard-code lại.
                    resp_text, tool_calls, meta = stack["orchestrator"].process_turn(
                        turn, brief, current_date=call_date, call_name=call_name)
                    t_end = time.perf_counter()
                    lat = measure_latency(t_start, t_end, meta.get("llm_timing"))

                    # 5. Trace (ghi trễ 1 lượt: lượt cuối của call nhận thêm kết quả chốt cuộc gọi)
                    extra = {"_brief_must_carry_over": list(brief.must_carry_over),
                             "_brief_facts": sorted(brief.profile_facts.keys())}
                    if meta.get("memory_extraction"):
                        extra["memory_extractor"] = meta["memory_extraction"]     # chốt ở lúc chuyển máy
                    if meta.get("order_gate"):
                        extra["order_gate"] = meta["order_gate"]                   # order gate đã chặn/hỏi/đọc lại đơn ở lượt này
                    if injected:
                        extra["_injected"] = True                                  # lượt khách mô phỏng của --gate-assist (không phải lời kịch bản BTC)
                    lt = meta.get("llm_timing") or {}
                    if "rounds_before_first_token" in lt:
                        extra["latency_detail"] = {k: lt[k] for k in ("rounds_before_first_token", "round_ms", "tool_ms",
                                                                        "final_round_ttft_ms", "prompt_tokens", "cached_tokens") if k in lt}
                    pending_row = dict(
                        run_id=run_id, config=trace_config, scenario_id=sid, call=call_name, turn=t_idx,
                        customer_text=turn.normalized_text, agent_text=resp_text,
                        questions=meta["questions"], claims=meta["claims"], facts_used=meta["facts_used"],
                        tool_calls=tool_calls, ttft_ms=lat["ttft_ms"], total_ms=lat["total_ms"],
                        llm_cost=meta.get("llm_usage"),
                        call_brief_latency_ms=brief_ms if (t_idx == 1 and call_name != "call_1") else None,
                        memory_writes=stack["orchestrator"].commit_turn(),
                        customer_input_mode="clean" if injected else input_mode,
                        # Trường gỡ lỗi (tiền tố '_'): Brief của lượt này mang theo gì — dùng để kiểm baseline stateless.
                        extra=extra)
                    pending.append(pending_row)
                    if gate_assist and n_injected < MAX_INJECTED_PER_CALL and meta.get("order_gate"):
                        reply = assist_reply(meta["order_gate"][-1], brief.customer_name if brief.customer_name != "Quý khách" else "")
                        if reply:
                            queue.insert(0, (reply, True))
                            n_injected += 1
                    self._enforce_budget(llm_client, max_cost_vnd, flush)

                # Thời điểm kích hoạt #1: CUỐI CUỘC GỌI -> chốt episode + trích slot khó (LLM, ≤ 1 lần).
                # Baseline KHÔNG chạy bộ trích (không có bộ nhớ xuyên cuộc gọi).
                if config != "baseline_no_memory" and identity is not None and identity.customer_id and not identity.is_ambiguous:
                    memory.begin_turn(f"{call_name}#end", call_date=call_date, channel=channel.value)
                    result = stack["orchestrator"].finalize_call(identity.customer_id, call_date, call_name, channel.value, trigger="end")
                    info = {"trigger": "end", "llm_called": result.llm_called, "llm_cost": result.usage}
                    flush(stack["orchestrator"].commit_turn(), info)
                    self._enforce_budget(llm_client, max_cost_vnd, flush)
                else:
                    flush()

                if config == "full_oracle" and identity is not None and identity.customer_id:
                    self._inject_oracle(memory, identity.customer_id, call_name, call_date, call_spec)

            self._close_stack(stack)
            self._live_stack = None

        return output_trace_file
