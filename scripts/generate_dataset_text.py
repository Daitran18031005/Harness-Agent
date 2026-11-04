"""
Sinh dataset VĂN BẢN (kịch bản + lời thoại từng lượt) — bước D2/D3a của docs/DATASET_TEXT_PLAN.md.

    python scripts/generate_dataset_text.py --frames-only                          # chỉ dựng khung xác định (không gọi LLM, 0 VND)
    python scripts/generate_dataset_text.py --dry-run --set frames54               # in lô sẽ sinh + trần còn lại (không gọi LLM)
    python scripts/generate_dataset_text.py --set frames54 --batch 10              # sinh MỘT lô 10 khung CHƯA xong (cần người duyệt từng lô)
    python scripts/generate_dataset_text.py --model gpt-4o-mini --out dataset_cmp/gpt-4o-mini --max-cost-vnd 500

Đáp án do code tính (truth.py); LLM chỉ viết lời thoại.

TRẦN CHI PHÍ — thực thi BẰNG MÃ (src/dataset/budget.py):
  * Trần TÍCH LŨY 10.000 VND cho cả quá trình sinh dữ liệu, tính trên sổ cái dataset/reports/generation_runs.jsonl (mọi lần chạy, mọi --out). Hết → dừng, không gọi LLM.
  * `--max-cost-vnd` chỉ HẠ được trần của một lần chạy; không nâng được trần tích lũy. Client kiểm trần TRƯỚC mỗi lần gọi API.
  * Mỗi lần chạy luôn ghi nốt sổ cái (kể cả khi lỗi/dừng giữa chừng).
Kết quả: <out>/frames, scenarios (đúng định dạng BTC), dialogues, review/, reports/.
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

REVIEW_FILE = {"sample10": ("sample10.md", "10 kịch bản mẫu — bản duyệt"), "frames54": ("frames54_dialogues.md", "54 kịch bản (SC-Dxx) — bản duyệt theo lô")}


def customer_lines(existing):
    """Lời khách của các cuộc ĐÃ ĐẠT — dùng cho kiểm trùng S10. Cuộc chưa đạt (meta.ok=False) sắp bị sinh lại nên không được làm lý do để loại cuộc khác."""
    return [(k, t["text_written"]) for k, r in existing.items() if (r.get("meta") or {}).get("ok", True) for t in r["turns"] if t["speaker"] == "C"]


def select_batch(frames, kept, batch):
    """Khung CHƯA xong (còn cuộc chưa có lời thoại đạt kiểm tra), giữ nguyên thứ tự; `batch` ≤ 0 = tất cả."""
    pending = [f for f in frames if any(f"{f['scenario']['scenario_id']}/{c['name']}" not in kept for c in f["calls"])]
    return pending[:batch] if batch and batch > 0 else pending


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "dataset"))
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--set", dest="which", choices=sorted(REVIEW_FILE), default="sample10", help="bộ khung: sample10 (10 mẫu) hoặc frames54 (SC-D01…SC-D54)")
    ap.add_argument("--batch", type=int, default=10, help="tối đa N khung CHƯA xong mỗi lần chạy (mặc định 10; 0 = không giới hạn)")
    ap.add_argument("--max-cost-vnd", type=float, default=500.0, help="trần của lần chạy này (chỉ hạ được trần tích lũy, không nâng)")
    ap.add_argument("--ids", default=None, help="chỉ xét các kịch bản này (vd SC-A01,SC-C02)")
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="in lô sẽ sinh và trần còn lại, KHÔNG gọi LLM")
    ap.add_argument("--force", action="store_true", help="sinh lại cả cuộc đã có file lời thoại")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--retries", type=int, default=2)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.dataset import budget as B
    from src.dataset.assemble import review_markdown, scenario_from
    from src.dataset.validate import distribution, load_dialogues, load_scenarios, validate_all
    from src.dataset.writer import DialogueWriter, rebuild_record, record_errors

    if args.which == "frames54":
        from src.dataset.frames54 import build_frames54
        frames = build_frames54()
    else:
        from src.dataset.specs import build_sample10
        frames = build_sample10()
    if args.ids:
        want = {x.strip() for x in args.ids.split(",")}
        frames = [f for f in frames if f["scenario"]["scenario_id"] in want]
    for sub in ("frames", "agent_eval", "asr", "reports"):
        os.makedirs(os.path.join(args.out, sub), exist_ok=True)
    for fr in frames:
        with open(os.path.join(args.out, "frames", f"{fr['scenario']['scenario_id']}.frame.json"), "w", encoding="utf-8") as fh:
            json.dump(fr, fh, ensure_ascii=False, indent=1)
    print(f"Đã dựng {len(frames)} khung xác định ({args.which}) → {args.out}/frames")
    if args.frames_only:
        return 0

    # --- tiền kiểm KHÔNG tốn LLM: cuộc đã có lời thoại và vẫn đạt luật hiện hành thì GIỮ (dựng lại bằng mã hiện tại); cuộc còn lỗi → chờ sinh lại
    dlg_dir = os.path.join(args.out, "asr")
    existing = load_dialogues(dlg_dir)
    other_lines = customer_lines(existing)
    kept = set()
    for fr in frames:
        sid = fr["scenario"]["scenario_id"]
        for call in fr["calls"]:
            key = f"{sid}/{call['name']}"
            path = os.path.join(dlg_dir, f"{sid}.{call['name']}.json")
            if key in existing and not args.force:
                rec = rebuild_record(fr, call, existing[key])
                errs = record_errors(rec, call, [x for x in other_lines if x[0] != key], fr)
                rec["meta"].update({"ok": not errs, "unresolved": errs})
                if not errs:
                    with open(path, "w", encoding="utf-8") as fh:
                        json.dump(rec, fh, ensure_ascii=False, indent=1)
                    existing[key] = rec
                    kept.add(key)
                else:
                    print(f"[{key}] đã có nhưng còn {len(errs)} lỗi → chờ sinh lại")
    batch = select_batch(frames, kept, args.batch)
    spent_before = B.spent_total()
    print(f"Sổ cái: đã tiêu {spent_before:,.1f}/{B.HARD_CAP_VND:,.0f} VND (còn {B.remaining():,.1f}) · khung chưa xong: "
          f"{len(select_batch(frames, kept, 0))}/{len(frames)} · lô lần này: {len(batch)} khung → {', '.join(f['scenario']['scenario_id'] for f in batch) or '(không có)'}")
    if args.dry_run or not batch:
        if not batch:
            print("Không còn khung nào cần sinh.")
        return 0
    try:
        cap = B.run_cap(args.max_cost_vnd)
    except B.CumulativeBudgetExhausted as e:
        print(f"DỪNG: {e}")
        return 4
    print(f"Trần lần chạy này: {cap:,.1f} VND (yêu cầu {args.max_cost_vnd:,.0f}; trần tích lũy còn {B.remaining():,.1f} trừ biên {B.ONE_CALL_MARGIN_VND:.0f})")

    from src.eval.runner import BudgetExceeded, spent_vnd
    from src.llm.client import LLMClient
    with open(os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "simulator", "personas.json"), encoding="utf-8") as fh:
        personas = {p["persona_id"]: p["style"] for p in json.load(fh)["personas"]}
    llm = LLMClient(model=args.model, seed=args.seed, reasoning_effort="low", max_output_tokens=3500)
    if not llm.available:
        print("Không có OPENAI_API_KEY — không gọi được LLM.")
        return 2
    llm.cost_tracker.set_hard_cap(cap)                        # kiểm TRƯỚC mỗi lần gọi API (BudgetExceeded kế thừa BaseException)
    writer = DialogueWriter(llm, cap, spent_vnd, personas, retries=args.retries)

    stopped = None
    try:
        for fr in batch:
            sid = fr["scenario"]["scenario_id"]
            summary = ""
            for call in fr["calls"]:
                key = f"{sid}/{call['name']}"
                if key in kept:
                    summary += f"{call['name']}: {call['goal']}. "
                    continue
                path = os.path.join(dlg_dir, f"{sid}.{call['name']}.json")
                try:
                    rec = writer.write_call(fr, call, summary, other_lines)
                except BudgetExceeded as e:
                    stopped = str(e)
                    print(f"[{key}] DỪNG: vượt trần chi phí ({e})")
                    break
                rec["frame_sha256"] = hashlib.sha256(json.dumps(call, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(rec, fh, ensure_ascii=False, indent=1)
                existing[key] = rec
                other_lines += [(key, t["text_written"]) for t in rec["turns"] if t["speaker"] == "C"]
                print(f"[{key}] {len(rec['turns'])} lượt · lần sinh {rec['meta']['attempts']} · đạt={rec['meta']['ok']} · đã tiêu {spent_vnd(llm):.1f} VND")
                summary += f"{call['name']}: {call['goal']}. "
            if stopped:
                break
    finally:                                                  # luôn ghi sổ cái, kể cả khi lỗi/Ctrl-C: không để mất chi phí đã tiêu
        spent_run = spent_vnd(llm)
        if writer.log or spent_run > 0:
            B.record_run({"run": "auto", "model": args.model, "seed": args.seed, "set": args.which, "max_cost_vnd": round(cap, 3), "spent_vnd": round(spent_run, 3),
                          "stopped": stopped, "calls": [{"scenario": g["scenario"], "call": g["call"], "attempts": g["attempt"], "cost_vnd": g["cost_vnd"],
                                                         "ok": g["ok"], "errors": g["errors"]} for g in writer.log]})

    # ghép kịch bản BTC-format cho các kịch bản có đủ lời thoại
    done = []
    for fr in frames:
        sid = fr["scenario"]["scenario_id"]
        recs = {c["name"]: existing.get(f"{sid}/{c['name']}") for c in fr["calls"]}
        if all(recs.values()):
            with open(os.path.join(args.out, "agent_eval", f"{sid}.json"), "w", encoding="utf-8") as fh:
                json.dump(scenario_from(fr, recs), fh, ensure_ascii=False, indent=2)
            done.append(sid)

    scenarios = load_scenarios([os.path.join(args.out, "agent_eval")])
    dialogues = load_dialogues(dlg_dir)
    issues = validate_all(scenarios, dialogues)
    by_sc = {}
    for i in issues:
        by_sc.setdefault(i.scenario, []).append(i.line())
    runs = []
    if os.path.exists(B.LEDGER_PATH):
        with open(B.LEDGER_PATH, encoding="utf-8") as fh:
            runs = [json.loads(l) for l in fh if l.strip()]
    total_cost = sum(r["spent_vnd"] for r in runs)
    gen_log = [{"scenario": c["scenario"], "call": c["call"], "attempt": c["attempts"], "ok": c.get("ok", True), "cost_vnd": c["cost_vnd"], "reasoning_tokens": None,
                "errors": c.get("errors", [])} for r in runs for c in r.get("calls", [])]
    review_name, review_title = REVIEW_FILE[args.which]
    review = review_markdown([f for f in frames if f["scenario"]["scenario_id"] in done], dialogues, by_sc, gen_log, total_cost, args.model,
                             title=review_title, cap_text=f"trần tích lũy {B.HARD_CAP_VND:,.0f} VND")
    with open(os.path.join(args.out, "reports", review_name), "w", encoding="utf-8") as fh:
        fh.write(review)
    with open(os.path.join(args.out, "reports", "generation_log.json"), "w", encoding="utf-8") as fh:
        json.dump({"model": args.model, "seed": args.seed, "set": args.which, "total_spent_vnd_all_runs": round(total_cost, 3), "hard_cap_vnd": B.HARD_CAP_VND,
                   "last_run_spent_vnd": round(spent_run, 3), "stopped": stopped, "scenarios_done": done, "runs": runs, "distribution": distribution(scenarios, dialogues)},
                  fh, ensure_ascii=False, indent=1)
    errs = [i for i in issues if i.severity == "LỖI"]
    print(f"\nXong lô: {len([f for f in batch if f['scenario']['scenario_id'] in done])}/{len(batch)} khung · chi phí lần này {spent_run:.1f} VND · tổng sổ cái {total_cost:,.1f}/{B.HARD_CAP_VND:,.0f} VND "
          f"· validate: {len(errs)} LỖI, {len(issues) - len(errs)} CẢNH BÁO")
    for i in issues:
        print(" ", i.line())
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
