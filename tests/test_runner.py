"""Bước 2–3 — runner/CLI chuẩn BTC, baseline stateless, latency thật (B1, B2, B3, B5, B8, N8, N9)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests._helpers import CODE_DIR, PUBLIC_DIR


class RunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        from src.eval.runner import ScenarioRunner
        r = ScenarioRunner(PUBLIC_DIR)
        cls.full = os.path.join(cls.dir, "full.jsonl")
        cls.base = os.path.join(cls.dir, "base.jsonl")
        r.run_all(config="full", output_trace_file=cls.full, only=["SAMPLE-01", "SAMPLE-04"])
        r.run_all(config="baseline_no_memory", output_trace_file=cls.base, only=["SAMPLE-01", "SAMPLE-04"])
        with open(cls.full, encoding="utf-8") as fh:
            cls.rows_full = [json.loads(line) for line in fh]
        with open(cls.base, encoding="utf-8") as fh:
            cls.rows_base = [json.loads(line) for line in fh]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_latency_not_fake(self):  # B1
        for r in self.rows_full:
            self.assertNotIn("call_brief_ms", r["latency"])
            self.assertIsInstance(r["latency"]["total_ms"], int)
        # Nhánh không-LLM: số đo thật rất nhỏ. Dùng trung vị (lượt đầu có thể chậm do khởi động nguội/tải máy);
        # số giả cũ là random 350–750 ms nên trung vị luôn ≥ 350.
        totals = sorted(r["latency"]["total_ms"] for r in self.rows_full)
        self.assertLess(totals[len(totals) // 2], 300)

    def test_call_brief_latency_field(self):  # B8
        c2t1 = [r for r in self.rows_full if r["call"] == "call_2" and r["turn"] == 1]
        self.assertTrue(c2t1 and all(isinstance(r.get("call_brief_latency_ms"), int) for r in c2t1))
        c1 = [r for r in self.rows_full if r["call"] == "call_1"]
        self.assertTrue(all(r.get("call_brief_latency_ms") is None for r in c1))

    def test_trace_has_memory_writes_and_mode(self):  # B8
        for r in self.rows_full:
            self.assertIn("memory_writes", r)
            self.assertIn(r["customer_input_mode"], ("clean", "asr_transcript", "chat_teencode"))

    def test_baseline_has_no_cross_call_memory(self):  # B2
        c2 = [r for r in self.rows_base if r["call"] == "call_2" and r["turn"] == 1]
        for r in c2:
            self.assertEqual(r.get("_brief_must_carry_over", []), [])

    def test_full_does_not_seed_answers(self):  # B3
        """call_2 brief của full chỉ chứa fact hệ thống tự ghi (không có 'phone_provided'/'channel' từ đáp án)."""
        c2 = [r for r in self.rows_full if r["scenario_id"] == "SAMPLE-04" and r["call"] == "call_2" and r["turn"] == 1][0]
        self.assertNotIn("phone_provided", c2.get("_brief_facts", []))

    def test_cli_has_btc_flags(self):  # B5
        out = subprocess.run([sys.executable, os.path.join(CODE_DIR, "run_eval.py"), "--help"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", cwd=CODE_DIR, env={**os.environ, "PYTHONUTF8": "1"})
        for flag in ("--scenarios", "--config", "--out", "--seed"):
            self.assertIn(flag, out.stdout)


class BudgetGuardTest(unittest.TestCase):  # hàng rào chi phí cứng (--max-cost-vnd)
    def _stub_llm(self, spent_usd):
        from types import SimpleNamespace
        from src.llm.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.cumulative_usd_cost = spent_usd
        return SimpleNamespace(available=False, cost_tracker=tracker)

    def test_stops_when_over_limit_and_keeps_partial_trace(self):
        from src.eval.runner import ScenarioRunner, BudgetExceeded
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "t.jsonl")
        with self.assertRaises(BudgetExceeded) as ctx:
            ScenarioRunner(PUBLIC_DIR).run_all(config="full", output_trace_file=out, only=["SAMPLE-01"],
                                               llm_client=self._stub_llm(0.5), max_cost_vnd=100)   # 0.5 USD ≈ 12.700 VND
        self.assertGreater(ctx.exception.spent_vnd, 100)
        with open(out, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        self.assertEqual(len(rows), 1)                                                          # lượt đã chạy được giữ lại

    def test_no_limit_or_under_limit_runs_all(self):
        from src.eval.runner import ScenarioRunner
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "t.jsonl")
        ScenarioRunner(PUBLIC_DIR).run_all(config="full", output_trace_file=out, only=["SAMPLE-01"],
                                           llm_client=self._stub_llm(0.0), max_cost_vnd=100)
        with open(out, encoding="utf-8") as fh:
            self.assertGreater(len(fh.readlines()), 3)

    def test_cli_rejects_a_non_positive_cost_cap(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, "t.jsonl")
        proc = subprocess.run([sys.executable, os.path.join(CODE_DIR, "run_eval.py"), "--config", "full", "--only", "SAMPLE-01",
                               "--out", out, "--max-cost-vnd", "-1"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=CODE_DIR, env={**os.environ, "PYTHONUTF8": "1", "OPENAI_API_KEY": ""})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)          # trần cứng luôn bật: không có chế độ chạy không trần / trần âm
        self.assertIn("phải > 0", proc.stdout)


if __name__ == "__main__":
    unittest.main()
