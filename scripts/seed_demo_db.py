"""
Seed dữ liệu DEMO vào DB bộ nhớ — IDEMPOTENT (chạy lại bao nhiêu lần cũng ra đúng 1 bộ dữ liệu, D15).

Khách demo: Hoa (C001) — cuộc gọi 1 (2026-10-15, hotline): hỏi máy lọc không khí AirPure Y cho phòng 25 m², nhà có
trẻ nhỏ, ngân sách ~5 triệu, báo giá 5.200.000đ, hẹn "hỏi chồng rồi gọi lại". Ghi MỘT khách MỘT mã (C001) — không còn
seed thêm theo SĐT/`CUST-001` như `main.py` cũ (D2). Episode có session_id cố định nên không bao giờ nhân bản (D5).

Dùng:
    python scripts/seed_demo_db.py                  # seed vào DB demo riêng (data/demo.db)
    python scripts/seed_demo_db.py --db other.db
    python scripts/seed_demo_db.py --reset          # xóa sạch khách demo rồi seed lại
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from src.memory.episodic import EpisodeRecord  # noqa: E402
from src.memory.sqlite_store import demo_db_path, is_production_db  # noqa: E402

DEMO_CUSTOMER_ID = "C001"
DEMO_SESSION_ID = "SEED-DEMO-C001-call_1"
DEMO_CALL_DATE = "2026-10-15"

DEMO_FACTS = [
    # key, value, ttl_days
    ("customer_name", "Hoa", None),
    ("honorific", "chị", None),
    ("room_area_m2", 25.0, 180),
    ("has_children", True, None),
    ("budget_vnd", 5000000, 90),
    ("product_advised", "SKU-AP-Y", None),
    ("price_quoted_vnd", 5200000, None),
    ("blocker", "can hoi chong", 60),
]


def seed_demo(memory, reset: bool = False, operator=None) -> dict:
    """Seed khách demo vào `memory` (MemoryService). Trả về thống kê. Idempotent: gọi lại không thêm bản ghi mới.
    `operator`: view có quyền xóa khách (qua mcp-memory chỉ caller `Operator`); mặc định dùng chính `memory`.
    reset=True: xóa SẠCH khách demo trước (kể cả cuộc gọi 2 của lần demo trước) để demo tái lập đúng mỗi lần."""
    if reset:
        backend = getattr(memory, "backend", None)
        if backend is not None and is_production_db(backend.db_path):
            raise RuntimeError(f"TỪ CHỐI reset: {backend.db_path} là DB mặc định (production). "
                               "Dùng DB demo (data/demo.db) hoặc --db khác.")
        (operator or memory).delete_customer_data(DEMO_CUSTOMER_ID)
    memory.begin_turn("call_1#turn1", call_date=DEMO_CALL_DATE, channel="hotline")
    for key, value, ttl in DEMO_FACTS:
        memory.set_profile_fact(DEMO_CUSTOMER_ID, key, value, session_id=DEMO_SESSION_ID, ttl_days=ttl, observed_on=DEMO_CALL_DATE)
    memory.set_profile_fact(DEMO_CUSTOMER_ID, "channels_seen", ["hotline"], observed_on=DEMO_CALL_DATE)
    memory.add_episode(DEMO_CUSTOMER_ID, EpisodeRecord(
        session_id=DEMO_SESSION_ID, call_index=1, call_date=DEMO_CALL_DATE, channel="hotline",
        customer_goal="Hỏi máy lọc không khí phòng 25m2 có trẻ nhỏ",
        product_advised="SKU-AP-Y", price_quoted_vnd=5200000, blocker="can hoi chong", outcome="hen_goi_lai",
        summary="Đã tư vấn máy lọc AirPure Y 5.2tr, khách bảo hỏi ông xã rồi gọi lại."))
    writes = memory.drain_writes()
    return {"customer_id": DEMO_CUSTOMER_ID, "writes_logged": len(writes),
            "episodes": len(memory.get_episodes(DEMO_CUSTOMER_ID)),
            "facts": len(memory.get_profile_facts(DEMO_CUSTOMER_ID))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed dữ liệu demo (idempotent).")
    ap.add_argument("--db", default=None, help="Đường dẫn DB (mặc định: data/demo.db; HARNESS_DB_PATH ghi đè). "
                                              "Reset bị TỪ CHỐI nếu trỏ vào DB mặc định data/harness_memory.db")
    ap.add_argument("--reset", action="store_true", help="Xóa sạch khách demo trước khi seed")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):                  # console Windows cp1252 làm vỡ tiếng Việt khi pipe/redirect
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    db = args.db or demo_db_path()
    if args.reset and is_production_db(db):
        print(f"TỪ CHỐI --reset: {db} là DB mặc định (production). Dùng DB demo (data/demo.db) hoặc --db khác.")
        return 2                                  # từ chối TRƯỚC khi mở DB
    from src.memory.service import MemoryService
    memory = MemoryService(db_path=db)
    try:
        stats = seed_demo(memory, reset=args.reset)
    finally:
        memory.close()
    print(f"Seed xong: {stats}  (DB: {memory.backend.db_path if memory.backend else 'in-memory'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
