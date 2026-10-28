"""
So khớp TỪ KHÓA tiếng Việt cho tìm sản phẩm — chịu được câu nói tự nhiên của khách ("có các mẫu máy lọc nước nào", "xe đẩy em bé",
"giày thể thao"). Mock BTC (`catalog_search`) đòi MỌI từ của câu truy vấn phải nằm trong tên/hãng/danh mục nên các câu trên trả 0 sản phẩm
(lỗi gặp trên UI khi khách hỏi "có các mẫu nào").

Quy tắc chung (không có tên sản phẩm/ngành hàng nào trong mã):
  1) bỏ từ đệm hỏi–đáp (các, những, mẫu, loại, nào, có, shop…) rồi so khớp KHÔNG DẤU;
  2) mọi từ còn lại đều khớp → kết quả chính xác;
  3) không sản phẩm nào khớp hết → lấy sản phẩm khớp NHIỀU từ nhất, với điều kiện khớp ≥ 60% số từ (tránh trả bừa cho câu không liên quan).
"""
import re
import unicodedata
from typing import Any, Callable, Dict, List

STOPWORDS = frozenset("""
cac nhung mau loai dong nao co khong gi nhe a ah oi dc duoc voi cua cho minh em anh chi co chu bac shop ben hoi xem tu van san pham ban dang
cai con chiec hang nua thi la va hay o day muon can tim mua lay giup toi nhu the thao nhom kieu mot vai may mat
""".split()) - {"may"}      # "máy" là danh từ loại (máy lọc, máy hút sữa) — giữ lại; "mát" (quạt mát) bỏ vì nhiễu


def fold(text: Any) -> str:
    s = unicodedata.normalize("NFD", str(text or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def terms(text: Any) -> List[str]:
    """Các từ mang nghĩa của câu truy vấn (đã bỏ dấu, bỏ từ đệm, bỏ trùng giữ thứ tự)."""
    out: List[str] = []
    for t in fold(text).split():
        if t not in STOPWORDS and t not in out:
            out.append(t)
    return out


def filter_products(products: List[Dict[str, Any]], text: Any, haystack: Callable[[Dict[str, Any]], str], min_fraction: float = 0.6) -> List[Dict[str, Any]]:
    """Sản phẩm khớp `text` theo quy tắc ở đầu file. `text` rỗng (hoặc chỉ có từ đệm) → không lọc."""
    toks = terms(text)
    if not toks:
        return list(products)
    hays = [(p, haystack(p)) for p in products]
    exact = [p for p, h in hays if all(t in h for t in toks)]
    if exact or len(toks) < 2:
        return exact
    scored = [(sum(t in h for t in toks) / len(toks), p) for p, h in hays]
    best = max((s for s, _ in scored), default=0.0)
    return [p for s, p in scored if s == best] if best >= min_fraction else []
