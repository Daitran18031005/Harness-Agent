"""Khách hỏi "có các mẫu nào": catalog.search và product.shortlist phải trả ĐỦ mọi mẫu cùng danh mục, không phụ thuộc cách khách diễn đạt."""
import json
import os
import unittest

from tests._helpers import BTC_DIR, build_components

CATEGORY_NAMES = {          # cách khách gọi tên danh mục → slug danh mục trong products.json (đáp án suy từ dữ liệu, không từ mã)
    "máy lọc không khí": "gia-dung/may-loc-khong-khi",
    "máy lọc nước": "gia-dung/may-loc-nuoc",
    "giày": "thoi-trang/giay",
    "quạt": "gia-dung/quat",
    "nồi chiên": "gia-dung/noi-chien",
}
PHRASES = ["{x}", "các mẫu {x}", "có những loại {x} nào", "shop có {x} nào không ạ", "cho anh xem các mẫu {x} bên em", "có các mẫu {x} nào"]


def expected_skus(category_slug):
    products = json.load(open(os.path.join(BTC_DIR, "catalog", "products.json"), encoding="utf-8"))
    products = products["products"] if isinstance(products, dict) else products
    return {p["sku"] for p in products if p["category"] == category_slug and not (p.get("attributes") or {}).get("discontinued")}


class ListingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = build_components()
        cls.mcp = cls.c["mcp"]

    def test_catalog_search_returns_every_model_for_every_phrasing(self):
        for name, slug in CATEGORY_NAMES.items():
            want = expected_skus(slug)
            self.assertGreaterEqual(len(want), 3, name)
            for ph in PHRASES:
                q = ph.format(x=name)
                res = self.mcp.execute_tool("catalog.search", {"query": q}, caller="LLMOrchestrator")
                self.assertEqual({i["sku"] for i in res["items"]}, want, q)

    def test_shortlist_list_all_returns_every_model_default_is_capped_with_more_available(self):
        for name, slug in CATEGORY_NAMES.items():
            want = expected_skus(slug)
            res = self.mcp.execute_tool("product.shortlist", {"category": f"các mẫu {name} nào", "list_all": True}, caller="LLMOrchestrator")
            self.assertEqual({i["sku"] for i in res["items"]}, want, name)
            self.assertNotIn("more_available", res)
            if len(want) > 3:
                capped = self.mcp.execute_tool("product.shortlist", {"category": name}, caller="LLMOrchestrator")
                self.assertEqual(len(capped["items"]), 3)
                self.assertEqual(capped["more_available"], len(want) - 3)

    def test_unknown_product_returns_nothing_instead_of_unrelated_models(self):
        for q in ("máy giặt", "kem đánh răng", "các mẫu điện thoại nào"):
            self.assertEqual(self.mcp.execute_tool("catalog.search", {"query": q}, caller="LLMOrchestrator")["items"], [], q)
            self.assertEqual(self.mcp.execute_tool("product.shortlist", {"category": q, "list_all": True}, caller="LLMOrchestrator")["items"], [], q)

    def test_exact_btc_behaviour_is_kept_when_the_query_already_matches(self):
        res = self.mcp.execute_tool("catalog.search", {"query": "giày"}, caller="LLMOrchestrator")
        self.assertNotIn("matched_by", res)                                     # không đụng đường mock BTC khi truy vấn vốn đã khớp
        by_sku = self.mcp.execute_tool("catalog.search", {"sku": "SKU-SN-CAS-39-DEN"}, caller="LLMOrchestrator")
        self.assertEqual(by_sku["items"][0]["sku"], "SKU-SN-CAS")

    def test_discontinued_models_are_not_listed(self):
        res = self.mcp.execute_tool("catalog.search", {"query": "các mẫu máy lọc không khí"}, caller="LLMOrchestrator")
        self.assertNotIn("SKU-AP-X-2024", {i["sku"] for i in res["items"]})

    def test_prompt_and_tool_schema_tell_the_llm_to_list_everything(self):
        from src.llm.client import build_openai_tools
        sl = next(t for t in build_openai_tools() if t["function"]["name"].replace("__", ".") == "product.shortlist")
        self.assertNotIn("list_all", sl["function"]["parameters"]["properties"])          # LLM không tự bật; code nhận ra ý định liệt kê
        import inspect
        from src.harness import orchestrator
        self.assertIn("listing_requested", inspect.getsource(orchestrator))

    def test_listing_intent_is_detected_by_code_not_by_llm(self):
        from src.harness.orchestrator import HarnessOrchestrator as H
        for yes in ("Bên em có các mẫu máy lọc nước nào?", "có những loại giày nào vậy em", "còn mẫu nào khác không", "cho anh xem hết các mẫu", "có bao nhiêu loại quạt"):
            self.assertTrue(H._wants_listing(yes), yes)
        for no in ("Alo, chị muốn hỏi máy lọc không khí cho phòng ngủ khoảng 25 mét vuông.", "Nhà chị có bé nhỏ, ngân sách tầm 5 triệu", "lên đơn cho chị đi",
                   "AirPure X đang giảm 500.000 đúng không?"):
            self.assertFalse(H._wants_listing(no), no)

    def test_orchestrator_passes_list_all_only_when_the_customer_asks_to_list(self):
        from src.channels.normalizer import InputChannel
        c = self.c
        orch = c["orchestrator"]
        seen = []
        real = orch.mcp.execute_tool
        orch.mcp.execute_tool = lambda name, args, caller="x": (seen.append((name, dict(args))) or real(name, args, caller=caller))
        try:
            for text, want in (("Bên em có các mẫu máy lọc nước nào?", True), ("chị cần máy lọc nước cho nhà", False)):
                t = c["normalizer"].normalize(text, InputChannel.HOTLINE, "0911000111")
                brief = c["brief"].build(c["resolver"].resolve(t), "2026-10-15")
                seen.clear()
                out = orch._run_shortlist({"category": "máy lọc nước", "list_all": True}, {}, brief, t, "2026-10-15", "S")
                call = next(a for n, a in seen if n == "product.shortlist")
                self.assertEqual(call.get("list_all", False), want, text)
                self.assertEqual(bool(out.get("listing_requested")), want)
        finally:
            orch.mcp.execute_tool = real


if __name__ == "__main__":
    unittest.main()
