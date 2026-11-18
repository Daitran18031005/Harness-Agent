"""Thử WebSocket mode vs HTTP stream (Responses API), gpt-4o-mini fast: một lượt 2 vòng (gọi tool -> trả lời).
Đo: thời gian tới sự kiện đầu có nội dung của từng vòng (gọi tool / chữ), và tổng."""
import json, statistics as st, time
from openai import OpenAI

MODEL, TIER = "gpt-4o-mini", "fast"
TOOLS = [{"type": "function", "name": "inventory_check", "description": "Kiểm tồn kho và giá một sản phẩm",
          "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]}}]
SYS = "Bạn là nhân viên bán hàng. Khi khách hỏi còn hàng/giá, BẮT BUỘC gọi inventory_check rồi trả lời một câu ngắn."
Q = "Máy lọc AirPure X (SKU-AP-X) còn hàng không em, giá bao nhiêu?"
RESULT = json.dumps({"in_stock": True, "price_vnd": 4890000})
FIRST = ("response.output_text.delta", "response.function_call_arguments.delta")
c = OpenAI()


def http_turn():
    t0 = time.perf_counter(); first = []
    def run(**kw):
        ts = time.perf_counter(); f = None; done = None
        for ev in c.responses.create(model=MODEL, service_tier=TIER, stream=True, tools=TOOLS, **kw):
            if f is None and ev.type in FIRST: f = time.perf_counter() - ts
            if ev.type == "response.completed": done = ev.response
        return f, done
    f1, r1 = run(instructions=SYS, input=Q, store=True)
    call = next(o for o in r1.output if o.type == "function_call")
    f2, _ = run(instructions=SYS, previous_response_id=r1.id, store=True,
                input=[{"type": "function_call_output", "call_id": call.call_id, "output": RESULT}])
    return f1, f2, time.perf_counter() - t0


def ws_turn(conn):
    t0 = time.perf_counter()
    def run(**kw):
        ts = time.perf_counter(); f = None
        conn.response.create(model=MODEL, service_tier=TIER, tools=TOOLS, store=False, **kw)
        for ev in conn:
            if f is None and ev.type in FIRST: f = time.perf_counter() - ts
            if ev.type == "response.completed": return f, ev.response
            if ev.type in ("response.failed", "response.incomplete", "error"): raise RuntimeError(ev.to_json())
    f1, r1 = run(instructions=SYS, input=Q)
    call = next(o for o in r1.output if o.type == "function_call")
    f2, _ = run(instructions=SYS, previous_response_id=r1.id,
                input=[{"type": "function_call_output", "call_id": call.call_id, "output": RESULT}])
    return f1, f2, time.perf_counter() - t0


def show(name, rows):
    f1 = [r[0] * 1000 for r in rows]; f2 = [r[1] * 1000 for r in rows]; tot = [r[2] * 1000 for r in rows]
    print(f"{name:10s} vòng1 tới gọi tool p50 {st.median(f1):.0f} | vòng2 tới chữ đầu p50 {st.median(f2):.0f} | cả lượt p50 {st.median(tot):.0f} ms | từng lượt {[round(x) for x in tot]}")


http_turn()                                     # làm ấm kết nối
H = [http_turn() for _ in range(4)]
with c.responses.connect() as conn:
    ws_turn(conn)                               # làm ấm
    W = [ws_turn(conn) for _ in range(4)]
show("HTTP", H); show("WebSocket", W)
