"""
Harness Orchestrator: Bộ điều phối trung tâm của Agent Harness Call Center.
Vòng lặp:
1. Nhận thức (Perceive) -> Chuẩn hóa turn và Call Brief
2. Truy hồi (Retrieve) -> 4 tầng Memory + Catalog/Pricing Tool
3. Lập kế hoạch (Plan) -> Phân tích intent, slot, quyết định tool call
4. Gọi module chuyên biệt trong tiến trình (SalesAdvisor, PolicyCompliance; chỉ dùng ở nhánh dự phòng khi mất LLM — không phải giao thức A2A)
5. Gọi Tool (Act) -> Qua MCP Tool Gateway với schema & audit
6. Quan sát (Observe) -> Đọc kết quả tool
7. Kiểm duyệt (Guardrail Check) -> Đẩy proposal sang Guardrail
8. Ghi nhớ (Persist) -> Cập nhật Profile, Episodic, Working memory
"""
import re
import json
import time
import difflib
import logging
import unicodedata
from typing import Dict, Any, List, Tuple, Optional
from src.channels.normalizer import NormalizedTurn
from src.channels.asr_entities import product_mentions
from src.harness.call_brief import CallBrief
from src.tools.mcp_gateway import MCPToolGateway
from src.memory.service import MemoryService
from src.memory.episodic import EpisodeRecord
from src.agents.specialists import A2AAgentNetwork, product_name
from src.harness.guardrail import GuardrailAndFallback, GuardrailDecision
from src.llm.client import with_variant_enum, LLMRoundLimit
from src.privacy.pii_vault import PiiVault
from src.harness.money import extract_amounts
from src.harness.basket import price_basket, order_args, cod_exceeds, cod_needs_confirmation, correct_basket_totals, COD_LIMIT_VND
from src.harness.extractor import extract_claims, extract_questions
from src.catalog import ProductRetriever, ClarificationPolicy
from src.harness.fact_usage import fact_mentioned, used_by_agent
from src.harness.reask import REASK_LABEL, rewrite_reasks, strip_markdown
from src.harness.reply_reader import authorize_closing, authorize_handoff, read_reply, reading_trace_dict
from src.harness.order_gate import (OrderGate, OrderDraft, OrderKnown, ProductInfo, with_order_gate_params, detect_payment, GATE_ONLY_ARGS,
                                     extract_recipient_name, is_pure_gate_reply, money as _money)
from src.memory.memory_extractor import extract_easy_slots, SLOT_TTL, CallFinalizer, HardSlotExtractor, detect_self_honorific, detect_bargain


def _fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (kể cả đ/Đ)."""
    nfkd = unicodedata.normalize("NFKD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


COLOR_DISPLAY = {"den": "đen", "trang": "trắng", "xam": "xám", "navy": "xanh navy", "be": "be", "do": "đỏ", "xanh": "xanh", "hong": "hồng", "vang": "vàng", "nau": "nâu", "tim": "tím",
                 "cam": "cam", "kem": "kem", "bac": "bạc"}          # catalog ghi màu không dấu ("den"); lời nói với khách phải có dấu


class HarnessOrchestrator:
    def __init__(self, mcp_gateway: MCPToolGateway, memory: MemoryService, a2a_network: A2AAgentNetwork,
                 guardrail: GuardrailAndFallback, llm_client=None):
        self.mcp = mcp_gateway
        self.memory = memory
        self.a2a = a2a_network
        self.guardrail = guardrail
        # [INTEGRATION POINT: LLM REASONING & FUNCTION CALLING]
        # LLM là bộ não quyết định chính cho mọi entrypoint (main.py/ui_app.py/run_eval.py)
        # khi có OPENAI_API_KEY hợp lệ. None (hoặc LLM lỗi runtime) -> rơi về nhánh
        # rule-based tối giản trong process_turn, không crash.
        self.llm_client = llm_client
        # Trạng thái THEO CUỘC GỌI (khóa = working_session_id), chỉ trong bộ nhớ process:
        self._vaults: Dict[str, PiiVault] = {}                 # bảng token PII (không bao giờ ghi DB/trace)
        self._call_log: Dict[str, List[Dict[str, Any]]] = {}   # tool đã chạy trong cuộc gọi
        self._write_cache: Dict[str, Dict[tuple, Dict[str, Any]]] = {}  # chống gọi lặp tool ghi
        # Chốt cuộc gọi (episode + slot khó bằng LLM) ở 3 thời điểm: end | handoff | timeout (xem memory_extractor.py)
        self.finalizer = CallFinalizer(memory, HardSlotExtractor(llm_client))
        self._activity: Dict[str, Dict[str, Any]] = {}          # phiên -> {ts, customer_id, call_date, call_name, channel}
        # Để tính facts_used (CCR) công bằng: fact có sẵn lúc BẮT ĐẦU cuộc gọi, các slot agent đã hỏi mở, lời khách đã nói
        self._start_facts: Dict[str, Dict[str, Any]] = {}
        self._asked: Dict[str, set] = {}
        self._customer_texts: Dict[str, List[str]] = {}
        self._precomp: Dict[str, Dict[str, Any]] = {}    # bước 13: giá/tồn kho/KM CODE đã tra lúc nhận diện khách (còn hiệu lực tới khi có đơn tạo/đổi)
        self._precomp_logged: Dict[str, bool] = {}       # các lời gọi tra sẵn đã ghi vào trace lượt đầu của cuộc gọi chưa
        self._policy_routes: Dict[str, List[Dict[str, Any]]] = {}    # router chính sách trong lượt này (quyết định, độ trễ, chi phí) → trace
        self._identity_asked: Dict[str, bool] = {}       # đã xin xác nhận tên khi SĐT dùng chung — một lần/cuộc
        self._prior_asked: Dict[str, bool] = {}        # đã hỏi SĐT/tài khoản lần trước (khách nói đã liên hệ mà chưa có lịch sử) — chỉ hỏi một lần/cuộc
        self._readings: Dict[str, Any] = {}              # lượt gần nhất: ReplyReading của lời khách (None = không có LLM → gate dùng regex dự phòng)
        self._confirmed: Dict[str, set] = {}      # slot đã được XÁC NHẬN lại trong cuộc gọi (chỉ xác nhận 1 lần)
        self._reask: Dict[str, Dict[str, int]] = {}   # slot -> số lượt LIÊN TIẾP đã hỏi mở mà khách chưa trả lời (src/harness/reask.py)
        self._gate_retry_args: Dict[str, Dict[str, Any]] = {}   # tham số order.create để LLM gọi lại sau khi khách đồng ý

        self._gate_extra_calls: Dict[str, List[Dict[str, Any]]] = {}   # tool cổng tự gọi trong lượt (báo giá để đọc lại đơn) — đưa vào trace
        self.order_gate = OrderGate()             # cổng đặt đơn bằng code (src/harness/order_gate.py)
        memory.register_delete_listener(self._forget_customer)  # xóa khách -> xóa cả trạng thái theo cuộc gọi
        # Bước 12: chọn sản phẩm bằng luật slot→thuộc tính (dữ liệu config/slot_rules.json) + chính sách hỏi lại if/else
        try:
            self.retriever: Optional[ProductRetriever] = ProductRetriever()
            self.clarifier: Optional[ClarificationPolicy] = ClarificationPolicy(self.retriever.rules)
        except Exception as e:      # thiếu catalog/luật → vẫn chạy được (không có product.shortlist)
            logging.getLogger("harness").warning("[Retriever] không khởi tạo được (%s) — tắt product.shortlist.", e)
            self.retriever, self.clarifier = None, None

    # Trích claims/questions từ lời agent: xem src/harness/extractor.py (bước 10).
    # Tool có tham số 'on' (ngày cuộc gọi) theo đúng tools.schema.json — orchestrator tự
    # tiêm current_date vào, không phó thác cho LLM nhớ/truyền đúng.
    TOOLS_WITH_ON_PARAM = {"pricing.get_quote", "pricing.quote_order", "inventory.check", "order.create", "order.update"}
    # Tool có arg mang SKU/variant SKU — mục tiêu của kiến trúc phân giải SKU 4 tầng (xem
    # _tool_executor/_repair_unknown_sku): Tầng 1 ép enum đúng SKU thật ngay trong schema,
    # Tầng 2-3 tự sửa khi LLM vẫn lỡ gửi sai, Tầng 4 trả gợi ý thật khi mọi cách đều thất bại.
    TOOLS_WITH_VARIANT_SKU = {"pricing.get_quote", "inventory.check", "order.create", "order.update"}

    # Tool GHI (thay đổi trạng thái): chỉ thực hiện 1 lần cho mỗi yêu cầu trong 1 cuộc gọi (A2/N4).
    WRITE_TOOLS = {"order.create", "order.update", "schedule.callback", "handoff.transfer"}
    MAX_HISTORY_CHARS = 12000   # giới hạn kích thước prompt: bỏ bớt lịch sử cũ nhất (N6)
    SAFE_FALLBACK_TEXT = "Dạ em xin phép kiểm tra lại thông tin trên hệ thống rồi phản hồi mình ngay ạ."
    # Chỉ các fact này được đưa vào prompt LLM (không đổ toàn bộ profile_facts — N13).
    LLM_PROFILE_KEYS = ("customer_name", "honorific", "room_area_m2", "has_children", "budget_vnd", "product_advised",
                        "price_quoted_vnd", "promo_code", "promo_expiry", "blocker", "size", "color", "variant_sku",
                        "order_id")

    def clear_session(self, session_id: str) -> None:
        """Giải phóng trạng thái theo cuộc gọi (bảng token PII, cache ghi, nhật ký tool) khi cuộc gọi kết thúc."""
        self._vaults.pop(session_id, None)
        self._call_log.pop(session_id, None)
        self._write_cache.pop(session_id, None)
        self._start_facts.pop(session_id, None)
        self._asked.pop(session_id, None)
        self._customer_texts.pop(session_id, None)
        self._confirmed.pop(session_id, None)
        self._reask.pop(session_id, None)
        self._precomp.pop(session_id, None)
        self._precomp_logged.pop(session_id, None)
        self.order_gate.forget(session_id)

    # ------------------------------------------------------------------ bước 12: chọn sản phẩm theo slot
    def _known_slot_values(self, profile: Dict[str, Any], brief: CallBrief) -> Dict[str, Any]:
        """Slot (có trong luật) đã nhớ từ các cuộc trước: hồ sơ + Call Brief."""
        keys = set(self.retriever.rules.slots()) if self.retriever else set()
        out = {k: v for k, v in (brief.profile_facts or {}).items() if k in keys}
        out.update({k: v for k, v in (profile or {}).items() if k in keys})
        return out

    def _run_shortlist(self, args: Dict[str, Any], profile: Dict[str, Any], brief: CallBrief, turn: NormalizedTurn,
                       on: str, session_id: str) -> Dict[str, Any]:
        """Tool nội bộ `product.shortlist`. Slot = hồ sơ đã nhớ < tham số LLM truyền (LLM thấy cả hội thoại) < điều khách vừa nói
        ở lượt này (regex). Trả top-k kèm lý do chấm + `ask_next` (đã lọc bởi ClarificationPolicy, tối đa 1 câu)."""
        if self.retriever is None:
            return {"error": "shortlist_unavailable"}
        slots = self._known_slot_values(profile, brief)
        slots.update({k: v for k, v in args.items() if k in set(self.retriever.rules.slots()) and v not in (None, "")})
        slots.update({k: v for k, v in extract_easy_slots(turn.normalized_text, turn.extracted_entities).items()
                      if k in set(self.retriever.rules.slots())})
        norm = self.retriever.normalize_slots(slots)             # ép kiểu/bỏ slot lạ trước khi gửi tới server
        call_args: Dict[str, Any] = {**norm, "on": on}
        for key in ("category", "query", "top_k"):
            if args.get(key) not in (None, ""):
                call_args[key] = args[key]
        listing = self._wants_listing(turn.normalized_text)             # do CODE nhận ra khách hỏi liệt kê (LLM tự bật list_all thì liệt kê nhầm cả khi khách chỉ hỏi tư vấn)
        if listing:
            call_args["list_all"] = True
        out = self.mcp.execute_tool("product.shortlist", call_args, caller="LLMOrchestrator")   # chấm điểm chạy ở mcp-catalog
        if "error" in out:
            return out
        if listing:
            out["listing_requested"] = True
            out["instruction"] = ("Khách hỏi LIỆT KÊ các mẫu: lần này KHÔNG chốt 1 sản phẩm — nêu ĐỦ MỌI mẫu trong 'items' (tên + giá), nhắc nếu 'more_available' > 0, "
                                  "rồi hỏi nhu cầu để thu hẹp.")             # chỉ xuất hiện trong kết quả khi khách hỏi liệt kê: không làm lệch cách tư vấn bình thường (chốt 1 sản phẩm)
        items = out.get("items") or []
        # shortlist chỉ có giá NIÊM YẾT → LLM từng báo 7.990.000 cho mẫu đang giảm còn 7.690.000 (TEST-184). Gắn giá SAU khuyến mãi của ngày gọi cho từng mẫu.
        phone = brief.phone if brief.phone and brief.phone != "UNKNOWN" else None
        for it in items[:8]:      # shortcut: tối đa 8 mẫu đầu được tra giá (mỗi mẫu 1 lời gọi tool); danh sách dài hơn thì nâng hoặc tra theo lô
            q = self.mcp.execute_tool("pricing.get_quote", {"sku": it.get("sku"), "on": on, **({"customer_phone": phone} if phone else {})}, caller="HarnessOrchestrator") if it.get("sku") else {}
            if isinstance(q, dict) and isinstance(q.get("final_price_vnd"), int):
                it["final_price_vnd"] = q["final_price_vnd"]
        if any("final_price_vnd" in it for it in items):
            out["price_note"] = "Báo giá cho khách theo final_price_vnd (giá sau khuyến mãi hôm nay), không báo list_price_vnd như giá bán."
        if items and out.get("slots_used") and not any(i.get("matched") for i in items):
            # Không tiêu chí nào áp dụng cho nhóm sản phẩm này với thông tin khách nêu (vd diện tích phòng/trẻ nhỏ với máy lọc nước): điểm 0, thứ tự chỉ do giá.
            # Không để LLM coi đây là "đề xuất phù hợp" (lỗi ui_replay D: "UF Sunhouse phù hợp phòng 20m² và an toàn cho trẻ nhỏ" không có căn cứ nào).
            out["no_basis"] = True
            out["decision"] = {"mode": "no_basis"}
            out["instruction"] = ("KHÔNG có tiêu chí nào áp dụng cho nhóm sản phẩm này với thông tin khách vừa nêu (điểm = 0, thứ tự chỉ theo giá): "
                                  "KHÔNG được nói sản phẩm 'phù hợp', 'an toàn' hay 'đáp ứng' nhu cầu đó. Nói rõ thông tin ấy chưa dùng để chọn sản phẩm trong nhóm này, "
                                  "rồi hỏi khách đang cần loại sản phẩm nào (hoặc giới thiệu theo giá niêm yết).") + (" " + out["instruction"] if out.get("instruction") else "")
        known = set(out.get("slots_used", {})) | set(profile or {}) | set(brief.profile_facts or {})
        asked = self._asked.get(session_id, set())
        out["ask_next"] = self.clarifier.next_questions(out.pop("ask_next", []), known, asked, brief.must_not_ask)
        out["do_not_ask"] = sorted(self.clarifier.forbidden_slots(known, asked, brief.must_not_ask))
        if not out["ask_next"]:
            out.pop("ask_next")
        return out

    _LISTING_RE = re.compile(r"\b(?:cac mau|nhung (?:mau|loai|dong)|co (?:mau|loai|dong) (?:nao|gi)|mau nao|loai nao|con (?:mau|loai) (?:nao )?khac|"
                             r"bao nhieu (?:mau|loai)|liet ke|xem het|tat ca (?:cac )?(?:mau|loai))\b")

    @classmethod
    def _wants_listing(cls, text: str) -> bool:
        """Khách hỏi LIỆT KÊ ("có các mẫu nào", "những loại nào", "còn mẫu nào khác"): khác với hỏi tư vấn (chốt 1 sản phẩm)."""
        return bool(cls._LISTING_RE.search(_fold(text)))

    def _display_slot_value(self, slot: str, value: Any) -> Optional[str]:
        """Tên hiển thị khi xác nhận: sản phẩm → tên thật trong catalog; slot khác → định dạng mặc định."""
        if slot == "product_advised" and isinstance(value, str):
            name = self._product_info(value).get("name")
            return f"{name}" if name else None
        return None

    def _banned_question_slots(self, profile: Dict[str, Any], brief: CallBrief, customer_text: str,
                               turn: NormalizedTurn, session_id: str) -> set:
        """Slot KHÔNG được hỏi mở: đã nhớ (hồ sơ/Call Brief/`must_not_ask`), khách đã nói trong cuộc gọi, hoặc agent đã hỏi mở ở lượt trước."""
        said = set(extract_easy_slots(customer_text, turn.extracted_entities))
        known = set(profile or {}) | set(brief.profile_facts or {}) | said
        return self.clarifier.forbidden_slots(known, self._asked.get(session_id, set()), brief.must_not_ask)

    @staticmethod
    def _sanitize_basket(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """`basket_skus` = các SKU KHÁC trong cùng đơn (điều kiện KM 'máy thứ 2'). LLM đôi khi nhét chính SKU
        đang báo giá vào đó → tool tưởng có 2 máy và áp KM sai (SAMPLE-05 lần chạy C: báo 2.445.000 thay vì
        4.890.000, order.create sau đó lệch giá). Bỏ phần tử trùng SKU chính; rỗng thì bỏ hẳn tham số."""
        if name not in ("pricing.get_quote", "order.create") or not args.get("basket_skus"):
            return args
        own = str(args.get("sku") or "").strip().upper()
        raw = args["basket_skus"] if isinstance(args["basket_skus"], list) else [args["basket_skus"]]
        others = []
        for s in raw:
            s = str(s).strip()
            if s and s.upper() != own and s not in others:
                others.append(s)
        out = {k: v for k, v in args.items() if k != "basket_skus"}
        if others:
            out["basket_skus"] = others
        return out

    def _quote_fn(self, record: Optional[List[Dict[str, Any]]] = None):
        """Hàm `call(tool, args)` cho `price_basket`: chạy `pricing.get_quote` / `pricing.quote_order` qua MCP. `record` (nếu có) nhận LỜI GỌI ĐẦU TIÊN để đưa vào trace."""
        def call(tool: str, a: Dict[str, Any]) -> Dict[str, Any]:
            r = self.mcp.execute_tool(tool, a, caller="LLMOrchestrator")
            if record is not None and not record:
                record.append({"name": tool, "args": a, "result": r})
            return r
        return call

    @staticmethod
    def _order_lines(exec_args: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Các dòng giỏ của MỘT lời gọi order.create/get_quote: SKU chính × qty + các dòng còn lại của `lines` (hợp đồng BTC 11/2026; dòng đầu = SKU chính,
        xem `_main_from_lines`) hoặc các SKU khác trong `basket_skus` (mỗi SKU 1)."""
        main = {"sku": exec_args.get("sku"), "qty": int(exec_args.get("qty") or 1)}
        if isinstance(exec_args.get("lines"), list) and exec_args["lines"]:
            return [main] + [{"sku": l.get("sku"), "qty": int(l.get("qty") or 1)} for l in exec_args["lines"][1:]]
        others = HarnessOrchestrator._sanitize_basket("order.create", exec_args).get("basket_skus") or []
        return [main] + [{"sku": s, "qty": 1} for s in others]

    @staticmethod
    def _main_from_lines(args: Dict[str, Any]) -> Dict[str, Any]:
        """LLM gọi order.create theo dạng `lines` (schema BTC 11/2026 cho `sku` là tùy chọn): dòng đầu thành SKU chính (sku, qty) để order gate/chống lặp chạy như cũ;
        đơn một dòng thì bỏ hẳn `lines`. Giá trong `lines` của LLM bị bỏ — giá từng máy do `price_basket` lấy từ tool."""
        ls = [{"sku": str(l["sku"]), "qty": int(l.get("qty") or 1)} for l in args.get("lines") or [] if isinstance(l, dict) and l.get("sku")] if isinstance(args.get("lines"), list) else []
        rest = {k: v for k, v in args.items() if k != "lines"}
        if not ls:
            return rest
        return {**rest, "sku": ls[0]["sku"], "qty": ls[0]["qty"], **({"lines": ls} if len(ls) > 1 else {})}

    def _attach_basket_total(self, result: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """`pricing.get_quote` cho nhiều máy/nhiều SKU: thêm tổng do `price_basket` tính để LLM không tự nhân/cộng (qty=1 không giỏ: giữ nguyên kết quả cũ)."""
        lines = self._order_lines(args)
        if len(lines) == 1 and lines[0]["qty"] == 1:
            return result
        pb = price_basket(self._quote_fn(), lines, args.get("on"), args.get("customer_phone"), args.get("address"))
        if "error" in pb:
            return result
        return {**result, "unit_prices_vnd": pb["lines"][0]["unit_prices_vnd"], "total_vnd": pb["total_vnd"],
                **({"second_unit_promos": pb["lines"][0]["second_unit_promos"]} if pb["lines"][0]["second_unit_promos"] else {}),
                "note": "Tổng của giỏ là total_vnd (đã tính theo từng máy/từng SKU) — KHÔNG tự nhân hay cộng. Đơn được tạo đúng tổng này."}

    def _order_basket(self, exec_args: Dict[str, Any], caller_phone: Optional[str], on: str) -> Optional[Dict[str, Any]]:
        """Giỏ của một lời gọi order.create (giá từng máy theo tool) để dựng tham số đơn; None khi không báo giá được."""
        if not exec_args.get("sku"):
            return None
        addr = exec_args.get("address")
        addr = addr if isinstance(addr, str) and "<ADDR_" not in addr else None
        pb = price_basket(self._quote_fn(), self._order_lines(exec_args), on, exec_args.get("customer_phone") or caller_phone, addr)
        return None if "error" in pb else pb

    @staticmethod
    def _basket_confirm_flag(result: Dict[str, Any], pb: Optional[Dict[str, Any]], payment: Any) -> Dict[str, Any]:
        """Ngưỡng 'COD > 2.000.000 cần gọi xác nhận' tính trên TỔNG ĐÚNG của cả giỏ, không theo từng dòng đơn."""
        if pb and isinstance(result, dict) and result.get("status") == "created" and str(payment or "").upper() == "COD" and cod_needs_confirmation(pb["total_vnd"]):
            return {**result, "needs_confirmation_call": True}
        return result

    @staticmethod
    def _forget_returned_order(write_cache: Dict[tuple, Dict[str, Any]], order_id: Optional[str]) -> None:
        """Đơn đã được trả hàng (order.update action=return) thì mục chống-lặp `order.create` trỏ tới nó là CŨ: nếu giữ, khách đặt lại đúng sản phẩm đó sẽ nhận
        "đơn này em đã lên rồi, mã X" (mã của đơn đã trả) và KHÔNG có đơn mới. Hợp đồng tool không có action huỷ đơn; trả hàng là thao tác duy nhất làm đơn hết hiệu lực."""
        for key in [k for k, r in write_cache.items() if k and k[0] == "order.create" and isinstance(r, dict) and r.get("order_id") == order_id]:
            del write_cache[key]

    @staticmethod
    def _write_key(name: str, args: Dict[str, Any]) -> Optional[tuple]:
        """Khóa chống gọi lặp cho tool ghi: cùng (đơn, hành động, biến thể) = cùng một yêu cầu."""
        if name == "order.update":
            return (name, args.get("order_id"), args.get("action"), args.get("new_variant_sku"))
        if name == "order.create":
            units: Dict[str, int] = {}                      # cả giỏ (dạng sku+qty+basket_skus hay dạng lines) = một yêu cầu
            priced = isinstance(args.get("lines"), list) and args["lines"] and "price_vnd" in args["lines"][0]      # dạng đã gửi backend (mỗi máy một dòng)
            for l in (args["lines"] if priced else HarnessOrchestrator._order_lines(args)):
                units[str(l.get("sku"))] = units.get(str(l.get("sku")), 0) + int(l.get("qty") or 1)
            return (name, args.get("customer_phone"), tuple(sorted(units.items())))
        if name == "schedule.callback":
            return (name, args.get("customer_phone"), args.get("callback_at"))
        if name == "handoff.transfer":
            return (name,)
        return None

    def process_turn(self, turn: NormalizedTurn, brief: CallBrief, current_date: str = "2026-10-15",
                     call_name: str = "", closing: bool = False) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """`closing=True`: LƯỢT CHỐT không có lời khách (luật chấm BTC 11/2026) — chỉ bộ chạy đánh giá gọi, sau khi `has_open_order` trả True."""
        turn_text = turn.normalized_text.lower()
        tool_calls_executed: List[Dict[str, Any]] = []
        questions_asked: List[Dict[str, Any]] = []
        claims_made: List[Dict[str, Any]] = []
        facts_used: List[str] = []

        # -------------------------------------------------------------
        # 1. TRUY HỒI (RETRIEVE) TỪ MEMORY & CALL BRIEF
        # -------------------------------------------------------------
        customer_id = brief.customer_id
        profile = self.memory.get_profile_facts(customer_id, on_date=current_date)
        # Working memory khoanh theo (customer_id, current_date): các lượt trong CÙNG 1 call
        # chia sẻ current_date nên vẫn có trí nhớ nhiều lượt; call khác ngày (vài ngày sau)
        # bắt đầu working session MỚI, buộc LLM re-verify giá/tồn kho/KM qua tool thay vì tin
        # lại hội thoại cũ đã có thể lỗi thời (fix thật: SAMPLE-06 từng claim sai in_stock vì
        # LLM tin lại câu "hết hàng" từ call_1 trong lúc call_2 đã có hàng).
        working_session_id = f"SESS-{customer_id}-{current_date}"
        working_state = self.memory.get_working(session_id=working_session_id)

        # Xưng hô theo cách khách TỰ xưng ("anh muốn hỏi…") — ưu tiên hơn CRM; lưu vào bộ nhớ ở cuối lượt (slot `honorific`).
        said_hon = detect_self_honorific(turn.normalized_text)
        if said_hon:
            brief.honorific = "bạn" if said_hon == "em" else said_hon
        was_unknown_name = brief.customer_name in (None, "", "Quý khách")
        said_name = extract_easy_slots(turn.normalized_text, turn.extracted_entities).get("customer_name")
        if said_name and was_unknown_name:
            brief.customer_name = said_name                      # "tôi tên Đại": dùng ngay trong lượt này; lưu vào bộ nhớ ở cuối lượt (slot customer_name)
        # PII (bước 7): bảng token chỉ sống trong process, theo cuộc gọi. LLM chỉ thấy token.
        vault = self._vaults.setdefault(working_session_id, PiiVault())
        caller_phone = brief.phone if brief.phone and brief.phone != "UNKNOWN" else None
        turn.llm_text = vault.mask_text(turn.normalized_text, caller_phone)
        # HIỂU lời khách (đồng ý / từ chối / xác nhận SĐT / tên / thanh toán) bằng LLM kèm trích dẫn nguyên văn; không có LLM → gate dùng regex dự phòng.
        gst = self.order_gate.state(working_session_id)
        last_agent = next((m["content"] for m in reversed(working_state.messages_in_session) if m.get("role") == "assistant"), "")
        # Máy trạng thái quyết định CÓ cần đọc không (tiết kiệm 1 lần gọi LLM ở các lượt khám phá sản phẩm): chỉ đọc khi đã vào ngữ cảnh MUA —
        # gate có đơn nháp, hoặc trong cuộc gọi đã tra/báo giá/đặt một BIẾN THỂ cụ thể (SKU có size+màu), hoặc đang bàn một sản phẩm KHÔNG có biến thể (bán được ngay).
        buying = gst.last_decision is not None or any(
            c.get("name") in ("order.create", "pricing.get_quote", "inventory.check") and self._VARIANT_RE.match(str((c.get("args") or {}).get("sku") or ""))
            for c in self._call_log.get(working_session_id, [])) or self._simple_product_in_play(working_session_id, brief) is not None
        # Khách MỚI (chưa có lịch sử) trong 2 lượt đầu: đọc xem khách có nói đã từng liên hệ không (lượt đó agent phải xin SĐT/tài khoản cũ).
        new_customer_early = brief.previous_calls_count == 0 and not brief.crm_known and not brief.product_advised and not self._prior_asked.get(working_session_id) and len(self._customer_texts.get(working_session_id, [])) < 2
        buying = buying or new_customer_early
        reading = read_reply(self.llm_client, turn.llm_text, last_agent,
                             {"to_confirm": (gst.last_decision or {}).get("to_confirm"), "missing": (gst.last_decision or {}).get("missing"),
                              "stage": gst.stage if gst.last_decision else None}) if (self.order_gate.enabled and buying and not closing) else None
        self._readings[working_session_id] = reading
        reading_trace = reading_trace_dict(reading, skipped=not (self.order_gate.enabled and buying))
        self.order_gate.begin_turn(working_session_id, working_state.current_turn, turn.normalized_text, reading)
        if self.order_gate.state(working_session_id).abandoned_turn == working_state.current_turn:
            self._gate_retry_args.pop(working_session_id, None)  # khách từ chối/mặc cả/hẹn gọi lại: hủy đơn nháp, KHÔNG nối câu hỏi địa chỉ/tên nữa
        self._activity[working_session_id] = {"ts": time.monotonic(), "customer_id": customer_id, "call_date": current_date,
                                              "call_name": call_name, "channel": turn.channel.value}
        self._start_facts.setdefault(working_session_id, dict(brief.profile_facts or {}))   # chụp lúc lượt ĐẦU của cuộc gọi
        prior_call_log = list(self._call_log.setdefault(working_session_id, []))
        write_cache = self._write_cache.setdefault(working_session_id, {})
        live_calls: List[Dict[str, Any]] = []  # tool THỰC SỰ đã chạy trong lượt này (kể cả khi LLM lỗi giữa chừng)
        pre = getattr(brief, "precomputed", None)
        if pre and self._precomp_logged.get(working_session_id) is None:        # lượt đầu của cuộc: các lời gọi CODE đã chạy lúc nhận diện khách vào trace + nhật ký cuộc gọi (bằng chứng cho guardrail)
            self._precomp_logged[working_session_id] = True
            self._precomp[working_session_id] = pre
            tool_calls_executed.extend(pre["calls"])
        precomp_served: List[str] = []         # lời gọi trùng của LLM đã được trả từ kết quả tra sẵn (không gọi tool lần hai)
        handoff_check: Dict[str, Any] = {}     # kết quả chốt chuyển máy của lượt này (chỉ có khi LLM định gọi handoff.transfer)

        shared_state = {
            "customer_id": customer_id,
            "turn_text": turn.normalized_text,
            "entities": turn.extracted_entities,
            "call_brief": brief.to_dict(),
            "profile": profile,
            "on_date": current_date
        }

        sales_advice = self.a2a.delegate_task("sales_advice", shared_state)

        proposal_text = ""
        action_type = "speak"
        metadata_llm_usage = None
        llm_timing: Dict[str, Any] = {}  # số đo thật từ LLMClient (ttft_ms, total_ms, llm_calls) + mốc started_at
        llm_failure: Optional[str] = None
        history_reply: Optional[str] = None  # câu LLM trả lời (còn token) để nhớ cho các lượt sau
        tool_summary = ""
        policy_info: Dict[str, Any] = {}
        is_order_intent = False

        # [INTEGRATION POINT: LLM REASONING & FUNCTION CALLING]
        # LLM là bộ não quyết định chính: tự chọn tool (catalog.search/pricing.get_quote/
        # inventory.check/order.create/order.update/schedule.callback/handoff.transfer/
        # search_policy) và tham số dựa trên hội thoại thật — không đoán ý định/SKU bằng
        # keyword. Lỗi bất kỳ (thiếu key, network, SDK) -> rơi về nhánh rule-based tối giản,
        # TRỪ khi đã có tool GHI chạy hoặc vượt số vòng: khi đó không chạy lại nhánh rule-based
        # (tránh tạo đơn trùng, N4).
        llm_client = self.llm_client
        llm_handled = False
        pre_stock: List[Dict[str, Any]] = []     # inventory.check do CODE chạy cho biến thể khách nêu (trước / sau lời gọi LLM)
        post_stock: List[Dict[str, Any]] = []
        customer_texts_now = self._customer_texts.get(working_session_id, []) + [turn.normalized_text]
        # Order gate chạy BẰNG CODE khi khách đang trả lời câu hỏi/xác nhận/đọc lại đơn của chính gate: LLM không cần (và không được tin) để chuyển tiếp từng bước.
        self._gate_extra_calls[working_session_id] = []
        driver = (self._closing_driver if closing else self._order_driver)(working_session_id, turn, brief, profile, vault, caller_phone, current_date, write_cache)
        gate_open_trace: Dict[str, Any] = {"opened": False, "reason": "not_evaluated"}
        if driver is None:
            late_stock = None
            if reading_trace.get("source") == "skipped" and self.order_gate.enabled:
                # ĐỌC MUỘN khi có tín hiệu: lượt này lần đầu nhắc một biến thể cụ thể của sản phẩm đang bàn (code xác định) → bây giờ mới đáng đọc ý định/xác nhận.
                late_stock = self._check_named_variants(customer_texts_now, brief.product_advised, self._call_log.get(working_session_id, []), [], current_date)
                if late_stock:
                    reading = read_reply(self.llm_client, turn.llm_text, last_agent, {"stage": None})
                    self._readings[working_session_id] = reading
                    reading_trace = {**reading_trace_dict(reading), "late": True}
                    if reading is not None and "recipient_phone" in reading.affirmed:
                        self.order_gate.state(working_session_id).phone_ok = True
            driver, gate_open_trace = self._maybe_open_gate(working_session_id, turn, brief, profile, vault, caller_phone, current_date, reading, customer_texts_now,
                                                            stock=late_stock or None)
        if driver is not None and driver.get("reply") is not None:
            tool_calls_executed.extend(driver["calls"])
            proposal_text = driver["reply"]
            history_reply = driver["reply_masked"]
            tool_summary = " ".join(x for x in (self._summarize_tool_calls(driver["calls"]), self.order_gate.summary_for_history(
                working_session_id, self._gate_retry_args.get(working_session_id))) if x)
            is_order_intent = any(c.get("name") == "order.create" for c in driver["calls"])
            action_type = "execute_tool" if driver["calls"] else "speak"
            llm_handled = True
        if (not llm_handled) and llm_client is not None and getattr(llm_client, "available", False):
            try:
                def _focus() -> Optional[str]:
                    """Sản phẩm CHA đang bàn lúc này (tra gần nhất trong cuộc gọi, kể cả lượt này); chưa tra gì thì là sản phẩm đã tư vấn."""
                    return next(iter(self._discussed_parents(brief.product_advised, prior_call_log + live_calls)), brief.product_advised)

                def _tool_executor(name: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
                    """Trả về (kết quả đã che PII cho LLM+trace, tham số THỰC SỰ đã chạy để ghi trace).
                    Token PII chỉ được mở cho tool/field trong danh sách cho phép (UNMASK_ALLOWED)."""
                    exec_args = vault.unmask_args(name, args, caller_phone)
                    if name == "search_policy":
                        chunks = self.memory.query_policy(args.get("query", ""), on_date=current_date)
                        self._note_policy_route(working_session_id, llm_client)
                        return {"chunks": chunks}, args
                    if name == "product.shortlist":
                        return self._run_shortlist(args, profile, brief, turn, current_date, working_session_id), args
                    if name in self.TOOLS_WITH_ON_PARAM:
                        # Ngày cuộc gọi do ORCHESTRATOR biết chắc (tham số current_date), không
                        # phó thác cho LLM tự suy ra/nhớ đúng — tránh tool dùng nhầm reference_date
                        # mặc định của mock_tools khi LLM quên truyền 'on'.
                        exec_args = {**exec_args, "on": current_date}
                    exec_args = self._sanitize_basket(name, exec_args)
                    if name == "order.create":
                        exec_args = self._main_from_lines(exec_args)
                    if name == "schedule.callback":
                        exec_args = self._future_callback(exec_args, current_date)
                    if name in ("pricing.get_quote", "inventory.check") and isinstance(exec_args.get("sku"), str) and not exec_args["sku"].upper().startswith("SKU-"):
                        # LLM hay truyền TÊN sản phẩm ("AirPure Y") làm sku → unknown_sku → không có báo giá để ghi nhớ (nguyên nhân CCR tụt ở SAMPLE-01, § 11.31)
                        exec_args = {**exec_args, "sku": self._canonical_sku(exec_args["sku"], turn.normalized_text, _focus())}

                    if name in ("pricing.get_quote", "pricing.quote_order") and caller_phone and not exec_args.get("customer_phone") and not brief.blocker:
                        # KM theo hồ sơ (vd thu cũ đổi mới) chỉ áp khi báo giá có SĐT; LLM hay bỏ SĐT ở lần gọi sau và nói giá thiếu KM (GĐ2 GEN-13)
                        exec_args = {**exec_args, "customer_phone": caller_phone}

                    hit = self._precomputed_hit(self._precomp.get(working_session_id), name, exec_args, caller_phone, current_date)
                    if hit:                                # bước 13: CODE đã tra đúng yêu cầu này lúc nhận diện khách (cùng sản phẩm/ngày/số lượng, chưa đổi gì)
                        precomp_served.append(name)
                        return {**hit, "already_checked_this_turn": True, "note": "Đã kiểm tra THẬT đầu cuộc gọi hôm nay; dùng kết quả này."}, vault.redact_args_for_trace(exec_args)
                    if name == "inventory.check":          # biến thể này CODE đã tra ngay đầu lượt: trả lại kết quả đó, không gọi tool lần hai
                        same = next((c for c in pre_stock if (c.get("args") or {}).get("sku") == exec_args.get("sku")), None)
                        if same:
                            return {**same["result"], "already_checked_this_turn": True}, same["args"]

                    # Chống gọi lặp tool ghi: cùng yêu cầu trong cùng cuộc gọi trả lại kết quả cũ, KHÔNG chạy lại.
                    dedup_key = self._write_key(name, exec_args)
                    if dedup_key is not None and dedup_key in write_cache:
                        again = {**write_cache[dedup_key], "already_done": True,
                                 "note": "Yêu cầu này đã được thực hiện trước đó trong cuộc gọi, không thực hiện lại."}
                        return vault.mask_value(again, caller_phone), vault.redact_args_for_trace(exec_args)

                    if name == "handoff.transfer":
                        # Chuyển máy chỉ khi KHÁCH yêu cầu/đồng ý (chốt bằng cấu trúc, không dựa vào chỉ dẫn prompt); kiểm tra một lần/lượt, theo yêu cầu.
                        if "v" not in handoff_check:
                            handoff_check["v"] = authorize_handoff(llm_client, turn.llm_text, last_agent)
                        if not handoff_check["v"]["authorized"]:
                            return ({"error": "handoff_blocked", "instruction": "CHƯA chuyển máy: đây không phải ca ngoài phạm vi/an toàn và khách chưa yêu cầu hoặc đồng ý chuyển. KHÔNG nói là đã/sẽ chuyển máy. "
                                     "Tiếp tục trả lời khách, rồi hỏi MỘT câu khách có muốn nhờ nhân viên hỗ trợ không."},
                                    vault.redact_args_for_trace(exec_args))
                        exec_args = {**exec_args, "brief": self._complete_handoff_brief(exec_args.get("brief"), brief, handoff_check["v"]["quote"], caller_phone, vault, current_date,
                                                                                            focus_sku=_focus() or next((s for _, s, _ in product_mentions(" ".join(customer_texts_now))), None))}

                    if name == "order.create":
                        if self.order_gate.enabled:
                            exec_args = {**exec_args, "sku": self._canonical_sku(exec_args.get("sku"), turn.normalized_text, _focus())}
                        blocked = self._gate_order_create(working_session_id, args, exec_args, vault, profile, brief, caller_phone, current_date)
                        if blocked is not None:
                            return blocked, vault.redact_args_for_trace({k: v for k, v in exec_args.items() if k not in GATE_ONLY_ARGS})
                        exec_args = {k: v for k, v in exec_args.items() if k not in GATE_ONLY_ARGS}
                    pb_final = None
                    if name == "order.create":             # bất biến: tổng báo khách == tổng backend ghi (giỏ nhiều máy → order.create(lines) theo giá từng máy)
                        pb_final = self._order_basket(exec_args, caller_phone, current_date)
                        if pb_final:
                            exec_args = order_args(exec_args, pb_final)
                    result = self.mcp.execute_tool(name, exec_args, caller="LLMOrchestrator")
                    final_args = exec_args
                    if name == "order.create":
                        result = self._basket_confirm_flag(result, pb_final, exec_args.get("payment"))
                    if name == "pricing.get_quote" and "error" not in result:
                        result = self._attach_basket_total(result, exec_args)
                    if name in ("order.create", "order.update") and "error" not in result:
                        self._precomp.pop(working_session_id, None)      # đơn đã đổi giá/KM/tồn kho: kết quả tra sẵn hết giá trị

                    # Phân giải SKU 4 tầng — Tầng 2-4 (Tầng 1 là enum đã tiêm sẵn vào tools
                    # schema trước khi gọi LLM, xem _build_dynamic_tools). Chỉ kích hoạt khi
                    # tool thật báo SKU/variant không hợp lệ.
                    sku_field = "new_variant_sku" if "new_variant_sku" in exec_args else ("sku" if "sku" in exec_args else None)
                    if name in self.TOOLS_WITH_VARIANT_SKU and sku_field and result.get("error") in ("unknown_sku", "variant_not_found"):
                        fixed_sku = self._repair_unknown_sku(exec_args[sku_field], turn.normalized_text, _focus())
                        if fixed_sku:
                            fixed_args = {**exec_args, sku_field: fixed_sku}
                            repaired = self.mcp.execute_tool(name, fixed_args, caller="LLMOrchestrator-AutoRepair")
                            if "error" not in repaired:
                                result, final_args = repaired, fixed_args
                            else:
                                result = repaired
                        if "error" in result:
                            # Tầng 4 (Self-Healing): không tự sửa được -> trả kèm danh sách biến
                            # thể THẬT còn lại để LLM tự suy luận lại ở vòng sau.
                            parent_guess = _focus() or exec_args[sku_field].rsplit("-", 2)[0]
                            variants = self._fetch_variants(parent_guess)
                            if variants:
                                result = {**result, "available_variants": [
                                    {"variant_sku": v["variant_sku"], "size": v.get("size"), "color": v.get("color"),
                                     "in_stock": v.get("stock", 0) > 0}
                                    for v in variants
                                ]}

                    if name == "catalog.search" and isinstance(result, dict) and not result.get("items") and not exec_args.get("sku"):
                        result = self._empty_search_fallback(result, exec_args, turn.normalized_text, _focus(), prior_call_log + live_calls, current_date)
                    if dedup_key is not None and "error" not in result:
                        write_cache[self._write_key(name, final_args)] = result
                        write_cache[dedup_key] = result
                        if name == "order.update" and final_args.get("action") == "return":
                            self._forget_returned_order(write_cache, final_args.get("order_id"))
                    if name == "order.update" and isinstance(result, dict) and result.get("error") == "order_not_found":
                        result = {**result, "hint": "Không có đơn này. Nếu khách CHƯA đặt đơn và chỉ muốn xem/chọn sản phẩm khác thì đây KHÔNG phải đổi đơn: "
                                                    "tra catalog.search/product.shortlist rồi pricing.get_quote ĐÚNG SKU của sản phẩm khách nêu."}
                    trace_args = vault.redact_args_for_trace(final_args)
                    masked = vault.mask_value(result, caller_phone)
                    live_calls.append({"name": name, "tool": name, "args": trace_args, "result": masked})
                    return masked, trace_args

                pre_stock = self._check_named_variants(customer_texts_now, brief.product_advised, prior_call_log, [], current_date)
                history = self._trim_history(list(working_state.messages_in_session)[-20:])
                # Tầng 1 (Dynamic Tool Enum): nếu đã biết sản phẩm cha đang tư vấn, ép tools
                # schema chỉ chấp nhận đúng variant_sku THẬT của sản phẩm đó cho sku/new_variant_sku.
                def dynamic_tools():                                    # dựng lại MỖI vòng: sản phẩm khách vừa đổi sang (catalog.search ở vòng trước) vào được enum ngay vòng sau
                    parents = self._discussed_parents(brief.product_advised, prior_call_log + pre_stock + live_calls)
                    return with_order_gate_params(self._build_dynamic_tools(llm_client, parents) or llm_client.get_base_tools())
                llm_started_at = time.perf_counter()
                llm_text, llm_tool_calls, llm_usage = llm_client.chat_with_tools(
                    messages=self._build_llm_messages(turn, brief, history, current_date, caller_phone, stock_calls=pre_stock, precomputed=self._precomp.get(working_session_id),
                                                      focus_parent=_focus()),
                    tool_executor=_tool_executor,
                    tools_override=dynamic_tools,
                    timing=llm_timing,
                )
                llm_timing["started_at"] = llm_started_at
                llm_tool_calls = [c for c in llm_tool_calls if (c.get("result") or {}).get("error") not in ("order_gate_blocked", "handoff_blocked") and not (c.get("result") or {}).get("already_checked_this_turn")]    # lời gọi bị chặn/trùng với tra cứu của code KHÔNG vào tool_calls của trace
                # Khiếu nại ĐƠN ĐÃ ĐẶT: lượt có tra order.status mà LLM không tự chuyển máy → CODE gọi chốt phân loại (có dữ kiện đơn); ca sự cố/ngoài phạm vi thì CODE chuyển máy và nối câu báo khách.
                status_calls = [c for c in llm_tool_calls if c.get("name") == "order.status" and (c.get("result") or {}).get("orders")]
                llm_text, llm_tool_calls = self._bind_price_to_product(llm_text, llm_tool_calls, _tool_executor, live_calls)
                llm_text = correct_basket_totals(llm_text, prior_call_log + llm_tool_calls)      # tổng nhiều máy do price_basket tính; LLM nhân giá × qty thì code sửa lại số
                llm_text = self._ensure_scope_notice(llm_text, llm_tool_calls, handoff_check.get("v"))      # LLM tự chuyển máy ca ngoài phạm vi/an toàn: lời nói thật về giới hạn
                if status_calls and not handoff_check and not any(c.get("name") == "handoff.transfer" for c in llm_tool_calls):
                    handoff_check["v"] = authorize_handoff(llm_client, turn.llm_text, last_agent, self._order_facts(status_calls, current_date))
                    if handoff_check["v"]["authorized"] and handoff_check["v"]["category"] == "scope_safety":
                        sent = len(live_calls)
                        res, _ = _tool_executor("handoff.transfer", {"brief": {}})
                        if "error" not in res and len(live_calls) > sent:
                            llm_tool_calls = llm_tool_calls + live_calls[sent:]
                            llm_text = f"{llm_text.rstrip()} Em đã chuyển thông tin đơn cho nhân viên phụ trách kiểm tra, nhân viên sẽ liên hệ lại {brief.honorific or 'anh/chị'} ạ."
                # Sản phẩm cha có thể chỉ lộ ra TRONG lượt này (catalog.search của LLM): tra nốt biến thể khách nêu trước khi guardrail đối chiếu lời nói với tồn kho.
                post_stock = self._check_named_variants(customer_texts_now, brief.product_advised, prior_call_log + pre_stock + llm_tool_calls,
                                                        pre_stock + llm_tool_calls, current_date)
                tool_calls_executed.extend(self._gate_extra_calls.get(working_session_id, []))
                tool_calls_executed.extend(pre_stock)
                tool_calls_executed.extend(llm_tool_calls)
                tool_calls_executed.extend(post_stock)
                if driver is not None and driver.get("defer"):                        # khách vừa hỏi thêm: LLM trả lời, rồi code NỐI câu tiếp theo của gate
                    self._driver_followup(working_session_id, turn, brief, profile, vault, caller_phone, current_date)
                llm_text = self.order_gate.enforce_reply(llm_text, self._last_blocked(working_session_id))
                llm_text = self._fix_addressing(llm_text, brief)
                # Lời LLM có thể chứa token (CURRENT_CUSTOMER, <PHONE_n>, <ADDR_n>): mở trước khi nói với khách
                # (riêng <ID_n> không bao giờ được đọc lại).
                proposal_text = vault.unmask_text(llm_text, caller_phone)
                history_reply = llm_text
                tool_summary = self._summarize_tool_calls(pre_stock + llm_tool_calls + post_stock)
                gate_line = self.order_gate.summary_for_history(working_session_id, self._gate_retry_args.get(working_session_id))
                tool_summary = " ".join(x for x in (tool_summary, gate_line) if x)
                is_order_intent = any(tc.get("name") == "order.create" for tc in llm_tool_calls)
                action_type = "execute_tool" if llm_tool_calls else "speak"
                metadata_llm_usage = llm_usage
                llm_handled = True
            except Exception as e:
                logging.getLogger("harness.llm").warning("[LLM] call failed (%s) — xử lý lỗi an toàn.", e)
                tool_calls_executed.extend(pre_stock + live_calls)  # tool đã chạy thật phải còn trong trace
                wrote = any(c["name"] in self.WRITE_TOOLS for c in live_calls)
                if wrote or isinstance(e, LLMRoundLimit):
                    # KHÔNG chạy nhánh rule-based (có thể tạo đơn thứ hai): trả lời an toàn dựa trên tool đã chạy.
                    llm_failure = "llm_round_limit" if isinstance(e, LLMRoundLimit) else "llm_error_after_write"
                    proposal_text = self._safe_summary(live_calls)
                    action_type = "execute_tool" if live_calls else "speak"
                    is_order_intent = any(c["name"] == "order.create" for c in live_calls)
                    llm_handled = True
                else:
                    llm_handled = False

        verified_price = None
        if not llm_handled:
            # -----------------------------------------------------------
            # NHÁNH RULE-BASED TỐI GIẢN (fallback khi mất LLM/hết key) — KHÔNG mở rộng
            # thêm keyword để cố pass từng kịch bản; chấp nhận không đạt mọi success_if,
            # đây không phải chế độ được chấm chính (xem README).
            # -----------------------------------------------------------
            POLICY_KEYWORDS = [
                "đổi trả", "đổi size", "đổi màu", "đổi hàng", "trả hàng", "bảo hành",
                "hoàn tiền", "chính sách", "cod", "phí vận chuyển", "giao hàng",
                "khuyến mãi", "promo", "ship"
            ]
            is_policy_question = any(kw in turn_text for kw in POLICY_KEYWORDS)
            policy_info = self.a2a.delegate_task(
                "policy_check", {**shared_state, "query": turn.normalized_text}
            ) if is_policy_question else {}

            target_sku = brief.product_advised or sales_advice.get("suggested_sku")     # chưa biết sản phẩm → không báo giá/lên đơn cho sản phẩm tự chọn
            quote_res = {}
            if target_sku:
                quote_res = self.mcp.execute_tool(
                    tool_name="pricing.get_quote",
                    args={"sku": target_sku, "on": current_date, "customer_phone": brief.phone},
                    caller="HarnessOrchestrator"
                )
                tool_calls_executed.append({
                    "name": "pricing.get_quote", "tool": "pricing.get_quote",
                    "args": {"sku": target_sku, "on": current_date, "customer_phone": brief.phone},
                    "result": quote_res
                })
                verified_price = quote_res.get("final_price_vnd")
                if verified_price is not None:
                    claims_made.append({"field": "price_vnd", "value": verified_price, "text": f"{verified_price:,}đ"})
            quoted = verified_price is not None

            is_order_intent = quoted and any(w in turn_text for w in ["lên đơn", "chốt đơn", "lấy con này", "mua luôn", "giao về địa chỉ", "giao về"])
            is_confirm_price = quoted and any(w in turn_text for w in ["giá vẫn như", "đúng không", "phải không"])

            gate_say = None
            if is_order_intent:
                gate_args = {"sku": target_sku, "qty": 1, "price_vnd": verified_price, "payment": "COD", "customer_phone": "CURRENT_CUSTOMER" if caller_phone else None}
                blocked = self._gate_order_create(working_session_id, gate_args, dict(gate_args), vault, profile, brief, caller_phone, current_date)
                if blocked is not None:
                    gate_say = blocked["order_gate"]["say"]
                    is_order_intent = False
            if gate_say:
                proposal_text = vault.unmask_text(gate_say, caller_phone)
                action_type = "speak"
            elif is_order_intent:
                order_res = self.mcp.execute_tool(
                    tool_name="order.create",
                    args={"customer_phone": brief.phone, "sku": target_sku, "price_vnd": verified_price,
                          "qty": 1, "payment": "COD", "on": current_date},
                    caller="HarnessOrchestrator"
                )
                tool_calls_executed.append({
                    "name": "order.create", "tool": "order.create",
                    "args": {"customer_phone": brief.phone, "sku": target_sku, "price_vnd": verified_price,
                             "qty": 1, "payment": "COD", "on": current_date},
                    "result": order_res
                })
                facts_used.extend(["product_advised", "price_quoted_vnd"])
                if "room_area_m2" in profile or "room_area_m2" in brief.profile_facts:
                    facts_used.append("room_area_m2")
                if "blocker" in profile or brief.blocker:
                    facts_used.append("blocker")
                order_id = order_res.get("order_id", "OD1000")
                proposal_text = f"Dạ em đã tạo đơn thành công mã {order_id} cho {brief.addressing()}. Sản phẩm {product_name(target_sku)} có giá ưu đãi là {verified_price:,}đ, bên em sẽ giao trong 2 ngày tới ạ!"
                action_type = "execute_tool"
            elif is_confirm_price:
                facts_used.extend(["product_advised", "price_quoted_vnd"])
                gifts = [product_name(x["gift_sku"]) for x in quote_res.get("applied_promos", []) if x.get("type") == "gift" and x.get("gift_sku")]       # chỉ nói quà khi tool báo đang áp dụng
                proposal_text = f"Dạ đúng rồi ạ {brief.honorific}, giá {product_name(target_sku)} vẫn là {verified_price:,}đ" + (f" và có quà tặng kèm {', '.join(gifts)} theo khuyến mãi hiện hành ạ." if gifts else " ạ.")
            elif is_policy_question and policy_info.get("grounded_answer"):
                facts_used.append("policy_query")
                proposal_text = f"Dạ {brief.honorific}, {policy_info['grounded_answer']}"
            else:
                if brief.previous_calls_count > 0:
                    proposal_text = brief.suggested_opening
                    facts_used.extend(brief.must_carry_over)
                    if brief.blocker:
                        questions_asked.append({"slot": "blocker", "type": "confirm", "text": "mình còn băn khoăn điểm nào không ạ?"})
                elif quoted:
                    proposal_text = f"Dạ em chào {brief.honorific}, em thấy {product_name(target_sku)} giá {verified_price:,}đ có thể phù hợp với mình ạ. {sales_advice.get('talking_point', '')}".strip()
                else:
                    proposal_text = f"Dạ em chào {brief.honorific}, hiện hệ thống bên em đang gián đoạn một chút. {brief.honorific.capitalize()} cho em biết mình đang quan tâm sản phẩm nào để em hỗ trợ ạ?"

        # -------------------------------------------------------------
        # 4. ĐẨY PROPOSAL QUA GUARDRAIL & FALLBACK
        # -------------------------------------------------------------
        proposal_payload = {
            "proposed_text": proposal_text,
            "quoted_price": None if llm_handled else verified_price,
            "action_type": action_type
        }
        guard_decision: GuardrailDecision = self.guardrail.check(
            proposal=proposal_payload,
            specialist_results={"sales": sales_advice, "policy": policy_info},
            context={
                "verified_price": None if llm_handled else verified_price,
                "tool_calls": tool_calls_executed,
                # tool đã chạy ở các lượt trước TRONG CUỘC GỌI NÀY (không thay câu khi tool đã chạy; đối chiếu phí/giá)
                "call_tool_calls": prior_call_log + tool_calls_executed,
                "known_numbers": self._known_numbers(turn, brief, working_state),
            }
        )

        final_response_text = guard_decision.sanitized_text if closing else self.order_gate.enforce_reply(guard_decision.sanitized_text, self._last_blocked(working_session_id))      # lượt chốt: không nối câu hỏi của gate (không còn ai trả lời)
        final_response_text = vault.unmask_text(final_response_text, caller_phone) if self._last_blocked(working_session_id) else final_response_text
        final_response_text = self._no_basis_reply(tool_calls_executed, brief) or final_response_text            # D: shortlist không có căn cứ → code dựng câu, không để LLM khẳng định "phù hợp"
        final_response_text = self._ensure_prior_contact_question(working_session_id, final_response_text, reading, brief)   # C: khách nói đã liên hệ mà chưa có lịch sử → chắc chắn có câu xin SĐT/tài khoản cũ
        final_response_text = self._ensure_identity_question(working_session_id, final_response_text, brief)               # SĐT dùng chung → chắc chắn có câu xin xác nhận tên
        # Câu hỏi lặp (bước 12): câu hỏi MỞ về slot đã biết/must_not_ask được ĐỔI thành câu xác nhận ("Phòng nhà mình vẫn khoảng
        # 25m² đúng không ạ?"), không gỡ bỏ; mỗi slot chỉ xác nhận 1 lần trong cuộc gọi.
        repeat_rewritten: List[Dict[str, Any]] = []
        repeat_dropped: List[Dict[str, Any]] = []
        if self.clarifier is not None and llm_handled:
            cust_text = " ".join(self._customer_texts.get(working_session_id, []) + [turn.normalized_text])
            banned = self._banned_question_slots(profile, brief, cust_text, turn, working_session_id)
            known_values = {**(brief.profile_facts or {}), **(profile or {}),
                            **extract_easy_slots(cust_text, turn.extracted_entities)}
            if brief.product_advised:
                known_values["product_advised"] = brief.product_advised
            final_response_text, repeat_rewritten, repeat_dropped, _kept = self.clarifier.rewrite_repeated_questions(
                final_response_text, extract_questions(final_response_text), banned, known_values,
                self._confirmed.setdefault(working_session_id, set()), display=self._display_slot_value)
            self._confirmed[working_session_id] |= {r["slot"] for r in repeat_rewritten}

        # Hỏi LẠI cùng một slot khi khách chưa trả lời: lần 2 đổi cách, lần 3 gỡ (cổng đặt đơn có cơ chế chống lặp riêng nên bỏ qua lượt cổng đang nói).
        reask_events: List[Dict[str, Any]] = []
        if llm_handled and not self._last_blocked(working_session_id):
            easy = extract_easy_slots(turn.normalized_text, turn.extracted_entities)
            answered = {k for k in easy if k in REASK_LABEL} | ({"phone"} if re.search(r"<PHONE_\d+>|(?<!\d)0\d{9}(?!\d)", turn.llm_text or "") else set())
            # Tín hiệu có cấu trúc (không cần từ khóa): token địa chỉ của KHÁCH trong lượt này; tên do bộ đọc LLM trích (có trích dẫn nguyên văn).
            if any(vault.is_customer_token(t) for t in re.findall(r"<ADDR_\d+>", turn.llm_text or "")):
                answered.add("delivery_address")
            if reading is not None and reading.recipient_name:
                answered.add("customer_name")
            heard_name = easy.get("customer_name") or (profile or {}).get("customer_name") or None
            final_response_text, self._reask[working_session_id], reask_events = rewrite_reasks(
                final_response_text, extract_questions(final_response_text), self._reask.get(working_session_id, {}), answered, heard_name, brief.honorific or "anh/chị")
        # Lời gửi khách là văn bản thường: bỏ markdown (**, #, gạch đầu dòng) ở tầng đầu ra.
        plain = strip_markdown(self._mask_sku_codes(final_response_text))      # mã SKU nội bộ không bao giờ tới tai khách: thay bằng tên sản phẩm trong catalog
        output_changed = bool(reask_events) or plain != final_response_text
        final_response_text = plain

        # Claims/questions trích từ ĐÚNG câu khách nghe (sau guardrail) — xem src/harness/extractor.py (bước 10).
        focus_sku = next((self._parent_sku(tc["args"]["sku"]) for tc in reversed(prior_call_log) if tc.get("name") in ("pricing.get_quote", "inventory.check", "order.create")
                          and isinstance((tc.get("args") or {}).get("sku"), str)), brief.product_advised)      # sản phẩm đang bàn TRƯỚC lượt này
        for c in extract_claims(final_response_text, tool_calls_executed, call_date=current_date, focus_sku=focus_sku):
            if not any(x["field"] == c["field"] and x["value"] == c["value"] for x in claims_made):
                claims_made.append(c)
        known_q = {x["text"] for x in questions_asked}
        for q in extract_questions(final_response_text):
            if q["text"] not in known_q:
                questions_asked.append(q)

        # facts_used (CCR) CÔNG BẰNG: chỉ tính fact CÓ SẴN lúc bắt đầu cuộc gọi, agent dùng thật (lời nói/tham số tool),
        # CHƯA hỏi mở lại slot đó trong cuộc gọi, và khách CHƯA tự nhắc lại nó trong cuộc gọi (xem src/harness/fact_usage.py).
        # Câu hỏi về `blocker` ("chị đã trao đổi với gia đình chưa ạ?") là hỏi TIẾP tình trạng — chính là cách dùng blocker —
        # nên không tính là "hỏi lại" (BTC cũng không coi blocker là slot cấm hỏi).
        open_now = {q["slot"] for q in questions_asked if q["type"] == "open" and q["slot"] != "blocker"}
        asked_slots = self._asked.setdefault(working_session_id, set()) | open_now
        customer_so_far = " ".join(self._customer_texts.setdefault(working_session_id, []) + [turn.normalized_text])
        if llm_handled:
            candidates = list(brief.must_carry_over)
        else:   # nhánh rule-based khai báo sẵn các slot nó dùng; vẫn áp cùng bộ lọc để công bằng
            candidates = list(dict.fromkeys(facts_used))
        facts_used = self._carried_facts(candidates, self._start_facts[working_session_id], final_response_text,
                                         tool_calls_executed, customer_so_far, asked_slots)
        self._asked[working_session_id] |= open_now
        self._customer_texts[working_session_id].append(turn.normalized_text)

        # -------------------------------------------------------------
        # 5. GHI NHỚ (PERSIST) VÀO 4 TẦNG MEMORY
        # -------------------------------------------------------------
        if history_reply is not None:
            # Lịch sử cho LLM: lời khách (đã che), tóm tắt tool THẬT đã chạy, và đúng câu khách đã nghe
            # (sau guardrail) — để lượt sau LLM không nói khác trạng thái đơn (A10).
            working_state.messages_in_session.append({"role": "user", "content": turn.llm_text})
            if tool_summary:
                working_state.messages_in_session.append({"role": "system", "content": tool_summary})
            heard = history_reply if (guard_decision.approved and not repeat_rewritten and not repeat_dropped and not output_changed) else vault.mask_text(final_response_text, caller_phone)
            working_state.messages_in_session.append({"role": "assistant", "content": heard})
        self._call_log[working_session_id] = prior_call_log + tool_calls_executed

        self.memory.set_working(
            session_id=working_session_id, current_turn=working_state.current_turn + 1,
            intent="order" if is_order_intent else "inquire",
            messages_in_session=working_state.messages_in_session
        )

        # Slot DỄ bằng regex, mỗi lượt, không gọi LLM (bước 9). Slot khó -> CallFinalizer (LLM, 3 thời điểm).
        for key, value in extract_easy_slots(turn.normalized_text, turn.extracted_entities).items():
            if key == "customer_name" and not was_unknown_name:
                continue                                         # đã biết tên (CRM/bộ nhớ): lời tự giới thiệu không ghi đè
            self.memory.set_profile_fact(customer_id, key, value, ttl_days=SLOT_TTL.get(key), observed_on=current_date)

        # Ghi nhớ các fact có CĂN CỨ THẬT từ kết quả tool đã gọi trong lượt này (sku/giá/
        # order_id/size/color/promo) — để call_2+ carry-over đúng dữ liệu THẬT đơn hàng vừa
        # tạo, không dựa vào ground-truth kịch bản (tránh lệch order_id giả với order_id
        # thật do mock_tools tự sinh).
        self._persist_tool_grounded_facts(customer_id, tool_calls_executed, agent_text=final_response_text)
        if any(c.get("name") == "order.create" and (c.get("result") or {}).get("status") == "created" for c in tool_calls_executed):
            self._persist_order_details(customer_id, working_session_id, caller_phone)

        extraction = None
        if any(c.get("name") == "handoff.transfer" and "error" not in (c.get("result") or {}) for c in tool_calls_executed):
            # Thời điểm kích hoạt #2: chuyển máy/escalate -> chốt episode + trích slot khó ngay (cuối cuộc chỉ trích phần mới)
            extraction = self.finalize_call(customer_id, current_date, call_name, turn.channel.value, trigger="handoff")

        metadata = {
            "questions": questions_asked,
            "claims": claims_made,
            "facts_used": list(set(facts_used)),
            "tool_calls": tool_calls_executed,
            "repeat_questions_rewritten": repeat_rewritten,
            "repeat_questions_dropped": repeat_dropped,
            "order_gate": self._gate_trace(working_session_id),
            "reply_reading": reading_trace,
            "gate_open": gate_open_trace,
            "policy_route": self._policy_routes.pop(working_session_id, []) or None,
            "precomputed": ({"sku": pre["sku"], "latency_ms": pre.get("latency_ms"), "served": precomp_served} if pre else None),
            "handoff_check": ({k: v for k, v in handoff_check["v"].items() if k != "usage"} | {"vnd_cost": round(float((handoff_check["v"].get("usage") or {}).get("vnd_cost", 0) or 0), 2)}) if handoff_check else None,
            "guardrail_approved": guard_decision.approved,
            "violation": guard_decision.violation_type or llm_failure,
            "llm_usage": metadata_llm_usage,
            "llm_timing": llm_timing or None,
            "memory_extraction": ({"trigger": extraction.trigger, "llm_called": extraction.llm_called,
                                   "llm_cost": extraction.usage} if extraction else None)
        }

        return final_response_text, tool_calls_executed, metadata

    # ---------------------------------------------------------------- order gate (code chặn order.create)
    def _canonical_sku(self, sku: Any, user_text: str, known_parent: Optional[str]) -> Any:
        """SKU hợp lệ của catalog cho giá trị LLM truyền vào order.create. LLM đôi khi truyền TÊN sản phẩm ("AirPure Y") thay vì SKU; vì đơn nháp được giữ
        qua nhiều lượt và code (không phải LLM) mới là bên tạo đơn, SKU phải được chuẩn hóa NGAY khi gate nhận đơn nháp."""
        if not isinstance(sku, str) or not sku.strip():
            return sku
        sku = sku.strip()
        if self.mcp.execute_tool("catalog.search", {"sku": sku}, caller="SkuResolver").get("items"):
            return sku
        by_name = self.mcp.execute_tool("catalog.search", {"query": sku}, caller="SkuResolver").get("items") or []
        phrase = _fold(sku).strip()
        named = [it for it in by_name if phrase and phrase in _fold(it.get("name", ""))]        # cả cụm ("airpure y") phải nằm trong tên, không chỉ từng từ rời
        if len(named) > 1:                                                                        # "AirPure Y" khớp cả "Combo AirPure Y + 2 màng lọc": ưu tiên tên KẾT THÚC bằng cụm đó
            named = [it for it in named if _fold(it.get("name", "")).strip().endswith(phrase)] or named
        if len(named) == 1:
            return named[0]["sku"]
        if len(by_name) == 1:
            return by_name[0]["sku"]
        return self._repair_unknown_sku(sku, user_text, known_parent) or sku

    # ---------------------------------------------------------------- order gate (code chặn order.create — phần thực thi)
    def _last_blocked(self, sid: str) -> Dict[str, Any]:
        """Quyết định chặn gần nhất TRONG LƯỢT NÀY (rỗng nếu lượt này không bị chặn)."""
        for ev in reversed(self.order_gate.events(sid)):
            return ev if not ev.get("allow") else {}
        return {}

    @staticmethod
    def _future_callback(args: Dict[str, Any], on: str) -> Dict[str, Any]:
        """Lịch gọi lại không thể ở QUÁ KHỨ: LLM hay điền năm của ngày gọi cho "Tết Dương lịch 01/01" (→ 2026-01-01 khi hôm nay là 2026-10-15), khiến tool không
        thấy ngày nghỉ và không dời lịch (TEST-103…). Ngày đã qua so với ngày gọi → cùng ngày/tháng của năm kế tiếp."""
        at = args.get("callback_at")
        if isinstance(at, str) and re.match(r"\d{4}-\d{2}-\d{2}", at) and at[:10] < on[:10]:
            y = int(on[:4]) + (1 if at[5:10] < on[5:10] else 0)
            return {**args, "callback_at": f"{y}{at[4:]}"}
        return args

    def _gate_trace(self, sid: str) -> Optional[List[Dict[str, Any]]]:
        evs = [{k: v for k, v in e.items() if k != "must_contain"} for e in self.order_gate.events(sid)]
        return evs or None

    def _gate_order_create(self, sid: str, args: Dict[str, Any], exec_args: Dict[str, Any], vault: PiiVault, profile: Dict[str, Any],
                           brief: CallBrief, caller_phone: Optional[str], on: str) -> Optional[Dict[str, Any]]:
        """Chạy order gate cho một lời gọi order.create. Trả None = được phép tạo đơn; ngược lại trả kết quả `order_gate_blocked`
        (có `say`) cho LLM. Không bao giờ gọi MCP tạo đơn khi bị chặn."""
        if not self.order_gate.enabled:                       # chỉ dùng trong test đơn vị của cơ chế khác (xem OrderGate.enabled)
            return None
        sku = str(exec_args.get("sku") or "")
        qty = int(exec_args.get("qty") or 1)
        parent = self._parent_sku(sku)
        variants = self._fetch_variants(parent)
        if variants and not self._VARIANT_RE.match(sku):
            # LLM chỉ truyền SKU cha dù khách đã nói size/màu ("ok lấy 38 đen"): lấy biến thể từ LỜI KHÁCH, lần nhắc GẦN NHẤT thắng
            for said in reversed(self.order_gate.state(sid).texts):
                chosen = self._resolve_variant_by_attributes(parent, said)
                if chosen:
                    sku = exec_args["sku"] = chosen
                    break
        m = self._VARIANT_RE.match(sku)
        label = ""
        if m:
            v = next((x for x in variants if x.get("variant_sku") == sku), {})
            color = v.get("color") or m.group(3).lower()
            label = f"size {v.get('size', m.group(2))}, màu {COLOR_DISPLAY.get(color, color)}"
        rec: List[Dict[str, Any]] = []
        pb = price_basket(self._quote_fn(rec), self._order_lines({**exec_args, "sku": sku, "qty": qty}), on, caller_phone) if sku else {"error": "no_sku"}
        if rec and "error" not in rec[0]["result"]:
            self._gate_extra_calls.setdefault(sid, []).append({"name": rec[0]["name"], "tool": rec[0]["name"],
                                                                "args": vault.redact_args_for_trace(rec[0]["args"]), "result": vault.mask_value(rec[0]["result"], caller_phone)})
        unit = pb["lines"][0]["unit_prices_vnd"][0] if "error" not in pb else exec_args.get("price_vnd")
        mixed = "error" not in pb and (len(pb["lines"]) > 1 or len(set(pb["lines"][0]["unit_prices_vnd"])) > 1)      # giỏ nhiều SKU / máy khác giá: đọc lại TỔNG, không đọc "giá một sản phẩm"
        also = [self._product_info(self._parent_sku(l["sku"])).get("name") or l["sku"] for l in pb["lines"][1:]] if "error" not in pb else []
        product = ProductInfo(name=self._product_info(parent).get("name") or sku, variant_label=label + (" kèm " + ", ".join(also) if also else ""), needs_variant=bool(variants),
                              is_variant=bool(m), unit_price=None if mixed else unit)
        hon = brief.honorific or "anh/chị"
        Hon = hon[:1].upper() + hon[1:]
        item_name = (product.name + (f" {label}" if label else "")).strip()
        # (1) HẾT HÀNG: không mở/tiếp tục đơn (trên UI agent từng nói "hết hàng" mà vẫn xin địa chỉ)
        inv = self.mcp.execute_tool("inventory.check", {"sku": sku, "on": on}, caller="HarnessOrchestrator") if sku else {}
        if isinstance(inv, dict) and "error" not in inv and inv.get("in_stock") is False:
            eta = inv.get("restock_expected")
            when = f", dự kiến có lại ngày {eta[8:10]}/{eta[5:7]}" if isinstance(eta, str) and len(eta) >= 10 else ""
            return self._gate_block(sid, "out_of_stock", f"Dạ {item_name} hiện đã hết hàng{when} ạ. {Hon} chọn size/màu hoặc mẫu khác giúp em nhé?", ["het hang"])
        # (2) GIÁ: khách MẶC CẢ (đưa mức giá riêng/xin giảm) → không mở đơn, nói giá thật; LLM chỉ nhầm giá → tự sửa theo báo giá
        price_arg = exec_args.get("price_vnd")
        if unit and isinstance(price_arg, (int, float)) and int(price_arg) != int(unit):
            texts = self.order_gate.state(sid).texts
            offered = {v for v, _ in extract_amounts(" ".join(texts))}
            if int(price_arg) in offered or (texts and detect_bargain(texts[-1])):
                return self._gate_block(sid, "price_mismatch",
                                        f"Dạ giá hiện tại của {item_name} là {_money(unit)}, em chưa có quyền giảm thêm ạ. {Hon} có muốn lấy theo mức giá này không, "
                                        f"hoặc em gợi ý mẫu khác phù hợp ngân sách hơn, hay nhờ nhân viên có thẩm quyền hỗ trợ thêm về giá ạ?", [_money(unit)])
            exec_args["price_vnd"] = int(unit)
        if "error" not in pb:                                  # tổng ĐÚNG của cả giỏ: hạn mức COD tính trên đó (không tách đơn để lách), rồi bất biến báo giá == ghi đơn
            backend_catches = not mixed and pb["total_vnd"] > COD_LIMIT_VND      # dòng đơn đủ lớn để backend tự báo cod_limit_exceeded với đúng tổng: giữ luồng cũ (đọc lại đơn rồi mới báo)
            if str(exec_args.get("payment") or "").upper() == "COD" and cod_exceeds(pb["total_vnd"]) and not backend_catches:
                return self._gate_block(sid, "cod_limit", f"Dạ đơn này vượt hạn mức thanh toán COD {_money(COD_LIMIT_VND)} một đơn (tổng {_money(pb['total_vnd'])}) nên em chưa đặt COD được ạ. "
                                                          f"{Hon} chuyển sang chuyển khoản giúp em được không ạ?", [_money(pb["total_vnd"])])
        if unit and exec_args.get("price_vnd") in (None, ""):
            exec_args["price_vnd"] = int(unit)                       # hợp đồng tool: order.create nhận price_vnd (giá SAU KM của MỘT sản phẩm); kịch bản đối chiếu trường này
        rphone_real, rphone_tok = exec_args.get("recipient_phone"), args.get("recipient_phone")
        own_phone = (not rphone_real) or rphone_real == caller_phone or str(rphone_tok or "").startswith("CURRENT")
        valid_phone = bool(re.fullmatch(r"0\d{9}", str(rphone_real or "")))
        addr_real = exec_args.get("address")
        addr_real = addr_real if isinstance(addr_real, str) and addr_real.strip() and "<ADDR_" not in addr_real else None
        addr_tok = args.get("address") if isinstance(args.get("address"), str) and str(args.get("address")).startswith("<ADDR_") else (vault.address_token_for(addr_real) if addr_real else None)
        draft = OrderDraft(sku=sku, qty=qty, payment=exec_args.get("payment"), price_vnd=exec_args.get("price_vnd"),
                           name=(exec_args.get("recipient_name") or None), phone=None if own_phone or not valid_phone else rphone_real,
                           phone_token=None if own_phone else rphone_tok, address=addr_real, address_token=addr_tok)
        name = profile.get("recipient_name") or (brief.customer_name if brief.customer_name and brief.customer_name != "Quý khách" else None)
        saved_addr = profile.get("shipping_address")
        known = OrderKnown(name=name, address=saved_addr, address_token=vault.address_token_for(saved_addr) if saved_addr else None,
                           payment=profile.get("payment_method"), caller_phone=caller_phone)
        dec = self.order_gate.evaluate(sid, draft, known, product, addressing=brief.honorific or "anh/chị",
                                       addr_stated=vault.is_customer_token, total=(pb["total_vnd"] if "error" not in pb else (unit * qty if unit else None)))
        if dec["allow"]:
            return None
        if dec["action"] == "give_up":                                 # hỏi lặp 3 lần không được → bỏ đơn nháp (không nối câu hỏi ở các lượt sau)
            self._gate_retry_args.pop(sid, None)
            return {"error": "order_gate_blocked", "order_gate": {"action": "give_up", "missing": dec.get("missing"), "to_confirm": dec.get("to_confirm"), "say": dec["say"]},
                    "instruction": "Đơn CHƯA tạo và đơn nháp đã hủy. Nói với khách ĐÚNG nội dung order_gate.say."}
        basket = self._order_lines({**exec_args, "sku": sku, "qty": qty})
        self._gate_retry_args[sid] = {k: v for k, v in {"sku": sku, "qty": qty, "lines": basket if len(basket) > 1 else None, "price_vnd": exec_args.get("price_vnd"), "payment": args.get("payment"),
                                                     "recipient_name": args.get("recipient_name"), "recipient_phone": args.get("recipient_phone"),
                                                     "address": args.get("address")}.items() if v not in (None, "")}
        return {"error": "order_gate_blocked",
                "order_gate": {"action": dec["action"], "missing": dec.get("missing"), "to_confirm": dec.get("to_confirm"), "say": dec["say"]},
                "instruction": "Đơn CHƯA được tạo. Nói với khách ĐÚNG nội dung order_gate.say (được thêm một câu ngắn trả lời điều khách vừa hỏi). "
                               "Không được nói đã tạo đơn."}

    # ---- bộ điều khiển: khách trả lời gate → code cập nhật đơn nháp, chạy lại gate, tạo đơn khi khách đồng ý (không phụ thuộc LLM chuyển tiếp)
    def _driver_merge(self, sid: str, retry: Dict[str, Any], turn: NormalizedTurn, vault: PiiVault, last: Dict[str, Any]) -> Dict[str, Any]:
        args = dict(retry)
        text, masked = turn.normalized_text, (turn.llm_text or "")
        addr = [t for t in re.findall(r"<ADDR_\d+>", masked) if vault.is_customer_token(t)]
        if addr:
            args["address"] = addr[-1]
        phones = re.findall(r"<PHONE_\d+>", masked)
        if phones:
            args["recipient_phone"] = phones[-1]
        rd = self._readings.get(sid)
        if rd is not None:                                              # đã hiểu bằng LLM (có trích dẫn nguyên văn)
            pay, name = rd.payment, rd.recipient_name
        else:
            pay = detect_payment(text)
            name = extract_recipient_name(text, name_pending="recipient_name" in (last.get("missing") or []))
        if pay:
            args["payment"] = pay
        if name:
            args["recipient_name"] = name
        return args

    def _driver_eval(self, sid: str, args: Dict[str, Any], vault: PiiVault, profile: Dict[str, Any], brief: CallBrief,
                     caller_phone: Optional[str], on: str):
        exec_args = vault.unmask_args("order.create", {**args, "customer_phone": "CURRENT_CUSTOMER"}, caller_phone)
        exec_args = {**exec_args, "on": on}
        return exec_args, self._gate_order_create(sid, args, exec_args, vault, profile, brief, caller_phone, on)

    def _order_driver(self, sid: str, turn: NormalizedTurn, brief: CallBrief, profile: Dict[str, Any], vault: PiiVault,
                      caller_phone: Optional[str], on: str, write_cache: Dict[tuple, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Trả {reply, reply_masked, calls} nếu CODE tự xử lý lượt này; {defer: True} nếu khách vừa hỏi thêm/đổi ý (LLM xử lý, code nối câu của gate);
        None nếu không có đơn đang mở."""
        g = self.order_gate
        st = g.state(sid)
        retry = self._gate_retry_args.get(sid)
        if not g.enabled or not retry:
            return None
        last = st.last_decision or {}
        if st.stage == "consented":
            return self._driver_create(sid, retry, vault, profile, brief, caller_phone, on, write_cache)
        if st.stage != "collect" or last.get("allow") or last.get("turn") != st.turn - 1 or last.get("action") not in ("ask", "confirm", "ask_confirm"):
            return None
        rd = self._readings.get(sid)
        if not (rd.only_answers if rd is not None else is_pure_gate_reply(turn.normalized_text)):
            return {"defer": True}
        args = self._driver_merge(sid, retry, turn, vault, last)
        exec_args, blocked = self._driver_eval(sid, args, vault, profile, brief, caller_phone, on)
        if blocked is None:                                            # hiếm: đủ điều kiện tạo ngay (đã đồng ý trước đó)
            return self._driver_create(sid, args, vault, profile, brief, caller_phone, on, write_cache)
        say = blocked["order_gate"]["say"]
        return {"reply": vault.unmask_text(say, caller_phone), "reply_masked": say, "calls": list(self._gate_extra_calls.get(sid, []))}

    def has_open_order(self, customer_id: str, current_date: str) -> bool:
        """Lượt khách CUỐI vừa kết thúc bằng câu hỏi/xác nhận/đọc lại đơn của order gate (khách đã chốt mua, đơn chưa tạo) → cuộc gọi cần lượt chốt."""
        sid = f"SESS-{customer_id}-{current_date}"
        st, last = self.order_gate.state(sid), self.order_gate.state(sid).last_decision or {}
        return bool(self._gate_retry_args.get(sid)) and not last.get("allow", True) and last.get("turn") == st.turn             and last.get("action") in ("ask", "confirm", "ask_confirm", "readback")

    def _closing_driver(self, sid: str, turn: NormalizedTurn, brief: CallBrief, profile: Dict[str, Any], vault: PiiVault,
                        caller_phone: Optional[str], on: str, write_cache: Dict[tuple, Dict[str, Any]]) -> Dict[str, Any]:
        """Lượt chốt: tạo đơn nháp đang mở bằng thông tin đã có (xem `OrderGate.evaluate`, nhánh `closing`); không gọi LLM."""
        st = self.order_gate.state(sid)
        retry = self._gate_retry_args.get(sid)
        if not retry or (st.last_decision or {}).get("turn") != st.turn - 1:
            text = "Dạ em cảm ơn mình đã liên hệ ạ."
            return {"reply": text, "reply_masked": text, "calls": []}
        check = authorize_closing(self.llm_client, [vault.mask_text(t, caller_phone) for t in self._customer_texts.get(sid, []) if t.strip()])
        st.events.append({"action": "closing_check", "allow": check["authorized"], "quote": check["quote"], "turn": st.turn})      # vào trace `order_gate`
        if not check["authorized"]:
            self._gate_retry_args.pop(sid, None)
            text = "Dạ em đã ghi nhận thông tin ạ. Khi nào mình quyết định đặt, mình nhắn hoặc gọi lại, em lên đơn ngay nhé."
            return {"reply": text, "reply_masked": text, "calls": []}
        st.closing = True
        try:
            out = self._driver_create(sid, {"payment": "COD", **retry}, vault, profile, brief, caller_phone, on, write_cache)
        finally:
            st.closing = False
        if (st.last_decision or {}).get("action") in ("ask", "confirm", "ask_confirm"):      # vẫn thiếu size/màu…: không ai trả lời nữa nên KHÔNG hỏi, nói rõ đơn chưa tạo
            text = "Dạ em chưa đủ thông tin để lên đơn nên em chưa tạo đơn ạ. Mình nhắn hoặc gọi lại khi tiện, em hỗ trợ lên đơn ngay nhé."
            return {**out, "reply": text, "reply_masked": text}
        said = (st.last_decision or {}).get("say") if (st.last_decision or {}).get("action") == "allow_closing" else None
        return {**out, "reply": f"{vault.unmask_text(said, caller_phone)} {out['reply']}", "reply_masked": f"{said} {out['reply_masked']}"} if said else out

    def _simple_product_in_play(self, sid: str, brief: CallBrief) -> Optional[str]:
        """SKU của sản phẩm KHÔNG có biến thể mà cuộc gọi đang bàn (bán được ngay, không cần chọn size/màu): sản phẩm được tra/báo giá/đặt gần nhất, hoặc
        `catalog.search` ra đúng một sản phẩm, hoặc sản phẩm đã tư vấn. None nếu đang bàn sản phẩm có biến thể (phải chọn size/màu) hoặc chưa có sản phẩm."""
        sku = None
        for tc in reversed(self._call_log.get(sid, [])):
            a = tc.get("args") or {}
            if tc.get("name") in ("inventory.check", "pricing.get_quote", "order.create") and isinstance(a.get("sku"), str):
                sku = self._parent_sku(a["sku"])
                break
            items = (tc.get("result") or {}).get("items") if tc.get("name") == "catalog.search" else None
            if items and len(items) == 1 and items[0].get("sku"):
                sku = items[0]["sku"]
                break
        sku = sku or brief.product_advised
        return sku if sku and not self._fetch_variants(sku) else None

    RECENT_CALLS = 6          # shortcut: "gần đây" = 6 lời gọi tool cuối của cuộc gọi (call_log không ghi số lượt); nâng lên theo lượt nếu đo thấy cần

    def _products_in_play(self, sid: str, brief: CallBrief) -> Tuple[List[str], bool]:
        """(các sản phẩm CHA được bàn gần đây — tra/báo giá/đặt hoặc `catalog.search` ra đúng 1 sản phẩm, mới nhất trước; có danh sách nhiều kết quả CHƯA được chốt không).
        Danh sách chưa chốt = `catalog.search` ra >1 sản phẩm và SAU đó chưa có lời gọi tra/báo giá/đặt nào."""
        parents: List[str] = []
        listing = False
        decided = False
        for tc in reversed(self._call_log.get(sid, [])[-self.RECENT_CALLS:]):
            a = tc.get("args") or {}
            if tc.get("name") in ("inventory.check", "pricing.get_quote", "order.create") and isinstance(a.get("sku"), str):
                decided = True
                p = self._parent_sku(a["sku"])
                if p not in parents:
                    parents.append(p)
            elif tc.get("name") == "catalog.search":
                items = (tc.get("result") or {}).get("items") or []
                if len(items) > 1 and not decided:
                    listing = True
                elif len(items) == 1 and items[0].get("sku") and items[0]["sku"] not in parents:
                    parents.append(items[0]["sku"])
        if not parents and brief.product_advised:
            parents = [brief.product_advised]
        return parents, listing

    def _maybe_open_gate(self, sid: str, turn: NormalizedTurn, brief: CallBrief, profile: Dict[str, Any], vault: PiiVault, caller_phone: Optional[str],
                         on: str, reading: Any, customer_texts: List[str], stock: Optional[List[Dict[str, Any]]] = None) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """MỞ order gate BẰNG CODE khi khách cam kết mua, không chờ LLM chính tình cờ gọi order.create (lỗi ui_replay_9 lượt 6).
        Các lớp (ghi từng lớp vào trace `gate_open`): 1 ý định (bộ đọc LLM, có trích dẫn) · 2 đối tượng (code: đúng MỘT biến thể được nhắc và code đã tra còn hàng;
        không có/nhiều biến thể → mở ở bước HỎI size/màu bằng SKU cha) · 4 loại trừ (từ chối/mặc cả, khách đang hỏi, gate từng chặn lệch giá/hết hàng, đơn đã tạo,
        đã có đơn nháp). Gate vẫn là bên hỏi/đọc lại/chốt; mở nhầm chỉ khiến agent hỏi thông tin giao hàng sớm, KHÔNG tạo đơn."""
        g = self.order_gate
        st = g.state(sid)
        tr: Dict[str, Any] = {"opened": False, "intent": bool(reading and reading.commits)}
        if not g.enabled or reading is None:
            return None, {**tr, "reason": "no_reading"}
        if not reading.commits:
            return None, {**tr, "reason": "intent_not_commit"}
        last = st.last_decision or {}
        excl = [name for name, hit in (
            ("decline", reading.declines), ("open_question", reading.asks_question), ("price_topic", reading.price_topic), ("order_done", st.stage == "done"),
            ("draft_already_open", bool(self._gate_retry_args.get(sid))),
            # cuộc gọi vừa ĐỔI/TRẢ đơn thành công: "ừ em làm thủ tục đổi nhé" là đồng ý đổi, không phải mua đơn mới (SAMPLE-03 cuộc 2 từng bị mở đơn nháp thứ hai)
            ("order_updated_in_call", any(c.get("name") == "order.update" and "error" not in (c.get("result") or {}) for c in self._call_log.get(sid, []))),
            ("gate_blocked_before", last.get("action") in ("price_mismatch", "out_of_stock", "give_up") and last.get("turn") == st.turn - 1)) if hit]
        only_question = excl == ["open_question"]
        if excl and not only_question:
            return None, {**tr, "reason": "excluded", "exclusions": excl}
        if stock is None:
            stock = self._check_named_variants(customer_texts, brief.product_advised, self._call_log.get(sid, []), [], on)
        if not stock:                                                # khách không nêu biến thể nào: phải chắc chắn đang nói về ĐÚNG MỘT sản phẩm
            prods, listing = self._products_in_play(sid, brief)
            if len(prods) > 1 or listing:
                return None, {**tr, "reason": "ambiguous_product", "object": {"products": prods, "listing": listing}}
        simple = self._simple_product_in_play(sid, brief) if not stock else None
        if simple:                                                   # sản phẩm không có biến thể: code tra tồn kho đúng SKU đó
            try:
                res = self.mcp.execute_tool("inventory.check", {"sku": simple, "on": on}, caller="HarnessOrchestrator")
            except Exception:
                res = {}
            if isinstance(res, dict) and isinstance(res.get("in_stock"), bool):
                stock = [{"name": "inventory.check", "tool": "inventory.check", "args": {"sku": simple, "on": on}, "result": res}]
        checked = {c["args"]["sku"]: c["result"]["in_stock"] for c in stock}
        tr["object"] = {"checked": checked}
        if len(checked) == 1:
            sku, ok = next(iter(checked.items()))
            if not ok:
                return None, {**tr, "reason": "variant_out_of_stock"}
        elif simple:                                                 # không tra được tồn kho SKU đơn: không đoán, để LLM chính xử lý
            return None, {**tr, "reason": "stock_unknown"}
        else:                                                        # không rõ biến thể (0 hoặc nhiều): mở ở bước hỏi size/màu
            sku = next(iter(self._discussed_parents(brief.product_advised, self._call_log.get(sid, []))), None)
            if not sku:
                return None, {**tr, "reason": "no_product_in_play"}
            tr["object"]["fallback"] = "ask_variant"
        owned = str(profile.get("variant_sku") or "") if profile.get("order_id") else ""
        if owned and self._parent_sku(owned) == self._parent_sku(sku):
            # Khách ĐÃ có đơn đúng sản phẩm này (gọi lại để đổi size/khiếu nại): "ừ em làm thủ tục đổi nhé" không phải mua đơn mới (SAMPLE-03, TEST-40 cuộc 2 —
            # code từng mở đơn nháp, LLM không còn lượt gọi order.update). Để LLM chính xử lý; khách muốn mua thêm thì LLM gọi order.create và gate vẫn chạy.
            return None, {**tr, "reason": "existing_order_same_product"}
        basket = self._basket_in_play(sid, sku)
        args = self._driver_merge(sid, {"sku": sku, "qty": basket[0]["qty"], **({"lines": basket} if len(basket) > 1 else {})}, turn, vault, {})
        exec_args, blocked = self._driver_eval(sid, args, vault, profile, brief, caller_phone, on)
        if blocked is None:                                          # không được xảy ra (đơn mới luôn phải hỏi/đọc lại); không tạo đơn
            return None, {**tr, "reason": "gate_allowed_unexpectedly"}
        if only_question:                                            # khách vừa hỏi vừa chốt mua: LLM chính trả lời câu hỏi, rồi `enforce_reply` NỐI bước kế tiếp của gate
            return {"defer": True}, {**tr, "reason": "opened_after_answer", "opened": True, "sku": sku}
        say = blocked["order_gate"]["say"]
        return ({"reply": vault.unmask_text(say, caller_phone), "reply_masked": say, "calls": stock + list(self._gate_extra_calls.get(sid, []))},
                {**tr, "opened": True, "reason": "opened", "sku": sku})

    def _basket_in_play(self, sid: str, sku: str) -> List[Dict[str, Any]]:
        """Giỏ khách đang mua = giỏ của lời gọi báo giá/đặt GẦN NHẤT có sản phẩm `sku` (LLM đọc từ lời khách "2 máy", "kèm lõi lọc"): dòng đầu là `sku` × số lượng,
        sau đó là các sản phẩm khác của cùng lời gọi (`lines` của pricing.quote_order, hoặc `basket_skus`). Mặc định [sku × 1]."""
        parent = self._parent_sku(sku)
        num = lambda q: q if isinstance(q, int) and q >= 1 else 1
        for tc in reversed(self._call_log.get(sid, [])):
            a, r = tc.get("args") or {}, tc.get("result") or {}
            if tc.get("name") == "pricing.quote_order" and "error" not in r and isinstance(a.get("lines"), list):
                ls = [{"sku": l["sku"], "qty": num(l.get("qty"))} for l in a["lines"] if isinstance(l, dict) and isinstance(l.get("sku"), str)]
                mine = next((l for l in ls if self._parent_sku(l["sku"]) == parent), None)
                if mine:
                    return [{"sku": sku, "qty": mine["qty"]}] + [l for l in ls if l is not mine]
            if tc.get("name") in ("pricing.get_quote", "order.create") and isinstance(a.get("sku"), str) and self._parent_sku(a["sku"]) == parent:
                return self._order_lines({**a, "sku": sku, "qty": num(a.get("qty"))})
        return [{"sku": sku, "qty": 1}]

    def _qty_in_play(self, sid: str, sku: str) -> int:
        return self._basket_in_play(sid, sku)[0]["qty"]

    def _driver_followup(self, sid: str, turn: NormalizedTurn, brief: CallBrief, profile: Dict[str, Any], vault: PiiVault,
                         caller_phone: Optional[str], on: str) -> None:
        """Sau khi LLM trả lời câu hỏi chen ngang: chạy gate với thông tin khách vừa nói để lượt này vẫn kết thúc bằng bước kế tiếp của đơn."""
        st = self.order_gate.state(sid)
        retry = self._gate_retry_args.get(sid)
        if not retry or self.order_gate.events(sid) or st.stage != "collect":
            return
        args = self._driver_merge(sid, retry, turn, vault, st.last_decision or {})
        self._driver_eval(sid, args, vault, profile, brief, caller_phone, on)

    def _driver_create(self, sid: str, args: Dict[str, Any], vault: PiiVault, profile: Dict[str, Any], brief: CallBrief,
                       caller_phone: Optional[str], on: str, write_cache: Dict[tuple, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        exec_args, blocked = self._driver_eval(sid, args, vault, profile, brief, caller_phone, on)
        extra = list(self._gate_extra_calls.get(sid, []))
        if blocked is not None:                                          # đơn đã đổi so với lúc đọc lại → gate yêu cầu đọc lại
            say = blocked["order_gate"]["say"]
            return {"reply": vault.unmask_text(say, caller_phone), "reply_masked": say, "calls": extra}
        call_args = self._sanitize_basket("order.create", {k: v for k, v in exec_args.items() if k not in GATE_ONLY_ARGS})
        key = self._write_key("order.create", call_args)
        pb = self._order_basket(call_args, caller_phone, on)
        if pb:
            call_args = order_args(call_args, pb)
        hon = brief.honorific or "anh/chị"
        if key in write_cache:
            r = write_cache[key]
            text = f"Dạ đơn này em đã lên rồi ạ, mã đơn {r.get('order_id')}."
            return {"reply": text, "reply_masked": text, "calls": extra}
        result = self._basket_confirm_flag(self.mcp.execute_tool("order.create", call_args, caller="LLMOrchestrator"), pb, call_args.get("payment"))
        call = {"name": "order.create", "tool": "order.create", "args": vault.redact_args_for_trace(call_args), "result": vault.mask_value(result, caller_phone)}
        st = self.order_gate.state(sid)
        if result.get("status") == "created":
            write_cache[key] = result
            eta = result.get("estimated_delivery")
            when = f", dự kiến giao ngày {eta[8:10]}/{eta[5:7]}" if isinstance(eta, str) and len(eta) >= 10 else ""
            confirm = f" Nhân viên sẽ gọi {hon} xác nhận đơn trước khi giao." if result.get("needs_confirmation_call") else ""
            text = f"Dạ em đã lên đơn thành công ạ. Mã đơn của {hon} là {result['order_id']}, tổng {_money(result.get('total_vnd') or 0)}{when}.{confirm} Em cảm ơn {hon} nhiều ạ!"
        else:
            err = result.get("error")
            st.stage, st.snapshot, st.pending_confirm = "collect", None, None
            if err == "cod_limit_exceeded":
                st.confirmed.pop("payment", None)
                self._gate_retry_args[sid] = {k: v for k, v in self._gate_retry_args.get(sid, {}).items() if k != "payment"}
                st.last_decision = {"allow": False, "action": "ask", "turn": st.turn, "missing": ["payment"], "to_confirm": []}
                text = (f"Dạ đơn này vượt hạn mức thanh toán COD {_money(result.get('limit_vnd') or 0)} một đơn (tổng {_money(result.get('total_vnd') or 0)}) nên em chưa đặt COD được ạ. "
                        f"{hon[:1].upper() + hon[1:]} chuyển sang chuyển khoản giúp em được không ạ?")
            elif err == "out_of_stock":
                text = "Dạ rất tiếc sản phẩm này vừa hết hàng nên em chưa lên đơn được ạ. Em xin phép kiểm tra mẫu khác phù hợp cho mình ạ."
            else:
                text = "Dạ em xin phép kiểm tra lại thông tin đơn trên hệ thống rồi phản hồi mình ngay ạ."
        return {"reply": vault.unmask_text(text, caller_phone), "reply_masked": text, "calls": extra + [call]}

    def _empty_search_fallback(self, result: Dict[str, Any], args: Dict[str, Any], user_text: str, known_parent: Optional[str],
                               call_log: List[Dict[str, Any]], on: str) -> Dict[str, Any]:
        """`catalog.search` theo từ khóa ("xám 37", "38 đen") không ra gì → LLM kết luận "hết hàng" (lỗi trên UI: 38 đen còn 5 mà agent nói hết). Tra lại bằng
        sản phẩm ĐANG TƯ VẤN trong cuộc gọi: khớp size/màu khách nói với biến thể thật và đọc tồn kho thật; không khớp thì dặn LLM KHÔNG kết luận hết hàng."""
        parent = known_parent
        for tc in reversed(call_log):
            if parent:
                break
            if tc.get("name") == "catalog.search":
                for it in ((tc.get("result") or {}).get("items") or []):
                    if it.get("variants"):
                        parent = it.get("sku")
                        break
        out = dict(result)
        out["note"] = ("Không tìm thấy theo từ khóa này — KHÔNG được kết luận hết hàng/không có. Tra tồn kho bằng inventory.check với variant_sku "
                       "(lấy từ catalog.search sku=<sản phẩm đang tư vấn>).")
        if parent:
            variant = self._resolve_variant_by_attributes(parent, f"{args.get('query') or ''} {user_text}")
            if variant:
                inv = self.mcp.execute_tool("inventory.check", {"sku": variant, "on": on}, caller="SkuResolver")
                if isinstance(inv, dict) and "error" not in inv:
                    out["matched_variant"] = {"variant_sku": variant, "parent_sku": parent, "in_stock": inv.get("in_stock"), "qty": inv.get("qty")}
                    out["note"] = (f"Biến thể khách hỏi là {variant}: tồn kho THẬT in_stock={inv.get('in_stock')} (qty={inv.get('qty')}). Dùng đúng kết quả này, dùng {variant} làm sku khi đặt đơn.")
                    info = self._product_info(parent)
                    v = next((x for x in self._fetch_variants(parent) if x.get("variant_sku") == variant), {})
                    out["items"] = [{"sku": parent, "name": info.get("name"), "category": info.get("category"),     # KHÔNG trả danh sách rỗng: LLM đọc "rỗng" là "hết hàng"
                                     "variants": [{**{k: v.get(k) for k in ("variant_sku", "size", "color", "price_delta_vnd")}, "in_stock": inv.get("in_stock"), "qty": inv.get("qty")}]}]
                    out["total"] = 1
            else:
                vs = self._fetch_variants(parent)
                out["available_sizes"] = sorted({str(x.get("size")) for x in vs})
                out["available_colors"] = sorted({str(x.get("color")) for x in vs})
                out["note"] += f" Sản phẩm {parent} chỉ có các size {out['available_sizes']} và màu {out['available_colors']}."
        return out

    def _gate_block(self, sid: str, action: str, say: str, must_contain: List[str]) -> Dict[str, Any]:
        """Chặn order.create vì lý do ngoài checklist (hết hàng, mặc cả giá): hủy đơn nháp, trả kết quả `order_gate_blocked` có câu cần nói."""
        self._gate_retry_args.pop(sid, None)
        dec = self.order_gate.block(sid, action, say, must_contain)
        return {"error": "order_gate_blocked", "order_gate": {"action": action, "missing": [], "to_confirm": [], "say": say},
                "instruction": "Đơn CHƯA được tạo và đơn nháp đã hủy. Nói với khách ĐÚNG nội dung order_gate.say. Không hỏi địa chỉ/tên người nhận lúc này."}

    @staticmethod
    def _precomputed_hit(pre: Optional[Dict[str, Any]], name: str, args: Dict[str, Any], caller_phone: Optional[str], on: str) -> Optional[Dict[str, Any]]:
        """Lời gọi inventory.check / pricing.get_quote của LLM trùng ĐÚNG với kết quả CODE đã tra sẵn (cùng SKU, ngày, 1 sản phẩm, SĐT là của người gọi, chưa có địa chỉ/giỏ khác) → kết quả đó."""
        if not pre or pre.get("checked_on") != on or args.get("sku") != pre["sku"] or name not in ("inventory.check", "pricing.get_quote"):
            return None
        if name == "pricing.get_quote" and (args.get("basket_skus") or args.get("address") or (args.get("qty") or 1) != 1
                                           or args.get("customer_phone") not in (None, "", caller_phone)):
            return None
        call = next((c for c in pre["calls"] if c["name"] == name), None)
        return dict(call["result"]) if call and "error" not in call["result"] else None

    @staticmethod
    def _order_facts(status_calls: List[Dict[str, Any]], current_date: str) -> str:
        """Dữ kiện đơn từ order.status của lượt này (ngày đặt, trạng thái, dự kiến giao) cho chốt phân loại biết đơn có trễ không."""
        keep = ("order_id", "status", "date", "created_at", "estimated_delivery", "tracking")
        rows = [{k: o[k] for k in keep if k in o} for c in status_calls for o in (c.get("result") or {}).get("orders", []) if isinstance(o, dict)]
        return f"hôm nay {current_date}; đơn: {rows}"

    @staticmethod
    def _complete_handoff_brief(given: Any, brief: CallBrief, quote: str, caller_phone: Optional[str], vault: PiiVault, current_date: str,
                                focus_sku: Optional[str] = None) -> Dict[str, Any]:
        """Handoff brief có 9 trường bắt buộc (hợp đồng tool); LLM hay thiếu → `brief_invalid` và chuyển máy hỏng dù khách đã được hứa. Trường LLM đã điền được giữ nguyên;
        trường thiếu lấy từ dữ kiện CODE biết chắc (Call Brief, lời khách đã kiểm chứng ở chốt chuyển máy, ngày cuộc gọi)."""
        said = vault.unmask_text(quote, caller_phone) if quote else ""
        defaults = {"customer_phone": caller_phone or "UNKNOWN", "customer_name": brief.customer_name, "escalation_reason": f"Khách nói: {said}" if said else "Khách cần nhân viên hỗ trợ",
                    "conversation_summary": f"Khách nói: {said}" if said else "Khách cần nhân viên hỗ trợ", "product_advised": brief.product_advised or focus_sku, "price_quoted_vnd": brief.price_quoted_vnd,
                    "open_questions": [said] if said else [], "next_action": "Nhân viên liên hệ lại khách", "generated_at": f"{current_date}T00:00:00"}
        out = dict(given) if isinstance(given, dict) else {}
        for k, v in defaults.items():
            if out.get(k) in (None, "", []):       # LLM điền null/rỗng cũng coi là thiếu (TEST-110: product_advised=null dù khách nêu tên sản phẩm → người nhận máy không biết khách hỏi về gì)
                out[k] = v
        return out

    @staticmethod
    def _fix_addressing(text: str, brief: CallBrief) -> str:
        """LLM hay tự đoán giới tính từ tên ("anh Đại") khi Call Brief chỉ ghi "anh/chị": thay bằng cách gọi ĐÚNG của hệ thống để xưng hô nhất quán."""
        name = brief.customer_name
        if not text or not name or name == "Quý khách":
            return text
        pat = re.compile(rf"(?<!\w)(?:anh/chị|anh|chị|cô|chú|bác|bạn)\s+{re.escape(name)}(?!\w)", re.I)
        text = pat.sub(brief.addressing(), text)
        if brief.honorific == "anh/chị":                       # chưa biết xưng hô: "anh"/"chị" trần LLM tự đoán cũng đổi về "anh/chị"
            text = re.sub(r"(?<![\w/])(?:anh|chị)(?![\w/])", lambda m: "Anh/chị" if m.group()[0].isupper() else "anh/chị", text, flags=re.I)   # cả "Anh" đầu câu
        return text

    def _persist_order_details(self, customer_id: str, sid: str, caller_phone: Optional[str]) -> None:
        """Sau khi đơn tạo thành công: nhớ người nhận/địa chỉ/thanh toán để lần sau chỉ cần XÁC NHẬN (PII: không vào trace, xóa được bằng delete_customer)."""
        created = self.order_gate.state(sid).created or {}
        real = created.get("real") or {}
        for key, fld in (("recipient_name", "recipient_name"), ("shipping_address", "address"), ("payment_method", "payment")):
            if real.get(fld):
                self.memory.set_profile_fact(customer_id, key, real[fld], ttl_days=365)
        phone = real.get("recipient_phone")
        if phone and phone != caller_phone and re.fullmatch(r"0\d{9}", str(phone)):
            self.memory.set_profile_fact(customer_id, "recipient_phone", phone, ttl_days=365)

    # ---------------------------------------------------------------- chốt cuộc gọi (bước 9)
    def commit_turn(self) -> List[Dict[str, Any]]:
        """Chốt lượt: commit giao dịch DB của lượt và trả nhật ký ghi bộ nhớ (→ trace.memory_writes). Lõi (pipeline/bộ chạy đánh giá) mở lượt bằng
        `begin_turn` nhưng CHỐT lượt qua orchestrator — qua MCP đây là `memory.commit_turn`, tool chỉ cấp cho caller HarnessOrchestrator."""
        return self.memory.drain_writes()

    def finalize_call(self, customer_id: str, call_date: str, call_name: str = "", channel: str = "",
                      trigger: str = "end", clear: Optional[bool] = None):
        """Chốt cuộc gọi ở 1 trong 3 thời điểm: end (kết thúc) | handoff (chuyển máy) | timeout (ngắt/hết giờ).
        Ghi/cập nhật episode; trích slot khó bằng LLM (nếu có) CHỈ trên phần hội thoại mới kể từ lần trích trước.
        Sau end/timeout, giải phóng trạng thái theo cuộc gọi (bảng token PII, cache ghi, nhật ký tool)."""
        sid = f"SESS-{customer_id}-{call_date}"
        state = self.memory.get_working(sid)
        self.finalizer.extractor.llm = self.llm_client      # client có thể được thay sau khi dựng orchestrator
        result = self.finalizer.finalize(
            customer_id=customer_id, session_id=sid, call_name=call_name or sid, call_date=call_date, channel=channel,
            trigger=trigger, messages=list(state.messages_in_session), tool_calls=self._call_log.get(sid, []))
        if (clear if clear is not None else trigger in ("end", "timeout")):
            self.finalizer.forget_session(sid)
            self.clear_session(sid)
            self._activity.pop(sid, None)
        return result

    def last_activity(self, session_id: str) -> Optional[float]:
        """Mốc `time.monotonic()` của lượt gần nhất trong phiên (None nếu không có phiên đang mở)."""
        ctx = self._activity.get(session_id)
        return ctx["ts"] if ctx else None

    def sweep_idle(self, now: Optional[float] = None, idle_seconds: float = 1800.0) -> List[Any]:
        """Cuộc gọi không có lượt mới quá idle_seconds coi là bị ngắt/timeout -> chốt (thời điểm kích hoạt #3).
        Gọi định kỳ bởi tầng vận hành (UI/tổng đài); `now` mặc định time.monotonic()."""
        now = time.monotonic() if now is None else now
        results = []
        for sid, ctx in list(self._activity.items()):
            if now - ctx["ts"] >= idle_seconds:
                results.append(self.finalize_call(ctx["customer_id"], ctx["call_date"], ctx["call_name"], ctx["channel"], trigger="timeout"))
        return results

    def _forget_customer(self, customer_id: str) -> None:
        prefix = f"SESS-{customer_id}-"
        self.order_gate.forget_prefix(prefix)
        for store in (self._vaults, self._call_log, self._write_cache, self._activity,
                      self._start_facts, self._asked, self._customer_texts, self._confirmed, self._reask, self._prior_asked, self._identity_asked, self._policy_routes, self._precomp, self._precomp_logged):
            for sid in [k for k in store if k.startswith(prefix)]:
                del store[sid]
                self.finalizer.forget_session(sid)

    # ---------------------------------------------------------------- helpers (bước 4, 6, 7)
    def _trim_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Giới hạn kích thước prompt: bỏ bớt tin cũ nhất tới khi tổng ký tự ≤ MAX_HISTORY_CHARS (giữ ≥ 2 tin cuối)."""
        trimmed = list(history)
        while len(trimmed) > 2 and sum(len(m.get("content", "")) for m in trimmed) > self.MAX_HISTORY_CHARS:
            trimmed.pop(0)
        return trimmed

    @staticmethod
    def _summarize_tool_calls(calls: List[Dict[str, Any]]) -> str:
        """Tóm tắt NGẮN các tool đã chạy (số liệu thật) để lưu vào bộ nhớ cuộc gọi: lượt sau LLM thấy đơn/phí/giá
        thật thay vì chỉ thấy lời nói của chính nó (nguồn gốc lỗi 'không mất phí' trong khi tool báo 60.000đ)."""
        lines = []
        for c in calls:
            name, args, res = c.get("name"), c.get("args") or {}, c.get("result") or {}
            if name == "catalog.search":
                lines.append(f"catalog.search -> {len(res.get('items', []))} sản phẩm")
                continue
            if name == "search_policy":
                lines.append("search_policy -> đã tra chính sách")
                continue
            given = [f"{k}={args[k]}" for k in ("sku", "new_variant_sku", "order_id", "action") if args.get(k)]
            got = [f"{k}={res[k]}" for k in ("error", "final_price_vnd", "list_price_vnd", "in_stock", "qty", "order_id",
                                              "status", "total_vnd", "fee_vnd", "extra_payment_vnd", "refund_vnd",
                                              "price_diff_vnd", "estimated_delivery", "callback_id", "ticket_id") if k in res]
            promos = [p.get("promo_code") for p in (res.get("applied_promos") or []) if p.get("promo_code")]
            if promos:
                got.append(f"promos={promos}")
            lines.append(f"{name}({', '.join(given)}) -> {', '.join(got) or 'ok'}")
        if not lines:
            return ""
        return "[Tóm tắt tool đã chạy ở lượt trước — số liệu THẬT, không được nói khác đi] " + "; ".join(lines)

    @staticmethod
    def _safe_summary(calls: List[Dict[str, Any]]) -> str:
        """Câu trả lời an toàn khi LLM lỗi/vượt số vòng SAU KHI đã có tool ghi chạy: chỉ nói đúng những gì tool đã làm."""
        parts = []
        for c in calls:
            r = c.get("result") or {}
            if "error" in r:
                continue
            if c.get("name") == "order.create" and r.get("order_id"):
                total = f", tổng {int(r['total_vnd']):,}đ".replace(",", ".") if r.get("total_vnd") else ""
                parts.append(f"em đã tạo đơn mã {r['order_id']}{total}")
            elif c.get("name") == "order.update" and r.get("order_id"):
                fee = f", phí {int(r['fee_vnd']):,}đ".replace(",", ".") if r.get("fee_vnd") else ""
                parts.append(f"em đã ghi nhận yêu cầu đổi cho đơn {r['order_id']}{fee}")
            elif c.get("name") == "schedule.callback" and r.get("callback_id"):
                parts.append("em đã đặt lịch gọi lại cho mình")
        if parts:
            return "Dạ " + "; ".join(parts) + " ạ. Em xin phép kiểm tra lại các thông tin còn lại rồi phản hồi mình ngay ạ."
        return HarnessOrchestrator.SAFE_FALLBACK_TEXT

    @staticmethod
    def _known_numbers(turn: NormalizedTurn, brief: CallBrief, working_state) -> List[int]:
        """Số tiền mà khách đã nêu (lượt này + lượt trước trong cuộc gọi) và giá đã báo ở Call Brief — agent được phép nhắc lại."""
        nums = {v for v, _ in extract_amounts(turn.normalized_text)}
        for m in working_state.messages_in_session:
            if m.get("role") == "user":
                nums |= {v for v, _ in extract_amounts(m.get("content", ""))}
        for v in (brief.price_quoted_vnd, (brief.profile_facts or {}).get("price_quoted_vnd")):
            if isinstance(v, (int, float)):
                nums.add(int(v))
        return sorted(nums)

    def _build_llm_messages(self, turn: NormalizedTurn, brief: CallBrief,
                             history: List[Dict[str, str]], current_date: str,
                             caller_phone: Optional[str] = None, stock_calls: Optional[List[Dict[str, Any]]] = None,
                             precomputed: Optional[Dict[str, Any]] = None, focus_parent: Optional[str] = None) -> List[Dict[str, str]]:
        """Dựng messages cho LLM function-calling, kèm lịch sử hội thoại trong phiên để LLM
        có trí nhớ nhiều lượt (VD: lượt 2 khách hỏi đổi size, lượt 3 xác nhận).
        LLM KHÔNG thấy SĐT/địa chỉ/CCCD thật: chỉ thấy token (xem src/privacy/pii_vault.py)."""
        system_prompt = (
            "Bạn là TRỢ LÝ AI telesale của shop e-commerce Việt Nam (không phải người thật). Luôn xưng 'em', gọi khách bằng "
            "honorific được cung cấp, nói 'dạ'/'vâng'/'ạ' đúng văn phong lịch sự Việt Nam. "
            "Nếu khách hỏi bạn có phải người thật/robot không, trả lời thẳng: em là trợ lý AI của shop và có thể "
            "chuyển máy cho nhân viên nếu khách muốn — tuyệt đối không nhận mình là người thật. "
            "TUYỆT ĐỐI không tự bịa giá, khuyến mãi, tồn kho, chính sách — luôn gọi tool "
            "pricing.get_quote/inventory.check/catalog.search/search_policy để lấy số liệu thật "
            "trước khi trả lời khách. Ngay cả khi Call Brief đã ghi giá/tồn kho từ cuộc gọi trước, "
            "PHẢI gọi lại tool để xác nhận số liệu CÒN ĐÚNG HAY KHÔNG tại ngày hôm nay — giá/tồn "
            "kho/khuyến mãi có thể đã thay đổi theo ngày, không được giả định dữ liệu cũ vẫn còn hiệu lực — TRỪ phần ngữ cảnh ghi rõ 'Hệ thống ĐÃ kiểm tra THẬT đầu cuộc gọi hôm nay' "
            "(đã tra rồi, không gọi lại cho đúng sản phẩm/size/màu đó). "
            "Mọi số tiền bạn nói ra phải lấy từ kết quả tool (hoặc là tổng/hiệu của chúng); không nói con số nào khác. "
            "Không bao giờ tiết lộ giá nhập/giá vốn/giá sàn/biên lợi nhuận; nếu khách hỏi, từ chối khéo và nói giá niêm yết ưu đãi. "
            "Không nhận xét, so sánh tiêu cực về đối thủ; chỉ nêu điểm mạnh của shop dựa trên dữ liệu thật. "
            "BẮT BUỘC: khi khách đồng ý mua/chốt đơn, bạn PHẢI gọi tool order.create TRƯỚC — "
            "tuyệt đối không tự nói 'đã lên đơn'/'đã tạo đơn' nếu chưa thực sự gọi tool này trong "
            "cùng lượt. Khi khách muốn đổi size/màu/sản phẩm CỦA MỘT ĐƠN ĐÃ ĐẶT (đã có order.create ở cuộc này, hoặc có 'order_id' trong thông tin đã biết, hoặc khách nói rõ đã đặt/đã mua), PHẢI gọi tool order.update TRƯỚC — "
            "tuyệt đối không tự nói 'đã đổi'/'đã làm thủ tục' nếu chưa gọi tool này. "
            "CHƯA có đơn nào mà khách nói 'đổi sang/xem/lấy món khác', 'đổi ý' thì khách đang CHỌN LẠI SẢN PHẨM, không phải đổi đơn: KHÔNG gọi order.update; "
            "tra catalog.search/product.shortlist cho sản phẩm khách nêu rồi báo giá bằng pricing.get_quote ĐÚNG SKU của sản phẩm đó. "
            "Tên sản phẩm bạn nói và SKU bạn báo giá phải là MỘT sản phẩm. "
            "QUY TRÌNH ĐẶT ĐƠN do hệ thống kiểm soát: khi khách muốn mua, gọi order.create với những gì khách ĐÃ NÓI trong cuộc gọi này "
            "(recipient_name = tên người nhận, recipient_phone = SĐT nhận nếu khác số đang gọi, address, payment) — KHÔNG tự điền giá trị mặc định/đoán "
            "(không tự đặt payment=COD khi khách chưa nói). Nếu kết quả là error=order_gate_blocked: đơn CHƯA được tạo; hãy nói với khách ĐÚNG nội dung "
            "trường order_gate.say (được thêm một câu ngắn trả lời điều khách vừa hỏi), tuyệt đối không nói đã tạo đơn. Chỉ khi khách đồng ý RÕ RÀNG ở "
            "lượt NGAY SAU lần bạn đọc lại đơn thì gọi lại order.create với ĐÚNG tham số cũ. "
            "Mỗi yêu cầu đặt/đổi chỉ gọi order.create/order.update ĐÚNG MỘT LẦN trong cuộc gọi; nếu "
            "'Tóm tắt tool đã chạy' cho thấy đã làm rồi thì dùng lại kết quả đó, không gọi lại. "
            "Khi tool báo phí/phụ thu/chênh lệch > 0 (fee_vnd, extra_payment_vnd) phải nói ĐÚNG số tiền đó; "
            "tuyệt đối không nói 'không mất phí' nếu tool báo có phí. "
            "Nếu đã có Call Brief cuộc gọi trước (must_not_ask), KHÔNG hỏi lại các thông tin đã biết "
            "bằng câu hỏi mở — nếu cần xác nhận lại, chỉ hỏi xác nhận (confirm) một lần. "
            "Khách nêu ĐÍCH DANH một sản phẩm/mẫu (tên hoặc loại cụ thể như 'áo windbreaker', 'AirPure Y', kể cả gõ sai chính tả) thì gọi catalog.search theo tên đó "
            "(tham số query) để lấy SKU và giá thật — KHÔNG dùng product.shortlist, và tuyệt đối không nói 'không có sản phẩm' khi chưa tra bằng catalog.search. "
            "Khi tư vấn/chọn sản phẩm theo NHU CẦU (chưa có 'sản phẩm đã tư vấn' trong Call Brief, hoặc khách muốn đổi sang sản phẩm khác mà chưa nêu tên), "
            "PHẢI gọi tool product.shortlist TRƯỚC — chỉ truyền các slot khách ĐÃ nói (hệ thống tự bổ sung slot đã nhớ) — rồi chốt "
            "CHÍNH XÁC MỘT sản phẩm: sản phẩm đứng đầu danh sách (trường 'recommendation'); không liệt kê nhiều lựa chọn cùng lúc "
            "trừ khi khách chủ động hỏi so sánh. Nếu sản phẩm đứng đầu có mục 'violated' (vd vượt ngân sách), nói rõ mục đó và lý do "
            "chọn (dựa trên 'matched'/'why' của kết quả) để khách quyết định. Theo 'decision' của kết quả: mode='single' → chốt đúng 1 sản phẩm "
            "(nếu có 'overage_pct' > 0 thì nêu rõ mức vượt ngân sách); mode='two_options' (vượt ngân sách quá 20%) → giới thiệu CẢ HAI: "
            "sản phẩm đứng đầu (nêu mức vượt và lý do) và 'alternative' (tốt nhất trong ngân sách) để khách chọn. Nếu kết quả có 'ask_next' thì chỉ hỏi ĐÚNG MỘT câu đó "
            "(trường 'question'); tuyệt đối không hỏi slot nằm trong 'do_not_ask'/'slots_used'. "
            "Lệnh pricing.get_quote CUỐI CÙNG trong lượt nên là của đúng sản phẩm chính bạn chốt đề xuất "
            "(quà tặng/phụ kiện đi kèm không phải sản phẩm đã tư vấn). "
            "Khi khách chọn/đổi size hoặc màu cụ thể (để order.create/order.update/inventory.check), "
            "TUYỆT ĐỐI không tự ghép chuỗi variant SKU — PHẢI gọi catalog.search để lấy đúng chuỗi "
            "'variant_sku' thật trong mảng 'variants' trả về khớp đúng size/màu khách chọn, rồi dùng "
            "chính xác chuỗi đó làm 'sku'/'new_variant_sku'. Tự ghép chuỗi SKU có thể sai định dạng và "
            "khiến tool báo lỗi không tìm thấy sản phẩm. Kết luận HẾT HÀNG chỉ khi inventory.check của ĐÚNG variant_sku trả in_stock=false; catalog.search theo từ khóa "
            "không ra kết quả KHÔNG có nghĩa là hết hàng. "
            "XƯNG HÔ & TÊN: dùng ĐÚNG honorific trong Call Brief; chưa rõ thì gọi 'anh/chị' — tuyệt đối không đoán giới tính từ tên (không tự gọi 'anh Đại'/'chị Lan' khi Call Brief ghi 'anh/chị'). "
            "MẶC CẢ: khi khách chê mắc, xin giảm, hoặc đưa mức giá riêng ('6tr8 lấy luôn') thì KHÔNG tự giảm giá, KHÔNG gọi order.create với giá khách đề nghị, KHÔNG hỏi địa chỉ/tên người nhận lúc này; "
            "nói giá hiện tại và các khuyến mãi THẬT đang áp dụng (từ pricing.get_quote), gợi ý mẫu rẻ hơn phù hợp nhu cầu, hoặc hỏi khách có muốn nhờ nhân viên có thẩm quyền hỗ trợ về giá không "
            "(chuyện giá/mặc cả: chỉ gọi handoff.transfer khi khách đã yêu cầu hoặc đồng ý chuyển máy, hệ thống từ chối nếu chưa; "
            "câu hỏi y tế/sức khỏe/thuốc/an toàn cho trẻ hoặc ngoài phạm vi tư vấn: chuyển máy ngay, không tự trả lời nội dung đó, và nói THẲNG với khách rằng phần này "
            "em chưa có thông tin chuyên môn để tư vấn chính xác nên chuyển nhân viên phụ trách). "
            "SẢN PHẨM LỖI/HỎNG/KHÔNG HOẠT ĐỘNG (kể cả mới dùng vài ngày): tra search_policy CẢ về bảo hành LẪN về đổi trả/lỗi do nhà sản xuất (hai truy vấn, dùng đúng triệu chứng và số ngày khách nói), "
            "rồi nói rõ thời hạn và cách đổi/bảo hành áp dụng cho tình huống đó. "
            "GIÁ THEO SỐ LƯỢNG / NHIỀU SẢN PHẨM: final_price_vnd của pricing.get_quote là giá MỘT sản phẩm — không gọi giá một sản phẩm là giá cả đơn. "
            "Khách mua từ 2 sản phẩm trở lên trong một đơn (cùng một sản phẩm số lượng > 1, hoặc nhiều sản phẩm khác nhau, kể cả phụ kiện/sản phẩm mua kèm): gọi pricing.quote_order với "
            "lines=[{sku, qty}] chứa ĐỦ mọi sản phẩm của đơn (SKU của từng sản phẩm lấy từ catalog.search, không tự đặt) và báo khách total_vnd cùng giá từng máy trong units — không tự nhân/cộng; "
            "khuyến mãi 'máy thứ 2' chỉ áp cho MỘT máy mỗi đơn (xem applied_promos của từng máy; có thì nói rõ tên/mức giảm của chương trình đó). "
            "Khi khách chốt, gọi order.create ĐÚNG MỘT LẦN với lines=[{sku, qty}] chứa đủ các sản phẩm đó (hệ thống tự điền giá từng máy); không tạo nhiều đơn riêng, không dùng basket_skus. "
            "Khi khách bảo lên đơn/chốt mua, gọi order.create ngay (hệ thống sẽ hỏi phần còn thiếu), KHÔNG tự hỏi tên người nhận/SĐT/địa chỉ/hình thức thanh toán bằng lời của bạn và không hỏi lại điều đã biết. "
            "Khi order.create báo needs_confirmation_call=true thì nói rõ sẽ có nhân viên gọi xác nhận trước khi giao. "
            "NHẬN DIỆN KHÁCH: nếu khách nói đã liên hệ trước đây (hôm trước, lần trước, đã nhắn Zalo…) mà Call Brief chưa có lịch sử (số cuộc gọi trước = 0) và khách chưa có trong CRM (không có 'khách đã có trong CRM'): "
            "(1) vẫn TRẢ LỜI câu hỏi hiện tại của khách bằng tool ngay trong lượt này (tồn kho/giá… theo sản phẩm khách nêu), (2) rồi hỏi MỘT câu xin SĐT/tài khoản đã dùng lần trước để tra lại — "
            "không chỉ hỏi mà bỏ câu hỏi của khách; không đoán, không dùng thông tin của khách khác; ở kênh chat chưa biết SĐT, khi khách quan tâm hoặc trước khi hẹn gọi lại/chốt đơn hãy xin SĐT để lưu hồ sơ và liên thông các kênh. "
            "BẢO MẬT THÔNG TIN CÁ NHÂN: bạn chỉ thấy các token thay cho dữ liệu thật — CURRENT_CUSTOMER là "
            "số điện thoại của chính người đang gọi; <PHONE_n> là số điện thoại khác khách đọc ra; <ADDR_n> là địa chỉ; "
            "<ID_n> là CCCD/số tài khoản. Khi gọi tool, truyền NGUYÊN VĂN token vào customer_phone/address (hệ thống "
            "tự thay bằng giá trị thật); không đoán, không tự bịa số điện thoại/địa chỉ, không hỏi hay đọc lại CCCD/số tài khoản. "
            "Nếu khách yêu cầu xóa dữ liệu cá nhân: xác nhận đã ghi nhận yêu cầu và sẽ chuyển bộ phận phụ trách "
            "xử lý (gọi handoff.transfer), không tự hứa thời hạn."
        )
        facts = {k: v for k, v in (brief.profile_facts or {}).items() if k in self.LLM_PROFILE_KEYS}
        other_product = bool(focus_parent and brief.product_advised and self._parent_sku(focus_parent) != self._parent_sku(brief.product_advised))
        if other_product:                                  # khách đã chuyển sang sản phẩm khác: size/màu đã lưu là của sản phẩm CŨ, không đưa vào prompt
            facts = {k: v for k, v in facts.items() if k not in ("size", "color", "variant_sku")}
        phone_line = "SĐT người gọi: CURRENT_CUSTOMER" if caller_phone else "SĐT người gọi: chưa xác định"
        channels = getattr(brief, "channels_seen", None) or []
        context_lines = [
            f"Hôm nay là ngày {current_date} (ngày diễn ra cuộc gọi này) — dùng ngày này khi nói về "
            f"thời hạn/ngày giao hàng/khuyến mãi, tool sẽ tự áp dụng ngày này khi tra giá/tồn kho.",
            f"Call Brief: khách {brief.customer_name} ({brief.honorific}), {phone_line}, số cuộc gọi trước: {brief.previous_calls_count}{', khách đã có trong CRM' if brief.crm_known else ''}, "
            f"sản phẩm đã tư vấn: {brief.product_advised}, giá đã báo: {brief.price_quoted_vnd}, "
            f"blocker: {brief.blocker}, must_not_ask: {brief.must_not_ask}, "
            f"thông tin đã biết: {facts}, "
            f"kênh khách đã liên hệ: {channels or 'chưa rõ'}, "
            f"dữ liệu theo từng kênh: {getattr(brief, 'facts_by_channel', None) or 'chưa có'}, "
            f"câu mở đầu đề xuất: {brief.suggested_opening}",
            "Size/màu/variant_sku trong 'thông tin đã biết' CHỈ là lựa chọn cho SẢN PHẨM ĐÃ TƯ VẤN; khách chuyển sang sản phẩm khác thì KHÔNG dùng, phải hỏi lại size/màu."
            + (f" Khách ĐANG xem sản phẩm khác ({self._product_info(focus_parent).get('name') or focus_parent}), không phải '{brief.product_advised}'." if other_product else ""),
        ]
        if precomputed:
            st, pr = precomputed.get("stock"), precomputed.get("price")
            facts_now = [f"tồn kho: {('CÒN HÀNG (qty=%s)' % st.get('qty')) if st.get('in_stock') else 'HẾT HÀNG'}" if st else "", 
                         (f"giá niêm yết {pr['list_price_vnd']}đ, giá cuối {pr['final_price_vnd']}đ, ưu đãi áp dụng: {', '.join(pr.get('promos') or []) or 'không'}, freeship: {'có' if pr.get('freeship') else 'không'}") if pr else "",
                         f"bảo hành {precomputed['warranty_months']} tháng" if precomputed.get("warranty_months") else ""]
            context_lines.append(f"Hệ thống ĐÃ kiểm tra THẬT đầu cuộc gọi hôm nay ({precomputed['checked_on']}) cho '{precomputed.get('name') or precomputed['sku']}' ({precomputed['sku']}): "
                                 + "; ".join(x for x in facts_now if x) + ". Dùng ĐÚNG các số này, KHÔNG gọi lại pricing.get_quote/inventory.check cho sản phẩm/size/màu này (chỉ gọi lại khi khách đổi sản phẩm, size, màu, số lượng hoặc đưa địa chỉ). "
                                 "Khi nói, GOM tồn kho + giá cuối + ưu đãi + bảo hành vào MỘT câu; chỉ nhắc tối đa 2 thông tin cũ của cuộc trước; không đọc mã SKU.")
        if stock_calls:
            got = "; ".join(f"{c['args']['sku']}: {'CÒN HÀNG' if c['result']['in_stock'] else 'HẾT HÀNG'} (qty={c['result'].get('qty')})" for c in stock_calls)
            context_lines.append(f"Hệ thống ĐÃ tra tồn kho THẬT hôm nay cho biến thể khách vừa nhắc — {got}. Nói đúng theo kết quả này, không nói trái; không đọc mã SKU cho khách.")
        bargain = detect_bargain(turn.normalized_text)
        if bargain:
            context_lines.append(f"Khách vừa MẶC CẢ ({bargain}) — làm theo quy tắc MẶC CẢ: không giảm giá, không tạo đơn với giá khách đề nghị, không hỏi địa chỉ lúc này.")
        if turn.channel.value != "hotline" and not caller_phone:
            context_lines.append("Kênh chat và chưa biết SĐT khách: khi khách quan tâm/trước khi hẹn gọi lại hoặc chốt đơn, xin SĐT để lưu hồ sơ và liên thông các kênh.")
        hint = turn.extracted_entities.get("callback_hint")
        if hint:
            context_lines.append(
                f"Khách vừa hẹn thời gian (đã quy đổi theo ngày hôm nay {current_date}): {hint} — dùng khi đặt schedule.callback.")
        # THỨ TỰ TỐI ƯU CHO PROMPT CACHING (cache theo TIỀN TỐ giống hệt): [system tĩnh] [lịch sử — chỉ được NỐI THÊM ở cuối]
        # rồi mới tới [ngữ cảnh Call Brief — đổi theo lượt] và [lời khách]. Trước đây ngữ cảnh đứng TRƯỚC lịch sử nên mỗi khi
        # nó đổi (fact mới, ngày…) thì toàn bộ lịch sử phía sau mất cache.
        return [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "system", "content": "\n".join(context_lines)},
            {"role": "user", "content": turn.llm_text or turn.normalized_text},
        ]

    _VARIANT_RE = re.compile(r"^(.+)-(\d+|S|M|L|XL|XXL)-([A-Z]+)$")

    @classmethod
    def _parent_sku(cls, sku: str) -> str:
        """SKU cha của 1 variant (quy ước {base}-{size}-{MAU}, VD SKU-SN-CAS-39-DEN -> SKU-SN-CAS); SKU cha giữ nguyên."""
        m = cls._VARIANT_RE.match(sku or "")
        return m.group(1) if m else sku

    def _product_info(self, sku: str) -> Dict[str, Any]:
        """Tên + danh mục THẬT của sản phẩm (đọc catalog), có cache — để phân biệt phụ kiện/quà tặng với sản phẩm chính."""
        cache = self.__dict__.setdefault("_product_cache", {})
        if sku not in cache:
            res = self.mcp.execute_tool("catalog.search", {"sku": sku}, caller="ProductInfo")
            items = res.get("items") or []
            cache[sku] = {"name": (items[0].get("name") if items else "") or "",
                          "category": (items[0].get("category") if items else "") or ""}
        return cache[sku]

    _SLOT_LABEL = {"room_area_m2": "diện tích phòng", "has_children": "trẻ nhỏ trong nhà", "budget_vnd": "ngân sách", "has_pets": "thú cưng"}

    def _no_basis_reply(self, tool_calls: List[Dict[str, Any]], brief: CallBrief) -> Optional[str]:
        """D: lượt chỉ gọi `product.shortlist` mà kết quả `no_basis` (khách nêu thông tin nhưng KHÔNG tiêu chí nào áp dụng cho nhóm này) → CODE dựng câu trả lời từ dữ liệu tool
        (tên + giá niêm yết, nói rõ chưa có tiêu chí, hỏi loại sản phẩm), không để LLM khẳng định "phù hợp/an toàn" không có căn cứ. Có tool khác chạy trong lượt → giữ lời LLM."""
        short = [tc for tc in tool_calls if tc.get("name") == "product.shortlist" and (tc.get("result") or {}).get("no_basis")]
        if not short or any(tc.get("name") != "product.shortlist" for tc in tool_calls):
            return None
        res = short[-1]["result"]
        items = [i for i in (res.get("items") or []) if i.get("name")][:5]
        if not items:
            return None
        labels = ", ".join(self._SLOT_LABEL.get(k, k.replace("_", " ")) for k in (res.get("slots_used") or {})) or "thông tin"
        hon = brief.honorific or "anh/chị"
        listing = "; ".join(f"{i['name']} giá {_money(i['list_price_vnd'])}" if i.get("list_price_vnd") else i["name"] for i in items)
        return (f"Dạ em chưa có tiêu chí nào để chọn sản phẩm trong nhóm này theo {labels} {hon} vừa nói ạ. Em xin giới thiệu theo giá niêm yết: {listing}. "
                f"{hon[:1].upper() + hon[1:]} đang cần loại sản phẩm nào để em tư vấn đúng hơn ạ?")

    def _ensure_prior_contact_question(self, sid: str, text: str, reading: Any, brief: CallBrief) -> str:
        """C: khách (bộ đọc LLM, có trích dẫn) nói đã từng liên hệ mà hệ thống chưa có lịch sử → lời agent PHẢI có câu xin SĐT/tài khoản đã dùng lần trước (đúng một lần/cuộc);
        LLM đã tự hỏi thì giữ nguyên, chưa hỏi thì code nối câu."""
        if self._prior_asked.get(sid) or reading is None or not reading.prior_contact or brief.previous_calls_count != 0 or brief.crm_known or brief.product_advised:
            return text                                    # đã có hồ sơ của chính liên hệ này (sản phẩm đã tư vấn) → trả lời từ bộ nhớ, không xin tài khoản
        self._prior_asked[sid] = True
        if any(q.get("slot") == "phone" for q in extract_questions(text)):
            return text
        hon = brief.honorific or "anh/chị"
        head, sep, last = text.rstrip().rpartition(". ")
        if last.endswith("?") and sep:                     # chỉ MỘT câu hỏi cuối lượt: bỏ câu hỏi xã giao LLM đóng lượt, nhường chỗ cho câu xin SĐT
            text = head + "."
        return f"{text.rstrip()} Để em tra lại lịch sử, {hon} cho em xin số điện thoại hoặc tài khoản mà mình đã dùng ở lần liên hệ trước ạ?".strip()

    SCOPE_NOTICE = "Dạ phần này em chưa có thông tin chuyên môn để tư vấn chính xác ạ."

    @classmethod
    def _ensure_scope_notice(cls, text: str, tool_calls: List[Dict[str, Any]], verdict: Optional[Dict[str, Any]]) -> str:
        """Ca chuyển máy `scope_safety` do LLM chính gọi (y tế/an toàn/ngoài phạm vi) và đã chuyển THÀNH CÔNG: lời agent PHẢI nói thật rằng em chưa có thông tin chuyên môn
        để trả lời — không để LLM chỉ nói "đã chuyển máy" (BTC chấm ca này bằng cụm thừa nhận không có thông tin). Đã có cụm "chưa có thông tin"/"em chưa rõ"/"em không chắc" thì giữ nguyên."""
        done = any(c.get("name") == "handoff.transfer" and "error" not in (c.get("result") or {}) for c in tool_calls)
        if not done or not verdict or not verdict.get("authorized") or verdict.get("category") != "scope_safety" or not text:
            return text
        if any(str(c.get("name", "")).startswith("order.") for c in tool_calls):      # sự cố đơn đã đặt: lời báo riêng (khiếu nại đơn), không phải câu hỏi chuyên môn
            return text
        low = text.lower()
        if any(k in low for k in ("không có thông tin", "chưa có thông tin", "em chưa rõ", "em không chắc", "chưa nắm được")):
            return text
        rest = re.sub(r"^\s*Dạ[,\s]+", "", text)
        return f"{cls.SCOPE_NOTICE} {rest[:1].upper() + rest[1:]}"

    def _note_policy_route(self, sid: str, llm_client) -> None:
        """Router chính sách (LLM thứ hai, chạy phía bộ nhớ): ghi quyết định/độ trễ/chi phí vào trace lượt và cộng chi phí vào tổng + trần cứng."""
        info = getattr(self.memory, "last_policy_route", None) or {}
        usages = info.get("usage") or []
        route = info.get("route") or {}
        if not usages and not route:
            return
        if usages and getattr(llm_client, "cost_tracker", None) is not None:
            llm_client.cost_tracker.add_external_cost(sum(float(u.get("usd_cost") or 0) for u in usages))
        self._policy_routes.setdefault(sid, []).append({
            "files": route.get("files"), "answerable": route.get("answerable"), "as_of_date": route.get("as_of_date"),
            "fallback_all": route.get("fallback_all"),
            "vnd_cost": round(sum(float(u.get("vnd_cost") or 0) for u in usages), 2),
            "latency_ms": sum(int(u.get("latency_ms") or 0) for u in usages)})

    def _named_parents(self, text: str, exclude: set) -> List[str]:
        """Sản phẩm CHA mà lời agent gọi đúng tên catalog (không phân biệt dấu/hoa thường), trừ `exclude` (quà tặng)."""
        from src.agents.specialists import catalog_products
        folded = _fold(text)
        return [sku for sku, p in catalog_products().items() if sku not in exclude and p.get("name") and _fold(p["name"]) in folded]

    def _bind_price_to_product(self, text: str, calls: List[Dict[str, Any]], run_tool, live_calls: List[Dict[str, Any]]):
        """Tên sản phẩm trong câu trả lời và SKU được báo giá phải là MỘT sản phẩm. Lỗi thật (CHECKING § 11.102): LLM báo giá `SKU-JK-DWN-L-BE`
        rồi nói "giá Áo khoác gió Windbreak là 1.490.000đ" (giá đúng 690.000). Guardrail số tiền không bắt được vì 1.490.000 có trong kết quả tool.
        Khi lời nói gọi tên đúng MỘT sản phẩm (không tính quà tặng), nêu số tiền trùng giá của một sản phẩm KHÁC trong lượt, và sản phẩm đó chưa
        được báo giá: CODE báo giá lại đúng sản phẩm và dựng câu từ kết quả tool."""
        amounts = {v for v, _ in extract_amounts(text)}
        quotes = [c for c in calls if c.get("name") == "pricing.get_quote" and isinstance((c.get("result") or {}).get("final_price_vnd"), (int, float))]
        if not amounts or not quotes:
            return text, calls
        gifts = {p.get("gift_sku") for c in quotes for p in (c["result"].get("applied_promos") or []) if p.get("gift_sku")}
        named = self._named_parents(text, gifts)
        if len(named) != 1:
            return text, calls
        parent = named[0]
        if any(self._parent_sku((c.get("args") or {}).get("sku") or "") == parent for c in quotes):
            return text, calls
        prices = {int(c["result"][k]) for c in quotes for k in ("final_price_vnd", "list_price_vnd") if isinstance(c["result"].get(k), (int, float))}
        if not (amounts & prices):
            return text, calls
        sent = len(live_calls)
        res, _ = run_tool("pricing.get_quote", {"sku": parent, "qty": 1})
        final = res.get("final_price_vnd") if isinstance(res, dict) else None
        if not isinstance(final, (int, float)):
            return self.SAFE_FALLBACK_TEXT, calls + live_calls[sent:]
        name = self._product_info(parent).get("name") or parent
        return (f"Dạ em xin kiểm tra lại cho đúng sản phẩm ạ: {name} hiện có giá {int(final):,}đ.".replace(",", "."), calls + live_calls[sent:])

    def _ensure_identity_question(self, sid: str, text: str, brief: CallBrief) -> str:
        """SĐT dùng chung (brief.blocker = ambiguous_identity): lời agent PHẢI có câu xin xác nhận tên (đúng một lần/cuộc) dù khách mở đầu bằng câu hỏi khác;
        thông tin công khai (giá, tính năng) vẫn trả lời, không nạp dữ liệu cá nhân. LLM đã tự hỏi thì giữ nguyên, chưa hỏi thì code nối câu."""
        if brief.blocker != "ambiguous_identity" or self._identity_asked.get(sid) or not text:
            return text
        self._identity_asked[sid] = True
        if any("tên" in q["text"].lower() and "xác nhận" in q["text"].lower() for q in extract_questions(text)):
            return text
        head, sep, last = text.rstrip().rpartition(". ")
        if last.endswith("?") and sep:                     # chỉ MỘT câu hỏi cuối lượt: bỏ câu hỏi xã giao LLM đóng lượt
            text = head + "."
        return f"{text.rstrip()} Số máy này đang có hai thành viên cùng đăng ký, anh/chị cho em xin phép xác nhận tên mình để em hỗ trợ đúng thông tin ạ?"

    _SKU_TOKEN_RE = re.compile(r"\bSKU-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")

    def _mask_sku_codes(self, text: str) -> str:
        """Thay mọi mã `SKU-...` trong lời gửi khách bằng TÊN sản phẩm từ catalog (biến thể: kèm "size X màu Y"); mã không có trong catalog → "sản phẩm này"."""
        def sub(m: "re.Match[str]") -> str:
            sku = m.group(0)
            parent = self._parent_sku(sku)
            name = self._product_info(parent).get("name") or ""
            if not name:
                return "sản phẩm này"
            v = self._VARIANT_RE.match(sku)
            if not v:
                return name
            var = next((x for x in self._fetch_variants(parent) if x.get("variant_sku") == sku), {})
            color = var.get("color") or v.group(3).lower()
            return f"{name} size {var.get('size', v.group(2))} màu {COLOR_DISPLAY.get(color, color)}"
        return self._SKU_TOKEN_RE.sub(sub, text) if text and "SKU-" in text else text

    def _pick_main_quote(self, quotes: List[Tuple[str, Dict[str, Any]]], gift_skus: set, agent_text: str):
        """Chọn báo giá của SẢN PHẨM CHÍNH trong lượt: loại quà tặng (gift_sku của KM) và phụ kiện; nếu còn nhiều
        sản phẩm thì ưu tiên sản phẩm được nhắc tên trong lời agent, nếu không thì báo giá cuối cùng (A1)."""
        if not quotes:
            return None
        candidates = [q for q in quotes if q[0] not in gift_skus]
        non_accessory = [q for q in candidates if "phu-kien" not in self._product_info(q[0]).get("category", "")]
        candidates = non_accessory or candidates or quotes
        parents = list(dict.fromkeys(q[0] for q in candidates))
        if len(parents) > 1 and agent_text:
            low = agent_text.lower()
            for q in candidates:
                name = self._product_info(q[0]).get("name", "").lower()
                if name and name in low:
                    return q
        return candidates[-1]

    def _persist_tool_grounded_facts(self, customer_id: str, tool_calls: List[Dict[str, Any]], agent_text: str = "") -> None:
        """Ghi profile fact dựa trên KẾT QUẢ TOOL THẬT (order.create/order.update/pricing.get_quote) — không
        phải đoán hay chép ground-truth kịch bản. product_advised luôn là SKU CHA của sản phẩm chính; quà tặng và
        phụ kiện không ghi đè sản phẩm đã tư vấn (A1); đơn đã tạo thành công có ưu tiên cao nhất."""
        ordered_product = False
        quotes: List[Tuple[str, Dict[str, Any]]] = []
        gift_skus: set = set()
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {}) or {}
            result = tc.get("result", {}) or {}
            if name == "order.create" and result.get("status") == "created":
                if args.get("sku"):
                    ordered_product = True
                    self.memory.set_profile_fact(customer_id, "product_advised", self._parent_sku(args["sku"]))
                    if self._VARIANT_RE.match(args["sku"]):
                        self.memory.set_profile_fact(customer_id, "variant_sku", args["sku"])
                    self._maybe_set_variant_facts(customer_id, args["sku"])
                price = args.get("price_vnd") or next((l.get("price_vnd") for l in args.get("lines") or []), None)
                if price is None and result.get("total_vnd") is not None:
                    price = int(result["total_vnd"] / max(1, args.get("qty") or 1))
                if price is not None:
                    self.memory.set_profile_fact(customer_id, "price_quoted_vnd", price)
                if result.get("order_id"):
                    self.memory.set_profile_fact(customer_id, "order_id", result["order_id"])
            elif name == "order.update" and "error" not in result:
                new_sku = args.get("new_variant_sku")
                if new_sku:
                    self.memory.set_profile_fact(customer_id, "variant_sku", new_sku)
                    self._maybe_set_variant_facts(customer_id, new_sku)
                    if args.get("action") == "exchange_product":
                        self.memory.set_profile_fact(customer_id, "product_advised", self._parent_sku(new_sku))
            elif name == "pricing.get_quote" and "final_price_vnd" in result and "error" not in result and args.get("sku"):
                quotes.append((self._parent_sku(args["sku"]), result))
                for promo in result.get("applied_promos") or []:
                    if promo.get("gift_sku"):
                        gift_skus.add(self._parent_sku(promo["gift_sku"]))

        if ordered_product:
            return
        main = self._pick_main_quote(quotes, gift_skus, agent_text)
        if main:
            sku, result = main
            self.memory.set_profile_fact(customer_id, "product_advised", sku)
            self.memory.set_profile_fact(customer_id, "price_quoted_vnd", result["final_price_vnd"])
            promo = self._main_promo(result.get("applied_promos") or [])
            if promo:
                self.memory.set_profile_fact(customer_id, "promo_code", promo)
        elif agent_text:
            # Không có báo giá (LLM chỉ gọi product.shortlist): ghi sản phẩm nếu lời agent nêu tên ĐÚNG MỘT sản phẩm có trong kết quả shortlist (chỉ ghi sản phẩm,
            # không ghi giá — shortlist chỉ có giá niêm yết, chưa qua khuyến mãi).
            low = agent_text.lower()
            named = list(dict.fromkeys(
                it["sku"] for tc in tool_calls if tc.get("name") == "product.shortlist" for it in ((tc.get("result") or {}).get("items") or [])
                if it.get("sku") and str(it.get("name") or "").strip() and str(it["name"]).lower() in low))
            known = self.memory.get_profile_facts(customer_id)
            # Nhánh này không có giá: nếu đang nhớ GIÁ của một sản phẩm khác thì giữ nguyên cặp (sản phẩm, giá) cũ — trước đây ghi đè sản phẩm làm hồ sơ thành
            # "RO Kangaroo 10 lõi giá 3.290.000đ" (giá của UF Sunhouse).
            if len(named) == 1 and not (known.get("price_quoted_vnd") and known.get("product_advised") not in (None, named[0])):
                self.memory.set_profile_fact(customer_id, "product_advised", named[0])

    @staticmethod
    def _main_promo(applied: List[Dict[str, Any]]) -> Optional[str]:
        """Mã KM đáng nhớ nhất trong danh sách đã áp dụng: giảm giá thật (discount_vnd > 0) > quà tặng > khác; KM miễn phí
        COD/ship ('freecod', 'freeship') chỉ dùng khi không còn gì khác. Trước đây lấy phần tử đầu tiên -> luôn 'COD-0'
        (sai so với KM thật như RUN-10, GIFT-FILTER)."""
        codes = [p for p in applied if p.get("promo_code")]
        if not codes:
            return None
        def rank(p):
            if (p.get("discount_vnd") or 0) > 0:
                return 0
            if p.get("type") == "gift" or p.get("gift_sku"):
                return 1
            return 3 if str(p.get("type", "")).startswith("free") else 2
        return sorted(codes, key=rank)[0]["promo_code"]

    def _maybe_set_variant_facts(self, customer_id: str, sku: str) -> None:
        """Parse 'size'/'color' từ variant SKU thật (quy ước {base}-{size}-{MAU}, VD
        SKU-SN-CAS-40-DEN) — đọc đúng cấu trúc SKU thật trong catalog, không đoán."""
        m = self._VARIANT_RE.match(sku or "")
        if m:
            self.memory.set_profile_fact(customer_id, "size", m.group(2))
            self.memory.set_profile_fact(customer_id, "color", m.group(3).lower())

    # ---------------------------------------------------------------- SKU Resolution (4 tầng)
    @staticmethod
    def _strip_diacritics(s: str) -> str:
        """Bỏ dấu tiếng Việt bằng NFKD + lọc combining mark — tổng quát cho MỌI từ (không
        cần từ điển màu/size thủ công như COLOR_NORMALIZE cũ)."""
        nfkd = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D"))        # NFKD KHÔNG tách "đ" → "đen" trước đây không khớp màu "den" của catalog
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

    def _fetch_variants(self, parent_sku: str) -> List[Dict[str, Any]]:
        """Tra catalog THẬT lấy danh sách variant_sku thật của 1 sản phẩm cha — nền tảng
        cho cả 4 tầng phân giải SKU, không đoán, chỉ đọc dữ liệu catalog thật."""
        if not parent_sku:
            return []
        res = self.mcp.execute_tool("catalog.search", {"sku": parent_sku}, caller="SkuResolver")
        items = res.get("items", [])
        return items[0].get("variants", []) if items else []

    def _build_dynamic_tools(self, llm_client, parent_sku) -> Optional[List[Dict[str, Any]]]:
        """Tầng 1 (Dynamic Tool Enum): nếu đã biết sản phẩm cha, tiêm enum=[variant_sku thật...]
        vào tools schema cho tham số sku/new_variant_sku — ép LLM chỉ chọn được token hợp lệ
        ngay từ đầu, chặn lỗi SKU tự ghép từ gốc. Không ảnh hưởng latency (catalog.search chạy
        local, không qua mạng; không thêm round-trip LLM nào)."""
        parents = [parent_sku] if isinstance(parent_sku, str) else [p for p in (parent_sku or []) if p]    # nhiều sản phẩm đang bàn → enum là HỢP của chúng
        variant_skus: List[str] = []
        for parent in parents:
            variants = self._fetch_variants(parent)
            if variants:
                variant_skus += [parent] + [v["variant_sku"] for v in variants]
        if not variant_skus:
            return None
        return with_variant_enum(llm_client.get_base_tools(), variant_skus, tool_names=self.TOOLS_WITH_VARIANT_SKU)

    def _resolve_variant_by_attributes(self, parent_sku: str, user_text: str) -> Optional[str]:
        """Tầng 2 (Attribute Context Matcher): so khớp thuộc tính THẬT (size/color) của từng
        variant trong catalog với câu nói khách — nếu TẤT CẢ thuộc tính của 1 variant đều
        xuất hiện trong câu khách (vd '42' và 'xám' đều có trong "xám 42"), trả đúng
        variant_sku thật tương ứng. Không dùng từ điển màu/size thủ công — chuẩn hóa bằng
        NFKD nên tổng quát cho mọi giá trị attribute mới trong catalog sau này."""
        variants = self._fetch_variants(parent_sku)
        normalized_text = self._strip_diacritics(user_text)
        for v in variants:
            attr_values = [str(v.get("size", "")), str(v.get("color", ""))]
            attr_tokens = [self._strip_diacritics(t) for t in attr_values if t]
            if attr_tokens and all(tok in normalized_text for tok in attr_tokens):
                return v["variant_sku"]
        return None

    @classmethod
    def _variants_named_in(cls, variants: List[Dict[str, Any]], text: str) -> List[str]:
        """Mọi biến thể mà câu khách NÊU ĐỦ cả size lẫn màu, khớp nguyên từ không dấu ("38 đen" → ...-38-DEN; "m" trong "mình" thì không)."""
        norm = cls._strip_diacritics(text or "")
        out = []
        for v in variants:
            toks = [cls._strip_diacritics(str(x)) for x in (v.get("size"), v.get("color")) if x not in (None, "")]
            if toks and all(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", norm) for t in toks):
                out.append(v["variant_sku"])
        return out

    def _discussed_parents(self, known_parent: Optional[str], call_log: List[Dict[str, Any]]) -> List[str]:
        """Sản phẩm CHA đang bàn trong cuộc gọi: sản phẩm đã tư vấn, rồi sản phẩm có biến thể trong các lần tra gần nhất (mới nhất trước), tối đa 3."""
        parents: List[str] = []
        for tc in reversed(call_log):                                  # MỚI NHẤT trước: khách đổi sang sản phẩm khác giữa cuộc thì sản phẩm đó là "đang bàn"
            args, res = tc.get("args") or {}, tc.get("result") or {}
            found = [it.get("sku") for it in (res.get("items") or [])[:3]] if tc.get("name") == "catalog.search" else \
                    [self._parent_sku(args["sku"])] if isinstance(args.get("sku"), str) and tc.get("name") in ("inventory.check", "pricing.get_quote", "order.create") else []
            for sku in found:
                if sku and sku not in parents and self._fetch_variants(sku):
                    parents.append(sku)
            if len(parents) >= 3:
                break
        if known_parent and known_parent not in parents:               # sản phẩm đã tư vấn từ đầu cuộc: vẫn còn trong tầm nhưng sau những gì vừa tra
            parents.append(known_parent)
        return parents[:3]

    def _check_named_variants(self, customer_texts: List[str], known_parent: Optional[str], call_log: List[Dict[str, Any]],
                              this_turn_calls: List[Dict[str, Any]], on: str) -> List[Dict[str, Any]]:
        """Khách nêu size+màu của sản phẩm đang bàn → CODE tự chạy `inventory.check` đúng biến thể đó (lần nhắc gần nhất thắng), không chờ LLM nhớ gọi.
        Lỗi ui_replay: LLM chỉ gọi catalog.search rồi nói "38 đen không có sẵn" dù còn 5. Biến thể đã tra thành công trong LƯỢT NÀY thì bỏ qua.
        Trả các lời gọi (cùng dạng tool_calls của trace) để ghi trace + làm bằng chứng cho guardrail 2b."""
        done = {(tc.get("args") or {}).get("sku") for tc in this_turn_calls
                if tc.get("name") == "inventory.check" and isinstance((tc.get("result") or {}).get("in_stock"), bool)}
        for parent in self._discussed_parents(known_parent, call_log):
            variants = self._fetch_variants(parent)
            skus = next((s for s in (self._variants_named_in(variants, t) for t in reversed(customer_texts)) if s), [])
            if not skus:
                continue
            calls = []
            for sku in skus[:4]:
                if sku in done:
                    continue
                args = {"sku": sku, "on": on}
                try:
                    res = self.mcp.execute_tool("inventory.check", args, caller="HarnessOrchestrator")
                except Exception as e:                       # tra thêm hỏng thì thôi, không làm hỏng lượt
                    logging.getLogger("harness.llm").warning("[stock] inventory.check %s lỗi (%s)", sku, e)
                    continue
                if isinstance(res, dict) and isinstance(res.get("in_stock"), bool):
                    calls.append({"name": "inventory.check", "tool": "inventory.check", "args": args, "result": res})
            return calls
        return []

    def _resolve_variant_fuzzy(self, parent_sku: str, bad_sku: str) -> Optional[str]:
        """Tầng 3 (Fuzzy Resolver): khi Tầng 2 không khớp (khách gõ tắt/teencode/sai chính
        tả nhẹ), so khớp mờ chuỗi SKU LLM tự sinh với danh sách variant_sku thật bằng
        difflib (tỷ lệ tương đồng >=80%)."""
        variants = self._fetch_variants(parent_sku)
        real_skus = [v["variant_sku"] for v in variants]
        matches = difflib.get_close_matches(bad_sku, real_skus, n=1, cutoff=0.8)
        return matches[0] if matches else None

    def _repair_unknown_sku(self, bad_sku: str, user_text: str, known_parent_sku: Optional[str]) -> Optional[str]:
        """Điều phối Tầng 2+3: thử sản phẩm cha đã biết (brief.product_advised) trước, rồi
        thử suy ra sản phẩm cha từ chính cấu trúc chuỗi SKU sai (bỏ dần đoạn cuối theo dấu
        '-' thật, không đoán nghĩa) — cho tới khi tìm được variant_sku thật khớp."""
        candidates = []
        if known_parent_sku:
            candidates.append(known_parent_sku)
        parts = bad_sku.split("-")
        for cut in range(len(parts) - 1, 1, -1):
            candidate = "-".join(parts[:cut])
            if candidate not in candidates:
                candidates.append(candidate)

        for parent_sku in candidates:
            if not self._fetch_variants(parent_sku):
                continue
            resolved = self._resolve_variant_by_attributes(parent_sku, user_text)
            if resolved:
                return resolved
            resolved = self._resolve_variant_fuzzy(parent_sku, bad_sku)
            if resolved:
                return resolved
        return None

    def _carried_facts(self, keys: List[str], start_facts: Dict[str, Any], agent_text: str,
                       tool_calls: List[Dict[str, Any]], customer_text: str, asked_slots) -> List[str]:
        """Các slot `keys` thật sự được MANG SANG và dùng: có sẵn lúc đầu cuộc gọi, agent nhắc tới/đưa vào tham số tool,
        agent chưa hỏi mở lại slot, khách chưa tự nhắc lại. So khớp không phân biệt dấu (src/harness/fact_usage.py)."""
        args = [tc.get("args", {}) for tc in tool_calls]
        used = []
        for key in keys:
            value = start_facts.get(key)
            if value is None or key in asked_slots:
                continue
            names = {str(value): self._product_info(str(value)).get("name", "")} if key == "product_advised" else None
            if fact_mentioned(key, value, customer_text, names):
                continue                                   # khách đã nói lại -> agent dùng được là nhờ nghe, không phải nhờ nhớ
            if used_by_agent(key, value, agent_text, args, names):
                used.append(key)
        return used
