"""
Schema slot → thuộc tính catalog (DỮ LIỆU trong `config/slot_rules.json`, không hard-code tên sản phẩm).

Mỗi `SlotRule` nối một slot khách đã nêu (vd `has_children`, `room_area_m2`, `budget_vnd`) với MỘT thuộc tính thật của sản phẩm
(`attributes.child_safe_lock`, `attributes.room_area_m2`, `list_price_vnd`…) bằng một phép so (`eq|gte|lte|over_budget|contains`).
Luật chỉ áp dụng khi slot đã biết VÀ sản phẩm có thuộc tính đó; ngược lại trung tính. Thêm luật/ngành mới = thêm dòng JSON.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_RULES_PATH = os.path.join(CODE_DIR, "config", "slot_rules.json")
OPS = {"eq", "gte", "lte", "over_budget", "contains"}
PRICE_ATTRIBUTE = "list_price_vnd"


@dataclass(frozen=True)
class SlotRule:
    id: str
    slot: str
    attribute: str
    op: str
    weight: float
    violate_weight: float
    reason: str
    question: str = ""
    value: Any = None                 # với op=eq: giá trị thuộc tính cần có
    slot_equals: Any = None           # luật chỉ kích hoạt khi slot == giá trị này (vd has_children == true)
    prefer_closest: bool = False      # gte: thưởng sản phẩm sát nhu cầu (tránh thừa công suất)


@dataclass
class RuleSet:
    version: str
    rules: List[SlotRule]
    settings: Dict[str, Any] = field(default_factory=dict)
    question_priority: List[str] = field(default_factory=list)
    confirm_templates: Dict[str, Any] = field(default_factory=dict)

    def slots(self) -> List[str]:
        return list(dict.fromkeys(r.slot for r in self.rules))

    def rules_for(self, slot: str) -> List[SlotRule]:
        return [r for r in self.rules if r.slot == slot]

    def question_for(self, slot: str) -> str:
        for r in self.rules_for(slot):
            if r.question:
                return r.question
        return ""


class RuleError(ValueError):
    pass


def parse_rules(data: Dict[str, Any]) -> RuleSet:
    rules: List[SlotRule] = []
    seen = set()
    for raw in data.get("rules", []):
        for key in ("id", "slot", "attribute", "op", "weight", "reason"):
            if key not in raw:
                raise RuleError(f"luật thiếu trường '{key}': {raw}")
        if raw["op"] not in OPS:
            raise RuleError(f"luật {raw['id']}: op '{raw['op']}' không hợp lệ (chọn {sorted(OPS)})")
        if raw["id"] in seen:
            raise RuleError(f"trùng id luật: {raw['id']}")
        seen.add(raw["id"])
        if float(raw["weight"]) <= 0:
            raise RuleError(f"luật {raw['id']}: weight phải > 0")
        if raw["op"] == "eq" and "value" not in raw:
            raise RuleError(f"luật {raw['id']}: op=eq cần 'value'")
        rules.append(SlotRule(id=raw["id"], slot=raw["slot"], attribute=raw["attribute"], op=raw["op"],
                              weight=float(raw["weight"]), violate_weight=float(raw.get("violate_weight", raw["weight"])),
                              reason=raw["reason"], question=raw.get("question", ""), value=raw.get("value"),
                              slot_equals=raw.get("slot_equals"), prefer_closest=bool(raw.get("prefer_closest", False))))
    return RuleSet(version=data.get("version", "?"), rules=rules, settings=dict(data.get("settings", {})),
                   question_priority=list(data.get("question_priority", [])), confirm_templates=dict(data.get("confirm_templates", {})))


def load_rules(path: Optional[str] = None) -> RuleSet:
    with open(path or DEFAULT_RULES_PATH, encoding="utf-8") as fh:
        return parse_rules(json.load(fh))


def validate_against_catalog(rules: RuleSet, products: List[Dict[str, Any]]) -> List[str]:
    """Trả danh sách vấn đề: luật trỏ tới thuộc tính KHÔNG sản phẩm nào có (luật chết) hoặc tới giá trị sai kiểu."""
    problems = []
    for r in rules.rules:
        if r.attribute == PRICE_ATTRIBUTE:
            continue
        holders = [p for p in products if r.attribute in (p.get("attributes") or {})]
        if not holders:
            problems.append(f"luật '{r.id}': không sản phẩm nào có thuộc tính '{r.attribute}'")
            continue
        if r.op in ("gte", "lte") and not all(isinstance(p["attributes"][r.attribute], (int, float)) and not isinstance(p["attributes"][r.attribute], bool) for p in holders):
            problems.append(f"luật '{r.id}': op {r.op} cần thuộc tính số nhưng '{r.attribute}' có giá trị không phải số")
        if r.op == "contains" and not all(isinstance(p["attributes"][r.attribute], str) for p in holders):
            problems.append(f"luật '{r.id}': op contains cần thuộc tính chữ")
    return problems
