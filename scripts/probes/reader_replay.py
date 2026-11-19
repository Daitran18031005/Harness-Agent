"""Replay bộ đọc (LLM thật, 20/11) trên N câu đầu runs/reader_replay_0113/before.jsonl — bản gốc vs READER_COMPACT (đặt qua env), hai tiến trình cùng lúc, 6 luồng.
Ghi TỪNG câu ngay khi xong (lần 1 mất trắng ~2.200 VND vì chỉ ghi ở cuối và BudgetExceeded làm dừng cả tiến trình). Chạm trần → dừng gửi câu mới, giữ kết quả đã có.
    python replay.py <tên> <out.jsonl> <trần VND> [N]"""
import json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); CODE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, CODE)
from src.llm.client import LLMClient
from src.harness.reply_reader import read_reply, reading_trace_dict
CAP = float(sys.argv[3]); N = int(sys.argv[4]) if len(sys.argv) > 4 else 100
items = [json.loads(l) for l in open(os.path.join(CODE, "runs", "reader_replay_0113", "before.jsonl"), encoding="utf-8")][:N]
llm = LLMClient(); llm.cost_tracker.set_hard_cap(CAP)
out = open(sys.argv[2], "w", encoding="utf-8"); lock = threading.Lock(); stop = threading.Event()

def one(it):
    if stop.is_set():
        return
    t = time.perf_counter()
    try:
        r = read_reply(llm, it["text"], it["last"], {"candidates": it.get("cands") or []}, guard="none")
        row = {"id": it["id"], "ms": int(1000 * (time.perf_counter() - t)), "ok": r is not None, "usage": (r.usage if r else None), "reading": reading_trace_dict(r) if r else {}}
    except BaseException as e:                       # BudgetExceeded là BaseException: dừng gửi câu mới, không mất kết quả đã ghi
        stop.set(); row = {"id": it["id"], "err": f"{type(e).__name__}: {e}"}
    with lock:
        out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n"); out.flush()

with ThreadPoolExecutor(6) as ex:
    list(ex.map(one, items))
print(sys.argv[1], "xong", N, "câu, chi phí VND", round(llm.cost_tracker.spent_vnd(), 1))
