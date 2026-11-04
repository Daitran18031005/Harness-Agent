"""
Kiểm tra tự động kịch bản + lời thoại (luật S1–S14, docs/DATASET_TEXT_PLAN.md § 5) và in báo cáo phân bố so với ngưỡng M1.

    python scripts/validate_scenarios.py                       # bộ hiện có (public_sample + team_eval)
    python scripts/validate_scenarios.py --report              # + bảng phân bố so ngưỡng M1 (✔/✗)
    python scripts/validate_scenarios.py --scenarios dataset/agent_eval --dialogues dataset/asr --report

Mã thoát: 0 nếu không có LỖI; 1 nếu có LỖI. `--no-existing` bỏ qua bộ hiện có (public_sample + team_eval).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

BTC = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS")
EXISTING = [os.path.join(BTC, "test_set", "public_sample"), os.path.join(BTC, "test_set", "team_eval")]

# Ngưỡng M1 (DATASET_PLAN § 1) — phần "đích" lấy từ cơ cấu đã duyệt
THRESHOLDS = [("calls", "Hội thoại (cuộc gọi/chat)", 120), ("multi_session", "Khách đa phiên (≥ 2 cuộc)", 30), ("ge3_sessions", "Khách ≥ 3 phiên", 1),
              ("multi_channel", "Khách đa kênh", 10)]
HARD_TYPES = ["đổi ý", "mâu thuẫn với phiên trước", "KM hết hạn", "hỏi ngoài tài liệu"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", action="append", default=[], help="thư mục kịch bản BTC-format (lặp lại được)")
    ap.add_argument("--dialogues", default=None, help="thư mục lời thoại từng lượt (dataset/asr)")
    ap.add_argument("--no-existing", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json", default=None, help="ghi báo cáo JSON")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    from src.dataset.validate import distribution, load_dialogues, load_scenarios, validate_all
    dirs = ([] if args.no_existing else EXISTING) + args.scenarios
    scenarios = load_scenarios(dirs)
    dialogues = load_dialogues(args.dialogues)
    issues = validate_all(scenarios, dialogues)
    errors = [i for i in issues if i.severity == "LỖI"]
    warns = [i for i in issues if i.severity != "LỖI"]
    print(f"## Kiểm tra {len(scenarios)} kịch bản ({sum(len(s['calls']) for s in scenarios.values())} cuộc), {len(dialogues)} file lời thoại")
    for i in issues:
        print(i.line())
    print(f"\n=> {len(errors)} LỖI, {len(warns)} CẢNH BÁO")

    dist = distribution(scenarios, dialogues)
    if args.report:
        print("\n## Phân bố so với ngưỡng M1 (S14)\n")
        print("| hạng mục | hiện có | ngưỡng | |\n|---|---:|---:|---|")
        for key, label, need in THRESHOLDS:
            print(f"| {label} | {dist[key]} | ≥ {need} | {'✔' if dist[key] >= need else '✗ thiếu ' + str(need - dist[key])} |")
        print(f"| Kịch bản đa phiên | {dist['multi_session_scenarios']} | ≥ 20 | {'✔' if dist['multi_session_scenarios'] >= 20 else '✗ thiếu ' + str(20 - dist['multi_session_scenarios'])} |")
        for t in HARD_TYPES:
            n = dist["hard_cases"].get(t, 0)
            print(f"| Ca khó — {t} | {n} | ≥ 5 | {'✔' if n >= 5 else '✗ thiếu ' + str(5 - n)} |")
        print(f"| Persona | {len(dist['personas'])} | ≥ 3 | {'✔' if len(dist['personas']) >= 3 else '✗'} |")
        print(f"| Ca khó khác (giữ lại) | {dist['hard_cases'].get('khác (giữ lại)', 0)} | — | |")
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"errors": [i.__dict__ for i in errors], "warnings": [i.__dict__ for i in warns], "distribution": dist}, fh, ensure_ascii=False, indent=1)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
