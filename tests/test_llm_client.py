"""Bước 2 — LLMClient stream + số đo thật (B1, N3). Dùng client OpenAI GIẢ, không gọi mạng."""
import unittest
from types import SimpleNamespace as NS
from tests import _helpers  # noqa: F401
from src.llm.client import LLMClient


def _tc_delta(index, id=None, name=None, arguments=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=arguments))


def _chunk(content=None, tool_calls=None, usage=None, with_choice=True):
    choices = [NS(delta=NS(content=content, tool_calls=tool_calls))] if with_choice else []
    return NS(choices=choices, usage=usage)


class FakeCompletions:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.rounds.pop(0))


def make_client(rounds, **kw):
    c = LLMClient(**kw)
    fake = FakeCompletions(rounds)
    c._client = NS(chat=NS(completions=fake))
    c.available = True
    return c, fake


class LLMClientStreamTest(unittest.TestCase):
    def test_tool_call_assembled_from_stream_and_executed_args_logged(self):
        rounds = [
            [  # vòng 1: tool call bị cắt thành nhiều delta
                _chunk(tool_calls=[_tc_delta(0, id="call_1", name="inventory__check", arguments="")]),
                _chunk(tool_calls=[_tc_delta(0, arguments='{"sku": "SKU-')]),
                _chunk(tool_calls=[_tc_delta(0, arguments='AP-Y"}')]),
                _chunk(with_choice=False, usage=NS(prompt_tokens=100, completion_tokens=10)),
            ],
            [  # vòng 2: câu trả lời cuối
                _chunk(content="Dạ "), _chunk(content="còn hàng ạ."),
                _chunk(with_choice=False, usage=NS(prompt_tokens=150, completion_tokens=8)),
            ],
        ]
        client, fake = make_client(rounds, temperature=0, seed=7)
        seen = {}

        def executor(name, args):
            seen["args"] = args
            return {"in_stock": True}, {**args, "on": "2026-10-17"}  # tham số THỰC SỰ đã chạy

        timing = {}
        text, log, cost = client.chat_with_tools([{"role": "user", "content": "còn hàng không"}], executor, timing=timing)

        self.assertEqual(text, "Dạ còn hàng ạ.")
        self.assertEqual(seen["args"], {"sku": "SKU-AP-Y"})
        self.assertEqual(log[0]["name"], "inventory.check")            # '__' -> '.'
        self.assertEqual(log[0]["args"], {"sku": "SKU-AP-Y", "on": "2026-10-17"})  # N3
        self.assertEqual(cost["prompt_tokens"], 250)
        self.assertEqual(cost["completion_tokens"], 18)
        self.assertEqual(cost["llm_calls"], 2)
        self.assertEqual(timing["llm_calls"], 2)
        self.assertLessEqual(timing["ttft_ms"], timing["total_ms"])
        self.assertTrue(all(k["stream"] is True and k["temperature"] == 0 and k["seed"] == 7 for k in fake.calls))
        self.assertTrue(all(k["stream_options"] == {"include_usage": True} for k in fake.calls))

    def test_no_tool_first_round_gets_nudged_once(self):
        rounds = [
            [_chunk(content="Để em kiểm tra."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))],
            [_chunk(content="Dạ xong ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=20, completion_tokens=3))],
        ]
        client, fake = make_client(rounds)
        text, log, cost = client.chat_with_tools([{"role": "user", "content": "alo"}], lambda n, a: ({}, a))
        self.assertEqual(text, "Dạ xong ạ.")
        self.assertEqual(cost["llm_calls"], 2)
        self.assertEqual(len(fake.calls), 2)

    def test_unavailable_raises(self):
        from src.llm.client import LLMUnavailable
        c = LLMClient()
        c.available = False
        with self.assertRaises(LLMUnavailable):
            c.chat_with_tools([], lambda n, a: ({}, a))


class MeasureLatencyTest(unittest.TestCase):
    def test_no_llm_ttft_equals_total(self):
        from src.tracing.tracer import measure_latency
        lat = measure_latency(10.0, 10.25, None)
        self.assertEqual(lat, {"ttft_ms": 250, "total_ms": 250})

    def test_llm_ttft_includes_pre_llm_time_and_is_capped(self):
        from src.tracing.tracer import measure_latency
        lat = measure_latency(10.0, 12.0, {"started_at": 10.1, "ttft_ms": 600, "total_ms": 1800})
        self.assertEqual(lat, {"ttft_ms": 700, "total_ms": 2000})


class RaisingThenOk:
    """Client giả: lần gọi đầu ném lỗi 'unsupported parameter', các lần sau trả stream."""
    def __init__(self, error, rounds):
        self.error, self.rounds, self.calls = error, list(rounds), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1 and self.error:
            raise self.error
        return iter(self.rounds.pop(0))


class ApiError(Exception):
    def __init__(self, message, param=None):
        super().__init__(message)
        self.param = param


def _final_text_round(text="Dạ ok ạ.", usage=None):
    return [_chunk(content=text), _chunk(with_choice=False, usage=usage or NS(prompt_tokens=5, completion_tokens=2))]


class MultiProviderTest(unittest.TestCase):  # bước 2b
    def test_profiles(self):
        from src.llm.model_profiles import profile_for
        self.assertTrue(profile_for("gpt-4o-mini").supports_temperature)
        self.assertEqual(profile_for("gpt-4o-mini").token_param, "max_tokens")
        luna = profile_for("gpt-6-luna")
        self.assertFalse(luna.supports_temperature)
        self.assertEqual(luna.token_param, "max_completion_tokens")
        self.assertTrue(luna.is_reasoning)
        self.assertFalse(profile_for("o3-mini").supports_temperature)

    def test_temperature_dropped_up_front_for_reasoning_model(self):
        client, fake = make_client([_final_text_round(), _final_text_round()], model="gpt-6-luna", temperature=0, seed=3, max_output_tokens=900)
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        sent = fake.calls[0]
        self.assertNotIn("temperature", sent)
        self.assertNotIn("max_tokens", sent)
        self.assertEqual(sent["max_completion_tokens"], 900)
        self.assertEqual(sent["seed"], 3)

    def test_chat_model_keeps_temperature_and_max_tokens(self):
        client, fake = make_client([_final_text_round(), _final_text_round()], model="gpt-4o-mini", temperature=0, max_output_tokens=500)
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertEqual(fake.calls[0]["temperature"], 0)
        self.assertEqual(fake.calls[0]["max_tokens"], 500)

    def test_unknown_model_learns_unsupported_param_and_retries(self):
        client = LLMClient(model="vendor-x-1", temperature=0.2, seed=5)
        fake = RaisingThenOk(ApiError("Unsupported parameter: 'temperature' is not supported with this model.", param="temperature"),
                             [_final_text_round(), _final_text_round()])
        client._client = NS(chat=NS(completions=fake))
        client.available = True
        text, _, _ = client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertEqual(text, "Dạ ok ạ.")
        self.assertEqual(len(fake.calls), 3)  # lỗi + thử lại + 1 lần nhắc gọi tool
        self.assertIn("temperature", fake.calls[0])
        self.assertNotIn("temperature", fake.calls[1])
        self.assertIn("temperature", client.dropped_params)

    def test_error_message_without_param_attr_is_parsed(self):
        client = LLMClient(model="vendor-x-1", seed=5)
        fake = RaisingThenOk(Exception("Unsupported value: 'seed' does not support 5 with this model."), [_final_text_round(), _final_text_round()])
        client._client = NS(chat=NS(completions=fake))
        client.available = True
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertNotIn("seed", fake.calls[1])

    def test_max_tokens_rejected_switches_to_max_completion_tokens(self):
        client = LLMClient(model="vendor-x-1", max_output_tokens=300)
        fake = RaisingThenOk(ApiError("Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens'.", param="max_tokens"),
                             [_final_text_round(), _final_text_round()])
        client._client = NS(chat=NS(completions=fake))
        client.available = True
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertNotIn("max_tokens", fake.calls[1])
        self.assertEqual(fake.calls[1]["max_completion_tokens"], 300)

    def test_other_errors_are_raised(self):
        client = LLMClient(model="gpt-4o-mini")
        fake = RaisingThenOk(Exception("Rate limit reached"), [_final_text_round(), _final_text_round()])
        client._client = NS(chat=NS(completions=fake))
        client.available = True
        with self.assertRaises(Exception):
            client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))

    def test_reasoning_tokens_recorded(self):
        usage = NS(prompt_tokens=100, completion_tokens=400, completion_tokens_details=NS(reasoning_tokens=350))
        client, _ = make_client([_final_text_round(usage=usage), _final_text_round()], model="gpt-6-luna")
        _, _, cost = client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertEqual(cost["reasoning_tokens"], 350)
        self.assertEqual(cost["completion_tokens"], 402)  # 2 vòng (có 1 lần nhắc gọi tool)

    def test_judge_must_differ_from_agent(self):
        from src.llm.model_profiles import assert_distinct_judge, JudgeModelConflict
        with self.assertRaises(JudgeModelConflict):
            assert_distinct_judge("gpt-4o-mini", "GPT-4o-mini")
        with self.assertRaises(JudgeModelConflict):
            assert_distinct_judge("gpt-4o", "gpt-4o-2024-08-06")
        assert_distinct_judge("gpt-4o-mini", "gpt-6-luna")  # không ném lỗi


class PricingAndEffortTest(unittest.TestCase):  # giá judge + reasoning_effort (bước 14b nền)
    def test_pricing_file_has_luna_flagged_for_verification(self):
        from src.llm.cost_tracker import load_pricing
        t = load_pricing()
        inp, out, needs, source = t["models"]["gpt-6-luna"]
        self.assertEqual((inp, out), (0.10, 0.50))
        self.assertTrue(needs)                                   # cần đối chiếu giá OpenAI chính thức
        self.assertIn("OpenRouter", source)
        self.assertIn("2026-10-20", source)

    def test_cost_uses_per_million_prices_and_marks_unverified(self):
        from src.llm.cost_tracker import CostTracker
        c = CostTracker().record_turn("gpt-6-luna", 1_000_000, 1_000_000)
        self.assertAlmostEqual(c["usd_cost"], 0.60, places=6)     # 0.10 + 0.50
        self.assertFalse(c["pricing_verified"])
        c2 = CostTracker().record_turn("gpt-4o-mini", 1_000_000, 1_000_000)
        self.assertAlmostEqual(c2["usd_cost"], 0.75, places=6)    # 0.15 + 0.60
        self.assertTrue(c2["pricing_verified"])

    def test_dated_model_name_and_unknown_model(self):
        from src.llm.cost_tracker import CostTracker
        self.assertAlmostEqual(CostTracker().record_turn("gpt-4o-mini-2024-07-18", 1_000_000, 0)["usd_cost"], 0.15, places=6)
        unknown = CostTracker().record_turn("vendor-zzz", 1_000_000, 0)
        self.assertFalse(unknown["pricing_verified"])

    def test_missing_pricing_file_falls_back(self):
        from src.llm.cost_tracker import load_pricing
        t = load_pricing("khong_ton_tai.yaml")
        self.assertIn("gpt-6-luna", t["models"])

    def test_reasoning_effort_only_for_reasoning_models_and_dropped_on_reject(self):
        client, fake = make_client([_final_text_round(), _final_text_round()], model="gpt-6-luna", reasoning_effort="low", seed=1)
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertEqual(fake.calls[0]["reasoning_effort"], "low")
        self.assertEqual(fake.calls[0]["seed"], 1)
        self.assertNotIn("temperature", fake.calls[0])
        client2, fake2 = make_client([_final_text_round(), _final_text_round()], model="gpt-4o-mini", reasoning_effort="low")
        client2.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertNotIn("reasoning_effort", fake2.calls[0])
        c3 = LLMClient(model="gpt-6-luna", reasoning_effort="high")
        f3 = RaisingThenOk(ApiError("Unsupported parameter: 'reasoning_effort'", param="reasoning_effort"), [_final_text_round(), _final_text_round()])
        c3._client = NS(chat=NS(completions=f3))
        c3.available = True
        c3.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a))
        self.assertNotIn("reasoning_effort", f3.calls[1])


class LatencyBreakdownAndCacheTest(unittest.TestCase):
    """3(b): đo số vòng LLM trước token đầu tiên, thời gian tool, và token prompt được cache."""

    def test_timing_breakdown_with_one_tool_round(self):
        rounds = [
            [_chunk(tool_calls=[_tc_delta(0, id="c1", name="inventory__check", arguments='{"sku": "SKU-AP-Y"}')]),
             _chunk(with_choice=False, usage=NS(prompt_tokens=2000, completion_tokens=10,
                                                 prompt_tokens_details=NS(cached_tokens=0)))],
            [_chunk(content="Dạ còn hàng ạ."),
             _chunk(with_choice=False, usage=NS(prompt_tokens=2100, completion_tokens=8,
                                                 prompt_tokens_details=NS(cached_tokens=1536)))],
        ]
        client, _ = make_client(rounds)
        timing = {}
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({"in_stock": True}, a), timing=timing)
        self.assertEqual(timing["rounds_before_first_token"], 1)
        self.assertEqual(len(timing["round_ms"]), 2)
        self.assertIn("tool_ms", timing)
        self.assertLessEqual(timing["final_round_ttft_ms"], timing["ttft_ms"])
        self.assertEqual((timing["prompt_tokens"], timing["cached_tokens"]), (4100, 1536))

    def test_no_tool_round_means_zero_rounds_before_first_token(self):
        client, _ = make_client([[_chunk(content="Dạ chào ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))],
                                 [_chunk(content="Dạ chào ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))]])
        timing = {}
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing)
        self.assertEqual(timing["rounds_before_first_token"], 1)           # mặc định: 1 lần nhắc gọi tool (nudge) trước câu trả lời cuối
        client, _ = make_client([[_chunk(content="Dạ chào ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))]])
        timing = {}
        client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing, expect_tools=False)
        self.assertEqual(timing["rounds_before_first_token"], 0)           # dữ liệu đã tra sẵn (expect_tools=False): trả lời thẳng, không tốn vòng nhắc

    def test_promise_to_look_up_without_a_tool_call_is_nudged_once(self):
        """Agent nói "để em kiểm tra" mà không gọi tool → kể cả khi dữ liệu đã tra sẵn (expect_tools=False) vẫn nhắc đúng MỘT lần."""
        promise = [_chunk(content="Dạ để em kiểm tra giúp chị ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))]
        final = [_chunk(content="Dạ còn hàng ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))]
        client, _ = make_client([promise, final])
        timing = {}
        text, _, _ = client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing, expect_tools=False)
        self.assertEqual((text, timing["rounds_before_first_token"]), ("Dạ còn hàng ạ.", 1))

    def test_cached_tokens_are_priced_at_cached_rate(self):
        from src.llm.cost_tracker import CostTracker
        plain = CostTracker().record_turn("gpt-4o-mini", 2_000_000, 0)
        cached = CostTracker().record_turn("gpt-4o-mini", 2_000_000, 0, cached_tokens=1_000_000)
        self.assertAlmostEqual(plain["usd_cost"], 0.30, places=6)
        self.assertAlmostEqual(cached["usd_cost"], 0.15 + 0.075, places=6)   # 1M giá thường + 1M giá cache
        self.assertEqual(cached["cached_tokens"], 1_000_000)

    def test_cached_tokens_never_exceed_prompt(self):
        from src.llm.cost_tracker import CostTracker
        c = CostTracker().record_turn("gpt-4o-mini", 100, 0, cached_tokens=999)
        self.assertEqual(c["cached_tokens"], 100)


class CompleteJsonTest(unittest.TestCase):  # bộ trích slot khó (bước 9) gọi LLM qua complete_json
    @staticmethod
    def _response(content, prompt=40, completion=12, reasoning=0):
        usage = NS(prompt_tokens=prompt, completion_tokens=completion, completion_tokens_details=NS(reasoning_tokens=reasoning))
        return NS(choices=[NS(message=NS(content=content))], usage=usage)

    class _Completions:
        def __init__(self, responses):
            self.responses, self.calls = list(responses), []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    def _client(self, responses, **kw):
        c = LLMClient(**kw)
        fake = self._Completions(responses)
        c._client = NS(chat=NS(completions=fake))
        c.available = True
        return c, fake

    def test_returns_parsed_dict_and_cost_non_stream_json_mode(self):
        c, fake = self._client([self._response('{"blocker": "can hoi chong"}', reasoning=5)], model="gpt-6-luna", seed=1)
        data, cost = c.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(data, {"blocker": "can hoi chong"})
        self.assertEqual((cost["prompt_tokens"], cost["completion_tokens"], cost["reasoning_tokens"], cost["llm_calls"]), (40, 12, 5, 1))
        sent = fake.calls[0]
        self.assertNotIn("stream", sent)
        self.assertNotIn("temperature", sent)
        self.assertEqual(sent["response_format"], {"type": "json_object"})
        self.assertNotIn("tools", sent)

    def test_unsupported_response_format_is_dropped_and_retried(self):
        c, fake = self._client([ApiError("Unsupported parameter: 'response_format'", param="response_format"), self._response("{}")], model="vendor-x-1")
        data, _ = c.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual(data, {})
        self.assertIn("response_format", fake.calls[0])
        self.assertNotIn("response_format", fake.calls[1])

    def test_bad_json_or_non_object_raises_llm_unavailable(self):
        from src.llm.client import LLMUnavailable
        for bad in ("not json", "[1, 2]"):
            c, _ = self._client([self._response(bad)])
            with self.assertRaises(LLMUnavailable):
                c.complete_json([{"role": "user", "content": "x"}])

    def test_network_error_raises_llm_unavailable(self):
        from src.llm.client import LLMUnavailable
        c, _ = self._client([RuntimeError("down")])
        with self.assertRaises(LLMUnavailable):
            c.complete_json([{"role": "user", "content": "x"}])

    def test_unavailable_client(self):
        from src.llm.client import LLMUnavailable
        c = LLMClient()
        c.available = False
        with self.assertRaises(LLMUnavailable):
            c.complete_json([])


class StripInternalTest(unittest.TestCase):  # N15
    def test_recursive_strip_returns_copy(self):
        from src.tools.mcp_gateway import strip_internal
        src = {"final_price_vnd": 1, "_internal_price_floor_vnd": 2, "items": [{"sku": "A", "_note": "x"}], "n": {"_a": 1, "b": 2}}
        out = strip_internal(src)
        self.assertEqual(out, {"final_price_vnd": 1, "items": [{"sku": "A"}], "n": {"b": 2}})
        self.assertIn("_internal_price_floor_vnd", src)  # bản gốc không bị sửa

    def test_gateway_results_and_audit_have_no_internal_fields(self):
        from src.tools.mcp_gateway import MCPToolGateway, CRMTool, CatalogPricingTool, OrderCallbackTool
        gw = MCPToolGateway(CRMTool(), CatalogPricingTool(), OrderCallbackTool())
        res = gw.execute_tool("pricing.get_quote", {"sku": "SKU-AP-Y", "on": "2026-10-15"}, caller="HarnessOrchestrator")
        self.assertFalse([k for k in res if k.startswith("_")])
        self.assertNotIn("_internal", str(gw.audit_log))

    def test_llm_branch_trace_has_no_internal_fields(self):
        from tests._helpers import build_components
        from tests.test_orchestrator import FakeLLM
        from src.channels.normalizer import InputChannel
        c = build_components()
        orch = c["orchestrator"]
        orch.llm_client = FakeLLM({"calls": [("pricing.get_quote", {"sku": "SKU-AP-Y"})], "text": "Dạ giá 5.200.000đ ạ."})
        t = c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0984726714")
        b = c["brief"].build(c["resolver"].resolve(t), "2026-10-15")
        _, tool_calls, _ = orch.process_turn(t, b, current_date="2026-10-15")
        self.assertNotIn("_internal", str(tool_calls))


if __name__ == "__main__":
    unittest.main()


class HedgeAndLazyNudgeTest(unittest.TestCase):
    """Sửa độ trễ 2026-11-13: hedged request (gửi bản sao khi chưa có gói đầu) và quyết định vòng nhắc lúc vòng đầu xong."""

    def _slow_then_fast(self, delays):
        import time as _t

        class Stream:
            def __init__(self, delay, text):
                self.delay, self.text, self.closed = delay, text, False

            def __iter__(self):
                _t.sleep(self.delay)
                yield _chunk(content=self.text)
                yield _chunk(with_choice=False, usage=NS(prompt_tokens=100, completion_tokens=5))

            def close(self):
                self.closed = True
        made = []

        def create(**kw):
            s = Stream(*delays[len(made)])
            made.append(s)
            return s
        c = LLMClient()
        c._client = NS(chat=NS(completions=NS(create=create)))
        c.available = True
        return c, made

    def test_hedge_uses_whichever_first_chunk_arrives_first_and_bills_the_copy(self):
        c, made = self._slow_then_fast([(0.6, "chậm"), (0.0, "nhanh")])
        c.hedge_ms = 50
        timing = {}
        text, _, cost = c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing, expect_tools=False)
        self.assertEqual(text, "nhanh")
        self.assertEqual(len(made), 2)
        self.assertEqual(timing["hedged_rounds"], 1)
        self.assertEqual(cost["prompt_tokens"], 200)            # bản sao bị đóng vẫn tính tiền prompt

    def test_no_hedge_when_first_chunk_is_fast_or_hedging_off(self):
        for hedge in (500, 0):
            c, made = self._slow_then_fast([(0.0, "một")])
            c.hedge_ms = hedge
            timing = {}
            text, _, _ = c.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing, expect_tools=False)
            self.assertEqual((text, len(made), timing["hedged_rounds"]), ("một", 1, 0))

    def test_expect_tools_callable_is_asked_only_when_first_round_has_no_tool(self):
        rounds = [[_chunk(content="Dạ vâng ạ."), _chunk(with_choice=False, usage=NS(prompt_tokens=10, completion_tokens=3))]]
        client, fake = make_client(rounds)
        asked = []
        timing = {}
        text, _, _ = client.chat_with_tools([{"role": "user", "content": "x"}], lambda n, a: ({}, a), timing=timing,
                                            expect_tools=lambda: asked.append(1) or False)
        self.assertEqual((text, len(fake.calls), len(asked), timing["nudged"]), ("Dạ vâng ạ.", 1, 1, False))


class ReadingNeedsNothingTest(unittest.TestCase):
    def test_only_a_reading_with_no_request_skips_the_nudge(self):
        from src.harness.orchestrator import reading_needs_nothing
        from src.harness.reply_reader import ReplyReading
        self.assertFalse(reading_needs_nothing(None))
        self.assertTrue(reading_needs_nothing(ReplyReading()))
        for kw in ({"asks_question": True}, {"price_topic": True}, {"commits": True}, {"asks_transfer": True}, {"stance": "agree"},
                   {"product_sku": "SKU-AP-X"}, {"qty": 2}, {"address": "12 Lê Lợi"}, {"affirmed": ["recipient_phone"]}):
            self.assertFalse(reading_needs_nothing(ReplyReading(**kw)), kw)


class JsonHedgeTest(unittest.TestCase):
    def test_slow_json_call_is_hedged_and_loser_is_billed(self):
        import time as _t
        delays = [0.5, 0.0]
        made = []

        def create(**kw):
            d = delays[len(made)]
            made.append(d)
            _t.sleep(d)
            return NS(usage=NS(prompt_tokens=1000, completion_tokens=100, completion_tokens_details=None),
                      choices=[NS(message=NS(content='{"who": %d}' % (len(made) - 1)))])
        c = LLMClient()
        c._client = NS(chat=NS(completions=NS(create=create)))
        c.available = True
        c.json_hedge_ms = 50
        before = c.cost_tracker.cumulative_usd_cost
        data, cost = c.complete_json([{"role": "user", "content": "x"}])
        self.assertEqual((data, len(made), c.json_hedged_calls), ({"who": 1}, 2, 1))     # bản sao (nhanh) thắng
        _t.sleep(0.7)                                                                      # bản thua chạy xong → tiền được cộng
        self.assertGreater(c.cost_tracker.cumulative_usd_cost - before, cost["usd_cost"] * 1.5)


class JsonTruncationTest(unittest.TestCase):
    def test_truncated_json_is_unreadable_and_reader_gets_the_cap(self):
        from src.llm.client import LLMUnavailable
        from src.harness import reply_reader as RR
        sent = []

        def create(**kw):
            sent.append(kw)
            return NS(usage=NS(prompt_tokens=10, completion_tokens=5, completion_tokens_details=None),
                      choices=[NS(finish_reason="length", message=NS(content='{"stance":"agr'))])
        c = LLMClient()
        c._client = NS(chat=NS(completions=NS(create=create)))
        c.available = True
        with self.assertRaises(LLMUnavailable):
            c.complete_json([{"role": "user", "content": "x"}], max_tokens=5)
        self.assertIsNone(RR.read_reply(c, "ok lấy luôn", "Anh lấy không ạ?"))          # bị cắt → không đọc được, không đoán
        self.assertEqual(sent[-1][c._token_param], RR.READER_MAX_TOKENS)
