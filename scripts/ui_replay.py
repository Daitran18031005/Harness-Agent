"""
Phát lại các cuộc hội thoại gõ tay trên UI demo (lỗi người dùng thấy ngày 2026-10-22) qua pipeline THẬT + LLM thật, để xem agent còn mắc lỗi không.
KHÔNG dùng lời khách chuẩn do mã viết ra: các câu dưới đây chép nguyên văn từ ảnh chụp UI (viết thường, tên cuối câu địa chỉ, mặc cả, từ chối, đổi kênh).
Trần chi phí CỨNG nằm trong mã (`REPLAY_MAX_COST_VND`).

    python scripts/ui_replay.py [--only A B C]
"""
import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

REPLAY_MAX_COST_VND = 550.0

CONVERSATIONS = {
    "A": ("Hàng hết + địa chỉ kèm tên + tên gõ thường (ảnh 1–3)", "0986886113", "hotline", "2026-10-15", [
        "cho mình hỏi giày chạy bộ RunLite 2 Pro", "có xám 37 ko?", "vậy cho tôi 38 xám đi", "thế 38 đen có không?", "ok lấy 38 đen",
        "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại", "đại, COD", "ok chốt"]),
    "B": ("Mặc cả + từ chối + rào cản (ảnh 5–6)", "", "zalo", "2026-10-15", [
        "máy lọc nước 10 lõi giá như nào?", "mắc quá vậy? 6tr8 lấy luôn", "không, mắc quá tôi muốn giảm thêm 90k", "hiện tại chưa cần, sẽ gọi lại sau", "tôi tên Đại"]),
    "C": ("Khách nói đã liên hệ kênh khác (ảnh 7–9)", "0399401064", "hotline", "2026-10-30", [
        "tôi là Đại, hôm trước tôi có gọi để tư vấn sản phẩm máy lọc nước 10 lõi, giờ tôi muốn hỏi sản phẩm đó còn hàng không"]),
    "D": ("Số nói bằng chữ (mười lõi, hai mươi mét vuông, mười lăm tháng mười)", "0986886114", "hotline", "2026-10-15", [
        "máy lọc nước mười lõi còn hàng không", "phòng nhà tôi hai mươi mét vuông, có bé ba tuổi"]),
    "E": ("Đổi ngày = cuộc mới; Call Brief cuộc 2 mang blocker/tên/xưng hô (dòng '@ngày' = đổi ngày cuộc gọi)", "0986886115", "hotline", "2026-10-15", [
        "chị tên Lan, chị hỏi máy lọc không khí cho phòng 20m2", "giá cao quá, để chị hỏi chồng đã", "@2026-10-17", "alo em, chị gọi lại đây"]),
    "F": ("Sản phẩm KHÔNG có biến thể: hỏi giá → cam kết → địa chỉ → COD → chốt (đường mở gate bằng code cho SKU đơn)", "0986886116", "hotline", "2026-10-15", [
        "máy lọc nước 10 lõi giá như nào?", "ok lấy luôn", "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại", "COD", "ok chốt"]),
    "G": ("Chuyển máy theo lý do: lượt 1 hỏi thông số (KHÔNG chuyển), lượt 2 hỏi y tế/an toàn cho trẻ (chuyển ngay, không cần khách yêu cầu)", "0986886117", "hotline", "2026-10-15", [
        "máy lọc không khí AirPure Y có khóa trẻ em không?", "bé nhà tôi đang uống thuốc hen, dùng máy này có an toàn không?"]),
    "H": ("Xóa dữ liệu cá nhân (ca ngoài phạm vi: chuyển ngay, không cần khách yêu cầu chuyển máy)", "0986886118", "hotline", "2026-10-15", [
        "tôi muốn xóa hết thông tin cá nhân của tôi trong hệ thống của shop"]),
    "I": ("Khiếu nại đơn ĐÃ ĐẶT chưa nhận được hàng (khách C032 Tâm, đơn OD301177 đang shipping từ 03/10; ca ngoài phạm vi)", "0965384535", "hotline", "2026-10-25", [
        "đơn OD301177 của tôi đặt từ hôm 3/10 mà tới giờ vẫn chưa nhận được hàng, sao vậy?"]),
    "J": ("Mặc cả rồi ĐỒNG Ý chuyển máy (ca giá: lượt 1 phải bị chặn chuyển, lượt 2 khách đồng ý đề nghị → accepted_offer)", "0986886119", "hotline", "2026-10-15", [
        "máy lọc nước 10 lõi, mắc quá, giảm cho tôi còn 6tr8 được không?", "ừ, nhờ nhân viên hỗ trợ giá giúp tôi"]),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", default=list(CONVERSATIONS))
    ap.add_argument("--max-cost", type=float, default=REPLAY_MAX_COST_VND, help="trần chi phí VND cho lần chạy này (không bao giờ vượt trần cứng trong mã)")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("MCP_TRANSPORT", "stdio")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CODE_DIR, ".env"))
    from src.channels.normalizer import InputChannel
    from src.llm.cost_tracker import BudgetExceeded
    from pipeline import CallCenterHarnessPipeline
    d = tempfile.mkdtemp()
    pipe = CallCenterHarnessPipeline(trace_file=os.path.join(d, "t.jsonl"), db_path=os.path.join(d, "t.db"))
    if not getattr(pipe.llm_client, "available", False):
        print("Không có OPENAI_API_KEY — không phát lại được với LLM thật.")
        return 2
    pipe.llm_client.cost_tracker.set_hard_cap(min(args.max_cost, REPLAY_MAX_COST_VND))
    ch_of = {"hotline": InputChannel.HOTLINE, "zalo": InputChannel.ZALO}
    try:
        for key in args.only:
            title, phone, channel, date, lines = CONVERSATIONS[key]
            print(f"\n===== {key}: {title} — kênh {channel}, SĐT {phone or '(trống)'}, ngày {date} =====")
            call_no, i, cur_date = 1, 0, date
            for text in lines:
                if text.startswith("@"):                     # đổi ngày cuộc gọi = cuộc gọi MỚI (pipeline tự chốt cuộc cũ)
                    cur_date, call_no, i = text[1:], call_no + 1, 0
                    print(f"--- đổi ngày sang {cur_date} → call_{call_no} ---")
                    continue
                i += 1
                r = pipe.handle_incoming_request(raw_input=text, contact_id=phone, channel=ch_of[channel], call_date=cur_date, scenario_id=f"REPLAY-{key}",
                                                 call_name=f"call_{call_no}", turn_num=i)
                gate = [e["action"] for e in ((r["trace"] or {}).get("order_gate") or [])]
                tools = [(t["name"], (t.get("args") or {}).get("sku") or (t.get("args") or {}).get("query"),
                          (t.get("result") or {}).get("in_stock", (t.get("result") or {}).get("error"))) for t in r["tool_calls"]]
                rr = (r["trace"] or {}).get("reply_reading") or {}
                read = ""
                if rr.get("source") == "llm":
                    read = (f"\n        [reader: llm stance={rr['stance']} conf={rr['confidence']} intent={rr.get('order_intent')} asks={rr.get('asks_question')} prior={rr.get('prior_contact')} only_answers={rr['only_answers']} affirmed={rr['affirmed']} "
                            f"name={rr['recipient_name']} pay={rr['payment']} guard={rr['guard']} calls={rr['llm_calls']} {rr['vnd_cost']}VND {rr['latency_ms']}ms]")
                elif rr:
                    read = f"\n        [reader: {rr.get('source')}]"
                go = (r["trace"] or {}).get("gate_open") or {}
                opened = f"\n        [gate_open: {go.get('reason')} intent={go.get('intent')} object={go.get('object')} excl={go.get('exclusions')}]" if go.get("intent") else ""
                hc = (r["trace"] or {}).get("handoff_check")
                handoff = f"\n        [handoff_check: authorized={hc['authorized']} category={hc.get('category')} basis={hc['basis']} quote={hc['quote']!r} {hc['vnd_cost']}VND]" if hc else ""
                print(f"KHÁCH : {text}\nAGENT : {r['answer']}" + (f"\n        [order_gate: {gate}]" if gate else "") + read + opened + handoff + (f"\n        [tool: {tools}]" if tools else ""))
            ident = r["customer_id"]
            facts = pipe.memory.as_caller("EvalRunner").get_profile_facts(ident) if ident else {}
            show = {k: facts[k] for k in ("customer_name", "honorific", "blocker", "objection", "product_advised", "order_id") if k in facts}
            print(f"  → bộ nhớ sau cuộc {key}: {show}")
            b = r.get("call_brief") or {}
            if b.get("previous_calls_count"):
                print(f"  → Call Brief cuộc {call_no}: blocker={b.get('blocker')!r} tên={b.get('customer_name')!r} xưng hô={b.get('honorific')!r} mở đầu={str(b.get('suggested_opening'))[:150]!r}")
            if key == "D":
                print(f"  → bản chuẩn hóa lượt 1: {r.get('normalized_input')!r}")
    except BudgetExceeded as e:
        print(f"[DỪNG] {e}")
        return 3
    from src.eval.runner import spent_vnd
    print(f"\nChi phí: {spent_vnd(pipe.llm_client):,.1f} VND (trần lần này {min(args.max_cost, REPLAY_MAX_COST_VND):,.0f}, trần cứng {REPLAY_MAX_COST_VND:,.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
