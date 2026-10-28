"""
Policy Router (bước 11): chọn tài liệu chính sách bằng LLM trước khi TF-IDF tìm trong đó (2 tầng).
- Tầng 1: LLM rẻ (cùng model agent, temperature=0, JSON) đọc MỤC LỤC (tên file, các mục, ngày hiệu lực)
  và câu tra cứu -> {files[], as_of_date, answerable}. Không đưa nội dung tài liệu cho LLM.
- Tầng 2: TF-IDF (semantic_rag) lấy ROUTED_TOP_K kết quả đầu trong các file đã chọn, bù phần còn lại từ toàn bộ (lai).
Code chỉ KIỂM CHỨNG đầu ra LLM: tên file phải có trong mục lục (tên bịa bị bỏ); as_of_date phải là ngày hợp lệ
VÀ đi kèm đoạn trích nguyên văn có thật trong câu hỏi (không thì bỏ, dùng ngày cuộc gọi). Router lỗi / không có
LLM / đầu ra hỏng -> route() trả None và caller quay về TF-IDF toàn bộ như trước.
Tắt hẳn bằng POLICY_ROUTER=off; model riêng bằng POLICY_ROUTER_MODEL (mặc định = LLM_MODEL của agent).
"""
import os
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("harness.memory")

# Số kết quả đầu lấy từ file router chọn; phần còn lại của top-k bù từ toàn bộ tài liệu (đo bước 11: k=2 cho Recall@5 cao nhất).
ROUTED_TOP_K = 2

SYSTEM_PROMPT = """Bạn là bộ định tuyến tra cứu chính sách của tổng đài bán hàng. Bạn KHÔNG trả lời khách; chỉ chọn tài liệu cần đọc.

MỤC LỤC tài liệu (mỗi dòng: tên file | phiên bản | hiệu lực từ→đến | các mục "mã tiêu đề"):
{catalog}

Với câu tra cứu của khách, trả về MỘT JSON object:
{{"files": ["tên file", ...], "as_of_date": "YYYY-MM-DD" hoặc null, "as_of_evidence": "đoạn trích NGUYÊN VĂN trong câu hỏi" hoặc null, "answerable": true hoặc false}}

Quy tắc:
- files: chỉ tên file CÓ trong mục lục, chép đúng từng ký tự; chọn ít nhất đủ để trả lời (câu cần ghép nhiều tài liệu thì chọn nhiều file). Câu hỏi so sánh với chính sách cũ / "có đúng là…" / số liệu đã đổi thì thêm file nhật ký thay đổi nếu mục lục có. Không chọn file không liên quan.
- as_of_date: CHỈ khi câu hỏi nêu ngày/tháng khách MUA hoặc ĐẶT hàng (đơn cũ): đổi ra YYYY-MM-DD (chỉ nêu tháng thì lấy ngày 1; ngày tương đối như "hôm qua" tính từ ngày hôm nay bên dưới; thiếu năm thì lấy năm hôm nay) và chép nguyên văn cụm từ chỉ ngày vào as_of_evidence. Không nêu ngày mua/đặt thì cả hai là null. Đừng lấy ngày khách gọi, ngày nhận hàng hay ngày hẹn làm as_of_date.
- Khi đơn mua trước ngày hiệu lực của phiên bản mới, hãy chọn cả file phiên bản cũ nếu mục lục có.
- answerable: mặc định true. Chỉ false khi bạn chắc chắn không file nào trong mục lục có thể chứa câu trả lời (thông tin chưa từng được công bố trong tài liệu, hoặc thuộc loại nội bộ như giá nhập, biên lợi nhuận, nhà cung cấp, giá sàn). Có file liên quan dù chưa chắc → true.
Chỉ trả JSON, không giải thích."""


@dataclass
class RouteDecision:
    files: List[str]                       # đã kiểm chứng; rỗng = không giới hạn file
    as_of_date: Optional[str]              # ISO, đã kiểm chứng; None = dùng ngày cuộc gọi
    answerable: bool
    as_of_evidence: Optional[str] = None
    dropped_files: List[str] = field(default_factory=list)   # tên LLM bịa / không có trong mục lục
    date_dropped: bool = False             # LLM đưa ngày nhưng thiếu bằng chứng nguyên văn hoặc ngày sai


def _fold(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text or "").casefold().split())


def build_catalog(chunks: Sequence[Any]) -> List[Dict[str, Any]]:
    """Mục lục theo file từ các chunk (đã lọc quyền truy cập): tên, phiên bản, hiệu lực, các mục (mã + tiêu đề)."""
    docs: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        d = docs.setdefault(c.doc_name, {"name": c.doc_name, "version": c.version, "effective_from": c.effective_from,
                                         "effective_to": c.effective_to, "sections": []})
        # loader ghép content = "<tiêu đề>. <nội dung>" -> tiêu đề là đoạn trước ". " đầu tiên.
        title = c.content.split(". ", 1)[0].strip()[:70]
        d["sections"].append(f"{c.chunk_id.strip('[]')} {title}")
    return list(docs.values())


def catalog_text(catalog: Sequence[Dict[str, Any]]) -> str:
    return "\n".join(f"{d['name']} | {'v' + d['version'] if d['version'] != 'default' else '-'} | {d['effective_from']}→{d['effective_to']} | "
                     + "; ".join(d["sections"]) for d in catalog)


def validate(raw: Dict[str, Any], names: Sequence[str], question: str) -> Optional[RouteDecision]:
    """Đưa JSON của LLM về dạng an toàn. None nếu thiếu/sai kiểu `answerable` hoặc `files` (coi như router hỏng)."""
    answerable, files = raw.get("answerable"), raw.get("files")
    if not isinstance(answerable, bool) or not isinstance(files, list):
        return None
    known = set(names)
    kept = list(dict.fromkeys(f.strip() for f in files if isinstance(f, str) and f.strip() in known))
    dropped = [str(f) for f in files if not (isinstance(f, str) and f.strip() in known)]
    as_of, evidence, date_dropped = None, None, False
    if raw.get("as_of_date"):
        try:
            as_of = date.fromisoformat(str(raw["as_of_date"])).isoformat()
        except ValueError:
            as_of = None
        evidence = raw.get("as_of_evidence")
        if as_of and not (isinstance(evidence, str) and evidence.strip() and _fold(evidence) in _fold(question)):
            as_of = None
        if not as_of:
            evidence, date_dropped = None, True
    return RouteDecision(files=kept, as_of_date=as_of, answerable=answerable, as_of_evidence=evidence,
                         dropped_files=dropped, date_dropped=date_dropped)


class PolicyRouter:
    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm
        self._llm_tried = llm is not None
        self.usages: List[Dict[str, Any]] = []         # chi phí/độ trễ mỗi lần gọi; drain_usage() để gộp vào trace
        self.last_error: Optional[str] = None

    def _client(self) -> Optional[Any]:
        if os.environ.get("POLICY_ROUTER", "").strip().lower() in ("off", "0", "false"):
            return None
        if not self._llm_tried:
            self._llm_tried = True
            try:
                from ..llm.client import LLMClient
                self._llm = LLMClient(model=os.environ.get("POLICY_ROUTER_MODEL", "").strip() or None, temperature=0.0)
            except Exception as e:
                logger.warning("[POLICY_ROUTER] không tạo được LLM client (%s) — dùng TF-IDF toàn bộ.", e)
        llm = self._llm
        return llm if llm is not None and getattr(llm, "available", False) and hasattr(llm, "complete_json") else None

    def route(self, query: str, catalog: Sequence[Dict[str, Any]], today: str) -> Optional[RouteDecision]:
        """Quyết định đã kiểm chứng, hoặc None (không có LLM / lỗi / đầu ra hỏng) -> caller dùng TF-IDF toàn bộ.
        BudgetExceeded (BaseException) cố ý không bị bắt."""
        self.last_error = None
        llm = self._client()
        if llm is None or not catalog or not (query or "").strip():
            return None
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(catalog=catalog_text(catalog))},
                    {"role": "user", "content": f"Hôm nay: {today}\nCâu tra cứu: {query}"}]
        try:
            raw, usage = llm.complete_json(messages)
            self.usages.append(usage)
            decision = validate(raw, [d["name"] for d in catalog], query)
            if decision is None:
                self.last_error = "đầu ra router thiếu/sai kiểu: " + json.dumps(raw, ensure_ascii=False)[:200]
        except Exception as e:
            self.last_error, decision = f"{type(e).__name__}: {e}", None
        if self.last_error:
            logger.warning("[POLICY_ROUTER] %s — dùng TF-IDF toàn bộ.", self.last_error)
        return decision

    def drain_usage(self) -> List[Dict[str, Any]]:
        out, self.usages = self.usages, []
        return out
