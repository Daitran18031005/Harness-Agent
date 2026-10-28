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
import time
import logging
from typing import Dict, Any, List, Callable, Tuple, Optional

from .cost_tracker import CostTracker
from .model_profiles import profile_for, forced_unsupported_params

logger = logging.getLogger("harness.llm")


class LLMUnavailable(Exception):
    pass


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
        return isinstance(exc, (openai.APIConnectionError, httpx.TimeoutException, httpx.TransportError))
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
                      stream: bool = True, json_mode: bool = False) -> Dict[str, Any]:
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
        if self.temperature is not None and self.profile.supports_temperature and "temperature" not in self.dropped_params:
            kwargs["temperature"] = self.temperature
        if self.seed is not None and self.profile.supports_seed and "seed" not in self.dropped_params:
            kwargs["seed"] = self.seed
        if self.reasoning_effort and self.profile.is_reasoning and "reasoning_effort" not in self.dropped_params:
            kwargs["reasoning_effort"] = self.reasoning_effort
        if self.max_output_tokens is not None:
            kwargs[self._token_param] = self.max_output_tokens
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

    def _create(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], stream: bool = True, json_mode: bool = False):
        """Gọi API; nếu API từ chối 1 tham số thì bỏ tham số đó và thử lại (tối đa 4 lần)."""
        for _ in range(4):
            self.cost_tracker.check_cap()                          # trần chi phí cứng: dừng TRƯỚC khi gọi API (không bao giờ vượt quá một vòng)
            kwargs = self._build_kwargs(messages, tools, stream=stream, json_mode=json_mode)
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

    def complete_json(self, messages: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """1 lần gọi KHÔNG tool, đầu ra JSON object (dùng cho bộ trích bộ nhớ). Trả về (dict đã parse, chi phí/usage).
        Lỗi mạng/JSON hỏng -> ném LLMUnavailable (caller bỏ qua phần trích LLM, không crash)."""
        if not self.available:
            raise LLMUnavailable("LLM client không khả dụng (thiếu OPENAI_API_KEY hoặc lỗi khởi tạo).")
        t0 = time.perf_counter()
        try:
            response = self._create(messages, [], stream=False, json_mode=True)
            usage = getattr(response, "usage", None)
            prompt_t = getattr(usage, "prompt_tokens", 0) or 0
            completion_t = getattr(usage, "completion_tokens", 0) or 0
            details = getattr(usage, "completion_tokens_details", None)
            cost = self.cost_tracker.record_turn(self.model, prompt_t, completion_t)   # đã trả tiền: ghi TRƯỚC khi phân tích (JSON hỏng vẫn tốn tiền)
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

    def _stream_round(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """`_stream_round_once` + thử lại khi timeout/đứt kết nối (bỏ phần đã nhận dở: tool chỉ chạy SAU khi vòng đọc xong). Lỗi khác, kể cả trần chi phí, ném ngay."""
        for attempt in range(self.stream_retries + 1):
            try:
                return self._stream_round_once(messages, tools)
            except Exception as e:
                if attempt >= self.stream_retries or not _is_transient(e):
                    raise
                logger.warning("[LLM] vòng stream lỗi mạng/timeout (%s) — thử lại %d/%d", e, attempt + 1, self.stream_retries)
                time.sleep(0.5 * (attempt + 1))

    def _stream_round_once(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """1 vòng gọi API ở chế độ stream: gom text + tool_call từ các delta; trả về
        (text, tool_calls[{id,name,arguments}], usage, thời điểm perf_counter của token text đầu tiên)."""
        text_parts: List[str] = []
        calls: Dict[int, Dict[str, str]] = {}
        usage = None
        first_token_at = None
        for chunk in self._create_stream(messages, tools):
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
                         timing: Optional[Dict[str, Any]] = None
                         ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
        try:
            return self._chat_with_tools(messages, tool_executor, max_rounds, tools_override, timing)
        except BaseException:               # kể cả BudgetExceeded: các vòng đã trả tiền phải nằm trong tổng chi phí
            self.cost_tracker.commit_inflight()
            raise

    def _chat_with_tools(self, messages: List[Dict[str, Any]], tool_executor: Callable[[str, Dict[str, Any]], Tuple[Any, Dict[str, Any]]],
                         max_rounds: int, tools_override: Optional[List[Dict[str, Any]]], timing: Optional[Dict[str, Any]]
                         ) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
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
        api_calls = 0
        round_ms: List[int] = []          # thời gian từng vòng gọi LLM (đến hết stream của vòng đó)
        tool_ms = 0.0                      # tổng thời gian chạy tool giữa các vòng

        for _ in range(max_rounds):
            round_start = time.perf_counter()
            text, tool_calls, usage, first_token_at = self._stream_round(working_messages, active_tools)
            round_ms.append(int(round((time.perf_counter() - round_start) * 1000)))
            api_calls += 1
            if usage is not None:
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                usage_totals["cached_tokens"] += (getattr(prompt_details, "cached_tokens", 0) or 0) if prompt_details else 0
                usage_totals["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0
                usage_totals["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0
                self.cost_tracker.note_round(self.model, getattr(usage, "prompt_tokens", 0) or 0, getattr(usage, "completion_tokens", 0) or 0,
                                             (getattr(prompt_details, "cached_tokens", 0) or 0) if prompt_details else 0)
                details = getattr(usage, "completion_tokens_details", None)
                usage_totals["reasoning_tokens"] += (getattr(details, "reasoning_tokens", 0) or 0) if details else 0

            if not tool_calls:
                if not tool_calls_log and not nudged_once:
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
                        "final_round_ttft_ms": final_ttft,
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

            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                real_name = _from_openai_safe_name(tc["name"])
                executed_args = args
                tool_started = time.perf_counter()
                try:
                    result, executed_args = tool_executor(real_name, args)
                except Exception as e:
                    result = {"error": "tool_execution_failed", "details": str(e)}
                tool_ms += (time.perf_counter() - tool_started) * 1000
                tool_calls_log.append({"name": real_name, "tool": real_name, "args": executed_args, "result": result})
                working_messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": self._tool_content(result)
                })

        raise LLMRoundLimit("LLM vượt quá số round tool-call cho phép (có thể bị loop).")
