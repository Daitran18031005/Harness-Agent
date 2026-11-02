"""
A2A Specialist Agents: Multi-Agent chuyên biệt phối hợp cùng Orchestrator
Ủy quyền nhiệm vụ cho:
1. Context & Memory Agent: Xác thực và chuẩn bị ngữ cảnh
2. Sales Advisor Agent: Tư vấn sản phẩm, so sánh thông số theo profile khách
3. Policy Compliance Agent: Tra cứu chính sách từ RAG, veto nếu vi phạm
4. QA / Evaluator Agent: Đánh giá chất lượng lượt thoại
"""
from typing import Dict, Any, List, Optional
from src.memory.service import MemoryService

_CATALOG: Optional[Dict[str, Dict[str, Any]]] = None


def catalog_product(sku: Optional[str]) -> Dict[str, Any]:
    """Sản phẩm CHA trong catalog (rỗng nếu không biết). Biến thể `SKU-SN-CAS-39-DEN` → sản phẩm cha `SKU-SN-CAS`."""
    global _CATALOG
    if _CATALOG is None:
        from src.catalog.retriever import ProductRetriever
        _CATALOG = {p["sku"]: p for p in ProductRetriever().products}
    s = sku or ""
    while s and s not in _CATALOG:
        s = s.rsplit("-", 1)[0] if "-" in s else ""
    return _CATALOG.get(s, {})


def catalog_products() -> Dict[str, Dict[str, Any]]:
    """Mọi sản phẩm CHA của catalog {sku: sản phẩm}."""
    catalog_product(None)
    return _CATALOG or {}


def product_name(sku: Optional[str]) -> str:
    """Tên nói với khách: tên trong catalog; không có thì giữ mã (không bao giờ bịa tên)."""
    return catalog_product(sku).get("name") or (sku or "")


class ContextAgent:
    """Xử lý tính nhất quán của danh tính và đề xuất ghi nhớ"""
    def __init__(self, memory: MemoryService):
        self.memory = memory

    def analyze_memory_proposal(self, customer_id: str, turn_text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        proposals = []
        for k, v in entities.items():
            proposals.append({"key": k, "value": v, "confidence": 0.95})
        return {"agent": "ContextAgent", "memory_proposals": proposals}


class SalesAdvisorAgent:
    """Tư vấn bán hàng dựa trên profile khách và catalog"""
    def __init__(self, memory: MemoryService):
        self.memory = memory

    def advise(self, shared_state: Dict[str, Any]) -> Dict[str, Any]:
        profile = shared_state.get("profile", {})
        advised_sku = shared_state.get("call_brief", {}).get("product_advised")
        if not advised_sku:                                   # không biết sản phẩm → không gợi ý sản phẩm tự chọn
            return {"agent": "SalesAdvisor", "suggested_sku": None, "talking_point": ""}
        attrs = catalog_product(advised_sku).get("attributes") or {}
        area, has_kids = profile.get("room_area_m2"), profile.get("has_children", False)

        # Chỉ nói điều CÓ trong catalog (không gắn cứng "HEPA H13"/"khóa trẻ em" cho mọi sản phẩm): đây là nhánh dự phòng khi mất LLM.
        points = []
        if attrs.get("features"):
            points.append(f"có {attrs['features']}")
        if area and attrs.get("room_area_m2") and float(attrs["room_area_m2"]) >= float(area):
            points.append(f"phù hợp phòng khoảng {float(area):g}m²")
        if has_kids and attrs.get("child_safe_lock") is True:
            points.append("có khóa an toàn cho trẻ nhỏ")
        advice = f"{product_name(advised_sku)} " + ", ".join(points) + "." if points else ""

        return {
            "agent": "SalesAdvisor",
            "suggested_sku": advised_sku,
            "talking_point": advice
        }


class PolicyComplianceAgent:
    """Kiểm tra tuân thủ chính sách từ Semantic KB (RAG), veto nếu cam kết sai"""
    def __init__(self, memory: MemoryService):
        self.memory = memory

    def verify_policy(self, query: str, on_date: str) -> Dict[str, Any]:
        chunks = self.memory.query_policy(query, on_date=on_date)
        # Chunk internal không bao giờ được lọt qua access_level="public" ở semantic_rag.search,
        # nhưng double-check ở đây để veto cứng nếu có bất thường.
        is_compliant = all(c.get("access", "public") == "public" for c in chunks)

        grounded_answer = ""
        if chunks:
            top = chunks[0]
            # Lấy 1-2 câu đầu của chunk thật làm câu trả lời có căn cứ (grounded),
            # thay vì để agent tự bịa — đây là cách phrase chuẩn (VD "7 ngày") xuất hiện tự nhiên.
            sentences = [s.strip() for s in top["content"].split(". ") if s.strip()]
            grounded_answer = ". ".join(sentences[:2])
            if grounded_answer and not grounded_answer.endswith("."):
                grounded_answer += "."

        return {
            "agent": "PolicyComplianceAgent",
            "policy_chunks": chunks,
            "is_compliant": is_compliant,
            "citation": [c["chunk_id"] for c in chunks],
            "grounded_answer": grounded_answer,
            "top_chunk_id": chunks[0]["chunk_id"] if chunks else None
        }


class QAEvaluatorAgent:
    """Chấm điểm cuộc gọi theo rubric thời gian thực"""
    def __init__(self):
        pass

    def check_turn(self, agent_text: str, must_not_ask: List[str]) -> Dict[str, Any]:
        violations = []
        for slot in must_not_ask:
            if slot == "room_area_m2" and "bao nhiêu mét vuông" in agent_text.lower():
                violations.append("Hỏi lại diện tích phòng đã có trong profile")
        return {
            "agent": "QAEvaluatorAgent",
            "violations": violations,
            "passed": len(violations) == 0
        }


class A2AAgentNetwork:
    """Facade điều phối giao tiếp giữa các Specialist Agents"""
    def __init__(self, memory: MemoryService):
        self.context_agent = ContextAgent(memory)
        self.sales_agent = SalesAdvisorAgent(memory)
        self.policy_agent = PolicyComplianceAgent(memory)
        self.qa_agent = QAEvaluatorAgent()

    def delegate_task(self, task_type: str, shared_state: Dict[str, Any]) -> Dict[str, Any]:
        if task_type == "sales_advice":
            return self.sales_agent.advise(shared_state)
        elif task_type == "policy_check":
            query = shared_state.get("query", "chính sách đổi trả bảo hành")
            on_date = shared_state.get("on_date", "2026-10-15")
            return self.policy_agent.verify_policy(query, on_date)
        elif task_type == "context_analysis":
            cid = shared_state.get("customer_id", "")
            turn_text = shared_state.get("text", "")
            entities = shared_state.get("entities", {})
            return self.context_agent.analyze_memory_proposal(cid, turn_text, entities)
        return {"error": f"Task {task_type} unknown"}
