"""Ghép khung + lời thoại → file kịch bản ĐÚNG định dạng BTC (`schemas/scenario_format.md`) và bản đọc cho người duyệt."""
from typing import Any, Dict, List

from src.dataset.validate import CUSTOMER_FACT_KEYS

BTC_CALL_ORDER = ["channel", "channel_identity", "call_date", "days_later", "customer_goal", "input_mode", "customer_turns", "customer_turns_asr",
                  "seed_history", "facts_established", "must_carry_over", "must_not_ask", "success_if", "ground_truth_facts", "memory_expectation",
                  "expected_outcome"]


def scenario_from(frame: Dict[str, Any], dialogues: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    sc = {k: v for k, v in frame["scenario"].items() if k != "group"}
    calls: Dict[str, Any] = {}
    for call in frame["calls"]:
        rec = dialogues[call["name"]]
        cust = [t for t in rec["turns"] if t["speaker"] == "C"]
        exp = dict(call["expected"])
        facts = dict(exp.pop("facts_established", {}))
        for f in call["customer_facts"]:
            if f["key"] in CUSTOMER_FACT_KEYS and f["key"] != "phone_provided":
                facts.setdefault(f["key"], f["value"])
        c: Dict[str, Any] = {"channel": call["channel"]}
        if "channel_identity" in call:
            c["channel_identity"] = call["channel_identity"]
        if call["name"] == "call_1" or "call_date" in call:
            c["call_date"] = call["abs_date"]
        else:
            c["days_later"] = call["days_later"]
        c["customer_goal"] = call["goal"]
        c["customer_turns"] = [t["text_written"] for t in cust]
        if call["style"] == "teencode":
            c["customer_turns_asr"] = [t["text_asr"] for t in cust]
        elif call["style"] == "spoken":                                 # lời khách như ASR trả về: số/SĐT bằng chữ, không dấu câu
            c["customer_turns_asr"] = [t["text_spoken"] for t in cust]
        if facts:
            c["facts_established"] = facts
        for k in ("input_mode", "must_carry_over", "must_not_ask", "success_if", "ground_truth_facts", "memory_expectation", "expected_outcome"):
            if k in exp:
                c[k] = exp[k]
        calls[call["name"]] = {k: c[k] for k in BTC_CALL_ORDER if k in c}
    sc["calls"] = calls
    return sc


def review_markdown(frames: List[Dict[str, Any]], dialogues: Dict[str, Dict[str, Any]], issues_by_scenario: Dict[str, List[str]],
                    gen_log: List[Dict[str, Any]], cost_vnd: float, model: str, title: str = "10 kịch bản mẫu — bản duyệt", cap_text: str = "trần 500") -> str:
    out = [f"# {title}", "",
           f"> Sinh bằng **{model}** (lời thoại khách + agent); đáp án/giá/ngày do code tính từ `mock_tools.py`. Tổng chi phí LLM thực tế (mọi lần chạy trong sổ cái): **{cost_vnd:,.1f} VND** ({cap_text}). "
           "Cột `written` = như khách/agent gõ-nói; `spoken` = dạng đọc thành lời (số bằng chữ) dùng cho TTS + chuẩn WER. Mỗi mục kết thúc bằng kết quả kiểm tự động (S1–S14).", ""]
    for fr in frames:
        sc = fr["scenario"]
        out += [f"## {sc['scenario_id']} — {sc['persona']}" + (f" · ca khó: `{sc['hard_case']}`" if sc["hard_case"] else ""), "",
                f"*Khách:* {sc['honorific']} {sc['customer_name']} · SĐT giả `{sc['customer_phone']}` · {sc['notes']}", ""]
        for call in fr["calls"]:
            rec = dialogues.get(f"{sc['scenario_id']}/{call['name']}")
            exp = call["expected"]
            out += [f"### {call['name']} — {call['channel']} · {call['abs_date']} · {call['goal']}", ""]
            gt = {k: v for k, v in {**exp.get("ground_truth_facts", {})}.items()}
            out += [f"**Đáp án do code tính:** `success_if` = `{exp.get('success_if')}` · `ground_truth_facts` = `{gt}` · outcome = `{exp.get('expected_outcome')}`"
                    + (f" · carry-over = `{exp.get('must_carry_over')}` · không được hỏi = `{exp.get('must_not_ask')}`" if exp.get("must_carry_over") else ""), ""]
            if rec is None:
                out += ["_(chưa sinh)_", ""]
                continue
            out += ["| # | ai | written | spoken | entities |", "|---|---|---|---|---|"]
            for t in rec["turns"]:
                who = "Agent" if t["speaker"] == "A" else "Khách"
                written = t["text_written"].replace("|", "\\|")
                extra = f"<br>*(teencode)* {t['text_asr']}" if t.get("text_asr") else ""
                out.append(f"| {t['idx']} | {who} | {written}{extra} | {t['text_spoken']} | `{t['entities']}` |")
            meta = rec.get("meta", {})
            out += ["", f"_Lần sinh: {meta.get('attempts')} · đạt kiểm tra khi sinh: {meta.get('ok')}_", ""]
        issues = issues_by_scenario.get(sc["scenario_id"], [])
        out += ["**Kết quả validate:** " + ("✔ không có lỗi" if not issues else ""), ""]
        out += [f"- {i}" for i in issues]
        out += [""]
    out += ["## Nhật ký sinh (từng lần gọi LLM, gộp 3 lần chạy — xem `reports/generation_runs.jsonl`)", "",
            f"Tổng chi phí LLM: **{cost_vnd:,.1f} VND** ({cap_text}). Cuộc sinh lại nhiều lần do lỗi của bộ kiểm hay của LLM được ghi ở cột số lần sinh.", "",
            "| kịch bản | cuộc | số lần sinh | chi phí VND |", "|---|---|---|---|"]
    for g in gen_log:
        out.append(f"| {g['scenario']} | {g['call']} | {g['attempt']} | {g['cost_vnd']} |")
    return chr(10).join(out) + chr(10)
