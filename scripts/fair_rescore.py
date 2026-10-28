"""
Chấm lại một lần chạy theo cách CÔNG BẰNG giữa full và baseline (chỉ đọc trace + kịch bản, không gọi API):

  1. HR: trích lại claims cho CẢ HAI cấu hình bằng CÙNG một bộ trích (src/harness/extractor.py hiện tại); in HR trước/sau,
     liệt kê từng claim thay đổi kèm lý do; thêm "HR theo căn cứ tool" (số tiền agent nói có từng xuất hiện trong kết quả
     tool/lời khách không) để không phạt oan việc liệt kê nhiều sản phẩm.
  2. CCR: cách cũ = công thức BTC trên facts_used của trace; cách mới = fact chỉ tính khi agent DÙNG THẬT, CHƯA hỏi mở lại
     slot đó, và khách CHƯA tự nhắc lại trong cuộc gọi (src/harness/fact_usage.py). Giá trị tham chiếu = những gì CHÍNH cấu hình
     đó đã ghi nhớ ở các cuộc gọi trước (replay memory_writes + mã đơn từ kết quả tool).

    python scripts/fair_rescore.py runs/buoc15_B [--json out.json]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
sys.path.insert(0, os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval"))
import reference_eval as ref  # noqa: E402
from src.harness.extractor import extract_claims, extract_questions  # noqa: E402
from src.harness.fact_usage import fact_mentioned, used_by_agent  # noqa: E402
from src.common.money import numbers_in  # noqa: E402

SCEN_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")
CALLS = ("call_1", "call_2", "call_3")
MONEY_FIELDS = ("price_vnd", "list_price_vnd", "final_price_vnd", "discount_vnd", "total_vnd", "exchange_fee_vnd",
                "cod_limit_vnd", "variant_price_delta_vnd")


def read_rows(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def group(rows):
    out = {}
    for r in rows:
        out.setdefault((r["scenario_id"], r["call"]), []).append(r)
    return out


def call_dates(spec):
    from src.eval.runner import ScenarioRunner
    out, prev = {}, "2026-10-15"
    for cn in CALLS:
        if cn in spec["calls"]:
            prev = ScenarioRunner._call_date(spec["calls"][cn], prev)
            out[cn] = prev
    return out


def product_names():
    try:
        import mock_tools
        return {p["sku"]: p["name"] for p in mock_tools.PRODUCTS}
    except Exception:
        return {}


# ------------------------------------------------------------------ 1. HR
def reason_for_change(removed, new_claims_same_row):
    """Đoán lý do một claim biến mất/đổi: so với claim mới cùng giá trị."""
    field, value = removed
    for f2, v2 in new_claims_same_row:
        if v2 == value and f2 != field:
            if f2 == "variant_price_delta_vnd":
                return f"{value:,}đ là phần CHÊNH LỆCH giữa các size, không phải giá bán -> `{field}` đổi thành `{f2}`"
            if f2 == "discount_vnd":
                return f"{value:,}đ là số tiền được GIẢM, không phải giá bán -> `{field}` đổi thành `{f2}`"
            return f"`{field}` đổi thành `{f2}` (gán lại vai trò của số tiền)"
    if str(field).startswith("promo"):
        return "tên sản phẩm rút gọn (vd AP-Y) bị hiểu nhầm là mã khuyến mãi -> bỏ"
    if field == "in_stock":
        return "'khuyến mãi đã hết hạn' bị hiểu nhầm là hết hàng -> bỏ"
    return "bộ trích mới không còn phát claim này (thiếu căn cứ)"


def rescore_hr(scenarios, rows, dates, label):
    as_run_g = group(rows)
    as_run = ref.hallucination_rate(scenarios, as_run_g)
    new_rows = []
    diffs = []
    for r in rows:
        nr = dict(r)
        nr["claims"] = extract_claims(r["agent_text"], r["tool_calls"], call_date=dates[r["scenario_id"]][r["call"]])
        new_rows.append(nr)
        gt = scenarios[r["scenario_id"]]["calls"][r["call"]].get("ground_truth_facts", {})
        old_set = {(c["field"], c["value"]) for c in r["claims"] if c["field"] in gt}
        new_set = {(c["field"], c["value"]) for c in nr["claims"] if c["field"] in gt}
        new_all = {(c["field"], c["value"]) for c in nr["claims"]}
        for ch in sorted(old_set - new_set, key=str):
            diffs.append({"cfg": label, "where": f"{r['scenario_id']}/{r['call']} t{r['turn']}", "kind": "bỏ/đổi", "claim": ch,
                          "truth": gt.get(ch[0]), "reason": reason_for_change(ch, new_all)})
        for ch in sorted(new_set - old_set, key=str):
            diffs.append({"cfg": label, "where": f"{r['scenario_id']}/{r['call']} t{r['turn']}", "kind": "thêm", "claim": ch,
                          "truth": gt.get(ch[0]), "reason": "bộ trích mới trích được claim này"})
    new = ref.hallucination_rate(scenarios, group(new_rows))
    return as_run, new, diffs, new_rows


def grounded_stats(rows_by_scen_call, scenarios, new_rows):
    """Số claim TIỀN mà agent nói: có căn cứ (từng xuất hiện trong kết quả tool/lời khách của kịch bản tính đến lượt đó) hay không."""
    total = ungrounded = 0
    examples = []
    by_scen = {}
    for r in new_rows:
        by_scen.setdefault(r["scenario_id"], []).append(r)
    for sid, rs in by_scen.items():
        known = set()
        for r in sorted(rs, key=lambda x: (x["call"], x["turn"])):
            known |= {v for v, _ in __import__("src.common.money", fromlist=["extract_amounts"]).extract_amounts(r["customer_text"])}
            for tc in r["tool_calls"]:
                known |= numbers_in(tc.get("result"))
            for c in r["claims"]:
                if c["field"] in MONEY_FIELDS and isinstance(c["value"], int) and c["value"] >= 1000:
                    total += 1
                    if c["value"] not in known:
                        ungrounded += 1
                        examples.append((sid, r["call"], r["turn"], c["field"], c["value"]))
    return total, ungrounded, examples


# ------------------------------------------------------------------ 2. CCR
def replay_reference(rows_scn, upto_call):
    """Giá trị mà CẤU HÌNH này đã ghi nhớ ở các cuộc gọi TRƯỚC `upto_call` của một kịch bản (replay memory_writes + mã đơn từ tool)."""
    facts = {}
    for r in sorted(rows_scn, key=lambda x: (x["call"], x["turn"])):
        if r["call"] >= upto_call:
            continue
        for w in r.get("memory_writes", []):
            if not str(w["key"]).startswith("episode:") and w["key"] != "channels_seen":
                facts[w["key"]] = w["value"]
        for tc in r.get("tool_calls", []):
            res = tc.get("result")
            if tc.get("name") == "order.create" and isinstance(res, dict) and res.get("order_id"):
                facts["order_id"] = res["order_id"]
    return facts


def strict_ccr(scenarios, rows, ask_kinds=("open",), names=None):
    used = required = 0
    detail = []
    by_scen = {}
    for r in rows:
        by_scen.setdefault(r["scenario_id"], []).append(r)
    for sid, s in scenarios.items():
        rs = by_scen.get(sid, [])
        for call, spec in s["calls"].items():
            mco = spec.get("must_carry_over") or []
            if not mco:
                continue
            required += len(mco)
            reference = replay_reference(rs, call)
            turns = sorted([r for r in rs if r["call"] == call], key=lambda x: x["turn"])
            for slot in mco:
                value = reference.get(slot)
                credited, why = False, "hệ thống không có giá trị đã ghi nhớ" if value is None else "agent không dùng"
                if value is not None:
                    restated = asked = False
                    for r in turns:
                        restated = restated or fact_mentioned(slot, value, r["customer_text"], names)
                        qs = extract_questions(r["agent_text"])
                        asked = asked or any(q["slot"] == slot and q["type"] in ask_kinds and slot != "blocker" for q in qs)
                        if restated:
                            why = "khách đã nhắc lại"
                            break
                        if asked:
                            why = "agent đã hỏi lại"
                            break
                        if used_by_agent(slot, value, r["agent_text"], [t.get("args", {}) for t in r["tool_calls"]], names):
                            credited = True
                            why = "dùng đúng"
                            break
                used += int(credited)
                detail.append((sid, call, slot, credited, why))
    return {"value": ref.pct(used, required), "used": used, "required": required, "detail": detail}


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    bpath = os.path.join(args.run_dir, "baseline.jsonl")
    rows = {"full": read_rows(os.path.join(args.run_dir, "full.jsonl")), "baseline": read_rows(bpath) if os.path.exists(bpath) else []}
    CFGS = ("baseline", "full") if rows["baseline"] else ("full",)          # run chẩn đoán chỉ chạy cấu hình full
    ids = {r["scenario_id"] for r in rows["full"]}
    scenarios = {sid: s for sid, s in ref.load_scenarios(SCEN_DIR).items() if sid in ids}
    dates = {sid: call_dates(s) for sid, s in scenarios.items()}
    names = product_names()
    out = {}

    print(f"## A. HR — trích lại claims cho CẢ HAI cấu hình bằng cùng một bộ trích ({len(scenarios)} kịch bản)")
    print(f"{'cấu hình':10s} | {'HR giá&KM như lúc chạy':26s} | {'sau trích lại':26s} | {'HR mọi claim: trước → sau':28s} | tiền có căn cứ tool")
    all_diffs = []
    for cfg in CFGS:
        as_run, new, diffs, new_rows = rescore_hr(scenarios, rows[cfg], dates, cfg)
        all_diffs += diffs
        pp, pn = as_run["price_promo_only"], new["price_promo_only"]
        total, ungr, ex = grounded_stats(None, scenarios, new_rows)
        print(f"{cfg:10s} | {str(pp['value'])+'% ('+str(pp['wrong'])+'/'+str(pp['total'])+')':26s} | {str(pn['value'])+'% ('+str(pn['wrong'])+'/'+str(pn['total'])+')':26s} | "
              f"{str(as_run['value'])+'% → '+str(new['value'])+'%':28s} | {ungr}/{total} claim tiền không có căn cứ")
        out[cfg] = {"hr_as_run": pp, "hr_after": pn, "hr_all_as_run": as_run["value"], "hr_all_after": new["value"],
                    "money_claims": total, "money_ungrounded": ungr, "ungrounded_examples": ex[:10],
                    "wrong_examples_after": new["examples"][:10]}
    print("\nTừng claim thay đổi (chỉ tính field có trong ground truth):")
    if not all_diffs:
        print("  (không claim nào thay đổi)")
    for d in all_diffs:
        print(f"  [{d['cfg']}] {d['where']}: {d['kind']} {d['claim']} (đáp án={d['truth']}) — {d['reason']}")
    for cfg in CFGS:
        for e in out[cfg]["wrong_examples_after"]:
            print(f"  [{cfg}] claim sai còn lại: {e['scenario']}/{e['call']} t{e['turn']} {e['field']}: nói {e['claimed']}, đáp án {e['truth']}")
        for e in out[cfg]["ungrounded_examples"]:
            print(f"  [{cfg}] số tiền KHÔNG có trong tool/lời khách: {e}")

    print("\n## B. CCR — cách cũ (công thức BTC trên facts_used của trace) và cách mới (chặt)")
    print(f"{'cấu hình':10s} | {'cách cũ':22s} | {'cách mới (hỏi mở = hỏi lại)':30s} | {'nếu cả câu xác nhận cũng là hỏi lại':36s}")
    for cfg in CFGS:
        old = ref.context_carryover_rate(scenarios, ref.load_trace(os.path.join(args.run_dir, f"{cfg}.jsonl")))
        new = strict_ccr(scenarios, rows[cfg], ("open",), names)
        sens = strict_ccr(scenarios, rows[cfg], ("open", "confirm"), names)
        print(f"{cfg:10s} | {str(old['value'])+'% ('+str(old['used'])+'/'+str(old['required'])+')':22s} | {str(new['value'])+'% ('+str(new['used'])+'/'+str(new['required'])+')':30s} | {str(sens['value'])+'% ('+str(sens['used'])+'/'+str(sens['required'])+')':36s}")
        out.setdefault(cfg, {})["ccr_old"] = old
        out[cfg]["ccr_new"] = {k: v for k, v in new.items() if k != "detail"}
        out[cfg]["ccr_new_with_confirm"] = {k: v for k, v in sens.items() if k != "detail"}
        out[cfg]["ccr_detail"] = new["detail"]
    print("\nChi tiết cách mới (từng slot bắt buộc mang sang):")
    for cfg in CFGS:
        print(f"  [{cfg}]")
        for sid, call, slot, ok, why in out[cfg]["ccr_detail"]:
            print(f"    {sid}/{call} {slot:20s} {'✔' if ok else '✗'} {why}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
