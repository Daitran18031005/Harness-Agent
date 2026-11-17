import os
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from src.harness import reply_reader as rr


class ReaderModelTest(unittest.TestCase):
    """READER_MODEL (17/11): bộ đọc chạy model riêng, dùng chung sổ chi phí của LLM chính; trống thì dùng chính LLM được truyền vào."""

    def test_unset_uses_main_llm(self):
        main = NS(model="gpt-5.4-mini", cost_tracker=object())
        with mock.patch.dict(os.environ, {"READER_MODEL": ""}):
            self.assertIs(rr._reader_llm(main), main)

    def test_set_uses_separate_client_sharing_tracker(self):
        main = NS(model="gpt-5.4-mini", cost_tracker=object())
        with mock.patch.dict(os.environ, {"READER_MODEL": "gpt-4o-mini"}):
            r = rr._reader_llm(main)
            self.assertEqual(r.model, "gpt-4o-mini")
            self.assertIs(r.cost_tracker, main.cost_tracker)
            self.assertIs(rr._reader_llm(main), r)
