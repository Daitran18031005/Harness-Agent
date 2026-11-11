"""Tính tiền một giỏ hàng ở MỘT nơi duy nhất, dùng cho (a) kết quả `pricing.get_quote` trả cho LLM, (b) tổng "đọc lại đơn" của order gate,
(c) tham số `order.create`: tổng báo cho khách == tổng backend ghi.

Hợp đồng tool (BTC cập nhật 11/2026): giỏ từ 2 máy trở lên được báo giá TỪNG MÁY bằng `pricing.quote_order` (AIR-2ND-50 một máy/đơn, mỗi máy tối đa một KM không cộng dồn),
và `order.create(lines=[{sku, qty, price_vnd}])` ghi đúng các giá đó. Không có tên sản phẩm/kịch bản/luật KM nào ở đây: mọi con số lấy từ tool."""
import re
from typing import Any, Callable, Dict, List, Optional

# shortcut: hạn mức lấy từ mock_tools.order_create (> 10.000.000 lỗi, > 2.000.000 cần gọi xác nhận) và chính sách VC-03; chưa có file dữ liệu, nâng lên khi BTC đưa vào config
COD_LIMIT_VND = 10_000_000
COD_CONFIRM_VND = 2_000_000


def price_basket(call: Callable[[str, Dict[str, Any]], Dict[str, Any]], lines: List[Dict[str, Any]], on: str,
                 customer_phone: Optional[str] = None, address: Optional[str] = None) -> Dict[str, Any]:
    """`call(tool, args)` chạy tool giá; `lines` = [{"sku", "qty"}]. Một máy → `pricing.get_quote` (như cũ); từ 2 máy → `pricing.quote_order`.
    Trả {lines: [{sku, qty, unit_prices_vnd, line_total_vnd, second_unit_promos}], total_vnd} hoặc {error, sku}."""
    lines = [{"sku": str(l["sku"]), "qty": max(1, int(l.get("qty") or 1))} for l in lines]
    opt = {**({"customer_phone": customer_phone} if customer_phone else {}), **({"address": address} if address else {})}
    if len(lines) == 1 and lines[0]["qty"] == 1:
        q = call("pricing.get_quote", {"sku": lines[0]["sku"], "on": on, "qty": 1, **opt})
        ok = isinstance(q, dict) and "error" not in q and isinstance(q.get("final_price_vnd"), (int, float))
        units = [{"line": 0, "final_price_vnd": q["final_price_vnd"]}] if ok else None
    else:
        q = call("pricing.quote_order", {"lines": lines, "on": on, **opt})
        units = q.get("units") if isinstance(q, dict) and "error" not in q else None
    if not units:
        q = q if isinstance(q, dict) else {}
        return {"error": q.get("error", "quote_failed"), "sku": q.get("sku") or lines[0]["sku"]}
    out = []
    for i, ln in enumerate(lines):
        mine = [u for u in units if u["line"] == i]
        prices = [int(u["final_price_vnd"]) for u in mine]
        out.append({**ln, "unit_prices_vnd": prices, "line_total_vnd": sum(prices),
                    "second_unit_promos": [a for u in mine for a in u.get("applied_promos", []) if a.get("type") == "percent_second_item"]})
    return {"lines": out, "total_vnd": sum(l["line_total_vnd"] for l in out)}


def order_args(args: Dict[str, Any], pb: Dict[str, Any]) -> Dict[str, Any]:
    """Tham số `order.create` cho giỏ `pb`. Một SKU đồng giá → dạng cũ (sku, qty, price_vnd). Còn lại → `lines`, mỗi máy một dòng qty=1 (ghi chú của pricing.quote_order).
    `sku` (sản phẩm chính) được giữ ở mức đơn cho mã dùng sau đó; mock và script chấm lấy sku/qty/price_vnd của TỪNG DÒNG."""
    rest = {k: v for k, v in args.items() if k not in ("basket_skus", "lines")}
    units = [(l["sku"], p) for l in pb["lines"] for p in l["unit_prices_vnd"]]
    if len(pb["lines"]) == 1 and len({p for _, p in units}) == 1:
        return rest
    return {**{k: v for k, v in rest.items() if k not in ("qty", "price_vnd")}, "lines": [{"sku": s, "qty": 1, "price_vnd": p} for s, p in units]}


def cod_exceeds(total_vnd: int) -> bool:
    return int(total_vnd) > COD_LIMIT_VND


def cod_needs_confirmation(total_vnd: int) -> bool:
    return int(total_vnd) > COD_CONFIRM_VND


def replace_amount(text: str, old: int, new: int) -> str:
    """Thay mọi cách viết số tiền `old` ("15.380.000", "15,380,000", "15380000") bằng `new` kiểu "11.685.000"; đơn vị (đ, VNĐ…) đứng sau được giữ nguyên."""
    digits = str(int(old))
    groups = [digits[max(0, i - 3):i] for i in range(len(digits), 0, -3)][::-1]
    pat = r"(?<![\d.,])" + r"[.,]?".join(groups) + r"(?![\d]|[.,]\d)"
    return re.sub(pat, f"{int(new):,}".replace(",", "."), text)


def correct_basket_totals(text: str, calls: List[Dict[str, Any]]) -> str:
    """LLM hay tự nhân `final_price_vnd × qty` rồi nói tổng sai khi báo giá có KM 'máy thứ 2'. Kết quả get_quote của chính cuộc gọi mang `total_vnd` đúng (từ `price_basket`):
    số tiền 'giá × qty' KHÁC `total_vnd` trong lời nói được thay bằng `total_vnd`. Chỉ áp cho MỘT SKU, qty ≥ 2, không giỏ khác (giá đơn vị của SKU khác không bị đụng)."""
    for c in calls:
        r, a = c.get("result") or {}, c.get("args") or {}
        qty = int(a.get("qty") or 1)
        if c.get("name") != "pricing.get_quote" or "error" in r or "total_vnd" not in r or qty < 2 or a.get("basket_skus"):
            continue
        right = int(r["total_vnd"])
        for wrong in {int(r.get("final_price_vnd") or 0) * qty} - {right, 0}:
            text = replace_amount(text, wrong, right)
    return text
