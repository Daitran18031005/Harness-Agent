"""Kiểm tra môi trường lúc khởi động (N12): báo RÕ khi thiếu thư viện khiến hệ thống tự hạ
cấp âm thầm (vd thiếu scikit-learn -> RAG rơi về so khớp chuỗi, Recall@k đo được không còn đúng)."""
import os
import sys
import logging
from typing import Dict, Any

logger = logging.getLogger("harness.env")


def check_environment() -> Dict[str, Any]:
    problems = []
    try:
        import sklearn  # noqa: F401
        rag_backend = "tfidf"
    except ImportError:
        rag_backend = "substring"
        problems.append("Thiếu scikit-learn: RAG chính sách đang chạy so khớp chuỗi (kém hơn TF-IDF). "
                        "Hãy chạy bằng conda env nlp_env hoặc `pip install -r requirements.txt`.")
    if os.environ.get("VECTOR_BACKEND", "tfidf").strip().lower() == "chroma":
        problems.append("VECTOR_BACKEND=chroma chỉ là stub — vẫn dùng TF-IDF.")
    if not os.environ.get("OPENAI_API_KEY"):
        problems.append("OPENAI_API_KEY trống: LLM tắt, hệ thống chạy nhánh rule-based tối giản.")
    return {"python": sys.version.split()[0], "executable": sys.executable,
            "rag_backend": rag_backend, "problems": problems}


def log_environment() -> Dict[str, Any]:
    report = check_environment()
    for p in report["problems"]:
        logger.warning("[ENV] %s", p)
    return report
