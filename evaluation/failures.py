"""Liệt kê ca sai: (kịch bản, cuộc gọi, lượt, chỉ số vi phạm, chi tiết). Dùng lại hàm chấm của BTC trên từng kịch bản riêng."""
from .parrot import parrot_cases

METRIC_ORDER = ("missing_trace", "tsr", "rqr", "ccr", "hr", "guardrail", "parrot")


def failure_cases(ref, scenarios: dict, trace: dict, max_old_facts: int = 2) -> list:
    out = []
    for sid, s in scenarios.items():
        one = {sid: s}
        for call, spec in s["calls"].items():
            rows = trace.get((sid, call), [])
            if not rows:
                out.append({"scenario": sid, "call": call, "turn": None, "metric": "missing_trace",
                            "detail": "không có dòng trace nào cho cuộc gọi này"})
                continue
            earlier = [r for c in sorted(s["calls"]) if c < call for r in trace.get((sid, c), [])]
            ok, reasons = ref.check_call(spec, rows, ref.created_order_ids(earlier))
            if ok is False:
                out.append({"scenario": sid, "call": call, "turn": None, "metric": "tsr", "detail": "; ".join(reasons)})
            seen = set()
            for r in rows:
                seen.update(r.get("facts_used", []))
                for tc in r.get("tool_calls", []):
                    seen.update(tc.get("args", {}).keys())
            missing = [k for k in spec.get("must_carry_over", []) if k not in seen]
            if missing:
                out.append({"scenario": sid, "call": call, "turn": None, "metric": "ccr",
                            "detail": "chưa mang sang: " + ", ".join(missing)})
        for e in ref.repeat_question_rate(one, trace)["examples"]:
            out.append({"scenario": sid, "call": e["call"], "turn": e["turn"], "metric": "rqr",
                        "detail": f"hỏi lại slot {e['slot']} ({e['type']}): {e.get('text')}"})
        for e in ref.hallucination_rate(one, trace)["examples"]:
            out.append({"scenario": sid, "call": e["call"], "turn": e["turn"], "metric": "hr",
                        "detail": f"claim {e['field']}={e['claimed']} ≠ sự thật {e['truth']}"})
        for e in ref.guardrail_violations(one, trace)["examples"]:
            out.append({"scenario": sid, "call": e["call"], "turn": None, "metric": "guardrail", "detail": e["type"]})
    out += parrot_cases(scenarios, trace, max_old_facts)
    out.sort(key=lambda c: (c["scenario"], c["call"], c["turn"] or 0, METRIC_ORDER.index(c["metric"])))
    return out


def format_cases(cases: list) -> str:
    if not cases:
        return "Không có ca sai.\n"
    lines = [f"{len(cases)} ca sai", ""]
    for c in cases:
        turn = "-" if c["turn"] is None else c["turn"]
        lines.append(f"[{c['metric']:<13}] {c['scenario']} {c['call']} lượt {turn}: {c['detail']}")
    return "\n".join(lines) + "\n"
