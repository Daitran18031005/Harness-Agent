"""Tính tiền một giỏ hàng ở MỘT nơi duy nhất, dùng cho (a) kết quả `pricing.get_quote` trả cho LLM, (b) tổng "đọc lại đơn" của order gate,
(c) chốt bất biến trước `order.create`: tổng báo cho khách == tổng backend sẽ ghi.

Hợp đồng tool: `pricing.get_quote` trả MỘT giá cho mỗi đơn vị; `order.create(sku, qty=n)` ghi `final_price_vnd × n` của lời báo giá KHÔNG có `basket_skus`
(schema BTC chỉ cho `basket_skus` ở get_quote; tầng tool của nhóm cũng không chuyển nó sang order.create). KM "máy thứ 2" làm hai máy cùng SKU (hoặc hai SKU khác nhau)
có giá khác giá đơn → `synced=False` và đơn KHÔNG được tạo (người gọi chuyển nhân viên).
Quy tắc đọc từ kết quả `pricing.get_quote` (loại KM `percent_second_item` trong promotions.json), không có tên sản phẩm/kịch bản nào ở đây."""
import re
from typing import Any, Callable, Dict, List, Optional

# shortcut: hạn mức lấy từ mock_tools.order_create (> 10.000.000 lỗi, > 2.000.000 cần gọi xác nhận) và chính sách VC-03; chưa có file dữ liệu, nâng lên khi BTC đưa vào config
COD_LIMIT_VND = 10_000_000
COD_CONFIRM_VND = 2_000_000


def _ok(q: Any) -> bool:
    return isinstance(q, dict) and "error" not in q and isinstance(q.get("final_price_vnd"), (int, float))


def price_basket(quote: Callable[[Dict[str, Any]], Dict[str, Any]], lines: List[Dict[str, Any]], on: str,
                 customer_phone: Optional[str] = None, address: Optional[str] = None) -> Dict[str, Any]:
    """`quote(args)` chạy `pricing.get_quote`; `lines` = [{"sku", "qty"}]. Mỗi dòng được báo giá với `basket_skus` = các SKU KHÁC trong giỏ (cách tool hiểu KM "máy thứ 2"
    giữa hai sản phẩm). Trả {lines, total_vnd (theo chính sách), order_total_vnd (backend sẽ ghi), synced} hoặc {error, sku}.
    Mỗi dòng: unit_prices_vnd, line_total_vnd, order_unit_vnd, order_line_total_vnd, synced, second_unit_promos."""
    skus = [str(l["sku"]) for l in lines]
    out: List[Dict[str, Any]] = []
    for ln in lines:
        sku, qty = str(ln["sku"]), max(1, int(ln.get("qty") or 1))
        others = list(dict.fromkeys(s for s in skus if s.upper() != sku.upper()))
        base = {"sku": sku, "on": on, "qty": qty, **({"customer_phone": customer_phone} if customer_phone else {}), **({"address": address} if address else {})}
        q = quote({**base, **({"basket_skus": others} if others else {})})          # giá THEO CHÍNH SÁCH (có KM giữa các SKU trong giỏ)
        if not _ok(q):
            return {"error": (q or {}).get("error", "quote_failed") if isinstance(q, dict) else "quote_failed", "sku": sku}
        qo = quote(base) if others else q                                             # giá backend SẼ GHI: order.create không nhận giỏ
        if not _ok(qo):
            return {"error": (qo or {}).get("error", "quote_failed") if isinstance(qo, dict) else "quote_failed", "sku": sku}
        unit, order_unit = int(q["final_price_vnd"]), int(qo["final_price_vnd"])
        units, promos = [unit] * qty, []
        # shortcut: chỉ qty == 2 cùng SKU, không giỏ khác: KM nói 'máy thứ 2' (cặp). Từ máy thứ 3 (và dòng có giỏ khác) KHÔNG áp giảm thêm — quy tắc 'máy thứ 4 có giảm không?' không rõ,
        # và KM-06 yêu cầu đơn ≥ 3 sản phẩm cùng loại do quản lý duyệt; đoán sẽ báo sai giá. Nâng lên khi BTC làm rõ.
        if qty == 2 and not others:
            second = quote({**base, "basket_skus": [sku]})
            if _ok(second) and int(second["final_price_vnd"]) < order_unit and any(p.get("type") == "percent_second_item" for p in second.get("applied_promos", [])):
                units, promos = [order_unit, int(second["final_price_vnd"])], second.get("applied_promos", [])
        out.append({"sku": sku, "qty": qty, "unit_prices_vnd": units, "line_total_vnd": sum(units), "order_unit_vnd": order_unit, "order_line_total_vnd": order_unit * qty,
                    "synced": sum(units) == order_unit * qty, "second_unit_promos": promos})
    return {"lines": out, "total_vnd": sum(l["line_total_vnd"] for l in out), "order_total_vnd": sum(l["order_line_total_vnd"] for l in out),
            "synced": all(l["synced"] for l in out)}


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
    số tiền 'giá × qty' hoặc `order_total_vnd` KHÁC `total_vnd` trong lời nói được thay bằng `total_vnd`. Chỉ áp cho MỘT SKU, qty ≥ 2, không giỏ khác (giá đơn vị của SKU khác không bị đụng)."""
    for c in calls:
        r, a = c.get("result") or {}, c.get("args") or {}
        qty = int(a.get("qty") or 1)
        if c.get("name") != "pricing.get_quote" or "error" in r or "total_vnd" not in r or qty < 2 or a.get("basket_skus"):
            continue
        right = int(r["total_vnd"])
        for wrong in {int(r.get("final_price_vnd") or 0) * qty, int(r.get("order_total_vnd") or 0)} - {right, 0}:
            text = replace_amount(text, wrong, right)
    return text
