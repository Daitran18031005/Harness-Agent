"""
Đo bộ đọc lời khách bằng LLM THẬT (src/harness/reply_reader.py) trên các câu khách ĐA DẠNG, gồm cả cách nói không chứa từ khóa quen thuộc.
Mỗi mẫu: (câu cuối của agent, lời khách, kỳ vọng). Báo số đúng/sai từng mẫu — đây là phép đo, không phải test đạt/không đạt.
Trần chi phí CỨNG trong mã (`MAX_COST_VND`). Cần OPENAI_API_KEY; tốn tiền → chỉ chạy khi người dùng duyệt.

    python scripts/eval_reply_reader.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

MAX_COST_VND = 100.0
READBACK = "Dạ em đọc lại đơn: 1 giày RunLite 2 Pro size 38 màu đen, tổng 1.521.000đ, giao cho Đại, COD. Anh xác nhận đặt đơn này giúp em nhé?"
PHONE_Q = "Dạ em xin xác nhận lại số điện thoại 0986886113, đúng không ạ?"
NAME_Q = "Mình cho em xin tên người nhận hàng ạ?"
PAY_Q = "Mình thanh toán COD hay chuyển khoản ạ?"
OPEN_Q = "Anh/chị cho em xin tên người nhận, số điện thoại (nếu khác số đang gọi) và địa chỉ giao hàng ạ?"

# (agent, khách, kỳ vọng: stance / affirmed ⊇ / name / payment / only_answers)
CASES = [
    (READBACK, "ừ chốt đi em", dict(stance="agree")),
    (READBACK, "được rồi em cứ lên đơn cho anh", dict(stance="agree")),
    (READBACK, "thôi cũng được, lấy luôn", dict(stance="agree")),
    (READBACK, "ờ thì cứ vậy đi", dict(stance="agree")),
    (READBACK, "đúng hết rồi nha em", dict(stance="agree")),
    (READBACK, "khoan, cho anh đổi sang màu xám đã", dict(stance="other", only_answers=False)),
    (READBACK, "giao mất mấy ngày vậy em?", dict(stance="other", only_answers=False)),
    (READBACK, "hơi mắc, bớt cho anh 100k nữa thì chốt", dict(stance="decline")),
    (READBACK, "để chị hỏi chồng đã rồi gọi lại", dict(stance="decline")),
    (READBACK, "chưa cần nữa, cảm ơn em", dict(stance="decline")),
    (READBACK, "ừm", dict(stance="other")),
    (READBACK, "sai tên rồi, giao cho Hà chứ không phải Đại", dict(stance="other")),
    (PHONE_Q, "ừ đúng rồi", dict(affirmed="recipient_phone")),
    (PHONE_Q, "ừa cái số em đang gọi đây nè", dict(affirmed="recipient_phone")),
    (PHONE_Q, "vẫn số đó, khỏi hỏi lại", dict(affirmed="recipient_phone")),
    (PHONE_Q, "không phải, gửi qua số 0912345678 nhé", dict(affirmed=None, stance="other")),
    (PHONE_Q, "hmm", dict(stance="other")),
    (READBACK, "ờ... à", dict(stance="other")),
    (READBACK, "địa chỉ sai rồi em, phải là 20 Lê Lợi cơ", dict(stance="other")),
    (NAME_Q, "bác Tư nhé", dict(name="Tư", only_answers=True)),
    (OPEN_Q, "đúng sdt, 45/1 đường 10 phường linh đông, Đại", dict(affirmed="recipient_phone", name="Đại")),
    (OPEN_Q, "số này luôn nha. giao về 12 Nguyễn Trãi Thanh Xuân Hà Nội, em tên Lan", dict(affirmed="recipient_phone", name="Lan")),
    (OPEN_Q, "cứ giao số máy này thôi, người nhận là chị Hoa", dict(affirmed="recipient_phone", name="Hoa")),
    (NAME_Q, "đại", dict(name="Đại", only_answers=True)),
    (NAME_Q, "Trần Quang Minh ạ", dict(name="Trần Quang Minh", only_answers=True)),
    (NAME_Q, "tên là thu, gửi hộ chị cái ví luôn nhé", dict(name="Thu")),
    (NAME_Q, "bên em có size 41 không?", dict(name=None, only_answers=False)),
    (PAY_Q, "cod nha", dict(payment="COD", only_answers=True)),
    (PAY_Q, "nhận hàng rồi mới trả tiền", dict(payment="COD")),
    (PAY_Q, "anh chuyển khoản trước cho chắc", dict(payment="bank")),
    (PAY_Q, "quét mã qr được không em", dict(payment="bank")),
    (PAY_Q, "momo đi", dict(payment="momo")),
    (PAY_Q, "đại, COD", dict(name="Đại", payment="COD")),
    (PAY_Q, "thanh toán sao cũng được, em chọn giúp", dict(payment=None)),
]


def check(r, exp):
    bad = []
    if "stance" in exp and r.stance != exp["stance"]:
        bad.append(f"stance={r.stance}")
    if "only_answers" in exp and r.only_answers != exp["only_answers"]:
        bad.append(f"only_answers={r.only_answers}")
    if "affirmed" in exp and (bool(r.affirmed) if exp["affirmed"] is None else exp["affirmed"] not in r.affirmed):
        bad.append(f"affirmed={r.affirmed}")
    if "name" in exp and (r.recipient_name or "").lower() != (exp["name"] or "").lower():
        bad.append(f"name={r.recipient_name}")
    if "payment" in exp and r.payment != exp["payment"]:
        bad.append(f"payment={r.payment}")
    return bad


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.llm.client import LLMClient
    from src.llm.cost_tracker import BudgetExceeded
    from src.harness.reply_reader import read_reply
    llm = LLMClient()
    if not llm.available:
        print("Không có OPENAI_API_KEY — không đo được.")
        return 2
    llm.cost_tracker.set_hard_cap(MAX_COST_VND)
    ok = 0
    try:
        for agent, text, exp in CASES:
            r = read_reply(llm, text, agent, {})
            bad = ["(không đọc được)"] if r is None else check(r, exp)
            ok += not bad
            print(f"{'ĐÚNG' if not bad else 'SAI '} | {text!r} → {None if r is None else (r.stance, r.only_answers, r.affirmed, r.recipient_name, r.payment)}" + (f"  ✗ {bad}" if bad else ""))
    except BudgetExceeded as e:
        print(f"[DỪNG] {e}")
        return 3
    from src.eval.runner import spent_vnd
    print(f"\nĐúng {ok}/{len(CASES)}. Chi phí: {spent_vnd(llm):,.1f} VND (trần cứng {MAX_COST_VND:,.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
