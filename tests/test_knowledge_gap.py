"""Knowledge Gap Loop: gom thiếu sót từ trace, chỉ mục đã duyệt mới vào kho bổ sung + kịch bản hồi quy."""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import knowledge_gap as kg
from src.memory.policy_loader import _parse_file


def row(chunks, query="gói miễn công lắp đặt"):
    return {"scenario_id": "S", "call": "call_1", "turn": 1, "customer_text": "Có gói miễn công lắp đặt không em?",
            "tool_calls": [{"name": "search_policy", "args": {"query": query}, "result": {"chunks": [{"chunk_id": c} for c in chunks]}}]}


class KnowledgeGapTest(unittest.TestCase):
    def test_only_unanswered_lookups_are_gaps_and_duplicates_merge(self):
        found = kg.find_gaps([row(["[PB-05]"]), row(["[BH-03]"]), row([]), row(["[PB-05]"], "Gói miễn công lắp đặt")])
        self.assertEqual(len(found), 3)
        gaps = kg.merge([], found)
        self.assertEqual([(g["id"], g["seen"], g["status"]) for g in gaps], [("KG-01", 3, "pending")])

    def test_apply_writes_only_approved_entries(self):
        gaps = kg.merge([], kg.find_gaps([row(["[PB-05]"]), row(["[PB-05]"], "giá sàn đại lý")]))
        gaps[0].update(status="approved", answer="Miễn công lắp đặt nội thành cho máy lọc nước.", must_say=["miễn công"])
        with tempfile.TemporaryDirectory() as d:
            ok = kg.apply(gaps, os.path.join(d, "kb"), os.path.join(d, "t"))
            self.assertEqual([g["id"] for g in ok], ["KG-01"])                       # mục chờ duyệt (dò giá sàn) KHÔNG vào kho
            chunks = _parse_file(os.path.join(d, "kb", "bo-sung-tri-thuc.md"), "bo-sung-tri-thuc.md")
            self.assertEqual([(c.chunk_id, c.access) for c in chunks], [("[BS-01]", "public")])
            self.assertIn("Miễn công lắp đặt", chunks[0].content)
            with open(os.path.join(d, "t", "KG-01.json"), encoding="utf-8") as f:
                scen = json.load(f)
            self.assertEqual(scen["calls"]["call_1"]["success_if"]["must_say_any"], ["miễn công"])
            self.assertEqual(os.listdir(os.path.join(d, "t")), ["KG-01.json"])


if __name__ == "__main__":
    unittest.main()


class LazyLoadAndRetentionTest(unittest.TestCase):
    """D12: hồ sơ/episode đọc THEO KHÁCH khi cần; D10: phiên làm việc bỏ dở quá hạn bị xóa khi mở DB."""

    def test_only_touched_customer_is_loaded_and_old_working_sessions_are_purged(self):
        from src.memory.sqlite_store import SQLiteStore
        from src.memory.profile import ProfileMemoryStore
        from src.memory.episodic import EpisodicMemoryStore, EpisodeRecord
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            path = os.path.join(d, "t.db")
            s = SQLiteStore(path)
            p, e = ProfileMemoryStore(s), EpisodicMemoryStore(s)
            p.set_fact("C1", "budget_vnd", 5000000)
            p.set_fact("C2", "budget_vnd", 7000000)
            e.append("C1", EpisodeRecord(session_id="S1", call_index=1, call_date="2026-10-15", channel="hotline", customer_goal="hỏi giá"))
            s.save_working("SESS-old", {"x": 1})
            s._conn.execute("UPDATE working_sessions SET updated_at='2020-01-01T00:00:00' WHERE session_id='SESS-old'")
            s.save_working("SESS-new", {"x": 1})
            s.close()
            s2 = SQLiteStore(path)
            p2, e2 = ProfileMemoryStore(s2), EpisodicMemoryStore(s2)
            self.assertEqual(p2._store, {})                                    # chưa nạp gì lúc khởi tạo
            self.assertEqual(p2.get_active_facts("C1"), {"budget_vnd": 5000000})
            self.assertEqual(set(p2._store), {"C1"})                           # C2 không bị nạp theo
            self.assertEqual([x.session_id for x in e2.get_episodes("C1")], ["S1"])
            self.assertIsNone(s2.load_working("SESS-old"))
            self.assertEqual(s2.load_working("SESS-new"), {"x": 1})
            s2.close()
