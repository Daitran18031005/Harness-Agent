"""
MCP server `mcp-crm`: khách hàng (CRM), đơn hàng, lịch gọi lại, chuyển máy, và tool quản trị cho bộ chạy đánh giá.

Tool: crm.get_customer · order.create · order.status · order.update · schedule.callback · handoff.transfer · admin.reset_state · admin.audit
(Tạm gộp `order.*` ở đây; tách `mcp-order` ở M2.) Tool GHI chỉ dành cho lõi điều phối (xem config/mcp_permissions.json).
Chạy riêng:  python -m mcp_servers.crm_server   (stdio)
"""
from typing import Any, Dict, Optional

from mcp.server.mcpserver import Context, MCPServer

from mcp_servers.common import Guarded, Permissions
from src.tools.tool_impl import CRMTool, OrderCallbackTool, reset_mock_state


def build_server(crm: Optional[CRMTool] = None, order: Optional[OrderCallbackTool] = None, permissions: Optional[Permissions] = None):
    crm, order = crm or CRMTool(), order or OrderCallbackTool()
    guard = Guarded("mcp-crm", permissions or Permissions.load())
    server = MCPServer("mcp-crm", instructions="CRM, đơn hàng, lịch gọi lại, chuyển máy. Tool ghi bị giới hạn theo caller.")

    @server.tool(name="crm.get_customer")
    def crm_get_customer(ctx: Context, phone: Optional[str] = None, zalo_id: Optional[str] = None, fb_id: Optional[str] = None) -> Dict[str, Any]:
        """Tra khách theo SĐT / Zalo / Fanpage."""
        return guard.run("crm.get_customer", ctx, crm.get_customer, phone=phone, zalo_id=zalo_id, fb_id=fb_id)

    @server.tool(name="order.create")
    def order_create(ctx: Context, customer_phone: str, sku: str, qty: int = 1, price_vnd: Optional[int] = None, promo_code: Optional[str] = None,
                     payment: str = "COD", address: Optional[str] = None, on: str = "2026-10-15") -> Dict[str, Any]:
        """Tạo đơn hàng (GHI)."""
        return guard.run("order.create", ctx, order.create_order, customer_phone=customer_phone, sku=sku, qty=qty, price_vnd=price_vnd,
                         promo_code=promo_code, payment=payment, address=address, on=on)

    @server.tool(name="order.status")
    def order_status(ctx: Context, order_id: Optional[str] = None, customer_phone: Optional[str] = None) -> Dict[str, Any]:
        """Trạng thái đơn theo mã đơn hoặc SĐT."""
        return guard.run("order.status", ctx, order.order_status, order_id=order_id, customer_phone=customer_phone)

    @server.tool(name="order.update")
    def order_update(ctx: Context, order_id: str, action: str, new_variant_sku: Optional[str] = None, reason: Optional[str] = None,
                     on: str = "2026-10-15") -> Dict[str, Any]:
        """Đổi size/màu/hủy/hoàn (GHI)."""
        return guard.run("order.update", ctx, order.order_update, order_id=order_id, action=action, new_variant_sku=new_variant_sku,
                         reason=reason, on=on)

    @server.tool(name="schedule.callback")
    def schedule_callback(ctx: Context, customer_phone: str, callback_at: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Đặt lịch gọi lại (GHI)."""
        return guard.run("schedule.callback", ctx, order.schedule_callback, customer_phone=customer_phone, callback_at=callback_at, note=note)

    @server.tool(name="handoff.transfer")
    def handoff_transfer(ctx: Context, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Chuyển máy cho nhân viên kèm Handoff Brief (GHI)."""
        return guard.run("handoff.transfer", ctx, order.handoff_transfer, brief=brief)

    @server.tool(name="admin.reset_state")
    def admin_reset_state(ctx: Context) -> Dict[str, Any]:
        """(Chỉ bộ chạy đánh giá/test) xóa trạng thái đơn/vé/lịch/KM dùng-một-lần để mỗi kịch bản độc lập."""
        return guard.run("admin.reset_state", ctx, lambda: (reset_mock_state(), {"reset": True})[1])

    @server.tool(name="admin.audit")
    def admin_audit(ctx: Context) -> Dict[str, Any]:
        """(Chỉ bộ chạy đánh giá/test) nhật ký kiểm toán phía server (không chứa tham số)."""
        return guard.run("admin.audit", ctx, lambda: {"audit": list(guard.audit)})

    return server, guard


if __name__ == "__main__":
    build_server()[0].run("stdio")
