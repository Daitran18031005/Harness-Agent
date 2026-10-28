"""
Identity Resolver: Nhận dạng khách hàng xuyên kênh (Hotline, Zalo, FB, Web)
Gọi crm.get_customer qua MCP Tool Gateway.

- Một khách một mã xuyên kênh (A3/N7): khách chat Fanpage rồi đọc SĐT -> nối FB id với hồ sơ theo SĐT
  (CRM hoặc mã ổn định theo SĐT), gộp bộ nhớ đã ghi trên mã tạm vào mã chính.
- SĐT dùng chung (A6): không dùng chung mã 'AMBIGUOUS'; khách nêu tên khớp 1 ứng viên thì xác định luôn.
- Mỗi lượt ghi nhận kênh khách đã dùng (`channels_seen`) để Call Brief biết lịch sử kênh.
"""
import re
import unicodedata
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from src.channels.normalizer import NormalizedTurn, InputChannel
from src.tools.mcp_gateway import MCPToolGateway
from src.identity.identity_map import IdentityLinkMap

PHONE_FULL = re.compile(r"^0\d{9}$")


@dataclass
class ResolvedIdentity:
    customer_id: Optional[str]
    is_ambiguous: bool
    phone: str
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    customer_profile: Optional[Dict[str, Any]] = None


def _fold(text: str) -> str:
    """Bỏ dấu + chữ thường để so khớp tên ('Loan' ~ 'loan', 'Hạnh' ~ 'hanh')."""
    nfkd = unicodedata.normalize("NFKD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


class IdentityResolver:
    def __init__(self, mcp_gateway: MCPToolGateway, identity_backend=None):
        self.mcp = mcp_gateway
        # [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE]
        # identity_backend = SQLiteStore dùng chung với MemoryService (hoặc None -> fallback
        # in-memory, hermetic theo process/scenario) — đảm bảo customer_id của khách MỚI
        # (chưa có trong CRM) ổn định xuyên phiên/lượt, không sinh UUID ngẫu nhiên mỗi lần.
        self.identity_map = IdentityLinkMap(backend=identity_backend)
        self._shared_choice: Dict[str, Dict[str, Any]] = {}   # SĐT dùng chung -> ứng viên đã xác minh tên
        self._contact_phone: Dict[str, str] = {}              # FB/Zalo id -> SĐT khách đã đọc ra
        self._delete_hooked = set()                           # các MemoryService đã đăng ký listener xóa khách

    # ------------------------------------------------------------------ tra CRM theo kênh
    @staticmethod
    def _lookup_keys(turn: NormalizedTurn) -> Dict[str, Optional[str]]:
        cid = turn.contact_id or ""
        if PHONE_FULL.match(cid) or turn.channel == InputChannel.HOTLINE:
            return {"phone": cid, "zalo_id": None, "fb_id": None}
        if turn.channel == InputChannel.ZALO:
            return {"phone": None, "zalo_id": cid, "fb_id": None}
        if turn.channel == InputChannel.FANPAGE:
            return {"phone": None, "zalo_id": None, "fb_id": cid}
        return {"phone": None, "zalo_id": None, "fb_id": None}

    def _crm(self, **keys) -> Dict[str, Any]:
        return self.mcp.execute_tool("crm.get_customer", {"phone": keys.get("phone"), "zalo_id": keys.get("zalo_id"),
                                                          "fb_id": keys.get("fb_id")}, caller="IdentityResolver")

    # ------------------------------------------------------------------ SĐT dùng chung
    def _resolve_shared(self, phone: str, crm_res: Dict[str, Any], turn: NormalizedTurn) -> ResolvedIdentity:
        candidates = crm_res.get("candidates", [])
        chosen = self._shared_choice.get(phone)
        if chosen is None:
            folded_text = f" {_fold(turn.normalized_text)} "
            matches = [c for c in candidates
                       if c.get("name") and re.search(rf"(?<![a-z]){re.escape(_fold(c['name']))}(?![a-z])", folded_text)]
            if len(matches) == 1:
                chosen = matches[0]
                self._shared_choice[phone] = chosen
        if chosen is not None:
            return ResolvedIdentity(customer_id=chosen["customer_id"], is_ambiguous=False, phone=phone,
                                    customer_profile={**chosen, "found": True, "phone": phone})
        return ResolvedIdentity(customer_id=None, is_ambiguous=True, phone=phone, candidates=candidates)

    # ------------------------------------------------------------------ nối kênh ↔ SĐT
    def _link_by_phone(self, turn: NormalizedTurn, anon_master: str, phone: str, memory) -> ResolvedIdentity:
        crm_res = self._crm(phone=phone)
        profile = None
        if crm_res.get("found") and not crm_res.get("ambiguous"):
            master, profile = crm_res["customer_id"], crm_res
        elif crm_res.get("found"):
            # SĐT dùng chung nhiều người: chưa đủ căn cứ để nối -> giữ mã tạm
            return ResolvedIdentity(customer_id=anon_master, is_ambiguous=False, phone="UNKNOWN")
        else:
            master = self.identity_map.resolve_master_id(phone)   # khách mới, mã ổn định theo SĐT
        self.identity_map.link_contact(turn.contact_id, master)
        self._contact_phone[turn.contact_id] = phone
        if memory is not None and anon_master != master:
            memory.merge_customer(anon_master, master)
        return ResolvedIdentity(customer_id=master, is_ambiguous=False, phone=phone, customer_profile=profile)

    # ------------------------------------------------------------------ ghi nhận kênh / xưng hô
    @staticmethod
    def _record_context(memory, identity: ResolvedIdentity, turn: NormalizedTurn) -> None:
        cid = identity.customer_id
        if memory is None or not cid or identity.is_ambiguous:
            return
        facts = memory.get_profile_facts(cid)
        seen = list(facts.get("channels_seen") or [])
        if turn.channel.value not in seen:
            memory.set_profile_fact(cid, "channels_seen", seen + [turn.channel.value])
        crm = identity.customer_profile or {}
        hon = turn.extracted_entities.get("self_honorific")
        if hon and not crm.get("honorific") and "honorific" not in facts:
            memory.set_profile_fact(cid, "honorific", hon)    # xưng hô lấy từ chính lời khách
        if crm.get("name") and "customer_name" not in facts:
            memory.set_profile_fact(cid, "customer_name", crm["name"])
        if crm.get("honorific") and "honorific" not in facts:
            memory.set_profile_fact(cid, "honorific", crm["honorific"])

    def _forget_customer(self, customer_id: str) -> None:
        self.identity_map.forget_master(customer_id)
        self._shared_choice = {p: c for p, c in self._shared_choice.items() if c.get("customer_id") != customer_id}

    # ------------------------------------------------------------------ resolve
    def resolve(self, turn: NormalizedTurn, memory=None) -> ResolvedIdentity:
        if memory is not None and id(memory) not in self._delete_hooked:
            memory.register_delete_listener(self._forget_customer)   # xóa khách -> xóa cả liên kết định danh trong RAM
            self._delete_hooked.add(id(memory))
        keys = self._lookup_keys(turn)
        crm_res = self._crm(**keys)
        phone = keys.get("phone") or self._contact_phone.get(turn.contact_id) or "UNKNOWN"

        if crm_res.get("found") and crm_res.get("ambiguous"):
            identity = self._resolve_shared(phone, crm_res, turn)
        elif crm_res.get("found"):
            identity = ResolvedIdentity(customer_id=crm_res.get("customer_id"), is_ambiguous=False,
                                        phone=crm_res.get("phone", phone), customer_profile=crm_res)
        else:
            # Khách chưa có trong CRM — customer_id PHẢI ổn định/deterministic theo liên hệ (băm SHA-256
            # có salt, không lộ SĐT/Zalo ID thô). Nếu liên hệ này đã được nối với hồ sơ khác thì trả về mã đã nối.
            master = self.identity_map.resolve_master_id(turn.contact_id or phone)
            identity = ResolvedIdentity(customer_id=master, is_ambiguous=False, phone=phone, customer_profile=None)
            said_phone = turn.extracted_entities.get("phone")
            if said_phone and not keys.get("phone"):
                identity = self._link_by_phone(turn, master, said_phone, memory)

        self._record_context(memory, identity, turn)
        return identity
