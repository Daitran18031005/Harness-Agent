"""
Báo cáo bước 15 giai đoạn 2 từ các trace đã chạy (KHÔNG gọi LLM): gộp 2 bộ (7 mẫu BTC `sample/` + 15 kịch bản sinh `gen/`) thành 22 kịch bản cho mỗi seed,
chấm bằng reference_eval của BTC (qua `evaluation.scoring`), rồi tính mean ± std qua các seed và đối chiếu ngưỡng BTC.

    python scripts/gd2_report.py --root runs/gd2_run [--scenarios-sample DIR] [--scenarios-gen DIR] [--out-dir DIR]

Thư mục `--root` có `sample/` và `gen/`, mỗi thư mục là đầu ra của `run_eval.py --config both --repeats N` (full.r1.jsonl, baseline.r1.jsonl, … hoặc full.jsonl nếu 1 lần).
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

from evaluation.scoring import REFERENCE_EVAL, load_reference, score   # noqa: E402

BTC_SAMPLES = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")
GEN_SAMPLES = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "generated_m1")


def _runs(folder: str, cfg: str) -> dict:
    """{chỉ số lần chạy: đường dẫn} — `full.r1.jsonl` → 1; `full.jsonl` → 1."""
    out = {}
    for p in glob.glob(os.path.join(folder, f"{cfg}*.jsonl")):
        m = re.fullmatch(rf"{cfg}(?:\.r(\d+))?\.jsonl", os.path.basename(p))
        if m:
            out[int(m.group(1) or 1)] = p
    return out


def _concat(paths: list, dest: str) -> str:
    with open(dest, "w", encoding="utf-8") as w:
        for p in paths:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        w.write(line if line.endswith("\n") else line + "\n")
    return dest


def _copy_union(dirs: list, dest: str) -> str:
    os.makedirs(dest, exist_ok=True)
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.json")):
            with open(p, "rb") as r, open(os.path.join(dest, os.path.basename(p)), "wb") as w:
                w.write(r.read())
    return dest


def _metrics(rep: dict) -> dict:
    s = rep["system"]
    lat = s["latency"]
    out = {"tsr": s["task_success_rate"]["value"], "tsr_hard": (s["task_success_rate"].get("hard_cases") or {}).get("value"),
           "rqr": s["repeat_question_rate"]["value"], "ccr": s["context_carryover_rate"]["value"],
           "hr_price_promo": s["hallucination_rate"]["price_promo_only"]["value"], "hr_all": s["hallucination_rate"]["value"],
           "avg_turns_per_call": s["avg_turns_per_call"], "calls_to_close": s["calls_to_close"]["value"],
           "guardrail_violations": s["guardrail_violations"]["total"],
           "ttft_p95_ms": (lat.get("ttft") or {}).get("p95_ms"), "total_p95_ms": (lat.get("total") or {}).get("p95_ms"),
           "n_turns": lat.get("n_turns"), "call_brief_p95_ms": (lat.get("call_brief") or {}).get("p95_ms")}
    base = rep.get("baseline")
    if base:
        out.update({"base_tsr": base["task_success_rate"]["value"], "base_rqr": base["repeat_question_rate"]["value"], "base_ccr": base["context_carryover_rate"]["value"],
                    "base_hr_price_promo": base["hallucination_rate"]["price_promo_only"]["value"], "base_total_p95_ms": (base["latency"].get("total") or {}).get("p95_ms")})
        out.update(rep.get("comparison") or {})
    return out


def _mean_std(vals: list):
    xs = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not xs:
        return None
    return {"mean": round(statistics.mean(xs), 2), "std": round(statistics.stdev(xs), 2) if len(xs) > 1 else 0.0, "n": len(xs), "values": xs}


def build(root: str, scen_sample: str, scen_gen: str, out_dir: str) -> dict:
    ref = load_reference(REFERENCE_EVAL)
    tmp = os.path.join(out_dir, "_merged")
    os.makedirs(tmp, exist_ok=True)
    all_dir = _copy_union([scen_sample, scen_gen], os.path.join(tmp, "scenarios_all"))
    scen = {"all": ref.load_scenarios(all_dir), "sample": ref.load_scenarios(scen_sample), "gen": ref.load_scenarios(scen_gen)}
    sets = {"sample": os.path.join(root, "sample"), "gen": os.path.join(root, "gen")}
    seeds = sorted(set(_runs(sets["sample"], "full")) & set(_runs(sets["gen"], "full")))
    if not seeds:
        raise SystemExit(f"Không có lần chạy chung của sample/ và gen/ trong {root}")
    per_seed = {}
    for r in seeds:
        merged = {}
        for cfg in ("full", "baseline"):
            paths = [p for p in (_runs(sets["sample"], cfg).get(r), _runs(sets["gen"], cfg).get(r)) if p]
            merged[cfg] = _concat(paths, os.path.join(tmp, f"{cfg}.r{r}.jsonl"))
        entry = {"all": _metrics(score(ref, scen["all"], merged["full"], merged["baseline"]))}
        for part in ("sample", "gen"):                                       # tách hai loại kịch bản (cố định của BTC / tương tác có khách mô phỏng)
            fp, bp = _runs(sets[part], "full").get(r), _runs(sets[part], "baseline").get(r)
            entry[part] = _metrics(score(ref, scen[part], fp, bp)) if fp and bp else None
        per_seed[r] = entry
    keys = sorted({k for e in per_seed.values() for k in e["all"]})
    agg = {k: _mean_std([e["all"].get(k) for e in per_seed.values()]) for k in keys}
    rqr_red = [e["all"]["rqr_relative_reduction_pct"] for e in per_seed.values() if e["all"].get("rqr_relative_reduction_pct") is not None]
    verdict = {"seeds": len(seeds), "turns_per_seed": per_seed[seeds[0]]["all"].get("n_turns"),
               "rqr_reduction_pct_mean": round(statistics.mean(rqr_red), 1) if rqr_red else None,
               "meets_rqr_40pct": bool(rqr_red) and statistics.mean(rqr_red) >= 40,
               "meets_tsr_70pct": bool(agg.get("tsr")) and agg["tsr"]["mean"] >= 70,
               "meets_hr_price_5pct": bool(agg.get("hr_price_promo")) and agg["hr_price_promo"]["mean"] <= 5,
               "better_than_baseline_tsr": bool(agg.get("tsr") and agg.get("base_tsr")) and agg["tsr"]["mean"] > agg["base_tsr"]["mean"],
               "ttft_p95_ms_mean": (agg.get("ttft_p95_ms") or {}).get("mean"), "ttft_p95_target_ms": 3000}
    return {"root": root, "scenarios": {k: len(v) for k, v in scen.items()}, "per_seed": per_seed, "aggregate": agg, "verdict": verdict}


def render(rep: dict) -> str:
    a, v = rep["aggregate"], rep["verdict"]
    def cell(k):
        x = a.get(k)
        return f"{x['mean']} ± {x['std']}" if x else "—"
    rows = [("TSR (%)", "tsr", "base_tsr"), ("RQR (%)", "rqr", "base_rqr"), ("CCR (%)", "ccr", "base_ccr"), ("HR giá/KM (%)", "hr_price_promo", "base_hr_price_promo"),
            ("Total p95 (ms)", "total_p95_ms", "base_total_p95_ms")]
    lines = [f"# Bước 15 GĐ2 — {v['seeds']} seed, {rep['scenarios']['all']} kịch bản ({rep['scenarios']['sample']} mẫu BTC + {rep['scenarios']['gen']} sinh), {v['turns_per_seed']} lượt/seed (cấu hình full)", "",
             "| Chỉ số | full (mean ± std) | baseline (mean ± std) |", "|---|---:|---:|"]
    lines += [f"| {name} | {cell(k)} | {cell(b)} |" for name, k, b in rows]
    lines += ["", f"- TTFT p95 (full): {cell('ttft_p95_ms')} ms (mục tiêu ≤ {v['ttft_p95_target_ms']} ms); cuộc gọi tới chốt: {cell('calls_to_close')}; lượt/cuộc: {cell('avg_turns_per_call')}; vi phạm guardrail: {cell('guardrail_violations')}",
              f"- RQR giảm so với baseline: {v['rqr_reduction_pct_mean']}% (ngưỡng ≥ 40%) → {'ĐẠT' if v['meets_rqr_40pct'] else 'CHƯA ĐẠT'}",
              f"- TSR ≥ 70%: {'ĐẠT' if v['meets_tsr_70pct'] else 'CHƯA ĐẠT'} · HR giá/KM ≤ 5%: {'ĐẠT' if v['meets_hr_price_5pct'] else 'CHƯA ĐẠT'} · TSR hơn baseline: {'có' if v['better_than_baseline_tsr'] else 'không'}",
              "", "## Theo từng seed (full)", "", "| seed | TSR | TSR mẫu BTC | TSR sinh (tương tác) | RQR | CCR | HR giá/KM |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r, e in sorted(rep["per_seed"].items()):
        f = lambda part, k: (e[part] or {}).get(k, "—") if part != "all" else e["all"].get(k, "—")
        lines.append(f"| {r} | {f('all','tsr')} | {f('sample','tsr')} | {f('gen','tsr')} | {f('all','rqr')} | {f('all','ccr')} | {f('all','hr_price_promo')} |")
    lines += ["", "> Lưu ý: TSR của 7 mẫu BTC cố định bị chặn bởi order gate (lời khách không trả lời câu hỏi của gate) — xem § 11.31; TSR chính là cột 'sinh (tương tác)'."]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--scenarios-sample", default=BTC_SAMPLES)
    ap.add_argument("--scenarios-gen", default=GEN_SAMPLES)
    ap.add_argument("--out-dir", default=None, help="mặc định = --root")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    out_dir = a.out_dir or a.root
    os.makedirs(out_dir, exist_ok=True)
    rep = build(a.root, a.scenarios_sample, a.scenarios_gen, out_dir)
    with open(os.path.join(out_dir, "gd2_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    md = render(rep)
    with open(os.path.join(out_dir, "gd2_report.md"), "w", encoding="utf-8") as f:
        f.write(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
