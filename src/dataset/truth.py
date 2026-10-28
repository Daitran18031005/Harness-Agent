"""
Sự thật (truth) của dataset do CODE tính từ `mock_tools.py` của BTC — không để LLM bịa đáp án.
Mỗi hàm chạy trên trạng thái mock SẠCH khi cần mô phỏng đơn (để mã đơn đầu tiên = OD600001 như lúc chấm).
"""
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
_EVAL = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval")
if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)
import mock_tools as m  # noqa: E402

REF_DATE = "2026-10-15"
PRODUCTS = {p["sku"]: p for p in m.PRODUCTS}


def money(v: int) -> str:
    return f"{int(v):,}".replace(",", ".") + "đ"


def dmy(iso: str) -> str:
    y, mo, d = iso.split("-")
    return f"{int(d)}/{int(mo)}"


def add_days(iso: str, days: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.strptime(iso, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def product_name(sku: str) -> str:
    return PRODUCTS[m._parent(sku)[0]["sku"] if sku not in PRODUCTS else sku]["name"]


def quote(sku: str, on: str, phone: Optional[str] = None, address: Optional[str] = None, qty: int = 1) -> Dict[str, Any]:
    q = m.pricing_get_quote(sku, on, qty, phone, address)
    q.pop("_internal_price_floor_vnd", None)
    return q


def promo(code: str) -> Dict[str, Any]:
    return next(p for p in m.PROMOS if p["promo_code"] == code)


def promo_active(code: str, on: str) -> bool:
    p = promo(code)
    return p["start"] <= on <= p["end"]


def stock(sku: str, on: str) -> Dict[str, Any]:
    return m.inventory_check(sku, on)


def attr(sku: str, key: str) -> Any:
    return PRODUCTS[sku]["attributes"].get(key)


def fresh_orders():
    m._ORDERS.clear()
    m._CALLBACKS.clear()
    m._TICKETS.clear()
    m._ONCE_USED.clear()


def simulate_order(phone: str, sku: str, price: Optional[int], promo_code: Optional[str], payment: str, address: Optional[str], on: str,
                   qty: int = 1) -> Dict[str, Any]:
    """Tạo đơn trên trạng thái sạch → kết quả thật của `order.create` (mã đơn OD600001, ngày giao dự kiến…)."""
    fresh_orders()
    return m.order_create(phone, sku, qty, price, promo_code, payment, address, on)


def simulate_exchange(phone: str, sku: str, price: int, promo_code: Optional[str], address: str, created_on: str,
                      new_variant: str, on: str) -> Dict[str, Any]:
    fresh_orders()
    o = m.order_create(phone, sku, 1, price, promo_code, "COD", address, created_on)
    upd = m.order_update(o["order_id"], "exchange_size", new_variant, None, on)
    return {"order": o, "update": upd}
