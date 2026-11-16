"""
Đo mọi cách tìm chính sách đã xây (TF-IDF, BM25, lai, Qwen3 embedding, Qwen3 reranker) qua ĐÚNG đường hệ thống dùng (SemanticKBStore.search,
router tắt bằng POLICY_NO_ROUTER=on). Offline, KHÔNG gọi LLM. Reranker/embedding cần model Qwen3 trong cache HF (GPU nếu có).

Phần 1 — bộ BTC `rag/qa_labeled.json` (60 câu), chấm bằng `reference_eval.rag_eval` (Recall@3/@5, multi-hop đủ, abstain, false-abstain):
  câu gốc và câu teencode (src.dataset.writer.teencodify); kèm độ trễ mỗi câu p50/p95.
  Router LLM KHÔNG chạy lại ở đây (tốn tiền): nếu có runs/policy_router_eval/router_served_results.json thì chấm lại file đó để so.
Phần 2 — 94 lời gọi search_policy THẬT trong trace (evaluation/rag/real_queries.json, nhãn tay): trúng nếu top-3 chứa đoạn đúng,
  với 3 dạng truy vấn: từ khóa LLM viết / lời khách / "từ khóa | lời khách" (POLICY_QUERY_CONTEXT); và chế độ mọi phiên bản (POLICY_ALL_VERSIONS).

    nlp_env/python.exe scripts/eval_rag_all.py [--backends tfidf,bm25,hybrid,qwen_emb,qwen_rerank] [--out runs/rag_all]
"""
import argparse, json, os, statistics, sys, time

CODE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, CODE)
sys.path.insert(0, os.path.join(CODE, "BTC-Data-Vong1-TEAMS", "eval"))
QA = os.path.join(CODE, "BTC-Data-Vong1-TEAMS", "rag", "qa_labeled.json")
REAL = os.path.join(CODE, "evaluation", "rag", "real_queries.json")


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else 0


ROUTER = {}      # "llm": LLMClient dùng chung (trần chi phí cứng), chỉ có khi --router


def store(backend, all_versions=False):
    """backend="router": router LLM thật + TF-IDF (đúng cấu hình đang nộp); còn lại: router tắt, backend cục bộ."""
    os.environ.update(POLICY_NO_ROUTER="off" if backend == "router" else "on", VECTOR_BACKEND="tfidf" if backend == "router" else backend,
                      POLICY_ALL_VERSIONS="on" if all_versions else "off")
    from src.memory import MemoryService
    sem = MemoryService(enable_persistence=False).semantic
    if backend == "router":
        from src.memory.policy_router import PolicyRouter
        sem.router = PolicyRouter(ROUTER["llm"])
    return sem


def run_qa(sem, questions, on_date, transform):
    res, ms = {}, []
    for q in questions:
        t = time.perf_counter()
        out = sem.search(transform(q["question"]), on_date=on_date, top_k=5)
        ms.append(1000 * (time.perf_counter() - t))
        res[q["qid"]] = {"retrieved_chunk_ids": [c["chunk_id"].strip("[]") for c in out],
                         "abstained": bool(out and out[0].get("answerable") is False), "answer": ""}
    return res, ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", default="tfidf,bm25,hybrid,qwen_emb,qwen_rerank")
    ap.add_argument("--on-date", default="2026-10-15")
    ap.add_argument("--out", default=os.path.join(CODE, "runs", "rag_all"))
    ap.add_argument("--router", action="store_true", help="đo cả router LLM THẬT (tốn tiền: ~402 lời gọi gpt-4o-mini)")
    ap.add_argument("--cap-vnd", type=float, default=4000, help="trần chi phí cứng cho router (VND)")
    a = ap.parse_args()
    if a.router:
        from src.llm.client import LLMClient
        ROUTER["llm"] = LLMClient(temperature=0.0)
        if not ROUTER["llm"].available:
            sys.exit("--router nhưng LLM không khả dụng (thiếu OPENAI_API_KEY?)")
        ROUTER["llm"].cost_tracker.set_hard_cap(a.cap_vnd)
    import reference_eval as ref
    from src.dataset.writer import teencodify
    os.makedirs(a.out, exist_ok=True)
    questions = json.load(open(QA, encoding="utf-8"))["questions"]
    backends = (["router"] if a.router else []) + [b for b in a.backends.split(",") if b]

    print("## Phần 1 — 60 câu qa_labeled.json (reference_eval.rag_eval, top-5)\n")
    print("| cách tìm | câu | Recall@3 | Recall@5 | multi-hop đủ @5 | abstain unanswerable | abstain restricted | false-abstain | single | multi_hop | version | numeric | ms p50 / p95 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    def row(name, variant, path, ms=None):
        r = ref.rag_eval(QA, path)
        t = r["by_type_recall@5"]
        lat = f"{pct(ms, .5):.0f} / {pct(ms, .95):.0f}" if ms else "—"
        print(f"| {name} | {variant} | {r['recall@3']} | {r['recall@5']} | {r['multi_hop_full_recall@5']} | {r['abstain_rate_unanswerable']} | "
              f"{r['abstain_rate_restricted']} | {r['false_abstain_rate']} | {t['single']} | {t['multi_hop']} | {t['version_conflict']} | {t['numeric']} | {lat} |")

    saved = os.path.join(CODE, "runs", "policy_router_eval", "router_served_results.json")
    if os.path.exists(saved) and not a.router:
        row("router LLM + TF-IDF (đang dùng; kết quả lưu 11/11)", "gốc", saved)
    for b in backends:
        sem = store(b)
        if b != "router":
            sem.search("khởi động", on_date=a.on_date, top_k=5)      # bỏ thời gian nạp model khỏi độ trễ
        for variant, f in (("gốc", lambda x: x), ("teencode", teencodify)):
            res, ms = run_qa(sem, questions, a.on_date, f)
            path = os.path.join(a.out, f"{b}_{'goc' if variant == 'gốc' else 'teencode'}_results.json")
            json.dump(res, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            row(b, variant, path, ms)

    items = json.load(open(REAL, encoding="utf-8"))["items"]
    rt = [i for i in items if i["router_top3"] and i["router_top3"][0] != "[PB-05]"]
    gold = lambda i: {f"[{g}]" for g in i["gold"]}
    print(f"\n## Phần 2 — {len(items)} lời gọi search_policy thật ({len({i['key'] for i in items})} tình huống), trúng = top-3 chứa đoạn đúng\n")
    print(f"- router LLM (kết quả trong trace m1_final7): {sum(bool(gold(i) & set(i['router_top3'])) for i in rt)}/{len(rt)} "
          f"(bỏ {len(items) - len(rt)} lần router từ chối)\n")
    print("| cách tìm | truy vấn | phiên bản | trúng | ms p50 / p95 | lời gọi có bản hết hiệu lực trong top-3 |")
    print("|---|---|---|---|---|---|")
    forms = (("từ khóa LLM", lambda i: i["query"]), ("lời khách", lambda i: i["customer_text"]),
             ("từ khóa + lời khách", lambda i: f"{i['query']} | {i['customer_text']}"))
    chunks = None
    for b in backends:
        for allv in ((False, True) if b == "qwen_rerank" else (False,)):
            sem = store(b, allv)
            chunks = chunks or {c.chunk_id: c for c in sem.chunks}
            for fname, f in (forms if not allv else forms[2:]):
                hit, ms, old = [], [], 0
                for i in items:
                    t = time.perf_counter()
                    out = sem.search(f(i), on_date=i["call_date"], top_k=3)
                    ms.append(1000 * (time.perf_counter() - t))
                    got = {c["chunk_id"] for c in out}
                    hit.append(bool(gold(i) & got))
                    old += any(chunks[c].effective_to < i["call_date"] for c in got if c in chunks)
                print(f"| {b} | {fname} | {'mọi phiên bản' if allv else 'theo ngày gọi'} | {sum(hit)}/{len(hit)} ({100 * statistics.mean(hit):.0f} %) | "
                      f"{pct(ms, .5):.0f} / {pct(ms, .95):.0f} | {old} |", flush=True)
    if a.router:
        print(f"\nChi phí router: {ROUTER['llm'].cost_tracker.spent_vnd():,.0f} VND")


if __name__ == "__main__":
    main()
