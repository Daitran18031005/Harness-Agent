"""Giám sát Prometheus/Grafana (monitoring/): định dạng văn bản, số đo từ dòng trace, /metrics của API, exporter đọc trace, và dashboard không tham chiếu số đo không tồn tại."""
import json
import os
import re
import tempfile
import unittest
from unittest import mock

from tests import _helpers  # noqa: F401
from tests.test_api import DATE, LAN, ApiCase

from api.app import create_app
from monitoring.metrics import HELP, PREFIX, Registry, observe_turn
from monitoring.trace_exporter import build_registry
from src.tracing.tracer import monitoring_extras

SAMPLE_ROW = {
    "config": "full", "latency": {"ttft_ms": 2500, "total_ms": 4200}, "call_brief_latency_ms": 70,
    "llm_cost": {"vnd_cost": 21.5, "prompt_tokens": 1000, "completion_tokens": 80, "cached_tokens": 600, "llm_calls": 2},
    "latency_detail": {"rounds_before_first_token": 1, "round_ms": [900, 800], "tool_ms": 15, "final_round_ttft_ms": 700},
    "tool_calls": [{"name": "pricing.get_quote", "result": {"final_price_vnd": 1}}, {"name": "order.create", "result": {"error": "price_mismatch"}}],
    "guardrail": {"approved": False, "violation": "price_hallucination"},
    "order_gate": [{"action": "ask_address"}, {"action": "readback"}],
}
LINE = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^{}]*\})? (-?\d+(\.\d+)?(e[+-]?\d+)?|\+Inf)$')


def values(text, name):
    return {l.rsplit(" ", 1)[0]: float(l.rsplit(" ", 1)[1]) for l in text.splitlines() if l.startswith(name) and not l.startswith("#")}


class RegistryFormatTest(unittest.TestCase):
    def test_every_line_is_valid_exposition_text(self):
        reg = Registry()
        observe_turn(reg, SAMPLE_ROW, source="trace", run='runs/"x"\\y', config="full")
        for line in reg.render().splitlines():
            if line and not line.startswith("#"):
                self.assertRegex(line, LINE, line)

    def test_histogram_is_cumulative_with_inf_sum_and_count(self):
        reg = Registry()
        for v in (0.4, 2.0, 9.0):
            reg.observe("ttft_seconds", v, (0.5, 3, 8), {"a": "b"})
        got = values(reg.render(), f"{PREFIX}ttft_seconds")
        self.assertEqual(got[f'{PREFIX}ttft_seconds_bucket{{a="b",le="0.5"}}'], 1)
        self.assertEqual(got[f'{PREFIX}ttft_seconds_bucket{{a="b",le="3"}}'], 2)
        self.assertEqual(got[f'{PREFIX}ttft_seconds_bucket{{a="b",le="8"}}'], 2)
        self.assertEqual(got[f'{PREFIX}ttft_seconds_bucket{{a="b",le="+Inf"}}'], 3)
        self.assertEqual(got[f'{PREFIX}ttft_seconds_count{{a="b"}}'], 3)
        self.assertAlmostEqual(got[f'{PREFIX}ttft_seconds_sum{{a="b"}}'], 11.4)


class ObserveTurnTest(unittest.TestCase):
    def test_trace_row_becomes_the_expected_series(self):
        reg = Registry()
        observe_turn(reg, SAMPLE_ROW, source="api", config="full")
        text = reg.render()
        self.assertEqual(values(text, f"{PREFIX}turns_total")[f'{PREFIX}turns_total{{config="full",source="api"}}'], 1)
        self.assertEqual(values(text, f"{PREFIX}llm_cost_vnd_total")[f'{PREFIX}llm_cost_vnd_total{{config="full",source="api"}}'], 21.5)
        self.assertIn(f'{PREFIX}tool_calls_total{{config="full",outcome="error",source="api",tool="order.create"}} 1', text)
        self.assertIn(f'{PREFIX}tool_calls_total{{config="full",outcome="ok",source="api",tool="pricing.get_quote"}} 1', text)
        self.assertIn(f'{PREFIX}guardrail_total{{config="full",result="violation",source="api",type="price_hallucination"}} 1', text)
        self.assertIn(f'{PREFIX}order_gate_events_total{{action="readback",config="full",source="api"}} 1', text)
        self.assertIn(f'{PREFIX}ttft_seconds_bucket{{config="full",source="api",le="3"}} 1', text)       # 2,5 s <= 3 s

    def test_missing_fields_are_skipped_and_a_clean_turn_counts_as_approved(self):
        reg = Registry()
        observe_turn(reg, {"latency": {"ttft_ms": 300, "total_ms": 300}, "tool_calls": []}, source="api")
        text = reg.render()
        self.assertNotIn("llm_cost", text)
        self.assertIn(f'{PREFIX}guardrail_total{{result="approved",source="api",type="none"}} 1', text)

    def test_monitoring_extras(self):
        self.assertEqual(monitoring_extras({}), {})
        self.assertEqual(monitoring_extras({"guardrail_approved": True, "violation": None, "llm_timing": {"ttft_ms": 1}}), {})
        got = monitoring_extras({"guardrail_approved": False, "violation": "x", "llm_timing": {"rounds_before_first_token": 1, "round_ms": [1, 2], "ttft_ms": 9}})
        self.assertEqual(got["guardrail"], {"approved": False, "violation": "x"})
        self.assertEqual(got["latency_detail"], {"rounds_before_first_token": 1, "round_ms": [1, 2]})


class ApiMetricsTest(ApiCase):
    def test_metrics_endpoint_counts_turns_and_never_breaks_a_chat(self):
        self.assertEqual(self.client.get("/metrics").status_code, 200)
        self.chat("Chị tên Lan, hỏi máy lọc không khí cho phòng 20m2", contact_id=LAN, channel="hotline", call_date=DATE)
        r = self.client.get("/metrics")
        self.assertTrue(r.headers["content-type"].startswith("text/plain"))
        self.assertRegex(r.text, rf'{PREFIX}turns_total{{config="full",source="api"}} 1\b')
        self.assertIn(f"{PREFIX}ttft_seconds_count", r.text)
        self.assertNotIn(LAN, r.text)                                   # không có PII trong số đo
        with mock.patch("api.routes.observe_turn", side_effect=RuntimeError("boom")):
            self.chat("giá bao nhiêu em", contact_id=LAN, channel="hotline", call_date=DATE)


class TraceExporterTest(unittest.TestCase):
    def test_reads_trace_files_and_skips_underscore_folders(self):
        with tempfile.TemporaryDirectory() as root:
            for sub in ("gd2_run9/gen", "gd2_run9/_merged"):
                os.makedirs(os.path.join(root, "runs", sub))
                with open(os.path.join(root, "runs", sub, "full.r1.jsonl"), "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(SAMPLE_ROW) + "\n" + '{"truncated":\n')       # dòng cuối dở dang do file đang ghi
            text = build_registry(("runs/gd2_run*/**/full*.jsonl",), root).render()
        self.assertIn('run="runs/gd2_run9/gen"', text)
        self.assertNotIn("_merged", text)
        self.assertIn(f'{PREFIX}turns_total{{config="full",run="runs/gd2_run9/gen",source="trace"}} 1', text)


class DashboardTest(unittest.TestCase):
    def test_dashboard_only_uses_metrics_the_code_produces(self):
        path = os.path.join(_helpers.CODE_DIR, "monitoring", "grafana", "dashboards", "harness.json")
        with open(path, encoding="utf-8") as fh:
            dash = json.load(fh)
        reg = Registry()
        observe_turn(reg, SAMPLE_ROW, source="api")
        reg.set("llm_spent_vnd", 1)
        reg.set("llm_cap_vnd", 2)
        produced = set(re.findall(r"^# TYPE (\S+)", reg.render(), re.M))
        used = set(re.findall(r"harness_[a-z_]+", json.dumps(dash)))
        base = {re.sub(r"_(bucket|sum|count)$", "", u) for u in used}
        self.assertEqual(sorted(b for b in base if b not in produced), [])
        self.assertTrue({f"{PREFIX}{k}" for k in HELP} >= produced)
        ids = [p["id"] for p in dash["panels"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
