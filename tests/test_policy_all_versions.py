import os
import unittest
from unittest import mock


class PolicyAllVersionsTest(unittest.TestCase):
    """POLICY_ALL_VERSIONS (16/11): không router thì trả cả bản hết hiệu lực kèm thời gian hiệu lực để LLM chính chọn theo ngày mua."""

    def _search(self, flag):
        from src.memory import MemoryService
        svc = MemoryService(enable_persistence=False)
        svc.semantic.router = None
        env = {"POLICY_ALL_VERSIONS": "on"} if flag else {}
        with mock.patch.dict(os.environ, env, clear=False):
            if not flag:
                os.environ.pop("POLICY_ALL_VERSIONS", None)
            return svc.semantic.search("thời hạn đổi trả 14 ngày", on_date="2026-10-15", top_k=5)

    def test_on_returns_old_version_with_dates(self):
        out = self._search(True)
        self.assertTrue(all("effective_from" in c and "effective_to" in c for c in out))
        self.assertIn("[DT-OLD-01]", [c["chunk_id"] for c in out])

    def test_off_keeps_call_date_filter(self):
        out = self._search(False)
        self.assertNotIn("[DT-OLD-01]", [c["chunk_id"] for c in out])
        self.assertTrue(all("effective_from" not in c for c in out))
