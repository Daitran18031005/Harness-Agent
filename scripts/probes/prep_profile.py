"""Đo phần CHUẨN BỊ trước LLM (không gọi LLM, 0 VND): LLMClient giả trả lời ngay, mọi phần code (chuẩn hóa, nhận diện, Call Brief,
bộ nhớ qua MCP, tool qua MCP, dựng prompt) chạy thật như run_eval. Ghi theo từng bước: tổng ms trước / sau khi LLM bắt đầu, mỗi lượt.
Chạy:  python scripts/probes/prep_profile.py OUT_DIR SCENARIO_ID ...   (cùng env cờ như m1_final8; OPENAI_API_KEY bị xóa)"""
import os, sys, time, json, threading, collections, functools
os.environ["OPENAI_API_KEY"] = ""                            # chặn mọi lời gọi OpenAI thật (rỗng: load_dotenv không ghi đè biến đã có)
os.environ.setdefault("MCP_TRANSPORT", "stdio"); os.environ.setdefault("MEMORY_TRANSPORT", "stdio")
sys.path.insert(0, os.getcwd())
from src.llm import client as C
from src.llm.client import LLMClient
from src.eval.runner import ScenarioRunner
assert os.environ.get("OPENAI_API_KEY") == "", "OPENAI_API_KEY phải rỗng"

STATE = {"llm_started": False}
ACC = collections.defaultdict(lambda: [0.0, 0])               # (pha, bước) -> [ms, số lần]
LOCK = threading.Lock()

def timed(label_fn):
    def deco(fn):
        @functools.wraps(fn)
        def w(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                ms = (time.perf_counter() - t) * 1000
                with LOCK:
                    key = ("trước LLM" if not STATE["llm_started"] else "sau LLM", label_fn(a, k))
                    ACC[key][0] += ms; ACC[key][1] += 1
        return w
    return deco

class FakeLLM(LLMClient):
    def __init__(self, seed=None):
        super().__init__(seed=seed)
        self.available = True
        self._tools = C.build_openai_tools()
    def complete_json(self, messages, max_tokens=None):
        return {}, {"prompt_tokens": 0, "completion_tokens": 0}
    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None, **kw):
        STATE["llm_started"] = True
        if callable(tools_override):
            tools_override()                                   # dựng tools động như vòng thật
        if timing is not None:
            timing.update({"ttft_ms": 0, "total_ms": 0, "llm_calls": 1, "rounds_before_first_token": 0, "round_ms": [0], "tool_ms": 0,
                           "final_round_ttft_ms": 0, "nudged": False, "hedged_rounds": 0})
        return "Dạ em ghi nhận ạ.", [], {"prompt_tokens": 0, "completion_tokens": 0}

from src.channels.normalizer import RequestNormalizer
from src.identity.resolver import IdentityResolver
from src.harness.call_brief import CallBriefBuilder
from src.harness.orchestrator import HarnessOrchestrator
from src.memory.remote import MemoryLink
from src.tools import mcp_gateway as G

_orig_norm = RequestNormalizer.normalize
def norm(self, *a, **k):
    STATE["llm_started"] = False                              # lượt mới bắt đầu ở bước chuẩn hóa (runner đặt t_start ngay trước)
    return timed(lambda a, k: "1 chuẩn hóa")(_orig_norm)(self, *a, **k)
RequestNormalizer.normalize = norm
IdentityResolver.resolve = timed(lambda a, k: "2 nhận diện khách")(IdentityResolver.resolve)
CallBriefBuilder.build = timed(lambda a, k: "3 Call Brief")(CallBriefBuilder.build)
HarnessOrchestrator.process_turn = timed(lambda a, k: "4 process_turn (cả lượt)")(HarnessOrchestrator.process_turn)
HarnessOrchestrator._build_llm_messages = timed(lambda a, k: "5 dựng prompt")(HarnessOrchestrator._build_llm_messages)
MemoryLink.call = timed(lambda a, k: "mem: " + str(a[1]))(MemoryLink.call)
for cls in (G.MCPToolGateway, G.LocalToolGateway):
    cls.execute_tool = timed(lambda a, k: "tool: " + str(a[1]) + " / " + str(k.get("caller", a[3] if len(a) > 3 else "")))(cls.execute_tool)

if __name__ == "__main__":
    out = sys.argv[1]; only = sys.argv[2:] or None
    os.makedirs(out, exist_ok=True)
    runner = ScenarioRunner(scenarios_dir="BTC-Data-Vong1-TEAMS/test_set/team_eval")
    t = time.perf_counter()
    runner.run_all(config="full", output_trace_file=os.path.join(out, "full.jsonl"), only=only, seed=42, llm_client=FakeLLM(seed=42), max_cost_vnd=1)
    rows = [json.loads(l) for l in open(os.path.join(out, "full.jsonl"), encoding="utf-8")]
    n = len(rows)
    res = {"turns": n, "wall_s": round(time.perf_counter() - t, 1),
           "steps": {f"{ph} | {name}": {"ms_per_turn": round(v[0] / n, 1), "calls_per_turn": round(v[1] / n, 2), "ms_per_call": round(v[0] / max(1, v[1]), 1)}
                     for (ph, name), v in sorted(ACC.items(), key=lambda x: -x[1][0])}}
    xs = sorted(r["latency"]["ttft_ms"] for r in rows if r.get("latency_detail"))
    if xs:
        res["pre_llm_ms (ttft với LLM giả)"] = {"n": len(xs), "p50": xs[len(xs) // 2], "p90": xs[int(.9 * len(xs))], "p95": xs[int(.95 * len(xs))]}
    json.dump(res, open(os.path.join(out, "profile.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))
