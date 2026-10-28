"""
Hồ sơ tham số theo model (bước 2b — client đa nhà cung cấp/đa dòng model).

Các model suy luận (o-series, gpt-5*, gpt-6*...) từ chối `temperature` và đòi `max_completion_tokens`
thay cho `max_tokens`; model chat thường thì ngược lại. Bảng dưới đây chỉ là *giả định ban đầu* — client còn
tự học thêm khi API trả lỗi "unsupported parameter" (xem LLMClient._create_stream), nên tên model lạ
không làm vỡ pipeline.

Không có API nào cho biết tham số nào được hỗ trợ; `GET /v1/models` chỉ cho biết model có tồn tại/được cấp quyền.
"""
import os
import re
from dataclasses import dataclass
from typing import Set


@dataclass(frozen=True)
class ModelProfile:
    supports_temperature: bool = True
    supports_seed: bool = True
    token_param: str = "max_tokens"      # hoặc "max_completion_tokens"
    is_reasoning: bool = False


_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")


def normalize_model_name(model: str) -> str:
    """Chữ thường, bỏ hậu tố ngày phát hành (gpt-4o-2024-08-06 -> gpt-4o)."""
    name = (model or "").strip().lower()
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", name)


def profile_for(model: str) -> ModelProfile:
    name = normalize_model_name(model)
    if name.startswith(_REASONING_PREFIXES):
        return ModelProfile(supports_temperature=False, supports_seed=True,
                            token_param="max_completion_tokens", is_reasoning=True)
    return ModelProfile()


def forced_unsupported_params() -> Set[str]:
    """Cho phép người dùng khai báo thêm tham số bị loại: LLM_UNSUPPORTED_PARAMS=temperature,seed"""
    raw = os.environ.get("LLM_UNSUPPORTED_PARAMS", "")
    return {p.strip() for p in raw.split(",") if p.strip()}


class JudgeModelConflict(ValueError):
    """Judge dùng cùng model với agent -> đánh giá thiên vị (tự chấm mình)."""


def assert_distinct_judge(agent_model: str, judge_model: str) -> None:
    if normalize_model_name(agent_model) == normalize_model_name(judge_model):
        raise JudgeModelConflict(
            f"Model judge '{judge_model}' trùng model agent '{agent_model}': LLM-judge phải là model khác "
            f"(đặt EVAL_LLM_MODEL khác LLM_MODEL)."
        )
