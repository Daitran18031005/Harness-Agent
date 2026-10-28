"""Hai loại đo của order gate (src/eval/gate_metrics.py): TSR tương tác (chính) và kiểm tra kịch bản cố định (không tính TSR chính)."""
import os
import tempfile
import unittest

from src.eval import gate_metrics as GM

SPEC = {"success_if": {"tool_called": "order.create", "args_match": {"sku": "SKU-AP-Y", "price_vnd": 5200000}}}


def scen(sid="SC-D01"):
    return {sid: {"scenario_id": sid, "calls": {"call_1": dict(SPEC)}}}


def row(sid, turn, customer="x", gate=None, order=None, injected=False):
    r = {"scenario_id": sid, "call": "call_1", "turn": turn, "customer_text": customer, "agent_text": "ok", "tool_calls": [], "order_gate": gate or [], "questions": [], "claims": []}
    if order:
        r["tool_calls"].append({"name": "order.create", "args": order, "result": {"status": "created", "order_id": "OD600001"}})
    if injected:
        r["_injected"] = True
    return r


def trace(rows):
    out = {}
    for r in rows:
        out.setdefault((r["scenario_id"], r["call"]), []).append(r)
    return out


GOOD = {"sku": "SKU-AP-Y", "price_vnd": 5200000, "qty": 1, "payment": "COD"}
ASK = [{"action": "ask_confirm", "allow": False}]
RB = [{"action": "readback", "allow": False}]


class FixedScriptCheckTest(unittest.TestCase):
    def check(self, rows, sid="SAMPLE-01"):
        return GM.fixed_script_check(scen(sid), trace(rows))

    def test_stuck_at_the_first_question_is_not_a_pass_but_creates_nothing(self):
        c = self.check([row("SAMPLE-01", 1), row("SAMPLE-01", 2, gate=ASK)])
        r = c["calls"][0]
        self.assertEqual((r["stage"], r["early_order_turns"], r["reached_readback"], r["passed"]), ("ask", [], False, False))
        self.assertEqual((c["early_orders"], c["reached_any_gate_step"]), (0, 1))

    def test_reached_readback_without_creating_an_order_passes(self):
        c = self.check([row("SAMPLE-01", 1, gate=ASK), row("SAMPLE-01", 2, gate=RB)])
        self.assertTrue(c["calls"][0]["passed"])

    def test_order_created_without_a_readback_turn_before_it_is_an_early_order(self):
        c = self.check([row("SAMPLE-01", 1, gate=ASK), row("SAMPLE-01", 2, customer="ok em", order=GOOD)])
        self.assertEqual(c["calls"][0]["early_order_turns"], [2])
        self.assertFalse(c["calls"][0]["passed"])
        self.assertEqual(c["early_orders"], 1)

    def test_order_after_readback_and_explicit_consent_is_not_early(self):
        c = self.check([row("SAMPLE-01", 1, gate=RB), row("SAMPLE-01", 2, customer="ok chốt đi", order=GOOD)])
        self.assertEqual(c["calls"][0]["early_order_turns"], [])
        self.assertTrue(c["calls"][0]["passed"])

    def test_order_right_after_readback_but_without_clear_consent_is_early(self):
        c = self.check([row("SAMPLE-01", 1, gate=RB), row("SAMPLE-01", 2, customer="ừm để xem đã", order=GOOD)])
        self.assertEqual(c["calls"][0]["early_order_turns"], [2])


class InteractiveTsrTest(unittest.TestCase):
    def tsr(self, rows):
        return GM.interactive_tsr(scen(), trace(rows))

    def test_order_created_after_confirmation_with_right_sku_and_price_passes(self):
        r = self.tsr([row("SC-D01", 1, gate=ASK), row("SC-D01", 2, gate=RB, injected=True), row("SC-D01", 3, customer="ok em", order=GOOD, injected=True)])
        self.assertEqual((r["value"], r["passed"], r["total"], r["injected_turns"]), (100.0, 1, 1, 2))

    def test_wrong_sku_or_price_fails(self):
        for bad in ({**GOOD, "sku": "SKU-AP-X"}, {**GOOD, "price_vnd": 4890000}):
            r = self.tsr([row("SC-D01", 1, gate=RB), row("SC-D01", 2, customer="ok em", order=bad)])
            self.assertEqual(r["passed"], 0)
            self.assertIn("args_match", r["failures"][0]["reasons"][0])

    def test_right_order_but_not_after_confirmation_fails(self):
        r = self.tsr([row("SC-D01", 1, gate=ASK), row("SC-D01", 2, customer="ok em", order=GOOD)])
        self.assertEqual(r["passed"], 0)
        self.assertIn("chưa đọc lại đơn", r["failures"][0]["reasons"][0])

    def test_no_order_fails_and_reports_the_stage_reached(self):
        r = self.tsr([row("SC-D01", 1, gate=ASK)])
        self.assertEqual((r["passed"], r["failures"][0]["stage"]), (0, "ask"))


class ReportSplitTest(unittest.TestCase):
    def test_fixed_btc_and_interactive_are_reported_separately_and_assist_on_btc_is_flagged(self):
        scenarios = {**scen("SAMPLE-01"), **scen("SC-D01")}
        t = trace([row("SAMPLE-01", 1, gate=RB), row("SAMPLE-01", 2, customer="ok em", order=GOOD, injected=True),
                   row("SC-D01", 1, gate=RB), row("SC-D01", 2, customer="ok em", order=GOOD, injected=True)])
        text = GM.report_text(scenarios, t)
        self.assertIn("[1] TSR TƯƠNG TÁC (TSR CHÍNH)", text)
        self.assertIn("100.0% (1/1 kịch bản)", text)                                    # chỉ SC-D01 tính vào TSR chính
        self.assertIn("[2] KIỂM TRA KỊCH BẢN CỐ ĐỊNH", text)
        self.assertIn("KHÔNG tính vào TSR chính", text)
        self.assertIn("KHÔNG nên chạy với --gate-assist", text)

    def test_interactive_without_assist_is_labelled_as_not_meaningful(self):
        text = GM.report_text(scen("SC-D01"), trace([row("SC-D01", 1, gate=ASK)]))
        self.assertIn("KHÔNG có khách mô phỏng", text)

    def test_only_btc_samples_means_no_main_tsr(self):
        text = GM.report_text(scen("SAMPLE-02"), trace([row("SAMPLE-02", 1, gate=ASK)]))
        self.assertIn("chưa có số", text)


class AssistGuardTest(unittest.TestCase):
    def test_gate_assist_is_refused_on_btc_fixed_scenarios(self):
        import run_eval
        out = os.path.join(tempfile.mkdtemp(), "x.jsonl")
        self.assertEqual(run_eval.main(["--config", "full", "--only", "SAMPLE-01", "--gate-assist", "--out", out]), 2)


if __name__ == "__main__":
    unittest.main()
