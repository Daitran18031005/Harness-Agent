import unittest
from tests import _helpers  # noqa: F401


class EnvironmentTest(unittest.TestCase):
    def test_check_environment_reports_backend(self):
        from src.env_check import check_environment
        report = check_environment()
        self.assertIn("rag_backend", report)
        self.assertIn("problems", report)

    def test_tfidf_backend_available(self):
        """Chạy bằng nlp_env phải có TF-IDF (N12) — nếu đỏ là đang chạy sai Python."""
        from src.memory.vector_rag import get_vector_backend, TfidfBackend
        self.assertIsInstance(get_vector_backend(), TfidfBackend)


if __name__ == "__main__":
    unittest.main()
