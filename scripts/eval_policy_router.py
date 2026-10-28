"""
Đo bước 11 — chọn policy 2 tầng (router LLM -> TF-IDF) trên 60 câu `rag/qa_labeled.json`, chấm bằng `rag_eval` của BTC.
Hai chế độ so cùng bộ câu, cùng MemoryService (baseline và hệ thống dùng cùng router khi bật):
  tfidf   — router TẮT, TF-IDF toàn bộ (như trước bước 11). Offline, không tốn LLM. Luôn chạy.
  router  — (với --llm) router LLM thật (model = POLICY_ROUTER_MODEL hoặc LLM_MODEL, temperature=0). CHỈ chạy khi có cờ --llm.

    python scripts/eval_policy_router.py                    # chỉ TF-IDF (offline) + in ước tính chi phí của --llm
    python scripts/eval_policy_router.py --llm [--cap-vnd 700]
    python scripts/eval_policy_router.py --offline-hybrid   # KHÔNG LLM: strict vs lai từ quyết định router đã lưu

Kết quả: runs/policy_router_eval/{tfidf,router,router_served}_results.json (định dạng `reference_eval.py --rag`) + report.md.
  router         — truy hồi của router, KHÔNG tính abstain (so được với Recall của TF-IDF);
  router_served  — đúng thứ hệ thống trả (câu abstain chỉ còn [PB-05]) nên Recall@k của câu unanswerable/restricted giảm theo.
Ngoài Recall@3/@5: tỉ lệ từ chối (unanswerable/restricted) và từ chối nhầm, file router chọn có chứa đủ chunk nhãn, tên file bịa bị bỏ,
ngày mua bị bỏ vì thiếu trích dẫn, độ trễ và chi phí thêm mỗi câu. Trần chi phí CỨNG (VND) kiểm trước mỗi lần gọi.
"""
import argparse
import importlib.util
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

BTC_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS")
OUT_DIR = os.path.join(CODE_DIR, "runs", "policy_router_eval")
DEFAULT_CAP_VND = 700.0       # ≈ 60 câu × ~9 VND (≈ 2.000 token vào + ~80 ra, gpt-4o-mini, chưa tính prompt cache) + dư


def load_reference_eval():
    spec = importlib.util.spec_from_file_location("reference_eval", os.path.join(BTC_DIR, "eval", "reference_eval.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Fixed:
    """Router giả lặp lại quyết định đã có nhưng bỏ abstain — để đo truy hồi của router tách khỏi việc từ chối."""
    def __init__(self, decision):
        self.decision = decision

    def route(self, query, catalog, today):
        return self.decision


def run_mode(questions, svc, on_date, cap_vnd=None):
    """Trả (served, retrieval, details, router_stats). Với tfidf (router=None) served == retrieval."""
    from src.llm.cost_tracker import BudgetExceeded
    from src.memory.policy_router import RouteDecision
    served, retrieval, details = {}, {}, {}
    router = svc.semantic.router
    for q in questions:
        qid = q["qid"]
        try:
            out = svc.semantic.search(q["question"], on_date=on_date, top_k=5)
        except BudgetExceeded as e:
            print(f"!! chạm trần chi phí ở {qid}: {e}")
            break
        route = svc.semantic.last_route
        abstained = bool(out and out[0].get("answerable") is False)
        served[qid] = {"retrieved_chunk_ids": [c["chunk_id"].strip("[]") for c in out], "abstained": abstained, "answer": ""}
        if abstained:       # lặp lại cùng quyết định nhưng coi như trả lời được -> chunk TF-IDF tìm được trong file đã chọn
            svc.semantic.router = Fixed(RouteDecision(files=route["files"], as_of_date=route["as_of_date"], answerable=True))
            replay = svc.semantic.search(q["question"], on_date=on_date, top_k=5)
            svc.semantic.router = router
            retrieval[qid] = {"retrieved_chunk_ids": [c["chunk_id"].strip("[]") for c in replay], "abstained": True, "answer": ""}
        else:
            retrieval[qid] = served[qid]
        details[qid] = {"type": q["type"], "route": route, "last_error": getattr(router, "last_error", None)}
    return served, retrieval, details


def offline_variants(questions, details, svc, on_date):
    """Tính OFFLINE (không LLM) từ quyết định router đã lưu: 'strict' = chỉ tìm trong file chọn; 'hybrid_kN' = N kết quả đầu từ file
    chọn rồi bù từ toàn bộ tài liệu đã lọc ngày (bỏ trùng). Mỗi biến thể trả {qid: kết quả định dạng reference_eval}, top-5."""
    from src.memory.policy_router import ROUTED_TOP_K  # noqa: F401  (hybrid_k{ROUTED_TOP_K} là cấu hình đang chạy)
    be = svc.semantic.backend
    visible = [c for c in svc.semantic.chunks if c.access == "public"]
    out = {"strict": {}, "hybrid_k1": {}, "hybrid_k2": {}, "hybrid_k3": {}}
    for q in questions:
        r = (details.get(q["qid"]) or {}).get("route")
        if not r:
            continue
        as_of = r["as_of_date"] or on_date
        by_date = [c for c in visible if c.effective_from <= as_of <= c.effective_to]
        selected = [c for c in by_date if c.doc_name in r["files"]] if r["files"] else by_date
        everything = be.rank(q["question"], by_date, top_k=5)
        for name in out:
            if name == "strict":
                ranked = be.rank(q["question"], selected, top_k=5)
            elif not r["files"]:
                ranked = everything
            else:
                ranked = be.rank(q["question"], selected, top_k=int(name[-1]))
                ranked = ranked + [c for c in everything if c not in ranked][:5 - len(ranked)]
            out[name][q["qid"]] = {"retrieved_chunk_ids": [c.chunk_id.strip("[]") for c in ranked], "abstained": not r["answerable"], "answer": ""}
    return out


def file_coverage(questions, details, chunk_doc):
    """Với câu có nhãn: router có chọn đủ file chứa các chunk nhãn không (files rỗng = không giới hạn = đủ)."""
    ok = n = 0
    for q in questions:
        d = details.get(q["qid"])
        if not q["relevant_chunk_ids"] or not d or not d["route"]:
            continue
        need = {chunk_doc.get(c) for c in q["relevant_chunk_ids"]} - {None}
        n += 1
        ok += int(not d["route"]["files"] or need <= set(d["route"]["files"]))
    return ok, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", action="store_true", help="chạy router bằng LLM THẬT (tốn tiền); mặc định chỉ đo TF-IDF offline")
    ap.add_argument("--cap-vnd", type=float, default=DEFAULT_CAP_VND, help=f"trần chi phí cứng, VND (mặc định {DEFAULT_CAP_VND:g})")
    ap.add_argument("--offline-hybrid", action="store_true",
                    help="KHÔNG gọi LLM: so strict vs lai (k=1..3) từ quyết định router đã lưu ở runs/policy_router_eval/router_details.json")
    ap.add_argument("--on-date", default="2026-10-15", help="ngày cuộc gọi dùng cho mọi câu (mặc định 2026-10-15)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.memory.service import MemoryService
    from src.memory.policy_router import PolicyRouter, SYSTEM_PROMPT, build_catalog, catalog_text

    ref = load_reference_eval()
    questions = json.load(open(os.path.join(BTC_DIR, "rag", "qa_labeled.json"), encoding="utf-8"))["questions"]
    os.makedirs(OUT_DIR, exist_ok=True)
    svc = MemoryService(enable_persistence=False)
    chunk_doc = {c.chunk_id.strip("[]"): c.doc_name for c in svc.semantic.chunks}
    prompt_chars = len(SYSTEM_PROMPT) + len(catalog_text(build_catalog([c for c in svc.semantic.chunks if c.access == "public"])))
    est_tokens = prompt_chars // 2.5 + 40   # tiếng Việt ≈ 2,5 ký tự/token (ước lượng thô)
    est_vnd = len(questions) * (est_tokens * 0.15 + 80 * 0.60) / 1e6 * float(os.environ.get("USD_TO_VND_RATE", 25400))
    print(f"[ước tính] router: ~{int(est_tokens)} token vào + ~80 ra mỗi câu → ~{est_vnd:,.0f} VND cho {len(questions)} câu (gpt-4o-mini, chưa tính prompt cache)")

    report = {}
    svc.semantic.router = None
    _, tfidf_res, _ = run_mode(questions, svc, args.on_date)
    report["tfidf"] = ref.rag_eval(os.path.join(BTC_DIR, "rag", "qa_labeled.json"), _dump("tfidf", tfidf_res))

    if args.offline_hybrid:
        saved = os.path.join(OUT_DIR, "router_details.json")
        details = json.load(open(saved, encoding="utf-8"))
        qa_path = os.path.join(BTC_DIR, "rag", "qa_labeled.json")
        report["offline_from_saved_routes"] = {name: ref.rag_eval(qa_path, _dump(f"offline_{name}", res))
                                               for name, res in offline_variants(questions, details, svc, args.on_date).items()}
        report["offline_warning"] = ("QUÁ KHỚP: k (số kết quả đầu lấy từ file chọn) được chọn trên chính 60 câu này nên số của hybrid lạc quan; "
                                     "chưa đo lại bằng LLM thật. Router vẫn là quyết định của lần chạy --llm trước (không gọi lại).")
    if args.llm:
        from src.llm.client import LLMClient
        llm = LLMClient(temperature=0.0)
        if not llm.available:
            print("!! --llm nhưng LLM không khả dụng (thiếu OPENAI_API_KEY?) — chỉ có kết quả TF-IDF.")
        else:
            llm.cost_tracker.set_hard_cap(args.cap_vnd)
            router = PolicyRouter(llm)
            svc.semantic.router = router
            served, retrieval, details = run_mode(questions, svc, args.on_date)
            report["router"] = ref.rag_eval(os.path.join(BTC_DIR, "rag", "qa_labeled.json"), _dump("router", retrieval))
            report["router_served"] = ref.rag_eval(os.path.join(BTC_DIR, "rag", "qa_labeled.json"), _dump("router_served", served))
            usages = router.drain_usage()
            ok, n = file_coverage(questions, details, chunk_doc)
            routes = [d["route"] for d in details.values() if d["route"]]
            report["router_extra"] = {
                "model": llm.model, "questions_run": len(details), "router_failed_to_tfidf": sum(1 for d in details.values() if not d["route"]),
                "file_coverage": f"{ok}/{n}", "dropped_file_names": sum(len(r["dropped_files"]) for r in routes),
                "date_dropped_no_evidence": sum(1 for r in routes if r["date_dropped"]),
                "as_of_dates": {qid: d["route"]["as_of_date"] for qid, d in details.items() if d["route"] and d["route"]["as_of_date"]},
                "mean_files_chosen": round(statistics.mean(len(r["files"]) or len(set(chunk_doc.values())) for r in routes), 2) if routes else None,
                "mean_latency_ms": round(statistics.mean(u["latency_ms"] for u in usages)) if usages else None,
                "total_cost_vnd": round(llm.cost_tracker.spent_vnd(), 2), "mean_cost_vnd": round(llm.cost_tracker.spent_vnd() / max(1, len(usages)), 3),
                "llm_calls": len(usages)}
            json.dump(details, open(os.path.join(OUT_DIR, "router_details.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    text = json.dumps(report, ensure_ascii=False, indent=1)
    open(os.path.join(OUT_DIR, "report.json"), "w", encoding="utf-8").write(text)
    print(text)
    return 0


def _dump(name, results):
    path = os.path.join(OUT_DIR, f"{name}_results.json")
    json.dump(results, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
