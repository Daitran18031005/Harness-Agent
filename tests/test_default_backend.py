"""Mặc định từ 18/11 (số nộp m1_final8): VECTOR_BACKEND để trống → reranker khi máy chạy được (GPU + model trong cache) và bỏ router;
không chạy được → TF-IDF + router LLM (cấu hình m1_final7). Không nạp model thật."""
import os
import unittest
from unittest import mock

from src.memory import vector_rag as V
from src.memory.policy_router import PolicyRouter


class _LLM:
    available = True

    def complete_json(self, *a, **k):
        return {}


class DefaultBackendTest(unittest.TestCase):
    def _pick(self, ready):
        env = {k: v for k, v in os.environ.items() if k not in ("VECTOR_BACKEND", "POLICY_NO_ROUTER", "POLICY_ROUTER")}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(V, "_rerank_ready", return_value=ready):
            backend = V.get_vector_backend()
            return backend, V.reranker_active(), PolicyRouter(llm=_LLM())._client()

    def test_reranker_when_machine_can_run_it_and_router_skipped(self):
        backend, active, router = self._pick(True)
        self.assertIsInstance(backend, V.QwenRerankBackend)
        self.assertTrue(active)
        self.assertIsNone(router)

    def test_falls_back_to_tfidf_and_keeps_router(self):
        backend, active, router = self._pick(False)
        self.assertIsInstance(backend, V.TfidfBackend)
        self.assertFalse(active)
        self.assertIsNotNone(router)

    def tearDown(self):
        V._RERANK_ACTIVE = False


if __name__ == "__main__":
    unittest.main()
