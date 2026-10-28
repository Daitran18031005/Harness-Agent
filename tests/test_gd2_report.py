"""scripts/gd2_report.py — gộp trace 2 bộ, mean ± std qua seed, ngưỡng BTC (không LLM, trace tự dựng)."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "scripts")))
import gd2_report as G   # noqa: E402


class HelpersTest(unittest.TestCase):
    def test_mean_std_ignores_missing_and_bool(self):
        self.assertEqual(G._mean_std([10, 20, None, True]), {"mean": 15.0, "std": 7.07, "n": 2, "values": [10, 20]})
        self.assertIsNone(G._mean_std([None, "x"]))
        self.assertEqual(G._mean_std([5])["std"], 0.0)

    def test_runs_reads_suffixed_and_plain_names(self):
        d = tempfile.mkdtemp()
        for n in ("full.r1.jsonl", "full.r2.jsonl", "baseline.r1.jsonl", "full.r1.txt", "fullness.jsonl"):
            open(os.path.join(d, n), "w").close()
        self.assertEqual(sorted(G._runs(d, "full")), [1, 2])
        self.assertEqual(sorted(G._runs(d, "baseline")), [1])
        open(os.path.join(d, "x.jsonl"), "w").close()
        d2 = tempfile.mkdtemp()
        open(os.path.join(d2, "full.jsonl"), "w").close()
        self.assertEqual(list(G._runs(d2, "full")), [1])                       # một lần chạy không có hậu tố .rK

    def test_concat_keeps_every_line_once(self):
        d = tempfile.mkdtemp()
        a, b = os.path.join(d, "a.jsonl"), os.path.join(d, "b.jsonl")
        open(a, "w").write(json.dumps({"x": 1}) + "\n")
        open(b, "w").write(json.dumps({"x": 2}))                                # thiếu xuống dòng cuối
        out = G._concat([a, b], os.path.join(d, "m.jsonl"))
        self.assertEqual([json.loads(l)["x"] for l in open(out)], [1, 2])


if __name__ == "__main__":
    unittest.main()
