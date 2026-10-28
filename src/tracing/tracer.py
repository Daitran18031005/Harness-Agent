"""
Turn Tracer Module: Ghi nhận log trace chuẩn JSONL theo schema BTC (schemas/trace_log.schema.json).
Cung cấp dữ liệu trực tiếp cho script reference_eval.py.

Latency KHÔNG được bịa ở đây: caller phải truyền số đo thật (perf_counter ở ranh giới
harness). Không có giá trị mặc định cố định/ngẫu nhiên nào (B1).
"""
import os
import json
from typing import Dict, Any, List, Optional

INPUT_MODES = ("clean", "asr_transcript", "chat_teencode")


class TurnTracer:
    def __init__(self, trace_file: str = "runs/ui_session.jsonl"):
        self.trace_file = trace_file
        os.makedirs(os.path.dirname(os.path.abspath(trace_file)), exist_ok=True)

    def log(self, run_id: str, config: str, scenario_id: str, call: str, turn: int,
            customer_text: str, agent_text: str, questions: List[Dict[str, Any]],
            claims: List[Dict[str, Any]], facts_used: List[str], tool_calls: List[Dict[str, Any]],
            ttft_ms: int, total_ms: int, llm_cost: Optional[Dict[str, Any]] = None,
            call_brief_latency_ms: Optional[int] = None,
            memory_writes: Optional[List[Dict[str, Any]]] = None,
            customer_input_mode: str = "clean",
            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        if customer_input_mode not in INPUT_MODES:
            raise ValueError(f"customer_input_mode phải thuộc {INPUT_MODES}, nhận '{customer_input_mode}'")

        record = {
            "run_id": run_id,
            "config": config,
            "scenario_id": scenario_id,
            "call": call,
            "turn": turn,
            "customer_text": customer_text,
            "agent_text": agent_text,
            "questions": questions,
            "claims": claims,
            "facts_used": facts_used,
            "tool_calls": tool_calls,
            "latency": {
                "ttft_ms": int(ttft_ms),
                "total_ms": int(total_ms),
            },
            # Chỉ có giá trị ở turn 1 của call_2/call_3 (đo từ lúc nhận diện khách tới khi Call Brief sẵn sàng).
            "call_brief_latency_ms": None if call_brief_latency_ms is None else int(call_brief_latency_ms),
            "memory_writes": memory_writes or [],
            "customer_input_mode": customer_input_mode,
        }
        if llm_cost:
            # Field tùy chọn (không có trong required[]) — an toàn với trace_log.schema.json
            # vì schema không khóa additionalProperties.
            record["llm_cost"] = llm_cost
        if extra:
            record.update(extra)

        with open(self.trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        return record


def measure_latency(t_start: float, t_end: float, llm_timing: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """Quy đổi mốc perf_counter (giây) tại ranh giới harness thành ttft_ms/total_ms.
    - Nhánh có LLM (stream): TTFT = thời gian chuẩn bị trước LLM + thời gian tới token text đầu
      tiên của vòng trả lời cuối. Lưu ý: guardrail chạy SAU khi sinh xong, nên nếu UI stream thật
      cho khách thì phải đệm token tới khi guardrail duyệt — đây là số đo của mô hình, ghi rõ ở báo cáo.
    - Nhánh không-LLM (rule-based): không stream -> TTFT = Total (đúng hướng dẫn BTC, quy tắc 7)."""
    total_ms = int(round((t_end - t_start) * 1000))
    if llm_timing and "ttft_ms" in llm_timing and "started_at" in llm_timing:
        pre_ms = (llm_timing["started_at"] - t_start) * 1000
        ttft_ms = int(round(pre_ms + llm_timing["ttft_ms"]))
        ttft_ms = min(ttft_ms, total_ms)
    else:
        ttft_ms = total_ms
    return {"ttft_ms": ttft_ms, "total_ms": total_ms}
