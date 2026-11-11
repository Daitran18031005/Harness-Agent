"""
Run Evaluation Script — lệnh chuẩn BTC (B5):

    python run_eval.py --scenarios <dir> --config full|baseline_no_memory --out trace.jsonl [--seed N]

Chạy 1 cấu hình, ghi trace JSONL theo schema BTC. Cấu hình:
- full                : bộ nhớ 4 tầng do hệ thống TỰ ghi (không nạp đáp án).
- baseline_no_memory  : bộ nhớ mới ở mỗi call (stateless thật).
- full_oracle         : như full + nạp `facts_established` — chỉ để tham chiếu trần điểm, KHÔNG nộp.
- both (mặc định)     : chạy full + baseline_no_memory vào --out-dir (runs/), rồi gọi
                        BTC reference_eval.py in bảng Phụ lục A.6. --no-report bỏ bước chấm.

--repeats N chạy N lần với seed, seed+1, ... (file ra thêm hậu tố .rK) để báo mean ± std.
--only SAMPLE-01 SAMPLE-04 ... chỉ chạy các kịch bản chọn (rẻ khi thử).
"""
import os
import sys
import json
import shutil
import tempfile
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SCENARIOS = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")
EVAL_SCRIPT = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "eval", "reference_eval.py")
CONFIG_CHOICES = ["full", "baseline_no_memory", "full_oracle", "both"]


DEFAULT_MAX_COST_VND = 20000.0         # trần mặc định (ghi đè bằng --max-cost-vnd). Đủ cho bộ ẩn BTC 41 kịch bản × 2 cấu hình (≈ 170 lượt × ~34 VND × 2 ≈ 12.000); 1.500 cũ sẽ cắt ngang lần chấm của BTC


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Chạy kịch bản BTC qua Harness Agent và ghi trace JSONL.")
    p.add_argument("--scenarios", default=DEFAULT_SCENARIOS, help="Thư mục chứa các file kịch bản *.json")
    p.add_argument("--config", default="both", choices=CONFIG_CHOICES)
    p.add_argument("--out", default=None, help="File trace đầu ra (khi --config là 1 cấu hình)")
    p.add_argument("--out-dir", default=os.path.join(HERE, "runs"), help="Thư mục đầu ra khi --config both")
    p.add_argument("--seed", type=int, default=None, help="Seed cho LLM (ghi vào run_id); mặc định lấy LLM_SEED")
    p.add_argument("--repeats", type=int, default=1, help="Số lần lặp (seed, seed+1, ...)")
    p.add_argument("--only", nargs="+", default=None, help="Chỉ chạy các scenario_id này")
    p.add_argument("--no-report", action="store_true", help="Bỏ bước chấm reference_eval.py (khi --config both)")
    p.add_argument("--gate-assist", action="store_true",
                   help="Chèn lượt khách mô phỏng trả lời order gate (hỏi/xác nhận/đọc lại đơn) — chỉ để đo gate trên kịch bản BTC có lời khách cố định")
    p.add_argument("--max-cost-vnd", type=float, default=None,
                   help="Hàng rào chi phí CỨNG (VND, tổng mọi cấu hình/lần lặp), kiểm trước mỗi lần gọi API: chạm ngưỡng thì dừng ngay (mã thoát 3). "
                        "Mặc định 20.000 VND; luôn bật.")
    return p


def _with_suffix(path: str, repeat_idx: int, repeats: int) -> str:
    if repeats <= 1:
        return path
    stem, ext = os.path.splitext(path)
    return f"{stem}.r{repeat_idx}{ext}"


def _scenarios_subset_dir(scenarios: str, only) -> "tempfile.TemporaryDirectory":
    """Thư mục tạm chỉ chứa các kịch bản trong `only` — để reference_eval KHÔNG tính các kịch bản không chạy là
    'trượt' (làm sai TSR/CCR khi chạy --only)."""
    tmp = tempfile.TemporaryDirectory()
    wanted = set(only)
    for name in os.listdir(scenarios):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        with open(os.path.join(scenarios, name), encoding="utf-8") as fh:
            sid = json.load(fh).get("scenario_id")
        if sid in wanted:
            shutil.copy(os.path.join(scenarios, name), os.path.join(tmp.name, name))
    return tmp


def _run_reference_eval(scenarios: str, full_trace: str, baseline_trace: str, report_path: str, only=None) -> None:
    subset = _scenarios_subset_dir(scenarios, only) if only else None
    if subset is not None:
        scenarios = subset.name
    cmd = [sys.executable, EVAL_SCRIPT, "--scenarios", scenarios, "--trace", full_trace,
           "--baseline", baseline_trace, "--out", report_path]
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True, encoding="utf-8", errors="replace")
    print("\n" + "=" * 85)
    print("BẢNG KẾT QUẢ ĐÁNH GIÁ SO SÁNH VỚI BASELINE (CHUẨN PHỤ LỤC A):")
    print("=" * 85)
    print(proc.stdout)
    if proc.stderr:
        print("[Log/Errors]:", proc.stderr)
    if subset is not None:
        subset.cleanup()


def _print_gate_report(scenarios_dir: str, traces: dict, only, assisted: bool) -> None:
    """Order gate luôn bật → báo cáo TÁCH HAI LOẠI: [1] TSR tương tác (chính; cần --gate-assist) và [2] kiểm tra kịch bản cố định (BTC; không tính TSR chính)."""
    from src.eval import gate_metrics as GM
    ref = GM.ref
    print(chr(10) + "=" * 85)
    print("ORDER GATE — HAI LOẠI ĐO (gate luôn bật ở mọi cấu hình):")
    print("  LƯU Ý: dòng TSR của bảng A.6 ở trên chấm bằng lời khách như trong file kịch bản; với kịch bản BTC cố định đó KHÔNG phải TSR chính.")
    print("=" * 85)
    for cfg, path in traces.items():
        trace = ref.load_trace(path)
        ids = {sid for sid, _ in trace}
        scen = {k: v for k, v in ref.load_scenarios(scenarios_dir).items() if k in ids and (not only or k in only)}
        print(f"--- cấu hình {cfg}" + (" (có khách mô phỏng --gate-assist: lượt chèn gắn _injected)" if assisted else ""))
        print(GM.report_text(scen, trace))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")

    # Import muộn: --help chạy được kể cả khi thiếu thư viện.
    from dotenv import load_dotenv
    load_dotenv()
    # Số đo chính thức chạy trên kiến trúc MCP với server là TIẾN TRÌNH RIÊNG (stdio); đặt MCP_TRANSPORT=inproc để chạy cùng tiến trình.
    os.environ.setdefault("MCP_TRANSPORT", "stdio")
    os.environ.setdefault("MEMORY_TRANSPORT", "stdio")   # bộ nhớ cũng qua MCP server riêng (mcp-memory, nơi ghi duy nhất); MEMORY_TRANSPORT=local để chạy cùng tiến trình
    from src.env_check import check_environment
    from src.eval.runner import ScenarioRunner, BudgetExceeded, spent_vnd
    from src.llm.client import LLMClient

    env_report = check_environment()
    for problem in env_report["problems"]:
        print(f"[ENV] {problem}")

    if args.config != "both" and not args.out:
        print("Thiếu --out: cần chỉ định file trace đầu ra khi --config là 1 cấu hình.")
        return 2

    runner = ScenarioRunner(scenarios_dir=args.scenarios)
    if args.gate_assist:
        picked = [k for k in runner.load_scenarios() if not args.only or k in args.only]
        btc = [k for k in picked if k.startswith("SAMPLE-")]
        if btc:
            print(f"--gate-assist chỉ dành cho kịch bản TƯƠNG TÁC (loại [1], lời khách có đáp án cho order gate — luật P5). Kịch bản BTC cố định không được chạy với cờ này: {btc}")
            return 2
    base_seed = args.seed
    configs = ["full", "baseline_no_memory"] if args.config == "both" else [args.config]
    last_traces = {}
    # 1 LLMClient dùng chung cho mọi cấu hình/lần lặp -> bộ đếm chi phí là TỔNG (dùng cho --max-cost-vnd)
    shared_llm = LLMClient(seed=base_seed)
    # TRẦN CHI PHÍ CỨNG luôn bật: không truyền --max-cost-vnd thì dùng mặc định; client kiểm trước MỖI lần gọi API (kể cả vòng giữa lượt) và dừng khi chạm trần.
    cap = args.max_cost_vnd if args.max_cost_vnd is not None else DEFAULT_MAX_COST_VND
    if cap <= 0:
        print("--max-cost-vnd phải > 0 (không có chế độ chạy không trần).")
        return 2
    args.max_cost_vnd = cap
    shared_llm.cost_tracker.set_hard_cap(cap)
    if shared_llm.available:
        print(f"[COST] Trần chi phí CỨNG: {cap:,.0f} VND (dừng ngay khi chạm trần).")

    for r in range(1, args.repeats + 1):
        seed = None if base_seed is None else base_seed + (r - 1)
        for cfg in configs:
            if args.config == "both":
                name = "full.jsonl" if cfg == "full" else "baseline.jsonl"
                out = os.path.join(args.out_dir, name)
            else:
                out = args.out
            out = _with_suffix(out, r, args.repeats)
            print(f"[{r}/{args.repeats}] config={cfg} seed={seed} -> {out}")
            try:
                runner.run_all(config=cfg, output_trace_file=out, only=args.only, seed=seed,
                               llm_client=shared_llm, max_cost_vnd=args.max_cost_vnd, gate_assist=args.gate_assist)
            except BudgetExceeded as e:
                print(f"[DỪNG] {e}  (trace đã chạy được vẫn nằm ở {out})")
                return 3
            last_traces[cfg] = out
            print(f"    chi phí LLM tích lũy: {spent_vnd(shared_llm):,.1f} VND")

    if args.config == "both" and not args.no_report:
        _run_reference_eval(args.scenarios, last_traces["full"], last_traces["baseline_no_memory"],
                            os.path.join(args.out_dir, "report.json"), only=args.only)
    if last_traces and not args.no_report:
        _print_gate_report(args.scenarios, last_traces, args.only, bool(args.gate_assist))
    return 0


if __name__ == "__main__":
    sys.exit(main())
