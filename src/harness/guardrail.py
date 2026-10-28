"""
Guardrail & Fallback Module:
Kiểm duyệt đầu ra, chặn bịa giá / phí / khuyến mãi, chặn lộ giá vốn, chặn tự nhận là người thật, bảo vệ PII,
quản lý Fallback và Handoff. Nhận proposal từ Orchestrator VÀ kết quả của các module chuyên biệt trong tiến trình.

Quy tắc đối chiếu (bước 6): số tiền trong lời agent phải xuất hiện trong kết quả tool của CUỘC GỌI này
(hoặc là tổng/hiệu/bội số lượng của chúng, hoặc số khách/Call Brief đã nêu). Không kiểm tra bằng cách đoán ý khách.
"""
import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from src.harness.money import extract_amounts, numbers_in, derived_numbers

AI_DISCLOSURE_TEXT = ("Dạ em là trợ lý AI của shop, em hỗ trợ mình tra cứu và lên đơn ạ. "
                      "Nếu mình muốn gặp nhân viên, em sẽ chuyển máy ngay ạ.")


@dataclass
class GuardrailDecision:
    approved: bool
    sanitized_text: str
    action_type: str = "speak"  # speak | execute_tool | handoff
    violation_type: Optional[str] = None
    handoff_payload: Optional[Dict[str, Any]] = None


class GuardrailAndFallback:
    REQUIRED_HANDOFF_FIELDS = [
        "customer_phone", "customer_name", "escalation_reason",
        "conversation_summary", "product_advised", "price_quoted_vnd",
        "open_questions", "next_action", "generated_at"
    ]

    # Cụm xác nhận-đã-hành-động — kiểm tra TÍNH NHẤT QUÁN giữa lời agent và tool đã thực sự gọi.
    # KHÔNG gồm "mã đơn": câu hỏi/nhắc "mã đơn" (xin mã đơn, mã đơn OD...) không phải khẳng định đã lên đơn (N1).
    ORDER_CLAIM_PHRASES = ["đã lên đơn", "đã tạo đơn", "lên đơn thành công", "đã đặt đơn", "đã chốt đơn"]
    EXCHANGE_CLAIM_PHRASES = ["đã đổi size", "đã đổi màu", "đã đổi sản phẩm", "đã làm thủ tục đổi"]

    # Giá vốn / giá sàn: chặn khi đi kèm con số; từ chối khéo không có số ("giá nhập là thông tin em không chia sẻ") thì cho qua.
    COST_TERMS = ["giá vốn", "giá nhập", "giá sàn", "giá gốc nhập", "biên lợi nhuận", "chiết khấu nhà cung cấp"]
    HUMAN_CLAIMS = re.compile(
        r"(?:em|mình|tôi)\s+(?:là|la)\s+(?:một\s+)?(?:nhân viên|người)\s+(?:thật|thực)|"
        r"nhân viên\s+thật|người\s+thật|không\s+phải\s+(?:là\s+)?(?:ai\b|AI\b|robot|máy|bot)", re.I)
    FREE_CLAIMS = re.compile(r"không\s+(?:mất|tốn|tính|phát sinh)\s+(?:thêm\s+)?(?:phí|tiền|đồng)|miễn phí\s+(?:đổi|hoàn|trả)|free", re.I)

    # Lời báo HẾT HÀNG (không gồm "hết hạn"/"hết khuyến mãi"); phủ định ("chưa hết hàng", "không hết hàng") không tính.
    STOCK_OUT = re.compile(r"(?<![\w])(?:đã\s+|hiện\s+|tạm\s+)?(?:hết\s+(?:hàng|size|màu|mẫu)|hết\s+rồi|không\s+còn\s+(?:hàng|size|màu|mẫu)|không\s+có\s+sẵn)(?![\w])", re.I)
    STOCK_NEG = re.compile(r"(?:chưa|không|chẳng|đâu)\s+(?:bị\s+|có\s+)?(?:hết\s+(?:hàng|size|màu|mẫu))", re.I)
    COLOR_VI = {"DEN": "đen", "TRANG": "trắng", "XAM": "xám", "NAVY": "xanh navy", "BE": "be"}

    # --- helpers ---
    @staticmethod
    def _stock_evidence(tool_calls: List[Dict[str, Any]]) -> Dict[str, bool]:
        """sku → còn hàng? theo kết quả `inventory.check` MỚI NHẤT của từng biến thể trong cuộc gọi."""
        out: Dict[str, bool] = {}
        for tc in tool_calls:
            r = tc.get("result") or {}
            if tc.get("name") == "inventory.check" and isinstance(r, dict) and r.get("sku") and isinstance(r.get("in_stock"), bool):
                out[r["sku"]] = r["in_stock"]
        return out

    def _in_stock_sentence(self, sku: str) -> str:
        from src.agents.specialists import catalog_product, product_name
        parent = catalog_product(sku).get("sku") or ""
        tail = sku[len(parent) + 1:] if parent and sku.startswith(parent + "-") else ""
        bits = tail.split("-") if tail else []
        variant = ""
        if len(bits) == 2:
            variant = f" size {bits[0]} màu {self.COLOR_VI.get(bits[1].upper(), bits[1].lower())}"
        elif bits:
            variant = " " + " ".join(self.COLOR_VI.get(b.upper(), b) for b in bits)
        return f"Dạ em kiểm tra kho thì {product_name(sku)}{variant} hiện còn hàng ạ."

    def _fix_stock_claims(self, text: str, tool_calls: List[Dict[str, Any]]) -> Optional[str]:
        """Lời agent báo HẾT HÀNG trong khi MỌI kết quả `inventory.check` của cuộc gọi (đúng một biến thể) đều ghi còn hàng → thay câu sai bằng câu đúng với tool.
        Có biến thể nào hết hàng, hoặc không có bằng chứng tồn kho → không can thiệp (agent có thể đang nói về biến thể khác, hoặc chưa tra)."""
        from src.agents.specialists import catalog_product
        # Chỉ biến thể CỤ THỂ mới là bằng chứng: tồn kho của SKU cha ("còn hàng") không nói gì về size/màu khách hỏi (lỗi thật ở ui_replay 2026-10-27).
        ev = {k: v for k, v in self._stock_evidence(tool_calls).items() if catalog_product(k).get("sku") not in (None, k)}
        if not ev:
            return None
        wants = {}
        for sku in ev:
            bits = [b.upper() for b in sku[len(catalog_product(sku)["sku"]) + 1:].split("-")]
            wants[sku] = {str(b).lower() for b in bits} | {self.COLOR_VI.get(b, b).lower() for b in bits}
        sentences = re.split(r"(?<=[.!?…])\s+", text)

        def candidates(sent: str) -> List[str]:
            """Biến thể đã tra mà câu có thể đang nói tới: size/màu câu nhắc phải nằm trong biến thể đó (câu nhắc size/màu KHÁC thì không phải câu về nó)."""
            low = sent.lower()
            sizes = set(re.findall(r"size\s*(\w+)", low))
            colors = {c.lower() for c in self.COLOR_VI.values() if re.search(rf"(?<!\w){re.escape(c.lower())}(?!\w)", low)}
            return [sku for sku, want in wants.items() if sizes <= want and colors <= want]

        # Câu báo hết hàng bị thay CHỈ khi mọi biến thể nó có thể nói tới đều còn hàng (có biến thể hết hàng/không rõ → không can thiệp).
        fix: Dict[int, str] = {}
        for i, s in enumerate(sentences):
            if self.STOCK_OUT.search(s) and not self.STOCK_NEG.search(s):
                c = candidates(s)
                if c and all(ev[k] for k in c):
                    fix[i] = c[0]
        if not fix:
            return None
        out, seen = [], set()
        for i, s in enumerate(sentences):
            if i not in fix:
                out.append(s)
            elif fix[i] not in seen:                  # nhiều câu sai cùng một biến thể → chỉ giữ MỘT câu đúng
                seen.add(fix[i])
                out.append(self._in_stock_sentence(fix[i]))
        return " ".join(out)

    @staticmethod
    def _names(tool_calls: List[Dict[str, Any]]) -> Set[str]:
        return {tc.get("name") for tc in tool_calls if tc.get("name")}

    def _allowed_numbers(self, tool_calls: List[Dict[str, Any]], context: Dict[str, Any],
                         specialist_results: Dict[str, Any]) -> Set[int]:
        known: Set[int] = set()
        for tc in tool_calls:
            known |= numbers_in(tc.get("result"))
        known |= {int(v) for v in (context.get("known_numbers") or []) if isinstance(v, (int, float))}
        known |= numbers_in(specialist_results)
        if context.get("verified_price"):
            known.add(int(context["verified_price"]))
        qtys = {2, 3}
        for tc in tool_calls:
            q = (tc.get("args") or {}).get("qty")
            if isinstance(q, int) and q > 0:
                qtys.add(q)
        return derived_numbers(known, frozenset(qtys))

    @staticmethod
    def _amount_ok(value: int, approx: bool, allowed: Set[int]) -> bool:
        if value in allowed:
            return True
        if approx:
            return any(abs(value - a) <= 0.06 * a for a in allowed if a)
        return False

    def check(self, proposal: Dict[str, Any], specialist_results: Dict[str, Any], context: Dict[str, Any]) -> GuardrailDecision:
        text = proposal.get("proposed_text", "")
        text_lower = text.lower()
        verified_price = context.get("verified_price")
        quoted_price = proposal.get("quoted_price")
        tool_calls = context.get("tool_calls", []) or []
        # Tool đã chạy ở các lượt trước TRONG CÙNG CUỘC GỌI cũng tính (không thay câu khi tool đã chạy).
        call_tool_calls = context.get("call_tool_calls") or tool_calls
        called_tool_names = self._names(tool_calls) | self._names(call_tool_calls) | set(context.get("call_tool_names") or [])

        # 1. Chặn Price & Promotion Hallucination (nhánh rule-based: so với giá đã tra)
        if quoted_price is not None and verified_price is not None:
            if quoted_price != verified_price:
                return GuardrailDecision(
                    approved=False,
                    sanitized_text="Dạ em xin phép kiểm tra lại bảng giá hệ thống để báo chính xác cho mình ạ.",
                    action_type="speak",
                    violation_type="hallucination_price_mismatch"
                )

        # 1b. Mọi số tiền trong lời agent phải có căn cứ từ tool/Call Brief/khách nêu (nhánh LLM)
        amounts = extract_amounts(text)
        if amounts:
            allowed = self._allowed_numbers(call_tool_calls, context, specialist_results)
            bad = [v for v, approx in amounts if not self._amount_ok(v, approx, allowed)]
            if bad:
                return GuardrailDecision(
                    approved=False,
                    sanitized_text="Dạ em xin phép kiểm tra lại bảng giá hệ thống để báo chính xác cho mình ạ.",
                    action_type="speak",
                    violation_type="hallucination_price_mismatch"
                )

        # 1c. "Không mất phí" trong khi tool báo có phí phát sinh
        if self.FREE_CLAIMS.search(text):
            fees = [(tc.get("result") or {}) for tc in call_tool_calls if tc.get("name") == "order.update"]
            charged = [r for r in fees if (r.get("fee_vnd") or 0) > 0 or (r.get("extra_payment_vnd") or 0) > 0]
            if charged:
                r = charged[-1]
                parts = []
                if r.get("fee_vnd"):
                    parts.append(f"phí đổi {int(r['fee_vnd']):,}đ".replace(",", "."))
                if r.get("extra_payment_vnd"):
                    parts.append(f"phụ thu chênh lệch {int(r['extra_payment_vnd']):,}đ".replace(",", "."))
                return GuardrailDecision(
                    approved=False,
                    sanitized_text=f"Dạ em xin phép đính chính: lần đổi này có {' và '.join(parts)} ạ.",
                    action_type="speak",
                    violation_type="hallucination_fee_mismatch"
                )

        # 2. Chặn agent tự nói "đã lên đơn"/"đã đổi size" mà KHÔNG thực sự gọi tool tương ứng
        # (tính cả tool đã chạy ở lượt trước trong cuộc gọi).
        if any(p in text_lower for p in self.ORDER_CLAIM_PHRASES) and "order.create" not in called_tool_names:
            return GuardrailDecision(
                approved=False,
                sanitized_text="Dạ em xin phép thao tác hệ thống để lên đơn cho mình ngay ạ, đợi em một chút nhé.",
                action_type="speak",
                violation_type="claims_action_without_tool_call"
            )
        if any(p in text_lower for p in self.EXCHANGE_CLAIM_PHRASES) and "order.update" not in called_tool_names:
            return GuardrailDecision(
                approved=False,
                sanitized_text="Dạ em xin phép thao tác hệ thống để cập nhật đổi size/màu cho mình ngay ạ, đợi em một chút nhé.",
                action_type="speak",
                violation_type="claims_action_without_tool_call"
            )

        # 2b. Lời báo "hết hàng" mâu thuẫn với kết quả tồn kho trong cuộc gọi (lỗi UI đã gặp: agent nói 38 đen "không có sẵn" dù tool ghi còn hàng)
        stock_fixed = self._fix_stock_claims(text, call_tool_calls)
        if stock_fixed is not None:
            text, text_lower = stock_fixed, stock_fixed.lower()

        # 3. Chặn tiết lộ giá vốn/giá sàn (chỉ khi kèm con số; lời từ chối không bị chặn)
        if any(term in text_lower for term in self.COST_TERMS) and re.search(r"\d", text):
            return GuardrailDecision(
                approved=False,
                sanitized_text="Dạ thông tin này thuộc quy chuẩn bảo mật nội bộ của shop, em xin phép tư vấn giá niêm yết ưu đãi cho mình ạ.",
                action_type="speak",
                violation_type="restricted_info_leak"
            )

        # 4. Chặn tự nhận là người thật
        if self.HUMAN_CLAIMS.search(text):
            return GuardrailDecision(
                approved=False,
                sanitized_text=AI_DISCLOSURE_TEXT,
                action_type="speak",
                violation_type="claims_human"
            )

        # 5. Mask PII trong lời thoại: CCCD (12 số) và số tài khoản (9–14 số); SĐT 10 số bắt đầu bằng 0 được phép.
        sanitized = re.sub(r'(?<!\d)\d{12}(?!\d)', '[CCCD ĐÃ BẢO MẬT]', text)
        sanitized = re.sub(
            r'(?<!\d)(?!0\d{9}(?!\d))\d{9,14}(?!\d)',
            lambda m: m.group()[:2] + "****" + m.group()[-2:], sanitized)

        # 6. Kiểm tra Handoff Transfer Brief (nếu là trường hợp chuyển máy người thật)
        if proposal.get("action_type") == "handoff":
            brief = proposal.get("handoff_brief", {})
            missing = [f for f in self.REQUIRED_HANDOFF_FIELDS if f not in brief]
            if missing:
                return GuardrailDecision(
                    approved=False,
                    sanitized_text="Dạ em xin phép giữ máy trong giây lát để hoàn tất hồ sơ bàn giao cho chuyên viên hỗ trợ mình ạ.",
                    action_type="speak",
                    violation_type=f"incomplete_handoff_brief_missing_{missing[0]}"
                )
            return GuardrailDecision(
                approved=True,
                sanitized_text="Dạ em đã chuyển thông tin tư vấn sang cho quản lý ca trực để hỗ trợ tiếp tục cho mình ngay đây ạ.",
                action_type="handoff",
                handoff_payload=brief
            )

        return GuardrailDecision(
            approved=stock_fixed is None,
            sanitized_text=sanitized,
            action_type=proposal.get("action_type", "speak"),
            violation_type="stock_claim_mismatch" if stock_fixed is not None else None
        )
