"""
SQLite Persistent Store: Bền vững hóa dữ liệu 4 tầng bộ nhớ qua restart.
Mọi phương thức tự fallback im lặng (self.available=False) khi SQLite lỗi
(disk đầy, quyền file, path hỏng...) để caller rơi về hành vi in-memory-only
hiện có, không bao giờ làm crash pipeline — nhưng lỗi ghi được đếm (write_errors) và log mức ERROR.

Bước 9 (D1, D5–D9, D11, D13, D14):
- Mỗi (khách, key) chỉ có đúng 1 dòng ACTIVE (unique index một phần); phiên bản cũ giữ lại ở trạng thái superseded.
- Episode UNIQUE theo (khách, session) và đọc theo ngày gọi, không theo giờ máy.
- Provenance của fact: source_call, source_turn, source_channel (+ observed_on theo ngày nghiệp vụ, ttl_days).
- Xóa khách = xóa SẠCH profile, episode, working session, identity link (và dọn trang đã xóa + checkpoint WAL).
- Ghi theo GIAO DỊCH từng lượt: begin_turn() ... commit_turn()/rollback_turn().
- close() checkpoint WAL (và tự chạy khi thoát process) -> chỉ cần copy file .db vẫn đủ dữ liệu.
- Đường dẫn DB mặc định là đường dẫn TUYỆT ĐỐI (không phụ thuộc thư mục hiện hành).
- Migration tự động DB cũ lên schema v2 (làm sạch bản trùng, thêm cột), có sao lưu `.pre_v2.bak` nếu phải xóa dòng.
"""
import os
import json
import atexit
import shutil
import sqlite3
import logging
import threading
import weakref
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("harness.memory")

SCHEMA_VERSION = 2
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# DB "production" (dữ liệu thật/UI) — KHÔNG BAO GIỜ bị reset bởi script demo. Cố định, không phụ thuộc biến môi trường.
PRODUCTION_DB_PATH = os.path.join(CODE_DIR, "data", "harness_memory.db")


def demo_db_path() -> str:
    """DB riêng cho demo (main.py, scripts/seed_demo_db.py): `<Code>/data/demo.db`, ghi đè được bằng HARNESS_DB_PATH."""
    env = os.environ.get("HARNESS_DB_PATH", "").strip()
    return os.path.abspath(env) if env else os.path.join(CODE_DIR, "data", "demo.db")


def is_production_db(path: Optional[str]) -> bool:
    """True nếu `path` trỏ vào DB mặc định (production) — so sánh theo đường dẫn chuẩn hóa, không phân biệt hoa/thường."""
    if not path:
        return False
    return os.path.normcase(os.path.realpath(path)) == os.path.normcase(os.path.realpath(PRODUCTION_DB_PATH))


def default_db_path() -> str:
    """Đường dẫn DB tuyệt đối: biến môi trường HARNESS_DB_PATH nếu có, nếu không `<Code>/data/harness_memory.db`.
    Không phụ thuộc thư mục hiện hành (D14)."""
    env = os.environ.get("HARNESS_DB_PATH", "").strip()
    return os.path.abspath(env) if env else os.path.join(CODE_DIR, "data", "harness_memory.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS customer_profiles (
    customer_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    source_session TEXT DEFAULT '',
    observed_at TEXT NOT NULL,
    ttl_days INTEGER,
    superseded INTEGER DEFAULT 0,
    superseded_by TEXT,
    source_call TEXT DEFAULT '',
    source_turn INTEGER,
    source_channel TEXT DEFAULT '',
    observed_on TEXT,
    PRIMARY KEY (customer_id, key, observed_at)
);
CREATE TABLE IF NOT EXISTS episodic_records (
    customer_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    call_index INTEGER,
    call_date TEXT,
    channel TEXT,
    customer_goal TEXT,
    product_advised TEXT,
    price_quoted_vnd INTEGER,
    promo_code TEXT,
    promo_expiry TEXT,
    blocker TEXT,
    outcome TEXT,
    summary TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS working_sessions (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identity_links (
    contact_hash TEXT PRIMARY KEY,
    master_customer_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_PROFILE_NEW_COLUMNS = {
    "source_call": "TEXT DEFAULT ''",
    "source_turn": "INTEGER",
    "source_channel": "TEXT DEFAULT ''",
    "observed_on": "TEXT",
}

_open_stores: "weakref.WeakSet[SQLiteStore]" = weakref.WeakSet()


@atexit.register
def _close_all_stores() -> None:
    """Checkpoint WAL của mọi store còn mở khi process thoát (D8)."""
    for store in list(_open_stores):
        try:
            store.close()
        except Exception:
            pass


class SQLiteStore:
    """Lưu bền vững cho Profile/Episodic/Working memory.
    [INTEGRATION POINT: PERSISTENT DATABASE & VECTOR STORE] — nửa database của integration point này."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path) if db_path else default_db_path()
        self.available = False
        self.write_errors = 0
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._in_turn = False
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA secure_delete=ON")   # trang bị xóa được ghi đè 0 (xóa dữ liệu khách thật sự)
            self._migrate()
            self.available = True
            _open_stores.add(self)
        except sqlite3.Error as e:
            logger.error("[PERSISTENCE] SQLite unavailable (%s) — falling back to in-memory-only storage; data will not survive restart.", e)
            self.available = False

    # ------------------------------------------------------------------ schema / migration
    def _migrate(self) -> None:
        c = self._conn
        version = c.execute("PRAGMA user_version").fetchone()[0]
        c.executescript(SCHEMA)
        # 1) thêm cột provenance cho DB cũ
        cols = {r[1] for r in c.execute("PRAGMA table_info(customer_profiles)").fetchall()}
        for name, decl in _PROFILE_NEW_COLUMNS.items():
            if name not in cols:
                c.execute(f"ALTER TABLE customer_profiles ADD COLUMN {name} {decl}")
        # 2) làm sạch bản trùng TRƯỚC khi tạo unique index
        dup_profiles = c.execute(
            "SELECT COUNT(*) FROM customer_profiles WHERE superseded=0 AND rowid NOT IN "
            "(SELECT MAX(rowid) FROM customer_profiles WHERE superseded=0 GROUP BY customer_id, key)").fetchone()[0]
        dup_episodes = c.execute(
            "SELECT COUNT(*) FROM episodic_records WHERE rowid NOT IN "
            "(SELECT MAX(rowid) FROM episodic_records GROUP BY customer_id, session_id)").fetchone()[0]
        if dup_episodes and version < SCHEMA_VERSION:
            self._backup_before_migration()
        if dup_profiles:
            # giữ dòng active mới nhất, các bản trùng cũ chuyển thành superseded (không xóa dữ liệu)
            c.execute("UPDATE customer_profiles SET superseded=1 WHERE superseded=0 AND rowid NOT IN "
                      "(SELECT MAX(rowid) FROM customer_profiles WHERE superseded=0 GROUP BY customer_id, key)")
        if dup_episodes:
            c.execute("DELETE FROM episodic_records WHERE rowid NOT IN "
                      "(SELECT MAX(rowid) FROM episodic_records GROUP BY customer_id, session_id)")
        if dup_profiles or dup_episodes:
            logger.warning("[PERSISTENCE] migration v%d: %d fact active trùng -> superseded, %d episode trùng đã gộp.",
                           SCHEMA_VERSION, dup_profiles, dup_episodes)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_active_fact ON customer_profiles(customer_id, key) WHERE superseded=0")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_episode ON episodic_records(customer_id, session_id)")
        c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        c.commit()

    def _backup_before_migration(self) -> None:
        try:
            self._conn.commit()
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            dst = self.db_path + ".pre_v2.bak"
            if not os.path.exists(dst):
                shutil.copy2(self.db_path, dst)
                logger.warning("[PERSISTENCE] đã sao lưu DB trước khi migration: %s", dst)
        except (OSError, sqlite3.Error) as e:
            logger.error("[PERSISTENCE] không sao lưu được DB trước migration (%s)", e)

    # ------------------------------------------------------------------ giao dịch theo lượt
    def begin_turn(self) -> None:
        """Bắt đầu giao dịch cho 1 lượt: mọi ghi trong lượt chỉ commit khi commit_turn()."""
        if not self.available:
            return
        with self._lock:
            if self._in_turn:
                self._conn.commit()           # lượt trước chưa đóng -> chốt nó trước
            self._in_turn = True

    def commit_turn(self) -> None:
        if not self.available:
            return
        with self._lock:
            self._conn.commit()
            self._in_turn = False

    def rollback_turn(self) -> None:
        """Hủy các ghi của lượt hiện tại trong DB (bản in-memory không tự hoàn tác)."""
        if not self.available:
            return
        with self._lock:
            self._conn.rollback()
            self._in_turn = False

    def _commit(self) -> None:
        if not self._in_turn:
            self._conn.commit()

    def _fail(self, what: str, e: Exception) -> bool:
        self.write_errors += 1
        logger.error("[PERSISTENCE] %s failed (%s) — write dropped, in-memory copy still holds.", what, e)
        try:
            self._conn.rollback()
        except sqlite3.Error:
            pass
        return False

    # ---------------------------------------------------------------- Profile
    def save_profile_version(self, customer_id: str, fact: Dict[str, Any], supersede_previous: bool) -> bool:
        """Ghi 1 phiên bản fact. supersede_previous=True: đánh dấu bản active hiện có là superseded RỒI chèn bản mới
        (cùng 1 giao dịch) — luôn còn đúng 1 dòng active cho (khách, key)."""
        if not self.available:
            return False
        with self._lock:
            try:
                if supersede_previous:
                    self._conn.execute(
                        "UPDATE customer_profiles SET superseded=1, superseded_by=? WHERE customer_id=? AND key=? AND superseded=0",
                        (json.dumps(fact.get("value"), ensure_ascii=False), customer_id, fact["key"]))
                self._conn.execute(
                    "INSERT OR REPLACE INTO customer_profiles (customer_id, key, value, confidence, source_session, observed_at, "
                    "ttl_days, superseded, superseded_by, source_call, source_turn, source_channel, observed_on) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (customer_id, fact["key"], json.dumps(fact.get("value"), ensure_ascii=False), fact.get("confidence", 1.0),
                     fact.get("source_session", ""), fact.get("observed_at") or datetime.now().isoformat(),
                     fact.get("ttl_days"), 0, None, fact.get("source_call", ""), fact.get("source_turn"),
                     fact.get("source_channel", ""), fact.get("observed_on")))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("save_profile_version", e)

    def renew_profile_fact(self, customer_id: str, key: str, observed_on: Optional[str], ttl_days: Optional[int]) -> bool:
        """Cùng giá trị được xác nhận lại: gia hạn hiệu lực (không thêm dòng mới)."""
        if not self.available:
            return False
        with self._lock:
            try:
                self._conn.execute("UPDATE customer_profiles SET observed_on=?, ttl_days=? WHERE customer_id=? AND key=? AND superseded=0",
                                   (observed_on, ttl_days, customer_id, key))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("renew_profile_fact", e)

    def load_all_profiles(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """customer_id -> key -> danh sách phiên bản (cũ -> mới), mỗi phiên bản đủ metadata/provenance."""
        if not self.available:
            return {}
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT customer_id, key, value, confidence, source_session, observed_at, ttl_days, superseded, superseded_by, "
                    "source_call, source_turn, source_channel, observed_on FROM customer_profiles ORDER BY rowid ASC")
                out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
                for cid, key, value, conf, src, obs, ttl, sup, sup_by, scall, sturn, schan, obs_on in cur.fetchall():
                    out.setdefault(cid, {}).setdefault(key, []).append({
                        "value": json.loads(value), "confidence": conf, "source_session": src or "", "observed_at": obs,
                        "ttl_days": ttl, "superseded": bool(sup), "superseded_by": sup_by, "source_call": scall or "",
                        "source_turn": sturn, "source_channel": schan or "", "observed_on": obs_on})
                return out
            except sqlite3.Error as e:
                logger.error("[PERSISTENCE] load_all_profiles failed (%s).", e)
                return {}

    # --------------------------------------------------------------- Episodic
    def append_episode(self, customer_id: str, episode: Dict[str, Any]) -> bool:
        """Upsert theo (khách, session): ghi lại cùng 1 cuộc gọi (vd lúc chuyển máy rồi lúc kết thúc) chỉ cập nhật 1 dòng."""
        if not self.available:
            return False
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO episodic_records (customer_id, session_id, call_index, call_date, channel, "
                    "customer_goal, product_advised, price_quoted_vnd, promo_code, promo_expiry, blocker, outcome, "
                    "summary, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (customer_id, episode.get("session_id"), episode.get("call_index"), episode.get("call_date"),
                     episode.get("channel"), episode.get("customer_goal"), episode.get("product_advised"),
                     episode.get("price_quoted_vnd"), episode.get("promo_code"), episode.get("promo_expiry"),
                     episode.get("blocker"), episode.get("outcome"), episode.get("summary"),
                     datetime.now().isoformat()))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("append_episode", e)

    def load_all_episodes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Sắp theo NGÀY GỌI (call_date, call_index), không theo giờ máy (D5)."""
        if not self.available:
            return {}
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT customer_id, session_id, call_index, call_date, channel, customer_goal, "
                    "product_advised, price_quoted_vnd, promo_code, promo_expiry, blocker, outcome, summary "
                    "FROM episodic_records ORDER BY call_date ASC, call_index ASC, rowid ASC")
                out: Dict[str, List[Dict[str, Any]]] = {}
                cols = ["session_id", "call_index", "call_date", "channel", "customer_goal", "product_advised",
                        "price_quoted_vnd", "promo_code", "promo_expiry", "blocker", "outcome", "summary"]
                for row in cur.fetchall():
                    out.setdefault(row[0], []).append(dict(zip(cols, row[1:])))
                return out
            except sqlite3.Error as e:
                logger.error("[PERSISTENCE] load_all_episodes failed (%s).", e)
                return {}

    # --------------------------------------------------------------- Working
    def save_working(self, session_id: str, state_dict: Dict[str, Any]) -> bool:
        if not self.available:
            return False
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO working_sessions (session_id, state_json, updated_at) VALUES (?, ?, ?)",
                    (session_id, json.dumps(state_dict, ensure_ascii=False), datetime.now().isoformat()))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("save_working", e)

    def load_working(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self.available:
            return None
        with self._lock:
            try:
                row = self._conn.execute("SELECT state_json FROM working_sessions WHERE session_id=?", (session_id,)).fetchone()
                return json.loads(row[0]) if row else None
            except sqlite3.Error as e:
                logger.error("[PERSISTENCE] load_working failed (%s).", e)
                return None

    def delete_working_session(self, session_id: str) -> bool:
        if not self.available:
            return False
        with self._lock:
            try:
                self._conn.execute("DELETE FROM working_sessions WHERE session_id=?", (session_id,))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("delete_working_session", e)

    # ------------------------------------------------------------ Identity Linkage
    def save_identity_link(self, contact_hash: str, master_customer_id: str) -> bool:
        if not self.available:
            return False
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO identity_links (contact_hash, master_customer_id, created_at) VALUES (?, ?, ?)",
                    (contact_hash, master_customer_id, datetime.now().isoformat()))
                self._commit()
                return True
            except sqlite3.Error as e:
                return self._fail("save_identity_link", e)

    def load_identity_links(self) -> Dict[str, str]:
        if not self.available:
            return {}
        with self._lock:
            try:
                return {r[0]: r[1] for r in self._conn.execute("SELECT contact_hash, master_customer_id FROM identity_links").fetchall()}
            except sqlite3.Error as e:
                logger.error("[PERSISTENCE] load_identity_links failed (%s).", e)
                return {}

    # ------------------------------------------------------------------ xóa khách (D9)
    def delete_customer(self, customer_id: str) -> bool:
        """Xóa SẠCH mọi dữ liệu của 1 khách ở MỌI bảng (profile + lịch sử phiên bản, episode, working session
        `SESS-<id>-*`, identity link trỏ về khách), trong 1 giao dịch; rồi checkpoint WAL để dữ liệu không còn
        nằm trong file -wal."""
        if not self.available:
            return False
        with self._lock:
            try:
                if self._in_turn:
                    self._conn.commit()
                    self._in_turn = False
                self._conn.execute("DELETE FROM customer_profiles WHERE customer_id=?", (customer_id,))
                self._conn.execute("DELETE FROM episodic_records WHERE customer_id=?", (customer_id,))
                self._conn.execute("DELETE FROM working_sessions WHERE session_id LIKE ? ESCAPE '\\'",
                                   (f"SESS-{_like_escape(customer_id)}-%",))
                self._conn.execute("DELETE FROM identity_links WHERE master_customer_id=?", (customer_id,))
                self._conn.commit()
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                return True
            except sqlite3.Error as e:
                return self._fail("delete_customer", e)

    # ------------------------------------------------------------------ đóng
    def close(self) -> None:
        """Chốt giao dịch, checkpoint WAL (dữ liệu về hẳn file .db) và đóng kết nối. An toàn khi gọi nhiều lần."""
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.commit()
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.close()
            except sqlite3.Error as e:
                logger.error("[PERSISTENCE] close failed (%s)", e)
            finally:
                self._conn = None
                self.available = False
                self._in_turn = False


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
