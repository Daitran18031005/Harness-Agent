"""File mẫu chấm tay N lượt (CSV mở được bằng Excel): chọn xen kẽ giữa các kịch bản, ưu tiên lượt đã bị đánh dấu sai."""
import csv
import random

RUBRIC_COLS = ["dung_san_pham", "khong_hoi_lai", "khong_doc_vet", "khong_bia_so", "xung_ho_tu_nhien", "ghi_chu"]
COLUMNS = ["scenario", "call", "turn", "customer_text", "agent_text", "co_tu_dong"] + RUBRIC_COLS


def pick_turns(trace: dict, cases: list, n: int = 20, seed: int = 0) -> list:
    flagged = {}
    for c in cases:
        if c["turn"] is not None:
            key = (c["scenario"], c["call"], c["turn"])
            flagged.setdefault(key, []).append(c["metric"])
    rng = random.Random(seed)
    by_scn = {}
    for (sid, call), rows in sorted(trace.items()):
        for r in rows:
            by_scn.setdefault(sid, []).append((sid, call, r["turn"], r))
    for rows in by_scn.values():
        rng.shuffle(rows)
        rows.sort(key=lambda x: -len(flagged.get(x[:3], [])))      # sort ổn định: giữ thứ tự ngẫu nhiên trong cùng mức
    picked = []
    queues = [by_scn[k] for k in sorted(by_scn)]
    while len(picked) < n and any(queues):
        for q in queues:
            if q and len(picked) < n:
                picked.append(q.pop(0))
    picked.sort(key=lambda x: x[:3])
    return [{"scenario": sid, "call": call, "turn": turn, "customer_text": r.get("customer_text", ""),
             "agent_text": r.get("agent_text", ""), "co_tu_dong": ",".join(flagged.get((sid, call, turn), [])),
             **{c: "" for c in RUBRIC_COLS}} for sid, call, turn, r in picked]


def write_csv(rows: list, path: str):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
