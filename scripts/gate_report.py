"""
Báo cáo HAI loại đo của order gate từ một file trace (chỉ đọc, không gọi API):
  [1] TSR tương tác (TSR chính; khách mô phỏng --gate-assist)   [2] kiểm tra kịch bản cố định (7 mẫu BTC; không tính TSR chính)

    python scripts/gate_report.py runs/buoc15_I/full.jsonl [--scenarios DIR ...]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trace")
    ap.add_argument("--scenarios", nargs="*", default=[os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")])
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    from src.eval import gate_metrics as GM
    ref = GM.ref
    trace = ref.load_trace(args.trace)
    ids = {sid for sid, _ in trace}
    scenarios = {}
    for d in args.scenarios:
        scenarios.update({k: v for k, v in ref.load_scenarios(d).items() if k in ids})
    print(GM.report_text(scenarios, trace))
    return 0


if __name__ == "__main__":
    sys.exit(main())
