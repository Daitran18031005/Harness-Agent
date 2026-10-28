"""Test cụm bước 9–10 — bộ nhớ/DB (provenance, TTL, giao dịch, migration, xóa trọn vẹn), bộ trích 2 tầng, chốt cuộc gọi.
Mọi test dùng client LLM GIẢ — không gọi API. DB luôn nằm trong thư mục tạm, không đụng data/harness_memory.db."""
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from tests._helpers import build_components, PUBLIC_DIR
from src.channels.normalizer import InputChannel
from src.memory.service import MemoryService
from src.memory.episodic import EpisodeRecord
from src.memory.memory_extractor import (extract_easy_slots, validate_hard_slots, HardSlotExtractor, CallFinalizer)
from src.memory.sqlite_store import SQLiteStore, default_db_path

LLM_ON = {"MEMORY_EXTRACTOR_LLM": "1"}


class FakeJSONLLM:
    """LLM giả cho bộ trích slot khó (complete_json) và cho vòng tool (chat_with_tools)."""
    available = True

    def __init__(self, answers=None, chat=None):
        self.answers = list(answers or [])
        self.chat = chat or {"calls": [], "text": "Dạ vâng ạ."}
        self.json_calls = []

    def complete_json(self, messages):
        self.json_calls.append(messages)
        answer = self.answers.pop(0) if self.answers else {}
        if isinstance(answer, Exception):
            raise answer
        return answer, {"prompt_tokens": 10, "completion_tokens": 5, "llm_calls": 1, "model": "fake"}

    def get_base_tools(self):
        return []

    def chat_with_tools(self, messages, tool_executor, max_rounds=6, tools_override=None, timing=None):
        log = []
        for name, args in self.chat["calls"]:
            result, executed = tool_executor(name, args)
            log.append({"name": name, "tool": name, "args": executed, "result": result})
        return self.chat["text"], log, {"prompt_tokens": 0, "completion_tokens": 0}


def tmp_db():
    d = tempfile.mkdtemp()
    return d, os.path.join(d, "t.db")


# =====================================================================  bộ nhớ / DB
class ProvenanceAndTTLTest(unittest.TestCase):
    def setUp(self):
        self.dir, self.db = tmp_db()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_provenance_call_turn_channel_and_persisted(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.begin_turn("call_2#turn3", call_date="2026-10-17", channel="fanpage")
        m.set_profile_fact("C1", "product_advised", "SKU-AP-Y")
        m.drain_writes()
        m.close()
        f = MemoryService(enable_persistence=True, db_path=self.db).profile.get_history("C1", "product_advised")[0]
        self.assertEqual((f.source_call, f.source_turn, f.source_channel, f.observed_on), ("call_2", 3, "fanpage", "2026-10-17"))

    def test_write_log_carries_provenance(self):
        m = MemoryService(enable_persistence=False)
        m.begin_turn("call_1#turn2", call_date="2026-10-15", channel="hotline")
        m.set_profile_fact("C1", "color", "den")
        w = m.drain_writes()[0]
        self.assertEqual((w["source_call"], w["source_turn"], w["source_channel"], w["source"]), ("call_1", 2, "hotline", "call_1#turn2"))

    def test_end_trigger_source_is_call_name(self):
        m = MemoryService(enable_persistence=False)
        m.begin_turn("call_2#end", call_date="2026-10-17", channel="hotline")
        m.set_profile_fact("C1", "blocker", "x")
        w = m.drain_writes()[0]
        self.assertEqual((w["source_call"], w["source_turn"]), ("call_2", None))

    def test_facts_by_channel(self):
        m = MemoryService(enable_persistence=False)
        m.begin_turn("call_1#turn1", call_date="2026-10-15", channel="fanpage")
        m.set_profile_fact("C1", "product_advised", "SKU-SN-RUN2")
        m.begin_turn("call_2#turn1", call_date="2026-10-16", channel="hotline")
        m.set_profile_fact("C1", "size", "41")
        self.assertEqual(m.facts_by_channel("C1"), {"fanpage": {"product_advised": "SKU-SN-RUN2"}, "hotline": {"size": "41"}})

    def test_ttl_zero_expires_immediately_and_no_date_means_no_filter(self):
        m = MemoryService(enable_persistence=False)
        m.set_profile_fact("C1", "intent_hot", True, ttl_days=0, observed_on="2026-10-15")
        self.assertNotIn("intent_hot", m.get_profile_facts("C1", on_date="2026-10-15"))
        self.assertIn("intent_hot", m.get_profile_facts("C1"))

    def test_reobserved_same_value_renews_ttl_without_new_row(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.set_profile_fact("C1", "address", "Hà Nội", ttl_days=30, observed_on="2026-01-01")
        self.assertNotIn("address", m.get_profile_facts("C1", on_date="2026-03-01"))
        m.set_profile_fact("C1", "address", "Hà Nội", ttl_days=30, observed_on="2026-02-25")      # khách xác nhận lại
        self.assertIn("address", m.get_profile_facts("C1", on_date="2026-03-01"))
        m.close()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("select count(*) from customer_profiles where key='address'").fetchone()[0], 1)
        c.close()

    def test_history_survives_reload(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.set_profile_fact("C1", "color", "den")
        m.set_profile_fact("C1", "color", "trang")
        m.close()
        hist = MemoryService(enable_persistence=True, db_path=self.db).profile.get_history("C1", "color")
        self.assertEqual([(h.value, h.superseded) for h in hist], [("den", True), ("trang", False)])

    def test_rapid_writes_never_collide_on_timestamp(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        for i in range(50):
            m.set_profile_fact("C1", "n", i)
        m.close()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("select count(*) from customer_profiles where key='n'").fetchone()[0], 50)
        self.assertEqual(c.execute("select count(*) from customer_profiles where key='n' and superseded=0").fetchone()[0], 1)
        c.close()


class TransactionTest(unittest.TestCase):
    def setUp(self):
        self.dir, self.db = tmp_db()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _count(self):
        c = sqlite3.connect(self.db)
        try:
            return c.execute("select count(*) from customer_profiles").fetchone()[0]
        finally:
            c.close()

    def test_turn_commits_only_on_drain(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.begin_turn("call_1#turn1", call_date="2026-10-15")
        m.set_profile_fact("C1", "a", 1)
        m.set_profile_fact("C1", "b", 2)
        self.assertEqual(self._count(), 0)                  # chưa chốt lượt: kết nối khác chưa thấy gì
        m.drain_writes()
        self.assertEqual(self._count(), 2)
        m.close()

    def test_abort_turn_discards_db_writes(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.begin_turn("call_1#turn1", call_date="2026-10-15")
        m.set_profile_fact("C1", "a", 1)
        m.abort_turn()
        m.close()
        self.assertEqual(self._count(), 0)

    def test_unclosed_previous_turn_is_committed_by_next_begin(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.begin_turn("call_1#turn1", call_date="2026-10-15")
        m.set_profile_fact("C1", "a", 1)
        m.begin_turn("call_1#turn2", call_date="2026-10-15")
        self.assertEqual(self._count(), 1)
        m.close()


class MigrationTest(unittest.TestCase):
    """DB cũ (schema v1, có fact active trùng và episode trùng như data/harness_memory.db thật) được nâng lên v2."""

    def setUp(self):
        self.dir, self.db = tmp_db()
        c = sqlite3.connect(self.db)
        c.executescript("""
            CREATE TABLE customer_profiles (customer_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
              confidence REAL DEFAULT 1.0, source_session TEXT DEFAULT '', observed_at TEXT NOT NULL, ttl_days INTEGER,
              superseded INTEGER DEFAULT 0, superseded_by TEXT, PRIMARY KEY (customer_id, key, observed_at));
            CREATE TABLE episodic_records (customer_id TEXT NOT NULL, session_id TEXT NOT NULL, call_index INTEGER, call_date TEXT,
              channel TEXT, customer_goal TEXT, product_advised TEXT, price_quoted_vnd INTEGER, promo_code TEXT, promo_expiry TEXT,
              blocker TEXT, outcome TEXT, summary TEXT, created_at TEXT NOT NULL);
            CREATE TABLE working_sessions (session_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE identity_links (contact_hash TEXT PRIMARY KEY, master_customer_id TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        for i in range(4):   # 4 bản active trùng của cùng (C001, product_advised)
            c.execute("insert into customer_profiles values ('C001','product_advised','\"SKU-AP-Y\"',1.0,'',?,NULL,0,NULL)", (f"2026-10-1{i}T10:00:00",))
        c.execute("insert into customer_profiles values ('C001','color','\"den\"',1.0,'','2026-10-10T10:00:00',NULL,0,NULL)")
        for i in range(4):   # 4 episode trùng
            c.execute("insert into episodic_records values ('C001','SESS-01',1,'2026-10-15','hotline','g','SKU-AP-Y',5200000,NULL,NULL,'b','hen_goi_lai','s',?)", (f"2026-10-1{i}T10:00:00",))
        c.commit()
        c.close()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_migration_cleans_duplicates_keeps_data_and_backs_up(self):
        store = SQLiteStore(self.db)
        self.assertTrue(store.available)
        store.close()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("pragma user_version").fetchone()[0], 2)
        active = c.execute("select count(*) from customer_profiles where customer_id='C001' and key='product_advised' and superseded=0").fetchone()[0]
        total = c.execute("select count(*) from customer_profiles where customer_id='C001' and key='product_advised'").fetchone()[0]
        self.assertEqual((active, total), (1, 4))                       # không mất dòng nào, chỉ đánh dấu superseded
        self.assertEqual(c.execute("select count(*) from episodic_records").fetchone()[0], 1)
        cols = {r[1] for r in c.execute("pragma table_info(customer_profiles)")}
        self.assertTrue({"source_call", "source_turn", "source_channel", "observed_on"} <= cols)
        c.close()
        self.assertTrue(os.path.exists(self.db + ".pre_v2.bak"))        # có sao lưu trước khi xóa episode trùng

    def test_unique_indexes_enforced_after_migration(self):
        SQLiteStore(self.db).close()
        c = sqlite3.connect(self.db)
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("insert into customer_profiles (customer_id,key,value,observed_at,superseded) values ('C001','color','\"x\"','2027-01-01',0)")
        c.close()

    def test_migrated_db_loads_through_memory_service(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        self.assertEqual(m.get_profile_facts("C001")["product_advised"], "SKU-AP-Y")
        self.assertEqual(len(m.get_episodes("C001")), 1)
        m.close()

    def test_second_open_is_noop(self):
        SQLiteStore(self.db).close()
        SQLiteStore(self.db).close()
        self.assertEqual(len([f for f in os.listdir(self.dir) if f.endswith(".bak")]), 1)


class EpisodeTest(unittest.TestCase):
    def test_same_session_upserts(self):
        m = MemoryService(enable_persistence=False)
        m.add_episode("C1", EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="a", summary="v1"))
        m.add_episode("C1", EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="a", summary="v2"))
        eps = m.get_episodes("C1")
        self.assertEqual([(e.session_id, e.summary) for e in eps], [("S1", "v2")])

    def test_ordered_by_call_date_not_insert_order(self):
        m = MemoryService(enable_persistence=False)
        for sid, date, idx in (("S3", "2026-10-20", 3), ("S1", "2026-10-15", 1), ("S2", "2026-10-17", 2)):
            m.add_episode("C1", EpisodeRecord(session_id=sid, call_index=idx, call_date=date, channel="hotline", customer_goal=""))
        self.assertEqual([e.session_id for e in m.get_episodes("C1")], ["S1", "S2", "S3"])
        self.assertEqual(m.get_last_episode("C1").session_id, "S3")


class DeleteEverythingTest(unittest.TestCase):
    """Ưu tiên cụm 9: xóa khách phải xóa MỌI tầng/bảng, kiểm tra từng bảng."""

    def setUp(self):
        self.dir, self.db = tmp_db()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _fill(self, m, cid):
        m.set_profile_fact(cid, "color", "den")
        m.set_profile_fact(cid, "color", "trang")                     # có cả lịch sử superseded
        m.add_episode(cid, EpisodeRecord(session_id=f"S-{cid}", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="x"))
        m.set_working(f"SESS-{cid}-2026-10-15", current_turn=2, messages_in_session=[{"role": "user", "content": "nguyên văn hội thoại"}])
        m.backend.save_identity_link(f"HASH-{cid}", cid)

    def _counts(self, cid):
        c = sqlite3.connect(self.db)
        try:
            return {
                "customer_profiles": c.execute("select count(*) from customer_profiles where customer_id=?", (cid,)).fetchone()[0],
                "episodic_records": c.execute("select count(*) from episodic_records where customer_id=?", (cid,)).fetchone()[0],
                "working_sessions": c.execute("select count(*) from working_sessions where session_id like ?", (f"SESS-{cid}-%",)).fetchone()[0],
                "identity_links": c.execute("select count(*) from identity_links where master_customer_id=?", (cid,)).fetchone()[0],
            }
        finally:
            c.close()

    def test_every_table_cleared_and_other_customers_untouched(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        self._fill(m, "C1")
        self._fill(m, "C10")                                           # id bắt đầu bằng 'C1' — không được bị xóa lây
        m.drain_writes()
        self.assertTrue(all(v > 0 for v in self._counts("C1").values()))
        m.delete_customer_data("C1")
        self.assertEqual(self._counts("C1"), {"customer_profiles": 0, "episodic_records": 0, "working_sessions": 0, "identity_links": 0})
        self.assertTrue(all(v > 0 for v in self._counts("C10").values()))
        self.assertEqual(m.get_profile_facts("C1"), {})
        self.assertEqual(m.profile.get_history("C1", "color"), [])
        self.assertEqual(m.get_episodes("C1"), [])
        self.assertNotIn("SESS-C1-2026-10-15", m.working._store)
        m.close()

    def test_deleted_data_is_gone_after_reopen_and_not_in_wal(self):
        m = MemoryService(enable_persistence=True, db_path=self.db)
        self._fill(m, "C1")
        m.delete_customer_data("C1")
        wal = self.db + "-wal"
        self.assertFalse(os.path.exists(wal) and os.path.getsize(wal) > 0)   # checkpoint sau khi xóa
        m.close()
        with open(self.db, "rb") as fh:
            raw = fh.read()
        self.assertNotIn("nguyên văn hội thoại".encode("utf-8"), raw)         # secure_delete: nội dung không còn trong file
        m2 = MemoryService(enable_persistence=True, db_path=self.db)
        self.assertEqual(m2.get_profile_facts("C1"), {})
        m2.close()

    def test_delete_also_clears_orchestrator_and_identity_state(self):
        c = build_components()
        orch, mem, resolver = c["orchestrator"], c["memory"], c["resolver"]
        t = c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0984726714")
        ident = resolver.resolve(t, memory=mem)
        brief = c["brief"].build(ident, "2026-10-17")
        orch.llm_client = FakeJSONLLM(chat={"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y",
                                                                         "price_vnd": 5200000, "payment": "COD"})], "text": "Dạ em đã lên đơn ạ."})
        orch.process_turn(t, brief, current_date="2026-10-17")
        sid = f"SESS-{ident.customer_id}-2026-10-17"
        self.assertIn(sid, orch._vaults)
        self.assertIn(sid, orch._write_cache)
        resolver.identity_map.link_contact("fb.x", ident.customer_id)
        mem.as_caller("Operator").delete_customer_data(ident.customer_id)        # qua mcp-memory chỉ Operator được xóa khách
        for store in (orch._vaults, orch._call_log, orch._write_cache, orch._activity):
            self.assertNotIn(sid, store)
        self.assertNotIn(ident.customer_id, resolver.identity_map._map.values())


class WorkingAndPathTest(unittest.TestCase):
    def test_unknown_working_field_is_an_error(self):
        from src.memory.working import WorkingMemoryStore
        with self.assertRaises(TypeError):
            WorkingMemoryStore().update("S1", last_intent="order")

    def test_orchestrator_saves_intent(self):  # N5
        c = build_components()
        orch = c["orchestrator"]
        orch.llm_client = FakeJSONLLM(chat={"calls": [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-AP-Y",
                                                                        "price_vnd": 5200000, "payment": "COD"})], "text": "Dạ em đã lên đơn ạ."})
        t = c["normalizer"].normalize("ok lên đơn", InputChannel.HOTLINE, "0984726714")
        b = c["brief"].build(c["resolver"].resolve(t, memory=c["memory"]), "2026-10-17")
        orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(c["memory"].get_working(f"SESS-{b.customer_id}-2026-10-17").intent, "order")

    def test_db_path_env_override_is_absolute(self):
        with mock.patch.dict(os.environ, {"HARNESS_DB_PATH": os.path.join("rel", "x.db")}):
            self.assertTrue(os.path.isabs(default_db_path()))
            self.assertTrue(default_db_path().endswith(os.path.join("rel", "x.db")))

    def test_default_path_independent_of_cwd(self):
        old = os.getcwd()
        try:
            a = default_db_path()
            os.chdir(tempfile.gettempdir())
            self.assertEqual(default_db_path(), a)
        finally:
            os.chdir(old)


class BriefMemoryTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()

    def _brief(self, date="2026-10-17", phone="0984726714"):
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, phone)
        ident = self.c["resolver"].resolve(t, memory=self.c["memory"])
        return ident, self.c["brief"].build(ident, date)

    def test_missing_order_id_is_dropped_with_warning(self):
        self.c["memory"].set_profile_fact("C001", "order_id", "OD999999")
        _, b = self._brief()
        self.assertNotIn("order_id", b.profile_facts)
        self.assertTrue(any("OD999999" in w for w in b.stale_warnings))

    def test_existing_order_id_is_kept(self):
        import mock_tools
        mock_tools.order_create("0984726714", "SKU-AP-Y", payment="COD", on="2026-10-15")
        self.c["memory"].set_profile_fact("C001", "order_id", "OD600001")
        _, b = self._brief()
        self.assertEqual(b.profile_facts.get("order_id"), "OD600001")
        self.assertFalse(b.stale_warnings)

    def test_ttl_applied_to_brief(self):
        mem = self.c["memory"]
        mem.set_profile_fact("C001", "room_area_m2", 25.0, ttl_days=30, observed_on="2026-09-01")
        _, b = self._brief("2026-10-17")
        self.assertNotIn("room_area_m2", b.profile_facts)
        self.assertNotIn("room_area_m2", b.must_not_ask)                 # fact đã hết hạn -> được phép hỏi lại
        _, b2 = self._brief("2026-09-20")
        self.assertEqual(b2.profile_facts.get("room_area_m2"), 25.0)

    def test_facts_under_raw_phone_key_are_ignored(self):               # D2: một khách một mã
        self.c["memory"].set_profile_fact("0984726714", "product_advised", "SKU-AP-X")
        _, b = self._brief()
        self.assertNotEqual(b.product_advised, "SKU-AP-X")

    def test_facts_by_channel_in_brief(self):
        mem = self.c["memory"]
        mem.begin_turn("call_1#turn1", call_date="2026-10-15", channel="fanpage")
        mem.set_profile_fact("C001", "product_advised", "SKU-AP-Y")
        mem.set_profile_fact("C001", "customer_name", "Hoa")            # không thuộc slot nghiệp vụ
        _, b = self._brief("2026-10-16")
        self.assertEqual(b.facts_by_channel.get("fanpage"), {"product_advised": "SKU-AP-Y"})


class DemoDbSafetyTest(unittest.TestCase):
    """main.py/seed dùng DB demo riêng; KHÔNG BAO GIỜ reset DB mặc định (production)."""

    def test_demo_path_differs_from_production_and_env_overrides(self):
        from src.memory.sqlite_store import demo_db_path, PRODUCTION_DB_PATH
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HARNESS_DB_PATH", None)
            self.assertTrue(demo_db_path().endswith(os.path.join("data", "demo.db")))
            self.assertNotEqual(os.path.normcase(demo_db_path()), os.path.normcase(PRODUCTION_DB_PATH))
        with mock.patch.dict(os.environ, {"HARNESS_DB_PATH": os.path.join(tempfile.gettempdir(), "x.db")}):
            self.assertEqual(demo_db_path(), os.path.abspath(os.path.join(tempfile.gettempdir(), "x.db")))

    def test_is_production_db_detection(self):
        from src.memory.sqlite_store import is_production_db, PRODUCTION_DB_PATH, CODE_DIR
        self.assertTrue(is_production_db(PRODUCTION_DB_PATH))
        self.assertTrue(is_production_db(os.path.join(CODE_DIR, "data", "..", "data", "harness_memory.db")))   # đường dẫn vòng
        self.assertTrue(is_production_db(PRODUCTION_DB_PATH.upper()))                                         # Windows không phân biệt hoa/thường
        self.assertFalse(is_production_db(os.path.join(CODE_DIR, "data", "demo.db")))
        self.assertFalse(is_production_db(None))

    def test_seed_reset_refused_on_production_db_and_nothing_deleted(self):
        from types import SimpleNamespace
        from scripts.seed_demo_db import seed_demo
        from src.memory.sqlite_store import PRODUCTION_DB_PATH
        fake = mock.MagicMock()
        fake.backend = SimpleNamespace(db_path=PRODUCTION_DB_PATH)
        with self.assertRaises(RuntimeError):
            seed_demo(fake, reset=True)
        fake.delete_customer_data.assert_not_called()
        fake.set_profile_fact.assert_not_called()

    def test_cli_refuses_reset_on_production_before_opening(self):
        from scripts.seed_demo_db import main
        from src.memory.sqlite_store import PRODUCTION_DB_PATH
        with mock.patch("src.memory.service.MemoryService") as opened:
            self.assertEqual(main(["--db", PRODUCTION_DB_PATH, "--reset"]), 2)
            opened.assert_not_called()

    def test_main_demo_leaves_production_db_untouched(self):
        import importlib
        from src.memory.sqlite_store import PRODUCTION_DB_PATH
        before = [(os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None
                  for p in (PRODUCTION_DB_PATH, PRODUCTION_DB_PATH + "-wal")]
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        env = {"HARNESS_DB_PATH": os.path.join(d, "demo.db"), "OPENAI_API_KEY": ""}
        import io, contextlib
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()) as out:
            import main as demo_main
            importlib.reload(demo_main)
            demo_main.main()
        self.assertIn("DB demo:", out.getvalue())
        self.assertTrue(os.path.exists(os.path.join(d, "demo.db")))
        after = [(os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None
                 for p in (PRODUCTION_DB_PATH, PRODUCTION_DB_PATH + "-wal")]
        self.assertEqual(before, after)


class BudgetVsQuotedPriceTest(unittest.TestCase):
    """Bước 15 giai đoạn A: LLM trích nhầm giá hệ thống đã báo (1.521.000đ) thành ngân sách của khách."""

    def test_budget_equal_to_quoted_price_without_cue_is_dropped(self):
        txt = "Bên Facebook báo chị giá 1.521.000 đúng không? Ok lấy size 41"
        self.assertEqual(validate_hard_slots({"budget_vnd": 1521000}, txt, known_prices={1521000}), {})

    def test_budget_with_budget_keyword_is_kept_even_if_equal(self):
        txt = "ngân sách chị tầm 1.521.000 thôi em"
        self.assertEqual(validate_hard_slots({"budget_vnd": 1521000}, txt, known_prices={1521000}), {"budget_vnd": 1521000})

    def test_budget_different_from_known_prices_is_kept(self):
        txt = "chị có 5.000.000 thôi, bên kia bán 4.590.000"
        self.assertEqual(validate_hard_slots({"budget_vnd": 5000000}, txt, known_prices={5200000}), {"budget_vnd": 5000000})

    def test_competitor_price_not_affected_by_known_prices(self):
        txt = "bên kia bán 4.590.000 thôi"
        self.assertEqual(validate_hard_slots({"competitor_price_vnd": 4590000}, txt, known_prices={4590000}), {"competitor_price_vnd": 4590000})

    def test_finalizer_does_not_store_quoted_price_as_budget(self):
        mem = MemoryService(enable_persistence=False)
        mem.set_profile_fact("C1", "price_quoted_vnd", 1521000)
        msgs = [{"role": "user", "content": "Bên Facebook báo chị giá 1.521.000 đúng không?"}, {"role": "assistant", "content": "Dạ đúng ạ."}]
        with mock.patch.dict(os.environ, LLM_ON):
            CallFinalizer(mem, HardSlotExtractor(FakeJSONLLM([{"budget_vnd": 1521000}]))).finalize(
                customer_id="C1", session_id="S", call_name="call_2", call_date="2026-10-16", channel="hotline",
                trigger="end", messages=msgs, tool_calls=[])
        self.assertNotIn("budget_vnd", mem.get_profile_facts("C1"))


class SlotRegressionFromRealRunTest(unittest.TestCase):
    """Lỗi chất lượng slot phát hiện ở bước 15 giai đoạn B."""

    def test_fee_in_thousands_is_not_a_shoe_size(self):
        self.assertNotIn("size", extract_easy_slots("Thế phí đổi size 20.000 à?", {}))
        self.assertNotIn("size", extract_easy_slots("phí đổi size 20 nghìn à", {}))
        self.assertNotIn("size", extract_easy_slots("size 20k thôi", {}))
        self.assertEqual(extract_easy_slots("lấy size 41 nhé", {}).get("size"), "41")
        self.assertEqual(extract_easy_slots("size M nhé", {}).get("size"), "M")
        self.assertNotIn("size", extract_easy_slots("size 99 nhé", {}))              # ngoài dải cỡ hợp lý

    def test_promo_code_prefers_real_promo_over_free_cod(self):
        from src.harness.orchestrator import HarnessOrchestrator as H
        applied = [{"promo_code": "COD-0", "type": "freecod", "discount_vnd": 0},
                   {"promo_code": "RUN-10", "type": "percent", "discount_vnd": 169000}]
        self.assertEqual(H._main_promo(applied), "RUN-10")
        gift = [{"promo_code": "COD-0", "type": "freecod", "discount_vnd": 0},
                {"promo_code": "GIFT-FILTER", "type": "gift", "discount_vnd": 0, "gift_sku": "SKU-AP-FLT-X"}]
        self.assertEqual(H._main_promo(gift), "GIFT-FILTER")
        self.assertEqual(H._main_promo([{"promo_code": "COD-0", "type": "freecod"}]), "COD-0")   # chỉ có KM chung thì dùng nó
        self.assertIsNone(H._main_promo([]))

    def test_promo_fact_persisted_from_quote(self):
        c = build_components()
        quote = {"name": "pricing.get_quote", "args": {"sku": "SKU-SN-RUN2"}, "result": {
            "final_price_vnd": 1521000, "list_price_vnd": 1690000,
            "applied_promos": [{"promo_code": "COD-0", "type": "freecod", "discount_vnd": 0},
                               {"promo_code": "RUN-10", "type": "percent", "discount_vnd": 169000}]}}
        c["orchestrator"]._persist_tool_grounded_facts("C017", [quote])
        self.assertEqual(c["memory"].get_profile_facts("C017")["promo_code"], "RUN-10")


class OpeningSentenceTest(unittest.TestCase):
    def test_natural_opening_has_product_name_short_date_and_clean_area(self):
        c = build_components()
        mem = c["memory"]
        mem.set_profile_fact("C001", "product_advised", "SKU-AP-Y")
        mem.set_profile_fact("C001", "price_quoted_vnd", 5200000)
        mem.set_profile_fact("C001", "room_area_m2", 25.0)
        mem.add_episode("C001", EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="x",
                                              product_advised="SKU-AP-Y", price_quoted_vnd=5200000))
        t = c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0984726714")
        b = c["brief"].build(c["resolver"].resolve(t, memory=mem), "2026-10-17")
        op = b.suggested_opening
        self.assertIn("bên em có tư vấn Máy lọc không khí AirPure Y", op)         # xưng hô KHÔNG đứng trước tên sản phẩm ("tư vấn chị Máy lọc…" đọc gượng)
        self.assertNotRegex(op, r"tư vấn (?:anh|chị|bạn|cô|chú) ")
        self.assertIn("hôm 15/10", op)
        self.assertNotIn("25m²", op)                                              # PB-01: tối đa 2 thông tin cũ (sản phẩm + giá); diện tích nằm ở bộ nhớ, không đọc lại
        self.assertIn("Em vừa kiểm tra hôm nay: còn hàng, giá 5.200.000đ", op)    # bước 13: câu gộp dữ kiện tra THẬT hôm nay
        self.assertNotIn("25.0", op)
        self.assertNotIn("2026-10-15", op)
        self.assertNotIn("AP-Y ", op.replace("AirPure Y", ""))


class SubsetEvaluationTest(unittest.TestCase):
    def test_subset_dir_contains_only_selected_scenarios(self):
        import run_eval
        tmp = run_eval._scenarios_subset_dir(run_eval.DEFAULT_SCENARIOS, ["SAMPLE-01", "SAMPLE-04"])
        self.addCleanup(tmp.cleanup)
        self.assertEqual(sorted(os.listdir(tmp.name)), ["SAMPLE-01.json", "SAMPLE-04.json"])

    def test_report_counts_only_selected_scenarios(self):
        import json as _json
        import subprocess
        import sys as _sys
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        code_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run([_sys.executable, os.path.join(code_dir, "run_eval.py"), "--only", "SAMPLE-01", "--out-dir", d],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=code_dir,
                              env={**os.environ, "PYTHONUTF8": "1", "OPENAI_API_KEY": ""})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(os.path.join(d, "report.json"), encoding="utf-8") as fh:
            self.assertEqual(_json.load(fh)["n_scenarios"], 1)


class SeedScriptTest(unittest.TestCase):
    def setUp(self):
        self.dir, self.db = tmp_db()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_seed_is_idempotent_and_single_customer_id(self):
        from scripts.seed_demo_db import seed_demo, DEMO_CUSTOMER_ID
        m = MemoryService(enable_persistence=True, db_path=self.db)
        first = seed_demo(m)
        second = seed_demo(m)
        third = seed_demo(m)
        self.assertEqual((first["episodes"], first["facts"]), (second["episodes"], second["facts"]))
        self.assertEqual(second, {**third})
        m.close()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("select count(*) from episodic_records").fetchone()[0], 1)
        self.assertEqual(c.execute("select count(distinct customer_id) from customer_profiles").fetchone()[0], 1)
        self.assertEqual(c.execute("select customer_id from customer_profiles limit 1").fetchone()[0], DEMO_CUSTOMER_ID)
        self.assertEqual(c.execute("select count(*) from customer_profiles").fetchone()[0],
                         c.execute("select count(*) from customer_profiles where superseded=0").fetchone()[0])
        c.close()

    def test_reset_removes_later_calls_of_demo_customer(self):
        from scripts.seed_demo_db import seed_demo, DEMO_CUSTOMER_ID
        m = MemoryService(enable_persistence=True, db_path=self.db)
        seed_demo(m)
        m.add_episode(DEMO_CUSTOMER_ID, EpisodeRecord(session_id="SESS-C001-2026-10-17", call_index=2, call_date="2026-10-17", channel="hotline", customer_goal=""))
        self.assertEqual(seed_demo(m)["episodes"], 2)
        self.assertEqual(seed_demo(m, reset=True)["episodes"], 1)
        m.close()

    def test_cli_main_runs(self):
        from scripts.seed_demo_db import main
        self.assertEqual(main(["--db", self.db, "--reset"]), 0)
        self.assertEqual(main(["--db", self.db]), 0)


# =====================================================================  bộ trích 2 tầng
class EasySlotsTest(unittest.TestCase):
    def test_slots(self):
        s = extract_easy_slots("phòng 25m2 nhà có bé nhỏ, ngân sách tầm 5.000.000, lấy size 41 màu đen nhé",
                               {"room_area_m2": 25.0, "has_children": True})
        self.assertEqual(s, {"room_area_m2": 25.0, "has_children": True, "budget_vnd": 5000000, "size": "41", "color": "den"})

    def test_discount_is_not_budget(self):
        self.assertNotIn("budget_vnd", extract_easy_slots("hôm trước bên em giảm 500.000 đúng không", {}))

    def test_upper_size_color_folding_and_unknown_color(self):
        self.assertEqual(extract_easy_slots("cho anh size xl", {}).get("size"), "XL")
        self.assertEqual(extract_easy_slots("màu Trắng nhé", {}).get("color"), "trang")
        self.assertNotIn("color", extract_easy_slots("màu gì cũng được", {}))

    def test_callback_slot(self):
        s = extract_easy_slots("gọi lại mai", {"callback_hint": {"date": "2026-10-16", "time": "15:00"}})
        self.assertEqual(s["callback_at"], "2026-10-16 15:00")

    def test_nothing_to_extract(self):
        self.assertEqual(extract_easy_slots("alo em ơi", {}), {})

    def test_no_llm_involved(self):
        spy = FakeJSONLLM()
        extract_easy_slots("ngân sách 5.000.000", {})
        self.assertEqual(spy.json_calls, [])


class HardSlotValidationTest(unittest.TestCase):
    def test_amounts_must_be_grounded_in_customer_text(self):
        raw = {"budget_vnd": 5000000, "competitor_price_vnd": 4590000, "blocker": "so sanh gia"}
        ok = validate_hard_slots(raw, "bên kia bán 4.590.000 thôi, ngân sách em 5.000.000")
        self.assertEqual(ok, {"blocker": "so sanh gia", "budget_vnd": 5000000, "competitor_price_vnd": 4590000})
        bad = validate_hard_slots(raw, "giá bao nhiêu vậy em")                      # LLM bịa số khách không nói
        self.assertEqual(bad, {"blocker": "so sanh gia"})

    def test_types_and_pii_cleaned(self):
        out = validate_hard_slots({"blocker": "cho vo goi 0912345678 va stk 1903456789012", "budget_vnd": "5 triệu", "objection": 7,
                                   "customer_goal": None}, "x")
        self.assertIn("0912345678", out["blocker"])                  # SĐT 10 số được phép
        self.assertIn("[REDACTED]", out["blocker"])                  # STK bị che
        self.assertNotIn("budget_vnd", out)
        self.assertNotIn("objection", out)

    def test_bool_and_small_numbers_rejected(self):
        self.assertEqual(validate_hard_slots({"budget_vnd": True, "competitor_price_vnd": 500}, "500 5.000.000"), {})


class HardSlotExtractorTest(unittest.TestCase):
    def test_disabled_by_env_or_missing_llm(self):
        with mock.patch.dict(os.environ, {"MEMORY_EXTRACTOR_LLM": "0"}):
            self.assertFalse(HardSlotExtractor(FakeJSONLLM()).enabled)
        with mock.patch.dict(os.environ, LLM_ON):
            self.assertTrue(HardSlotExtractor(FakeJSONLLM()).enabled)
            self.assertFalse(HardSlotExtractor(None).enabled)
            unavailable = FakeJSONLLM()
            unavailable.available = False
            self.assertFalse(HardSlotExtractor(unavailable).enabled)

    def test_llm_error_is_swallowed(self):
        with mock.patch.dict(os.environ, LLM_ON):
            ex = HardSlotExtractor(FakeJSONLLM([RuntimeError("boom")]))
            slots, usage = ex.extract([{"role": "user", "content": "để hỏi chồng"}])
        self.assertEqual((slots, usage), ({}, None))

    def test_no_customer_text_no_call(self):
        llm = FakeJSONLLM()
        with mock.patch.dict(os.environ, LLM_ON):
            HardSlotExtractor(llm).extract([{"role": "assistant", "content": "Dạ em chào chị ạ"}])
        self.assertEqual(llm.json_calls, [])


MSGS_1 = [{"role": "user", "content": "để chị hỏi chồng đã, bên kia bán 4.590.000 thôi"},
          {"role": "assistant", "content": "Dạ vâng ạ."}]
MSGS_2 = [{"role": "user", "content": "ngân sách chị 5.000.000 nhé"}, {"role": "assistant", "content": "Dạ em ghi nhận ạ."}]


class CallFinalizerTest(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryService(enable_persistence=False)
        self.mem.set_profile_fact("C1", "product_advised", "SKU-AP-Y")
        self.mem.set_profile_fact("C1", "price_quoted_vnd", 5200000)

    def _fin(self, llm):
        return CallFinalizer(self.mem, HardSlotExtractor(llm))

    def _run(self, fin, trigger, messages, tool_calls=None, sid="SESS-C1-2026-10-15"):
        return fin.finalize(customer_id="C1", session_id=sid, call_name="call_1", call_date="2026-10-15", channel="hotline",
                            trigger=trigger, messages=messages, tool_calls=tool_calls or [])

    def test_end_trigger_one_llm_call_writes_slots_and_episode(self):
        llm = FakeJSONLLM([{"blocker": "can hoi chong", "competitor_price_vnd": 4590000, "customer_goal": "hoi may loc"}])
        with mock.patch.dict(os.environ, LLM_ON):
            res = self._run(self._fin(llm), "end", MSGS_1)
        self.assertEqual(len(llm.json_calls), 1)
        self.assertTrue(res.llm_called)
        f = self.mem.get_profile_facts("C1", on_date="2026-10-16")
        self.assertEqual((f["blocker"], f["competitor_price_vnd"]), ("can hoi chong", 4590000))
        ep = self.mem.get_episodes("C1")[0]
        self.assertEqual((ep.outcome, ep.product_advised, ep.price_quoted_vnd, ep.blocker, ep.call_index),
                         ("hen_goi_lai", "SKU-AP-Y", 5200000, "can hoi chong", 1))
        self.assertEqual(ep.customer_goal, "hoi may loc")

    def test_slot_ttl_applied(self):
        with mock.patch.dict(os.environ, LLM_ON):
            self._run(self._fin(FakeJSONLLM([{"blocker": "can hoi chong"}])), "end", MSGS_1)
        self.assertIn("blocker", self.mem.get_profile_facts("C1", on_date="2026-10-20"))
        self.assertNotIn("blocker", self.mem.get_profile_facts("C1", on_date="2027-01-01"))   # TTL 60 ngày

    def test_handoff_then_end_only_new_messages_second_time(self):
        llm = FakeJSONLLM([{"blocker": "can hoi chong"}, {"budget_vnd": 5000000}])
        fin = self._fin(llm)
        with mock.patch.dict(os.environ, LLM_ON):
            self._run(fin, "handoff", MSGS_1)
            self._run(fin, "end", MSGS_1 + MSGS_2)
        self.assertEqual(len(llm.json_calls), 2)                          # mỗi thời điểm ≤ 1 lần
        second_prompt = llm.json_calls[1][1]["content"]
        self.assertIn("ngân sách chị 5.000.000", second_prompt)
        self.assertNotIn("hỏi chồng", second_prompt)                      # phần đã trích lúc chuyển máy không bị trích lại

    def test_end_without_new_messages_does_not_call_llm(self):
        llm = FakeJSONLLM([{"blocker": "can hoi chong"}])
        fin = self._fin(llm)
        with mock.patch.dict(os.environ, LLM_ON):
            self._run(fin, "handoff", MSGS_1)
            res = self._run(fin, "end", MSGS_1)
        self.assertEqual(len(llm.json_calls), 1)
        self.assertFalse(res.llm_called)

    def test_handoff_and_end_share_one_episode(self):
        fin = self._fin(FakeJSONLLM())
        self._run(fin, "handoff", MSGS_1)
        self._run(fin, "end", MSGS_1)
        eps = self.mem.get_episodes("C1")
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0].summary.split(";")[0], "[end]")

    def test_outcomes_by_trigger_and_tools(self):
        fin = self._fin(FakeJSONLLM())
        self.assertEqual(self._run(fin, "handoff", MSGS_1, sid="S-h").episode.outcome, "chuyen_may")
        self.assertEqual(self._run(fin, "timeout", MSGS_1, sid="S-t").episode.outcome, "ngat_cuoc")
        order = [{"name": "order.create", "result": {"status": "created", "order_id": "OD600001"}}]
        res = self._run(fin, "end", MSGS_1, tool_calls=order, sid="S-o")
        self.assertEqual(res.episode.outcome, "chot_don")
        self.assertIn("OD600001", res.episode.summary)

    def test_call_index_counts_other_sessions(self):
        fin = self._fin(FakeJSONLLM())
        self._run(fin, "end", MSGS_1, sid="S-a")
        res = fin.finalize(customer_id="C1", session_id="S-b", call_name="call_2", call_date="2026-10-17", channel="hotline",
                           trigger="end", messages=[], tool_calls=[])
        self.assertEqual(res.episode.call_index, 2)

    def test_llm_failure_still_writes_episode(self):
        with mock.patch.dict(os.environ, LLM_ON):
            res = self._run(self._fin(FakeJSONLLM([RuntimeError("down")])), "end", MSGS_1)
        self.assertEqual(res.hard_slots, {})
        self.assertEqual(len(self.mem.get_episodes("C1")), 1)

    def test_ungrounded_amount_not_stored(self):
        with mock.patch.dict(os.environ, LLM_ON):
            self._run(self._fin(FakeJSONLLM([{"competitor_price_vnd": 3999000}])), "end", MSGS_1)
        self.assertNotIn("competitor_price_vnd", self.mem.get_profile_facts("C1"))

    def test_episode_and_slots_have_provenance_and_no_pii(self):
        self.mem.begin_turn("call_1#end", call_date="2026-10-15", channel="hotline")
        with mock.patch.dict(os.environ, LLM_ON):
            self._run(self._fin(FakeJSONLLM([{"blocker": "can hoi chong"}])), "end", MSGS_1)
        writes = self.mem.drain_writes()
        keys = {w["key"] for w in writes}
        self.assertIn("blocker", keys)
        self.assertTrue(any(k.startswith("episode:") for k in keys))
        self.assertTrue(all(w["source"] == "call_1#end" and w["source_call"] == "call_1" for w in writes))

    def test_invalid_trigger_rejected(self):
        with self.assertRaises(ValueError):
            self._run(self._fin(FakeJSONLLM()), "weird", MSGS_1)

    def test_no_llm_configured_still_finalizes(self):
        res = self._run(self._fin(None), "end", MSGS_1)
        self.assertFalse(res.llm_called)
        self.assertEqual(len(self.mem.get_episodes("C1")), 1)


class OrchestratorFinalizeTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()
        self.orch = self.c["orchestrator"]

    def _turn(self, text="alo", date="2026-10-17", phone="0984726714"):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, phone, reference_date=date)
        return t, self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)

    HANDOFF = ("handoff.transfer", {"brief": {
        "customer_phone": "CURRENT_CUSTOMER", "customer_name": "Hoa", "escalation_reason": "hoi thong tin y te",
        "conversation_summary": "Khach hoi may hut sua", "product_advised": "SKU-AP-Y", "price_quoted_vnd": 5200000,
        "open_questions": ["an toan khi dung thuoc"], "next_action": "nhan vien goi lai", "generated_at": "2026-10-17T10:00:00"}})

    def test_handoff_in_turn_triggers_finalize_and_end_only_new_part(self):
        # câu JSON đầu tiên là chốt chuyển máy (khách PHẢI tự yêu cầu), hai câu sau là trích slot khó
        llm = FakeJSONLLM([{"authorized": True, "basis": "asked", "quote": "chuyển cho nhân viên"}, {"blocker": "can tu van y te"}, {"budget_vnd": 5000000}],
                          chat={"calls": [self.HANDOFF], "text": "Dạ em chuyển máy ạ."})
        self.orch.llm_client = llm
        with mock.patch.dict(os.environ, LLM_ON):
            t, b = self._turn("chị hỏi máy này dùng khi uống thuốc được không, chuyển cho nhân viên giúp chị")
            _, tool_calls, meta = self.orch.process_turn(t, b, current_date="2026-10-17", call_name="call_1")
            self.assertEqual(meta["memory_extraction"]["trigger"], "handoff")
            self.assertTrue(meta["memory_extraction"]["llm_called"])
            self.assertEqual(self.c["memory"].get_episodes(b.customer_id)[0].outcome, "chuyen_may")
            self.assertEqual(len(llm.json_calls), 2)                             # chốt chuyển máy + trích slot
            llm.chat = {"calls": [], "text": "Dạ vâng ạ."}
            t2, b2 = self._turn("ngân sách chị 5.000.000 nhé")
            self.assertEqual(b2.previous_calls_count, 0)                         # episode chốt giữa chừng là của CHÍNH cuộc gọi này, không phải cuộc gọi trước
            self.orch.process_turn(t2, b2, current_date="2026-10-17", call_name="call_1")
            res = self.orch.finalize_call(b.customer_id, "2026-10-17", "call_1", "hotline", trigger="end")
        self.assertEqual(len(llm.json_calls), 3)
        self.assertNotIn("uống thuốc", llm.json_calls[2][1]["content"])
        self.assertIn("5.000.000", llm.json_calls[2][1]["content"])
        self.assertEqual(len(self.c["memory"].get_episodes(b.customer_id)), 1)   # cùng 1 episode, được cập nhật
        self.assertEqual(self.c["memory"].get_profile_facts(b.customer_id)["budget_vnd"], 5000000)
        self.assertTrue(res.llm_called)

    def test_end_clears_per_call_state(self):
        self.orch.llm_client = FakeJSONLLM(chat={"calls": [], "text": "Dạ vâng ạ."})
        t, b = self._turn()
        self.orch.process_turn(t, b, current_date="2026-10-17")
        sid = f"SESS-{b.customer_id}-2026-10-17"
        self.assertIn(sid, self.orch._vaults)
        self.orch.finalize_call(b.customer_id, "2026-10-17", "call_1", "hotline", trigger="end")
        for store in (self.orch._vaults, self.orch._call_log, self.orch._write_cache, self.orch._activity):
            self.assertNotIn(sid, store)

    def test_sweep_idle_finalizes_timeout_once(self):
        self.orch.llm_client = FakeJSONLLM(chat={"calls": [], "text": "Dạ vâng ạ."})
        t, b = self._turn("cho chị xem máy lọc")
        self.orch.process_turn(t, b, current_date="2026-10-17", call_name="call_1")
        ts = self.orch._activity[f"SESS-{b.customer_id}-2026-10-17"]["ts"]
        self.assertEqual(self.orch.sweep_idle(now=ts + 10, idle_seconds=1800), [])           # chưa quá hạn
        results = self.orch.sweep_idle(now=ts + 1801, idle_seconds=1800)
        self.assertEqual([r.trigger for r in results], ["timeout"])
        self.assertEqual(self.c["memory"].get_episodes(b.customer_id)[0].outcome, "ngat_cuoc")
        self.assertEqual(self.orch.sweep_idle(now=ts + 99999, idle_seconds=1800), [])        # không chốt lần 2

    def test_easy_slots_extracted_each_turn_without_llm_call(self):
        llm = FakeJSONLLM(chat={"calls": [], "text": "Dạ vâng ạ."})
        self.orch.llm_client = llm
        t, b = self._turn("phòng 30m2 nhà có bé nhỏ, ngân sách 5 triệu, lấy màu đen size 41")
        self.orch.process_turn(t, b, current_date="2026-10-17", call_name="call_1")
        f = self.c["memory"].get_profile_facts(b.customer_id)
        self.assertEqual((f["room_area_m2"], f["has_children"], f["budget_vnd"], f["color"], f["size"]), (30.0, True, 5000000, "den", "41"))
        self.assertEqual(llm.json_calls, [])                                  # không có lần gọi trích LLM nào mỗi lượt

    def test_claims_and_questions_come_from_final_text(self):
        self.orch.llm_client = FakeJSONLLM(chat={"calls": [("pricing.get_quote", {"sku": "SKU-AP-Y"})],
                                                 "text": "Dạ máy giá 5.200.000đ ạ. Phòng mình rộng bao nhiêu mét vuông ạ?"})
        t, b = self._turn()
        _, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertIn(("price_vnd", 5200000), {(c["field"], c["value"]) for c in meta["claims"]})
        self.assertEqual([(q["slot"], q["type"]) for q in meta["questions"]], [("room_area_m2", "open")])

    def test_guardrail_replacement_is_what_gets_extracted(self):
        self.orch.llm_client = FakeJSONLLM(chat={"calls": [], "text": "Dạ máy giá 3.900.000đ thôi ạ."})
        t, b = self._turn()
        final, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertNotIn(("price_vnd", 3900000), {(c["field"], c["value"]) for c in meta["claims"]})   # câu bịa đã bị thay


# =====================================================================  runner / pipeline
class RunnerExtractionTest(unittest.TestCase):
    """Baseline không chạy bộ trích; full chốt cuộc gọi cuối mỗi call và gắn kết quả vào lượt cuối của call."""

    def _run(self, config):
        import json
        from src.eval.runner import ScenarioRunner
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        out = os.path.join(d, f"{config}.jsonl")
        with mock.patch.object(CallFinalizer, "finalize", autospec=True, side_effect=CallFinalizer.finalize) as spy:
            ScenarioRunner(PUBLIC_DIR).run_all(config=config, output_trace_file=out, only=["SAMPLE-01"])
        with open(out, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        return spy, rows

    def test_baseline_never_finalizes(self):
        spy, rows = self._run("baseline_no_memory")
        self.assertEqual(spy.call_count, 0)
        self.assertFalse([r for r in rows if "memory_extractor" in r])
        self.assertFalse([w for r in rows for w in r["memory_writes"] if str(w["key"]).startswith("episode:")])

    def test_full_finalizes_once_per_call_and_writes_episode(self):
        spy, rows = self._run("full")
        self.assertEqual(spy.call_count, 2)                                    # SAMPLE-01 có 2 cuộc gọi
        for call in ("call_1", "call_2"):
            last = [r for r in rows if r["call"] == call][-1]
            self.assertEqual(last["memory_extractor"]["trigger"], "end")
            self.assertTrue(any(w["key"].startswith("episode:") for w in last["memory_writes"]))
            self.assertTrue(all(w["source_call"] == call for w in last["memory_writes"] if w["key"].startswith("episode:")))
            others = [r for r in rows if r["call"] == call][:-1]
            self.assertFalse([r for r in others if "memory_extractor" in r])
        self.assertEqual([r["turn"] for r in rows if r["call"] == "call_1"], sorted(r["turn"] for r in rows if r["call"] == "call_1"))

    def test_full_call2_brief_now_knows_previous_call(self):
        _, rows = self._run("full")
        c2 = [r for r in rows if r["call"] == "call_2" and r["turn"] == 1][0]
        self.assertTrue(c2["_brief_must_carry_over"])                          # nhớ do hệ thống TỰ ghi (không nạp đáp án)

    def test_writes_have_channel_provenance_in_trace(self):
        _, rows = self._run("full")
        w = [w for r in rows for w in r["memory_writes"] if not w["key"].startswith("episode:")][0]
        self.assertEqual(w["source_channel"], "hotline")
        self.assertTrue(w["source_call"].startswith("call_"))


class PipelineEndCallTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.db = os.path.join(self.dir, "p.db")
        patcher = mock.patch.dict(os.environ, {"HARNESS_DB_PATH": self.db, "OPENAI_API_KEY": ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        from pipeline import CallCenterHarnessPipeline
        self.pipeline = CallCenterHarnessPipeline(trace_file=os.path.join(self.dir, "t.jsonl"))

    def test_end_call_writes_episode_and_close_checkpoints(self):
        self.pipeline.handle_incoming_request("alo cho chị hỏi máy lọc", "0984726714", call_date="2026-10-17", call_name="call_1", turn_num=1)
        out = self.pipeline.end_call("0984726714")
        self.assertTrue(out["finalized"])
        self.assertEqual(out["episode"].call_date, "2026-10-17")
        self.assertFalse(self.pipeline.end_call("0984726714")["finalized"])           # đã chốt rồi
        self.pipeline.close()
        wal = self.db + "-wal"
        self.assertFalse(os.path.exists(wal) and os.path.getsize(wal) > 0)
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("select count(*) from episodic_records").fetchone()[0], 1)
        c.close()

    def test_timeout_end_call_marks_outcome(self):
        self.pipeline.handle_incoming_request("alo", "0984726714", call_date="2026-10-17", call_name="call_1", turn_num=1)
        out = self.pipeline.end_call("0984726714", trigger="timeout")
        self.assertEqual(out["episode"].outcome, "ngat_cuoc")

    def test_failed_turn_rolls_back_db_writes_and_reraises(self):
        with mock.patch.object(self.pipeline.orchestrator, "process_turn", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.pipeline.handle_incoming_request("alo", "0984726714", call_date="2026-10-17", call_name="call_1", turn_num=1)
        self.pipeline.close()
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("select count(*) from customer_profiles").fetchone()[0], 0)   # channels_seen... đã bị hủy
        c.close()

    def test_sweep_idle_finalizes_open_calls(self):
        self.pipeline.handle_incoming_request("alo", "0984726714", call_date="2026-10-17", call_name="call_1", turn_num=1)
        self.assertEqual(self.pipeline.sweep_idle(idle_seconds=0), 1)
        self.assertEqual(self.pipeline.sweep_idle(idle_seconds=0), 0)
        self.assertEqual(self.pipeline.end_call("0984726714")["finalized"], False)


if __name__ == "__main__":
    unittest.main()
