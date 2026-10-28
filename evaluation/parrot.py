"""Kiểm tra "đọc vẹt" bằng luật: câu chào (lượt 1 của cuộc gọi thứ 2 trở đi) nhắc quá `max_old` fact của phiên trước."""
import re

SKU_LIKE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)+$")
NUM = re.compile(r"\d[\d.,]*")


def _mentions(text: str, value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (list, tuple)):
        return any(_mentions(text, v) for v in value)
    if isinstance(value, (int, float)):
        # shortcut: so khớp theo số nguyên, "15" trong "hôm 15/10" cũng tính; nâng cấp nếu báo dương tính giả
        return str(int(value)) in {re.sub(r"[.,]", "", m) for m in NUM.findall(text)}
    v = str(value).casefold().strip()
    return len(v) >= 3 and v in text.casefold()


def old_facts_in_opening(prior_facts: dict, agent_text: str, facts_used) -> list:
    """Slot cũ được nhắc: giá trị xuất hiện trong lời agent; riêng giá trị mã SKU (lời nói dùng tên sản phẩm) tính theo facts_used."""
    used = set(facts_used or [])
    hit = []
    for slot, value in prior_facts.items():
        if _mentions(agent_text, value) or (isinstance(value, str) and SKU_LIKE.match(value) and slot in used):
            hit.append(slot)
    return hit


def prior_facts_of(scenario: dict, call: str) -> dict:
    out = {}
    for c in sorted(scenario.get("calls", {})):
        if c < call:
            out.update(scenario["calls"][c].get("facts_established") or {})
    return out


def parrot_cases(scenarios: dict, trace: dict, max_old: int = 2) -> list:
    """trace: {(scenario_id, call): [rows]} như reference_eval.load_trace. Trả các lượt chào vi phạm."""
    cases = []
    for (sid, call), rows in sorted(trace.items()):
        s = scenarios.get(sid)
        prior = prior_facts_of(s, call) if s else {}
        if not rows or not prior:
            continue
        r = rows[0]
        hit = old_facts_in_opening(prior, r.get("agent_text", ""), r.get("facts_used"))
        if len(hit) > max_old:
            cases.append({"scenario": sid, "call": call, "turn": r["turn"], "metric": "parrot",
                          "detail": f"câu chào nhắc {len(hit)} fact cũ (> {max_old}): {', '.join(hit)}"})
    return cases
