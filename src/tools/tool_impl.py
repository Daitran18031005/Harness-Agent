"""
Cài đặt NGHIỆP VỤ của các tool (bọc `mock_tools.py` của BTC): CRM, Catalog/Giá/Tồn kho, Đơn hàng/Lịch gọi lại/Chuyển máy.
Đây là phần "bên trong" mà các MCP server (`mcp_servers/`) gọi tới; agent KHÔNG gọi trực tiếp mà đi qua `MCPToolGateway`
(client MCP, `src/tools/mcp_gateway.py`). Đảm bảo giá, tồn kho, khuyến mãi lấy 100% từ tool theo đúng business rules BTC.
"""
import os
import sys
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Import logic mock tools từ BTC-Data-Vong1-TEAMS nếu có
HERE = os.path.dirname(os.path.abspath(__file__))
for parent in [
    os.path.abspath(os.path.join(HERE, "..", "..")),
    os.path.abspath(os.path.join(HERE, "..", "..", "..")),
    os.getcwd(),
    os.path.abspath(os.path.join(os.getcwd(), ".."))
]:
    btc_candidate = os.path.join(parent, "BTC-Data-Vong1-TEAMS", "eval")
    if os.path.exists(btc_candidate):
        if btc_candidate not in sys.path:
            sys.path.insert(0, btc_candidate)
        break

try:
    import mock_tools as btc_mock
except ImportError:
    btc_mock = None


def reset_mock_state() -> None:
    """Xóa trạng thái toàn cục của mock_tools (đơn, vé, lịch gọi lại, KM dùng-một-lần) để mỗi
    kịch bản chạy độc lập: mã đơn (OD600001...) không phụ thuộc thứ tự chạy các kịch bản (N8)."""
    if btc_mock is None:
        return
    for name in ("_ORDERS", "_CALLBACKS", "_TICKETS", "_ONCE_USED"):
        container = getattr(btc_mock, name, None)
        if container is not None:
            container.clear()


def strip_internal(obj: Any) -> Any:
    """N15: loại ĐỆ QUY mọi field bắt đầu bằng '_' (vd _internal_price_floor_vnd — giá sàn nội bộ)
    khỏi kết quả tool TRƯỚC khi đưa vào LLM, trace và audit. Trả về bản sao mới, không sửa dữ liệu gốc."""
    if isinstance(obj, dict):
        return {k: strip_internal(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [strip_internal(v) for v in obj]
    return obj


class CRMTool:
    """Tương tác hệ thống CRM Khách hàng (Cloud/Database ngoài)"""
    def __init__(self):
        pass

    def get_customer(self, phone: Optional[str] = None, zalo_id: Optional[str] = None, fb_id: Optional[str] = None) -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.crm_get_customer(phone=phone, zalo_id=zalo_id, fb_id=fb_id)
        # Mock fallback nếu không có file BTC
        if phone == "0984726714":
            return {
                "found": True,
                "ambiguous": False,
                "customer_id": "C001",
                "name": "Hoa",
                "honorific": "chị",
                "phone": "0984726714",
                "orders": [],
                "sessions": []
            }
        return {"found": False}


class CatalogPricingTool:
    """Tra cứu sản phẩm, tồn kho và tính giá khuyến mãi chính xác theo ngày cuộc gọi"""
    def __init__(self):
        pass

    def search(self, query: str = None, category: str = None, sku: str = None, max_price_vnd: int = None, min_room_area_m2: float = None) -> Dict[str, Any]:
        if btc_mock:
            res = btc_mock.catalog_search(query=query, category=category, sku=sku, max_price_vnd=max_price_vnd, min_room_area_m2=min_room_area_m2)
            if not sku and (query or category):
                better = self._tolerant_search(query, category, max_price_vnd, min_room_area_m2)
                if better is not None and (better["total"] > res.get("total", 0)):
                    return better
            return res
        return {"items": [{"sku": "SKU-AP-Y", "name": "Máy lọc không khí AirPure Y", "list_price_vnd": 5200000}]}

    @staticmethod
    def _tolerant_search(query, category, max_price_vnd, min_room_area_m2) -> Optional[Dict[str, Any]]:
        """Mock BTC đòi MỌI từ của truy vấn nằm trong tên/hãng/danh mục nên "các mẫu máy lọc nước nào" trả 0 sản phẩm. So khớp lại bằng
        `src/catalog/textmatch.py` (bỏ từ đệm, không dấu), rồi lấy từng sản phẩm bằng đúng hàm của mock để giữ nguyên dạng kết quả."""
        from src.catalog.textmatch import filter_products, fold
        pool = [p for p in btc_mock.PRODUCTS if not (p.get("attributes") or {}).get("discontinued")]
        hay = lambda p: fold(f"{p['name']} {p['brand']} {p['category']} {p['sku']}")
        picked = filter_products(filter_products(pool, category, hay), query, hay)
        items: List[Dict[str, Any]] = []
        for p in picked:
            r = btc_mock.catalog_search(sku=p["sku"], max_price_vnd=max_price_vnd, min_room_area_m2=min_room_area_m2)
            items.extend(r.get("items", [])[:1])
        return {"items": items[:20], "total": len(items), "matched_by": "tolerant"}

    def inventory_check(self, sku: str, on: str = "2026-10-15") -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.inventory_check(sku=sku, on=on)
        return {"sku": sku, "in_stock": True, "qty": 15}

    def get_quote(self, sku: str, on: str = "2026-10-15", qty: int = 1, customer_phone: str = None, address: str = None, basket_skus: list = None) -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.pricing_get_quote(sku=sku, on=on, qty=qty, customer_phone=customer_phone, address=address, basket_skus=basket_skus)
        # Fallback
        price = 5200000 if sku == "SKU-AP-Y" else 4890000
        return {
            "sku": sku,
            "list_price_vnd": price,
            "final_price_vnd": price,
            "applied_promos": [{"promo_code": "GIFT-FILTER", "type": "gift"}]
        }


class OrderCallbackTool:
    """Tạo đơn hàng, cập nhật đổi trả, đặt lịch gọi lại, Handoff chuyển máy"""
    def __init__(self):
        pass

    def create_order(self, customer_phone: str, sku: str, qty: int = 1, price_vnd: int = None, promo_code: str = None, payment: str = "COD", address: str = None, on: str = "2026-10-15") -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.order_create(customer_phone=customer_phone, sku=sku, qty=qty, price_vnd=price_vnd, promo_code=promo_code, payment=payment, address=address, on=on)
        return {
            "order_id": f"OD{int(time.time()) % 1000000}",
            "status": "created",
            "total_vnd": price_vnd or 5200000,
            "needs_confirmation_call": False,
            "estimated_delivery": "2026-10-19"
        }

    def order_status(self, order_id: str = None, customer_phone: str = None) -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.order_status(order_id=order_id, customer_phone=customer_phone)
        return {"orders": []}

    def order_update(self, order_id: str, action: str, new_variant_sku: str = None, reason: str = None, on: str = "2026-10-15") -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.order_update(order_id=order_id, action=action, new_variant_sku=new_variant_sku, reason=reason, on=on)
        return {"order_id": order_id, "status": "updated"}

    def schedule_callback(self, customer_phone: str, callback_at: str, note: str = None) -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.schedule_callback(customer_phone=customer_phone, callback_at=callback_at, note=note)
        return {"callback_id": "CB0001", "customer_phone": customer_phone, "callback_at": callback_at}

    def handoff_transfer(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        if btc_mock:
            return btc_mock.handoff_transfer(brief=brief)
        return {"ticket_id": "HT0001", "status": "queued", "brief_ok": True}
