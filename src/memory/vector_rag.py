"""
Vector Backend cho Semantic/KB Memory — kiến trúc swappable qua biến môi trường VECTOR_BACKEND.
Mặc định (quyết định đã chốt): "tfidf" — TF-IDF/cosine nội bộ (scikit-learn), chạy 100% offline,
không tải model ngoài. "chroma" là backend dự phòng dùng ChromaDB + embedding model (chưa wire sâu,
chỉ chứng minh kiến trúc swap-được mà không cần sửa caller).
[INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE] — nửa vector-store của integration point này.
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .semantic_rag import PolicyChunk

logger = logging.getLogger("harness.memory")


class VectorBackend(ABC):
    @abstractmethod
    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        ...


class SubstringBackend(VectorBackend):
    """Fallback cuối cùng: logic substring/word-overlap thuần, không cần thư viện ngoài."""

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        q_lower = query.lower()
        words = q_lower.split()
        scored = []
        for c in candidates:
            text = (c.content + " " + c.chunk_id).lower()
            score = sum(1 for w in words if w in text)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]


class TfidfBackend(VectorBackend):
    """TF-IDF char n-gram (2-4) + cosine similarity — không cần word-segmentation tiếng Việt."""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vectorizer_cls = TfidfVectorizer

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        if not candidates:
            return []
        from sklearn.metrics.pairwise import cosine_similarity
        corpus = [c.content.lower() for c in candidates] + [query.lower()]
        vectorizer = self._vectorizer_cls(analyzer="char_wb", ngram_range=(2, 4))
        try:
            matrix = vectorizer.fit_transform(corpus)
        except ValueError:
            # corpus rỗng/toàn stopword biên -> fallback substring
            return SubstringBackend().rank(query, candidates, top_k)
        query_vec = matrix[-1]
        doc_vecs = matrix[:-1]
        sims = cosine_similarity(query_vec, doc_vecs)[0]
        ranked = sorted(zip(sims, candidates), key=lambda x: -x[0])
        return [c for score, c in ranked[:top_k] if score > 0]


class ChromaBackend(VectorBackend):
    """Stub ChromaDB + embedding model — chọn qua VECTOR_BACKEND=chroma. Chưa wire sâu theo quyết
    định của người dùng: TF-IDF là backend chính thức hiện tại, đây chỉ chứng minh interface swap được."""

    def __init__(self):
        import chromadb  # noqa: F401 — chỉ để xác nhận có thể import, chưa dùng sâu
        self._client = chromadb.Client()
        self._collection = None

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        # Chưa triển khai embedding thật — rơi về TF-IDF để không phá chức năng.
        logger.info("[RAG] ChromaBackend chưa triển khai đầy đủ — dùng TfidfBackend cho lần rank này.")
        return TfidfBackend().rank(query, candidates, top_k)


def get_vector_backend() -> VectorBackend:
    choice = os.environ.get("VECTOR_BACKEND", "tfidf").strip().lower()
    if choice == "chroma":
        try:
            return ChromaBackend()
        except Exception as e:
            logger.warning("[RAG] VECTOR_BACKEND=chroma unavailable (%s) — falling back to tfidf.", e)
    try:
        return TfidfBackend()
    except Exception as e:
        # ERROR (không phải warning): hạ cấp này làm sai số liệu RAG đã công bố — xem src/env_check.py.
        logger.error("[RAG] scikit-learn unavailable (%s) — falling back to keyword/substring matching. "
                     "Chạy bằng conda env nlp_env hoặc cài requirements.txt.", e)
        return SubstringBackend()
