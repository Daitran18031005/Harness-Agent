"""Đo thời gian search_policy (0 VND): câu tra thật lấy từ trace (query LLM | lời khách, như POLICY_QUERY_CONTEXT), gọi qua mcp-memory (stdio) và gọi thẳng trong tiến trình.
Chạy: python scripts/probes/policy_latency_probe.py TRACE.jsonl [N]"""
import os, sys, json, time, statistics as st
os.environ["OPENAI_API_KEY"] = ""
sys.path.insert(0, os.getcwd())
from src.memory.remote import create_memory_service
from src.memory.service import MemoryService

rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
qs = []
for r in rows:
    for t in r["tool_calls"]:
        if t["name"] == "search_policy" and t.get("by") == "llm":
            qs.append(f'{t["args"].get("query", "")} | {r["customer_text"]}')
qs = qs[:n]
q = lambda a: f"p50 {int(st.median(a))} / p90 {int(sorted(a)[int(.9 * len(a))])} / max {int(max(a))} ms"
for name, mem in (("qua MCP stdio", create_memory_service(enable_persistence=False, transport="stdio")), ("trong tiến trình", MemoryService(enable_persistence=False))):
    for _ in range(5):                                                          # lần đầu nạp model trong server có thể quá 60 s
        try:
            mem.query_policy("khởi động", on_date="2026-10-15"); break
        except Exception as e:
            print("khởi động lại:", type(e).__name__)
    ts = []
    for x in qs:
        time.sleep(float(os.environ.get("PROBE_GAP_S", "0")))             # khoảng nghỉ như lúc chạy thật (LLM đang sinh) — GPU có thể hạ xung
        t = time.perf_counter(); mem.query_policy(x, on_date="2026-10-15"); ts.append((time.perf_counter() - t) * 1000)
    print(f"{name}: {len(ts)} câu, {q(ts)}")
