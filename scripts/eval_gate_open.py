"""
Đo việc MỞ order gate bằng code (orchestrator._maybe_open_gate): hai tỷ lệ riêng
  mở nhầm  (rẻ: agent hỏi thông tin giao hàng sớm, KHÔNG tạo đơn) = nhãn "không nên mở" mà hệ thống mở
  bỏ sót mở (lỗi gốc ui_replay_9: gate không chạy, LLM chính hỏi lặp)   = nhãn "nên mở" mà hệ thống không mở

Hai phần:
  A. TẦNG Ý ĐỊNH (cần LLM THẬT, tốn tiền, chỉ chạy khi có cờ --llm): mỗi cảnh = (câu cuối của agent, lời khách, nên mở?). Dự đoán mở = bộ đọc báo
     order_intent=commit, KHÔNG decline, KHÔNG đang hỏi (đúng lớp 1+4 của _maybe_open_gate). Nhóm theo bản chất ngữ nghĩa: cam kết rõ, cam kết nhập nhằng/có điều kiện,
     so sánh/hỏi, "ok" chỉ là tiếng đáp sau câu không liên quan đến mua hàng, mặc cả, từ chối, sửa thông tin.
  B. TẦNG ĐỐI TƯỢNG (OFFLINE, không gọi LLM): cảnh nhiều sản phẩm/biến thể trong cuộc gọi với bộ đọc GIẢ luôn báo "cam kết" → xem code mở gate trên SKU nào (hoặc không mở).
Bộ cảnh do người viết code tự nghĩ → chỉ là điểm xuất phát; thêm cảnh THẬT bằng `--cases file.jsonl` (mỗi dòng {"agent_last","text","open":true|false,"kind":"..."}) — chỉ áp dụng cho phần A.

    python scripts/eval_gate_open.py            # chỉ phần B (offline)
    python scripts/eval_gate_open.py --llm [--cases file.jsonl] [--max-cost N]   # thêm phần A
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)
os.chdir(CODE_DIR)

MAX_COST_VND = 300.0
Q_BUY = "Dạ sản phẩm này giá 1.690.000đ, còn hàng ạ. Anh/chị có muốn đặt không ạ?"
Q_INFO = "Dạ sản phẩm có bảo hành 12 tháng, đổi trả trong 7 ngày ạ."
Q_MORE = "Dạ anh/chị cần em hỗ trợ thêm gì không ạ?"
Q_TWO = "Dạ mẫu A giá 4.890.000đ phủ 30m², mẫu B giá 2.990.000đ phủ 20m², cả hai đều còn hàng ạ."
Q_SHIP = "Dạ bên em giao toàn quốc, 2–4 ngày ạ."

# (câu cuối của agent, lời khách, nên mở gate?, nhóm)
SCENES_A = [
    # cam kết rõ
    (Q_BUY, "ok lấy luôn", True, "cam_ket_ro"), (Q_BUY, "ừ đặt đi em", True, "cam_ket_ro"), (Q_BUY, "chốt cho anh một cái", True, "cam_ket_ro"),
    (Q_BUY, "được, em lên đơn giúp chị", True, "cam_ket_ro"), (Q_INFO, "vậy thì mình lấy", True, "cam_ket_ro"), (Q_TWO, "lấy mẫu B nhé", True, "cam_ket_ro"),
    (Q_BUY, "dat luon di em", True, "cam_ket_ro"), (Q_SHIP, "ok vậy anh đặt 1 cái", True, "cam_ket_ro"),
    # cam kết nhập nhằng / có điều kiện → không nên mở (an toàn)
    (Q_BUY, "chắc cũng lấy", False, "nhap_nhang"), (Q_BUY, "lấy thì lấy mà giá cao quá", False, "nhap_nhang"), (Q_BUY, "để anh nghĩ đã, chắc lấy", False, "nhap_nhang"),
    (Q_BUY, "nếu giảm 100k thì lấy", False, "nhap_nhang"), (Q_BUY, "ok lấy, mà giao được hôm nay không?", False, "nhap_nhang"),
    (Q_BUY, "cũng được", False, "nhap_nhang"), (Q_BUY, "thôi để xem rồi quyết", False, "nhap_nhang"),
    # so sánh / hỏi
    (Q_TWO, "mẫu nào tốt hơn vậy em?", False, "so_sanh_hoi"), (Q_TWO, "hai cái khác nhau chỗ nào", False, "so_sanh_hoi"), (Q_TWO, "mẫu A với B cái nào ít ồn hơn", False, "so_sanh_hoi"),
    (Q_BUY, "bảo hành bao lâu em", False, "so_sanh_hoi"), (Q_BUY, "có màu khác không", False, "so_sanh_hoi"), (Q_BUY, "giá này đã gồm ship chưa", False, "so_sanh_hoi"),
    # "ok" chỉ là tiếng đáp sau câu không liên quan đến mua hàng
    (Q_INFO, "ok", False, "ok_khong_lien_quan"), (Q_SHIP, "ừ", False, "ok_khong_lien_quan"), (Q_MORE, "ok em", False, "ok_khong_lien_quan"),
    (Q_INFO, "dạ vâng", False, "ok_khong_lien_quan"), (Q_SHIP, "được rồi", False, "ok_khong_lien_quan"), (Q_MORE, "không có gì thêm đâu", False, "ok_khong_lien_quan"),
    # mặc cả / từ chối / sửa thông tin
    (Q_BUY, "mắc quá, bớt 200k thì lấy luôn", False, "mac_ca"), (Q_BUY, "6tr8 lấy luôn nhé", False, "mac_ca"), (Q_BUY, "giảm thêm chút nữa đi em", False, "mac_ca"),
    (Q_BUY, "thôi chưa cần đâu", False, "tu_choi"), (Q_BUY, "để chị hỏi chồng đã", False, "tu_choi"), (Q_BUY, "không lấy nữa, cảm ơn", False, "tu_choi"),
    (Q_BUY, "không phải cái này, anh hỏi cái kia cơ", False, "sua_thong_tin"), (Q_BUY, "sai rồi, anh cần màu đen", False, "sua_thong_tin"),
]


def run_part_b() -> None:
    """Phần offline: bộ đọc GIẢ luôn báo cam kết; xem code chọn đối tượng nào."""
    from tests.test_order_gate import GateBase, NEW_PHONE
    from tests.test_reply_reader import ReaderLLM

    class R(GateBase):
        def runTest(self):
            pass

    COMMIT = {"order_intent": "commit", "intent_quote": "lấy", "only_answers": True}
    DATE = "2026-10-15"

    def q(sku):
        return ("pricing.get_quote", {"sku": sku, "on": DATE})

    scenes = [
        ("hai sản phẩm đơn đã báo giá, khách 'lấy' không nói cái nào", [[q("SKU-WF-RO10"), q("SKU-AP-X")]], "ok em lấy", {"open": False}),
        ("một sản phẩm đơn, sau đó search ra nhiều kết quả (liệt kê), khách 'lấy'", [[q("SKU-WF-RO10")], [("catalog.search", {"query": "máy lọc"})]], "ok em lấy", {"open": False}),
        ("sản phẩm đơn duy nhất đã báo giá, khách 'lấy'", [[q("SKU-WF-RO10")]], "ok em lấy", {"open": True, "sku": "SKU-WF-RO10"}),
        ("sản phẩm có biến thể đã bàn, khách nêu rõ 39 đen", [[("catalog.search", {"query": "sneaker urban classic"})]], "ok lấy 39 đen", {"open": True, "sku": "SKU-SN-CAS-39-DEN"}),
        ("sản phẩm có biến thể đã bàn, khách 'lấy' không nêu size/màu", [[("catalog.search", {"query": "sneaker urban classic"}), ("inventory.check", {"sku": "SKU-SN-CAS-39-DEN", "on": DATE})]], "ok em lấy",
         {"open": True, "sku": "SKU-SN-CAS", "note": "khách chưa nêu size/màu → mở ở bước HỎI size/màu bằng SKU cha (thiết kế lớp 5)"}),
        ("sản phẩm có biến thể + sản phẩm đơn, khách nêu biến thể", [[("catalog.search", {"query": "sneaker urban classic"}), q("SKU-WF-RO10")]], "lấy 39 đen",
         {"open": True, "sku": "SKU-SN-CAS-39-DEN"}),
        ("sản phẩm đơn + sản phẩm có biến thể, khách 'lấy' (cái nào?)", [[q("SKU-WF-RO10"), ("catalog.search", {"query": "sneaker urban classic"})]], "ok em lấy", {"open": False}),
    ]
    bad = 0
    print("\n=== B. TẦNG ĐỐI TƯỢNG (offline, bộ đọc giả luôn 'cam kết') ===")
    for title, prior_turns, text, exp in scenes:
        r = R()
        r.setUp()
        r.llm = r.orch.llm_client = ReaderLLM(lambda t: {})
        r.llm.reader = lambda t: {}
        for calls in prior_turns:
            r.turn(NEW_PHONE, "xem sản phẩm", calls, "Dạ vâng ạ.", date=DATE)
        r.llm.reader = lambda t: COMMIT
        _, _, meta = r.turn(NEW_PHONE, text, [], "Dạ vâng ạ.", date=DATE)
        go = meta["gate_open"]
        got_sku = go.get("sku")
        ok = go["opened"] == exp["open"] and (not exp["open"] or exp.get("sku") in (None, got_sku))
        bad += not ok
        print(f"{'ĐÚNG' if ok else 'SAI '} | kỳ vọng mở={exp['open']} {exp.get('sku', '')} | thực tế mở={go['opened']} sku={got_sku} lý do={go.get('reason')} object={go.get('object')} | {title}")
    print(f"→ {len(scenes) - bad}/{len(scenes)} cảnh đúng kỳ vọng")


def run_part_a(cases, max_cost: float) -> int:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.llm.client import LLMClient
    from src.llm.cost_tracker import BudgetExceeded
    from src.harness.reply_reader import read_reply
    llm = LLMClient()
    if not llm.available:
        print("Không có OPENAI_API_KEY — không đo được phần A.")
        return 2
    llm.cost_tracker.set_hard_cap(min(max_cost, MAX_COST_VND))
    rows = []
    print("\n=== A. TẦNG Ý ĐỊNH (LLM thật) ===")
    try:
        for agent, text, should, kind in cases:
            r = read_reply(llm, text, agent, {"stage": None}, guard="none")
            pred = bool(r and r.commits and not r.declines and not r.asks_question)
            rows.append({"kind": kind, "should": should, "pred": pred, "text": text})
            print(f"{'ĐÚNG' if pred == should else 'SAI '} | nên mở={should!s:5} mở={pred!s:5} | [{kind}] {text!r}" + ("" if r is None else f"  (intent={'commit' if r.commits else 'other'} stance={r.stance} asks={r.asks_question})"))
    except BudgetExceeded as e:
        print(f"[DỪNG] {e} — bảng chỉ tính {len(rows)}/{len(cases)} cảnh đã chạy")
    pos, neg = [r for r in rows if r["should"]], [r for r in rows if not r["should"]]
    print(f"\nBỏ sót mở (lỗi gốc): {sum(not r['pred'] for r in pos)}/{len(pos)}    Mở nhầm (rẻ): {sum(r['pred'] for r in neg)}/{len(neg)}")
    for kind in sorted({r["kind"] for r in rows}):
        k = [r for r in rows if r["kind"] == kind]
        print(f"  {kind:<20} sai {sum(r['pred'] != r['should'] for r in k)}/{len(k)}")
    from src.eval.runner import spent_vnd
    print(f"Chi phí: {spent_vnd(llm):,.1f} VND (trần lần này {min(max_cost, MAX_COST_VND):,.0f}; trần chỉ kiểm TRƯỚC mỗi lần gọi nên có thể vượt nhẹ)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", action="store_true", help="chạy thêm phần A với LLM thật (tốn tiền)")
    ap.add_argument("--cases", help="JSONL cảnh thật cho phần A")
    ap.add_argument("--max-cost", type=float, default=MAX_COST_VND)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("MEMORY_TRANSPORT", "local")
    cases = list(SCENES_A)
    if args.cases:
        with open(args.cases, encoding="utf-8") as f:
            cases += [(d["agent_last"], d["text"], bool(d["open"]), d.get("kind", "that")) for d in map(json.loads, filter(str.strip, f))]
    rc = run_part_a(cases, args.max_cost) if args.llm else 0       # A trước: phần B nạp helper của test, có thể xóa khóa API khỏi môi trường
    run_part_b()
    return rc


if __name__ == "__main__":
    sys.exit(main())
