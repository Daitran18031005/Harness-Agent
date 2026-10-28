"""
So sánh các RÀO CHẮN chống tạo đơn do đọc nhầm "đồng ý" (src/harness/reply_reader.py, bước NGAY SAU khi agent đọc lại đơn), trên LLM THẬT:
  none        — chỉ lớp một (đối chứng, không có rào)
  confidence  — lớp một + trường "confidence" ≥ ngưỡng (không gọi thêm LLM)
  verify      — lớp một + lớp LLM thứ hai độc lập (gọi thêm chỉ khi lớp một nói agree)
Mỗi câu khách có nhãn `create` = ĐƠN CÓ ĐƯỢC TẠO không. Hai số quan trọng:
  tạo nhầm (false-create) = nhãn không tạo nhưng rào cho tạo  — rủi ro tiền bạc, phải ≈ 0
  bỏ sót (missed)         = nhãn tạo nhưng rào không cho       — khách phải xác nhận thêm (tốn lượt, không mất đơn)
Kèm số lần gọi LLM, chi phí và độ trễ trung bình thêm. Bộ câu dưới đây do người viết code tự nghĩ → chỉ là điểm xuất phát;
thêm câu khách THẬT bằng `--cases file.jsonl` (mỗi dòng {"text": "...", "create": true|false}). Trần chi phí CỨNG trong mã.

    python scripts/eval_consent_guard.py [--cases file.jsonl]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

MAX_COST_VND = 170.0
READBACK = "Dạ em đọc lại đơn: 1 giày RunLite 2 Pro size 38 màu đen, tổng 1.521.000đ, giao cho Đại, COD. Anh xác nhận đặt đơn này giúp em nhé?"
THRESHOLDS = (0.7, 0.85, 0.95)

# (lời khách, có tạo đơn không) — nhóm theo bản chất ngữ nghĩa, không theo từ khóa
CASES = [
    # chấp nhận rõ ràng, nhiều cách nói
    ("ừ chốt đi em", True), ("được rồi em cứ lên đơn cho anh", True), ("thôi cũng được, lấy luôn", True), ("đúng hết rồi nha em", True),
    ("ok em", True), ("dạ đồng ý", True), ("uh dat di em", True), ("chuẩn rồi, em làm giúp chị nhé", True), ("ờ thì cứ vậy đi", True),
    ("vâng ạ, anh chốt đơn này", True),
    # phản hồi chưa mang nội dung chấp nhận
    ("ừm", False), ("ờ...", False), ("hmm", False), ("à", False), ("để xem", False), ("...", False), ("alo? em nói gì anh nghe không rõ", False),
    # có điều kiện / câu hỏi / yêu cầu mới
    ("được nhưng giao trước thứ sáu nhé", False), ("ok, mà có tặng kèm gì không?", False), ("chốt, nhưng bớt thêm 50k được không", False),
    ("giao mất mấy ngày vậy em?", False), ("ok nhưng đổi sang màu xám đi", False), ("đúng rồi, thêm một đôi nữa nhé", False),
    # sửa thông tin trong đơn
    ("sai tên rồi, giao cho Hà", False), ("địa chỉ sai, phải là 20 Lê Lợi", False), ("không phải số đó, gửi số khác", False),
    # từ chối / hoãn / thương lượng
    ("hơi mắc, bớt 100k thì chốt", False), ("để chị hỏi chồng đã", False), ("thôi không lấy nữa", False), ("chưa cần, cảm ơn em", False),
    ("em gửi báo giá qua zalo anh xem đã", False),
    # mơ hồ / dễ hiểu nhầm
    ("cũng được", False), ("tạm được", False), ("chắc vậy", False), ("em cứ ghi lại đã, anh nghĩ thêm", False), ("đúng rồi, giá cao thật đấy", False),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", help="file JSONL câu khách thật: {\"text\":..., \"create\":true|false}")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    cases = list(CASES)
    if args.cases:
        with open(args.cases, encoding="utf-8") as f:
            cases += [(d["text"], bool(d["create"])) for d in map(json.loads, filter(str.strip, f))]
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.llm.client import LLMClient
    from src.llm.cost_tracker import BudgetExceeded
    from src.harness.reply_reader import read_reply, _second_opinion
    llm = LLMClient()
    if not llm.available:
        print("Không có OPENAI_API_KEY — không đo được.")
        return 2
    llm.cost_tracker.set_hard_cap(MAX_COST_VND)
    rows = []
    try:
        for text, create in cases:
            r = read_reply(llm, text, READBACK, {"stage": "readback"}, guard="none")
            row = {"text": text, "create": create, "agree": bool(r and r.agrees), "conf": r.confidence if r else 0.0,
                   "l1_ms": (r.usage[0].get("latency_ms", 0) if r and r.usage else 0), "l1_vnd": (r.usage[0].get("vnd_cost", 0) if r and r.usage else 0)}
            if row["agree"]:
                u = []
                row["verified"] = _second_opinion(llm, text, READBACK, u)
                row["l2_ms"], row["l2_vnd"] = (u[0].get("latency_ms", 0), u[0].get("vnd_cost", 0)) if u else (0, 0)
            rows.append(row)
            print(f"{'TẠO ' if create else 'KHÔNG'} | l1={'agree' if row['agree'] else 'other'} conf={row['conf']:.2f} verify={row.get('verified', '-')} | {text!r}")
    except BudgetExceeded as e:
        print(f"[DỪNG] {e} — bảng dưới đây chỉ tính {len(rows)}/{len(cases)} câu đã chạy")

    n_yes, n_no = sum(r["create"] for r in rows), sum(not r["create"] for r in rows)
    l1_ms = sum(r["l1_ms"] for r in rows) / len(rows)
    l1_vnd = sum(r["l1_vnd"] for r in rows) / len(rows)
    strategies = {"none": lambda r: r["agree"]}
    for t in THRESHOLDS:
        strategies[f"confidence>={t}"] = (lambda t: lambda r: r["agree"] and r["conf"] >= t)(t)
    strategies["verify"] = lambda r: r["agree"] and r.get("verified", False)
    strategies["verify+conf>=0.85"] = lambda r: r["agree"] and r.get("verified", False) and r["conf"] >= 0.85
    print(f"\n{len(rows)} câu ({n_yes} nên tạo, {n_no} không nên). Lớp một trung bình {l1_ms:.0f} ms, {l1_vnd:.2f} VND/lượt.\n")
    print(f"{'rào chắn':<22}{'tạo nhầm':>12}{'bỏ sót':>12}{'+ms/lượt':>12}{'+VND/lượt':>12}")
    for name, f in strategies.items():
        fc = [r["text"] for r in rows if not r["create"] and f(r)]
        ms_ = [r["text"] for r in rows if r["create"] and not f(r)]
        extra_ms = sum(r.get("l2_ms", 0) for r in rows) / len(rows) if name.startswith("verify") else 0
        extra_vnd = sum(r.get("l2_vnd", 0) for r in rows) / len(rows) if name.startswith("verify") else 0
        print(f"{name:<22}{f'{len(fc)}/{n_no}':>12}{f'{len(ms_)}/{n_yes}':>12}{extra_ms:>12.0f}{extra_vnd:>12.2f}")
        for t in fc:
            print(f"    tạo nhầm: {t!r}")
        for t in ms_:
            print(f"    bỏ sót : {t!r}")
    from src.eval.runner import spent_vnd
    print(f"\nChi phí: {spent_vnd(llm):,.1f} VND (trần cứng {MAX_COST_VND:,.0f}; trần chỉ kiểm TRƯỚC mỗi lần gọi nên có thể vượt nhẹ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
