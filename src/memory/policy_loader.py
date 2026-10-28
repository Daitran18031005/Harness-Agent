"""
Policy Chunk Loader: Parse 99 chunk chính sách thật từ BTC-Data-Vong1-TEAMS/policy/*.md.
Mỗi file dùng header dạng `## [XX-nn] Tiêu đề` để đánh dấu ranh giới chunk — giữ nguyên
chunk_id này làm nhãn Recall@k. effective_from/effective_to tra theo changelog.md thật
(không đoán): chỉ chinh-sach-doi-tra-v2026-06-HET-HIEU-LUC.md là tài liệu đã hết hiệu lực
(hết hạn 2026-09-30, trước ngày cutover 01/10/2026 trong changelog [CL-01]).
"""
import os
import re
import logging
from typing import List, Optional

from .semantic_rag import PolicyChunk

logger = logging.getLogger("harness.memory")

CHUNK_HEADER_RE = re.compile(r'^## \[([A-Z0-9-]+)\]\s*(.*)$', re.MULTILINE)

INTERNAL_DOCS = {"ghi-chu-nhap-hang-NOI-BO.md", "noi-quy-nhan-vien.md"}

# (effective_from, effective_to, version) tra từ changelog.md thật — xem [CL-01..05].
DOC_VALIDITY = {
    "chinh-sach-doi-tra.md": ("2026-10-01", "2099-12-31", "2026-10"),
    "chinh-sach-doi-tra-v2026-06-HET-HIEU-LUC.md": ("2020-01-01", "2026-09-30", "2026-06"),
    "dieu-khoan-khuyen-mai.md": ("2026-10-01", "2099-12-31", "2026-10"),
    "chinh-sach-van-chuyen-thanh-toan.md": ("2026-09-15", "2099-12-31", "2026-09"),
    "chinh-sach-bao-hanh.md": ("2026-08-01", "2099-12-31", "2026-08"),
}
DEFAULT_VALIDITY = ("2020-01-01", "2099-12-31", "default")


def _resolve_policy_dir(policy_dir: Optional[str]) -> str:
    if policy_dir and os.path.isdir(policy_dir):
        return policy_dir
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..", "BTC-Data-Vong1-TEAMS", "policy")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "BTC-Data-Vong1-TEAMS", "policy")),
        os.path.abspath(os.path.join(os.getcwd(), "BTC-Data-Vong1-TEAMS", "policy")),
        os.path.abspath(os.path.join(os.getcwd(), "..", "BTC-Data-Vong1-TEAMS", "policy")),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    raise FileNotFoundError(f"policy dir not found, tried: {candidates}")


def _parse_file(path: str, doc_name: str) -> List[PolicyChunk]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    access = "internal" if doc_name in INTERNAL_DOCS else "public"
    effective_from, effective_to, version = DOC_VALIDITY.get(doc_name, DEFAULT_VALIDITY)

    matches = list(CHUNK_HEADER_RE.finditer(text))
    chunks = []
    for i, m in enumerate(matches):
        chunk_id = f"[{m.group(1)}]"
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        content = f"{title}. {body}" if title else body
        chunks.append(PolicyChunk(
            chunk_id=chunk_id,
            doc_name=doc_name,
            content=content,
            version=version,
            effective_from=effective_from,
            effective_to=effective_to,
            access=access
        ))
    return chunks


def load_policy_chunks(policy_dir: Optional[str] = None) -> List[PolicyChunk]:
    resolved = _resolve_policy_dir(policy_dir)
    all_chunks: List[PolicyChunk] = []
    for fname in sorted(os.listdir(resolved)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(resolved, fname)
        try:
            all_chunks.extend(_parse_file(path, fname))
        except Exception as e:
            logger.warning("[RAG] failed to parse policy file %s (%s) — skipped.", fname, e)
    logger.info("[RAG] loaded %d policy chunks from %s", len(all_chunks), resolved)
    return all_chunks
