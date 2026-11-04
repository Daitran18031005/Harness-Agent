"""Phát số đo Prometheus từ các file trace JSONL của lần chạy đánh giá (runs/**), để dashboard Grafana xem được cả kết quả đo lẫn máy chủ trực tiếp.

    python -m monitoring.trace_exporter                       # mặc định: runs/gd2_run*/**/full*.jsonl và baseline*.jsonl (các lần đo GĐ2), cổng 9108
    python -m monitoring.trace_exporter --glob "runs/gd2_run7/**/*.jsonl" --port 9108

Mỗi lần Prometheus lấy số, registry được dựng lại từ file (cache theo mtime). Nhãn: source="trace", run = thư mục chứa file, config = trường `config` của dòng trace.
"""
import argparse
import glob
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, CODE_DIR)

from monitoring.metrics import Registry, observe_turn  # noqa: E402

DEFAULT_GLOBS = ("runs/gd2_run*/**/full*.jsonl", "runs/gd2_run*/**/baseline*.jsonl")
_cache: Dict[str, Tuple[float, List[dict]]] = {}


def _rows(path: str) -> List[dict]:
    mtime = os.path.getmtime(path)
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass                     # dòng dở dang do file đang được ghi
    _cache[path] = (mtime, rows)
    return rows


def build_registry(globs=DEFAULT_GLOBS, root: str = CODE_DIR) -> Registry:
    reg = Registry()
    seen = set()
    for pattern in globs:
        for path in sorted(glob.glob(os.path.join(root, pattern), recursive=True)):
            if path in seen:
                continue
            seen.add(path)
            run = os.path.relpath(os.path.dirname(path), root).replace("\\", "/")
            if any(part.startswith("_") for part in run.split("/")):
                continue                     # thư mục tạm/gộp (_merged, _ev1…) trùng dữ liệu của sample/ và gen/ — đếm hai lần sẽ làm sai số
            for row in _rows(path):
                observe_turn(reg, row, source="trace", run=run, config=row.get("config") or "unknown")
    return reg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--glob", action="append", default=None, help="mẫu đường dẫn (tính từ Code/), lặp lại được")
    ap.add_argument("--port", type=int, default=9108)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    globs = tuple(args.glob or DEFAULT_GLOBS)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/metrics":
                self.send_error(404)
                return
            body = build_registry(globs).render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    print(f"trace exporter: http://{args.host}:{args.port}/metrics  (mẫu: {', '.join(globs)})")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
