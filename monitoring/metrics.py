"""Số đo giám sát (Prometheus/Grafana) tính từ ĐÚNG dòng trace của mỗi lượt — một nguồn duy nhất cho hai đường:
  * trực tiếp: API ghi mỗi lượt vào `Registry` và phát ở `GET /metrics`;
  * ngoại tuyến: `monitoring/trace_exporter.py` đọc file trace JSONL của các lần chạy đánh giá.

Tự viết định dạng văn bản Prometheus (counter / gauge / histogram) nên không thêm phụ thuộc `prometheus_client`.
shortcut: không có summary/native histogram, nhãn tự do không giới hạn số tổ hợp — đủ cho một máy chủ demo; dùng prometheus_client khi chạy nhiều worker."""
import threading
from typing import Any, Dict, Iterable, Optional, Tuple

PREFIX = "harness_"
SECONDS = (0.25, 0.5, 1, 2, 3, 5, 8, 13, 21, 34)       # 3 s và 8 s là ngưỡng TTFT / Total của BTC nên là mép bucket
SMALL_COUNTS = (0, 1, 2, 3, 4, 6)

HELP = {
    "turns_total": "Số lượt hội thoại đã xử lý",
    "ttft_seconds": "TTFT: từ lúc nhận request tới token đầu của câu trả lời (ngưỡng BTC p95 <= 3 s)",
    "total_seconds": "Tổng thời gian một lượt (ngưỡng BTC p95 <= 8 s)",
    "call_brief_seconds": "Thời gian dựng Call Brief ở lượt đầu của cuộc gọi lại (ngưỡng BTC <= 5 s)",
    "llm_calls": "Số vòng gọi API LLM trong một lượt",
    "rounds_before_first_token": "Số vòng LLM phải xong trước token đầu tiên",
    "final_round_ttft_seconds": "Chờ token đầu của riêng vòng LLM cuối",
    "tool_seconds": "Tổng thời gian chạy tool giữa các vòng LLM trong một lượt",
    "llm_cost_vnd_total": "Chi phí LLM tích lũy (VND)",
    "llm_tokens_total": "Token LLM theo loại (prompt / completion / cached)",
    "tool_calls_total": "Số lời gọi tool theo tên và kết quả",
    "guardrail_total": "Lượt theo kết quả guardrail (approved / violation + loại)",
    "order_gate_events_total": "Sự kiện order gate theo hành động",
    "llm_spent_vnd": "Chi phí LLM đã tiêu của máy chủ (VND)",
    "llm_cap_vnd": "Trần chi phí LLM cứng của máy chủ (VND)",
}


def _fmt(v: float) -> str:
    return repr(float(v)) if v != int(v) else str(int(v))


def _labels(items: Iterable[Tuple[str, str]], extra: Optional[Tuple[str, str]] = None) -> str:
    pairs = list(items) + ([extra] if extra else [])
    if not pairs:
        return ""
    esc = lambda s: str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return "{" + ",".join(f'{k}="{esc(v)}"' for k, v in pairs) + "}"


class Registry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, Dict[tuple, float]] = {}
        self._gauges: Dict[str, Dict[tuple, float]] = {}
        self._hist: Dict[str, Dict[tuple, dict]] = {}
        self._buckets: Dict[str, tuple] = {}

    @staticmethod
    def _key(labels: Optional[Dict[str, Any]]) -> tuple:
        return tuple(sorted((k, str(v)) for k, v in (labels or {}).items()))

    def inc(self, name: str, labels: Optional[dict] = None, value: float = 1) -> None:
        with self._lock:
            d = self._counters.setdefault(name, {})
            k = self._key(labels)
            d[k] = d.get(k, 0) + value

    def set(self, name: str, value: float, labels: Optional[dict] = None) -> None:
        with self._lock:
            self._gauges.setdefault(name, {})[self._key(labels)] = value

    def observe(self, name: str, value: float, buckets: tuple, labels: Optional[dict] = None) -> None:
        with self._lock:
            self._buckets[name] = buckets
            h = self._hist.setdefault(name, {}).setdefault(self._key(labels), {"counts": [0] * len(buckets), "sum": 0.0, "n": 0})
            for i, b in enumerate(buckets):
                if value <= b:
                    h["counts"][i] += 1
            h["sum"] += value
            h["n"] += 1

    def render(self) -> str:
        out = []
        with self._lock:
            for kind, store in (("counter", self._counters), ("gauge", self._gauges)):
                for name in sorted(store):
                    out.append(f"# HELP {PREFIX}{name} {HELP.get(name, name)}\n# TYPE {PREFIX}{name} {kind}")
                    for k, v in sorted(store[name].items()):
                        out.append(f"{PREFIX}{name}{_labels(k)} {_fmt(v)}")
            for name in sorted(self._hist):
                out.append(f"# HELP {PREFIX}{name} {HELP.get(name, name)}\n# TYPE {PREFIX}{name} histogram")
                for k, h in sorted(self._hist[name].items()):
                    for b, c in zip(self._buckets[name], h["counts"]):
                        out.append(f"{PREFIX}{name}_bucket{_labels(k, ('le', _fmt(b)))} {c}")
                    out.append(f"{PREFIX}{name}_bucket{_labels(k, ('le', '+Inf'))} {h['n']}")
                    out.append(f"{PREFIX}{name}_sum{_labels(k)} {_fmt(h['sum'])}")
                    out.append(f"{PREFIX}{name}_count{_labels(k)} {h['n']}")
        return "\n".join(out) + "\n"


def observe_turn(reg: Registry, row: Dict[str, Any], **labels: str) -> None:
    """Ghi một dòng trace (đúng cấu trúc `TurnTracer.log`) vào registry. `labels`: nguồn (api/trace), config, run… Trường thiếu thì bỏ qua."""
    base = {k: v for k, v in labels.items() if v is not None}
    reg.inc("turns_total", base)
    lat = row.get("latency") or {}
    if lat.get("ttft_ms") is not None:
        reg.observe("ttft_seconds", lat["ttft_ms"] / 1000, SECONDS, base)
    if lat.get("total_ms") is not None:
        reg.observe("total_seconds", lat["total_ms"] / 1000, SECONDS, base)
    if row.get("call_brief_latency_ms") is not None:
        reg.observe("call_brief_seconds", row["call_brief_latency_ms"] / 1000, (0.05, 0.1, 0.25, 0.5, 1, 2, 5), base)
    cost = row.get("llm_cost") or {}
    if cost:
        reg.inc("llm_cost_vnd_total", base, float(cost.get("vnd_cost") or 0))
        for kind, key in (("prompt", "prompt_tokens"), ("completion", "completion_tokens"), ("cached", "cached_tokens")):
            reg.inc("llm_tokens_total", {**base, "kind": kind}, float(cost.get(key) or 0))
        if cost.get("llm_calls") is not None:
            reg.observe("llm_calls", cost["llm_calls"], SMALL_COUNTS, base)
    detail = row.get("latency_detail") or {}
    if "rounds_before_first_token" in detail:
        reg.observe("rounds_before_first_token", detail["rounds_before_first_token"], SMALL_COUNTS, base)
        reg.observe("final_round_ttft_seconds", detail.get("final_round_ttft_ms", 0) / 1000, SECONDS, base)
        reg.observe("tool_seconds", detail.get("tool_ms", 0) / 1000, SECONDS, base)
    for c in row.get("tool_calls") or []:
        name = c.get("tool") or c.get("name") or "unknown"
        err = bool((c.get("result") or {}).get("error")) if isinstance(c.get("result"), dict) else False
        reg.inc("tool_calls_total", {**base, "tool": name, "outcome": "error" if err else "ok"})
    g = row.get("guardrail") or {}
    reg.inc("guardrail_total", {**base, "result": "violation" if g.get("violation") else "approved", "type": str(g.get("violation") or "none")})
    gate = row.get("order_gate")
    for e in (gate if isinstance(gate, list) else []):
        reg.inc("order_gate_events_total", {**base, "action": str(e.get("action") or e.get("type") or "unknown")})
