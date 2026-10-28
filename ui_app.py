"""
Streamlit Dashboard cho Agent Harness Call Center — demo trực quan toàn bộ pipeline thật
(không mock riêng cho UI, dùng lại nguyên CallCenterHarnessPipeline).
Chạy: streamlit run ui_app.py

7 khu vực theo yêu cầu:
1. Khung chat trực tiếp (đóng vai Agent hoặc Khách hàng)
2. Audio upload -> ASR -> đẩy vào chat
3. Call Brief side panel
4. Memory Timeline
5. Tool Activity Log
6. Order/Callback status card
7. Evaluation Dashboard 1-click
"""
import os
import sys
import json
import tempfile
import subprocess
from datetime import datetime

try:
    import streamlit as st
except ImportError:
    print("Thiếu thư viện streamlit. Chạy: pip install -r requirements.txt")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()

import pandas as pd

from pipeline import CallCenterHarnessPipeline
from src.channels.normalizer import InputChannel
from src.identity.resolver import IdentityResolver

st.set_page_config(page_title="Agent Harness Call Center", layout="wide")


@st.cache_resource
def get_pipeline() -> CallCenterHarnessPipeline:
    """MỘT pipeline cho cả server Streamlit (không phải mỗi phiên trình duyệt một cái: mỗi cái mở thêm 2 tiến trình MCP). Kèm bộ quét nền chốt các cuộc
    gọi bị bỏ dở (khách đóng tab) sau IDLE_TIMEOUT_S giây (mặc định 1800)."""
    p = CallCenterHarnessPipeline(trace_file="runs/ui_session.jsonl")
    p.start_idle_sweeper(idle_seconds=float(os.environ.get("IDLE_TIMEOUT_S") or 1800))
    return p


def init_state():
    if "pipeline" not in st.session_state:
        st.session_state.pipeline = get_pipeline()
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []  # [{"role": "customer"|"agent", "text": ...}]
    if "pending_text" not in st.session_state:
        st.session_state.pending_text = ""
    if "call_date" not in st.session_state:
        st.session_state.call_date = "2026-10-15"
    if "phone" not in st.session_state:
        st.session_state.phone = "0984726714"
    if "call_no" not in st.session_state:
        st.session_state.call_no = 1


init_state()
pipeline = st.session_state.pipeline

st.title("📞 Agent Harness Call Center — Dashboard")

with st.sidebar:
    st.header("Thiết lập cuộc gọi")
    st.session_state.phone = st.text_input("Số điện thoại khách", value=st.session_state.phone)
    st.caption("Kênh chat: để trống = khách ẩn danh; khi khách đọc SĐT trong chat, hệ thống nối hồ sơ với số đó (liên thông kênh).")
    raw_date = st.text_input("Ngày cuộc gọi (YYYY-MM-DD)", value=st.session_state.call_date)
    from src.common.dates import normalize_call_date
    norm_date = normalize_call_date(raw_date)
    if norm_date is None:
        st.error("Ngày không hợp lệ (cần YYYY-MM-DD, vd 2026-10-15) — chưa gửi được tin nhắn.")
    else:
        st.session_state.call_date = norm_date
        # Đổi ngày hoặc số điện thoại giữa chừng = cuộc gọi MỚI: chốt cuộc cũ (bộ nhớ, episode) rồi xóa khung chat, tăng số cuộc.
        cur_key = (st.session_state.phone, norm_date)
        prev_key = st.session_state.get("active_key")
        if prev_key and prev_key != cur_key and st.session_state.chat_messages:
            try:
                res = pipeline.end_call(prev_key[0])
                st.session_state.call_no += 1
                st.session_state.chat_messages = []
                st.info(f"Đổi ngày/số điện thoại → đã chốt cuộc gọi trước ({prev_key[0]}, {prev_key[1]}) và bắt đầu cuộc gọi mới."
                        + (f" Ghi {len(res.get('memory_writes', []))} thay đổi bộ nhớ." if res.get("finalized") else ""))
            except Exception as e:
                st.warning(f"Không chốt được cuộc gọi trước: {e}")
        st.session_state.active_key = cur_key
    role = st.radio("Vai trò nhập liệu", ["Đóng vai Khách hàng (chạy pipeline thật)", "Đóng vai Agent (nhập tay, không chạy pipeline)"])
    channel = st.selectbox("Kênh", ["hotline", "zalo", "fanpage", "web_chat"])
    llm_status = "✅ ENABLED" if getattr(pipeline.llm_client, "available", False) else "⚠️ DISABLED (rule-based fallback)"
    st.caption(f"LLM: {llm_status}")
    if st.button("📴 Kết thúc cuộc gọi (chốt bộ nhớ: rào cản, phản đối, tóm tắt)"):
        try:
            res = pipeline.end_call(st.session_state.phone)
            st.session_state.call_no += 1
            st.session_state.chat_messages = []
            st.success("Đã chốt cuộc gọi: " + (f"ghi {len(res.get('memory_writes', []))} thay đổi bộ nhớ" if res.get("finalized") else res.get("reason", "")))
        except Exception as e:
            st.warning(f"Không chốt được cuộc gọi: {e}")

tab_chat, tab_brief, tab_timeline, tab_tools, tab_orders, tab_eval = st.tabs(
    ["💬 Chat & Audio", "🗂️ Call Brief", "🕐 Memory Timeline", "🛠️ Tool Activity Log", "📦 Đơn hàng/Lịch gọi lại", "📊 Evaluation"]
)

# -------------------------------------------------------------------- 1 & 2. Chat + Audio
with tab_chat:
    col_chat, col_upload = st.columns([3, 1])

    with col_upload:
        st.subheader("🎤 Upload audio")
        audio_file = st.file_uploader("File .wav/.mp3", type=["wav", "mp3"])
        if audio_file and st.button("Chuyển thành văn bản (ASR)"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_file.name)[1]) as tmp:
                tmp.write(audio_file.read())
                tmp_path = tmp.name
            try:
                from src.channels.offline_asr import transcribe_audio
                with st.spinner("Đang transcribe..."):
                    transcript = transcribe_audio(tmp_path)
                if transcript:
                    st.session_state.pending_text = transcript
                    st.success(f"Transcript: {transcript}")
                else:
                    st.warning("ASR không khả dụng hoặc transcribe thất bại — vui lòng nhập tay.")
            except Exception as e:
                st.warning(f"Lỗi ASR: {e} — vui lòng nhập tay.")
            finally:
                os.unlink(tmp_path)

    with col_chat:
        for msg in st.session_state.chat_messages:
            with st.chat_message("user" if msg["role"] == "customer" else "assistant"):
                st.write(msg["text"])

        user_input = st.chat_input("Nhập lời khách hàng...", key="chat_input") or st.session_state.pop("pending_text", "") or None

        if user_input and norm_date is None:
            st.warning("Sửa ngày cuộc gọi (YYYY-MM-DD) ở thanh bên rồi gửi lại.")
            user_input = None
        if user_input:
            st.session_state.chat_messages.append({"role": "customer", "text": user_input})
            if role.startswith("Đóng vai Khách hàng"):
                try:
                    ch = {"hotline": InputChannel.HOTLINE, "zalo": InputChannel.ZALO,
                          "fanpage": InputChannel.FANPAGE, "web_chat": InputChannel.WEB_CHAT}[channel]
                    with st.spinner("Agent đang xử lý..."):
                        result = pipeline.handle_incoming_request(
                            raw_input=user_input, contact_id=st.session_state.phone, channel=ch,
                            call_date=st.session_state.call_date, scenario_id="UI-SESSION",
                            call_name=f"call_{st.session_state.call_no}", turn_num=len(st.session_state.chat_messages)
                        )
                    st.session_state.chat_messages.append({"role": "agent", "text": result["answer"]})
                except Exception as e:
                    st.session_state.chat_messages.append({"role": "agent", "text": f"[Lỗi pipeline: {e}]"})
            st.rerun()

        if st.button("🗑️ Xóa hội thoại UI (không xóa memory đã lưu)"):
            st.session_state.chat_messages = []
            st.rerun()

# -------------------------------------------------------------------- 3. Call Brief
with tab_brief:
    st.subheader("Call Brief — tự động nạp theo số điện thoại")
    if st.button("🔄 Tải lại Call Brief"):
        st.rerun()
    try:
        from src.channels.normalizer import RequestNormalizer
        normalizer = RequestNormalizer()
        turn = normalizer.normalize(raw_text="", channel=InputChannel.HOTLINE, contact_id=st.session_state.phone)
        identity = pipeline.identity_resolver.resolve(turn)
        brief = pipeline.call_brief_builder.build(identity, current_call_date=st.session_state.call_date)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Khách hàng", f"{brief.honorific} {brief.customer_name}")
            st.metric("Sản phẩm đã tư vấn", brief.product_advised or "—")
            st.metric("Giá đã báo", f"{brief.price_quoted_vnd:,}đ" if brief.price_quoted_vnd else "—")
            st.metric("Số cuộc gọi trước", brief.previous_calls_count)
        with col2:
            st.write("**Rào cản (blocker):**", brief.blocker or "Không có")
            st.write("**Must NOT Ask:**", brief.must_not_ask or [])
            st.write("**Must carry over:**", brief.must_carry_over or [])
            if brief.stale_warnings:
                st.warning("\n".join(brief.stale_warnings))
        st.info(f"💬 Câu mở đầu đề xuất: \"{brief.suggested_opening}\"")
        with st.expander("Toàn bộ profile_facts"):
            st.json(brief.profile_facts)
    except Exception as e:
        st.error(f"Không tải được Call Brief: {e}")

# -------------------------------------------------------------------- 4. Memory Timeline
with tab_timeline:
    st.subheader("Dòng thời gian bộ nhớ (Episodic + Profile)")
    try:
        from src.channels.normalizer import RequestNormalizer
        normalizer = RequestNormalizer()
        turn = normalizer.normalize(raw_text="", channel=InputChannel.HOTLINE, contact_id=st.session_state.phone)
        identity = pipeline.identity_resolver.resolve(turn)
        cid = identity.customer_id

        rows = []
        ui_memory = pipeline.memory.as_caller("StreamlitUI")     # chỉ đọc (mcp-memory kiểm quyền theo caller)
        timeline = ui_memory.timeline(cid)
        for ep in timeline["episodes"]:
            rows.append({"time": ep.call_date, "type": "episode", "detail": f"{ep.channel} | {ep.customer_goal} | sp={ep.product_advised} | giá={ep.price_quoted_vnd} | outcome={ep.outcome}"})
        for key, versions in timeline["versions"].items():
            for fact in versions:
                status = "superseded" if fact.superseded else "active"
                rows.append({"time": fact.observed_at, "type": f"profile_fact ({status})", "detail": f"{key} = {fact.value}"})

        if rows:
            df = pd.DataFrame(rows).sort_values("time")
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("Chưa có dữ liệu bộ nhớ cho khách này.")
    except Exception as e:
        st.error(f"Lỗi tải Memory Timeline: {e}")

# -------------------------------------------------------------------- 5. Tool Activity Log
with tab_tools:
    st.subheader("Nhật ký hoạt động MCP Tool")
    audit_log = pipeline.mcp_gateway.audit_log
    if audit_log:
        rows = [{"call_id": a["call_id"], "tool": a["tool"], "caller": a["caller"],
                 "args": json.dumps(a["args"], ensure_ascii=False),
                 "result": json.dumps(a.get("result", {}), ensure_ascii=False)[:200],
                 "duration_ms": a.get("duration_ms")} for a in reversed(audit_log)]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("Chưa có tool call nào được ghi nhận trong phiên này.")

# -------------------------------------------------------------------- 6. Order/Callback card
with tab_orders:
    st.subheader("Trạng thái đơn hàng / Lịch gọi lại gần nhất")
    order_calls = [a for a in pipeline.mcp_gateway.audit_log if a["tool"] in ("order.create", "schedule.callback")]
    if order_calls:
        latest = order_calls[-1]
        res = latest.get("result", {})
        if latest["tool"] == "order.create":
            c1, c2, c3 = st.columns(3)
            c1.metric("Mã đơn", res.get("order_id", "—"))
            c2.metric("Tổng tiền", f"{res.get('total_vnd', 0):,}đ")
            c3.metric("Dự kiến giao", res.get("estimated_delivery", "—"))
            if res.get("needs_confirmation_call"):
                st.warning("⚠️ Đơn cần gọi xác nhận trước khi giao (COD giá trị cao).")
            if res.get("error"):
                st.error(f"Lỗi tạo đơn: {res['error']}")
        else:
            c1, c2 = st.columns(2)
            c1.metric("Mã lịch gọi lại", res.get("callback_id", "—"))
            c2.metric("Thời gian", res.get("callback_at", "—"))
            if res.get("moved_from"):
                st.info(f"Lịch đã tự dời từ {res['moved_from']} (trùng ngày nghỉ/ngoài giờ).")
    else:
        st.info("Chưa có đơn hàng/lịch gọi lại nào trong phiên này.")

# -------------------------------------------------------------------- 7. Evaluation Dashboard
with tab_eval:
    st.subheader("Đánh giá tự động (RQR / CCR / TSR / HR / Latency)")
    st.caption("Lưu ý: chạy LLM thật cho 7 kịch bản × 2 cấu hình — tốn thời gian và chi phí API thật.")
    if st.button("▶️ Chạy Evaluation"):
        with st.spinner("Đang chạy run_eval.py (có thể mất vài phút vì gọi LLM thật)..."):
            proc = subprocess.run([sys.executable, "run_eval.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        st.text_area("Log", proc.stdout + "\n" + proc.stderr, height=200)

    report_path = os.path.join("runs", "report.json")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        def pct(v):
            return "—" if v is None else f"{v:.1f}%"

        rows = [
            {"Chỉ số": "Repeat-Question Rate", "Baseline": pct(report["baseline"]["repeat_question_rate"]["value"]),
             "Hệ thống": pct(report["system"]["repeat_question_rate"]["value"]), "Ngưỡng BTC": "giảm ≥40%"},
            {"Chỉ số": "Context Carryover Rate", "Baseline": pct(report["baseline"]["context_carryover_rate"]["value"]),
             "Hệ thống": pct(report["system"]["context_carryover_rate"]["value"]), "Ngưỡng BTC": "càng cao càng tốt"},
            {"Chỉ số": "Task Success Rate", "Baseline": pct(report["baseline"]["task_success_rate"]["value"]),
             "Hệ thống": pct(report["system"]["task_success_rate"]["value"]), "Ngưỡng BTC": "≥70%"},
            {"Chỉ số": "Hallucination Rate (giá/KM)", "Baseline": pct(report["baseline"]["hallucination_rate"]["price_promo_only"]["value"]),
             "Hệ thống": pct(report["system"]["hallucination_rate"]["price_promo_only"]["value"]), "Ngưỡng BTC": "≤5%"},
        ]
        df = pd.DataFrame(rows)

        def color_pass(row):
            sys_val_str = row["Hệ thống"]
            try:
                val = float(sys_val_str.rstrip("%"))
            except ValueError:
                return [""] * len(row)
            threshold_ok = {
                "Task Success Rate": val >= 70,
                "Hallucination Rate (giá/KM)": val <= 5,
            }.get(row["Chỉ số"])
            color = "background-color: #c6f6d5" if threshold_ok else ("background-color: #fed7d7" if threshold_ok is False else "")
            return ["", "", f"{color}", ""]

        st.dataframe(df.style.apply(color_pass, axis=1), width="stretch", hide_index=True)
        st.caption(f"Latency hệ thống: p95 = {report['system']['latency']['total']['p95_ms']}ms (ngưỡng ≤8000ms)")
        with st.expander("Chi tiết report.json"):
            st.json(report)
    else:
        st.info("Chưa có runs/report.json — bấm 'Chạy Evaluation' để tạo.")
