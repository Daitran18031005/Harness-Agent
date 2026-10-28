"""
Quét kịch bản BTC (public_sample) tìm chỗ ĐÁP ÁN mâu thuẫn với lời khách hoặc với chính tool tham chiếu của BTC
(`mock_tools.py`). Chỉ đọc, không sửa GT. Kết quả là danh sách "NGHI lỗi dữ liệu BTC" để hỏi lại BTC — không phải kết luận.

    python scripts/scan_btc_data.py [--scenarios <dir>]
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
sys.path.insert(0, os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval"))
import mock_tools  # noqa: E402
from src.channels.normalizer import RequestNormalizer, InputChannel  # noqa: E402
from src.common.money import extract_amounts  # noqa: E402

DEFAULT_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "test_set", "public_sample")
NORM = RequestNormalizer()


def call_dates(spec):
    from src.eval.runner import ScenarioRunner
    out, prev = {}, "2026-10-15"
    for cn in ("call_1", "call_2", "call_3"):
        if cn in spec["calls"]:
            prev = ScenarioRunner._call_date(spec["calls"][cn], prev)
            out[cn] = prev
    return out


def customer_numbers(call_spec):
    turns = call_spec.get("customer_turns_asr") or call_spec.get("customer_turns") or []
    amounts, plain = set(), set()
    for t in turns:
        text = NORM.normalize(t, InputChannel.HOTLINE, "0900000000").normalized_text
        amounts |= {v for v, _ in extract_amounts(text)}
        import re
        plain |= {int(x) for x in re.findall(r"(?<![\d.,])(\d{1,3})(?![\d.,])", text)}
    return amounts, plain


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=DEFAULT_DIR)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    findings = []
    for path in sorted(glob.glob(os.path.join(args.scenarios, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            sc = json.load(fh)
        sid, dates, phone = sc["scenario_id"], call_dates(sc), sc.get("customer_phone")
        for cn, spec in sc["calls"].items():
            fe = spec.get("facts_established") or {}
            amounts, plain = customer_numbers(spec)
            # 1) số khách "nêu" mà đáp án ghi khác lời khách
            for key in ("budget_vnd", "competitor_price_vnd"):
                if key in fe and fe[key] not in amounts:
                    findings.append((sid, cn, f"facts_established.{key}={fe[key]:,} nhưng lời khách chỉ nêu các số tiền {sorted(amounts) or 'không có'}"))
            if "room_area_m2" in fe and int(fe["room_area_m2"]) not in plain:
                findings.append((sid, cn, f"facts_established.room_area_m2={fe['room_area_m2']} không thấy trong lời khách (các số: {sorted(plain)})"))
            # 2) giá đáp án so với tool tham chiếu của chính BTC
            sku = fe.get("product_advised")
            if sku and "price_quoted_vnd" in fe:
                q = mock_tools.pricing_get_quote(sku, dates[cn], 1, phone)
                if q.get("final_price_vnd") != fe["price_quoted_vnd"] and q.get("list_price_vnd") != fe["price_quoted_vnd"]:
                    findings.append((sid, cn, f"facts_established.price_quoted_vnd={fe['price_quoted_vnd']:,} khác mock_tools.pricing.get_quote({sku}, {dates[cn]}) = final {q.get('final_price_vnd'):,} / list {q.get('list_price_vnd'):,}"))
            gt = spec.get("ground_truth_facts") or {}
            target = (spec.get("success_if") or {}).get("args_match", {}) or {}
            sku2 = target.get("sku")
            if sku2 and "price_vnd" in gt:
                q = mock_tools.pricing_get_quote(sku2, dates[cn], 1, phone)
                if q.get("final_price_vnd") != gt["price_vnd"]:
                    findings.append((sid, cn, f"ground_truth_facts.price_vnd={gt['price_vnd']:,} khác mock_tools.pricing.get_quote({sku2}, {dates[cn]}) = {q.get('final_price_vnd'):,}"))
            # 3) mã đơn không thể sinh ra
            oid = target.get("order_id")
            if oid and oid.startswith("OD") and oid != "OD600001":
                findings.append((sid, cn, f"success_if.args_match.order_id={oid} — mock_tools chỉ sinh OD600001, OD600002… (BTC đã nới script chấm 2026-10-20, xem CHECKING § 11.0)"))
    print(f"## Nghi lỗi dữ liệu BTC trong {args.scenarios}  ({len(findings)} mục)")
    for sid, cn, msg in findings:
        print(f"- {sid}/{cn}: {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
