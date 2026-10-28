"""Hồi quy thường trực cho 3 mục kiểm (2026-10-27): số nói bằng chữ · đổi ngày bắt đầu cuộc mới và chốt cuộc cũ · Call Brief cuộc 2 mang blocker/tên/xưng hô cuộc 1."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from tests import _helpers  # noqa: F401
from tests._helpers import advisor_suggests
from src.channels.normalizer import InputChannel, RequestNormalizer, itn_small_numbers

PHONE = "0911222333"


class SpokenSmallNumbersTest(unittest.TestCase):
    def test_numbers_next_to_units_dates_and_sizes_become_digits(self):
        cases = {"máy lọc nước mười lõi giá bao nhiêu": "máy lọc nước 10 lõi giá bao nhiêu", "giao hôm mười lăm tháng mười nhé": "giao hôm 15 tháng 10 nhé",
                 "bảo hành mười hai tháng": "bảo hành 12 tháng", "phòng hai mươi lăm mét vuông": "phòng 25 mét vuông", "bé ba tuổi, size ba tám": "bé 3 tuổi, size 38",
                 "mùng năm tháng ba": "mùng 5 tháng 3", "ngày hai mươi mốt": "ngày 21", "size ba mươi tám": "size 38"}
        for raw, want in cases.items():
            self.assertEqual(itn_small_numbers(raw), want, raw)

    def test_ambiguous_words_are_left_alone(self):
        for t in ("thứ hai tháng sau", "năm ngoái mua hai cái", "size M", "em muốn mua hai", "mười"):
            self.assertEqual(itn_small_numbers(t), t, t)

    def test_through_the_normalizer_and_with_money_and_phone(self):
        n = RequestNormalizer()
        out = n.normalize("máy mười lõi, tổng sáu triệu tám, số không chín tám sáu tám tám sáu một một ba", InputChannel.HOTLINE, "0900000001").normalized_text
        self.assertIn("10 lõi", out)
        self.assertIn("6.800.000", out)
        self.assertIn("0986886113", out)
        e = n.normalize("phòng hai mươi mét vuông nhà có bé nhỏ", InputChannel.HOTLINE, "0900000001")
        self.assertEqual(e.extracted_entities.get("room_area_m2"), 20.0)               # slot diện tích chạy được từ lời nói bằng chữ


class NameExtractionTest(unittest.TestCase):
    def test_name_stops_at_punctuation_and_pronouns(self):
        from src.memory.memory_extractor import extract_customer_name as f
        self.assertEqual(f("Chị tên Lan, chị hỏi máy lọc"), "Lan")                       # lỗi thật: "Lan Chị"
        self.assertEqual(f("tôi tên Lan tôi muốn mua"), "Lan")
        self.assertEqual(f("mình tên là Nguyễn Văn Nam nhé"), "Nguyễn Văn Nam")


class CallContinuityTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        p = mock.patch.dict(os.environ, {"MCP_TRANSPORT": "inproc", "MEMORY_TRANSPORT": "local", "OPENAI_API_KEY": ""})
        p.start()
        self.addCleanup(p.stop)
        from pipeline import CallCenterHarnessPipeline
        self.p = CallCenterHarnessPipeline(trace_file=os.path.join(d, "t.jsonl"), db_path=os.path.join(d, "t.db"))
        self.addCleanup(self.p.close)
        advisor_suggests(self)

    def say(self, text, date, call, turn):
        return self.p.handle_incoming_request(text, PHONE, InputChannel.HOTLINE, call_date=date, call_name=call, turn_num=turn)

    def call1(self):
        self.say("Chị tên Lan, chị hỏi máy lọc không khí cho phòng 20m2 nhà có bé nhỏ", "2026-10-15", "call_1", 1)
        return self.say("giá cao quá, để chị hỏi chồng đã", "2026-10-15", "call_1", 2)

    def test_changing_the_date_closes_the_old_call_and_starts_a_new_one(self):
        r1 = self.call1()
        cid = r1["customer_id"]
        self.assertEqual(self.p._open_calls[PHONE][1:3], ("2026-10-15", "call_1"))
        self.assertEqual(self.p.memory.get_episodes(cid), [])                              # cuộc 1 chưa chốt
        self.say("alo em, chị gọi lại đây", "2026-10-17", "call_2", 1)
        self.assertEqual(self.p._open_calls[PHONE][1:3], ("2026-10-17", "call_2"))        # cuộc mới đang mở
        eps = self.p.memory.get_episodes(cid)
        self.assertEqual([(e.call_date, e.outcome) for e in eps], [("2026-10-15", "hen_goi_lai")])      # cuộc cũ ĐÃ chốt (episode + kết quả)

    def test_same_date_and_call_does_not_close_anything(self):
        r1 = self.call1()
        self.assertEqual(self.p.memory.get_episodes(r1["customer_id"]), [])
        self.say("ừ để chị xem", "2026-10-15", "call_1", 3)
        self.assertEqual(self.p.memory.get_episodes(r1["customer_id"]), [])

    def test_call_brief_of_call_2_carries_blocker_name_and_honorific_of_call_1(self):
        self.call1()
        r2 = self.say("alo em, chị gọi lại đây", "2026-10-17", "call_2", 1)
        b = r2["call_brief"]
        self.assertEqual(b["blocker"], "can hoi chong")
        self.assertEqual(b["customer_name"], "Lan")
        self.assertEqual(b["honorific"], "chị")
        self.assertEqual(b["previous_calls_count"], 1)
        self.assertIn("blocker", b["must_carry_over"])
        self.assertIn("chị Lan", b["suggested_opening"])
        self.assertNotIn("Lan Chị", b["suggested_opening"])
        self.assertIn("20", b["suggested_opening"])                                       # diện tích đã nêu ở cuộc 1


if __name__ == "__main__":
    unittest.main()
