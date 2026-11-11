"""So sánh các lượt chạy bật/tắt từng thành phần trên CÙNG bộ kịch bản (runs/ab/<tên>/full.jsonl) → runs/ab/report.md.

    python scripts/ab_report.py [--root runs/ab] [--base base]

Mỗi cột là một lượt chạy; cột `base` = mọi thành phần bật. Chấm bằng reference_eval.py của BTC, chỉ trên các kịch bản có trong trace."""
import argparse, glob, json, os, statistics, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTC = os.path.join(HERE, "BTC-Data-Vong1-TEAMS")
sys.path.insert(0, os.path.join(BTC, "eval"))
import reference_eval as ref  # noqa: E402


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def summarize(path, scenarios):
    tr = ref.load_trace(path)
    sc = {k: v for k, v in scenarios.items() if any(s == k for s, _ in tr)}
    rows = [r for rs in tr.values() for r in rs]
    llm = [r for r in rows if (r.get("latency_detail") or {}).get("round_ms")]
    t = ref.task_success_rate(sc, tr)
    hr = ref.hallucination_rate(sc, tr)
    first = [r["latency"]["ttft_ms"] for r in rows if r["turn"] == 1 and r["call"] != "call_1"]
    return {
        "Kịch bản": len(sc), "Lượt": len(rows),
        "TSR %": f"{t['value']} ({t['passed']}/{t['total']})",
        "RQR %": ref.repeat_question_rate(sc, tr)["value"], "CCR %": ref.context_carryover_rate(sc, tr)["value"],
        "HR giá/KM %": hr["price_promo_only"]["value"], "Guardrail (ca)": ref.guardrail_violations(sc, tr)["total"] if hasattr(ref, "guardrail_violations") else "-",
        "TTFT p50 (ms)": pct([r["latency"]["ttft_ms"] for r in rows], .5), "TTFT p95 (ms)": pct([r["latency"]["ttft_ms"] for r in rows], .95),
        "Total p95 (ms)": pct([r["latency"]["total_ms"] for r in rows], .95),
        "TTFT lượt đầu cuộc gọi lại p50 (ms)": pct(first, .5),
        "Vòng LLM / lượt có LLM": round(statistics.mean(len(r["latency_detail"]["round_ms"]) for r in llm), 2) if llm else None,
        "Đọc hiểu TB (ms)": round(statistics.mean(r["latency_detail"].get("reader_ms", 0) for r in llm)) if llm else None,
        "Thời gian tool TB (ms)": round(statistics.mean(r["latency_detail"].get("tool_ms", 0) for r in llm)) if llm else None,
        "Lượt code xử lý %": round(100 * (len(rows) - len(llm)) / max(1, len(rows))),
        "Chi phí (VND)": round(sum((r.get("llm_cost") or {}).get("vnd_cost", 0) for r in rows)),
        "_fail": {(f["scenario"], f["call"]) for f in t["failures"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(HERE, "runs", "ab"))
    ap.add_argument("--base", default="base")
    a = ap.parse_args()
    scenarios = ref.load_scenarios(os.path.join(HERE, "runs", "m1_final2", "scen_all"))
    runs = {os.path.basename(os.path.dirname(p)): summarize(p, scenarios) for p in sorted(glob.glob(os.path.join(a.root, "*", "full.jsonl")))}
    names = [a.base] + [n for n in runs if n != a.base] if a.base in runs else list(runs)
    keys = [k for k in runs[names[0]] if not k.startswith("_")]
    lines = ["| Chỉ số | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    lines += ["| " + k + " | " + " | ".join(str(runs[n][k]) for n in names) + " |" for k in keys]
    if a.base in runs:
        lines += ["", "Cuộc gọi đổi kết quả so với `" + a.base + "`:", ""]
        for n in names[1:]:
            worse, better = sorted(runs[n]["_fail"] - runs[a.base]["_fail"]), sorted(runs[a.base]["_fail"] - runs[n]["_fail"])
            lines.append(f"- `{n}`: trượt thêm {len(worse)} {['/'.join(x) for x in worse]}; đạt thêm {len(better)} {['/'.join(x) for x in better]}")
    out = os.path.join(a.root, "report.md")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
