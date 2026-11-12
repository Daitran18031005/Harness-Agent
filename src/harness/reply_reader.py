"""
ĐỌC LỜI KHÁCH BẰNG LLM (nguyên tắc người dùng chốt 2026-10-28): hiểu ngữ nghĩa lời khách (đồng ý / từ chối / xác nhận thông tin / tên / thanh toán)
là việc của LLM, trả về JSON có cấu trúc KÈM ĐOẠN TRÍCH NGUYÊN VĂN từ lời khách. Code chỉ KIỂM CHỨNG: đoạn trích phải thật sự nằm trong lời khách,
giá trị phải hợp lệ; thiếu bằng chứng thì bỏ. Máy trạng thái của order gate (khi nào được tạo đơn) vẫn là code.

RÀO CHẮN BẰNG CẤU TRÚC (không dựa vào prompt): một lần đọc sai "đồng ý" không đủ để tạo đơn. Ở lượt ngay sau khi đọc lại đơn, kết luận "agree" phải qua
một chốt nữa (`CONSENT_GUARD`): "verify" = lớp LLM thứ hai độc lập (prompt khác, không thấy kết quả lớp một) cũng phải xác nhận; "confidence" = độ tin cậy
lớp một ≥ ngưỡng; "none" = không chốt (chỉ để đo). Không qua chốt → coi như chưa đồng ý (đơn được đọc lại, KHÔNG tạo).

Không có LLM / LLM lỗi → `read_reply` trả None và gate rơi về bộ regex cũ trong order_gate.py (chỉ là đường dự phòng offline, luôn thiên về "chưa đồng ý").
"""
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.harness.fact_usage import fold

logger = logging.getLogger(__name__)

PAYMENTS = ("COD", "bank", "momo", "zalopay")
AFFIRMABLE = ("recipient_name", "recipient_phone", "address", "payment")
GUARDS = ("none", "confidence", "verify")
DEFAULT_GUARD = "verify"             # tạm thời: chốt an toàn nhất; chọn chính thức sau khi đo (scripts/eval_consent_guard.py)
CONFIDENCE_THRESHOLD = 0.85
NUM_WORDS = {1: "mot", 2: "hai", 3: "ba", 4: "bon", 5: "nam", 6: "sau", 7: "bay", 8: "tam", 9: "chin", 10: "muoi"}   # chữ số đã bỏ dấu (fold)

PROMPT = """Bạn là bộ ĐỌC HIỂU lời khách trong cuộc gọi bán hàng. Chỉ phân tích, không trả lời khách. Trả về DUY NHẤT một JSON object.

Ngữ cảnh: câu cuối của nhân viên, và các thông tin nhân viên đang chờ khách xác nhận/cung cấp. Lời khách là văn bản gõ/ASR, có thể viết thường, thiếu dấu, nói vòng.

JSON gồm các khóa:
- "stance": "agree" | "decline" | "other"
- "stance_quote": đoạn NGUYÊN VĂN trong lời khách làm bằng chứng cho stance (rỗng nếu stance = other)
- "confidence": số từ 0 đến 1 — mức chắc chắn của riêng "stance" (1 = không thể hiểu khác)
- "only_answers": true/false (định nghĩa bên dưới)
- "affirmed": danh sách các mục khách XÁC NHẬN là đúng, chọn trong ["recipient_name","recipient_phone","address","payment"]
- "affirmed_quote": đoạn nguyên văn làm bằng chứng cho affirmed (rỗng nếu affirmed rỗng)
- "recipient_name": tên NGƯỜI NHẬN HÀNG khách vừa nói (không phải tên sản phẩm/thương hiệu), hoặc null
- "name_quote": đoạn nguyên văn chứa tên đó, hoặc ""
- "qty": SỐ LƯỢNG (số nguyên) của sản phẩm khách đang đặt/chốt, nếu khách NÓI RÕ trong lời này (vd. "3 bộ", "5 món", "hai cái"); null nếu không nói
- "qty_quote": đoạn nguyên văn chứa số lượng đó, hoặc ""
- "address": địa chỉ NHẬN HÀNG khách vừa nói trong lời này (số nhà, đường, khu, phường/quận, tỉnh — kể cả khi viết thiếu dấu/thiếu chữ "số", "đường"), chép đúng như khách nói; null nếu không có hoặc chỉ là token dạng <ADDR_n>
- "address_quote": đoạn nguyên văn chứa địa chỉ đó, hoặc ""
- "product_sku": MÃ SKU của sản phẩm khách đang nói tới/chốt trong lời này, CHÉP ĐÚNG MỘT mã trong danh sách "Sản phẩm ứng viên" (danh sách có thể dư, gồm cả phụ kiện/combo; lời khách là ASR nên tên có thể bị nghe sai — chọn theo ý nghĩa và ngữ cảnh cuộc gọi, kể cả khi khách gọi tắt: "combo đó", "cái máy hôm trước", "bản Pro"). Phụ kiện/combo khác máy chính: "màng lọc của máy X" là màng lọc, không phải máy X. null nếu khách không nói tới sản phẩm nào, không chắc là mã nào, hay sản phẩm khách nói không có trong danh sách — đừng đoán theo âm gần giống
- "product_quote": đoạn nguyên văn trong lời khách chỉ ra sản phẩm đó, hoặc ""
- "extra_items": danh sách món KHÁC khách muốn mua THÊM trong CÙNG đơn, mỗi món {"name": tên món chép như khách nói, "qty": số nguyên, "quote": đoạn nguyên văn}; [] nếu không có
- "payment": "COD" | "bank" | "momo" | "zalopay" | null — hình thức thanh toán khách vừa CHỌN
- "payment_quote": đoạn nguyên văn chứa lựa chọn đó, hoặc ""
- "order_intent": "commit" | "other" — khách đang CAM KẾT mua/đặt thứ đang được bàn hay chưa
- "intent_quote": đoạn nguyên văn làm bằng chứng cho order_intent = commit (rỗng nếu other)
- "asks_question": true nếu khách đang hỏi điều gì mà nhân viên chưa trả lời
- "asks_price_promo": true nếu khách đang HỎI, chất vấn, đòi hoặc phản đối về giá/giảm giá/khuyến mãi/ưu đãi (kể cả nhắc mức giảm đã nghe trước đây) mà nhân viên chưa trả lời; chấp nhận một mức giá đã nêu thì không
- "price_promo_quote": đoạn nguyên văn trong lời khách làm bằng chứng (rỗng nếu false)
- "asks_transfer": true nếu khách YÊU CẦU NGAY BÂY GIỜ được nối máy/chuyển cuộc gọi/gặp nhân viên, quản lý hoặc bộ phận khác (vd. bộ phận khách hàng doanh nghiệp) xử lý thay trợ lý. Các việc sau KHÔNG phải yêu cầu chuyển máy (false): hẹn/đặt lịch GỌI LẠI sau; nhân viên gọi xác nhận đơn hay gọi báo trước khi giao; đổi địa chỉ/thông tin giao hàng; hỏi quy định thanh toán; mặc cả giá; nhờ kiểm tra sản phẩm/đơn hàng mà không đòi gặp người khác
- "transfer_quote": đoạn nguyên văn trong lời khách làm bằng chứng (rỗng nếu false)
- "claims_prior_contact": true nếu khách nói mình ĐÃ từng liên hệ/được tư vấn/trao đổi với cửa hàng trước thời điểm này (ở bất kỳ kênh nào)
- "prior_contact_quote": đoạn nguyên văn trong lời khách làm bằng chứng (rỗng nếu false)

NGUYÊN TẮC (áp dụng theo ý nghĩa, không theo từ ngữ cụ thể):
1. agree: người nghe không thể hiểu khác ngoài việc khách CHẤP NHẬN điều nhân viên vừa hỏi/đề nghị, một cách chủ động và không điều kiện. Âm thanh ậm ừ, tín hiệu "đang nghe/đang nghĩ", hay phản hồi chưa mang nội dung chấp nhận thì chưa phải chấp nhận.
2. Có điều kiện, câu hỏi, đổi ý, hay kèm yêu cầu mới thì không phải chấp nhận không điều kiện.
3. decline: khách không muốn tiếp tục mua, hoãn quyết định, hoặc thương lượng giá (theo định nghĩa mặc cả ở nguyên tắc 8). Khách chỉnh/sửa/phủ nhận MỘT THÔNG TIN cụ thể (số, tên, địa chỉ, sản phẩm) là đang cung cấp thông tin chính xác hơn, không phải từ chối: stance = other.
4. recipient_name: khi nhân viên vừa hỏi tên người nhận, một phản hồi ngắn đóng vai trò là tên người thì là tên, bất kể cách viết hoa/dấu. Danh xưng không thuộc về tên.
5. affirmed chỉ ghi mục khách xác nhận là ĐÚNG với thông tin đã có; thông tin khách mới đưa ra không nằm trong affirmed. Xác nhận bằng cách chỉ vào thứ đang dùng/đang nói tới (cùng đối tượng với thông tin nhân viên nêu) cũng là xác nhận.
6. only_answers = true khi lời khách chỉ nhằm đáp lại đúng điều nhân viên đang hỏi/chờ, dù đáp nhiều điều một lúc; false khi khách đưa thêm câu hỏi, thay đổi sản phẩm/số lượng, hoặc chuyển sang chuyện khác.
7. payment: chỉ điền khi khách đã LỰA CHỌN một hình thức; hỏi về khả năng hoặc chưa quyết thì null. Quy về hình thức phù hợp nhất theo cách trả tiền được mô tả.
8. order_intent = commit khi khách đã quyết định lấy/đặt thứ đang bàn (kể cả khi đó là câu đáp lại đề nghị của nhân viên). Chỉ tính quyết định MUA/ĐẶT một đơn MỚI: khách đồng ý ĐỔI size/màu, TRẢ hàng, hủy, bảo hành cho đơn ĐÃ mua, hay đồng ý hẹn gọi lại thì là other. Hỏi thông tin, so sánh, xem thử, cân nhắc, thương lượng chưa phải quyết định: other.
   Lời có động từ chốt mua (lấy, đặt, chốt, gửi cho, ship, lên đơn…) kèm sản phẩm/số lượng, hoặc kèm cách thanh toán/địa chỉ giao hàng, là commit KỂ CẢ khi khách nêu một con số giá: đó là khách nhắc lại giá; giá đúng hay sai do bước đọc lại đơn xử lý, không phải lý do hạ thành other.
   Mặc cả = hỏi hoặc đề nghị giá thấp hơn mà KHÔNG có lời chốt (hỏi "giá X được không", xin bớt, chê giá cao): order_intent other, asks_price_promo true. Chỉ hỏi giá: other.
   Vừa chốt vừa xin bớt trong cùng lời: order_intent commit VÀ asks_price_promo true (nhân viên trả lời chuyện giá trước, đơn chưa tạo cho tới khi khách xác nhận giá).
9. Không chắc thì chọn kết luận thận trọng (other/null/rỗng) và hạ "confidence" — đừng đoán.

Mọi *_quote PHẢI chép nguyên văn từ lời khách (không sửa, không dịch).

ĐỂ TRẢ LỜI NHANH: chỉ ghi các khóa có giá trị KHÁC mặc định; khóa vắng mặt được hiểu là mặc định (stance "other", order_intent "other", false, null, [] và "" cho mọi khóa còn lại).
Khi stance là agree/decline thì luôn ghi kèm "stance_quote" và "confidence". Không có gì khác mặc định thì trả {}."""

VERIFY_PROMPT = """Bạn là chốt kiểm tra độc lập trước khi tạo đơn hàng. Nhân viên đã đọc lại toàn bộ đơn và xin khách xác nhận. Bạn chỉ trả lời MỘT câu hỏi:
lời khách có phải là sự cho phép rõ ràng, chủ động, không điều kiện để đặt ĐÚNG đơn vừa đọc lại, ngay bây giờ hay không?
Chỉ trả "authorizes": true khi người nghe không thể hiểu khác. Mọi trường hợp mơ hồ, điều kiện, câu hỏi, sửa/đổi nội dung đơn, hoãn, hay phản hồi chưa mang nội dung chấp nhận đều là false.
Trả về DUY NHẤT JSON: {"authorizes": true|false, "quote": "<đoạn NGUYÊN VĂN trong lời khách làm bằng chứng, rỗng nếu false>"}"""


HANDOFF_PROMPT = """Bạn là chốt kiểm tra độc lập trước khi CHUYỂN MÁY cuộc gọi cho nhân viên/bộ phận khác. Bạn chỉ phân loại LỜI KHÁCH, không trả lời khách.
Hai loại ca chuyển máy, kiểm tra theo tiêu chí riêng:
A. "scope_safety" — việc khách hỏi/nêu nằm NGOÀI phạm vi tư vấn bán hàng của trợ lý và cần người có chuyên môn/thẩm quyền khác (sức khỏe, y tế, thuốc, bệnh lý; an toàn của người dùng, đặc biệt trẻ nhỏ; pháp lý; SỰ CỐ/khiếu nại về đơn đã đặt — đơn trễ so với thời gian hợp lý, sai, hỏng, mất, dựa cả vào "Dữ kiện hệ thống" nếu có, còn chỉ hỏi tình trạng đơn bình thường thì KHÔNG; yêu cầu liên quan dữ liệu cá nhân). Loại này KHÔNG cần khách yêu cầu chuyển máy; cần "category_quote" là đoạn NGUYÊN VĂN trong lời khách thể hiện việc đó. Chuyện giá, giảm giá, mặc cả, chê đắt, cân nhắc mua KHÔNG thuộc loại này.
B. Mọi trường hợp khác (kể cả thương lượng giá): chỉ được chuyển khi khách đã cho phép, với một trong hai căn cứ:
 - "asked": chính lời khách vừa nói là yêu cầu được nối máy/chuyển cuộc gọi cho người/bộ phận khác (nhân viên, quản lý, bộ phận có thẩm quyền) xử lý thay trợ lý — kể cả khi trong cùng câu khách còn nói chuyện mua hàng, số lượng, hóa đơn hay hợp đồng. Các việc sau KHÔNG phải yêu cầu chuyển máy: hẹn/đặt lịch GỌI LẠI sau; nhân viên gọi xác nhận đơn hay gọi báo trước khi giao; đổi địa chỉ/thông tin giao hàng; hỏi quy định thanh toán.
 - "accepted_offer": câu cuối của nhân viên có ĐỀ NGHỊ chuyển máy/nhờ người khác hỗ trợ, và lời khách là sự chấp nhận chủ động, không điều kiện đúng đề nghị đó.
 Khách than phiền, hỏi, thương lượng mà chưa tự yêu cầu/chấp nhận thì CHƯA phải là cho phép.
Mơ hồ thì chọn kết luận thận trọng (category "other", authorized false).
"category" và "authorized" là HAI câu hỏi độc lập: category "other" KHÔNG có nghĩa authorized false — ca loại B mà khách đã yêu cầu/chấp nhận thì authorized true.
Trả về DUY NHẤT JSON: {"basis": "asked"|"accepted_offer"|null, "quote": "<nguyên văn lời khách làm bằng chứng cho basis, rỗng nếu null>", "authorized": true|false, "category": "scope_safety"|"other", "category_quote": "<nguyên văn lời khách, rỗng nếu other>"}"""


CLOSING_PROMPT = """Bạn là chốt kiểm tra độc lập trước khi tạo đơn hàng ở CUỐI cuộc gọi, khi không còn lượt nào để hỏi lại khách. Dưới đây là TOÀN BỘ lời khách trong cuộc gọi, theo thứ tự.
Bạn chỉ trả lời MỘT câu hỏi: khách có yêu cầu rõ ràng, chủ động MUA/ĐẶT/LÊN một đơn MỚI ngay trong cuộc gọi này, và sau đó KHÔNG hoãn hay rút lại hay không?
Trả "orders_now": false khi khách bảo khoan/chưa/để sau/cân nhắc thêm/hỏi lại người nhà, chỉ hỏi giá hay thông tin, còn thương lượng, hoặc chỉ đồng ý ĐỔI/TRẢ/bảo hành một đơn đã mua. Mơ hồ thì false.
Trả về DUY NHẤT JSON: {"orders_now": true|false, "quote": "<đoạn NGUYÊN VĂN trong lời khách là yêu cầu đặt đơn, rỗng nếu false>"}"""


def authorize_closing(llm: Any, texts: List[str]) -> Dict[str, Any]:
    """Chốt cho LƯỢT CHỐT (tạo đơn không qua bước khách xác nhận): lớp LLM độc lập đọc toàn bộ lời khách của cuộc gọi, phải có trích dẫn nguyên văn.
    Không có LLM / lỗi / thiếu trích dẫn → không cho tạo đơn (TEST-198: khách nói "khoan chốt… vội" mà đơn vẫn bị tạo)."""
    out: Dict[str, Any] = {"authorized": False, "quote": "", "usage": {}}
    joined = "\n".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    if llm is None or not hasattr(llm, "complete_json") or not joined:
        return out
    try:
        raw, usage = llm.complete_json([{"role": "system", "content": CLOSING_PROMPT}, {"role": "user", "content": joined}])
    except Exception as e:
        logger.warning("[reply_reader] chốt lượt chốt lỗi (%s) — không tạo đơn", e)
        return out
    out["usage"] = usage or {}
    quote = _quoted(raw.get("quote"), joined) if isinstance(raw, dict) else ""
    if isinstance(raw, dict) and raw.get("orders_now") is True and quote:
        out.update(authorized=True, quote=quote)
    return out


def authorize_handoff(llm: Any, text: str, last_agent: str = "", facts: str = "") -> Dict[str, Any]:
    """Chốt cấu trúc cho `handoff.transfer`, tách theo LÝ DO: ca ngoài phạm vi/an toàn → cho chuyển ngay (chốt độc lập xác nhận khách thật sự thuộc loại này, kèm trích dẫn nguyên văn);
    ca còn lại (thương lượng giá…) → phải có khách yêu cầu hoặc chấp nhận đề nghị chuyển máy, kèm trích dẫn. Gọi theo yêu cầu (chỉ khi LLM chính định chuyển máy); lỗi/thiếu bằng chứng → không cho phép."""
    out: Dict[str, Any] = {"authorized": False, "basis": None, "category": "other", "quote": "", "usage": {}}
    if llm is None or not hasattr(llm, "complete_json"):
        return out
    try:
        raw, usage = llm.complete_json([{"role": "system", "content": HANDOFF_PROMPT},
                                        {"role": "user", "content": (f"Dữ kiện hệ thống: {facts}\n" if facts else "") + f"Câu cuối của nhân viên: {last_agent or '(chưa có)'}\n\nLời khách: {text}"}])
    except Exception as e:
        logger.warning("[reply_reader] chốt chuyển máy lỗi (%s) — không cho chuyển máy", e)
        return out
    out["usage"] = usage or {}
    if not isinstance(raw, dict):
        return out
    cq = _quoted(raw.get("category_quote"), text)
    if raw.get("category") == "scope_safety" and cq:
        return {**out, "authorized": True, "basis": "scope_safety", "category": "scope_safety", "quote": cq}
    quote = _quoted(raw.get("quote"), text)
    if raw.get("authorized") is True and raw.get("basis") in ("asked", "accepted_offer") and quote:
        out.update(authorized=True, basis=raw["basis"], quote=quote)
    return out


RECEIVED_PROMPT = """Đọc lời khách và cho biết khách nói đã NHẬN hàng được bao nhiêu NGÀY tính tới hôm nay (đổi tuần ra ngày). Chỉ tính khi khách nói rõ số ngày/tuần;
không nói thì days = null. Trả về DUY NHẤT JSON: {"days": số nguyên hoặc null, "quote": "đoạn NGUYÊN VĂN trong lời khách chứa con số đó"}"""


def _num_in(n: int, quote: str) -> bool:
    q = fold(quote)
    return bool(re.search(rf"(?<!\d){n}(?!\d)", quote) or (1 <= n <= 10 and re.search(rf"(?<!\w){NUM_WORDS[n]}(?!\w)", q)))


def days_since_received(llm: Any, text: str) -> Optional[int]:
    """Số ngày khách NÓI đã nhận hàng (LLM đọc, trích dẫn phải chứa con số — hoặc số tuần nếu khách nói theo tuần). Không chắc → None."""
    if llm is None or not hasattr(llm, "complete_json") or not (text or "").strip():
        return None
    try:
        raw, _ = llm.complete_json([{"role": "system", "content": RECEIVED_PROMPT}, {"role": "user", "content": f"Lời khách: {text}"}])
    except Exception as e:
        logger.warning("[reply_reader] không đọc được số ngày đã nhận hàng (%s)", e)
        return None
    d, q = (raw.get("days"), _quoted(raw.get("quote"), text)) if isinstance(raw, dict) else (None, "")
    if isinstance(d, int) and not isinstance(d, bool) and 0 <= d <= 400 and q and (_num_in(d, q) or (d % 7 == 0 and _num_in(d // 7, q))):
        return d
    return None


@dataclass
class ReplyReading:
    stance: str = "other"
    only_answers: bool = False
    affirmed: List[str] = field(default_factory=list)
    recipient_name: Optional[str] = None
    payment: Optional[str] = None
    qty: Optional[int] = None                                    # số lượng khách nói rõ (đã kiểm chứng: con số/chữ số nằm trong trích dẫn) — đơn code mở từng luôn là 1 (TEST-64/80)
    product_raw: Optional[str] = None                            # SKU LLM trả về TRƯỚC khi kiểm (để trace thấy bị loại hay không)
    candidates: List[str] = field(default_factory=list)          # SKU ứng viên đã đưa cho LLM
    product_sku: Optional[str] = None                            # SKU khách nói tới, ĐÚNG một mã trong danh sách ứng viên (đều lấy từ catalog), kèm trích dẫn nguyên văn — TEST-44 "combo đó"
    extra_items: List[Dict[str, Any]] = field(default_factory=list)   # món mua thêm cùng đơn [{name, qty}] (tên nằm trong trích dẫn) — TEST-153
    address: Optional[str] = None                                # địa chỉ nhận hàng khách vừa nói (đã kiểm chứng nguyên văn) — B1
    confidence: float = 0.0
    commits: bool = False                                        # order_intent = commit KÈM trích dẫn nguyên văn đã kiểm chứng
    asks_question: bool = False
    price_topic: bool = False                                    # khách đang hỏi/chất vấn về giá hoặc khuyến mãi (KÈM trích dẫn nguyên văn đã kiểm chứng)
    asks_transfer: bool = False                                 # khách yêu cầu nối máy/gặp người khác (KÈM trích dẫn) — C3: không để order gate chiếm lượt
    prior_contact: bool = False                                 # khách nói đã từng liên hệ trước đây (KÈM trích dẫn nguyên văn đã kiểm chứng)
    evidence: Dict[str, str] = field(default_factory=dict)       # khóa → đoạn trích ĐÃ kiểm chứng (để ghi trace)
    guard: Dict[str, Any] = field(default_factory=dict)          # kết quả chốt đồng ý: {"mode","raw_stance","passed",...}
    usage: List[Dict[str, Any]] = field(default_factory=list)    # usage từng lần gọi LLM (chi phí, latency_ms)

    @property
    def agrees(self) -> bool:
        return self.stance == "agree"

    @property
    def declines(self) -> bool:
        return self.stance == "decline"


def reading_trace_dict(r: Optional[ReplyReading], skipped: bool = False) -> Dict[str, Any]:
    """Bản ghi trace: nguồn hiểu lời khách ("skipped" = máy trạng thái bỏ qua; "regex_fallback" = không có LLM/LLM lỗi; "llm"), kết quả đã kiểm chứng, chốt đồng ý, chi phí/độ trễ."""
    if skipped:
        return {"source": "skipped"}
    if r is None:
        return {"source": "regex_fallback"}
    return {"source": "llm", "stance": r.stance, "confidence": r.confidence, "only_answers": r.only_answers, "affirmed": r.affirmed,
            "order_intent": "commit" if r.commits else "other", "asks_question": r.asks_question, "asks_price_promo": r.price_topic, "prior_contact": r.prior_contact, "recipient_name": r.recipient_name, "payment": r.payment, "product_sku": r.product_sku, "product_raw": r.product_raw, "product_quote": r.evidence.get("product"),
            "product_verified": r.product_sku is not None, "candidates": r.candidates, "address": bool(r.address), "evidence": r.evidence, "guard": r.guard or None,
            "llm_calls": len(r.usage), "vnd_cost": round(sum(float(u.get("vnd_cost", 0) or 0) for u in r.usage), 2),
            "latency_ms": sum(int(u.get("latency_ms", 0) or 0) for u in r.usage)}


def _quoted(quote: Any, text: str) -> str:
    """Đoạn trích hợp lệ = chuỗi không rỗng nằm nguyên văn (so không dấu, gộp khoảng trắng) trong lời khách; ngược lại ''."""
    q = re.sub(r"\s+", " ", fold(str(quote or ""))).strip()
    return str(quote).strip() if q and q in re.sub(r"\s+", " ", fold(text)) else ""


def product_candidates(text: str, catalog: List[Dict[str, Any]], seen: List[str] = (), limit: int = 8) -> List[Dict[str, str]]:
    """Ứng viên SKU cho bộ đọc LLM (ưu tiên ĐỦ, chấp nhận dư — LLM chọn, code chỉ kiểm): sản phẩm đã tra trong cuộc + SKU `product_mentions` khớp
    + mọi sản phẩm catalog có chung một từ tên "hiếm" (≤ 1/4 catalog, vd "airpure", "runlite") với các SKU đó → kéo theo phụ kiện/combo cùng họ.
    Tối đa `limit` mã (prompt ngắn → bộ đọc nhanh): đã tra + đã nhắc trước, rồi cùng họ trùng lời khách nhiều nhất (mỗi từ trùng nặng 1/số sản phẩm có từ đó)."""
    from src.channels.asr_entities import product_mentions
    by_sku = {p["sku"]: p for p in catalog if p.get("sku")}
    words = lambda p: {w for w in re.findall(r"\w+", fold(p.get("name") or "")) if len(w) >= 3 and not w.isdigit()}
    df: Dict[str, int] = {}
    for p in by_sku.values():
        for w in words(p):
            df[w] = df.get(w, 0) + 1
    base = [s for s in dict.fromkeys(list(seen) + [s for _, s, _ in product_mentions(text)]) if s in by_sku]
    rare = {w for s in base for w in words(by_sku[s]) if df[w] <= len(by_sku) // 4}
    said = set(re.findall(r"\w+", fold(text)))
    family = sorted((s for s, p in by_sku.items() if s not in base and words(p) & rare), key=lambda s: -sum(1 / df[w] for w in words(by_sku[s]) & said))   # từ trùng lời khách, từ HIẾM nặng hơn ("combo" > "không")
    return [{"sku": s, "name": by_sku[s]["name"]} for s in (base + family)[:limit]]


def exact_model_skus(text: str, catalog: List[Dict[str, Any]] = ()) -> List[str]:
    """SKU mà lời khách gọi ĐÚNG cụm hãng + mẫu (khớp tuyệt đối theo cụm từ, không khớp mờ) trong config/product_aliases.json.
    Bỏ alias chỉ có tên hãng (`alone`, mẫu rỗng): "phát" (Fatz), "hai pro" (HikePro) đều là hãng trơn → để bộ đọc LLM quyết định.
    Mơ hồ → bỏ: một sản phẩm KHÁC trong catalog có tên chứa cùng cụm đó và lời khách có từ riêng của tên sản phẩm kia
    ("màng lọc thay thế AirPure X" ⊃ "airpure x", "combo AirPure Y" ⊃ "airpure y") — khi đó bộ đọc chọn."""
    import json
    from src.channels.asr_entities import ALIAS_PATH, _tokens
    toks = [fold(t) for t in _tokens(text)]
    windows = {"".join(toks[i:i + n]) for i in range(len(toks)) for n in range(1, 9) if i + n <= len(toks)}
    with open(ALIAS_PATH, encoding="utf-8") as fh:
        products = json.load(fh)["products"]
    words = lambda name: {w for w in re.findall(r"\w+", fold(name or "")) if len(w) >= 3}
    names = {p["sku"]: p.get("name") or "" for p in catalog if p.get("sku")}
    out = []
    for sku, spec in products.items():
        hits = [fold(b + m).replace(" ", "") for b in spec.get("brand", []) for m in spec.get("model", []) if m.strip()]
        hits = [h for h in hits if h in windows]
        if not hits:
            continue
        own = words(names.get(sku))
        clash = any(o != sku and any(h in re.sub(r"\W", "", fold(n)) for h in hits) and (words(n) - own) & set(toks) for o, n in names.items())
        if not clash:
            out.append(sku)
    return out


def verify(raw: Dict[str, Any], text: str, candidates: Any = ()) -> ReplyReading:
    """Chỉ giữ phần của `raw` có bằng chứng nguyên văn trong `text`."""
    r = ReplyReading()
    stance = raw.get("stance")
    q = _quoted(raw.get("stance_quote"), text)
    if stance in ("agree", "decline") and q:
        r.stance, r.evidence["stance"] = stance, q
    c = raw.get("confidence")
    r.confidence = float(c) if isinstance(c, (int, float)) and not isinstance(c, bool) and 0 <= c <= 1 else 0.0
    r.only_answers = raw.get("only_answers") is True
    r.asks_question = raw.get("asks_question") is True
    q = _quoted(raw.get("price_promo_quote"), text)
    if raw.get("asks_price_promo") is True and q:
        r.price_topic, r.evidence["price_promo"] = True, q
    q = _quoted(raw.get("transfer_quote"), text)
    if raw.get("asks_transfer") is True and q:
        r.asks_transfer, r.evidence["transfer"] = True, q
    q = _quoted(raw.get("prior_contact_quote"), text)
    if raw.get("claims_prior_contact") is True and q:
        r.prior_contact, r.evidence["prior_contact"] = True, q
    q = _quoted(raw.get("intent_quote"), text)
    if raw.get("order_intent") == "commit" and q:
        r.commits, r.evidence["intent"] = True, q
    aff = [a for a in (raw.get("affirmed") or []) if a in AFFIRMABLE] if isinstance(raw.get("affirmed"), list) else []
    q = _quoted(raw.get("affirmed_quote"), text)
    if aff and q:
        r.affirmed, r.evidence["affirmed"] = aff, q
    name, q = raw.get("recipient_name"), _quoted(raw.get("name_quote"), text)
    if isinstance(name, str) and name.strip() and q and fold(name).strip() in fold(q):
        r.recipient_name, r.evidence["name"] = name.strip(), q
    qty, q = raw.get("qty"), _quoted(raw.get("qty_quote"), text)
    if isinstance(qty, int) and not isinstance(qty, bool) and 1 <= qty <= 50 and q and (
            re.search(rf"(?<!\d){qty}(?!\d)", q) or (qty <= 10 and re.search(rf"(?<!\w){NUM_WORDS[qty]}(?!\w)", fold(q)))):
        r.qty, r.evidence["qty"] = qty, q
    addr, q = raw.get("address"), _quoted(raw.get("address_quote"), text)
    if isinstance(addr, str) and addr.strip() and "<" not in addr and q and fold(addr).strip() in fold(q):
        r.address, r.evidence["address"] = addr.strip(), q
    pay, q = raw.get("payment"), _quoted(raw.get("payment_quote"), text)
    if pay in PAYMENTS and q:
        r.payment, r.evidence["payment"] = pay, q
    prod, q = raw.get("product_sku"), _quoted(raw.get("product_quote"), text)
    if isinstance(prod, str) and q and prod.strip() in {c.get("sku") for c in candidates or ()}:     # chỉ nhận mã nằm trong danh sách ứng viên (lấy từ catalog) — không để LLM bịa sản phẩm
        r.product_sku, r.evidence["product"] = prod.strip(), q
    for it in raw.get("extra_items") or [] if isinstance(raw.get("extra_items"), list) else []:
        q = _quoted(it.get("quote") if isinstance(it, dict) else None, text)
        name, n = (it.get("name"), it.get("qty")) if isinstance(it, dict) else (None, None)
        if isinstance(name, str) and name.strip() and q and fold(name).strip() in fold(q):
            r.extra_items.append({"name": name.strip(), "qty": n if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 50 else 1})
    return r


def _second_opinion(llm: Any, text: str, last_agent: str, usage: List[Dict[str, Any]]) -> bool:
    """Lớp độc lập: prompt khác, KHÔNG thấy kết quả lớp một. Lỗi/thiếu trích dẫn → False (không cho tạo đơn)."""
    try:
        raw, u = llm.complete_json([{"role": "system", "content": VERIFY_PROMPT},
                                    {"role": "user", "content": f"Câu cuối của nhân viên (đã đọc lại đơn): {last_agent}\n\nLời khách: {text}"}])
    except Exception as e:
        logger.warning("[reply_reader] chốt thứ hai lỗi (%s) — không cho đồng ý đi tiếp", e)
        return False
    usage.append(u or {})
    return isinstance(raw, dict) and raw.get("authorizes") is True and bool(_quoted(raw.get("quote"), text))


def apply_guard(r: ReplyReading, llm: Any, text: str, last_agent: str, mode: str) -> None:
    """Chốt đồng ý (xem docstring module): hạ "agree" về "other" nếu không qua chốt. Gọi khi đang ở bước ngay sau đọc lại đơn."""
    if r.stance != "agree" or mode == "none":
        return
    raw_conf = r.confidence
    passed = raw_conf >= CONFIDENCE_THRESHOLD if mode == "confidence" else _second_opinion(llm, text, last_agent, r.usage)
    r.guard = {"mode": mode, "raw_stance": "agree", "passed": passed, "confidence": raw_conf}
    if not passed:
        r.stance = "other"


def read_reply(llm: Any, text: str, last_agent: str = "", waiting: Optional[Dict[str, Any]] = None, guard: Optional[str] = None) -> Optional[ReplyReading]:
    """None nếu không có LLM / lỗi (caller dùng regex dự phòng). `text` nên là bản đã che PII (turn.llm_text).
    `guard` (mặc định env CONSENT_GUARD, rồi DEFAULT_GUARD) chỉ áp dụng khi `waiting['stage'] == 'readback'`."""
    if llm is None or not getattr(llm, "available", False) or not hasattr(llm, "complete_json") or not (text or "").strip():
        return None
    ctx = f"Câu cuối của nhân viên: {last_agent or '(chưa có)'}\nSản phẩm ứng viên: {[f"{c['sku']} — {c['name']}" for c in (waiting or {}).get('candidates') or []]}\nĐang chờ khách xác nhận: {(waiting or {}).get('to_confirm') or []}; đang chờ khách cung cấp: {(waiting or {}).get('missing') or []}; giai đoạn đơn: {(waiting or {}).get('stage') or 'chưa có đơn'}"
    try:
        raw, usage = llm.complete_json([{"role": "system", "content": PROMPT}, {"role": "user", "content": f"{ctx}\n\nLời khách: {text}"}])
    except Exception as e:                                     # LLMUnavailable, lỗi mạng… → dự phòng regex, không làm hỏng lượt
        logger.warning("[reply_reader] không đọc được bằng LLM (%s) — dùng regex dự phòng", e)
        return None
    if not isinstance(raw, dict):
        return None
    r = verify(raw, text, (waiting or {}).get('candidates') or ())
    r.usage.append(usage or {})
    r.product_raw = raw.get("product_sku") if isinstance(raw.get("product_sku"), str) else None
    r.candidates = [c.get("sku") for c in (waiting or {}).get("candidates") or []]
    mode = guard or os.environ.get("CONSENT_GUARD") or DEFAULT_GUARD
    if mode not in GUARDS:
        mode = DEFAULT_GUARD
    if (waiting or {}).get("stage") == "readback":
        apply_guard(r, llm, text, last_agent, mode)
    return r
