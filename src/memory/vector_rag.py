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


class Bm25Backend(VectorBackend):
    """BM25 trên từ đã bỏ dấu (khách/teencode không dấu vẫn khớp) + cặp từ liền nhau. Thuần Python, không tải model."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b

    @staticmethod
    def _terms(text: str) -> List[str]:
        import re
        from src.harness.fact_usage import fold
        words = re.findall(r"\w+", fold(text))
        return words + [a + "_" + b for a, b in zip(words, words[1:])]

    def scores(self, query: str, candidates: List["PolicyChunk"]) -> List[float]:
        import math
        from collections import Counter
        docs = [Counter(self._terms(c.content + " " + c.doc_name)) for c in candidates]
        n = len(docs)
        avg = sum(sum(d.values()) for d in docs) / max(1, n)
        df = Counter(t for d in docs for t in d)
        out = []
        for d in docs:
            dl = sum(d.values())
            out.append(sum(math.log(1 + (n - df[t] + .5) / (df[t] + .5)) * d[t] * (self.k1 + 1) / (d[t] + self.k1 * (1 - self.b + self.b * dl / avg))
                           for t in set(self._terms(query)) if d[t]))
        return out

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        ranked = sorted(zip(self.scores(query, candidates), candidates), key=lambda x: -x[0])
        return [c for s, c in ranked[:top_k] if s > 0]


class HybridBackend(VectorBackend):
    """Lai BM25 + TF-IDF char n-gram, gộp bằng Reciprocal Rank Fusion (k=60). VECTOR_BACKEND=hybrid, mặc định tắt."""

    def __init__(self):
        self.parts = [Bm25Backend(), TfidfBackend()]

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        fused = {}
        for part in self.parts:
            for i, c in enumerate(part.rank(query, candidates, top_k=len(candidates))):
                fused[id(c)] = (fused.get(id(c), (0.0, c))[0] + 1 / (60 + i), c)
        return [c for _, c in sorted(fused.values(), key=lambda x: -x[0])[:top_k]]


_QWEN = {}      # model nạp một lần mỗi tiến trình
_EMB_CACHE = {}  # vector tài liệu theo nội dung, dùng chung mọi kho chính sách trong tiến trình (kho được tạo lại mỗi cuộc gọi)


_QWEN_LOCK = __import__("threading").Lock()   # luồng nạp sẵn và lần tra đầu không nạp cùng một model hai lần


def _qwen(name: str):
    with _QWEN_LOCK:
        return _qwen_load(name)


def _qwen_load(name: str):
    if name not in _QWEN:
        import torch
        from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM
        repo = {"emb": "Qwen/Qwen3-Embedding-0.6B", "rerank": "Qwen/Qwen3-Reranker-0.6B"}[name]
        tok = AutoTokenizer.from_pretrained(repo, padding_side="left")
        model = (AutoModel if name == "emb" else AutoModelForCausalLM).from_pretrained(repo, dtype=torch.float16 if torch.cuda.is_available() else torch.float32).eval()
        model = model.to("cuda") if torch.cuda.is_available() else model
        _QWEN[name] = (tok, model)
    return _QWEN[name]


class QwenEmbedBackend(VectorBackend):
    """Qwen3-Embedding-0.6B (CPU), last-token pooling; vector tài liệu nhớ theo nội dung. VECTOR_BACKEND=qwen_emb, mặc định tắt."""
    INSTRUCT = "Instruct: Given a customer's question to an e-commerce call center, retrieve policy passages that answer it\nQuery:"

    def __init__(self):
        self._cache = _EMB_CACHE

    def warm(self, chunks: List["PolicyChunk"]) -> None:
        """Nạp model và tính sẵn vector tài liệu ở luồng nền (lần tra đầu từng mất 21–29 s); lỗi thì thôi, lần tra đầu tự nạp như cũ."""
        def run():
            try:
                self.scores("khởi động", list(chunks))
            except Exception as e:
                logger.warning("[RAG] nạp sẵn embedding lỗi (%s)", e)
        __import__("threading").Thread(target=run, daemon=True).start()

    def _embed(self, texts: List[str]):
        import torch
        tok, model = _qwen("emb")
        with torch.no_grad():
            batch = tok(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(model.device)
            vec = model(**batch).last_hidden_state[:, -1].float().cpu()
        return torch.nn.functional.normalize(vec, dim=-1)

    def scores(self, query: str, candidates: List["PolicyChunk"]) -> List[float]:
        import torch
        todo = [c.content for c in candidates if c.content not in self._cache]
        for i in range(0, len(todo), 16):
            for t, v in zip(todo[i:i + 16], self._embed(todo[i:i + 16])):
                self._cache[t] = v
        q = self._embed([self.INSTRUCT + query])[0]
        return (torch.stack([self._cache[c.content] for c in candidates]) @ q).tolist()

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        if not candidates:
            return []
        return [c for _, c in sorted(zip(self.scores(query, candidates), candidates), key=lambda x: -x[0])[:top_k]]


class QwenRerankBackend(VectorBackend):
    """Ứng viên = hợp BM25 top-N và embedding top-N, rồi Qwen3-Reranker-0.6B chấm p(yes). `last_scores` để chọn ngưỡng từ chối. VECTOR_BACKEND=qwen_rerank."""
    N = int(os.environ.get("RERANK_POOL_N", "5"))
    PREFIX = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. "
              "Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
    SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    INSTRUCT = "Given a customer's question to an e-commerce call center, judge whether the policy passage helps answer it"

    def __init__(self):
        self.first = [Bm25Backend(), QwenEmbedBackend()]
        self.last_scores: List[float] = []

    def warm(self, chunks: List["PolicyChunk"]) -> None:
        """Nạp sẵn reranker + embedding và vector tài liệu ở luồng nền."""
        def run():
            try:
                _qwen("rerank")
            except Exception as e:
                logger.warning("[RAG] nạp sẵn reranker lỗi (%s)", e)
        __import__("threading").Thread(target=run, daemon=True).start()
        self.first[1].warm(chunks)

    def rank(self, query: str, candidates: List["PolicyChunk"], top_k: int = 3) -> List["PolicyChunk"]:
        import torch
        pool = []
        for part in self.first:
            pool += [c for c in part.rank(query, candidates, top_k=self.N) if c not in pool]
        if not pool:
            self.last_scores = []
            return []
        tok, model = _qwen("rerank")
        yes, no = tok.convert_tokens_to_ids("yes"), tok.convert_tokens_to_ids("no")
        texts = [self.PREFIX + f"<Instruct>: {self.INSTRUCT}\n<Query>: {query}\n<Document>: {c.content}" + self.SUFFIX for c in pool]
        with torch.no_grad():
            batch = tok(texts, padding=True, truncation=True, max_length=1024, return_tensors="pt").to(model.device)
            logits = model(**batch).logits[:, -1, [no, yes]]
            p = torch.softmax(logits.float(), dim=-1)[:, 1].tolist()
        ranked = sorted(zip(p, pool), key=lambda x: -x[0])[:top_k]
        self.last_scores = [s for s, _ in ranked]
        return [c for _, c in ranked]


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
    if choice in ("bm25", "hybrid", "qwen_emb", "qwen_rerank"):
        try:
            return {"bm25": Bm25Backend, "hybrid": HybridBackend, "qwen_emb": QwenEmbedBackend, "qwen_rerank": QwenRerankBackend}[choice]()
        except Exception as e:
            logger.warning("[RAG] VECTOR_BACKEND=%s unavailable (%s) — falling back to tfidf.", choice, e)
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
