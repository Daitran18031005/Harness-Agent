"""Bước 9 — Bộ nhớ & DB (A4, A5, N5, N11, D1, D2, D5, D8, D9, D14)."""
import os
import shutil
import sqlite3
import tempfile
import unittest
from tests import _helpers  # noqa: F401
from src.memory.service import MemoryService
from src.memory.episodic import EpisodeRecord
from src.memory.working import WorkingMemoryStore


class MemoryInMemoryTest(unittest.TestCase):
    def test_ttl_applied_on_read(self):  # A5
        m = MemoryService(enable_persistence=False)
        m.set_profile_fact("C999", "address", "Hà Nội", ttl_days=180, observed_on="2026-01-01")
        self.assertIn("address", m.get_profile_facts("C999", on_date="2026-03-01"))
        self.assertNotIn("address", m.get_profile_facts("C999", on_date="2026-10-15"))

    def test_supersede_keeps_history(self):
        m = MemoryService(enable_persistence=False)
        m.set_profile_fact("C1", "color", "đen")
        m.set_profile_fact("C1", "color", "trắng")
        self.assertEqual(m.get_profile_facts("C1")["color"], "trắng")
        hist = m.profile.get_history("C1", "color")
        self.assertEqual([h.value for h in hist], ["đen", "trắng"])
        self.assertTrue(hist[0].superseded)

    def test_write_log_ops(self):
        m = MemoryService(enable_persistence=False)
        m.begin_turn("call_1#turn1", "C1")
        m.set_profile_fact("C1", "color", "đen")
        m.set_profile_fact("C1", "color", "đen")      # trùng giá trị -> không ghi lại
        m.set_profile_fact("C1", "color", "trắng")
        ops = [(w["key"], w["op"]) for w in m.drain_writes()]
        self.assertEqual(ops, [("color", "set"), ("color", "supersede")])

    def test_working_intent_saved(self):  # N5
        st = WorkingMemoryStore().update("S1", intent="order")
        self.assertEqual(st.intent, "order")

    def test_delete_customer_everything(self):  # N11, D9
        m = MemoryService(enable_persistence=False)
        m.set_profile_fact("C1", "color", "đen")
        m.add_episode("C1", EpisodeRecord(session_id="S", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="x"))
        m.set_working("SESS-C1-2026-10-15", current_turn=2)
        m.delete_customer_data("C1")
        self.assertEqual(m.get_profile_facts("C1"), {})
        self.assertEqual(m.get_episodes("C1"), [])
        self.assertNotIn("SESS-C1-2026-10-15", m.working._store)


class MemorySQLiteTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "t.db")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_no_duplicate_active_rows(self):  # D1
        m = MemoryService(enable_persistence=True, db_path=self.db)
        for _ in range(3):
            m.set_profile_fact("C1", "customer_name", "Hoa")
        m.set_profile_fact("C1", "customer_name", "Hoa B")
        m.close()
        c = sqlite3.connect(self.db)
        active = c.execute("select count(*) from customer_profiles where customer_id='C1' and key='customer_name' and superseded=0").fetchone()[0]
        total = c.execute("select count(*) from customer_profiles where customer_id='C1' and key='customer_name'").fetchone()[0]
        c.close()
        self.assertEqual(active, 1)
        self.assertEqual(total, 2)

    def test_episode_unique_and_ordered(self):  # D5
        m = MemoryService(enable_persistence=True, db_path=self.db)
        ep2 = EpisodeRecord(session_id="S2", call_index=2, call_date="2026-10-17", channel="hotline", customer_goal="b")
        ep1 = EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="a")
        m.add_episode("C1", ep2); m.add_episode("C1", ep1); m.add_episode("C1", ep1)
        m.close()
        m2 = MemoryService(enable_persistence=True, db_path=self.db)
        self.assertEqual([e.session_id for e in m2.get_episodes("C1")], ["S1", "S2"])
        m2.close()

    def test_data_in_main_db_after_close(self):  # D8
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.set_profile_fact("C1", "color", "đen")
        m.close()
        self.assertFalse(os.path.exists(self.db + "-wal") and os.path.getsize(self.db + "-wal") > 0)

    def test_delete_clears_all_tables(self):  # D9
        m = MemoryService(enable_persistence=True, db_path=self.db)
        m.set_profile_fact("C1", "color", "đen")
        m.add_episode("C1", EpisodeRecord(session_id="S", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="x"))
        m.set_working("SESS-C1-2026-10-15", current_turn=2)
        m.backend.save_identity_link("HASH-x", "C1")
        m.delete_customer_data("C1")
        m.close()
        c = sqlite3.connect(self.db)
        for table, col in [("customer_profiles", "customer_id"), ("episodic_records", "customer_id"),
                           ("identity_links", "master_customer_id")]:
            self.assertEqual(c.execute(f"select count(*) from {table} where {col}='C1'").fetchone()[0], 0, table)
        self.assertEqual(c.execute("select count(*) from working_sessions where session_id like 'SESS-C1-%'").fetchone()[0], 0)
        c.close()

    def test_default_db_path_absolute(self):  # D14
        from src.memory.sqlite_store import default_db_path
        self.assertTrue(os.path.isabs(default_db_path()))


if __name__ == "__main__":
    unittest.main()
