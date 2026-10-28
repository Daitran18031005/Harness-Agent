"""
Báo cáo KHUNG 54 kịch bản còn lại (CHƯA gọi LLM, 0 VND): bảng phân bố + 5 khung chọn ngẫu nhiên (seed cố định) + kiểm ràng buộc.

    python scripts/frames54_report.py [--seed 42] [--out dataset/review]

Ghi: <out>/frames54_distribution.md, <out>/frames54_random5.md, <out>/../frames54/SC-Dxx.frame.json (khung đầy đủ để duyệt).
"""
import argparse
import collections
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)


def table(title, counter, total=None):
    rows = [f"| {k} | {v} |" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))]
    return f"**{title}**\n\n| giá trị | số kịch bản |\n|---|---|\n" + "\n".join(rows) + (f"\n| *tổng* | *{total}* |" if total else "") + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "dataset", "review"))
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from src.dataset.frames54 import PLAN, build_frames54
    from src.dataset.rules import is_order_call
    frames = build_frames54()
    os.makedirs(args.out, exist_ok=True)
    fdir = os.path.join(os.path.dirname(args.out), "frames54")
    os.makedirs(fdir, exist_ok=True)
    for fr in frames:
        with open(os.path.join(fdir, f"{fr['scenario']['scenario_id']}.frame.json"), "w", encoding="utf-8") as fh:
            json.dump(fr, fh, ensure_ascii=False, indent=1)

    sc = [f["scenario"] for f in frames]
    calls = [(f["scenario"], c) for f in frames for c in f["calls"]]
    by_group = collections.Counter(s["group"] for s in sc)
    n_calls = collections.Counter(len(f["calls"]) for f in frames)
    persona = collections.Counter(s["persona"] for s in sc)
    hard = collections.Counter(s["hard_case"] or "(không)" for s in sc)
    chan = collections.Counter(c["channel"] for _, c in calls)
    first_ch = collections.Counter(f["calls"][0]["channel"] for f in frames)
    industry = collections.Counter(s["industry"] for s in sc)
    arche = collections.Counter(s["archetype"] for s in sc)
    region = collections.Counter("miền Nam" if s["south"] else "miền Bắc" for s in sc)
    multi_ch = sum(1 for f in frames if len({c["channel"] for c in f["calls"]}) >= 2)
    order_calls = [c for _, c in calls if is_order_call(c)]
    over = [s["scenario_id"] for s in sc if s["hard_case"] == "vuot_ngan_sach_2_lua_chon"]
    saved = [s["scenario_id"] for f in frames for s in [f["scenario"]] if any(c.get("saved_address") for c in f["calls"])]
    teen = sum(1 for _, c in calls if c["style"] == "teencode")
    conflict = [s["scenario_id"] for s in sc if s["persona"] == "khach_da_kenh_mau_thuan" and s["hard_case"] == "mau_thuan_phien_truoc"]
    demo = {"mac_ca": hard["mac_ca"], "tu_choi/hoan_giua_gate": hard["tu_choi_giua_gate"] + hard["hoan_giua_gate"], "het_hang_bien_the": hard["het_hang_bien_the"],
            "tu_nhan_khach_cu_chua_sdt": hard["tu_nhan_khach_cu_chua_sdt"], "so_noi_bang_chu": hard["so_noi_bang_chu"]}
    cross = collections.Counter((s["group"], s["archetype"], len(f["calls"])) for f in frames for s in [f["scenario"]])
    ctab = "\n".join(f"| {g} | {a} | {n} calls | {v} |" for (g, a, n), v in sorted(cross.items()))

    checks = [("≥ 3 ca vượt ngân sách > 20% (nhánh HAI LỰA CHỌN)", len(over) >= 3, f"{len(over)}: {', '.join(over)}"),
              ("≥ 2 khách cũ có sẵn địa chỉ (gate chỉ xác nhận)", len(saved) >= 2, f"{len(saved)}: {', '.join(saved)}"),
              ("Tổng đúng cơ cấu 54 (A 13 + B 10 + C 31)", (by_group["A"], by_group["B"], by_group["C"]) == (13, 10, 31), dict(by_group)),
              ("Số cuộc gọi mới = 87 (+17 mẫu + 31 hiện có = 135)", len(calls) == 87, len(calls)),
              ("≥ 2 khung mâu thuẫn phiên trước với persona khach_da_kenh_mau_thuan (duyệt 2026-10-24)", len(conflict) >= 2, f"{len(conflict)}: {', '.join(conflict)}"),
              ("Mỗi kiểu tái hiện lỗi demo có ≥ 1 khung (mặc cả · từ chối/hoãn giữa gate · hết hàng biến thể · tự nhận khách cũ chưa có SĐT · số nói bằng chữ)",
               all(demo[k] >= 1 for k in demo), dict(demo))]
    md = ["# Phân bố 54 khung kịch bản còn lại (chưa sinh lời thoại, 0 VND)\n",
          f"54 kịch bản · **{len(calls)} cuộc gọi** (cộng 10 mẫu = 17 cuộc và 22 kịch bản hiện có = 31 cuộc → **135 cuộc**, đúng cơ cấu đã duyệt) · {sum(1 for f in frames if len(f['calls']) >= 2)} khách đa phiên · "
          f"{multi_ch} kịch bản đa kênh · {len(order_calls)} cuộc có tạo đơn (đều qua order gate) · {teen} cuộc teencode.\n",
          "## Ràng buộc bạn đặt ra\n", "| ràng buộc | đạt? | chi tiết |\n|---|---|---|", *[f"| {a} | {'✔' if ok else '✗'} | {d} |" for a, ok, d in checks], "",
          table("Nhóm", by_group, len(sc)), table("Số cuộc gọi mỗi kịch bản", n_calls), table("Persona (BTC `personas.json`)", persona), table("Loại ca khó (`hard_case`)", hard),
          table("Kênh — tính theo CUỘC gọi", chan), table("Kênh của cuộc ĐẦU TIÊN", first_ch), table("Ngành hàng", industry), table("Miền giao hàng", region), table("Kiểu kịch bản (archetype)", arche),
          "## Chéo: nhóm × kiểu × số cuộc\n\n| nhóm | kiểu | số cuộc | số kịch bản |\n|---|---|---|---|\n" + ctab + "\n",
          "## Danh sách\n\n| id | nhóm | kiểu | persona | ca khó | ngành | kênh các cuộc |\n|---|---|---|---|---|---|---|"]
    for f in frames:
        s = f["scenario"]
        md.append(f"| {s['scenario_id']} | {s['group']} | {s['archetype']} | {s['persona']} | {s['hard_case'] or '-'} | {s['industry']} | {' → '.join(c['channel'] for c in f['calls'])} |")
    with open(os.path.join(args.out, "frames54_distribution.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")

    rng = random.Random(args.seed)
    picks = sorted(rng.sample(range(len(frames)), 5))
    out = [f"# 5 khung chọn ngẫu nhiên (seed {args.seed}: " + ", ".join(frames[i]["scenario"]["scenario_id"] for i in picks) + ")\n",
           "Mỗi khung gồm: thông tin khách, từng cuộc (kênh/ngày/mục tiêu), **dàn ý khách và agent** (LLM chỉ viết lời từ đây), **fact khách PHẢI nói**, **ô trống lời agent** (giá trị do code tính), "
           "và **đáp án định dạng BTC**. File đầy đủ: `dataset/frames54/SC-Dxx.frame.json`.\n"]
    for i in picks:
        f = frames[i]
        s = f["scenario"]
        out.append(f"## {s['scenario_id']} — {s['archetype']} (nhóm {s['group']}, {len(f['calls'])} cuộc)\n")
        out.append(f"- Khách: **{s['honorific']} {s['customer_name']}**, SĐT {s['customer_phone']}; persona `{s['persona']}`; ca khó `{s['hard_case']}`; ngành {s['industry']}; {'miền Nam' if s['south'] else 'miền Bắc'}\n- Ghi chú: {s['notes']}\n")
        for c in f["calls"]:
            out.append(f"### {c['name']} — {c['channel']} — {c['abs_date']} — `{c['goal']}`" + (" — **ORDER GATE**" if c.get("order_flow") else "") + (" — **địa chỉ đã lưu (chỉ xác nhận)**" if c.get("saved_address") else ""))
            out.append(f"- Mở đầu: `{c['opening']}` · số lượt {c['n_turns']} · style `{c['style']}`")
            out.append(f"- **Dàn ý khách:** {c['customer_plot']}")
            out.append(f"- **Dàn ý agent:** {c['agent_plot']}")
            out.append("- **Fact khách phải nói:** " + "; ".join(f"`{x['key']}`={x['value']!r} ({x['hint']})" for x in c["customer_facts"]))
            out.append("- **Ô trống agent:** " + "; ".join(f"`{{{k}}}`={v['text']!r}" + (f" [sau khi khách nói `{v['after']}`]" if v.get("after") else "") for k, v in c["agent_vars"].items()))
            out.append("- **Đáp án BTC:** `" + json.dumps({k: v for k, v in c["expected"].items()}, ensure_ascii=False) + "`\n")
    with open(os.path.join(args.out, "frames54_random5.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(md[:30]))
    print(f"\n→ {args.out}/frames54_distribution.md, frames54_random5.md; khung đầy đủ: {fdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
