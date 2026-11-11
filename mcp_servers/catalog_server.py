"""
MCP server `mcp-catalog`: tra cứu sản phẩm, tồn kho theo ngày, báo giá theo khuyến mãi, và chọn sản phẩm theo slot.

Tool: catalog.search · inventory.check · pricing.get_quote · pricing.quote_order · product.shortlist
Kết quả của `mock_tools.py` (BTC) giữ nguyên. Chạy riêng:  python -m mcp_servers.catalog_server   (stdio)
"""
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import Context, MCPServer

from mcp_servers.common import Guarded, Permissions
from src.tools.tool_impl import CatalogPricingTool


def build_server(impl: Optional[CatalogPricingTool] = None, permissions: Optional[Permissions] = None, retriever=None):
    impl = impl or CatalogPricingTool()
    guard = Guarded("mcp-catalog", permissions or Permissions.load())
    server = MCPServer("mcp-catalog", instructions="Catalog, tồn kho theo ngày, giá sau khuyến mãi, chọn sản phẩm theo slot. Chỉ đọc.")
    state = {"retriever": retriever}

    def _retriever():
        if state["retriever"] is None:
            from src.catalog import ProductRetriever
            state["retriever"] = ProductRetriever()
        return state["retriever"]

    @server.tool(name="catalog.search")
    def catalog_search(ctx: Context, query: Optional[str] = None, category: Optional[str] = None, sku: Optional[str] = None,
                       max_price_vnd: Optional[int] = None, min_room_area_m2: Optional[float] = None) -> Dict[str, Any]:
        """Tìm sản phẩm theo từ khóa/danh mục/SKU (kèm biến thể size, màu)."""
        return guard.run("catalog.search", ctx, impl.search, query=query, category=category, sku=sku,
                         max_price_vnd=max_price_vnd, min_room_area_m2=min_room_area_m2)

    @server.tool(name="inventory.check")
    def inventory_check(ctx: Context, sku: str, on: str = "2026-10-15") -> Dict[str, Any]:
        """Tồn kho của SKU tại ngày `on`."""
        return guard.run("inventory.check", ctx, impl.inventory_check, sku=sku, on=on)

    @server.tool(name="pricing.get_quote")
    def pricing_get_quote(ctx: Context, sku: str, on: str = "2026-10-15", qty: int = 1, customer_phone: Optional[str] = None,
                          address: Optional[str] = None, basket_skus: Optional[List[str]] = None) -> Dict[str, Any]:
        """Giá cuối cho 1 đơn vị `sku` sau khuyến mãi theo ngày `on` (basket_skus = các SKU KHÁC trong cùng đơn)."""
        return guard.run("pricing.get_quote", ctx, impl.get_quote, sku=sku, on=on, qty=qty, customer_phone=customer_phone,
                         address=address, basket_skus=basket_skus)

    @server.tool(name="pricing.quote_order")
    def pricing_quote_order(ctx: Context, lines: List[Dict[str, Any]], on: str = "2026-10-15", customer_phone: Optional[str] = None,
                            address: Optional[str] = None) -> Dict[str, Any]:
        """Giá TỪNG MÁY cho đơn nhiều dòng `lines` = [{sku, qty}] (KM 'máy thứ 2' chỉ một máy/đơn)."""
        return guard.run("pricing.quote_order", ctx, impl.quote_order, lines=lines, on=on, customer_phone=customer_phone, address=address)

    @server.tool(name="product.shortlist")
    def product_shortlist(ctx: Context, category: Optional[str] = None, query: Optional[str] = None, on: str = "2026-10-15",
                          top_k: Optional[int] = None, room_area_m2: Optional[float] = None, has_children: Optional[bool] = None,
                          budget_vnd: Optional[int] = None, child_weight_kg: Optional[float] = None, volume_ml: Optional[int] = None,
                          min_warranty_months: Optional[int] = None, min_stages: Optional[int] = None, material: Optional[str] = None,
                          min_return_days: Optional[int] = None, list_all: Optional[bool] = None) -> Dict[str, Any]:
        """Chấm điểm sản phẩm theo slot khách nêu (luật dữ liệu config/slot_rules.json); trả top-k kèm lý do và slot còn thiếu. list_all=true: liệt kê MỌI mẫu khớp."""
        slots = {"room_area_m2": room_area_m2, "has_children": has_children, "budget_vnd": budget_vnd, "child_weight_kg": child_weight_kg,
                 "volume_ml": volume_ml, "min_warranty_months": min_warranty_months, "min_stages": min_stages, "material": material,
                 "min_return_days": min_return_days}

        def run() -> Dict[str, Any]:
            def in_stock(sku: str) -> Optional[bool]:
                res = impl.inventory_check(sku=sku, on=on)
                return res.get("in_stock") if isinstance(res, dict) and "error" not in res else None
            return _retriever().shortlist({k: v for k, v in slots.items() if v is not None}, category=category, query=query,
                                          top_k=top_k, in_stock_fn=in_stock, list_all=bool(list_all)).to_dict()
        return guard.run("product.shortlist", ctx, run)

    @server.tool(name="admin.audit")
    def admin_audit(ctx: Context) -> Dict[str, Any]:
        """(Chỉ bộ chạy đánh giá/test) nhật ký kiểm toán phía server (không chứa tham số)."""
        return guard.run("admin.audit", ctx, lambda: {"audit": list(guard.audit)})

    return server, guard


if __name__ == "__main__":
    build_server()[0].run("stdio")
