"""
Run CHẨN ĐOÁN nhiều seed (cấu hình full, 7 mẫu BTC, lời khách cố định, KHÔNG chèn lượt — --gate-assist chỉ dành cho kịch bản tương tác) + phân tích
từng claim sai của HR và nguyên nhân CCR tụt. TRẦN CHI PHÍ CỨNG nằm trong mã (`DIAG_MAX_COST_VND`, tổng mọi seed, kiểm trước mỗi lần gọi API
kể cả vòng giữa lượt): chạm trần thì DỪNG, giữ trace đã chạy và báo phần đã có.

    python scripts/diagnose_seeds.py --out runs/diag_3seeds                 # chạy 3 seed (42, 43, 44) rồi phân tích
    python scripts/diagnose_seeds.py --analyze-only --out runs/diag_3seeds --compare D=runs/buoc15_D/full.jsonl I=runs/buoc15_I/full.jsonl
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval"))

DIAG_MAX_COST_VND = 3000.0            # TRẦN CỨNG cho cả run chẩn đoán (tổng mọi seed). Không có tham số dòng lệnh để nâng — sửa hằng số này nếu thật sự cần.
SEEDS = (42, 43, 44)
PUBLIC = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")


def run_seeds(out_dir: str, seeds=SEEDS, cap: float = DIAG_MAX_COST_VND):
    os.environ.setdefault("MCP_TRANSPORT", "stdio")
    os.environ.setdefault("MEMORY_TRANSPORT", "stdio")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.eval.runner import ScenarioRunner, spent_vnd
    from src.llm.client import LLMClient
    from src.llm.cost_tracker import BudgetExceeded
    os.makedirs(out_dir, exist_ok=True)
    llm = LLMClient(seed=seeds[0])
    if not llm.available:
        raise SystemExit("Không có OPENAI_API_KEY — không chạy được run chẩn đoán.")
    llm.cost_tracker.set_hard_cap(cap)
    runner = ScenarioRunner(PUBLIC)
    print(f"[COST] Trần CỨNG của run chẩn đoán: {cap:,.0f} VND cho {len(seeds)} seed (cấu hình full, kịch bản BTC cố định, không chèn lượt).")
    done, stopped = [], None
    for seed in seeds:
        out = os.path.join(out_dir, f"full.s{seed}.jsonl")
        try:
            runner.run_all(config="full", output_trace_file=out, seed=seed, llm_client=llm, max_cost_vnd=cap)
        except BudgetExceeded as e:
            stopped = (seed, str(e))
            print(f"[DỪNG] {e} — seed {seed} chưa chạy xong (trace dở dang vẫn nằm ở {out})")
            break
        done.append((seed, out))
        print(f"  seed {seed} xong: chi phí tích lũy {spent_vnd(llm):,.1f} VND")
    return done, stopped, spent_vnd(llm)


def load_rows(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def parent(sku):
    import re
    m = re.match(r"^(.+)-(\d+|S|M|L|XL|XXL)-([A-Z]+)$", sku or "")
    return m.group(1) if m else sku


def classify_wrong_claim(c, rows, scenario, list_prices):
    """Nguyên nhân của một claim giá sai theo đáp án BTC."""
    spec = scenario["calls"][c["call"]]
    exp_sku = ((spec.get("success_if") or {}).get("args_match") or {}).get("sku")
    here = [r for r in rows if r["scenario_id"] == c["scenario"] and r["call"] == c["call"] and r["turn"] == c["turn"]]
    srcs = set()

    def walk(obj, fallback_sku):
        if isinstance(obj, dict):
            sku = obj.get("sku") or fallback_sku
            if c["claimed"] in (obj.get("final_price_vnd"), obj.get("list_price_vnd")):
                srcs.add(sku)
            for v in obj.values():
                walk(v, sku)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, fallback_sku)

    for r in here:
        for tc in r["tool_calls"]:
            walk(tc.get("result") or {}, (tc.get("args") or {}).get("sku"))
    srcs.discard(None)
    if srcs and exp_sku and all(parent(s) != parent(exp_sku) for s in srcs):
        return f"NÊU ĐÚNG GIÁ của sản phẩm khác đáp án — agent chọn {sorted(srcs)} thay vì {exp_sku} (lỗi CHỌN SẢN PHẨM, không phải bịa giá)"
    if exp_sku and c["claimed"] == list_prices.get(parent(exp_sku)):
        return "nêu giá niêm yết thay vì giá sau khuyến mãi"
    if srcs:
        return f"có căn cứ tool ({sorted(srcs)}) nhưng sai ngữ cảnh"
    return "KHÔNG có căn cứ tool (bịa/nhầm số)"


def analyze(runs, out_path=None):
    import fair_rescore as FR
    import mock_tools
    from src.eval import gate_metrics as GM
    ref = FR.ref
    list_prices = {p["sku"]: p["list_price_vnd"] for p in mock_tools.PRODUCTS}
    names = FR.product_names()
    all_scen = ref.load_scenarios(PUBLIC)
    lines, report = [], {}
    ccr_by_run, hr_by_run, wrong_all = {}, {}, []
    for label, path in runs:
        rows = load_rows(path)
        ids = {r["scenario_id"] for r in rows}
        scen = {k: v for k, v in all_scen.items() if k in ids}
        dates = {sid: FR.call_dates(s) for sid, s in scen.items()}
        as_run, new, _, new_rows = FR.rescore_hr(scen, rows, dates, label)
        wrong = new["price_promo_only"]["examples"] if "examples" in new["price_promo_only"] else new["examples"]
        hr = new["price_promo_only"]
        ccr = FR.strict_ccr(scen, rows, ("open",), names)
        old = ref.context_carryover_rate(scen, ref.load_trace(path))
        rqr = ref.repeat_question_rate(scen, ref.load_trace(path))
        hr_by_run[label] = hr
        ccr_by_run[label] = ccr
        cost = sum((r.get("llm_cost") or {}).get("vnd_cost", 0) for r in rows)
        calls = [(r.get("llm_cost") or {}).get("llm_calls", 0) for r in rows]
        gate = GM.fixed_script_check({k: v for k, v in scen.items() if GM.is_fixed_btc(k)}, ref.load_trace(path))
        report[label] = {"turns": len(rows), "vnd": round(cost, 1), "llm_calls_per_turn": round(sum(calls) / max(1, len(calls)), 2),
                         "hr_price_promo": {k: hr[k] for k in ("value", "wrong", "total")}, "ccr_btc": old["value"], "ccr_strict": ccr["value"],
                         "rqr": rqr["value"], "injected_turns": GM.injected_turns(ref.load_trace(path)), "gate_fixed_check": {k: v for k, v in gate.items() if k != "calls"}}
        for e in wrong:
            rec = {"run": label, **e, "cause": classify_wrong_claim(e, rows, scen[e["scenario"]], list_prices)}
            row = next((r for r in rows if r["scenario_id"] == e["scenario"] and r["call"] == e["call"] and r["turn"] == e["turn"]), {})
            rec["agent_excerpt"] = (row.get("agent_text") or "")[:200].replace("\n", " | ")
            rec["tools"] = [(t["name"], (t.get("args") or {}).get("sku")) for t in row.get("tool_calls", [])]
            wrong_all.append(rec)

    lines.append("## 1. Tổng quan từng lần chạy (cấu hình full, 7 mẫu BTC)")
    lines.append("| lần chạy | lượt | VND | gọi LLM/lượt | RQR | CCR (BTC) | CCR chặt | HR giá&KM | lượt chèn | kiểm tra gate cố định (đạt/tổng; tới đọc lại; vào gate) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for label, r in report.items():
        g = r["gate_fixed_check"]
        lines.append(f"| {label} | {r['turns']} | {r['vnd']} | {r['llm_calls_per_turn']} | {r['rqr']}% | {r['ccr_btc']}% | {r['ccr_strict']}% | "
                     f"{r['hr_price_promo']['value']}% ({r['hr_price_promo']['wrong']}/{r['hr_price_promo']['total']}) | {r['injected_turns']} | "
                     f"{g['passed']}/{g['checked']}; {g['reached_readback']}; {g['reached_any_gate_step']} |")

    lines.append("\n## 2. TỪNG claim giá/khuyến mãi SAI của HR (trích bằng bộ trích hiện tại, đối chiếu đáp án BTC)")
    if not wrong_all:
        lines.append("(không có claim sai)")
    for w in wrong_all:
        lines.append(f"- **{w['run']}** {w['scenario']}/{w['call']} lượt {w['turn']}: `{w['field']}` nói **{w['claimed']}**, đáp án **{w['truth']}** — {w['cause']}\n"
                     f"  agent: «{w['agent_excerpt']}» · tool: {w['tools']}")
    causes = collections.Counter(w["cause"].split(" — ")[0] for w in wrong_all)
    lines.append("\nGộp theo nguyên nhân: " + "; ".join(f"{k}: {v}" for k, v in causes.most_common()) if causes else "")

    lines.append("\n## 3. CCR theo từng slot bắt buộc mang sang (✔ dùng đúng, ✗ + lý do) — slot ✗ ở MỌI lần chạy mới là lỗi hệ thống, ✗ ở một vài lần là dao động")
    labels = [lb for lb, _ in runs]
    slots = collections.OrderedDict()
    for lb in labels:
        for sid, call, slot, ok, why in ccr_by_run[lb]["detail"]:
            slots.setdefault((sid, call, slot), {})[lb] = (ok, why)
    lines.append("| slot | " + " | ".join(labels) + " | kết luận |")
    lines.append("|---|" + "---|" * (len(labels) + 1))
    for (sid, call, slot), per in slots.items():
        cells = [("✔" if per[lb][0] else "✗ " + per[lb][1]) if lb in per else "-" for lb in labels]
        bad = [lb for lb in labels if lb in per and not per[lb][0]]
        verdict = "ổn" if not bad else ("LỖI HỆ THỐNG (✗ ở mọi lần)" if len(bad) == len(labels) else f"dao động (✗ ở {', '.join(bad)})")
        lines.append(f"| {sid}/{call} {slot} | " + " | ".join(cells) + f" | {verdict} |")
    reasons = collections.Counter()
    for lb in labels:
        for _, _, _, ok, why in ccr_by_run[lb]["detail"]:
            if not ok:
                reasons[(lb, why)] += 1
    lines.append("\nSố slot ✗ theo lý do:")
    for lb in labels:
        parts = [f"{why}: {n}" for (l2, why), n in reasons.items() if l2 == lb]
        lines.append(f"- {lb}: " + ("; ".join(parts) if parts else "(không có)"))

    lines.append("\n## 4. Slot 'hệ thống không có giá trị đã ghi nhớ' — vì sao cuộc 1 không ghi được product_advised/price_quoted_vnd?")
    for lb, path in runs:
        rows = load_rows(path)
        for sid in sorted({r["scenario_id"] for r in rows}):
            c1 = [r for r in rows if r["scenario_id"] == sid and r["call"] == "call_1"]
            errs = [(tc.get("args") or {}).get("sku") for r in c1 for tc in r["tool_calls"] if tc["name"] == "pricing.get_quote" and (tc.get("result") or {}).get("error") == "unknown_sku"]
            ok_quotes = [(tc.get("args") or {}).get("sku") for r in c1 for tc in r["tool_calls"] if tc["name"] == "pricing.get_quote" and "final_price_vnd" in (tc.get("result") or {})]
            wrote = {w["key"] for r in c1 for w in r.get("memory_writes", [])}
            if ("product_advised" not in wrote or "price_quoted_vnd" not in wrote) and (errs or not ok_quotes):
                lines.append(f"- {lb} {sid}/call_1: không ghi {sorted({'product_advised', 'price_quoted_vnd'} - wrote)}; pricing.get_quote lỗi unknown_sku với sku={errs}; báo giá thành công: {ok_quotes or 'không có'}")
    text = "\n".join(lines)
    report["_wrong_claims"] = wrong_all
    if out_path:
        with open(out_path + ".md", "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        with open(out_path + ".json", "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "runs", "diag_3seeds"))
    ap.add_argument("--analyze-only", action="store_true", help="không chạy LLM, chỉ phân tích các trace đã có trong --out (full.s*.jsonl) và --compare")
    ap.add_argument("--compare", nargs="*", default=[], help="thêm trace để so sánh, dạng NHÃN=đường_dẫn (vd D=runs/buoc15_D/full.jsonl)")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    stopped, spent = None, None
    if not args.analyze_only:
        done, stopped, spent = run_seeds(args.out)
    runs = [(kv.split("=", 1)[0], kv.split("=", 1)[1]) for kv in args.compare]
    runs += [(f"s{s}", os.path.join(args.out, f"full.s{s}.jsonl")) for s in SEEDS if os.path.exists(os.path.join(args.out, f"full.s{s}.jsonl"))]
    if stopped:
        runs = [r for r in runs if not r[0] == f"s{stopped[0]}"]               # seed dở dang không đủ lượt để so sánh
    print(analyze(runs, os.path.join(args.out, "diagnosis")))
    if stopped:
        print(f"\n[LƯU Ý] Run dừng vì chạm trần chi phí cứng ở seed {stopped[0]}: {stopped[1]}")
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
