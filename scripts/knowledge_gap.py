"""Knowledge Gap Loop (đề bài C.5, cơ chế cải tiến M1) — câu khách hỏi mà kho chính sách KHÔNG trả lời được → danh sách thiếu sót → NGƯỜI duyệt câu trả lời
→ bổ sung vào kho tri thức + tự thêm kịch bản hồi quy để lần sau không tái phạm.

    python scripts/knowledge_gap.py collect --trace runs/m1_final/full.jsonl     # vòng 0: gom thiếu sót từ trace (không gọi LLM)
    #   → người duyệt sửa data/knowledge_gaps.json: status = "approved" | "rejected", điền answer (+ must_say: các cụm agent phải nói)
    python scripts/knowledge_gap.py apply                                         # ghi data/kb_supplement/bo-sung-tri-thuc.md + test_set/knowledge_gap/KG-nn.json
    #   → chạy lại run_eval.py trên CÙNG bộ test (vòng 1) và so với vòng 0

Thiếu sót = lượt có `search_policy` trả về đúng quy tắc "chưa có thông tin" [PB-05] (router chính sách kết luận tài liệu không có câu trả lời) hoặc không trả chunk nào.
AN TOÀN: không mục nào vào kho tri thức khi chưa có người đổi status thành "approved"; câu hỏi dò thông tin nội bộ (giá nhập, hoa hồng…) phải để "rejected"."""
import argparse, glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAPS = os.path.join(HERE, "data", "knowledge_gaps.json")
KB_DIR = os.path.join(HERE, "data", "kb_supplement")
TEST_DIR = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "test_set", "knowledge_gap")


def find_gaps(rows):
    """[{query, customer_text, scenario_id, call, turn}] cho các lượt mà kho chính sách không có câu trả lời."""
    out = []
    for r in rows:
        for tc in r.get("tool_calls") or []:
            if (tc.get("name") or tc.get("tool")) != "search_policy":
                continue
            ids = [c.get("chunk_id") for c in ((tc.get("result") or {}).get("chunks") or [])]
            if ids and ids != ["[PB-05]"]:
                continue
            out.append({"query": (tc.get("args") or {}).get("query") or "", "customer_text": r.get("customer_text") or "",
                        "scenario_id": r.get("scenario_id"), "call": r.get("call"), "turn": r.get("turn")})
    return out


def merge(existing, found):
    """Thêm thiếu sót MỚI (theo `query`, không phân biệt hoa thường); mục đã có (kể cả đã duyệt/từ chối) giữ nguyên, chỉ tăng `seen`."""
    by_q = {g["query"].strip().lower(): g for g in existing}
    for f in found:
        k = f["query"].strip().lower()
        if not k:
            continue
        if k in by_q:
            by_q[k]["seen"] = by_q[k].get("seen", 1) + 1
            continue
        g = {"id": f"KG-{len(existing) + 1:02d}", **f, "seen": 1, "status": "pending", "answer": "", "must_say": []}
        existing.append(g)
        by_q[k] = g
    return existing


def apply(gaps, kb_dir=KB_DIR, test_dir=TEST_DIR):
    """Chỉ mục `approved` có `answer`: ghi chunk [BS-nn] vào kho bổ sung (bộ nạp chính sách đọc thư mục này) và một kịch bản hồi quy định dạng BTC."""
    ok = [g for g in gaps if g.get("status") == "approved" and (g.get("answer") or "").strip()]
    os.makedirs(kb_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(kb_dir, "bo-sung-tri-thuc.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# Bổ sung tri thức (Knowledge Gap Loop — mục nào cũng đã có người duyệt)\n\n")
        for g in ok:
            f.write(f"## [BS-{g['id'][3:]}] {g['query']}\n{g['answer'].strip()}\n\n")
    for old in glob.glob(os.path.join(test_dir, "KG-*.json")):
        os.remove(old)
    for g in ok:
        scen = {"scenario_id": g["id"], "level": "M1", "persona": "knowledge_gap", "hard_case": "hoi_ngoai_tai_lieu_da_bo_sung",
                "customer_phone": "0900000000", "customer_name": "Khách", "honorific": "anh/chị",
                "notes": f"Sinh tự động từ thiếu sót {g['id']} (lần đầu thấy ở {g.get('scenario_id')}/{g.get('call')} lượt {g.get('turn')}).",
                "calls": {"call_1": {"customer_turns": [g["customer_text"] or g["query"]],
                                     "success_if": {"tool_called": None, **({"must_say_any": g["must_say"]} if g.get("must_say") else {})}}}}
        with open(os.path.join(test_dir, g["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(scen, f, ensure_ascii=False, indent=1)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["collect", "apply"])
    ap.add_argument("--trace", nargs="*", default=[])
    a = ap.parse_args()
    gaps = json.load(open(GAPS, encoding="utf-8")) if os.path.exists(GAPS) else []
    if a.cmd == "collect":
        rows = [json.loads(l) for p in a.trace for l in open(p, encoding="utf-8")]
        n0 = len(gaps)
        gaps = merge(gaps, find_gaps(rows))
        with open(GAPS, "w", encoding="utf-8") as f:
            json.dump(gaps, f, ensure_ascii=False, indent=1)
        print(f"{len(rows)} lượt → {len(gaps) - n0} thiếu sót mới, tổng {len(gaps)} ({sum(g['status'] == 'pending' for g in gaps)} chờ duyệt) → {GAPS}")
    else:
        ok = apply(gaps)
        print(f"đã áp dụng {len(ok)}/{len(gaps)} mục đã duyệt → {KB_DIR}, {TEST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
