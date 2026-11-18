"""
Semantic / KB Memory: Tri thức nghiệp vụ RAG có versioning & access control.
- Chunk policy theo Section ID ([DT-03], [BH-01], v.v.)
- Lọc theo thời gian có hiệu lực (effective_from / effective_to)
- Lọc quyền truy cập: Public (được nói với khách) vs Internal (chỉ dùng nội bộ)
- Chọn tài liệu 2 tầng (policy_router.py): LLM chọn file + ngày mua + abstain, TF-IDF chỉ tìm trong file đã chọn
"""
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

OLD_VERSIONS_EXTRA = 2   # POLICY_ALL_VERSIONS: số đoạn bản cũ nối thêm sau top_k bản hiện hành


@dataclass
class PolicyChunk:
    chunk_id: str
    doc_name: str
    content: str
    version: str
    effective_from: str
    effective_to: str
    access: str = "public"  # public | internal | restricted


class SemanticKBStore:
    # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
    def __init__(self, backend: Optional[Any] = None, router: Optional[Any] = None):
        self.chunks: List[PolicyChunk] = []
        if backend is None:
            from .vector_rag import get_vector_backend
            backend = get_vector_backend()
        self.backend = backend
        if router is None:
            from .policy_router import PolicyRouter
            router = PolicyRouter()          # LLM chỉ được tạo khi có OPENAI_API_KEY (lazy); không có -> TF-IDF toàn bộ
        self.router = router
        self.last_route: Optional[Dict[str, Any]] = None   # quyết định router của lần search gần nhất (cho trace / script đo)
        self.last_usage: List[Dict[str, Any]] = []         # chi phí/độ trễ các lần gọi router của lần search gần nhất (để vào trace và trần chi phí)

    def add_chunk(self, chunk: PolicyChunk):
        self.chunks.append(chunk)

    def _abstain_chunk(self) -> Dict[str, Any]:
        """Câu hỏi ngoài tài liệu (router: answerable=false) -> trả quy tắc 'chưa có thông tin' của playbook (PB-05)."""
        for c in self.chunks:
            if c.chunk_id == "[PB-05]" and c.access == "public":
                return {"chunk_id": c.chunk_id, "doc_name": c.doc_name, "content": c.content, "version": c.version,
                        "access": c.access, "answerable": False}
        return {"chunk_id": "[PB-05]", "doc_name": "", "version": "", "access": "public", "answerable": False,
                "content": 'Trả lời "hiện em chưa có thông tin về…", ghi nhận câu hỏi, hẹn phản hồi qua kênh khách chọn. Không suy đoán.'}

    def _format(self, ranked: List[PolicyChunk], dated: bool = False) -> List[Dict[str, Any]]:
        return [{"chunk_id": c.chunk_id, "doc_name": c.doc_name, "content": c.content, "version": c.version, "access": c.access,
                 **({"effective_from": c.effective_from, "effective_to": c.effective_to} if dated else {})} for c in ranked]

    def prefetch(self, query: str, on_date: str = "2026-10-15", top_k: int = 3) -> List[Dict[str, Any]]:
        """Tra trước theo lời khách (POLICY_PREFETCH): chỉ khi backend chấm được điểm (reranker); kèm `score`. Không router, không abstain.
        POLICY_ALL_VERSIONS bật → mọi phiên bản kèm thời gian hiệu lực; không thì chỉ bản đang hiệu lực ngày gọi."""
        scored = getattr(self.backend, "rank_scored", None)
        if scored is None or not (query or "").strip():
            return []
        visible = [c for c in self.chunks if c.access == "public"]
        all_versions = os.environ.get("POLICY_ALL_VERSIONS", "").strip().lower() in ("on", "1", "true")
        current = [c for c in visible if c.effective_from <= on_date <= c.effective_to]
        ranked = scored(query, current, top_k)
        if all_versions:      # bản cũ chỉ nối thêm sau, không chiếm chỗ bản hiện hành (17/11: SAMPLE-07 mất "7 ngày" vì 2 bản cũ chen top-3)
            ranked += scored(query, [c for c in visible if c not in current], OLD_VERSIONS_EXTRA)
        return [{**d, "score": round(sc, 3)} for (sc, _), d in zip(ranked, self._format([c for _, c in ranked], dated=all_versions))]

    def search(self, query: str, on_date: str = "2026-10-15", access_level: str = "public",
               top_k: int = 3) -> List[Dict[str, Any]]:
        """2 tầng: router LLM chọn file (+ ngày mua để chọn phiên bản, + abstain), vector backend xếp hạng trong file đã chọn (lai, xem dưới).
        Không có router/LLM hoặc router lỗi -> lọc theo ngày cuộc gọi và xếp hạng toàn bộ như trước."""
        from .policy_router import build_catalog, ROUTED_TOP_K
        visible = [c for c in self.chunks if not (access_level == "public" and c.access != "public")]
        used = getattr(self.router, "usages", None)
        n0 = len(used) if used is not None else 0
        route = self.router.route(query, build_catalog(visible), on_date) if self.router else None
        self.last_usage = list(used[n0:]) if used is not None else []     # không drain: script đo vẫn tự drain tổng cuối
        self.last_route = None if route is None else {
            "files": route.files, "as_of_date": route.as_of_date, "answerable": route.answerable,
            "dropped_files": route.dropped_files, "date_dropped": route.date_dropped}
        if route is not None and not route.answerable:
            return [self._abstain_chunk()]

        as_of = (route.as_of_date if route else None) or on_date
        by_date = [c for c in visible if c.effective_from <= as_of <= c.effective_to]   # chọn phiên bản theo ngày mua (nếu có)
        restricted = bool(route and route.files)
        selected = [c for c in by_date if c.doc_name in route.files] if restricted else by_date
        if not restricted:
            if route is None and os.environ.get("POLICY_ALL_VERSIONS", "").strip().lower() in ("on", "1", "true"):
                # Không router thì không biết ngày mua: trả cả bản cũ lẫn bản mới kèm thời gian hiệu lực để LLM chính chọn theo ngày khách mua (MẶC ĐỊNH TẮT)
                old = [c for c in visible if c not in by_date]
                return self._format(self.backend.rank(query, by_date, top_k=top_k) + self.backend.rank(query, old, top_k=OLD_VERSIONS_EXTRA), dated=True)
            return self._format(self.backend.rank(query, by_date, top_k=top_k))
        # Lai: ROUTED_TOP_K kết quả đầu từ file router chọn, phần còn lại bù từ TOÀN BỘ tài liệu đã lọc ngày (bỏ trùng) —
        # router chọn thiếu file thì kết quả đúng vẫn có cơ hội lọt top-k.
        ranked = self.backend.rank(query, selected, top_k=min(ROUTED_TOP_K, top_k))
        if not ranked:
            self.last_route["fallback_all"] = True
        for c in self.backend.rank(query, by_date, top_k=top_k):
            if len(ranked) >= top_k:
                break
            if c not in ranked:
                ranked.append(c)
        return self._format(ranked)
