"""
Tạo `asr/hypotheses.json` theo định dạng BTC (`reference_eval.py --asr`):

    {"D01": {"text": "<transcript>", "entities": {...},
             "turns": [{"idx": 1, "speaker": "A", "start": 0.0, "end": 4.1, "text": "...", "entities": {...}}]}}

QUY TẮC VỀ `turns` (không giả lập): chỉ có `turns` khi file audio có MỐC THỜI GIAN TỪNG LƯỢT do khâu tạo audio ghi lại
(`<id>.segments.json` cạnh file audio, cùng định dạng BTC dùng cho diarization, thêm khóa `idx`):

    {"id": "D01", "segments": [{"idx": 1, "speaker": "A", "start": 0.0, "end": 4.1}, ...]}

Khi đó mỗi TỪ nhận dạng được (có mốc thời gian theo token) được gán vào lượt có khoảng thời gian chứa điểm giữa của từ;
điểm giữa nằm ngoài mọi lượt thì gán vào lượt gần nhất nếu cách ≤ `tolerance_s`, quá xa thì bỏ từ đó. Không có file mốc
thời gian, hoặc backend không có mốc thời gian theo từ → KHÔNG xuất `turns` (không đoán người nói).
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from src.channels.asr_postprocess import extract_hypothesis_entities

SEGMENT_SUFFIX = ".segments.json"


def segments_path(audio_path: str) -> str:
    return os.path.splitext(audio_path)[0] + SEGMENT_SUFFIX


def load_turn_segments(audio_path: str) -> Optional[List[Dict[str, Any]]]:
    """Đọc mốc thời gian lượt thoại cạnh file audio; None nếu không có/không hợp lệ."""
    path = segments_path(audio_path)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        segs = json.load(fh).get("segments")
    if not segs or any(k not in s for s in segs for k in ("idx", "speaker", "start", "end")):
        return None
    return sorted(segs, key=lambda s: s["start"])


def assign_words_to_turns(words: List[Tuple[str, float, float]], segments: List[Dict[str, Any]],
                          tolerance_s: float = 0.6) -> List[Dict[str, Any]]:
    """Gán từ → lượt theo điểm giữa của từ. Trả danh sách lượt (đủ mọi lượt trong `segments`, text có thể rỗng)."""
    buckets: Dict[int, List[str]] = {s["idx"]: [] for s in segments}
    for text, start, end in words:
        mid = (start + end) / 2
        best, best_d = None, None
        for s in segments:
            d = 0.0 if s["start"] <= mid <= s["end"] else min(abs(mid - s["start"]), abs(mid - s["end"]))
            if best_d is None or d < best_d:
                best, best_d = s, d
        if best is not None and best_d <= tolerance_s:
            buckets[best["idx"]].append(text)
    return [{"idx": s["idx"], "speaker": s["speaker"], "start": round(float(s["start"]), 3),
             "end": round(float(s["end"]), 3), "text": " ".join(buckets[s["idx"]])} for s in segments]


def build_entry(result, audio_path: Optional[str] = None, call_date: Optional[str] = "2026-10-15",
                segments: Optional[List[Dict[str, Any]]] = None) -> Tuple[Dict[str, Any], List[str]]:
    """`result`: `ASRResult`. Trả (mục hypotheses, ghi chú về điều đã/không làm được)."""
    notes: List[str] = []
    entry: Dict[str, Any] = {"text": result.text, "entities": extract_hypothesis_entities(result.text, call_date)}
    segs = segments if segments is not None else (load_turn_segments(audio_path) if audio_path else None)
    if segs is None:
        notes.append("không có mốc thời gian lượt thoại (<id>.segments.json) → không xuất turns")
    elif not result.words:
        notes.append(f"backend '{result.backend}' không có mốc thời gian theo từ → không xuất turns")
    else:
        turns = assign_words_to_turns(result.words, segs)
        for t in turns:
            t["entities"] = extract_hypothesis_entities(t["text"], call_date) if t["text"] else {}
        entry["turns"] = turns
    return entry, notes
