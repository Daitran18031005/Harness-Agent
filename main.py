"""
Mô phỏng 1 Request hoàn chỉnh qua toàn bộ Pipeline Agent Harness Call Center
Theo đúng kiến trúc và luồng dữ liệu của hệ thống:
1. Normalize (ASR, Teencode, ITN, PII Mask)
2. Identity Resolver (crm.get_customer qua MCP)
3. Call Brief Builder (Lịch sử, Blocker, Must Not Ask, Opening tiếp nối)
4. Harness Orchestrator:
   - MCP Tool Gateway: Pricing (Giá từ tool, không bịa giá) & Order Create
   - Module chuyên biệt trong tiến trình (Sales Advisor, Policy Compliance; chỉ dùng ở nhánh dự phòng khi mất LLM — không phải giao thức A2A)
   - Bộ nhớ: Working, Episodic, Profile, Semantic RAG — qua MCP server mcp-memory (nơi ghi duy nhất)
5. Guardrail & Fallback: Kiểm duyệt an toàn, chặn bịa giá
6. Response & Trace Log JSONL
"""
import json
from dotenv import load_dotenv
load_dotenv()

from pipeline import CallCenterHarnessPipeline
from src.channels.normalizer import InputChannel
from scripts.seed_demo_db import seed_demo
from src.memory.sqlite_store import demo_db_path, is_production_db


def main():
    print("=" * 85)
    print("MÔ PHỎNG 1 REQUEST HOÀN CHỈNH: RUNTIME AGENT HARNESS CALL CENTER")
    print("=" * 85)

    # Khởi tạo Pipeline
    # DB riêng cho demo: data/demo.db (ghi đè bằng HARNESS_DB_PATH). KHÔNG đụng DB mặc định data/harness_memory.db.
    db_path = demo_db_path()
    pipeline = CallCenterHarnessPipeline(trace_file="runs/demo.jsonl",  # KHÔNG ghi vào runs/full.jsonl (file chấm điểm)
                                         db_path=db_path)
    print(f"DB demo: {db_path}")

    # Lịch sử cuộc 1 của khách Hoa (C001): seed IDEMPOTENT (chạy main.py nhiều lần không nhân bản dữ liệu) và chỉ ghi
    # dưới MỘT mã khách C001 — xem scripts/seed_demo_db.py. Khách gọi bằng SĐT được nhận diện ra C001 qua CRM.
    customer_phone = "0984726714"
    # Reset khách demo -> mỗi lần chạy cho cùng một kết quả — nhưng KHÔNG BAO GIỜ reset DB mặc định (production).
    seed_demo(pipeline.memory, reset=not is_production_db(db_path), operator=pipeline.memory.as_caller("Operator"))

    # -----------------------------------------------------------------------------------------
    # 2 NGÀY SAU (2026-10-17): KHÁCH HÀNG GỌI LẠI (CALL 2)
    # Khách nói: "Alo em, hôm trc c có hỏi máy lọc y. Ông xã c đồng ý r, lên đơn cho c nhé!"
    # -----------------------------------------------------------------------------------------
    raw_customer_input = "Alo em, hôm trc c có hỏi máy lọc y. Ông xã c đồng ý r, lên đơn cho c nhé!"
    print(f"\n[1. RAW INPUT]:\n    Text: \"{raw_customer_input}\"\n    Kênh: Hotline | SĐT: {customer_phone}")

    result = pipeline.handle_incoming_request(
        raw_input=raw_customer_input,
        contact_id=customer_phone,
        channel=InputChannel.HOTLINE,
        is_audio=True,
        call_date="2026-10-17",
        scenario_id="SAMPLE-01",
        call_name="call_2",
        turn_num=1
    )

    print(f"\n[2. TIẾP NHẬN & CHUẨN HÓA (NORMALIZE)]:")
    print(f"    Normalized: \"{result['normalized_input']}\"")

    print(f"\n[3. IDENTITY RESOLUTION & CALL BRIEF BUILDER]:")
    print(f"    Customer ID: {result['customer_id']}")
    brief = result['call_brief']
    price_str = f"{brief['price_quoted_vnd']:,}đ" if brief.get('price_quoted_vnd') else "chưa có"
    print(f"    Sản phẩm đã tư vấn: {brief['product_advised']} ({price_str})")
    print(f"    Rào cản cũ: {brief['blocker']}")
    print(f"    Must NOT Ask (Cấm hỏi lại): {brief['must_not_ask']}")
    print(f"    Opening Xác Nhận Tiếp Nối đề xuất: \"{brief['suggested_opening']}\"")

    print(f"\n[4. HARNESS ORCHESTRATOR & MCP TOOLS]:")
    for tc in result['tool_calls']:
        print(f"    -> Gọi MCP Tool: {tc['tool']}")
        print(f"       Args: {tc['args']}")
        print(f"       Result: {tc['result']}")

    print(f"\n[5. GUARDRAIL & FINAL RESPONSE (ANSWER)]:")
    print(f"    \"{result['answer']}\"")

    print(f"\n[6. TURN TRACE JSONL LOGGED]:")
    print(json.dumps(result['trace'], ensure_ascii=False, indent=2))

    # Kết thúc cuộc gọi: chốt episode (+ trích slot khó nếu có LLM), rồi đóng DB (checkpoint WAL).
    end = pipeline.end_call(customer_phone)
    print()
    print(f"[7. CHỐT CUỘC GỌI] {end['trigger']}: episode={end['episode'].summary if end.get('episode') else None} | LLM trích slot khó: {end['llm_called']}")
    pipeline.close()
    print("=" * 85)


if __name__ == "__main__":
    main()
