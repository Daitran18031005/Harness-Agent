"""
Phần dùng chung của các MCP server: phân quyền theo caller (mặc định TỪ CHỐI), nhật ký kiểm toán, loại field nội bộ `_*` (N15).

Caller đi theo `_meta.caller` của yêu cầu MCP (client đặt, server kiểm lại). Tên tool giữ nguyên như `tools.schema.json` của BTC
(`pricing.get_quote`, `order.create`…), kết quả của `mock_tools.py` được trả NGUYÊN (chỉ bỏ field bắt đầu bằng `_`).
"""
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)
PERMISSIONS_PATH = os.path.join(CODE_DIR, "config", "mcp_permissions.json")


def strip_internal(obj: Any) -> Any:
    """N15: bỏ ĐỆ QUY field bắt đầu bằng '_' (vd `_internal_price_floor_vnd`) trước khi trả ra khỏi server."""
    if isinstance(obj, dict):
        return {k: strip_internal(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [strip_internal(v) for v in obj]
    return obj


class Permissions:
    def __init__(self, tools: Dict[str, List[str]], version: str = "?"):
        self.tools, self.version = tools, version

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Permissions":
        with open(path or PERMISSIONS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data["tools"], data.get("version", "?"))

    def allowed(self, tool: str, caller: Optional[str]) -> bool:
        return bool(caller) and caller in self.tools.get(tool, [])


def caller_of(ctx: Any) -> Optional[str]:
    meta = getattr(getattr(ctx, "request_context", None), "meta", None) or {}
    caller = meta.get("caller") if isinstance(meta, dict) else getattr(meta, "caller", None)
    return caller if isinstance(caller, str) else None


class Guarded:
    """Bọc một hàm nghiệp vụ: kiểm quyền theo caller, ghi nhật ký kiểm toán (không ghi tham số — có thể chứa SĐT/địa chỉ thật),
    bắt lỗi → kết quả lỗi có cấu trúc, bỏ field nội bộ."""

    def __init__(self, server_name: str, permissions: Permissions, strip: bool = True):
        # strip=False: server dữ liệu của chính hệ thống (mcp-memory) — khóa dữ liệu có thể bắt đầu bằng '_', và kết quả không đi tới LLM.
        self.server_name, self.permissions, self.strip = server_name, permissions, strip
        self.audit: List[Dict[str, Any]] = []

    def run(self, tool: str, ctx: Any, fn: Callable[..., Any], **kwargs: Any) -> Dict[str, Any]:
        caller = caller_of(ctx)
        started = time.perf_counter()
        if not self.permissions.allowed(tool, caller):
            result: Dict[str, Any] = {"error": "forbidden", "tool": tool, "caller": caller or "unknown"}
        else:
            try:
                result = fn(**{k: v for k, v in kwargs.items() if v is not None or k in ("brief",)})
            except Exception as e:                       # lỗi nghiệp vụ không làm chết server
                result = {"error": "tool_execution_failed", "details": str(e)}
        if self.strip:
            result = strip_internal(result)
        self.audit.append({"server": self.server_name, "tool": tool, "caller": caller, "ok": "error" not in result,
                           "error": result.get("error"), "ms": round((time.perf_counter() - started) * 1000, 3)})
        return result
