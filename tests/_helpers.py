"""Tiện ích dùng chung cho bộ test offline: không gọi OpenAI, không ghi runs/ hay data/."""
import os
import sys

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

# Ép nhánh không-LLM cho mọi test (không tốn API, kết quả tất định).
os.environ["OPENAI_API_KEY"] = ""
os.environ["MEMORY_EXTRACTOR_LLM"] = "0"
# Vận chuyển mặc định của TEST: cùng tiến trình. Phải đặt TRƯỚC khi test nào gọi `run_eval.main()` — hàm đó `setdefault` MCP_TRANSPORT/MEMORY_TRANSPORT = stdio
# vào os.environ của cả tiến trình, khiến mọi test sau đó (mỗi `build_components`) sinh thêm 2 tiến trình MCP server không bao giờ đóng: bộ test chậm gấp ~5 lần
# (2.411 s thay vì ~490 s) và để lại hàng trăm tiến trình. Test cần stdio thì tự đặt (test_mcp_servers, test_mcp_memory, test_pipeline_lifecycle).
os.environ.setdefault("MCP_TRANSPORT", "inproc")
os.environ.setdefault("MEMORY_TRANSPORT", "local")

BTC_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS")
PUBLIC_DIR = os.path.join(BTC_DIR, "test_set", "public_sample")
GENERATED_DIR = os.path.join(BTC_DIR, "test_set", "generated_m1")


def advisor_suggests(test, sku="SKU-AP-Y"):
    """Nhánh rule-based không tự chọn sản phẩm (CHECKING §11.93): test cần một sản phẩm đã tư vấn thì nói rõ ở đây."""
    from unittest import mock
    from src.agents.specialists import SalesAdvisorAgent
    real = SalesAdvisorAgent.advise

    def advise(self, st):
        brief = st.get("call_brief", {})
        return real(self, {**st, "call_brief": {**brief, "product_advised": brief.get("product_advised") or sku}})
    p = mock.patch.object(SalesAdvisorAgent, "advise", advise)
    p.start()
    test.addCleanup(p.stop)


def build_components(order_gate: bool = False):
    """Dựng bộ thành phần runtime in-memory (không SQLite) giống runner.
    `order_gate=False` (mặc định cho test) tắt cổng đặt đơn để các test về cơ chế khác (chống gọi lặp, PII, bộ nhớ…) không phải đi qua quy trình
    hỏi–đọc lại–đồng ý; test của chính cổng (tests/test_order_gate.py) dùng `order_gate=True`. Runner/UI/main luôn bật cổng."""
    from src.channels.normalizer import RequestNormalizer
    from src.memory.remote import create_memory_service
    from src.tools.mcp_gateway import MCPToolGateway, CRMTool, CatalogPricingTool, OrderCallbackTool, reset_mock_state
    from src.identity.resolver import IdentityResolver
    from src.harness.call_brief import CallBriefBuilder
    from src.harness.guardrail import GuardrailAndFallback
    from src.harness.orchestrator import HarnessOrchestrator
    from src.agents.specialists import A2AAgentNetwork

    reset_mock_state()
    # Bộ nhớ theo MEMORY_TRANSPORT (mặc định `local`; đặt `inproc`/`stdio` để chạy CẢ bộ test qua mcp-memory). `memory` là view của TestHarness (toàn quyền, để test
    # đọc/ghi trực tiếp); mỗi thành phần nhận view riêng với tên caller của nó — phân quyền được kiểm thật trên cùng đường chạy.
    memory = create_memory_service(enable_persistence=False, caller="TestHarness")
    orch_memory = memory.as_caller("HarnessOrchestrator")
    mcp = MCPToolGateway(CRMTool(), CatalogPricingTool(), OrderCallbackTool())
    orch = HarnessOrchestrator(mcp, orch_memory, A2AAgentNetwork(orch_memory), GuardrailAndFallback(), llm_client=None)
    if not order_gate:
        orch.order_gate.disable_for_unit_tests()
    return {
        "normalizer": RequestNormalizer(),
        "memory": memory,
        "mcp": mcp,
        "resolver": IdentityResolver(mcp, identity_backend=None),
        "brief": CallBriefBuilder(memory.as_caller("CallBriefBuilder"), tool_gateway=mcp),
        "guardrail": GuardrailAndFallback(),
        "orchestrator": orch,
    }
