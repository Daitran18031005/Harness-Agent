"""
TRẦN CHI PHÍ CỨNG TÍCH LŨY cho việc sinh dataset (quyết định của người dùng 2026-10-24: 10.000 VND, thực thi BẰNG MÃ).

Sổ cái duy nhất = `dataset/reports/generation_runs.jsonl` (mỗi dòng một lần chạy, có `spent_vnd`), kể cả khi `--out` trỏ nơi khác —
nên không thể né trần bằng cách đổi thư mục ra. Hằng số `HARD_CAP_VND` nằm trong mã; cờ dòng lệnh chỉ HẠ được trần mỗi lần chạy, không nâng được.
"""
import json
import os
from typing import Optional

HARD_CAP_VND = 10_000.0
# Client chỉ kiểm trần TRƯỚC mỗi lần gọi (spent >= cap) nên có thể vượt đúng một lần gọi; một lần gọi sinh lời thoại tối đa ~3.500 token ra + ~6.000 token vào
# ≈ 60 VND (gpt-6-luna) → trừ biên 100 VND để TỔNG không bao giờ vượt HARD_CAP_VND.
ONE_CALL_MARGIN_VND = 100.0
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LEDGER_PATH = os.path.join(CODE_DIR, "dataset", "reports", "generation_runs.jsonl")


class CumulativeBudgetExhausted(RuntimeError):
    """Đã chạm trần tích lũy: không được gọi LLM nữa."""


def spent_total(ledger: Optional[str] = None) -> float:
    path = ledger or LEDGER_PATH
    if not os.path.exists(path):
        return 0.0
    total = 0.0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                total += float(json.loads(line).get("spent_vnd") or 0.0)
    return total


def remaining(ledger: Optional[str] = None, cap: float = HARD_CAP_VND) -> float:
    return max(0.0, cap - spent_total(ledger))


def run_cap(requested: float, ledger: Optional[str] = None, cap: float = HARD_CAP_VND) -> float:
    """Trần cho MỘT lần chạy = min(trần người dùng yêu cầu, phần còn lại của trần tích lũy). Hết phần còn lại → ném lỗi, không gọi LLM."""
    left = remaining(ledger, cap) - ONE_CALL_MARGIN_VND
    if left <= 0:
        raise CumulativeBudgetExhausted(f"đã tiêu {spent_total(ledger):,.1f}/{cap:,.0f} VND — chạm trần tích lũy (đã trừ biên {ONE_CALL_MARGIN_VND:.0f} VND cho một lần gọi), dừng")
    if requested <= 0:
        raise ValueError("--max-cost-vnd phải > 0")
    return min(requested, left)


def record_run(entry: dict, ledger: Optional[str] = None) -> None:
    """Ghi NỐI một dòng vào sổ cái (không bao giờ ghi đè)."""
    path = ledger or LEDGER_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
