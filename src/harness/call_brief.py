"""
Call Brief Builder: Dựng bản tóm tắt trước khi agent bắt máy.
Nhiệm vụ:
- Tổng hợp thông tin từ Profile và Episodic memory
- Kiểm tra tính hợp lệ của khuyến mãi, blocker tồn đọng, cảnh báo hết hạn (stale warnings)
- Thiết lập must_not_ask (những slot cấm hỏi lại bằng câu hỏi mở)
- Tạo câu mở đầu bằng 'Xác nhận tiếp nối'
"""
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from src.identity.resolver import ResolvedIdentity
from src.identity.identity_map import hash_contact
from src.memory.service import MemoryService


@dataclass
class CallBrief:
    customer_id: str
    customer_name: str
    honorific: str
    phone: str
    previous_calls_count: int
    last_call_date: Optional[str]
    product_advised: Optional[str]
    price_quoted_vnd: Optional[int]
    promo_code: Optional[str]
    promo_expiry: Optional[str]
    promo_active: bool
    blocker: Optional[str]
    must_not_ask: List[str]
    must_carry_over: List[str]
    suggested_opening: str
    stale_warnings: List[str] = field(default_factory=list)
    profile_facts: Dict[str, Any] = field(default_factory=dict)
    channels_seen: List[str] = field(default_factory=list)   # lịch sử kênh khách đã liên hệ (fanpage, hotline, zalo...)
    facts_by_channel: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # khách đã nói/được báo gì ở TỪNG kênh (provenance)
    precomputed: Optional[Dict[str, Any]] = None             # bước 13: giá/tồn kho/KM/bảo hành CODE đã tra THẬT lúc nhận diện khách (xem CallBriefBuilder.precompute)
    crm_known: bool = False                                  # SĐT khớp một hồ sơ CRM có tên/đơn → đã biết là ai dù chưa có episode (khác "tên vừa nghe trong cuộc")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def addressing(self) -> str:
        """Cách gọi khách: 'chị Hoa' khi biết cả hai; chỉ xưng hô khi chưa biết tên; 'anh/chị' khi chưa biết gì."""
        known_name = self.customer_name and self.customer_name != "Quý khách"
        return f"{self.honorific} {self.customer_name}" if known_name else self.honorific


class CallBriefBuilder:
    def __init__(self, memory: MemoryService, tool_gateway=None):
        self.memory = memory
        # tool_gateway: dành cho bước 13 (kiểm tra lại giá/tồn kho/KM lúc nhận diện khách).
        self.tool_gateway = tool_gateway
        self._pre_cache: Dict[tuple, Optional[Dict[str, Any]]] = {}      # (customer_id, ngày cuộc gọi) -> kết quả tra sẵn: MỘT lần/cuộc, không tra lại mỗi lượt

    def build(self, identity: ResolvedIdentity, current_call_date: str = "2026-10-17") -> CallBrief:
        # Trường hợp mơ hồ danh tính
        if identity.is_ambiguous:
            return CallBrief(
                # Mã riêng theo SĐT (không dùng chung 'AMBIGUOUS'): bộ nhớ của người này không lẫn với người khác
                # trong lúc chưa xác minh danh tính, và không lộ SĐT thô trong mã.
                customer_id="AMB-" + hash_contact(identity.phone or "UNKNOWN")[5:],
                customer_name="Quý khách",
                honorific="anh/chị",
                phone=identity.phone,
                previous_calls_count=0,
                last_call_date=None,
                product_advised=None,
                price_quoted_vnd=None,
                promo_code=None,
                promo_expiry=None,
                promo_active=False,
                blocker="ambiguous_identity",
                must_not_ask=[],
                must_carry_over=[],
                suggested_opening="Dạ em chào anh/chị, số máy mình đang có hai thành viên cùng đăng ký, cho em xin phép xác nhận tên mình để hỗ trợ đúng thông tin ạ?",
                stale_warnings=["SĐT có nhiều người dùng chung, cấm nạp thông tin nhạy cảm trước khi xác minh danh tính!"]
            )

        cid = identity.customer_id
        # MỘT khách một mã (D2): đọc theo customer_id, không còn đọc gộp theo SĐT thô. TTL áp theo ngày cuộc gọi (A5).
        # Episode của CHÍNH cuộc gọi đang diễn ra (chốt giữa chừng khi chuyển máy) không phải "cuộc gọi trước": nếu đếm, lượt sau chào như khách gọi lại.
        episodes = [e for e in self.memory.get_episodes(cid) if e.session_id != f"SESS-{cid}-{current_call_date}"]
        profile = dict(self.memory.get_profile_facts(cid, on_date=current_call_date)) if cid else {}
        stale_warnings = []

        # Kiểm tra order_id còn tồn tại trên hệ đơn hàng trước khi dùng (D4): mã đơn lưu bền nhưng hệ đơn có thể đã
        # khởi động lại -> mã trỏ tới đơn không tồn tại hoặc đơn của người khác.
        if self.tool_gateway is not None and profile.get("order_id"):
            res = self.tool_gateway.execute_tool("order.status", {"order_id": profile["order_id"]}, caller="CallBriefBuilder")
            if not res.get("orders"):
                stale_warnings.append(f"Đơn {profile.pop('order_id')} không còn tồn tại trên hệ thống đơn hàng — không dùng mã này.")

        last_ep = episodes[-1] if episodes else None

        # Tên/xưng hô: bộ nhớ -> CRM -> mặc định trung tính. KHÔNG mặc định 'Hoa'/'chị' (A3, A11).
        crm = identity.customer_profile or {}
        name = profile.get("customer_name") or crm.get("name") or "Quý khách"
        honorific = profile.get("honorific") or crm.get("honorific") or "anh/chị"
        if honorific == "em":                  # khách tự xưng "em": nhân viên (xưng "em") gọi khách là "bạn", không gọi "em" trùng ngôi
            honorific = "bạn"
        channels_seen = list(profile.get("channels_seen") or [])
        addr = f"{honorific} {name}" if name != "Quý khách" else honorific
        Hon = honorific[:1].upper() + honorific[1:]
        prod = profile.get("product_advised") or (last_ep.product_advised if last_ep else None)
        price = profile.get("price_quoted_vnd") or (last_ep.price_quoted_vnd if last_ep else None)
        promo = profile.get("promo_code") or (last_ep.promo_code if last_ep else None)
        promo_exp = profile.get("promo_expiry") or (last_ep.promo_expiry if last_ep else None)
        blocker = profile.get("blocker") or (last_ep.blocker if last_ep else None)

        # Kiểm tra khuyến mãi còn hạn hay không
        promo_active = True
        if promo_exp and promo_exp < current_call_date:
            promo_active = False
            stale_warnings.append(f"Khuyến mãi {promo} đã hết hạn vào ngày {promo_exp}")

        # Danh sách Must Not Ask (Slot cấm hỏi mở lại)
        must_not_ask = []
        if "room_area_m2" in profile: must_not_ask.append("room_area_m2")
        if "has_children" in profile: must_not_ask.append("has_children")
        if "budget_vnd" in profile: must_not_ask.append("budget_vnd")
        if prod: must_not_ask.append("product_advised")

        # Must carry over sang phiên sau
        must_carry_over = []
        if prod: must_carry_over.append("product_advised")
        if price: must_carry_over.append("price_quoted_vnd")
        if "room_area_m2" in profile: must_carry_over.append("room_area_m2")
        if blocker: must_carry_over.append("blocker")
        # Thông tin đơn/biến thể đã chốt cũng phải được mang sang (kịch bản đổi size/hỏi vận đơn): trước đây thiếu nên
        # `facts_used` không bao giờ ghi nhận agent đã dùng order_id/size/màu (CCR thấp giả ở SAMPLE-03).
        for extra_key in ("order_id", "variant_sku", "size", "color", "promo_code", "competitor_price_vnd", "objection",
                          "has_children", "budget_vnd"):
            if profile.get(extra_key) is not None:
                must_carry_over.append(extra_key)

        # Bước 13: tra sẵn giá/tồn kho/KM/bảo hành bằng tool lúc nhận diện khách quay lại (MỘT lần/cuộc), để LLM khỏi tra lại và câu chào có số liệu hôm nay
        pre = self.precompute(cid, prod, profile, identity.phone, current_call_date) if (last_ep and prod) else None

        # Sinh câu mở đầu Xác Nhận Tiếp Nối (Continuity Opening)
        opening = ""
        if last_ep and prod:
            prod_name = self._product_name(prod)
            price_display = f"{price:,}đ".replace(",", ".") if price else ""
            area = profile.get("room_area_m2")
            area_display = f"cho phòng {area:g}m²" if isinstance(area, (int, float)) else ""
            when = self._short_date(last_ep.call_date)
            
            if blocker == "can hoi chong":
                follow = f"{Hon} đã trao đổi lại với gia đình chưa ạ, hay còn băn khoăn điểm nào để em hỗ trợ thêm?"
            else:
                follow = f"{Hon} đã trao đổi với người nhà chưa ạ, bên em hỗ trợ lên đơn cho mình luôn nhé?"

            # PB-01: nhắc TỐI ĐA 2 thông tin cũ — sản phẩm + (giá hoặc diện tích); giá thì ưu tiên giá đã tra lại hôm nay (câu gộp bên dưới)
            parts = [f"Dạ em chào {addr}, {when} bên em có tư vấn {prod_name}"]
            if pre:
                today = self._today_sentence(pre)
            else:
                today = ""
                parts.append(f"giá ưu đãi {price_display}" if price_display else area_display)
            opening = " ".join(x for x in parts if x) + "." + (f" {today}" if today else "") + f" {follow}"
        else:
            opening = f"Dạ em chào {honorific}, em có thể hỗ trợ tư vấn sản phẩm nào cho mình hôm nay ạ?"

        return CallBrief(
            customer_id=cid,
            customer_name=name,
            honorific=honorific,
            phone=identity.phone,
            previous_calls_count=len(episodes),
            last_call_date=last_ep.call_date if last_ep else None,
            product_advised=prod,
            price_quoted_vnd=price,
            promo_code=promo,
            promo_expiry=promo_exp,
            promo_active=promo_active,
            blocker=blocker,
            must_not_ask=must_not_ask,
            must_carry_over=must_carry_over,
            suggested_opening=opening,
            stale_warnings=stale_warnings,
            profile_facts=profile,
            channels_seen=channels_seen,
            facts_by_channel=self._facts_by_channel(cid, current_call_date),
            crm_known=bool(crm.get("found") and (crm.get("name") or crm.get("orders"))),
            precomputed=pre
        )

    def precompute(self, cid: str, prod: str, profile: Dict[str, Any], phone: Optional[str], on: str) -> Optional[Dict[str, Any]]:
        """Tra sẵn bằng CODE (không LLM): thông tin sản phẩm/bảo hành, tồn kho, giá cuối + KM của đúng biến thể đã tư vấn (hoặc sản phẩm cha) tại ngày cuộc gọi.
        Một lần cho mỗi (khách, ngày). Trả None nếu không có cổng tool hoặc không tra được gì. `calls` cùng dạng tool_calls của trace (SĐT thay bằng token) để orchestrator ghi
        vào trace lượt đầu và làm bằng chứng cho guardrail; thời gian tra tính vào `call_brief_latency_ms` vì nằm trong `build()`."""
        key = (cid, on)
        if key in self._pre_cache:
            return self._pre_cache[key]
        out = None
        if self.tool_gateway is not None and prod:
            t0 = time.perf_counter()
            sku = profile.get("variant_sku") or prod
            plan = [("catalog.search", {"sku": prod}), ("inventory.check", {"sku": sku, "on": on}),
                    ("pricing.get_quote", {"sku": sku, "on": on, **({"customer_phone": phone} if phone and phone != "UNKNOWN" else {})})]
            calls, res = [], {}
            try:
                for name, args in plan:
                    r = self.tool_gateway.execute_tool(name, args, caller="CallBriefBuilder")
                    r = {k: v for k, v in r.items() if not str(k).startswith("_")}
                    res[name] = r
                    shown = {**args, "customer_phone": "CURRENT_CUSTOMER"} if "customer_phone" in args else args
                    calls.append({"name": name, "tool": name, "args": shown, "result": r})
            except Exception:
                res = {}
            item = ((res.get("catalog.search") or {}).get("items") or [{}])[0]
            stock, quote = res.get("inventory.check") or {}, res.get("pricing.get_quote") or {}
            if isinstance(stock.get("in_stock"), bool) or "final_price_vnd" in quote:
                out = {"sku": sku, "name": item.get("name") or "", "checked_on": on, "calls": calls,
                       "warranty_months": (item.get("attributes") or {}).get("warranty_months"),
                       "stock": {k: stock[k] for k in ("in_stock", "qty", "restock_expected") if k in stock} if isinstance(stock.get("in_stock"), bool) else None,
                       "price": {"list_price_vnd": quote.get("list_price_vnd"), "final_price_vnd": quote.get("final_price_vnd"),
                                 "promos": [self._promo_phrase(a) for a in quote.get("applied_promos") or [] if self._promo_phrase(a)],
                                 "freeship": bool(quote.get("freeship"))} if "final_price_vnd" in quote else None,
                       "latency_ms": int(round((time.perf_counter() - t0) * 1000))}
        self._pre_cache[key] = out
        return out

    @staticmethod
    def _promo_phrase(a: Dict[str, Any]) -> str:
        """Ưu đãi đã áp dụng → cụm nói với khách (không đọc mã khuyến mãi)."""
        t, d = a.get("type"), a.get("discount_vnd") or 0
        if t in ("fixed", "percent", "percent_second_item") and d:
            return f"giảm {d:,}đ".replace(",", ".")
        return {"gift": "tặng quà kèm", "freeship": "miễn phí vận chuyển"}.get(t, "")

    @staticmethod
    def _today_sentence(pre: Dict[str, Any]) -> str:
        """MỘT câu gộp dữ kiện đã tra hôm nay: tồn kho + giá cuối + ưu đãi + bảo hành (bước 13)."""
        bits = []
        st, pr = pre.get("stock"), pre.get("price")
        if st:
            bits.append("còn hàng" if st.get("in_stock") else "tạm hết hàng" + (f", dự kiến có lại ngày {st['restock_expected']}" if st.get("restock_expected") else ""))
        if pr and pr.get("final_price_vnd"):
            extra = list(pr.get("promos") or []) + (["miễn phí vận chuyển"] if pr.get("freeship") and "miễn phí vận chuyển" not in (pr.get("promos") or []) else [])
            bits.append(f"giá {pr['final_price_vnd']:,}đ".replace(",", ".") + (f" ({', '.join(extra)})" if extra else ""))
        if pre.get("warranty_months"):
            bits.append(f"bảo hành {pre['warranty_months']} tháng")
        return f"Em vừa kiểm tra hôm nay: {', '.join(bits)}." if bits else ""

    def _product_name(self, sku: str) -> str:
        """Tên sản phẩm đọc được cho câu chào (vd 'Máy lọc không khí AirPure Y'); không tra được thì dùng mã SKU rút gọn."""
        cache = self.__dict__.setdefault("_name_cache", {})
        if sku not in cache:
            name = ""
            if self.tool_gateway is not None:
                try:
                    res = self.tool_gateway.execute_tool("catalog.search", {"sku": sku}, caller="CallBriefBuilder")
                except Exception:                                  # cổng tool hỏng: câu chào dùng tên chung, không làm hỏng việc dựng brief
                    return "sản phẩm mình quan tâm"
                items = res.get("items") or []
                name = (items[0].get("name") if items else "") or ""
            cache[sku] = name or "sản phẩm mình quan tâm"          # không bao giờ đưa mã SKU vào câu chào
        return cache[sku]

    @staticmethod
    def _short_date(iso_date: str) -> str:
        """'2026-10-15' -> 'hôm 15/10' (đọc tự nhiên); không phân tích được thì 'hôm trước'."""
        try:
            y, m, d = iso_date.split("-")
            return f"hôm {int(d)}/{int(m)}"
        except (ValueError, AttributeError):
            return "hôm trước"

    BRIEF_CHANNEL_KEYS = ("product_advised", "price_quoted_vnd", "promo_code", "room_area_m2", "has_children",
                          "budget_vnd", "blocker", "order_id", "size", "color")

    def _facts_by_channel(self, cid: str, on_date: str) -> Dict[str, Dict[str, Any]]:
        """Dữ liệu khách theo từng nền tảng (nhờ provenance source_channel), chỉ các slot nghiệp vụ."""
        if not cid:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for channel, facts in self.memory.facts_by_channel(cid, on_date=on_date).items():
            keep = {k: v for k, v in facts.items() if k in self.BRIEF_CHANNEL_KEYS}
            if keep:
                out[channel] = keep
        return out
