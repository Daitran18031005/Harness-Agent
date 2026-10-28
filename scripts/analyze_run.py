"""
Phân tích 1 lần chạy đánh giá (thư mục chứa full.jsonl + baseline.jsonl) — chỉ ĐỌC trace và kịch bản, không gọi API.

    python scripts/analyze_run.py runs/buoc15_B [--scenarios <dir>] [--json out.json]

In ra: (1) bảng A.6 full vs baseline; (2) số lần gọi LLM/lượt, tool/lượt, latency p50/p95, chi phí thực tế;
(3) chất lượng trích slot (dễ = regex; khó = LLM): đúng / sai / bỏ sót so với `facts_established`;
(4) từng kịch bản mà full thua baseline, kèm lý do chấm trượt.
Mọi số đều tái lập được từ trace (đúng yêu cầu "số liệu tái lập được bằng code").
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval"))
import reference_eval as ref  # noqa: E402  (script chấm chính thức của BTC — không sửa)

DEFAULT_SCENARIOS = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")
HARD_SLOTS = ("blocker", "budget_vnd", "competitor_price_vnd", "objection")
TOOL_SLOTS = ("product_advised", "price_quoted_vnd", "promo_code")
EASY_SLOTS = ("room_area_m2", "has_children", "budget_vnd", "size", "color")


def _rows(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _group(rows):
    out = {}
    for r in rows:
        out.setdefault((r["scenario_id"], r["call"]), []).append(r)
    return out


def _pctl(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def cost_stats(rows):
    """Chi phí thật = llm_cost của từng lượt + chi phí bộ trích slot khó (memory_extractor.llm_cost)."""
    turn_cost = sum((r.get("llm_cost") or {}).get("vnd_cost", 0) for r in rows)
    extractor = [(r["memory_extractor"] or {}) for r in rows if r.get("memory_extractor")]
    ext_cost = sum(((e.get("llm_cost") or {}).get("vnd_cost", 0)) for e in extractor)
    calls = [(r.get("llm_cost") or {}).get("llm_calls", 0) for r in rows]
    tools = [len(r.get("tool_calls", [])) for r in rows]
    errors = [tc for r in rows for tc in r.get("tool_calls", []) if isinstance(tc.get("result"), dict) and tc["result"].get("error")]
    tokens = [(r.get("llm_cost") or {}).get("total_tokens", 0) for r in rows]
    return {
        "turns": len(rows), "vnd_turns": round(turn_cost, 1), "vnd_extractor": round(ext_cost, 1),
        "vnd_total": round(turn_cost + ext_cost, 1), "vnd_per_turn": round((turn_cost + ext_cost) / max(1, len(rows)), 1),
        "llm_calls_per_turn_mean": round(statistics.mean(calls), 2) if calls else None,
        "llm_calls_per_turn_median": statistics.median(calls) if calls else None,
        "llm_calls_per_turn_max": max(calls) if calls else None,
        "extractor_llm_calls": sum(1 for e in extractor if e.get("llm_called")),
        "tool_calls_per_turn_mean": round(statistics.mean(tools), 2) if tools else None,
        "tool_calls_per_turn_max": max(tools) if tools else None,
        "tool_errors": len(errors), "tool_errors_unknown_sku": sum(1 for tc in errors if tc["result"].get("error") == "unknown_sku"),
        "tokens_per_turn_median": statistics.median(tokens) if tokens else None,
        "rows_without_llm": sum(1 for c in calls if not c),
    }


def _norm(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())               # '39' và 39 là cùng một giá trị
        except ValueError:
            return v.strip().lower()
    return None


def slot_quality(rows, scenarios, slots, writer_filter=None):
    """Mỗi (kịch bản, call, slot) có trong facts_established -> 'đúng'/'sai'/'bỏ sót'; slot hệ thống ghi mà GT không có -> 'thừa'.
    Giá trị lấy từ memory_writes của CHÍNH call đó (fact active cuối cùng)."""
    res = {s: {"đúng": [], "sai": [], "bỏ sót": [], "thừa": []} for s in slots}
    for (sid, call), rs in _group(rows).items():
        gt = (scenarios[sid]["calls"][call].get("facts_established") or {})
        written = {}
        for r in rs:
            for w in r.get("memory_writes", []):
                if w["key"] in slots and (writer_filter is None or writer_filter(w)):
                    written[w["key"]] = w["value"]
        for s in slots:
            if s in gt and s in written:
                (res[s]["đúng"] if _norm(gt[s]) == _norm(written[s]) else res[s]["sai"]).append((sid, call, gt[s], written[s]))
            elif s in gt:
                res[s]["bỏ sót"].append((sid, call, gt[s], None))
            elif s in written:
                res[s]["thừa"].append((sid, call, None, written[s]))
    return res


def per_scenario(scenarios, full_g, base_g):
    out = []
    for sid, s in scenarios.items():
        one = {sid: s}
        ev = {name: ref.evaluate(one, g) for name, g in (("full", full_g), ("baseline", base_g))}
        out.append((sid, s, ev))
    return out


def worse(ev):
    f, b = ev["full"], ev["baseline"]
    why = []
    ft, bt = f["task_success_rate"], b["task_success_rate"]
    if ft["total"] and ft["value"] is not None and bt["value"] is not None and ft["value"] < bt["value"]:
        why.append("TSR")
    fc, bc = f["context_carryover_rate"], b["context_carryover_rate"]
    if fc["required"] and fc["value"] < bc["value"]:
        why.append("CCR")
    fr, br = f["repeat_question_rate"], b["repeat_question_rate"]
    if fr["total_questions"] and br["total_questions"] and fr["value"] > br["value"]:
        why.append("RQR")
    fh, bh = f["hallucination_rate"], b["hallucination_rate"]
    if fh["total_claims"] and (bh["total_claims"] == 0 or fh["value"] > bh["value"]):
        why.append("HR")
    return why


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    full_rows, base_rows = _rows(os.path.join(args.run_dir, "full.jsonl")), _rows(os.path.join(args.run_dir, "baseline.jsonl"))
    ids = {r["scenario_id"] for r in full_rows}
    all_scen = ref.load_scenarios(args.scenarios)
    scenarios = {sid: s for sid, s in all_scen.items() if sid in ids}
    full_g, base_g = ref.load_trace(os.path.join(args.run_dir, "full.jsonl")), ref.load_trace(os.path.join(args.run_dir, "baseline.jsonl"))
    ev_f, ev_b = ref.evaluate(scenarios, full_g), ref.evaluate(scenarios, base_g)
    report = {"n_scenarios": len(scenarios), "full": ev_f, "baseline": ev_b}

    def v(x):
        return "N/A" if x is None else f"{x}"

    print(f"## 1. Bảng A.6 — {len(scenarios)} kịch bản, {len(full_rows)} lượt/cấu hình")
    rows = [("Repeat-Question Rate (%)", "repeat_question_rate", lambda d: f"{v(d['value'])} ({d['redundant']}/{d['total_questions']} câu)"),
            ("Context Carryover Rate (%)", "context_carryover_rate", lambda d: f"{v(d['value'])} ({d['used']}/{d['required']} fact)"),
            ("Task Success Rate (%)", "task_success_rate", lambda d: f"{v(d['value'])} ({d['passed']}/{d['total']} kịch bản)"),
            ("Hallucination giá&KM (%)", "hallucination_rate", lambda d: f"{v(d['price_promo_only']['value'])} ({d['price_promo_only']['wrong']}/{d['price_promo_only']['total']} claim)"),
            ("Số lượt TB / cuộc", "avg_turns_per_call", lambda d: v(d)),
            ("Vi phạm guardrail", "guardrail_violations", lambda d: v(d.get("total", d) if isinstance(d, dict) else d))]
    print(f"{'Chỉ số':32s} | {'Baseline':34s} | {'Hệ thống (full)':34s}")
    for name, key, fmt in rows:
        print(f"{name:32s} | {fmt(ev_b[key]):34s} | {fmt(ev_f[key]):34s}")

    from src.eval import gate_metrics as GM
    print("\n## 1b. Hai loại đo (order gate luôn bật). Dòng TSR ở bảng A.6 trên là của reference_eval với lời khách như trong file; "
          "TSR CHÍNH chỉ là loại [1]; kịch bản BTC cố định chỉ có loại [2]:")
    for cfg_name, g in (("full", full_g), ("baseline", base_g)):
        print(f"  --- cấu hình {cfg_name}")
        print("  " + GM.report_text(scenarios, g).replace("\n", "\n  "))

    print("\n## 2. Chi phí / số lần gọi / độ trễ")
    cs = {"full": cost_stats(full_rows), "baseline": cost_stats(base_rows)}
    report["costs"] = cs
    for k in ("turns", "llm_calls_per_turn_mean", "llm_calls_per_turn_median", "llm_calls_per_turn_max", "extractor_llm_calls",
              "tool_calls_per_turn_mean", "tool_calls_per_turn_max", "tool_errors", "tool_errors_unknown_sku",
              "tokens_per_turn_median", "rows_without_llm", "vnd_turns", "vnd_extractor", "vnd_total", "vnd_per_turn"):
        print(f"{k:28s} | baseline={cs['baseline'][k]!s:10s} | full={cs['full'][k]!s:10s}")
    print(f"TỔNG chi phí LLM thực tế (VND): {cs['full']['vnd_total'] + cs['baseline']['vnd_total']:.1f}")
    for name, ev in (("baseline", ev_b), ("full", ev_f)):
        lat = ev["latency"]
        print(f"latency {name:8s}: TTFT p50/p95 = {lat['ttft']['p50_ms']}/{lat['ttft']['p95_ms']} ms | total p50/p95 = {lat['total']['p50_ms']}/{lat['total']['p95_ms']} ms | "
              f"Call Brief p50/p95 = {(lat['call_brief'] or {}).get('p50_ms')}/{(lat['call_brief'] or {}).get('p95_ms')} ms (n={(lat['call_brief'] or {}).get('n')}) | n_turns={lat['n_turns']}")

    print("\n## 2a. Order gate (trace.order_gate): số lần chặn/hỏi/xác nhận/đọc lại/cho tạo đơn")
    report["order_gate"] = {}
    for name, rs in (("baseline", base_rows), ("full", full_rows)):
        evs = [(r["scenario_id"], r["call"], r["turn"], e) for r in rs for e in (r.get("order_gate") or [])]
        by_action = {}
        for _, _, _, e in evs:
            by_action[e["action"]] = by_action.get(e["action"], 0) + 1
        blocked = [x for x in evs if not x[3].get("allow")]
        made = [(r["scenario_id"], r["call"]) for r in rs for tc in r.get("tool_calls", [])
                if tc.get("name") == "order.create" and (tc.get("result") or {}).get("status") == "created"]
        extra_turns = {}
        for sid, call, turn, e in blocked:
            extra_turns.setdefault((sid, call), set()).add(turn)
        report["order_gate"][name] = {"events": by_action, "blocked_attempts": len(blocked), "orders_created": len(made),
                                      "turns_with_gate_block": sum(len(v) for v in extra_turns.values())}
        print(f"  {name}: {by_action} | lời gọi order.create bị chặn: {len(blocked)} | đơn đã tạo: {len(made)} {made} | "
              f"số lượt có chặn (lượt dành để hỏi/xác nhận/đọc lại): {sum(len(v) for v in extra_turns.values())}")
        for (sid, call), ts in sorted(extra_turns.items()):
            print(f"     {sid}/{call}: chặn ở lượt {sorted(ts)}")

    print("\n## 2b. Phân rã độ trễ TTFT và prompt caching (từ trace.latency_detail; chỉ có ở lần chạy sau khi thêm đo)")
    for name, rs in (("baseline", base_rows), ("full", full_rows)):
        det = [r["latency_detail"] for r in rs if r.get("latency_detail")]
        if not det:
            print(f"  {name}: (trace không có latency_detail)")
            continue
        rounds = [d["rounds_before_first_token"] for d in det]
        pre = [sum(d["round_ms"][:-1]) + d["tool_ms"] for d in det]
        final = [d["final_round_ttft_ms"] for d in det]
        prompt_t = sum(d["prompt_tokens"] for d in det)
        cached_t = sum(d["cached_tokens"] for d in det)
        dist = {k: rounds.count(k) for k in sorted(set(rounds))}
        print(f"  {name}: vòng LLM trước token đầu — TB {statistics.mean(rounds):.2f}, phân bố {dist} | "
              f"thời gian TRƯỚC vòng cuối (các vòng tool + tool) p50/p95 = {int(statistics.median(pre))}/{_pctl(pre, 0.95)} ms | "
              f"chờ token đầu của vòng cuối p50/p95 = {int(statistics.median(final))}/{_pctl(final, 0.95)} ms | "
              f"token prompt được cache: {cached_t}/{prompt_t} = {100 * cached_t / max(1, prompt_t):.1f}%")
        report.setdefault("latency_detail", {})[name] = {"rounds_mean": statistics.mean(rounds), "rounds_dist": dist,
                                                         "cached_ratio": cached_t / max(1, prompt_t)}

    print("\n## 3. Chất lượng trích slot (so với facts_established của kịch bản; chỉ cấu hình full)")
    for title, slots, filt in (("SLOT KHÓ (LLM, cuối cuộc gọi/chuyển máy)", HARD_SLOTS, lambda w: str(w.get("source", "")).endswith(("#end", "#handoff", "#timeout"))),
                               ("SLOT DỄ (regex mỗi lượt, không LLM)", EASY_SLOTS, lambda w: "#turn" in str(w.get("source", ""))),
                               ("SLOT GHI TỪ KẾT QUẢ TOOL (sản phẩm/giá/KM)", TOOL_SLOTS, lambda w: "#turn" in str(w.get("source", "")))):
        q = slot_quality(full_rows, scenarios, slots, filt)
        report["slots_" + ("hard" if slots is HARD_SLOTS else "easy" if slots is EASY_SLOTS else "tool")] = {s: {k: len(x) for k, x in d.items()} for s, d in q.items()}
        print(f"\n{title}")
        print(f"{'slot':22s} đúng  sai  bỏ sót  thừa(ghi mà GT không có)")
        for s, d in q.items():
            print(f"{s:22s} {len(d['đúng']):4d} {len(d['sai']):4d} {len(d['bỏ sót']):7d} {len(d['thừa']):6d}")
            for k in ("sai", "bỏ sót", "thừa"):
                for sid, call, g, w in d[k]:
                    print(f"    [{k}] {sid}/{call}: GT={g!r} | hệ thống ghi={w!r}")

    print("\n## 4. Kịch bản full THUA baseline")
    losers = 0
    for sid, s, ev in per_scenario(scenarios, full_g, base_g):
        why = worse(ev)
        f, b = ev["full"], ev["baseline"]
        print(f"- {sid}: TSR full/base = {f['task_success_rate']['passed']}/{f['task_success_rate']['total']} vs {b['task_success_rate']['passed']}/{b['task_success_rate']['total']} | "
              f"CCR {f['context_carryover_rate']['used']}/{f['context_carryover_rate']['required']} vs {b['context_carryover_rate']['used']}/{b['context_carryover_rate']['required']} | "
              f"RQR {f['repeat_question_rate']['redundant']}/{f['repeat_question_rate']['total_questions']} vs {b['repeat_question_rate']['redundant']}/{b['repeat_question_rate']['total_questions']} | "
              f"HR {f['hallucination_rate']['wrong']}/{f['hallucination_rate']['total_claims']} vs {b['hallucination_rate']['wrong']}/{b['hallucination_rate']['total_claims']}"
              f"  => {'THUA ở: ' + ', '.join(why) if why else 'không thua'}")
        if why:
            losers += 1
            for fail in f["task_success_rate"]["failures"]:
                print(f"    full trượt {fail['call']}: {fail['reasons']}")
            for ex in f["hallucination_rate"]["examples"]:
                print(f"    full claim sai: {ex}")
            for ex in f["repeat_question_rate"]["examples"]:
                print(f"    full hỏi thừa: {ex['call']} t{ex['turn']} slot={ex['slot']}/{ex['type']} | {ex['text']}")
    print(f"\nSố kịch bản full thua baseline ở ít nhất một chỉ số: {losers}/{len(scenarios)}")
    report["losers"] = losers

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
