"""python -m evaluation --trace runs/X/full.jsonl [--baseline ...] [--scenarios DIR] [--out-dir DIR]

Chỉ đọc trace + kịch bản; ghi report.json, failures.json/.txt, manual_review.csv vào --out-dir. Không gọi LLM.
"""
import argparse
import json
import os
import sys

from . import failures, scoring, sheet


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evaluation", description=__doc__)
    ap.add_argument("--trace", required=True, help="trace JSONL của hệ thống (config=full)")
    ap.add_argument("--baseline", help="trace JSONL của baseline_no_memory")
    ap.add_argument("--scenarios", default=scoring.DEFAULT_SCENARIOS)
    ap.add_argument("--out-dir", default=None, help="mặc định: thư mục chứa file trace, thêm /eval14a")
    ap.add_argument("--max-old-facts", type=int, default=2, help="ngưỡng 'đọc vẹt' trong câu chào")
    ap.add_argument("--sheet-n", type=int, default=20, help="số lượt trong file chấm tay")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    out_dir = a.out_dir or os.path.join(os.path.dirname(os.path.abspath(a.trace)), "eval14a")
    os.makedirs(out_dir, exist_ok=True)
    ref = scoring.load_reference()
    scenarios = ref.load_scenarios(a.scenarios)
    trace = ref.load_trace(a.trace)
    cases = failures.failure_cases(ref, scenarios, trace, a.max_old_facts)
    report = scoring.score(ref, scenarios, a.trace, a.baseline)

    def dump(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
    dump("report.json", report)
    dump("failures.json", cases)
    text = failures.format_cases(cases)
    with open(os.path.join(out_dir, "failures.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)
    rows = sheet.pick_turns(trace, cases, a.sheet_n, a.seed)
    sheet.write_csv(rows, os.path.join(out_dir, "manual_review.csv"))

    s = report["system"]
    print(f"Kịch bản: {len(scenarios)} | TSR {s['task_success_rate']['value']}% | RQR {s['repeat_question_rate']['value']}% | "
          f"CCR {s['context_carryover_rate']['value']}% | HR giá/KM {s['hallucination_rate']['price_promo_only']['value']}% | "
          f"guardrail {s['guardrail_violations']['total']}")
    print(f"{len(cases)} ca sai, {len(rows)} lượt chấm tay → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
