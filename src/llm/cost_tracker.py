"""
Cost Tracker: Ghi nhận chi phí token thật cho mỗi lượt gọi LLM.
Giá đọc từ `config/pricing.yaml` (USD / 1M token, có ghi chú nguồn và cờ `needs_official_verification`).
Tỷ giá USD->VND đọc từ biến môi trường USD_TO_VND_RATE (nạp qua .env thật của người
dùng, KHÔNG hard-code) — fallback 25.400đ nếu biến không được set.
"""
import os
import logging
from typing import Dict, Any, Tuple, Optional

from .model_profiles import normalize_model_name

logger = logging.getLogger("harness.llm")

PRICING_FILE = os.environ.get(
    "PRICING_FILE",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "pricing.yaml")))

# Dự phòng khi thiếu PyYAML hoặc thiếu file: (input, output, needs_official_verification) USD / 1M token.
_FALLBACK_MODELS = {
    "gpt-4o-mini": (0.15, 0.60, False),
    "gpt-4o": (2.50, 10.00, True),
    "gpt-4.1-mini": (0.40, 1.60, True),
    "gpt-4.1": (2.00, 8.00, True),
    "gpt-6-luna": (0.10, 0.50, True),   # OpenRouter 2026-10-20 — cần đối chiếu giá OpenAI chính thức
}
_FALLBACK_DEFAULT = (0.50, 1.50, True)

_warned_models = set()
_cached_table: Optional[Dict[str, Any]] = None


def load_pricing(path: Optional[str] = None) -> Dict[str, Any]:
    """Trả về {'default': (in, out, verify), 'models': {tên: (in, out, verify, source)}}."""
    path = path or PRICING_FILE
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        models = {normalize_model_name(k): (float(v["input_usd_per_1m"]), float(v["output_usd_per_1m"]),
                                            bool(v.get("needs_official_verification", True)), str(v.get("source", "")))
                  for k, v in (raw.get("models") or {}).items()}
        cached = {normalize_model_name(k): float(v["cached_input_usd_per_1m"])
                  for k, v in (raw.get("models") or {}).items() if v.get("cached_input_usd_per_1m") is not None}
        d = raw.get("default") or {}
        default = (float(d.get("input_usd_per_1m", _FALLBACK_DEFAULT[0])), float(d.get("output_usd_per_1m", _FALLBACK_DEFAULT[1])),
                   bool(d.get("needs_official_verification", True)))
        return {"default": default, "models": models, "cached": cached}
    except Exception as e:  # thiếu PyYAML / file hỏng / thiếu khóa -> dùng bảng dự phòng, không crash
        logger.warning("[COST] không đọc được %s (%s) — dùng bảng giá dự phòng trong mã.", path, e)
        return {"default": _FALLBACK_DEFAULT, "cached": {"gpt-4o-mini": 0.075},
                "models": {k: (a, b, c, "bảng dự phòng trong cost_tracker.py") for k, (a, b, c) in _FALLBACK_MODELS.items()}}


def _table() -> Dict[str, Any]:
    global _cached_table
    if _cached_table is None:
        _cached_table = load_pricing()
    return _cached_table


class BudgetExceeded(BaseException):
    """Tổng chi phí LLM đã chạm TRẦN CỨNG: dừng ngay, trace đã chạy được giữ lại.

    Cố ý kế thừa `BaseException` (không phải `Exception`): các lớp trên (orchestrator, bộ trích slot, runner) có `except Exception` để rơi về nhánh an toàn khi LLM
    lỗi — nếu trần chi phí bị nuốt ở đó thì run vẫn tiếp tục tiêu tiền. Chỉ `except BudgetExceeded` tường minh mới bắt được."""

    def __init__(self, spent_vnd: float, limit_vnd: float):
        super().__init__(f"Chi phí LLM {spent_vnd:,.0f} VND vượt ngưỡng {limit_vnd:,.0f} VND — dừng.")
        self.spent_vnd, self.limit_vnd = spent_vnd, limit_vnd


class CostTracker:
    def __init__(self, pricing: Optional[Dict[str, Any]] = None):
        self.cumulative_prompt_tokens = 0
        self.cumulative_completion_tokens = 0
        self.cumulative_usd_cost = 0.0
        self._pricing = pricing
        # Trần cứng (VND): kiểm TRƯỚC MỖI lần gọi API, tính cả chi phí các vòng đã chạy nhưng chưa được ghi (record_turn chỉ chạy cuối lượt).
        self.hard_cap_vnd: Optional[float] = None
        self._inflight_usd = 0.0

    def spent_vnd(self, include_inflight: bool = True) -> float:
        return (self.cumulative_usd_cost + (self._inflight_usd if include_inflight else 0.0)) * self._vnd_rate()

    def set_hard_cap(self, vnd: Optional[float]) -> None:
        if vnd is not None and vnd <= 0:
            raise ValueError("trần chi phí phải > 0 VND")
        self.hard_cap_vnd = vnd

    def check_cap(self) -> None:
        """Ném BudgetExceeded nếu đã chạm trần — gọi trước mỗi lần gọi API."""
        if self.hard_cap_vnd is not None and self.spent_vnd() >= self.hard_cap_vnd:
            raise BudgetExceeded(self.spent_vnd(), self.hard_cap_vnd)

    def note_round(self, model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> None:
        """Ghi tạm chi phí của một vòng gọi API (trước khi lượt kết thúc) để trần cứng không bị trễ cả một lượt."""
        in_price, out_price, _ = self.price_for(model)
        table = self._pricing or _table()
        cached_price = (table.get("cached") or {}).get(normalize_model_name(model), in_price)
        cached_tokens = max(0, min(cached_tokens or 0, prompt_tokens))
        self._inflight_usd += (((prompt_tokens - cached_tokens) / 1e6) * in_price + (cached_tokens / 1e6) * cached_price + (completion_tokens / 1e6) * out_price)

    def add_external_cost(self, usd: float) -> None:
        """Chi phí LLM đã trả ở nơi khác (vd router chính sách chạy trong server bộ nhớ): vào tổng và trần cứng."""
        self.cumulative_usd_cost += max(0.0, float(usd or 0))

    def commit_inflight(self) -> None:
        """Lượt hỏng giữa chừng (lỗi mạng, vượt số vòng, chạm trần): các vòng đã gọi API vẫn đã TRẢ TIỀN — chuyển ước tính tạm vào tổng thật.
        Không làm vậy thì lần `record_turn` kế tiếp đặt ước tính về 0 và tiền các vòng đó biến mất khỏi tổng (trần cứng và báo cáo chi phí thấp hơn thực tế)."""
        self.cumulative_usd_cost += self._inflight_usd
        self._inflight_usd = 0.0

    def _vnd_rate(self) -> float:
        try:
            return float(os.environ.get("USD_TO_VND_RATE", 25400))
        except (TypeError, ValueError):
            return 25400.0

    def price_for(self, model: str) -> Tuple[float, float, bool]:
        """(input, output USD/1M, giá đã đối chiếu chính thức?). Cảnh báo 1 lần cho model lạ / giá chưa đối chiếu."""
        table = self._pricing or _table()
        key = normalize_model_name(model)
        entry = table["models"].get(key)
        if entry is None:
            if key not in _warned_models:
                logger.warning("[COST] model '%s' chưa có trong config/pricing.yaml — dùng giá mặc định để ước tính chi phí.", model)
                _warned_models.add(key)
            d = table["default"]
            return d[0], d[1], False
        if entry[2] and key not in _warned_models:
            logger.warning("[COST] giá model '%s' CHƯA đối chiếu giá OpenAI chính thức (nguồn: %s).", model, entry[3] or "?")
            _warned_models.add(key)
        return entry[0], entry[1], not entry[2]

    def record_turn(self, model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> Dict[str, Any]:
        """cached_tokens: số token prompt được prompt-caching phục vụ (tính theo giá cached nếu config/pricing.yaml có)."""
        in_price, out_price, verified = self.price_for(model)
        table = self._pricing or _table()
        cached_price = (table.get("cached") or {}).get(normalize_model_name(model), in_price)
        cached_tokens = max(0, min(cached_tokens or 0, prompt_tokens))
        usd_cost = (((prompt_tokens - cached_tokens) / 1_000_000.0) * in_price + (cached_tokens / 1_000_000.0) * cached_price
                    + (completion_tokens / 1_000_000.0) * out_price)
        vnd_rate = self._vnd_rate()
        vnd_cost = usd_cost * vnd_rate

        self.cumulative_prompt_tokens += prompt_tokens
        self.cumulative_completion_tokens += completion_tokens
        self.cumulative_usd_cost += usd_cost
        self._inflight_usd = 0.0                                   # chi phí thật của lượt đã vào tổng; bỏ ước tính tạm

        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "usd_cost": round(usd_cost, 8),
            "vnd_cost": round(vnd_cost, 2),
            "pricing_verified": verified,
            "cumulative_usd_cost": round(self.cumulative_usd_cost, 6),
            "cumulative_vnd_cost": round(self.cumulative_usd_cost * vnd_rate, 2),
        }
