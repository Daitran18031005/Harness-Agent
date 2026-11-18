import unittest
from types import SimpleNamespace as C
from src.memory.vector_rag import Bm25Backend, HybridBackend


class Bm25BackendTest(unittest.TestCase):
    docs = [C(content="Đổi trả trong 7 ngày nếu sản phẩm còn nguyên tem", doc_name="doi_tra.md"),
            C(content="Miễn phí vận chuyển cho đơn từ 500.000đ", doc_name="van_chuyen.md"),
            C(content="Bảo hành máy lọc không khí 24 tháng", doc_name="bao_hanh.md")]

    def test_unaccented_query_finds_doc(self):
        self.assertIs(Bm25Backend().rank("doi tra may ngay", self.docs, 1)[0], self.docs[0])

    def test_no_overlap_returns_nothing(self):
        self.assertEqual(Bm25Backend().rank("xyz", self.docs, 3), [])

    def test_hybrid_ranks_relevant_first(self):
        self.assertIs(HybridBackend().rank("bảo hành máy lọc", self.docs, 2)[0], self.docs[2])
