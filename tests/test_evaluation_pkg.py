"""Pipeline đánh giá tách riêng (bước 14a): chấm lại từ trace nhỏ tự dựng, ca sai, đọc vẹt, file chấm tay, độc lập với runtime."""
import ast
import csv
import json
import os
import tempfile
import unittest

from evaluation import __main__ as cli
from evaluation import failures, parrot, scoring, sheet

PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluation")

SCENARIO = {
    "scenario_id": "T-01", "hard_case": None,
    "calls": {
        "call_1": {"facts_established": {"product_advised": "SKU-AP-X", "price_quoted_vnd": 4890000,
                                         "room_area_m2": 35, "blocker": "so sanh gia"}},
        "call_2": {"must_carry_over": ["price_quoted_vnd", "product_advised"], "must_not_ask": ["product_advised"],
                   "ground_truth_facts": {"price_vnd": 4890000},
                   "success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-X"}}},
    },
}


def row(call, turn, text, **kw):
    r = {"run_id": "R", "config": "full", "scenario_id": "T-01", "call": call, "turn": turn, "customer_text": "alo",
         "agent_text": text, "questions": [], "claims": [], "facts_used": [], "tool_calls": [],
         "latency": {"ttft_ms": 10, "total_ms": 20}, "memory_writes": []}
    r.update(kw)
    return r


BAD = [  # câu chào đọc vẹt 3 fact, hỏi lại slot cấm, báo sai giá, không chốt đơn
    row("call_1", 1, "Dạ chào chị."),
    row("call_2", 1, "Dạ hôm trước em tư vấn phòng 35m2 giá 4.890.000đ, chị còn cân nhắc không ạ?", facts_used=["price_quoted_vnd"]),
    row("call_2", 2, "Giá 5.200.000đ ạ. Chị chọn sản phẩm nào?",
        questions=[{"slot": "product_advised", "type": "open", "text": "Chị chọn sản phẩm nào?"}],
        claims=[{"field": "price_vnd", "value": 5200000, "text": "Giá 5.200.000đ"}]),
]
GOOD = [
    row("call_1", 1, "Dạ chào chị."),
    row("call_2", 1, "Dạ hôm trước em tư vấn giá 4.890.000đ, chị chốt không ạ?", facts_used=["price_quoted_vnd", "product_advised"]),
    row("call_2", 2, "Dạ em lên đơn ạ.", tool_calls=[{"name": "order.create", "args": {"sku": "SKU-AP-X"}, "result": {"order_id": "O1"}}]),
]


class EvalPkgTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = scoring.load_reference()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sc_dir = os.path.join(cls.tmp.name, "sc")
        os.makedirs(cls.sc_dir)
        with open(os.path.join(cls.sc_dir, "T-01.json"), "w", encoding="utf-8") as fh:
            json.dump(SCENARIO, fh)
        cls.bad, cls.good = (cls._write(n, rows) for n, rows in (("bad", BAD), ("good", GOOD)))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def _write(cls, name, rows):
        p = os.path.join(cls.tmp.name, name + ".jsonl")
        with open(p, "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        return p

    def cases(self, path, **kw):
        return failures.failure_cases(self.ref, self.ref.load_scenarios(self.sc_dir), self.ref.load_trace(path), **kw)

    def test_score_matches_reference(self):
        sc = self.ref.load_scenarios(self.sc_dir)
        rep = scoring.score(self.ref, sc, self.bad, baseline_path=self.good)
        self.assertEqual(rep["system"]["task_success_rate"]["value"], 0.0)
        self.assertEqual(rep["baseline"]["task_success_rate"]["value"], 100.0)
        self.assertIn("meets_rqr_threshold_40pct", rep["comparison"])

    def test_failure_cases_list_each_metric(self):
        metrics = {c["metric"] for c in self.cases(self.bad)}
        self.assertEqual(metrics, {"tsr", "ccr", "rqr", "hr"})
        hr = [c for c in self.cases(self.bad) if c["metric"] == "hr"][0]
        self.assertEqual((hr["scenario"], hr["call"], hr["turn"]), ("T-01", "call_2", 2))
        self.assertEqual([c for c in self.cases(self.good) if c["metric"] != "parrot"], [])

    def test_missing_trace_reported(self):
        only_c1 = self._write("c1", BAD[:1])
        self.assertIn("missing_trace", {c["metric"] for c in self.cases(only_c1)})

    def test_parrot_rule(self):
        sc = self.ref.load_scenarios(self.sc_dir)
        hit = parrot.parrot_cases(sc, self.ref.load_trace(self.good_parrot()), max_old=2)
        self.assertEqual([(c["call"], c["turn"]) for c in hit], [("call_2", 1)])
        self.assertIn("product_advised", hit[0]["detail"])         # SKU tính qua facts_used
        self.assertEqual(parrot.parrot_cases(sc, self.ref.load_trace(self.good), max_old=2), [])
        self.assertEqual(parrot.parrot_cases(sc, self.ref.load_trace(self.good_parrot()), max_old=3), [])
        self.assertEqual(parrot.parrot_cases(sc, self.ref.load_trace(self.bad), max_old=2), [])   # 2 fact: giá + diện tích

    def good_parrot(self):
        rows = [GOOD[0], row("call_2", 1, "Dạ phòng 35m2, giá 4.890.000đ, chị đang phân vân đúng không ạ?",
                              facts_used=["product_advised"])]
        return self._write("parrot", rows)

    def test_manual_sheet_20_turns_csv(self):
        many = [row(f"call_{c}", t, f"agent {c}-{t}") for c in (1, 2) for t in range(1, 15)]
        tr = self.ref.load_trace(self._write("many", many))
        rows = sheet.pick_turns(tr, [], n=20, seed=1)
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows, sheet.pick_turns(tr, [], n=20, seed=1))     # tất định
        p = os.path.join(self.tmp.name, "s.csv")
        sheet.write_csv(rows, p)
        with open(p, encoding="utf-8-sig", newline="") as fh:
            back = list(csv.DictReader(fh))
        self.assertEqual(len(back), 20)
        self.assertEqual(list(back[0]), sheet.COLUMNS)

    def test_sheet_prefers_flagged_turns(self):
        tr = self.ref.load_trace(self.bad)
        rows = sheet.pick_turns(tr, self.cases(self.bad), n=1)
        self.assertEqual((rows[0]["call"], rows[0]["turn"]), ("call_2", 2))

    def test_cli_end_to_end(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(cli.main(["--trace", self.bad, "--baseline", self.good, "--scenarios", self.sc_dir, "--out-dir", out]), 0)
        for name in ("report.json", "failures.json", "failures.txt", "manual_review.csv"):
            self.assertTrue(os.path.getsize(os.path.join(out, name)) > 0, name)

    def test_package_does_not_import_runtime(self):
        banned = ("src", "pipeline", "run_eval", "main", "ui_app")
        for fn in os.listdir(PKG_DIR):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(PKG_DIR, fn), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                       [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
                for m in mods:
                    self.assertNotIn(m.split(".")[0], banned, f"{fn} import {m}")


if __name__ == "__main__":
    unittest.main()
