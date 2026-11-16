import unittest
from unittest import mock


class RagWarmTest(unittest.TestCase):
    def test_memory_service_warms_backend_with_public_chunks(self):
        """17/11: backend có warm() (Qwen) được gọi một lần với các đoạn public ngay khi nạp kho chính sách."""
        calls = []

        class Fake:
            def warm(self, chunks):
                calls.append(chunks)

            def rank(self, query, candidates, top_k=3):
                return candidates[:top_k]

        with mock.patch("src.memory.vector_rag.get_vector_backend", return_value=Fake()):
            from src.memory import MemoryService
            MemoryService(enable_persistence=False)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0] and all(c.access == "public" for c in calls[0]))
