"""Chấm lại từ trace bằng chính hàm của BTC (BTC-Data-Vong1-TEAMS/eval/reference_eval.py), nạp theo đường dẫn file."""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.dirname(HERE)
BTC_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS")
REFERENCE_EVAL = os.path.join(BTC_DIR, "eval", "reference_eval.py")
DEFAULT_SCENARIOS = os.path.join(BTC_DIR, "test_set", "public_sample")


def load_reference(path: str = REFERENCE_EVAL):
    spec = importlib.util.spec_from_file_location("reference_eval", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def score(ref, scenarios: dict, trace_path: str, baseline_path: str = None) -> dict:
    """Cùng cấu trúc báo cáo với `reference_eval.py` (system / baseline / comparison)."""
    full = ref.evaluate(scenarios, ref.load_trace(trace_path))
    rep = {"n_scenarios": len(scenarios), "system": full}
    if baseline_path:
        base = ref.evaluate(scenarios, ref.load_trace(baseline_path))
        rep["baseline"] = base
        rq_b, rq_s = base["repeat_question_rate"]["value"], full["repeat_question_rate"]["value"]
        hr = full["hallucination_rate"]["price_promo_only"]["value"]
        tsr = full["task_success_rate"]["value"]
        rep["comparison"] = {
            "rqr_relative_reduction_pct": round((rq_b - rq_s) / rq_b * 100, 1) if rq_b else None,
            "meets_rqr_threshold_40pct": bool(rq_b and (rq_b - rq_s) / rq_b >= 0.40),
            "meets_tsr_70pct": bool(tsr is not None and tsr >= 70),
            "meets_hr_price_5pct": bool(hr is not None and hr <= 5),
        }
    return rep
