"""Trần chi phí CỨNG: kiểm trước mỗi lần gọi API (kể cả vòng giữa lượt), không bị `except Exception` nuốt, trace đang chờ vẫn được ghi nốt."""
import json
import os
import tempfile
import unittest

from types import SimpleNamespace as NS

from tests._helpers import PUBLIC_DIR
from tests.test_llm_client import _chunk, _tc_delta, make_client
from src.llm.cost_tracker import BudgetExceeded, CostTracker


class TrackerCapTest(unittest.TestCase):
    def test_check_cap_raises_once_spent_reaches_the_cap(self):
        t = CostTracker()
        t.set_hard_cap(100)
        t.check_cap()                                              # chưa tiêu gì
        t.cumulative_usd_cost = 99 / t._vnd_rate()
        t.check_cap()                                              # 99 < 100
        t.cumulative_usd_cost = 100 / t._vnd_rate()
        with self.assertRaises(BudgetExceeded) as ctx:
            t.check_cap()
        self.assertGreaterEqual(ctx.exception.spent_vnd, 100)
        self.assertEqual(ctx.exception.limit_vnd, 100)

    def test_inflight_rounds_count_before_the_turn_is_recorded(self):
        t = CostTracker()
        t.set_hard_cap(5)
        for _ in range(200):                                       # nhiều vòng trong MỘT lượt, record_turn chưa được gọi
            t.note_round("gpt-4o-mini", 8000, 300)
            if t.spent_vnd() >= 5:
                break
        self.assertEqual(t.cumulative_usd_cost, 0.0)               # tổng thật chưa đổi…
        with self.assertRaises(BudgetExceeded):                    # …nhưng trần vẫn chặn vòng kế tiếp
            t.check_cap()
        t.record_turn("gpt-4o-mini", 8000, 300)
        self.assertEqual(t._inflight_usd, 0.0)                     # chi phí thật thay cho ước tính tạm (không đếm hai lần)

    def test_budget_exceeded_is_not_swallowed_by_except_exception(self):
        self.assertFalse(issubclass(BudgetExceeded, Exception))
        try:
            try:
                raise BudgetExceeded(10, 5)
            except Exception:                                      # kiểu `except Exception` ở orchestrator/bộ trích
                self.fail("BudgetExceeded bị except Exception nuốt")
        except BudgetExceeded:
            pass

    def test_invalid_cap_is_rejected(self):
        with self.assertRaises(ValueError):
            CostTracker().set_hard_cap(0)


class ClientCapTest(unittest.TestCase):
    def test_client_stops_before_calling_the_api(self):
        calls = []

        class FakeCompletions:
            def create(self, **kw):
                calls.append(kw)
                raise AssertionError("không được gọi API khi đã chạm trần")

        class FakeClient:
            chat = type("C", (), {"completions": FakeCompletions()})()

        os.environ["OPENAI_API_KEY"] = "sk-test-not-real"
        try:
            from src.llm.client import LLMClient
            c = LLMClient()
        finally:
            os.environ["OPENAI_API_KEY"] = ""
        c._client = FakeClient()
        c.cost_tracker.set_hard_cap(1)
        c.cost_tracker.cumulative_usd_cost = 2 / c.cost_tracker._vnd_rate()
        with self.assertRaises(BudgetExceeded):
            c._create([{"role": "user", "content": "x"}], [])
        with self.assertRaises(BudgetExceeded):
            c.complete_json([{"role": "user", "content": "x"}])    # complete_json không biến lỗi trần thành LLMUnavailable
        self.assertEqual(calls, [])


class FailedTurnCostTest(unittest.TestCase):
    """Audit #1: tiền của các vòng ĐÃ TRẢ trong một lượt hỏng giữa chừng không được biến mất khỏi tổng (nếu không, trần cứng và báo cáo chi phí thấp hơn thực tế)."""

    @staticmethod
    def _tool_round(prompt=6000, completion=300):
        return [_chunk(tool_calls=[_tc_delta(0, id="c1", name="inventory__check", arguments='{"sku": "SKU-AP-Y"}')]),
                _chunk(with_choice=False, usage=NS(prompt_tokens=prompt, completion_tokens=completion))]

    @staticmethod
    def _text_round(prompt=6000, completion=300):
        return [_chunk(content="Dạ xong ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=prompt, completion_tokens=completion))]

    def _client(self, steps):
        """steps: mỗi phần tử là list chunk (stream) hoặc một Exception sẽ được ném khi gọi API."""
        steps = list(steps)

        class Completions:
            def create(self, **kw):
                step = steps.pop(0)
                if isinstance(step, Exception):
                    raise step
                return iter(step)

        c = make_client([])[0]
        c._client = NS(chat=NS(completions=Completions()))
        return c

    @staticmethod
    def _price(model, prompt=6000, completion=300):
        return CostTracker().record_turn(model, prompt, completion)["usd_cost"]

    def test_rounds_paid_before_a_network_error_stay_in_the_total(self):
        c = self._client([self._tool_round(), RuntimeError("network down")])
        with self.assertRaises(RuntimeError):
            c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a))
        paid = self._price(c.model)
        self.assertAlmostEqual(c.cost_tracker.cumulative_usd_cost, paid, places=9)       # vòng 1 đã trả tiền
        self.assertEqual(c.cost_tracker._inflight_usd, 0.0)

    def test_next_successful_turn_does_not_erase_the_failed_turn(self):
        c = self._client([self._tool_round(), RuntimeError("network down"), self._tool_round(), self._text_round()])
        with self.assertRaises(RuntimeError):
            c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a))
        c.chat_with_tools([{"role": "user", "content": "y"}], lambda n, a: ({}, a))
        self.assertAlmostEqual(c.cost_tracker.cumulative_usd_cost, 3 * self._price(c.model), places=9)      # 1 vòng của lượt hỏng + 2 vòng của lượt sau

    def test_round_limit_counts_all_six_paid_rounds(self):
        from src.llm.client import LLMRoundLimit
        c = self._client([self._tool_round() for _ in range(6)])
        with self.assertRaises(LLMRoundLimit):
            c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a))
        self.assertAlmostEqual(c.cost_tracker.cumulative_usd_cost, 6 * self._price(c.model), places=9)

    def test_hitting_the_cap_mid_turn_keeps_the_paid_rounds_in_the_total(self):
        c = self._client([self._tool_round(), self._text_round()])
        c.cost_tracker.set_hard_cap(0.5)                                                  # vòng 1 (~2,3 VND) vượt trần 0,5 VND
        with self.assertRaises(BudgetExceeded):
            c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a))
        self.assertAlmostEqual(c.cost_tracker.cumulative_usd_cost, self._price(c.model), places=9)

    def test_complete_json_charges_a_paid_response_even_when_the_json_is_broken(self):
        from src.llm.client import LLMUnavailable
        c = self._client([])
        bad = NS(usage=NS(prompt_tokens=6000, completion_tokens=300, completion_tokens_details=None),
                 choices=[NS(message=NS(content="không phải json {"))])
        c._client = NS(chat=NS(completions=NS(create=lambda **kw: bad)))
        with self.assertRaises(LLMUnavailable):
            c.complete_json([{"role": "user", "content": "x"}])
        self.assertAlmostEqual(c.cost_tracker.cumulative_usd_cost, self._price(c.model), places=9)      # đã trả tiền cho phản hồi hỏng

    def test_runner_spent_vnd_reports_the_failed_turn(self):
        from src.eval.runner import spent_vnd
        c = self._client([self._tool_round(), RuntimeError("network down")])
        with self.assertRaises(RuntimeError):
            c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a))
        self.assertGreater(spent_vnd(c), 0)


class StubLLM:
    """LLM giả đã khai báo trần: lượt 1 trả lời bình thường, lượt 2 chạm trần giữa chừng."""
    available = True

    def __init__(self):
        self.cost_tracker = CostTracker()
        self.n = 0

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        self.n += 1
        if self.n == 2:
            raise BudgetExceeded(11, 10)
        return "Dạ em nghe ạ.", [], {"prompt_tokens": 1, "completion_tokens": 1, "vnd_cost": 0.0}


class SeedLLM:
    available = True
    seed = 1

    def __init__(self):
        self.cost_tracker = CostTracker()

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        return "Dạ em nghe ạ.", [], {"prompt_tokens": 1, "completion_tokens": 1, "vnd_cost": 0.0}


class SharedClientSeedTest(unittest.TestCase):
    def test_run_all_sets_the_llm_seed_for_every_run_of_a_shared_client(self):
        from src.eval.runner import ScenarioRunner
        llm = SeedLLM()
        out = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        for seed in (42, 43, 44):
            ScenarioRunner(PUBLIC_DIR).run_all(config="full", output_trace_file=out, only=["SAMPLE-07"], seed=seed, llm_client=llm)
            self.assertEqual(llm.seed, seed)


class RunnerCapTest(unittest.TestCase):
    def test_orchestrator_and_runner_do_not_swallow_the_cap_and_the_pending_row_is_flushed(self):
        from src.eval.runner import ScenarioRunner
        out = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        with self.assertRaises(BudgetExceeded):
            ScenarioRunner(PUBLIC_DIR).run_all(config="full", output_trace_file=out, only=["SAMPLE-01"], llm_client=StubLLM())
        rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
        self.assertEqual(len(rows), 1)                             # lượt 1 đã chạy xong được ghi; lượt 2 bị chặn giữa chừng

    def test_run_eval_has_a_default_hard_cap_and_refuses_non_positive(self):
        import run_eval
        self.assertGreater(run_eval.DEFAULT_MAX_COST_VND, 0)
        self.assertEqual(run_eval.main(["--config", "full", "--only", "SAMPLE-01", "--out", os.path.join(tempfile.mkdtemp(), "x.jsonl"), "--max-cost-vnd", "-5"]), 2)


if __name__ == "__main__":
    unittest.main()
