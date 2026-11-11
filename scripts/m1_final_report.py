"""Gộp trace của lần chạy chia luồng (runs/<root>/{sample,s1,s2,...}/{full,baseline}.jsonl) rồi chấm bằng reference_eval.py của BTC.

    python scripts/m1_final_report.py --root runs/m1_final

Ghi <root>/full.jsonl, baseline.jsonl, scen_all/ (7 BTC + team_eval), report.json (đúng định dạng BTC) và report.md (bảng A.6 + TSR theo nhóm kịch bản + lý do trượt)."""
import argparse, collections, glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTC = os.path.join(HERE, "BTC-Data-Vong1-TEAMS")
sys.path.insert(0, os.path.join(BTC, "eval"))
import reference_eval as ref  # noqa: E402


def group(sid: str) -> str:
    return sid.rsplit("-", 1)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    a = ap.parse_args()
    root = a.root
    for cfg in ("full", "baseline"):
        parts = sorted(glob.glob(os.path.join(root, "sample", f"{cfg}.jsonl")) + glob.glob(os.path.join(root, "s[0-9]*", f"{cfg}.jsonl")))      # không lấy thư mục chạy thử (pilot*)
        with open(os.path.join(root, f"{cfg}.jsonl"), "w", encoding="utf-8") as out:
            for p in parts:
                out.write(open(p, encoding="utf-8").read())
    scen = os.path.join(root, "scen_all")
    shutil.rmtree(scen, ignore_errors=True)
    os.makedirs(scen)
    for d in ("public_sample", "team_eval"):
        for f in glob.glob(os.path.join(BTC, "test_set", d, "*.json")):
            shutil.copy(f, scen)
    full, base = os.path.join(root, "full.jsonl"), os.path.join(root, "baseline.jsonl")
    proc = subprocess.run([sys.executable, os.path.join(BTC, "eval", "reference_eval.py"), "--scenarios", scen, "--trace", full, "--baseline", base,
                           "--out", os.path.join(root, "report.json")], env={**os.environ, "PYTHONUTF8": "1"}, text=True, capture_output=True, encoding="utf-8")
    print(proc.stdout, proc.stderr)

    scenarios, lines = ref.load_scenarios(scen), ["```", proc.stdout.strip(), "```", ""]
    ran = {sid for sid, _ in ref.load_trace(full)}
    lines.append(f"Kịch bản: {len(scenarios)} (có trace full: {len(ran)}).\n")
    lines.append("| Nhóm | Số kịch bản | TSR full | TSR baseline | RQR full | CCR full |\n|---|---|---|---|---|---|")
    fails = collections.Counter()
    for g in sorted({group(s) for s in scenarios}) + ["TẤT CẢ"]:
        sub = {k: v for k, v in scenarios.items() if g == "TẤT CẢ" or group(k) == g}
        row = [g, str(len(sub))]
        for path in (full, base):
            tr = ref.load_trace(path)
            t = ref.task_success_rate(sub, tr)
            row.append(f"{t['value']} ({t['passed']}/{t['total']})")
            if path == full:
                keep = (ref.repeat_question_rate(sub, tr)["value"], ref.context_carryover_rate(sub, tr)["value"])
        lines.append("| " + " | ".join(row + [str(keep[0]), str(keep[1])]) + " |")
    tr = ref.load_trace(full)
    per = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            earlier = [r for c in sorted(s["calls"]) if c < call for r in tr.get((sid, c), [])]
            ok, reasons = ref.check_call(spec, tr.get((sid, call), []), ref.created_order_ids(earlier))
            if ok is False:
                per.append((sid, call, reasons))
                for r in reasons:
                    fails[r.split(":")[0].split(" khớp")[0][:60]] += 1
    lines += ["", "Lý do trượt (theo cuộc gọi, cấu hình full):", ""] + [f"- {n} × {r}" for r, n in fails.most_common(15)]
    lines += ["", "Cuộc gọi trượt:", ""] + [f"- {sid}/{call}: {'; '.join(rs)}" for sid, call, rs in per]
    open(os.path.join(root, "report.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("→", os.path.join(root, "report.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
