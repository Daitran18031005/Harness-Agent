"""Bước 11 — chọn policy 2 tầng (router LLM -> TF-IDF). Dùng LLM GIẢ, không gọi mạng."""
import os
import unittest
from unittest import mock
from tests import _helpers  # noqa: F401
from src.llm.client import LLMUnavailable
from src.memory.policy_router import PolicyRouter, ROUTED_TOP_K, build_catalog, validate
from src.memory.service import MemoryService

DOI_TRA = "chinh-sach-doi-tra.md"
DOI_TRA_CU = "chinh-sach-doi-tra-v2026-06-HET-HIEU-LUC.md"
CHANGELOG = "changelog.md"


class FakeLLM:
    """complete_json trả lần lượt các kết quả đã định; Exception -> ném ra."""
    available = True

    def __init__(self, *results):
        self.results, self.calls = list(results), []

    def complete_json(self, messages):
        self.calls.append(messages)
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r, {"llm_calls": 1, "cost_vnd": 1.0}


def make_service(llm):
    svc = MemoryService(enable_persistence=False)
    svc.semantic.router = PolicyRouter(llm)
    return svc


def docs(chunks):
    return {c["doc_name"] for c in chunks}


class PolicyRouterTest(unittest.TestCase):
    Q = "Mua giày về chật, đổi size có mất phí không?"

    def baseline(self, q=None, on_date="2026-10-15"):
        svc = MemoryService(enable_persistence=False)
        svc.semantic.router = None
        return svc.query_policy(q or self.Q, on_date=on_date)

    def test_router_restricts_tfidf_to_selected_files(self):
        llm = FakeLLM({"files": [DOI_TRA], "as_of_date": None, "as_of_evidence": None, "answerable": True})
        out = make_service(llm).query_policy(self.Q)
        self.assertEqual(len(out), 3)
        self.assertEqual([c["doc_name"] for c in out[:ROUTED_TOP_K]], [DOI_TRA] * ROUTED_TOP_K)   # lai: đầu từ file đã chọn, phần còn lại bù từ toàn bộ
        sys_prompt = llm.calls[0][0]["content"]
        self.assertIn(DOI_TRA, sys_prompt)
        self.assertNotIn("NOI-BO", sys_prompt)          # tài liệu nội bộ không vào mục lục
        self.assertNotIn("noi-quy-nhan-vien.md", sys_prompt)
        self.assertIn("Hôm nay: 2026-10-15", llm.calls[0][1]["content"])

    def test_fabricated_file_names_are_dropped(self):
        llm = FakeLLM({"files": [DOI_TRA, "chinh-sach-tu-che.md", 7], "as_of_date": None, "answerable": True})
        svc = make_service(llm)
        out = svc.query_policy(self.Q)
        self.assertEqual([c["doc_name"] for c in out[:ROUTED_TOP_K]], [DOI_TRA] * ROUTED_TOP_K)
        self.assertEqual(svc.semantic.last_route["dropped_files"], ["chinh-sach-tu-che.md", "7"])

    def test_all_fabricated_means_no_file_restriction(self):
        llm = FakeLLM({"files": ["khong-co.md"], "as_of_date": None, "answerable": True})
        self.assertEqual(make_service(llm).query_policy(self.Q), self.baseline())

    def test_not_answerable_returns_pb05_only(self):
        llm = FakeLLM({"files": [], "as_of_date": None, "answerable": False})
        svc = make_service(llm)
        out = svc.query_policy("AirPure Y có lọc được khí radon không?")
        self.assertEqual([c["chunk_id"] for c in out], ["[PB-05]"])
        self.assertIs(out[0]["answerable"], False)
        self.assertIn("chưa có thông tin", out[0]["content"])
        self.assertFalse(svc.semantic.last_route["answerable"])

    def test_router_failure_falls_back_to_full_tfidf(self):
        base = self.baseline()
        for failure in (LLMUnavailable("mạng"), RuntimeError("boom"), {"files": [DOI_TRA]},   # thiếu answerable
                        {"files": "chinh-sach-doi-tra.md", "answerable": True}, {"files": [], "answerable": "false"}):
            with self.subTest(failure=failure):
                svc = make_service(FakeLLM(failure))
                self.assertEqual(svc.query_policy(self.Q), base)
                self.assertIsNone(svc.semantic.last_route)
                self.assertTrue(svc.semantic.router.last_error)

    def test_no_llm_falls_back_without_calling(self):
        base = self.baseline()
        llm = FakeLLM()
        llm.available = False
        self.assertEqual(make_service(llm).query_policy(self.Q), base)
        self.assertEqual(llm.calls, [])
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):      # router mặc định: không key -> không router
            self.assertIsNone(PolicyRouter()._client())

    def test_env_off_disables_router(self):
        llm = FakeLLM({"files": [DOI_TRA], "answerable": False})
        with mock.patch.dict(os.environ, {"POLICY_ROUTER": "off"}):
            out = make_service(llm).query_policy(self.Q)
        self.assertEqual(llm.calls, [])
        self.assertEqual(out, self.baseline())

    def test_selected_files_without_tfidf_hit_do_not_lose_result(self):
        # router chọn file mà backend không xếp hạng được gì -> thử lại toàn bộ thay vì trả rỗng
        class OnlyDoiTra:
            def rank(self, query, candidates, top_k=3):
                return [c for c in candidates if c.doc_name == DOI_TRA][:top_k]
        svc = make_service(FakeLLM({"files": ["thong-bao-lich-nghi.md"], "as_of_date": None, "answerable": True}))
        svc.semantic.backend = OnlyDoiTra()
        out = svc.query_policy(self.Q)
        self.assertEqual(docs(out), {DOI_TRA})
        self.assertTrue(svc.semantic.last_route["fallback_all"])

    def test_hybrid_two_from_selected_then_fill_from_all_without_duplicates(self):
        class ByDocOrder:       # xếp hạng tất định: chunk theo thứ tự nạp, chỉ trong candidates
            def rank(self, query, candidates, top_k=3):
                return list(candidates)[:top_k]
        svc = make_service(FakeLLM({"files": ["faq.md"], "as_of_date": None, "answerable": True}))
        svc.semantic.backend = ByDocOrder()
        out = svc.query_policy(self.Q)
        public = [c for c in svc.semantic.chunks if c.access == "public" and c.effective_from <= "2026-10-15" <= c.effective_to]
        faq = [c for c in public if c.doc_name == "faq.md"]
        everything = list(public)
        ids = [c["chunk_id"] for c in out]
        self.assertEqual(ids[:ROUTED_TOP_K], [c.chunk_id for c in faq[:ROUTED_TOP_K]])
        self.assertEqual(len(ids), 3)
        self.assertEqual(len(set(ids)), 3)                                  # không trùng chunk
        self.assertEqual(ids[ROUTED_TOP_K], everything[0].chunk_id)         # chỗ còn lại: bù từ toàn bộ theo thứ hạng toàn bộ
        # top_k nhỏ hơn hằng số: không lấy quá top_k
        self.assertEqual(len(svc.semantic.search(self.Q, top_k=1)), 1)

    def test_hybrid_fill_still_filters_old_policy_version_by_date(self):
        both = [DOI_TRA, DOI_TRA_CU]
        svc = make_service(FakeLLM({"files": both, "as_of_date": None, "answerable": True}))
        out = svc.query_policy("Hoàn tiền mất bao lâu?", on_date="2026-10-15")
        self.assertNotIn(DOI_TRA_CU, docs(out))                              # bản cũ hết hiệu lực không lọt qua phần bù
        svc = make_service(FakeLLM({"files": [DOI_TRA_CU], "as_of_date": "2026-09-28", "as_of_evidence": "28/09/2026", "answerable": True}))
        out = svc.query_policy("Đơn ngày 28/09/2026 hoàn tiền mất bao lâu?", on_date="2026-10-15")
        self.assertEqual([c["doc_name"] for c in out[:ROUTED_TOP_K]], [DOI_TRA_CU] * ROUTED_TOP_K)
        self.assertNotIn(DOI_TRA, docs(out))                                 # đơn cũ: cả phần bù cũng chỉ gồm bản có hiệu lực ngày mua

    def test_purchase_date_selects_old_policy_version(self):
        q = "Đơn tạo ngày 28/09/2026, khách đòi đổi trả ngày 09/10 (11 ngày) được không?"
        both = [DOI_TRA, DOI_TRA_CU, CHANGELOG]
        with_date = make_service(FakeLLM({"files": both, "as_of_date": "2026-09-28", "as_of_evidence": "28/09/2026", "answerable": True}))
        out = with_date.query_policy(q, on_date="2026-10-09")
        self.assertIn(DOI_TRA_CU, docs(out))
        self.assertNotIn(DOI_TRA, docs(out))
        self.assertEqual(with_date.semantic.last_route["as_of_date"], "2026-09-28")
        # cùng file nhưng KHÔNG ngày mua: dùng ngày cuộc gọi -> bản cũ hết hiệu lực không bao giờ được trả
        no_date = make_service(FakeLLM({"files": both, "as_of_date": None, "answerable": True}))
        self.assertNotIn(DOI_TRA_CU, docs(no_date.query_policy(q, on_date="2026-10-09")))

    def test_as_of_date_needs_verbatim_evidence_and_valid_date(self):
        names = [DOI_TRA, DOI_TRA_CU]
        q = "Đơn tạo ngày 28/09/2026 đổi trả được không?"
        ok = validate({"files": names, "answerable": True, "as_of_date": "2026-09-28", "as_of_evidence": "ngày 28/09/2026"}, names, q)
        self.assertEqual(ok.as_of_date, "2026-09-28")
        for bad in ({"as_of_date": "2026-09-28", "as_of_evidence": "hôm qua"},           # trích dẫn không có trong câu hỏi
                    {"as_of_date": "2026-09-28"},                                          # thiếu trích dẫn
                    {"as_of_date": "2026-13-45", "as_of_evidence": "28/09/2026"},          # ngày không tồn tại
                    {"as_of_date": "28/09/2026", "as_of_evidence": "28/09/2026"}):         # không phải ISO
            with self.subTest(bad=bad):
                d = validate({"files": names, "answerable": True, **bad}, names, q)
                self.assertIsNone(d.as_of_date)
                self.assertTrue(d.date_dropped)

    def test_catalog_lists_public_files_with_validity(self):
        svc = MemoryService(enable_persistence=False)
        public = [c for c in svc.semantic.chunks if c.access == "public"]
        cat = {d["name"]: d for d in build_catalog(public)}
        self.assertIn(DOI_TRA_CU, cat)
        self.assertEqual(cat[DOI_TRA_CU]["effective_to"], "2026-09-30")
        self.assertNotIn("ghi-chu-nhap-hang-NOI-BO.md", cat)
        self.assertTrue(all(d["sections"] for d in cat.values()))

    def test_usage_is_recorded_and_drained(self):
        router = PolicyRouter(FakeLLM({"files": [], "answerable": True}))
        svc = MemoryService(enable_persistence=False)
        svc.semantic.router = router
        svc.query_policy(self.Q)
        self.assertEqual(len(router.drain_usage()), 1)
        self.assertEqual(router.drain_usage(), [])

class EvalScriptSmokeTest(unittest.TestCase):
    """scripts/eval_policy_router.py chạy được với router GIẢ (không LLM): abstain tách khỏi truy hồi, độ phủ file."""

    def test_run_mode_with_fake_router(self):
        import importlib.util
        path = os.path.join(_helpers.CODE_DIR, "scripts", "eval_policy_router.py")
        spec = importlib.util.spec_from_file_location("eval_policy_router", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        qs = [{"qid": "A", "type": "single", "question": "Đổi size có mất phí không?", "relevant_chunk_ids": ["DT-03"]},
              {"qid": "B", "type": "unanswerable", "question": "Lọc được khí radon không?", "relevant_chunk_ids": ["FAQ-03"]}]
        svc = make_service(FakeLLM({"files": [DOI_TRA], "answerable": True},
                                   {"files": ["faq.md"], "answerable": False}))
        served, retrieval, details = mod.run_mode(qs, svc, "2026-10-15")
        self.assertEqual(served["B"]["retrieved_chunk_ids"], ["PB-05"])
        self.assertTrue(served["B"]["abstained"])
        self.assertTrue(retrieval["B"]["abstained"])
        self.assertNotIn("PB-05", retrieval["B"]["retrieved_chunk_ids"])       # truy hồi tách khỏi abstain: lấy lại từ file đã chọn
        self.assertTrue(retrieval["B"]["retrieved_chunk_ids"][0].startswith("FAQ"))      # đầu lấy từ file đã chọn
        self.assertIsInstance(svc.semantic.router, PolicyRouter)               # router gốc được trả lại sau khi replay
        chunk_doc = {c.chunk_id.strip("[]"): c.doc_name for c in svc.semantic.chunks}
        self.assertEqual(mod.file_coverage(qs, details, chunk_doc), (2, 2))
        # biến thể OFFLINE từ quyết định đã lưu: strict (chỉ file chọn) vs lai k=1..3, không gọi LLM
        variants = mod.offline_variants(qs, details, svc, "2026-10-15")
        self.assertEqual(set(variants), {"strict", "hybrid_k1", "hybrid_k2", "hybrid_k3"})
        self.assertEqual(variants["strict"]["A"]["retrieved_chunk_ids"][0], variants["hybrid_k2"]["A"]["retrieved_chunk_ids"][0])
        self.assertEqual(len(variants["hybrid_k2"]["A"]["retrieved_chunk_ids"]), 5)   # cả hai câu: file router chọn chứa đủ chunk nhãn


if __name__ == "__main__":
    unittest.main()
