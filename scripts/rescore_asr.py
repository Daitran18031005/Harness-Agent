"""
Chấm LẠI offline các giả thuyết ASR đã lưu (không giải mã lại, không tốn thời gian model) bằng luật ITN/trích thực thể HIỆN TẠI, rồi so với số
đã lưu trong báo cáo cũ — để báo số "luật v1" vs "luật v2" khi nâng khóa luật (config/asr_rules.lock.json).

    python scripts/rescore_asr.py --old runs/asr_rules_v1/compare_report_v1.json --items runs/asr_compare/items.json

WER thô không đổi (không qua ITN); đổi ở: WER "ITN 2 vế", entity số tiền/SĐT, entity BTC.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
sys.path.insert(0, HERE)


def old_scored_ids(path):
    return json.load(open(path, encoding="utf-8"))["scored"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", default=os.path.join(CODE_DIR, "runs", "asr_rules_v1", "compare_report_v1.json"))
    ap.add_argument("--items", default=None, help="(không còn dùng — danh sách file lấy từ báo cáo cũ)")
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "runs", "asr_rules_v2"))
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    import compare_asr as C
    gts = {d["id"]: d for d in json.load(open(C.GT_PATH, encoding="utf-8"))["dialogues"]}
    first = next(iter(old_scored_ids(args.old)))
    items = [{"id": i, "gt_id": i.split("~")[0], "noise": v["attrs"].get("noise"), "attrs": v["attrs"]}      # dựng danh sách file từ CHÍNH báo cáo cũ
             for i, v in json.load(open(args.old, encoding="utf-8"))["scored"][first].items()]
    for it in items:
        it["attrs"].setdefault("split", "dev" if it["gt_id"] in C.DEV_SET else "unseen")      # items.json cũ chưa có khóa split
    old = json.load(open(args.old, encoding="utf-8"))
    for per in old["scored"].values():
        for v in per.values():
            v["attrs"].setdefault("split", "dev")                                    # báo cáo v1 cũ chưa có khóa split (toàn bộ là D01–D04)
    lock_old = json.load(open(os.path.join(os.path.dirname(args.old), "asr_rules.lock.v1.json"), encoding="utf-8"))["version"]
    lock_new = json.load(open(os.path.join(CODE_DIR, "config", "asr_rules.lock.json"), encoding="utf-8"))["version"]

    new_scored = {}
    for label, per in old["scored"].items():
        fake = {"results": {i: {"text": v["hypothesis"], "decode_s": v["decode_s"], "duration_s": v["duration_s"]} for i, v in per.items() if "hypothesis" in v}}
        new_scored[label] = C.score_backend(fake, items, gts)

    groups = C.groups_for(items)
    rows = ["| điều kiện | backend | WER thô (v1 = v2) | WER ITN 2 vế v1 → v2 | entity số tiền v1 → v2 | entity SĐT v1 → v2 | entity BTC v1 → v2 |", "|---|---|---|---|---|---|---|"]
    changed = 0
    for gname, sel in groups:
        for label in old["scored"]:
            a, b = C.aggregate(old["scored"][label], sel), C.aggregate(new_scored[label], sel)
            if not a["n"]:
                continue
            same = all(a[k] == b[k] for k in ("wer_itn", "ent_money", "ent_phone", "ent_btc"))
            changed += 0 if same else 1
            rows.append(f"| {gname} | {label} | {C.fmt(a['wer_raw'])} | {C.fmt(a['wer_itn'])} → {C.fmt(b['wer_itn'])} | {C.fmt(a['ent_money'])} → {C.fmt(b['ent_money'])} | "
                        f"{C.fmt(a['ent_phone'])} → {C.fmt(b['ent_phone'])} | {C.fmt(a['ent_btc'])} → {C.fmt(b['ent_btc'])} |" + ("" if same else " **đổi**"))
    text = (f"Chấm lại từ giả thuyết ĐÃ LƯU: luật {lock_old} → {lock_new}. Phạm vi: {C.SCOPE}; nhiễu/điện thoại là mô phỏng; entity trên D01–D04 là trong tập phát triển.\n\n"
            + "\n".join(rows) + f"\n\n{changed} dòng (điều kiện × backend) có số thay đổi.\n")
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "rescore_v1_vs_v2.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(args.out, "rescore_v2.json"), "w", encoding="utf-8") as fh:
        json.dump({"old_version": lock_old, "new_version": lock_new, "scored_v2": new_scored}, fh, ensure_ascii=False, indent=1)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
