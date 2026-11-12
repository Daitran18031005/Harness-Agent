"""Chấm cuộc gọi bằng MỘT LLM RIÊNG (LLM-as-a-judge) theo đúng rubric 12 tiêu chí PASS/FAIL của BTC — tách khỏi pipeline: script chỉ đọc trace + kịch bản.

    python scripts/llm_judge.py judge --trace runs/ab/base/full.jsonl --out runs/ab/judge --model gpt-6-luna --max-cost-vnd 5000
    #   → judge.json (mọi verdict), judge.md (tỷ lệ đạt từng tiêu chí), manual_20.csv (20 mẫu cho NGƯỜI chấm; cột human_verdict để trống)
    python scripts/llm_judge.py agreement --out runs/ab/judge
    #   → sau khi người điền PASS/FAIL vào manual_20.csv: % đồng thuận + Cohen's kappa (giao thức của BTC: kappa < 0,6 là chưa tin cậy)

Model chấm khác model agent (mặc định gpt-6-luna). LLM tự bỏ qua tiêu chí không áp dụng cho cuộc gọi (verdict "NA")."""
import argparse, csv, json, os, random, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTC = os.path.join(HERE, "BTC-Data-Vong1-TEAMS")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BTC, "eval"))
import reference_eval as ref  # noqa: E402

RUBRIC = json.load(open(os.path.join(BTC, "eval", "llm_judge_rubric.json"), encoding="utf-8"))
HIDE = ("customer_phone",)          # không gửi SĐT cho model chấm


def scrub(v):
    """Che SĐT trong dữ liệu gửi model chấm (giữ khóa để phiếu chuyển máy không bị coi là thiếu SĐT)."""
    if isinstance(v, dict):
        return {k: ("<đã có SĐT>" if k in ("customer_phone", "phone", "recipient_phone") and x else scrub(x)) for k, x in v.items()}
    return [scrub(x) for x in v] if isinstance(v, list) else v


def applicable(rows, call, spec):
    """E2: CODE quyết định J01/J05/J07 có áp dụng không (model chấm từng áp J05 cho cuộc không chuyển máy)."""
    names = [tc for r in rows for tc in r.get("tool_calls") or []]
    handoff = any(tc.get("name") == "handoff.transfer" for tc in names) or "handoff.transfer" in json.dumps(spec, ensure_ascii=False)
    created = any(tc.get("name") == "order.create" and "error" not in (tc.get("result") or {"error": 1}) for tc in names)
    skip = {"J01_opening_continuity": call == "call_1", "J05_escalation_quality": not handoff, "J07_closing_summary": not created}
    return [c for c in RUBRIC["criteria"] if not skip.get(c["id"])]


def transcript_of(rows, prior_note):
    """Model chấm phải thấy KẾT QUẢ tool (giá, tồn kho, chính sách tra được) và phiếu chuyển máy: thiếu chúng thì mọi con số agent nói đều bị coi là bịa
    (lần chấm đầu, chỉ đưa tên tool: J02 đạt 16 %, J05 đạt 0/7)."""
    lines = [prior_note] if prior_note else []
    for r in rows:
        if (r.get("customer_text") or "").strip():
            lines.append(f"KHÁCH: {r['customer_text']}")
        tools = "".join(f"\n  [tool {tc.get('name')}({json.dumps(scrub(tc.get('args')), ensure_ascii=False)[:500]}) → {json.dumps(scrub(tc.get('result')), ensure_ascii=False)[:700]}]"
                        for tc in r.get("tool_calls") or [])
        lines.append(f"AGENT: {r['agent_text']}" + tools)
    return "\n".join(lines)


def judge(args):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(HERE, ".env"))
    from src.llm.client import LLMClient
    scenarios = ref.load_scenarios(args.scenarios)
    trace = ref.load_trace(args.trace)
    llm = LLMClient(model=args.model, temperature=0.0)
    assert llm.available, "thiếu OPENAI_API_KEY"
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "judge.json")
    done = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock()

    def one(item):
        (sid, call), rows = item
        key = f"{sid}/{call}"
        if key in done or sid not in scenarios:
            return
        if llm.cost_tracker.spent_vnd() >= args.max_cost_vnd:
            print(f"[DỪNG] chạm trần {args.max_cost_vnd} VND — bỏ {key}")
            return
        s = scenarios[sid]
        spec = s["calls"][call]
        prior = {c: s["calls"][c].get("facts_established") for c in sorted(s["calls"]) if c < call and s["calls"][c].get("facts_established")}
        scen_json = {"scenario_id": sid, "call": call, "persona": s.get("persona"), "hard_case": s.get("hard_case"),
                     "su_that_tu_phien_truoc": prior, **{k: v for k, v in spec.items() if k not in ("customer_turns",) + HIDE}}
        crits = applicable(rows, call, spec)
        crit_text = "\n".join(f"- {c['id']} (áp dụng: {c['applies_to']}): {c['pass_if']}" for c in crits)
        prompt = (RUBRIC["judge_prompt_template"].replace("{scenario_json}", json.dumps(scen_json, ensure_ascii=False))
                  .replace("{transcript}", transcript_of(rows, "(Đây là cuộc gọi lại của cùng khách.)" if call != "call_1" else "")).replace("{criteria}", crit_text))
        prompt += ('\n\nTrả về DUY NHẤT JSON: {"verdicts": [{"criterion_id": "...", "verdict": "PASS"|"FAIL"|"NA", "evidence": "trích 1 câu"}]} cho ĐỦ '
                   f'{len(crits)} tiêu chí trên; tiêu chí phụ thuộc loại ca (J03/J04/J09–J12) mà cuộc gọi không thuộc loại đó thì dùng "NA".')
        raw = None
        for attempt in range(2):                      # model chấm hay lỗi/timeout: thử lại một lần
            try:
                raw, _ = llm.complete_json([{"role": "user", "content": prompt}])
                break
            except Exception as e:
                print(f"{key}: lỗi model chấm lần {attempt + 1} ({str(e)[:120]})")
        if raw is None:
            return
        ids = {c["id"] for c in RUBRIC["criteria"]}
        with lock:
            done[key] = [v for v in (raw.get("verdicts") or []) if isinstance(v, dict) and v.get("criterion_id") in ids and v.get("verdict") in ("PASS", "FAIL", "NA")]
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(done, f, ensure_ascii=False, indent=1)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(one, sorted(trace.items())))
    spent = llm.cost_tracker.spent_vnd()
    print(f"đã chấm {len(done)}/{sum(1 for (s_, _c) in trace if s_ in scenarios)} cuộc")

    stats = {c["id"]: [0, 0] for c in RUBRIC["criteria"]}
    for vs in done.values():
        for v in vs:
            if v["verdict"] != "NA":
                stats[v["criterion_id"]][0] += v["verdict"] == "PASS"
                stats[v["criterion_id"]][1] += 1
    lines = [f"Model chấm: `{args.model}` · trace: `{args.trace}` · {len(done)} cuộc gọi · chi phí lần chạy này {spent:,.0f} VND".replace(",", "."), "",
             "| Tiêu chí | Đạt / áp dụng | Tỷ lệ đạt |", "|---|---:|---:|"]
    lines += [f"| {cid} | {p}/{n} | {round(100 * p / n, 1) if n else '—'}{' %' if n else ''} |" for cid, (p, n) in stats.items()]
    open(os.path.join(args.out, "judge.md"), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    # 20 mẫu (call, tiêu chí) có verdict PASS/FAIL cho người chấm — không hiện verdict của LLM trong file
    pool = [(k, v) for k, vs in sorted(done.items()) for v in vs if v["verdict"] != "NA"]
    random.Random(42).shuffle(pool)
    fails = [x for x in pool if x[1]["verdict"] == "FAIL"][:10]
    sample = fails + [x for x in pool if x[1]["verdict"] == "PASS"][:20 - len(fails)]
    random.Random(7).shuffle(sample)
    pass_if = {c["id"]: c["pass_if"] for c in RUBRIC["criteria"]}
    with open(os.path.join(args.out, "manual_20.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["call", "criterion_id", "pass_if", "transcript", "human_verdict (PASS/FAIL)"])
        for k, v in sample:
            sid, call = k.split("/")
            w.writerow([k, v["criterion_id"], pass_if[v["criterion_id"]], transcript_of(trace[(sid, call)], ""), ""])
    print(f"→ {args.out}: judge.json, judge.md, manual_20.csv ({len(sample)} mẫu chờ người chấm)")
    return 0


def agreement(args):
    done = json.load(open(os.path.join(args.out, "judge.json"), encoding="utf-8"))
    llm_v = {(k, v["criterion_id"]): v["verdict"] for k, vs in done.items() for v in vs}
    pairs = []
    for row in csv.DictReader(open(os.path.join(args.out, "manual_20.csv"), encoding="utf-8-sig")):
        h = (row.get("human_verdict (PASS/FAIL)") or "").strip().upper()
        if h in ("PASS", "FAIL") and (row["call"], row["criterion_id"]) in llm_v:
            pairs.append((h, llm_v[(row["call"], row["criterion_id"])]))
    if len(pairs) < 20:
        print(f"mới có {len(pairs)}/20 mẫu người chấm — điền cột human_verdict trong manual_20.csv")
        return 1
    n = len(pairs)
    po = sum(h == l for h, l in pairs) / n
    pe = sum((sum(h == c for h, _ in pairs) / n) * (sum(l == c for _, l in pairs) / n) for c in ("PASS", "FAIL"))
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    print(f"{n} mẫu · đồng thuận {100 * po:.1f}% · Cohen's kappa {kappa:.2f}" + (" (< 0,6: chưa tin cậy theo giao thức BTC)" if kappa < 0.6 else ""))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["judge", "agreement"])
    ap.add_argument("--trace")
    ap.add_argument("--scenarios", default=os.path.join(HERE, "runs", "m1_final2", "scen_all"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--max-cost-vnd", type=float, default=5000.0)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    sys.exit(judge(a) if a.cmd == "judge" else agreement(a))
