"""
LLM Client: Bộ não suy luận chính của Harness Orchestrator qua OpenAI function-calling.
LLM tự quyết định gọi tool nào (catalog.search/pricing.get_quote/inventory.check/
order.create/order.update/schedule.callback/handoff.transfer/search_policy) dựa trên
hội thoại thật — không dùng keyword đoán ý định khách hàng.
Fallback: thiếu OPENAI_API_KEY hoặc bất kỳ lỗi khởi tạo/runtime nào -> LLMUnavailable,
caller (HarnessOrchestrator) bắt và rơi về nhánh rule-based tối giản, không crash pipeline.
"""
import os
import re
import copy
import json
import hashlib
import time
import queue
import logging
import threading
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Callable, Tuple, Optional

from .cost_tracker import CostTracker
from .model_profiles import profile_for, forced_unsupported_params

logger = logging.getLogger("harness.llm")


# Lời AGENT hứa sẽ tra cứu mà chưa tra ("để em kiểm tra…", "em sẽ tìm…", "chờ em một chút"): dấu hiệu để nhắc model gọi tool. Soi lời của chính agent, không phải lời khách.
LLM_WS = os.environ.get("LLM_WS", "").strip().lower() in ("on", "1", "true")   # MẶC ĐỊNH TẮT (18/11): vòng LLM chính qua Responses API WebSocket (kết nối thường trực; đo thử: lượt 2 vòng bớt ~0,4 s)
SERVICE_TIER = os.environ.get("LLM_SERVICE_TIER", "fast").strip()     # MẶC ĐỊNH "fast" từ 18/11 (số nộp m1_final8); "" = tier tài khoản; model không nhận thì tham số tự bị bỏ. Đo 17/11: "fast" (= priority)
PARALLEL_REQUIRED_TOOLS = os.environ.get("PARALLEL_REQUIRED_TOOLS", "on").strip().lower() in ("on", "1", "true")   # MẶC ĐỊNH BẬT từ 18/11 (m1_final8): vòng đầu gửi song song thêm 1 yêu cầu tool_choice="required"; vòng thường không gọi tool mà lẽ ra bị nhắc → dùng ngay lời gọi tool của yêu cầu song song thay cho vòng nhắc (+1 lời gọi LLM mỗi lượt)
PROMPT_CACHE_ORDER = os.environ.get("PROMPT_CACHE_ORDER", "on").strip().lower() in ("on", "1", "true")   # MẶC ĐỊNH BẬT từ 18/11 (m1_final8): gửi prompt_cache_key theo system prompt + tính giá cache cho lời gọi JSON


def _cache_key(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Khóa định tuyến cache của OpenAI: các lời gọi cùng system prompt (phần cố định đứng đầu) dùng chung khóa → dễ trúng cùng máy đã cache tiền tố."""
    head = next((m.get("content") for m in messages if m.get("role") == "system"), None)
    return "h" + hashlib.sha1(head.encode("utf-8")).hexdigest()[:16] if isinstance(head, str) else None


_PROMISES_LOOKUP = re.compile(
    r"(?:để|xin phép|sẽ|đang|cho em|chờ em|đợi em)\s+(?:em\s+)?(?:kiểm tra|tra cứu|tra lại|tìm|xem lại|xem giúp|check)|chờ (?:em )?(?:một|1) (?:chút|lát)|vui lòng (?:chờ|đợi)"
    r"|(?:sẽ|để em|xin phép(?: em)?)\s+(?:tiến hành|lên đơn|tạo đơn|đặt đơn|chuyển (?:máy|cuộc gọi|thông tin|tiếp)|đặt lịch|hẹn (?:lịch|gọi)|cập nhật đơn|làm thủ tục|hủy đơn)"
    r"|đã\s+(?:lên đơn|tạo đơn|đặt đơn|chuyển (?:máy|thông tin)|đặt lịch|ghi nhận lịch|cập nhật đơn)", re.I)


class LLMUnavailable(Exception):
    pass


class LLMCancelled(BaseException):
    """Caller hủy lượt LLM đang chạy (vd code đã nhận lượt). BaseException: vòng lặp tool không được nuốt nó thành lỗi tool."""


class LLMRoundLimit(LLMUnavailable):
    """LLM vẫn đòi gọi tool sau số vòng tối đa (có thể bị loop). Tool đã chạy xong vẫn có hiệu lực — caller
    KHÔNG được chạy lại nhánh rule-based (tránh tạo đơn trùng)."""


def _resolve_tools_schema_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..", "BTC-Data-Vong1-TEAMS", "schemas", "tools.schema.json")),
        os.path.abspath(os.path.join(here, "..", "..", "..", "BTC-Data-Vong1-TEAMS", "schemas", "tools.schema.json")),
        os.path.abspath(os.path.join(os.getcwd(), "BTC-Data-Vong1-TEAMS", "schemas", "tools.schema.json")),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"tools.schema.json not found, tried: {candidates}")


def _parse_dsl_type(raw: str) -> Tuple[Dict[str, Any], bool]:
    """Chuyển micro-DSL của tools.schema.json ('string?', 'int', 'COD|bank|momo|zalopay',
    'array? (xét AIR-2ND-50)', 'HandoffBrief') sang JSON Schema cho OpenAI function-calling."""
    raw = re.sub(r"\s*\(.*?\)\s*$", "", raw.strip())  # bỏ chú thích "(...)"
    optional = raw.endswith("?")
    base = raw[:-1] if optional else raw

    if "|" in base:
        return {"type": "string", "enum": [v.strip() for v in base.split("|")]}, optional

    mapping = {"string": "string", "int": "integer", "boolean": "boolean", "date": "string", "datetime": "string"}
    if base in mapping:
        return {"type": mapping[base]}, optional
    if base == "array":
        return {"type": "array", "items": {"type": "string"}}, optional

    # Kiểu phức tạp (VD "HandoffBrief") -> object tự do, model tự điền theo mô tả.
    return {"type": "object", "description": f"{base} object"}, optional


def _to_openai_safe_name(name: str) -> str:
    """OpenAI function name chỉ chấp nhận [a-zA-Z0-9_-]+ — tên tool thật dùng '.'
    (VD 'pricing.get_quote') nên phải đổi sang '__' khi khai báo cho OpenAI, rồi đổi
    ngược lại ('__' -> '.') trước khi thực sự gọi tool/ghi log, để tool_calls trong
    trace vẫn đúng tên thật theo tools.schema.json."""
    return name.replace(".", "__")


def _from_openai_safe_name(safe_name: str) -> str:
    return safe_name.replace("__", ".")


def build_openai_tools(tools_schema_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = tools_schema_path or _resolve_tools_schema_path()
    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    openai_tools = []
    for tool in spec.get("tools", []):
        name = tool.get("name", "")
        if "input" not in tool or "/" in name or " " in name:
            continue  # bỏ entry không có input schema rõ ràng (VD "memory.read / memory.write")
        properties, required = {}, []
        for field_name, type_str in tool["input"].items():
            schema, optional = _parse_dsl_type(type_str)
            properties[field_name] = schema
            if not optional:
                required.append(field_name)
        openai_tools.append({
            "type": "function",
            "function": {
                "name": _to_openai_safe_name(name),
                "description": tool.get("description", ""),
                "parameters": {"type": "object", "properties": properties, "required": required}
            }
        })

    # Tool nội bộ (không thuộc schema BTC): LLM tự quyết định khi nào cần tra RAG chính
    # sách thật, thay cho orchestrator đoán trước bằng keyword.
    openai_tools.append({
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "Tra cứu chính sách công khai (đổi trả, bảo hành, vận chuyển, điều khoản chung của khuyến mãi, COD...) "
                "từ knowledge base thật, đã lọc theo ngày hiệu lực hiện tại. Luôn gọi tool này khi "
                "khách hỏi về chính sách — không tự suy diễn số liệu. KHÔNG dùng để hỏi khuyến mãi/quà/giảm giá/freeship "
                "đang áp dụng cho MỘT sản phẩm cụ thể: việc đó gọi pricing.get_quote (trả đúng KM còn hiệu lực hôm nay)."
            ) if os.environ.get("POLICY_TOOL_NO_PROMO", "").strip().lower() in ("on", "1", "true") else (
                "Tra cứu chính sách công khai (đổi trả, bảo hành, vận chuyển, khuyến mãi, COD...) "
                "từ knowledge base thật, đã lọc theo ngày hiệu lực hiện tại. Luôn gọi tool này khi "
                "khách hỏi về chính sách — không tự suy diễn số liệu."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Câu hỏi/chủ đề chính sách khách vừa nói"}},
                "required": ["query"]
            }
        }
    })
    openai_tools.append({
        "type": "function",
        "function": {
            "name": _to_openai_safe_name("product.shortlist"),
            "description": (
                "Chọn sản phẩm theo nhu cầu: chấm điểm mọi sản phẩm của danh mục bằng các ràng buộc khách đã nêu và trả danh sách xếp hạng "
                "(đã kèm SKU hợp lệ, lý do khớp/vi phạm, slot còn thiếu đáng hỏi). Gọi TRƯỚC khi tư vấn/đề xuất sản phẩm. Chỉ truyền slot khách "
                "ĐÃ nói; hệ thống tự thêm slot đã nhớ ở các cuộc trước."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Loại sản phẩm khách muốn (vd 'máy lọc không khí', 'giày', 'xe đẩy')"},
                    "query": {"type": "string", "description": "Từ khóa thêm (tên hãng/dòng) nếu khách nêu"},
                    "room_area_m2": {"type": "number", "description": "Diện tích phòng (m²) khách nêu"},
                    "has_children": {"type": "boolean", "description": "Nhà có trẻ nhỏ"},
                    "budget_vnd": {"type": "integer", "description": "Ngân sách khách nêu (VND)"},
                    "child_weight_kg": {"type": "number", "description": "Cân nặng của bé (kg)"},
                    "volume_ml": {"type": "integer", "description": "Dung tích mong muốn (ml)"},
                    "min_warranty_months": {"type": "integer", "description": "Bảo hành tối thiểu khách muốn (tháng)"},
                    "min_stages": {"type": "integer", "description": "Số cấp/lõi lọc tối thiểu"},
                    "material": {"type": "string", "description": "Chất liệu khách muốn"},
                    "min_return_days": {"type": "integer", "description": "Số ngày đổi trả tối thiểu"},
                    "top_k": {"type": "integer", "description": "Số sản phẩm trả về (mặc định 3)"}
                },
                "required": []
            }
        }
    })
    return openai_tools


def with_variant_enum(tools: List[Dict[str, Any]], variant_skus: List[str],
                       tool_names: Optional[set] = None) -> List[Dict[str, Any]]:
    """Tầng 1 phòng thủ SKU (Dynamic Tool Enum): trả về BẢN SAO tools schema, tiêm
    enum=variant_skus vào tham số 'sku'/'new_variant_sku' của các tool liên quan — ép LLM
    chỉ được chọn đúng chuỗi SKU/variant_sku THẬT đã biết trong catalog ngay từ đầu, thay vì
    tự ghép chuỗi (có thể sai thứ tự size/màu, sai hoa-thường, còn dấu...).
    tool_names (tên tool THẬT, có dấu '.', vd {'pricing.get_quote','inventory.check'}) giới
    hạn chỉ patch đúng các tool đó — KHÔNG patch 'catalog.search', vì tham số sku của nó dùng
    để tra cứu sản phẩm bất kỳ (kể cả sản phẩm khác), ép enum vào đó sẽ chặn nhầm khả năng
    tìm sản phẩm mới của LLM."""
    patched = copy.deepcopy(tools)
    safe_names = {_to_openai_safe_name(n) for n in tool_names} if tool_names is not None else None
    for tool in patched:
        fn = tool.get("function", {})
        if safe_names is not None and fn.get("name") not in safe_names:
            continue
        props = fn.get("parameters", {}).get("properties", {})
        for field_name in ("sku", "new_variant_sku"):
            if field_name in props:
                props[field_name]["enum"] = list(variant_skus)
    return patched

def _env_number(name: str, cast, default):
    """Đọc số từ biến môi trường; rỗng/sai định dạng -> default."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except ValueError:
        return default


def _is_transient(exc: BaseException) -> bool:
    """Lỗi mạng/timeout (thử lại được): OpenAI APIConnectionError (gồm APITimeoutError) và timeout/ngắt kết nối của httpx."""
    try:
        import httpx
        import openai
        if isinstance(exc, (openai.APIConnectionError, httpx.TimeoutException, httpx.TransportError, ConnectionError)):
            return True
        try:
            from websockets.exceptions import ConnectionClosed
            return isinstance(exc, ConnectionClosed)      # LLM_WS: kết nối WebSocket đứt → mở lại, thử lại vòng
        except Exception:
            return False
    except ImportError:
        return False


class LLMClient:
    def __init__(self, model: Optional[str] = None, temperature: Optional[float] = None, seed: Optional[int] = None,
                 max_output_tokens: Optional[int] = None, reasoning_effort: Optional[str] = None):
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.profile = profile_for(self.model)
        # Độ ổn định cho model suy luận: cố định seed + reasoning_effort (không dùng temperature).
        self.reasoning_effort = reasoning_effort or os.environ.get("LLM_REASONING_EFFORT", "").strip() or None
        self.max_tool_chars = _env_number("LLM_MAX_TOOL_CHARS", int, 6000)
        self.max_output_tokens = max_output_tokens if max_output_tokens is not None else _env_number("LLM_MAX_OUTPUT_TOKENS", int, None)
        # Tham số model không hỗ trợ: khai báo trước (LLM_UNSUPPORTED_PARAMS) + tự học khi API báo lỗi.
        self.dropped_params = set(forced_unsupported_params())
        self._token_param = self.profile.token_param
        self.temperature = temperature if temperature is not None else _env_number("LLM_TEMPERATURE", float, 0.0)
        self.seed = seed if seed is not None else _env_number("LLM_SEED", int, None)
        # Lượt đứng 68–128 s (CHECKING §11.94): mặc định của SDK là timeout 600 s. Timeout theo KHOẢNG LẶNG giữa 2 gói dữ liệu (stream vẫn chạy thì không bị cắt).
        self.timeout_s = _env_number("LLM_TIMEOUT_S", float, 20.0)
        self.api_retries = _env_number("LLM_API_RETRIES", int, 1)           # SDK tự thử lại trước khi có phản hồi (kết nối/429/5xx)
        self.stream_retries = _env_number("LLM_STREAM_RETRIES", int, 2)     # thử lại cả vòng stream khi đứt/đứng giữa chừng (vòng chưa chạy tool nên thử lại an toàn)
        # Hedged request (Dean & Barroso, "The Tail at Scale", CACM 2013): vòng stream chưa có gói đầu sau LLM_HEDGE_MS → gửi MỘT bản sao y hệt,
        # dùng bản nào có gói đầu trước, đóng bản kia. 0 = tắt. Bản thua vẫn tính tiền prompt (ước tính bằng prompt của bản thắng).
        self.hedge_ms = _env_number("LLM_HEDGE_MS", float, 0.0)
        self._last_round_hedged = False
        self._last_prompt_tokens = 0          # prompt tokens của vòng stream gần nhất: ước tính tiền của vòng bị hủy giữa chừng
        self.json_hedge_ms = _env_number("LLM_JSON_HEDGE_MS", float, 0.0)
        self.json_hedged_calls = 0
        self.available = False
        self._client = None
        self._tools: List[Dict[str, Any]] = []
        self.cost_tracker = CostTracker()

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.info("[LLM] OPENAI_API_KEY không được set — LLM reasoning DISABLED, dùng nhánh rule-based.")
            return
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key, timeout=self.timeout_s, max_retries=self.api_retries)
            self._tools = build_openai_tools()
            self.available = True
            logger.info("[LLM] OPENAI_API_KEY present — LLM reasoning ENABLED (model=%s)", self.model)
        except Exception as e:
            logger.warning("[LLM] không khởi tạo được OpenAI client (%s) — LLM reasoning DISABLED.", e)
            self.available = False

    def get_base_tools(self) -> List[Dict[str, Any]]:
        """Trả về tools schema cơ bản (chưa patch enum) — dùng để orchestrator tự xây dynamic
        tools theo ngữ cảnh sản phẩm đang biết (xem with_variant_enum())."""
        return self._tools

    def _tool_content(self, result: Any) -> str:
        """Nội dung gửi LLM cho 1 kết quả tool; cắt bớt khi quá dài (giới hạn kích thước prompt). Trace vẫn giữ nguyên bản."""
        content = json.dumps(result, ensure_ascii=False)
        if len(content) > self.max_tool_chars:
            content = content[:self.max_tool_chars] + '... [đã cắt bớt vì quá dài]'
        return content

    def _build_kwargs(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
                      stream: bool = True, json_mode: bool = False, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Dựng tham số gọi API, tự BỎ tham số model không hỗ trợ (hồ sơ model + tham số đã học từ lỗi)."""
        kwargs: Dict[str, Any] = {"model": self.model, "messages": messages}
        if stream:
            kwargs["stream"] = True
            if "stream_options" not in self.dropped_params:
                kwargs["stream_options"] = {"include_usage": True}
        if json_mode and "response_format" not in self.dropped_params:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools
        if SERVICE_TIER and "service_tier" not in self.dropped_params:
            kwargs["service_tier"] = SERVICE_TIER        # LLM_SERVICE_TIER=fast: Fast mode; sổ chi phí dùng bảng giá "fast" trong config/pricing.yaml
        if self.temperature is not None and self.profile.supports_temperature and "temperature" not in self.dropped_params:
            kwargs["temperature"] = self.temperature
        if self.seed is not None and self.profile.supports_seed and "seed" not in self.dropped_params:
            kwargs["seed"] = self.seed
        if self.reasoning_effort and self.profile.is_reasoning and "reasoning_effort" not in self.dropped_params:
            kwargs["reasoning_effort"] = self.reasoning_effort
        if PROMPT_CACHE_ORDER and "prompt_cache_key" not in self.dropped_params and _cache_key(messages):
            kwargs["prompt_cache_key"] = _cache_key(messages)
        caps = [m for m in (self.max_output_tokens, max_tokens) if m is not None]
        if caps:
            kwargs[self._token_param] = min(caps)
        return kwargs

    @staticmethod
    def _unsupported_param(exc: Exception) -> Optional[str]:
        """Tên tham số mà API từ chối ('Unsupported parameter/value: temperature'), hoặc None nếu lỗi khác."""
        message = str(exc)
        if "unsupported" not in message.lower() and "not supported" not in message.lower():
            return None
        param = getattr(exc, "param", None)
        if not param:
            body = getattr(exc, "body", None)
            if isinstance(body, dict):
                param = (body.get("error") or body).get("param")
        if not param:
            m = re.search(r"['\"`]([a-z_]+)['\"`]", message)
            param = m.group(1) if m else None
        return param

    def _create_stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        return self._create(messages, tools, stream=True)

    def _create(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], stream: bool = True, json_mode: bool = False,
                max_tokens: Optional[int] = None):
        """Gọi API; nếu API từ chối 1 tham số thì bỏ tham số đó và thử lại (tối đa 4 lần)."""
        for _ in range(4):
            self.cost_tracker.check_cap()                          # trần chi phí cứng: dừng TRƯỚC khi gọi API (không bao giờ vượt quá một vòng)
            kwargs = self._build_kwargs(messages, tools, stream=stream, json_mode=json_mode, max_tokens=max_tokens)
            try:
                return self._client.chat.completions.create(**kwargs)
            except Exception as e:
                param = self._unsupported_param(e)
                if param == "max_tokens" and self._token_param == "max_tokens":
                    self._token_param = "max_completion_tokens"
                    logger.warning("[LLM] model %s không nhận max_tokens -> dùng max_completion_tokens", self.model)
                    continue
                if param in kwargs and param not in ("model", "messages", "stream") and param not in self.dropped_params:
                    self.dropped_params.add(param)
                    logger.warning("[LLM] model %s không hỗ trợ tham số '%s' -> bỏ và thử lại", self.model, param)
                    continue
                raise
        raise LLMUnavailable("Không gọi được API sau khi bỏ các tham số không được hỗ trợ.")

    def _create_json_hedged(self, messages: List[Dict[str, Any]], max_tokens: Optional[int] = None):
        """Lời gọi JSON (bộ đọc, chốt…) có hedging: chưa xong sau LLM_JSON_HEDGE_MS → gửi MỘT bản sao, lấy bản xong trước (Dean & Barroso 2013).
        Đo 2026-11-13: một lần đọc có p50 1,8 s nhưng p95 6,2 s — đuôi do phía API, không do nội dung. Bản thua chạy nốt (lời gọi non-stream
        không hủy được) và được cộng tiền vào tổng khi xong."""
        if not self.json_hedge_ms or self.json_hedge_ms <= 0:
            return self._create(messages, [], stream=False, json_mode=True, max_tokens=max_tokens)
        results: "queue.Queue" = queue.Queue()
        state = {"taken": False}
        lock = threading.Lock()

        def run() -> None:
            try:
                resp, err = self._create(messages, [], stream=False, json_mode=True, max_tokens=max_tokens), None
            except BaseException as e:
                resp, err = None, e
            with lock:
                first = not state["taken"] and err is None
                if first:
                    state["taken"] = True
            if first or err is not None:
                results.put((resp, err))
            elif resp is not None:                   # bản thua đã xong: cộng tiền thật của nó vào tổng (trần cứng vẫn thấy)
                u = getattr(resp, "usage", None)
                in_p, out_p, _ = self.cost_tracker.price_for(self.model)
                self.cost_tracker.add_external_cost(((getattr(u, "prompt_tokens", 0) or 0) * in_p + (getattr(u, "completion_tokens", 0) or 0) * out_p) / 1e6)

        threading.Thread(target=run, daemon=True).start()
        launched = 1
        try:
            resp, err = results.get(timeout=self.json_hedge_ms / 1000.0)
        except queue.Empty:
            threading.Thread(target=run, daemon=True).start()
            launched = 2
            resp, err = results.get()
        if err is not None and launched == 2:         # bản đầu lỗi → chờ bản kia
            resp, err = results.get()
        elif err is not None:
            raise err
        if err is not None:
            raise err
        self.json_hedged_calls += launched - 1
        return resp

    def complete_json(self, messages: List[Dict[str, Any]], max_tokens: Optional[int] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """1 lần gọi KHÔNG tool, đầu ra JSON object (dùng cho bộ trích bộ nhớ). Trả về (dict đã parse, chi phí/usage).
        Lỗi mạng/JSON hỏng -> ném LLMUnavailable (caller bỏ qua phần trích LLM, không crash)."""
        if not self.available:
            raise LLMUnavailable("LLM client không khả dụng (thiếu OPENAI_API_KEY hoặc lỗi khởi tạo).")
        t0 = time.perf_counter()
        try:
            response = self._create_json_hedged(messages, max_tokens)
            usage = getattr(response, "usage", None)
            prompt_t = getattr(usage, "prompt_tokens", 0) or 0
            completion_t = getattr(usage, "completion_tokens", 0) or 0
            details = getattr(usage, "completion_tokens_details", None)
            pdet = getattr(usage, "prompt_tokens_details", None)
            cached_t = (getattr(pdet, "cached_tokens", 0) or 0) if pdet else 0
            cost = self.cost_tracker.record_turn(self.model, prompt_t, completion_t, cached_tokens=cached_t if PROMPT_CACHE_ORDER else 0)   # đã trả tiền: ghi TRƯỚC khi phân tích (JSON hỏng vẫn tốn tiền)
            cost["prompt_tokens"], cost["cached_tokens"] = prompt_t, cached_t
            if getattr(response.choices[0], "finish_reason", None) == "length":      # chạm max_tokens: đầu ra bị cắt → coi như không đọc được, không đoán phần thiếu
                raise LLMUnavailable("complete_json: đầu ra bị cắt ở max_tokens")
            content = response.choices[0].message.content or "{}"
            data = json.loads(content)
        except LLMUnavailable:
            raise
        except Exception as e:
            raise LLMUnavailable(f"complete_json lỗi: {e}")
        if not isinstance(data, dict):
            raise LLMUnavailable("complete_json: đầu ra không phải JSON object")
        cost["llm_calls"] = 1
        cost["reasoning_tokens"] = (getattr(details, "reasoning_tokens", 0) or 0) if details else 0
        cost["latency_ms"] = int(round((time.perf_counter() - t0) * 1000))
        return data, cost

    def _submit_required(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """PARALLEL_REQUIRED_TOOLS: gửi song song một yêu cầu bắt buộc gọi tool (không stream) với đúng prompt của vòng đầu. Chi phí ghi vào sổ khi xong, dùng hay không."""
        if not hasattr(self, "_required_pool"):
            self._required_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="required-tools")
        kwargs = {**self._build_kwargs(list(messages), tools, stream=False), "tool_choice": "required"}

        def call():
            resp = self._client.chat.completions.create(**kwargs)
            u = getattr(resp, "usage", None)
            if u is not None:
                det = getattr(u, "prompt_tokens_details", None)
                pt, ct = getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0
                cached = min(pt, (getattr(det, "cached_tokens", 0) or 0) if det else 0)
                in_p, out_p, _ = self.cost_tracker.price_for(self.model)
                self.cost_tracker.add_external_cost(((pt - cached) * in_p + cached * in_p / 2 + ct * out_p) / 1e6)   # ghi vĩnh viễn (ngoài sổ của lượt); giá cache ước = 1/2 giá vào
            return resp
        return self._required_pool.submit(call)

    @staticmethod
    def _required_calls(future) -> List[Dict[str, Any]]:
        """Lời gọi tool của yêu cầu song song, cùng dạng _stream_round trả về; lỗi/không có → [] (khi đó nhắc như cũ)."""
        try:
            msg = future.result(timeout=30).choices[0].message
        except Exception:
            return []
        return [{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments or ""} for tc in (getattr(msg, "tool_calls", None) or [])]

    def _stream_round(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], cancel: Optional[threading.Event] = None):
        """`_stream_round_once` + thử lại khi timeout/đứt kết nối (bỏ phần đã nhận dở: tool chỉ chạy SAU khi vòng đọc xong). Lỗi khác, kể cả trần chi phí, ném ngay."""
        for attempt in range(self.stream_retries + 1):
            try:
                return self._stream_round_once(messages, tools, cancel)
            except Exception as e:
                if attempt >= self.stream_retries or not _is_transient(e):
                    raise
                logger.warning("[LLM] vòng stream lỗi mạng/timeout (%s) — thử lại %d/%d", e, attempt + 1, self.stream_retries)
                time.sleep(0.5 * (attempt + 1))

    def _open_stream(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """(iterator các chunk, có gửi bản sao hay không). Hedging chỉ chờ GÓI ĐẦU: sau đó bản thắng stream bình thường."""
        if not self.hedge_ms or self.hedge_ms <= 0:
            return self._create_stream(messages, tools), False
        results: "queue.Queue" = queue.Queue()

        def start(tag: int) -> None:
            try:
                stream = self._create_stream(messages, tools)
                it = iter(stream)
                first = next(it, None)
                results.put((tag, stream, it, first, None))
            except BaseException as e:          # kể cả BudgetExceeded: đưa về luồng chính
                results.put((tag, None, None, None, e))

        threading.Thread(target=start, args=(0,), daemon=True).start()
        launched = 1
        try:
            got = results.get(timeout=self.hedge_ms / 1000.0)
        except queue.Empty:
            threading.Thread(target=start, args=(1,), daemon=True).start()
            launched = 2
            got = results.get()
        pending = launched - 1
        while got[4] is not None and pending:        # bản về trước lỗi mà còn bản kia đang chạy → chờ bản kia
            got = results.get()
            pending -= 1
        if got[4] is not None:
            raise got[4]
        if pending:                                   # bản thua: đóng ngay khi nó trả gói đầu (không đọc tiếp, không chặn luồng chính)
            def close_loser() -> None:
                loser = results.get()
                try:
                    if loser[1] is not None:
                        loser[1].close()
                except Exception:
                    pass
            threading.Thread(target=close_loser, daemon=True).start()
        _, _, it, first, _ = got

        def chain():
            if first is not None:
                yield first
            yield from it
        return chain(), launched == 2

    @staticmethod
    def _to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Tin nhắn Chat Completions → input item của Responses API (vai trò giữ nguyên; tool_calls → function_call; tool → function_call_output)."""
        items: List[Dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "tool":
                items.append({"type": "function_call_output", "call_id": m.get("tool_call_id"), "output": m.get("content") or ""})
                continue
            if m.get("content"):
                items.append({"role": role, "content": m["content"]})
            for tc in (m.get("tool_calls") or []):
                fn = tc.get("function") or {}
                items.append({"type": "function_call", "call_id": tc.get("id"), "name": fn.get("name"), "arguments": fn.get("arguments") or ""})
        return items

    def _ws_conn(self):
        if getattr(self, "_ws", None) is None:
            self._ws_mgr = self._client.responses.connect()
            self._ws = self._ws_mgr.__enter__()
        return self._ws

    def _ws_drop(self) -> None:
        try:
            self._ws_mgr.__exit__(None, None, None)
        except Exception:
            pass
        self._ws = None

    def _ws_round_once(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], cancel: Optional[threading.Event] = None):
        """LLM_WS: một vòng qua Responses API trên WebSocket thường trực; gửi đủ ngữ cảnh mỗi vòng (store=false, không dùng previous_response_id
        nên không phụ thuộc trạng thái kết nối), trả về cùng dạng `_stream_round_once`. Lỗi kết nối → bỏ kết nối, `_stream_round` thử lại (kết nối mới)."""
        kw = self._build_kwargs(messages, tools, stream=False)
        body: Dict[str, Any] = {"model": kw["model"], "input": self._to_responses_input(messages), "store": False}
        if tools:
            body["tools"] = [{"type": "function", "name": t["function"]["name"], "description": t["function"].get("description", ""),
                              "parameters": t["function"].get("parameters", {})} for t in tools]
        for k in ("service_tier", "temperature", "prompt_cache_key"):
            if k in kw:
                body[k] = kw[k]
        cap = kw.get(self._token_param)
        if cap:
            body["max_output_tokens"] = cap
        if "reasoning_effort" in kw:
            body["reasoning"] = {"effort": kw["reasoning_effort"]}
        if not hasattr(self, "_ws_lock"):
            self._ws_lock = threading.Lock()
        text_parts: List[str] = []
        first_token_at = None
        cancelled = False
        with self._ws_lock:
            conn = self._ws_conn()
            try:
                conn.response.create(**body)
                done = None
                for ev in conn:
                    if cancel is not None and cancel.is_set():
                        cancelled = True                     # đọc tiếp tới hết (kết nối dùng lại phải sạch), không lấy kết quả
                    t = ev.type
                    if t == "response.output_text.delta" and not cancelled:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        text_parts.append(ev.delta)
                    elif t == "response.completed":
                        done = ev.response
                        break
                    elif t in ("response.failed", "response.incomplete", "error"):
                        raise RuntimeError(f"WebSocket round {t}: {ev.to_json()[:300]}")
            except Exception:
                self._ws_drop()
                raise
        if cancelled:
            raise LLMCancelled()
        self._last_service_tier = getattr(done, "service_tier", None)
        u = getattr(done, "usage", None)
        usage = None
        if u is not None:
            det = getattr(u, "input_tokens_details", None)
            out_det = getattr(u, "output_tokens_details", None)
            usage = SimpleNamespace(prompt_tokens=getattr(u, "input_tokens", 0) or 0, completion_tokens=getattr(u, "output_tokens", 0) or 0,
                                    prompt_tokens_details=SimpleNamespace(cached_tokens=(getattr(det, "cached_tokens", 0) or 0) if det else 0),
                                    completion_tokens_details=SimpleNamespace(reasoning_tokens=(getattr(out_det, "reasoning_tokens", 0) or 0) if out_det else 0))
        calls = [{"id": o.call_id, "name": o.name, "arguments": o.arguments or ""} for o in (getattr(done, "output", None) or []) if getattr(o, "type", "") == "function_call"]
        self._last_round_hedged = False
        return "".join(text_parts), calls, usage, first_token_at

    def _stream_round_once(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], cancel: Optional[threading.Event] = None):
        """1 vòng gọi API ở chế độ stream: gom text + tool_call từ các delta; trả về
        (text, tool_calls[{id,name,arguments}], usage, thời điểm perf_counter của token text đầu tiên)."""
        if LLM_WS:
            return self._ws_round_once(messages, tools, cancel)
        text_parts: List[str] = []
        calls: Dict[int, Dict[str, str]] = {}
        usage = None
        first_token_at = None
        chunks, self._last_round_hedged = self._open_stream(messages, tools)
        for chunk in chunks:
            if cancel is not None and cancel.is_set():          # caller đã nhận lượt: đóng stream, ghi ước tính tiền prompt đã xử lý (vòng dở không có usage)
                try:
                    getattr(chunks, "close", lambda: None)()
                except Exception:
                    pass
                if self._last_prompt_tokens:
                    self.cost_tracker.note_round(self.model, self._last_prompt_tokens, 0)
                raise LLMCancelled()
            self._last_service_tier = getattr(chunk, "service_tier", None) or getattr(self, "_last_service_tier", None)
            chunk_usage = getattr(chunk, "usage", None)
            if chunk_usage is not None:
                usage = chunk_usage
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            if getattr(delta, "content", None):
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                text_parts.append(delta.content)
            for tcd in (getattr(delta, "tool_calls", None) or []):
                slot = calls.setdefault(tcd.index, {"id": "", "name": "", "arguments": ""})
                if getattr(tcd, "id", None):
                    slot["id"] = tcd.id
                fn = getattr(tcd, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        slot["name"] += fn.name
                    if getattr(fn, "arguments", None):
                        slot["arguments"] += fn.arguments
        return "".join(text_parts), [calls[i] for i in sorted(calls)], usage, first_token_at

    def chat_with_tools(self, messages: List[Dict[str, Any]], tool_executor: Callable[[str, Dict[str, Any]], Tuple[Any, Dict[str, Any]]],
                         max_rounds: int = 6, tools_override: Optional[List[Dict[str, Any]]] = None,
                         timing: Optional[Dict[str, Any]] = None, expect_tools: bool = True, parallel_tools: frozenset = frozenset(),
                         cancel: Optional[threading.Event] = None) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        try:
            return self._chat_with_tools(messages, tool_executor, max_rounds, tools_override, timing, expect_tools, parallel_tools, cancel)
        except BaseException:               # kể cả BudgetExceeded: các vòng đã trả tiền phải nằm trong tổng chi phí
            self.cost_tracker.commit_inflight()
            raise

    def _chat_with_tools(self, messages: List[Dict[str, Any]], tool_executor: Callable[[str, Dict[str, Any]], Tuple[Any, Dict[str, Any]]],
                         max_rounds: int, tools_override: Optional[List[Dict[str, Any]]], timing: Optional[Dict[str, Any]],
                         expect_tools: bool = True, parallel_tools: frozenset = frozenset(),
                         cancel: Optional[threading.Event] = None) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        """Chạy vòng lặp function-calling tới khi LLM trả lời bằng text (không còn tool_call).
        tool_executor(name, args) -> (result, executed_args): executed_args là tham số THỰC SỰ đã
        chạy (sau khi orchestrator tiêm 'on', sửa SKU...) — đó là thứ được ghi vào trace (N3).
        tools_override cho phép orchestrator tiêm tools schema đã patch enum (Tầng 1 phòng thủ SKU).
        timing (dict, tùy chọn) được điền số đo THẬT bằng perf_counter: ttft_ms = từ lúc bắt đầu
        tới token text đầu tiên của vòng trả lời cuối (stream), total_ms, llm_calls (số vòng gọi API)."""
        if not self.available:
            raise LLMUnavailable("LLM client không khả dụng (thiếu OPENAI_API_KEY hoặc lỗi khởi tạo).")

        t0 = time.perf_counter()
        working_messages = list(messages)
        tool_calls_log: List[Dict[str, Any]] = []
        usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0}
        active_tools = tools_override if tools_override is not None else self._tools
        nudged_once = False
        hedged_rounds = 0
        api_calls = 0
        round_ms: List[int] = []          # thời gian từng vòng gọi LLM (đến hết stream của vòng đó)
        tool_ms = 0.0                      # tổng thời gian chạy tool giữa các vòng

        for _ in range(max_rounds):
            round_start = time.perf_counter()
            round_tools = active_tools() if callable(active_tools) else active_tools      # callable: dựng lại schema mỗi vòng (sản phẩm đang bàn có thể đổi giữa lượt)
            if cancel is not None and cancel.is_set():
                raise LLMCancelled()
            required_future = self._submit_required(working_messages, round_tools) if (PARALLEL_REQUIRED_TOOLS and api_calls == 0 and round_tools) else None
            text, tool_calls, usage, first_token_at = self._stream_round(working_messages, round_tools, *([cancel] if cancel is not None else []))
            round_ms.append(int(round((time.perf_counter() - round_start) * 1000)))
            api_calls += 1
            if usage is not None:
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                usage_totals["cached_tokens"] += (getattr(prompt_details, "cached_tokens", 0) or 0) if prompt_details else 0
                usage_totals["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
                self._last_prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                usage_totals["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
                self.cost_tracker.note_round(self.model, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0,
                                             (getattr(prompt_details, "cached_tokens", 0) or 0) if prompt_details else 0)
                details = getattr(usage, "completion_tokens_details", None)
                usage_totals["reasoning_tokens"] += (getattr(details, "reasoning_tokens", 0) or 0) if details else 0
                if self._last_round_hedged:           # bản sao bị đóng vẫn đã xử lý prompt → tính tiền prompt như bản thắng (ước tính bảo thủ)
                    hedged_rounds += 1
                    loser_prompt = getattr(usage, "prompt_tokens", 0) or 0
                    loser_cached = (getattr(prompt_details, "cached_tokens", 0) or 0) if prompt_details else 0
                    usage_totals["prompt_tokens"] += loser_prompt
                    usage_totals["cached_tokens"] += loser_cached
                    self.cost_tracker.note_round(self.model, loser_prompt, 0, loser_cached)

            if not tool_calls:
                want_tools = expect_tools() if callable(expect_tools) else expect_tools    # callable: orchestrator quyết định lúc vòng đầu xong (bộ đọc song song đã có kết quả)
                forced = self._required_calls(required_future) if (required_future is not None and not tool_calls_log and not nudged_once
                                                                     and (want_tools or _PROMISES_LOOKUP.search(text or ""))) else []
                if forced:                            # lẽ ra bị nhắc: dùng lời gọi tool của yêu cầu song song (đã chạy cùng lúc) thay cho một vòng nhắc
                    nudged_once, tool_calls, text = True, forced, ""
                    self._required_used = getattr(self, "_required_used", 0) + 1
                elif not tool_calls_log and not nudged_once and (want_tools or _PROMISES_LOOKUP.search(text or "")):
                    # (2026-11-11: vòng nhắc tốn nguyên một vòng LLM ≈ 1,2 s ở MỌI lượt không gọi tool. Bỏ hẳn thì nhanh nhưng TSR 92,5 → 72,5 %: model hứa
                    # "em sẽ lên đơn" hoặc bỏ chuyển máy mà không gọi tool. Nên: vẫn nhắc mặc định; caller truyền expect_tools=False khi dữ liệu lượt này đã
                    # được code tra sẵn trong prompt — khi đó chỉ nhắc nếu câu trả lời còn HỨA tra cứu/hành động.)
                    # Bug thật đã gặp: model trả lời kiểu "để em kiểm tra..." nhưng KHÔNG kèm
                    # tool_call nào trong cùng completion -> nếu chấp nhận ngay làm câu trả lời
                    # cuối thì khách không bao giờ nhận được dữ liệu thật. Nhắc model tự kiểm tra
                    # lại ĐÚNG MỘT LẦN (không đoán nội dung câu trả lời từ phía code) trước khi
                    # chấp nhận — bounded ở +1 lệnh gọi API, chỉ xảy ra khi vòng đầu tiên chưa
                    # từng gọi tool nào.
                    nudged_once = True
                    working_messages.append({"role": "assistant", "content": text or ""})
                    working_messages.append({
                        "role": "system",
                        "content": (
                            "Câu trả lời trên của bạn CHƯA gọi tool nào. Nếu bạn vừa nói sẽ 'kiểm tra'/"
                            "'tìm kiếm'/'tra cứu' thông tin cho khách, hãy GỌI TOOL NGAY bây giờ để lấy "
                            "dữ liệu thật trước khi trả lời — không được để khách chờ mà không tra cứu "
                            "gì. Nếu câu trả lời trên đã đầy đủ, chính xác và không cần dữ liệu thêm, "
                            "hãy lặp lại đúng nội dung đó."
                        )
                    })
                    continue
            if not tool_calls:
                t_end = time.perf_counter()
                if timing is not None:
                    total_ms = int(round((t_end - t0) * 1000))
                    # Không có token text nào (hiếm) -> TTFT = Total.
                    ttft_ms = int(round(((first_token_at or t_end) - t0) * 1000))
                    final_ttft = int(round(((first_token_at or t_end) - round_start) * 1000))
                    timing.update({
                        "ttft_ms": ttft_ms, "total_ms": total_ms, "llm_calls": api_calls,
                        # Phân rã TTFT: bao nhiêu vòng LLM phải xong TRƯỚC khi có token đầu tiên của câu trả lời, mỗi vòng mất bao lâu,
                        # tool mất bao lâu, và riêng vòng cuối chờ token đầu bao lâu.
                        "rounds_before_first_token": api_calls - 1, "round_ms": round_ms, "tool_ms": int(round(tool_ms)),
                        "final_round_ttft_ms": final_ttft, "nudged": nudged_once, "hedged_rounds": hedged_rounds, "service_tier": getattr(self, "_last_service_tier", None),
                        "prompt_tokens": usage_totals["prompt_tokens"], "cached_tokens": usage_totals["cached_tokens"]})
                cost = self.cost_tracker.record_turn(self.model, usage_totals["prompt_tokens"], usage_totals["completion_tokens"],
                                                     cached_tokens=usage_totals["cached_tokens"])
                cost["llm_calls"] = api_calls
                cost["reasoning_tokens"] = usage_totals["reasoning_tokens"]  # đã nằm trong completion_tokens (tính tiền)
                return text or "", tool_calls_log, cost

            working_messages.append({
                "role": "assistant",
                "content": text or "",
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ]
            })

            def run_one(tc: Dict[str, Any]) -> Tuple[str, Any, Any]:
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                real_name = _from_openai_safe_name(tc["name"])
                try:
                    result, executed_args = tool_executor(real_name, args)
                except Exception as e:
                    result, executed_args = {"error": "tool_execution_failed", "details": str(e)}, args
                return real_name, result, executed_args

            tool_started = time.perf_counter()
            if len(tool_calls) > 1 and all(_from_openai_safe_name(tc["name"]) in parallel_tools for tc in tool_calls):
                # Mọi tool của vòng này đều CHỈ ĐỌC (caller khai báo) → chạy đồng thời; kết quả vẫn ghi theo đúng thứ tự model gọi.
                with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
                    outcomes = list(pool.map(run_one, tool_calls))
            else:
                outcomes = [run_one(tc) for tc in tool_calls]       # có tool ghi/chuyển máy: tuần tự như cũ (thứ tự tác dụng phụ quan trọng)
            tool_ms += (time.perf_counter() - tool_started) * 1000
            for tc, (real_name, result, executed_args) in zip(tool_calls, outcomes):
                tool_calls_log.append({"name": real_name, "tool": real_name, "args": executed_args, "result": result})
                working_messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": self._tool_content(result)
                })

        raise LLMRoundLimit("LLM vượt quá số round tool-call cho phép (có thể bị loop).")
