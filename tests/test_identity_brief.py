"""Bước 8 — Định danh đa kênh & Call Brief (A3, A6, A11, N7)."""
import unittest
from tests._helpers import build_components
from src.channels.normalizer import InputChannel


class IdentityBriefTest(unittest.TestCase):
    def setUp(self):
        self.c = build_components()

    def turn(self, text, channel, contact):
        return self.c["normalizer"].normalize(text, channel, contact)

    def test_zalo_and_fb_of_c001(self):
        r = self.c["resolver"]
        self.assertEqual(r.resolve(self.turn("hi", InputChannel.HOTLINE, "0984726714")).customer_id, "C001")

    def test_unknown_number_not_greeted_as_hoa(self):  # A3
        ident = self.c["resolver"].resolve(self.turn("alo", InputChannel.HOTLINE, "0900000999"))
        b = self.c["brief"].build(ident, "2026-10-15")
        self.assertNotEqual(b.customer_name, "Hoa")
        self.assertNotIn("Hoa", b.suggested_opening)

    def test_honorific_from_crm(self):  # A11 — SAMPLE-03 anh Khoa
        ident = self.c["resolver"].resolve(self.turn("alo", InputChannel.HOTLINE, "0922264686"))
        b = self.c["brief"].build(ident, "2026-10-15")
        self.assertEqual(b.honorific, "anh")
        self.assertEqual(b.customer_name, "Khoa")

    def test_shared_phone_not_shared_id(self):  # A6
        ident = self.c["resolver"].resolve(self.turn("alo", InputChannel.HOTLINE, "0958421083"))
        self.assertTrue(ident.is_ambiguous)
        b = self.c["brief"].build(ident, "2026-10-15")
        self.assertNotEqual(b.customer_id, "AMBIGUOUS")

    def test_shared_phone_resolved_by_name(self):  # A6
        r = self.c["resolver"]
        ident = r.resolve(self.turn("cô là Loan đây", InputChannel.HOTLINE, "0958421083"))
        self.assertFalse(ident.is_ambiguous)
        self.assertEqual(ident.customer_id, "C034")

    def test_scenario_channel_mapping(self):
        self.assertEqual(InputChannel.from_scenario("chat_fanpage"), InputChannel.FANPAGE)
        self.assertEqual(InputChannel.from_scenario("zalo_oa"), InputChannel.ZALO)
        self.assertEqual(InputChannel.from_scenario(None), InputChannel.HOTLINE)

    def test_fanpage_linked_to_phone(self):  # N7 — SAMPLE-04
        r, mem = self.c["resolver"], self.c["memory"]
        t1 = self.turn("shop oi giay RunLite 2 Pro gia bn v", InputChannel.FANPAGE, "fb.hạnh.274")
        anon = r.resolve(t1)
        self.assertTrue(anon.customer_id.startswith("CUST-ANON"))
        mem.set_profile_fact(anon.customer_id, "product_advised", "SKU-SN-RUN2")
        t3 = self.turn("sdt minh 0994893949 de minh goi hotline sau nhe", InputChannel.FANPAGE, "fb.hạnh.274")
        linked = r.resolve(t3, memory=mem)
        self.assertEqual(linked.customer_id, "C017")
        # Lượt sau trên Fanpage và cuộc gọi hotline đều về C017, bộ nhớ đã được gộp
        self.assertEqual(r.resolve(self.turn("ok", InputChannel.FANPAGE, "fb.hạnh.274")).customer_id, "C017")
        self.assertEqual(r.resolve(self.turn("alo", InputChannel.HOTLINE, "0994893949")).customer_id, "C017")
        self.assertEqual(mem.get_profile_facts("C017").get("product_advised"), "SKU-SN-RUN2")


if __name__ == "__main__":
    unittest.main()
