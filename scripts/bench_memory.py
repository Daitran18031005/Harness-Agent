"""
Đo chi phí TĂNG THÊM khi bộ nhớ đi qua MCP server `mcp-memory`: cục bộ (`local`) vs MCP cùng tiến trình (`inproc`) vs MCP server là tiến trình riêng (`stdio`),
cho cả hai tầng tool (tool thấp của lõi, tool cao của orchestrator), và — khi chạy kịch bản thật (nhánh không-LLM nên không tốn API) — số lời gọi bộ nhớ MỖI LƯỢT,
tách theo tool: lời gọi NHẸ (đọc/ghi một fact) khác hẳn lời gọi NẶNG (`memory.open` dựng Semantic KB 99 chunk). Kết quả: bảng markdown + runs/memory_overhead.json.

    python scripts/bench_memory.py [--n 200]
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def ops(m):
    """Các thao tác điển hình của một lượt: đọc fact, đọc working, ghi fact, ghi working, đọc episode."""
    return {
        "profile_get": lambda: m.get_profile_facts("C1", on_date="2026-10-15"),
        "working_get": lambda: m.get_working("SESS-C1-2026-10-15"),
        "profile_set": lambda: m.set_profile_fact("C1", "color", "den"),
        "working_set": lambda: m.set_working("SESS-C1-2026-10-15", current_turn=2, messages_in_session=[{"role": "user", "content": "alo " * 20}] * 10),
        "episodes_get": lambda: m.get_episodes("C1"),
    }


def measure(core, orch, n):
    core.begin_turn("call_1#turn1", call_date="2026-10-15", channel="hotline")
    out = {}
    for name, fn in ops(orch).items():
        for _ in range(5):
            fn()
        ms = []
        for _ in range(n):
            t = time.perf_counter()
            fn()
            ms.append((time.perf_counter() - t) * 1000)
        out[name] = {"p50": round(statistics.median(ms), 3), "p95": round(pct(ms, 0.95), 3), "mean": round(statistics.mean(ms), 3)}
    orch.drain_writes()
    return out


def calls_per_turn(transport):
    """Chạy 2 kịch bản public (nhánh không-LLM) với bộ nhớ qua MCP; trả về số lời gọi, thời gian, và bảng theo tool."""
    os.environ["MEMORY_TRANSPORT"] = transport
    from src.eval.runner import ScenarioRunner
    from src.memory.remote import shared_link
    link = shared_link(transport)
    before_calls, before_ms = dict(link.calls), dict(link.ms_by_tool)
    d = tempfile.mkdtemp()
    out = os.path.join(d, "t.jsonl")
    t = time.perf_counter()
    ScenarioRunner(os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")).run_all(
        config="full", output_trace_file=out, only=["SAMPLE-01", "SAMPLE-04"])
    wall = (time.perf_counter() - t) * 1000
    with open(out, encoding="utf-8") as fh:
        turns = sum(1 for _ in fh)
    by_tool = {}
    for tool in link.calls:
        c = link.calls[tool] - before_calls.get(tool, 0)
        if c:
            ms = link.ms_by_tool[tool] - before_ms.get(tool, 0.0)
            by_tool[tool] = {"calls": c, "ms": round(ms, 1), "avg_ms": round(ms / c, 2)}
    calls = sum(v["calls"] for v in by_tool.values())
    ms = sum(v["ms"] for v in by_tool.values())
    light = {k: v for k, v in by_tool.items() if k not in ("memory.open", "memory.close")}
    return {"turns": turns, "memory_calls": calls, "memory_ms": round(ms, 1), "wall_ms": round(wall, 1), "by_tool": by_tool,
            "light_calls": sum(v["calls"] for v in light.values()), "light_ms": round(sum(v["ms"] for v in light.values()), 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "runs", "memory_overhead.json"))
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["MEMORY_EXTRACTOR_LLM"] = "0"
    from src.memory.remote import RemoteMemoryService, create_memory_service

    results, startup = {}, {}
    local = create_memory_service(enable_persistence=False, transport="local")
    results["local"] = measure(local, local, args.n)
    startup["local"] = 0.0
    for transport in ("inproc", "stdio"):
        t = time.perf_counter()
        core = RemoteMemoryService(enable_persistence=False, transport=transport, caller="HarnessCore")
        startup[transport] = round(time.perf_counter() - t, 3)
        results[f"{transport}/low"] = measure(core, core.as_caller("TestHarness"), args.n)           # tool thấp (lõi)
        results[f"{transport}/high"] = measure(core, core.as_caller("HarnessOrchestrator"), args.n)  # 6 tool cao (orchestrator)
        core.close()

    print(f"n = {args.n} lần/thao tác (ms, p50)\n")
    cols = ["local", "inproc/low", "inproc/high", "stdio/low", "stdio/high"]
    print("| thao tác | " + " | ".join(cols) + " | stdio/high p95 |")
    print("|---|" + "---|" * (len(cols) + 1))
    for name in results["local"]:
        print(f"| {name} | " + " | ".join(str(results[c][name]["p50"]) for c in cols) + f" | {results['stdio/high'][name]['p95']} |")
    print(f"\nKhởi động server (một lần, gồm memory.open đầu tiên): inproc {startup['inproc']} s, stdio {startup['stdio']} s")

    per_turn = {}
    for transport in ("inproc", "stdio"):
        per_turn[transport] = r = calls_per_turn(transport)
        print(f"\n[{transport}] {r['turns']} lượt: {r['memory_calls']} lời gọi ({r['memory_calls'] / r['turns']:.1f}/lượt), "
              f"{r['memory_ms']} ms trong MCP ({r['memory_ms'] / r['turns']:.1f} ms/lượt); "
              f"không tính open/close: {r['light_calls']} lời gọi ({r['light_calls'] / r['turns']:.1f}/lượt), {r['light_ms']} ms ({r['light_ms'] / r['turns']:.1f} ms/lượt)")
        print("| tool | số lời gọi | tổng ms | ms/lời gọi |\n|---|---|---|---|")
        for tool, v in sorted(r["by_tool"].items(), key=lambda kv: -kv[1]["ms"]):
            print(f"| {tool} | {v['calls']} | {v['ms']} | {v['avg_ms']} |")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"n": args.n, "per_call_ms": results, "startup_s": startup, "per_turn": per_turn}, fh, ensure_ascii=False, indent=2)
    print(f"\nĐã ghi {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
