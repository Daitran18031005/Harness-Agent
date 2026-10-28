"""Bước 15 — CCR công bằng: fact chỉ tính là 'được mang sang và dùng' khi agent dùng thật, chưa hỏi mở lại, khách chưa nhắc lại."""
import unittest
from tests._helpers import build_components
from src.channels.normalizer import InputChannel
from src.harness.fact_usage import fact_mentioned, used_by_agent, blocker_cues, fold


class MentionTest(unittest.TestCase):
    def test_blocker_family_variants_are_recognised(self):
        # lỗi cũ: blocker không bao giờ được tính là đã dùng vì so khớp nguyên chuỗi 'can hoi chong'
        self.assertTrue(fact_mentioned("blocker", "can hoi chong", "Chị đã trao đổi lại với gia đình chưa ạ?"))
        self.assertTrue(fact_mentioned("blocker", "can hoi chong", "Anh nhà đã đồng ý chưa ạ?"))
        self.assertTrue(fact_mentioned("blocker", "can hoi vo", "Anh đã bàn với vợ chưa ạ?"))
        self.assertTrue(fact_mentioned("blocker", "so sanh gia", "Chị còn đang so sánh với bên kia phải không ạ?"))
        self.assertFalse(fact_mentioned("blocker", "can hoi chong", "Dạ máy giá 5.200.000đ ạ."))
        self.assertFalse(fact_mentioned("blocker", "so sanh gia", "Dạ em chào chị ạ."))

    def test_customer_restating_blocker(self):
        self.assertTrue(fact_mentioned("blocker", "can hoi chong", "Ừ để chị hỏi ông xã rồi gọi lại em nhé."))
        self.assertTrue(fact_mentioned("blocker", "can hoi vo", "để anh hỏi vợ đã"))

    def test_has_children_boolean_by_meaning(self):
        self.assertTrue(fact_mentioned("has_children", True, "Máy này có khóa an toàn cho bé nhỏ nhà mình ạ."))
        self.assertFalse(fact_mentioned("has_children", True, "Dạ máy giá 5.200.000đ ạ."))
        self.assertFalse(fact_mentioned("has_children", False, "bé nhỏ"))

    def test_numbers_respect_digit_boundaries_and_units(self):
        self.assertTrue(fact_mentioned("room_area_m2", 25.0, "phòng 25m² nhà mình"))
        self.assertFalse(fact_mentioned("room_area_m2", 25.0, "hôm 2026-10-25 có khuyến mãi"))
        self.assertFalse(fact_mentioned("room_area_m2", 25.0, "giá 125.000đ"))
        self.assertTrue(fact_mentioned("price_quoted_vnd", 5200000, "giá 5.200.000đ ạ"))
        self.assertTrue(fact_mentioned("price_quoted_vnd", 5200000, "price 5200000"))
        self.assertFalse(fact_mentioned("price_quoted_vnd", 5200000, "giá 5.200.0000đ"))

    def test_size_color_accent_insensitive(self):
        self.assertTrue(fact_mentioned("size", "39", "size 39 hơi chật"))
        self.assertFalse(fact_mentioned("size", "39", "giá 39.000đ"))
        self.assertTrue(fact_mentioned("color", "den", "màu đen nhé"))
        self.assertFalse(fact_mentioned("color", "be", "bên em cho phép đổi"))

    def test_product_by_sku_or_name(self):
        names = {"SKU-AP-Y": "Máy lọc không khí AirPure Y"}
        self.assertFalse(fact_mentioned("product_advised", "SKU-AP-Y", "mẫu AirPure Y", names))   # tên đầy đủ mới khớp
        self.assertTrue(fact_mentioned("product_advised", "SKU-AP-Y", "Máy lọc không khí AirPure Y giá tốt", names))
        self.assertTrue(fact_mentioned("product_advised", "SKU-AP-Y", "sku-ap-y"))

    def test_used_by_agent_reads_tool_args(self):
        self.assertTrue(used_by_agent("order_id", "OD600001", "Dạ em kiểm tra ạ", [{"order_id": "OD600001"}]))
        self.assertFalse(used_by_agent("order_id", "OD600001", "Dạ em kiểm tra ạ", [{"order_id": "OD600002"}]))

    def test_blocker_cues_generic_fallback(self):
        self.assertIn("ngan sach", " ".join(blocker_cues("het ngan sach")))
        self.assertEqual(fold("Đèn ĐỎ"), "den do")


class CarriedFactsRulesTest(unittest.TestCase):
    """Dùng thật · chưa hỏi mở lại · khách chưa nhắc lại · fact có sẵn lúc đầu cuộc gọi."""

    def setUp(self):
        self.orch = build_components()["orchestrator"]
        self.start = {"room_area_m2": 25.0, "has_children": True, "blocker": "can hoi chong", "product_advised": "SKU-AP-Y"}
        self.keys = list(self.start)

    def carried(self, agent, customer="alo hôm trước chị có gọi", asked=(), tools=()):
        return set(self.orch._carried_facts(self.keys, self.start, agent, list(tools), customer, set(asked)))

    def test_used_when_agent_remembers(self):
        got = self.carried("Dạ phòng 25m² nhà có bé nhỏ, chị đã trao đổi với gia đình chưa ạ?")
        self.assertEqual(got, {"room_area_m2", "has_children", "blocker"})

    def test_not_counted_if_agent_asked_open_again(self):
        got = self.carried("Dạ phòng 25m² phải không ạ?", asked={"room_area_m2"})
        self.assertNotIn("room_area_m2", got)

    def test_not_counted_if_customer_restated(self):
        got = self.carried("Dạ phòng 25m² ạ, chị đã hỏi ông xã chưa?", customer="phòng chị 25 mét vuông, chị hỏi ông xã rồi")
        self.assertNotIn("room_area_m2", got)
        self.assertNotIn("blocker", got)

    def test_fact_not_known_at_call_start_is_not_carried(self):
        self.assertEqual(set(self.orch._carried_facts(["order_id"], self.start, "Dạ đơn OD600001 ạ", [], "alo", set())), set())

    def test_baseline_without_memory_cannot_score(self):
        self.assertEqual(set(self.orch._carried_facts(self.keys, {}, "Dạ phòng 25m² nhà có bé nhỏ ạ", [], "alo", set())), set())


class RuntimeFlowTest(unittest.TestCase):
    """Trong luồng thật: facts_used của trace tuân theo quy tắc."""

    def setUp(self):
        from tests.test_orchestrator import FakeLLM
        self.FakeLLM = FakeLLM
        self.c = build_components()
        self.orch = self.c["orchestrator"]
        mem = self.c["memory"]
        for k, v in (("room_area_m2", 25.0), ("has_children", True), ("blocker", "can hoi chong"), ("product_advised", "SKU-AP-Y"),
                     ("price_quoted_vnd", 5200000)):
            mem.set_profile_fact("C001", k, v)

    def _turn(self, text, date="2026-10-17"):
        t = self.c["normalizer"].normalize(text, InputChannel.HOTLINE, "0984726714")
        return t, self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), date)

    def test_trace_facts_used_strict(self):
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ em chào chị Hoa, phòng 25m² nhà có bé nhỏ, chị đã trao đổi với gia đình chưa ạ?"})
        t, b = self._turn("Alo, hôm trước chị có gọi hỏi máy lọc không khí đó em.")
        _, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertEqual(set(meta["facts_used"]), {"room_area_m2", "has_children", "blocker"})

    def test_restated_by_customer_is_not_credited(self):
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ vâng ạ."})
        t, b = self._turn("Alo, ông xã chị đồng ý rồi, phòng chị 25 mét vuông nhé.")
        self.orch.process_turn(t, b, current_date="2026-10-17")
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ phòng 25m² ạ, anh nhà đã đồng ý rồi."})
        t2, b2 = self._turn("ừ đúng rồi")
        _, _, meta2 = self.orch.process_turn(t2, b2, current_date="2026-10-17")
        self.assertNotIn("room_area_m2", meta2["facts_used"])
        self.assertNotIn("blocker", meta2["facts_used"])

    def test_open_question_disqualifies_slot_for_rest_of_call(self):
        """Cơ chế CCR độc lập với bước 12: khi KHÔNG có chính sách hỏi lại (clarifier=None) câu hỏi mở vẫn làm slot mất điều kiện."""
        self.orch.clarifier = None
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ phòng mình rộng bao nhiêu mét vuông ạ?"})
        t, b = self._turn("alo")
        _, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertNotIn("room_area_m2", meta["facts_used"])
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ vậy phòng 25m² phù hợp mẫu này ạ."})
        t2, b2 = self._turn("khoảng 25")
        _, _, meta2 = self.orch.process_turn(t2, b2, current_date="2026-10-17")
        self.assertNotIn("room_area_m2", meta2["facts_used"])

    def test_repeat_question_rewritten_to_confirmation_counts_as_using_the_fact(self):
        """Bước 12: câu hỏi mở lặp về slot đã nhớ được đổi thành xác nhận → là CÁCH DÙNG fact, không phải hỏi lại."""
        self.orch.llm_client = self.FakeLLM({"calls": [], "text": "Dạ phòng mình rộng bao nhiêu mét vuông ạ?"})
        t, b = self._turn("alo")
        final, _, meta = self.orch.process_turn(t, b, current_date="2026-10-17")
        self.assertIn("vẫn khoảng 25m² đúng không ạ?", final)
        self.assertIn("room_area_m2", meta["facts_used"])

if __name__ == "__main__":
    unittest.main()
