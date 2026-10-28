"""Chạy demo giao diện: seed DB demo (idempotent) rồi mở API + giao diện tại http://127.0.0.1:8000/ .

    python scripts/run_demo.py            # DB riêng data/demo.db (khách Hoa C001 đã có cuộc 1 ngày 15/10)
    python scripts/run_demo.py --reset    # xóa sạch khách demo rồi seed lại (demo tái lập)
    python scripts/run_demo.py --port 8010

Không có OPENAI_API_KEY → nhánh rule-based (giao diện vẫn chạy, chỉ không có LLM). Không đụng DB production data/harness_memory.db."""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE)
os.chdir(CODE)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--max-cost-vnd", type=float, default=None, help="trần chi phí LLM cứng cho cả máy chủ (VND); chạm trần → /chat trả 402")
    a = ap.parse_args(argv)

    from src.memory.sqlite_store import demo_db_path
    db = demo_db_path()
    if a.max_cost_vnd is not None:
        os.environ["API_MAX_COST_VND"] = str(a.max_cost_vnd)
    os.environ["HARNESS_DB_PATH"] = db                      # API dựng pipeline từ DB demo (default_db_path đọc biến này)
    from scripts.seed_demo_db import seed_demo
    from src.memory.service import MemoryService
    mem = MemoryService(db_path=db)
    print("Seed demo:", seed_demo(mem, reset=a.reset))
    mem.close() if hasattr(mem, "close") else None

    import uvicorn
    print(f"Giao diện: http://{a.host}:{a.port}/   ·   tài liệu API: http://{a.host}:{a.port}/docs   ·   DB: {db}")
    uvicorn.run("api.app:app", host=a.host, port=a.port)      # MỘT worker (xem api/app.py)
    return 0


if __name__ == "__main__":
    sys.exit(main())
