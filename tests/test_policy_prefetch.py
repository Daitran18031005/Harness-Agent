import os
import unittest
from concurrent.futures import Future
from unittest import mock


class _Scored:
    """Backend giả chấm điểm: đoạn chứa 'đổi trả' điểm 0,95, còn lại 0,2."""
    def rank(self, query, candidates, top_k=3):
        return [c for _, c in self.rank_scored(query, candidates, top_k)]

    def rank_scored(self, query, candidates, top_k=3):
        return sorted(((0.95 if "đổi" in c.content.lower() else 0.2, c) for c in candidates), key=lambda x: -x[0])[:top_k]


class PolicyPrefetchTest(unittest.TestCase):
    def _svc(self, backend):
        with mock.patch("src.memory.vector_rag.get_vector_backend", return_value=backend):
            from src.memory import MemoryService
            return MemoryService(enable_persistence=False)

    def test_prefetch_returns_scored_current_chunks(self):
        svc = self._svc(_Scored())
        with mock.patch.dict(os.environ, {"POLICY_ALL_VERSIONS": "off"}):
            out = svc.prefetch_policy("máy mới mua bị lỗi có đổi được không", "2026-10-15")
        self.assertTrue(out and all("score" in c for c in out))
        self.assertNotIn("[DT-OLD-01]", [c["chunk_id"] for c in out])

    def test_backend_without_scores_gives_nothing(self):
        class Plain:
            def rank(self, query, candidates, top_k=3):
                return candidates[:top_k]
        self.assertEqual(self._svc(Plain()).prefetch_policy("đổi trả", "2026-10-15"), [])

    def test_orchestrator_keeps_only_chunks_above_threshold(self):
        from src.harness.orchestrator import HarnessOrchestrator as O
        f = Future(); f.set_result([{"chunk_id": "[DT-01]", "score": 0.95, "content": "x"}, {"chunk_id": "[VC-01]", "score": 0.3, "content": "y"}])
        out = O._prefetched_policy(f, "q")
        self.assertEqual([x["chunk_id"] for x in out[0]["result"]["chunks"]], ["[DT-01]"])
        self.assertTrue(out[0]["speculative"])
        f2 = Future(); f2.set_result([{"chunk_id": "[VC-01]", "score": 0.3, "content": "y"}])
        self.assertEqual(O._prefetched_policy(f2, "q"), [])
        self.assertEqual(O._prefetched_policy(Future(), "q"), [])      # chưa xong trong thời gian chờ → bỏ


class PolicyPrefetchRemoteTest(unittest.TestCase):
    def test_remote_memory_exposes_prefetch(self):
        """17/11: run_eval chạy bộ nhớ qua MCP (mcp-memory); thiếu tool này thì tra trước bị bỏ qua mà không báo (đo ab_polprefetch_1117: 0 lượt)."""
        from src.memory.remote import create_memory_service
        base = create_memory_service(enable_persistence=False, transport="inproc", caller="EvalRunner")
        for mem in (base, base.as_caller("HarnessOrchestrator")):
            self.assertTrue(hasattr(mem, "prefetch_policy"))
            self.assertIsInstance(mem.prefetch_policy("đổi trả trong bao lâu", "2026-10-15"), list)      # backend mặc định không chấm điểm → [] nhưng không lỗi quyền
