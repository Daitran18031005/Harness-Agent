"""
ProductRetriever — chấm điểm mọi sản phẩm trong catalog theo các SLOT khách đã nêu, bằng luật DỮ LIỆU (`config/slot_rules.json`),
trả top-k kèm LÝ DO chấm và danh sách slot còn thiếu đáng hỏi. Không có tên sản phẩm/SKU nào nằm trong mã.

Nguyên tắc: luật không LOẠI sản phẩm nào (trừ ngừng bán / ngoài danh mục), chỉ cộng/trừ điểm và nêu lý do — nên sản phẩm duy nhất
thỏa ràng buộc an toàn vẫn đứng đầu dù vượt ngân sách, còn mức vượt được nêu rõ để agent báo cho khách.
"""
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .slot_schema import PRICE_ATTRIBUTE, CODE_DIR, RuleSet, SlotRule, load_rules
from .textmatch import filter_products

DEFAULT_PRODUCTS_PATH = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "catalog", "products.json")


def fold(text: Any) -> str:
    s = unicodedata.normalize("NFD", str(text or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if re.fullmatch(r"[\d.,]+", str(v).strip()) else None
    except ValueError:
        return None


def _bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        low = v.strip().lower()
        if low in ("true", "có", "co", "yes", "1"):
            return True
        if low in ("false", "không", "khong", "no", "0"):
            return False
    if isinstance(v, (int, float)):
        return bool(v)
    return None


@dataclass
class ShortlistItem:
    sku: str
    name: str
    category: str
    list_price_vnd: int
    score: float
    matched: List[Dict[str, str]] = field(default_factory=list)
    violated: List[Dict[str, str]] = field(default_factory=list)
    unknown: List[str] = field(default_factory=list)
    in_stock: Optional[bool] = None
    has_variants: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = {"sku": self.sku, "name": self.name, "list_price_vnd": self.list_price_vnd, "score": round(self.score, 2),
             "matched": self.matched, "violated": self.violated}
        if self.unknown:
            d["unknown"] = self.unknown
        if self.in_stock is not None:
            d["in_stock"] = self.in_stock
        if self.has_variants:
            d["has_variants"] = True
        return d


@dataclass
class ShortlistResult:
    items: List[ShortlistItem]
    slots_used: Dict[str, Any]
    missing_slots: List[Dict[str, Any]]
    n_candidates: int
    rules_version: str
    decision: Dict[str, Any] = field(default_factory=lambda: {"mode": "single"})
    alternative: Optional["ShortlistItem"] = None

    @property
    def top(self) -> Optional[ShortlistItem]:
        return self.items[0] if self.items else None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"items": [i.to_dict() for i in self.items], "slots_used": self.slots_used,
                               "n_candidates": self.n_candidates, "rules_version": self.rules_version}
        if self.n_candidates > len(self.items):
            out["more_available"] = self.n_candidates - len(self.items)      # còn mẫu khác chưa liệt kê (gọi lại với list_all=true nếu khách muốn xem hết)
        if self.missing_slots:
            out["ask_next"] = self.missing_slots
        if self.items:
            out["recommendation"] = self.items[0].sku
        out["decision"] = self.decision
        if self.alternative is not None:
            out["alternative"] = self.alternative.to_dict()
        return out


class ProductRetriever:
    def __init__(self, products: Optional[List[Dict[str, Any]]] = None, rules: Optional[RuleSet] = None,
                 products_path: Optional[str] = None):
        if products is None:
            with open(products_path or DEFAULT_PRODUCTS_PATH, encoding="utf-8") as fh:
                products = json.load(fh)["products"]
        self.products = products
        self.rules = rules or load_rules()
        s = self.rules.settings
        self.top_k = int(s.get("top_k", 3))
        self.oos_penalty = float(s.get("out_of_stock_penalty", 2.0))
        self.discontinued_penalty = float(s.get("discontinued_penalty", 100.0))
        self.waste_penalty = float(s.get("oversize_waste_penalty", 0.4))
        self.budget_tolerance = float(s.get("budget_tolerance", 0.20))
        self.accessory_segments = {fold(x) for x in s.get("accessory_categories", [])}
        self.accessory_terms = [fold(x) for x in s.get("accessory_query_terms", [])]

    # -- chọn ứng viên ------------------------------------------------------------------------------
    @staticmethod
    def _haystack(p: Dict[str, Any]) -> str:
        return fold(" ".join([p.get("name", ""), p.get("brand", ""), p.get("category", ""), p.get("sku", "")]))

    def _is_accessory(self, p: Dict[str, Any]) -> bool:
        return fold(p.get("category", "").split("/")[-1]) in self.accessory_segments

    def candidates(self, category: Optional[str], query: Optional[str], include_discontinued: bool) -> List[Dict[str, Any]]:
        want_accessory = any(t and t in fold(f"{category or ''} {query or ''}") for t in self.accessory_terms)
        out = []
        for p in self.products:
            attrs = p.get("attributes") or {}
            if attrs.get("discontinued") and not include_discontinued:
                continue
            if self._is_accessory(p) and not want_accessory:
                continue
            out.append(p)
        # So khớp chịu được câu nói tự nhiên ("các mẫu máy lọc nước nào", "xe đẩy em bé") — xem textmatch.py
        out = filter_products(out, category, self._haystack)
        return filter_products(out, query, self._haystack)

    # -- chấm điểm ----------------------------------------------------------------------------------
    def _evaluate(self, p: Dict[str, Any], rule: SlotRule, slot_value: Any):
        """Trả (kết quả, điểm, mô tả) với kết quả ∈ matched | violated | unknown."""
        attrs = p.get("attributes") or {}
        attr = p.get("list_price_vnd") if rule.attribute == PRICE_ATTRIBUTE else attrs.get(rule.attribute)
        if attr is None:
            return "unknown", 0.0, ""
        if rule.op == "eq":
            ok = attr == rule.value
            return ("matched", rule.weight, rule.reason) if ok else ("violated", -rule.violate_weight, rule.reason)
        if rule.op == "contains":
            ok = fold(slot_value) in fold(attr)
            return ("matched", rule.weight, rule.reason) if ok else ("violated", -rule.violate_weight, rule.reason)
        need, have = _num(slot_value), _num(attr)
        if need is None or have is None:
            return "unknown", 0.0, ""
        if rule.op == "gte":
            if have >= need:
                waste = self.waste_penalty * (have - need) / have if (rule.prefer_closest and have) else 0.0
                return "matched", rule.weight - waste, rule.reason
            gap = min(1.0, (need - have) / need) if need else 1.0          # thiếu càng nhiều càng bị trừ nặng (50–100% mức phạt)
            return "violated", -rule.violate_weight * (0.5 + 0.5 * gap), f"{rule.reason} (có {have:g}, cần {need:g})"
        if rule.op == "lte":
            if have <= need:
                return "matched", rule.weight, rule.reason
            gap = min(1.0, (have - need) / need) if need else 1.0
            return "violated", -rule.violate_weight * (0.5 + 0.5 * gap), f"{rule.reason} (có {have:g}, tối đa {need:g})"
        if rule.op == "over_budget":
            if have <= need:
                return "matched", rule.weight, f"giá {int(have):,}đ trong ngân sách {int(need):,}đ".replace(",", ".")
            over = (have - need) / need
            return "violated", -rule.violate_weight * min(1.0, over * 2), f"giá {int(have):,}đ vượt ngân sách {int(need):,}đ khoảng {over:.0%}".replace(",", ".")
        return "unknown", 0.0, ""

    def _active_rules(self, slots: Dict[str, Any]):
        for r in self.rules.rules:
            if r.slot not in slots or slots[r.slot] is None:
                continue
            if r.slot_equals is not None:
                if _bool(slots[r.slot]) != _bool(r.slot_equals) and slots[r.slot] != r.slot_equals:
                    continue
            yield r

    def normalize_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Bỏ slot rỗng/không nhận ra, ép kiểu (số/boolean) theo loại luật."""
        out: Dict[str, Any] = {}
        known = {r.slot: r for r in self.rules.rules}
        for k, v in (slots or {}).items():
            if v is None or v == "" or k not in known:
                continue
            r = known[k]
            if r.op in ("gte", "lte", "over_budget"):
                n = _num(v)
                if n is not None:
                    out[k] = int(n) if float(n).is_integer() else n
            elif r.slot_equals is not None or r.op == "eq":
                b = _bool(v)
                if b is not None:
                    out[k] = b
            else:
                out[k] = str(v)
        return out

    def shortlist(self, slots: Optional[Dict[str, Any]] = None, category: Optional[str] = None, query: Optional[str] = None,
                  top_k: Optional[int] = None, in_stock_fn: Optional[Callable[[str], Optional[bool]]] = None,
                  include_discontinued: bool = False, list_all: bool = False) -> ShortlistResult:
        """`list_all=True`: khách hỏi "có các mẫu nào" → trả MỌI mẫu khớp (không cắt ở top_k), vẫn xếp theo điểm."""
        slots = self.normalize_slots(slots or {})
        cands = self.candidates(category, query, include_discontinued)
        active = list(self._active_rules(slots))
        items: List[ShortlistItem] = []
        for p in cands:
            attrs = p.get("attributes") or {}
            score, matched, violated, unknown = 0.0, [], [], []
            for r in active:
                outcome, pts, text = self._evaluate(p, r, slots[r.slot])
                if outcome == "unknown":
                    unknown.append(r.id)
                    continue
                score += pts
                (matched if outcome == "matched" else violated).append({"rule": r.id, "why": text})
            if attrs.get("discontinued"):
                score -= self.discontinued_penalty
                violated.append({"rule": "discontinued", "why": "sản phẩm đã ngừng bán"})
            stock = in_stock_fn(p["sku"]) if in_stock_fn else None
            if stock is False:
                score -= self.oos_penalty
                violated.append({"rule": "out_of_stock", "why": "hết hàng tại ngày gọi"})
            items.append(ShortlistItem(sku=p["sku"], name=p.get("name", ""), category=p.get("category", ""),
                                       list_price_vnd=int(p.get("list_price_vnd") or 0), score=score, matched=matched,
                                       violated=violated, unknown=unknown, in_stock=stock, has_variants=bool(p.get("variants"))))
        items.sort(key=lambda i: (-i.score, i.list_price_vnd, i.sku))
        k = len(items) if list_all else int(top_k or self.top_k)
        decision, alternative = self._budget_decision(items, slots)
        return ShortlistResult(items=items[:k], slots_used=slots, missing_slots=self._missing_slots(slots, cands),
                               n_candidates=len(cands), rules_version=self.rules.version, decision=decision, alternative=alternative)

    def _budget_decision(self, ranked: List[ShortlistItem], slots: Dict[str, Any]):
        """Luật ngân sách: sản phẩm đứng đầu vượt ngân sách ≤ `budget_tolerance` (20%) → chốt 1 sản phẩm và nêu mức vượt;
        vượt hơn → 2 lựa chọn: đứng đầu + sản phẩm điểm cao nhất TRONG ngân sách (nếu có)."""
        budget = _num(slots.get("budget_vnd"))
        if not ranked or not budget:
            return {"mode": "single", "primary": ranked[0].sku if ranked else None}, None
        top = ranked[0]
        over = (top.list_price_vnd - budget) / budget
        if over <= 0:
            return {"mode": "single", "primary": top.sku, "overage_pct": 0.0}, None
        if over <= self.budget_tolerance:
            return {"mode": "single", "primary": top.sku, "overage_pct": round(over * 100, 1),
                    "note": "vượt ngân sách trong mức cho phép → vẫn chốt sản phẩm đứng đầu và nêu rõ mức vượt"}, None
        alt = next((i for i in ranked[1:] if i.list_price_vnd <= budget and not any(v["rule"] in ("discontinued",) for v in i.violated)), None)
        if alt is None:
            return {"mode": "single", "primary": top.sku, "overage_pct": round(over * 100, 1), "no_in_budget_alternative": True,
                    "note": "vượt ngân sách quá mức cho phép nhưng không có sản phẩm nào trong ngân sách → nêu rõ mức vượt"}, None
        return {"mode": "two_options", "primary": top.sku, "alternative": alt.sku, "overage_pct": round(over * 100, 1),
                "note": "vượt ngân sách quá mức cho phép → giới thiệu CẢ HAI: sản phẩm đứng đầu và lựa chọn tốt nhất trong ngân sách"}, alt

    # -- slot còn thiếu đáng hỏi --------------------------------------------------------------------
    def _separates(self, rule: SlotRule, cands: List[Dict[str, Any]]) -> int:
        """Số sản phẩm mà luật này sẽ phân biệt được (0 = hỏi cũng không đổi kết quả)."""
        vals = []
        for p in cands:
            attrs = p.get("attributes") or {}
            v = p.get("list_price_vnd") if rule.attribute == PRICE_ATTRIBUTE else attrs.get(rule.attribute)
            if v is not None:
                vals.append(v)
        if len(vals) < 2:
            return 0
        if rule.op == "eq":
            hit = sum(1 for v in vals if v == rule.value)
            return min(hit, len(vals) - hit)
        if rule.op == "over_budget":
            lo, hi = min(vals), max(vals)
            return len(vals) if lo and hi / lo > 1.2 else 0
        return len(set(vals)) if len(set(vals)) > 1 else 0

    def _missing_slots(self, slots: Dict[str, Any], cands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(cands) < 2:
            return []
        prio = {s: i for i, s in enumerate(self.rules.question_priority)}
        out, seen = [], set()
        for r in self.rules.rules:
            if r.slot in slots or r.slot in seen:
                continue
            sep = max((self._separates(x, cands) for x in self.rules.rules_for(r.slot)), default=0)
            if sep > 0:
                seen.add(r.slot)
                out.append({"slot": r.slot, "question": self.rules.question_for(r.slot), "separates": sep})
        out.sort(key=lambda x: (prio.get(x["slot"], 99), -x["separates"]))
        return out
