"""Mã SKU nội bộ không bao giờ tới khách (ui_replay_14 hội thoại E: "tư vấn chị AP-X", "tặng kèm bộ lọc SKU-AP-FLT-X").
Hai nguyên nhân: (1) pipeline không truyền tool_gateway cho CallBriefBuilder nên tên sản phẩm luôn rơi về mã rút gọn; (2) lời LLM tự nêu mã.
Chặn BẰNG CẤU TRÚC ở tầng đầu ra: mã `SKU-...` → tên sản phẩm trong catalog."""
import os
import tempfile
import unittest
from unittest import mock

from src.channels.normalizer import InputChannel
from src.harness.call_brief import CallBriefBuilder
from tests._helpers import build_components
from tests.test_order_gate import GateBase, NEW_PHONE


class MaskTest(GateBase):
    def test_parent_variant_unknown_and_gift_codes(self):
        m = self.orch._mask_sku_codes
        self.assertEqual(m("Dạ em tư vấn SKU-WF-RO10 ạ"), "Dạ em tư vấn Máy lọc nước RO Kangaroo 10 lõi ạ")
        v = m("Dạ còn SKU-SN-CAS-39-DEN nhé")
        self.assertNotIn("SKU", v)
        self.assertIn("size 39", v)
        self.assertIn("đen", v)
        self.assertEqual(m("mã SKU-KHONG-CO-THAT ạ"), "mã sản phẩm này ạ")
        self.assertNotIn("SKU-", m("tặng kèm bộ lọc SKU-AP-FLT-X"))
        self.assertEqual(m("Dạ giá 1.690.000đ ạ"), "Dạ giá 1.690.000đ ạ")                # không có mã: giữ nguyên

    def test_reply_to_customer_never_contains_a_sku_code(self):
        txt, _, _ = self.turn(NEW_PHONE, "cho mình hỏi máy lọc nước 10 lõi", [], "Dạ em tư vấn SKU-WF-RO10, tặng kèm SKU-AP-FLT-X ạ.")
        self.assertNotIn("SKU-", txt)
        self.assertIn("Kangaroo", txt)


class OpeningTest(unittest.TestCase):
    def test_fallback_name_never_shows_a_code(self):
        b = CallBriefBuilder(build_components()["memory"].as_caller("CallBriefBuilder"))        # không có tool_gateway
        self.assertEqual(b._product_name("SKU-AP-X"), "sản phẩm mình quan tâm")

    def test_name_from_catalog_with_gateway(self):
        c = build_components()
        self.assertIn("AirPure", c["brief"]._product_name("SKU-AP-X"))

    def test_pipeline_wires_the_gateway_into_the_call_brief_builder(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"MCP_TRANSPORT": "inproc", "MEMORY_TRANSPORT": "local", "OPENAI_API_KEY": ""}):
            from pipeline import CallCenterHarnessPipeline
            p = CallCenterHarnessPipeline(trace_file=os.path.join(d, "t.jsonl"), db_path=os.path.join(d, "t.db"))
            try:
                self.assertIsNotNone(p.call_brief_builder.tool_gateway)
                self.assertIn("AirPure", p.call_brief_builder._product_name("SKU-AP-X"))
            finally:
                p.close()


if __name__ == "__main__":
    unittest.main()
