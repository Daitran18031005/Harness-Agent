"""Timeout + thử lại cuộc gọi LLM (CHECKING §11.95): lượt đứng 68–128 s ở run 4. Không gọi mạng thật."""
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from tests import _helpers  # noqa: F401
import httpx
import openai

from src.llm.client import LLMClient
from src.llm.cost_tracker import BudgetExceeded

REQ = httpx.Request("POST", "http://x")


def chunk(text):
    return SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))])


class StreamRetryTest(unittest.TestCase):
    def setUp(self):
        self.c = LLMClient()                                   # OPENAI_API_KEY rỗng trong test → không có client thật
        p = mock.patch("src.llm.client.time.sleep")
        self.sleep = p.start()
        self.addCleanup(p.stop)

    def script(self, *attempts):
        """Mỗi phần tử: list gói dữ liệu, kết thúc bằng một exception (sẽ được ném giữa stream) hoặc không."""
        it = iter(attempts)
        self.calls = 0

        def create_stream(messages, tools):
            self.calls += 1
            for item in next(it):
                if isinstance(item, BaseException):
                    raise item
                yield item
        self.c._create_stream = create_stream

    def test_timeout_mid_stream_is_retried_and_the_partial_text_is_dropped(self):
        self.script([chunk("Dạ em "), openai.APITimeoutError(REQ)], [chunk("Dạ chào chị ạ.")])
        text, calls, _, _ = self.c._stream_round([], [])
        self.assertEqual((text, calls, self.calls), ("Dạ chào chị ạ.", [], 2))

    def test_connection_error_before_any_chunk_is_retried(self):
        self.script([openai.APIConnectionError(request=REQ)], [chunk("ok")])
        self.assertEqual(self.c._stream_round([], [])[0], "ok")

    def test_gives_up_after_the_configured_retries(self):
        self.c.stream_retries = 2
        self.script(*[[openai.APITimeoutError(REQ)]] * 3)
        with self.assertRaises(openai.APITimeoutError):
            self.c._stream_round([], [])
        self.assertEqual(self.calls, 3)

    def test_other_errors_are_not_retried(self):
        self.script([ValueError("lỗi khác")], [chunk("không bao giờ tới")])
        with self.assertRaises(ValueError):
            self.c._stream_round([], [])
        self.assertEqual(self.calls, 1)

    def test_budget_cap_is_never_retried(self):
        self.script([BudgetExceeded(100, 50)], [chunk("không bao giờ tới")])
        with self.assertRaises(BudgetExceeded):
            self.c._stream_round([], [])
        self.assertEqual(self.calls, 1)


class ClientConfigTest(unittest.TestCase):
    def build(self, **env):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", **env}), mock.patch("openai.OpenAI") as ctor:
            c = LLMClient()
        return c, ctor.call_args.kwargs

    def test_defaults_replace_the_sdk_600s_timeout(self):
        c, kw = self.build()
        self.assertEqual((kw["timeout"], kw["max_retries"], c.stream_retries), (20.0, 1, 2))

    def test_env_overrides(self):
        _, kw = self.build(LLM_TIMEOUT_S="45", LLM_API_RETRIES="0", LLM_STREAM_RETRIES="0")
        self.assertEqual((kw["timeout"], kw["max_retries"]), (45.0, 0))


if __name__ == "__main__":
    unittest.main()
