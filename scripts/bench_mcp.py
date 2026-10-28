"""
Đo độ trễ TĂNG THÊM của MCP: gọi trực tiếp (`local`) vs MCP cùng tiến trình (`inproc`) vs MCP server là tiến trình riêng (`stdio`).
Không tốn API. Kết quả: bảng markdown + runs/mcp_overhead.json.

    python scripts/bench_mcp.py [--n 200]
"""
import argparse
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

CALLS = [
    ("pricing.get_quote", {"sku": "SKU-AP-Y", "on": "2026-10-15", "customer_phone": "0984726714"}, "LLMOrchestrator"),
    ("catalog.search", {"query": "AirPure"}, "LLMOrchestrator"),
    ("inventory.check", {"sku": "SKU-AP-Y", "on": "2026-10-15"}, "LLMOrchestrator"),
    ("crm.get_customer", {"phone": "0984726714"}, "IdentityResolver"),
    ("product.shortlist", {"category": "máy lọc không khí", "room_area_m2": 25, "has_children": True, "budget_vnd": 5000000, "on": "2026-10-15"}, "LLMOrchestrator"),
]


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def measure(gw, n):
    out = {}
    for tool, args, caller in CALLS:
        for _ in range(5):                                   # khởi động
            gw.execute_tool(tool, args, caller=caller)
        ms = []
        for _ in range(n):
            t = time.perf_counter()
            gw.execute_tool(tool, args, caller=caller)
            ms.append((time.perf_counter() - t) * 1000)
        out[tool] = {"p50": round(statistics.median(ms), 3), "p95": round(pct(ms, 0.95), 3), "mean": round(statistics.mean(ms), 3)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "runs", "mcp_overhead.json"))
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    from src.tools.mcp_gateway import LocalToolGateway, MCPToolGateway

    results, startup = {}, {}
    results["local"] = measure(LocalToolGateway(), args.n)
    startup["local"] = 0.0
    for transport in ("inproc", "stdio"):
        t = time.perf_counter()
        gw = MCPToolGateway(transport=transport, timeout_s=90)
        startup[transport] = round(time.perf_counter() - t, 3)
        try:
            results[transport] = measure(gw, args.n)
        finally:
            gw.close()

    lines = [f"Độ trễ mỗi lần gọi tool (ms), n = {args.n} lần/tool, máy dev, không tải khác. Khởi động: "
             + ", ".join(f"{k} {v:.2f}s" for k, v in startup.items()), "",
             "| tool | local p50 | local p95 | inproc p50 | inproc p95 | stdio p50 | stdio p95 | tăng thêm stdio (p50) |", "|---|---|---|---|---|---|---|---|"]
    for tool, _, _ in CALLS:
        r = {k: results[k][tool] for k in results}
        lines.append(f"| {tool} | {r['local']['p50']} | {r['local']['p95']} | {r['inproc']['p50']} | {r['inproc']['p95']} | "
                     f"{r['stdio']['p50']} | {r['stdio']['p95']} | +{r['stdio']['p50'] - r['local']['p50']:.2f} ms |")
    print("\n".join(lines))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"n": args.n, "startup_s": startup, "results": results}, fh, ensure_ascii=False, indent=1)
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
