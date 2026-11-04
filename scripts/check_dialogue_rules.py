"""
Kiểm các lời thoại ĐÃ SINH bằng luật P1–P4 mới (src/dataset/rules.py) — không gọi LLM, không tốn tiền.

    python scripts/check_dialogue_rules.py [--dialogues dataset/asr]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dialogues", default=os.path.join(CODE_DIR, "dataset", "asr"))
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    from src.dataset.specs import build_sample10
    from src.dataset.validate import load_dialogues
    from src.dataset.writer import rule_errors
    dlgs = load_dialogues(args.dialogues)
    n_bad = n_all = 0
    by_rule = {}
    for fr in build_sample10():
        sid = fr["scenario"]["scenario_id"]
        for call in fr["calls"]:
            rec = dlgs.get(f"{sid}/{call['name']}")
            if not rec:
                continue
            n_all += 1
            errs = rule_errors(rec["turns"], fr, call)
            n_bad += bool(errs)
            for e in errs:
                by_rule[e[:2]] = by_rule.get(e[:2], 0) + 1
                print(f"[{sid}/{call['name']}] {e}")
    print(f"\n{n_bad}/{n_all} cuộc vi phạm ≥ 1 luật; theo luật: {by_rule}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
