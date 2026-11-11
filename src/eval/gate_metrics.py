"""
Đo lường tách làm HAI loại (quyết định của người dùng 2026-10-22; order gate luôn bật ở mọi cấu hình):

  1. TSR TƯƠNG TÁC (TSR CHÍNH) — khách mô phỏng trả lời được câu hỏi/xác nhận/đọc lại của gate (`run_eval.py --gate-assist`, lượt chèn gắn `_injected`).
     Cuộc gọi tạo đơn đạt khi: `order.create` đúng SKU/giá (theo `args_match` của kịch bản) VÀ được tạo SAU khi khách xác nhận (lượt ngay trước có
     bước ĐỌC LẠI ĐƠN, lượt tạo đơn là lời đồng ý rõ ràng). Cuộc gọi không tạo đơn chấm như `reference_eval` (success_if).
     Dùng cho 54 kịch bản mới (luật P5 đảm bảo lời khách có đáp án cho gate).
  2. KIỂM TRA KỊCH BẢN CỐ ĐỊNH (7 mẫu BTC, lời khách không đổi) — KHÔNG tính vào TSR chính. Cuộc gọi tạo đơn đạt khi: KHÔNG tạo đơn sớm
     (đơn chỉ được tạo sau bước đọc lại + đồng ý) VÀ đã tới bước ĐỌC LẠI ĐƠN. Ghi thêm "mức đạt tới" (none/ask/readback/created) cho từng cuộc.
"""
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_EVAL = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval")
if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)
import reference_eval as ref  # noqa: E402

from src.harness.order_gate import is_explicit_consent  # noqa: E402


def is_order_call(spec: Dict[str, Any]) -> bool:
    return ((spec.get("success_if") or {}).get("tool_called")) == "order.create"


def is_fixed_btc(scenario_id: str) -> bool:
    """Kịch bản BTC (lời khách cố định, không thể trả lời gate)."""
    return str(scenario_id).startswith("SAMPLE-")


def injected_turns(trace: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> int:
    return sum(1 for rows in trace.values() for r in rows if r.get("_injected"))


def _events(rows: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    return {r["turn"]: list(r.get("order_gate") or []) for r in rows}


def _created(rows: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    return [(r, tc) for r in rows for tc in r.get("tool_calls", []) if tc.get("name") == "order.create" and (tc.get("result") or {}).get("status") == "created"]


def stage_reached(rows: List[Dict[str, Any]]) -> str:
    """none (gate không can thiệp) | ask (hỏi/xác nhận) | readback (đã đọc lại đơn) | created (đã tạo đơn)."""
    if _created(rows):
        return "created"
    acts = {e.get("action") for evs in _events(rows).values() for e in evs}
    if "readback" in acts:
        return "readback"
    if acts & {"ask", "confirm", "ask_confirm"}:
        return "ask"
    return "none"


def order_created_after_confirmation(rows: List[Dict[str, Any]], success_if: Dict[str, Any], aliases=()) -> Tuple[bool, str]:
    """Có `order.create` ĐÚNG args_match, được tạo ngay sau lần đọc lại đơn và ở lượt khách đồng ý rõ ràng?"""
    readback_turns = {t for t, evs in _events(rows).items() if any(e.get("action") == "readback" for e in evs)}
    seen_match = False
    for r, tc in _created(rows):
        if not any(ref.args_match(success_if.get("args_match"), ln, aliases) for ln in ref.order_lines([tc])):      # đơn nhiều dòng (lines): khớp theo TỪNG DÒNG như script BTC
            continue
        seen_match = True
        if (r["turn"] - 1) in readback_turns and is_explicit_consent(r.get("customer_text", "")):
            return True, ""
    return False, ("đơn đúng SKU/giá nhưng được tạo khi chưa đọc lại đơn/khách chưa đồng ý rõ ràng" if seen_match else "không tạo đơn đúng SKU/giá")


def interactive_tsr(scenarios: Dict[str, Dict[str, Any]], trace) -> Dict[str, Any]:
    """TSR TƯƠNG TÁC: mỗi kịch bản đạt khi MỌI cuộc có success_if đều đạt; cuộc tạo đơn còn phải được tạo SAU khi khách xác nhận."""
    ok = n = 0
    fails: List[Dict[str, Any]] = []
    for sid, s in scenarios.items():
        passed_all, has_any = True, False
        for call, spec in s["calls"].items():
            rows = trace.get((sid, call), [])
            earlier = [r for c in sorted(s["calls"]) if c < call for r in trace.get((sid, c), [])]
            res, reasons = ref.check_call(spec, rows, ref.created_order_ids(earlier))
            if res is None:
                continue
            has_any = True
            if res and is_order_call(spec):
                res, why = order_created_after_confirmation(rows, spec["success_if"], ref.created_order_ids(earlier))
                reasons = [why] if why else []
            if not res:
                passed_all = False
                fails.append({"scenario": sid, "call": call, "reasons": reasons, "stage": stage_reached(rows)})
        if has_any:
            n += 1
            ok += int(passed_all)
    return {"value": ref.pct(ok, n), "passed": ok, "total": n, "failures": fails, "injected_turns": injected_turns(trace)}


def fixed_script_check(scenarios: Dict[str, Dict[str, Any]], trace) -> Dict[str, Any]:
    """Kiểm tra kịch bản CỐ ĐỊNH (không tính TSR chính): với mỗi cuộc có tạo đơn — đạt khi không tạo đơn sớm VÀ đã tới bước đọc lại đơn."""
    rows_out: List[Dict[str, Any]] = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            if not is_order_call(spec):
                continue
            rows = trace.get((sid, call), [])
            readback_turns = {t for t, evs in _events(rows).items() if any(e.get("action") == "readback" for e in evs)}
            early = [r["turn"] for r, _ in _created(rows)
                     if not ((r["turn"] - 1) in readback_turns and is_explicit_consent(r.get("customer_text", "")))]      # tạo đơn mà không có bước đọc lại + đồng ý ngay trước
            stage = stage_reached(rows)
            reached = stage in ("readback", "created")
            rows_out.append({"scenario": sid, "call": call, "stage": stage, "early_order_turns": early, "reached_readback": reached,
                             "passed": (not early) and reached})
    n = len(rows_out)
    return {"checked": n, "passed": sum(1 for r in rows_out if r["passed"]), "early_orders": sum(len(r["early_order_turns"]) for r in rows_out),
            "reached_readback": sum(1 for r in rows_out if r["reached_readback"]), "reached_any_gate_step": sum(1 for r in rows_out if r["stage"] != "none"),
            "calls": rows_out}


def report_text(scenarios: Dict[str, Dict[str, Any]], trace) -> str:
    """Báo cáo gọn, luôn tách hai loại: kịch bản cố định (BTC) và kịch bản tương tác (có khách mô phỏng)."""
    fixed = {k: v for k, v in scenarios.items() if is_fixed_btc(k)}
    inter = {k: v for k, v in scenarios.items() if not is_fixed_btc(k)}
    injected = injected_turns(trace)
    out: List[str] = []
    if inter:
        r = interactive_tsr(inter, trace)
        tag = "CÓ khách mô phỏng (--gate-assist)" if injected else "KHÔNG có khách mô phỏng (không chèn lượt) — số này không phản ánh khả năng tạo đơn"
        out.append(f"[1] TSR TƯƠNG TÁC (TSR CHÍNH) — {tag}: {r['value']}% ({r['passed']}/{r['total']} kịch bản); lượt chèn `_injected` = {r['injected_turns']}")
        for f in r["failures"]:
            out.append(f"     trượt {f['scenario']}/{f['call']} (mức đạt tới: {f['stage']}): {'; '.join(f['reasons'])}")
    else:
        out.append("[1] TSR TƯƠNG TÁC (TSR CHÍNH): không có kịch bản tương tác trong lần chạy này — chưa có số.")
    if fixed:
        c = fixed_script_check(fixed, trace)
        note = "" if not injected else f"  [CẢNH BÁO: trace có {injected} lượt chèn `_injected` — mẫu BTC KHÔNG nên chạy với --gate-assist; số này chỉ chẩn đoán]"
        out.append(f"[2] KIỂM TRA KỊCH BẢN CỐ ĐỊNH (7 mẫu BTC; KHÔNG tính vào TSR chính): đạt {c['passed']}/{c['checked']} cuộc có tạo đơn "
                   f"(không tạo đơn sớm: {c['checked'] - sum(1 for r in c['calls'] if r['early_order_turns'])}/{c['checked']}; đã tới bước đọc lại đơn: {c['reached_readback']}/{c['checked']}; "
                   f"đã vào ít nhất một bước của gate: {c['reached_any_gate_step']}/{c['checked']}; đơn tạo sớm: {c['early_orders']}){note}")
        for r in c["calls"]:
            out.append(f"     {r['scenario']}/{r['call']}: mức đạt tới={r['stage']}, đơn sớm ở lượt {r['early_order_turns'] or '-'}, {'ĐẠT' if r['passed'] else 'chưa đạt'}")
    return "\n".join(out)
