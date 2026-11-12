"""Lượt chốt của cuộc gọi (luật chấm BTC 11/2026): sau lượt khách cuối, agent được một lượt không có lời khách để đọc lại đơn và gọi order.create."""
import unittest
from tests.test_basket_sync import OrderSyncTest, ON, AP_Y

RUN2 = "SKU-SN-RUN2"          # sản phẩm có biến thể size/màu


class ClosingTurnTest(unittest.TestCase):
    _setup, _run, _mock, _create = OrderSyncTest._setup, OrderSyncTest._run, staticmethod(OrderSyncTest._mock), staticmethod(OrderSyncTest._create)

    def _close(self, phone="0911265844", orders_now=True):
        t = self.c["normalizer"].normalize("", self._channel(), phone)
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), ON)
        self.orch.llm_client.complete_json = lambda msgs: ({"orders_now": orders_now, "quote": "lên đơn cho anh" if orders_now else ""}, {})   # chốt độc lập của lượt chốt
        return b, (lambda: self.orch.process_turn(t, b, current_date=ON, closing=True))

    @staticmethod
    def _channel():
        from src.channels.normalizer import InputChannel
        return InputChannel.HOTLINE

    def test_open_draft_is_created_with_cod_default(self):
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])              # gate hỏi địa chỉ/thanh toán, chưa tạo đơn
        m = self._mock()
        self.assertEqual(len(m._ORDERS), 0)
        b, close = self._close()
        self.assertTrue(self.orch.has_open_order(b.customer_id, ON))
        reply, tc, _ = close()
        oc = [c for c in tc if c["name"] == "order.create"]
        self.assertEqual((oc[0]["args"]["sku"], oc[0]["args"]["price_vnd"], oc[0]["args"]["payment"]), (AP_Y, 5200000, "COD"))
        self.assertEqual(oc[0]["result"]["status"], "created")
        self.assertEqual(len(m._ORDERS), 1)
        self.assertIn("đọc lại đơn", reply)
        self.assertIn("một sản phẩm", reply)                           # A2: đọc cả giá một sản phẩm, SĐT
        self.assertIn("số điện thoại", reply)
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))  # không chốt lần hai

    def test_no_closing_order_after_handoff(self):
        """A1: đã chuyển máy thành công thì lượt chốt không tạo đơn."""
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])
        b, close = self._close()
        sid = f"SESS-{b.customer_id}-{ON}"
        self.orch._call_log.setdefault(sid, []).append({"name": "handoff.transfer", "args": {}, "result": {"ticket_id": "T-1"}})
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))
        _, tc, _ = close()
        self.assertFalse([c for c in tc if c["name"] == "order.create"])

    def test_unknown_sku_is_not_read_back(self):
        """A3: SKU tự đặt → không đọc lại mã thô, không tạo đơn."""
        self._setup(order_gate=True)
        self._run([self._create("SPECTRA-S1", 1, payment=None)])
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse(self.orch.has_open_order(self._close()[0].customer_id, ON))

    def test_independent_check_blocks_when_customer_did_not_order(self):
        self._setup(order_gate=True)
        self._run([self._create(AP_Y, 1, payment=None)])
        _, close = self._close(orders_now=False)                       # "khoan chốt vội": chốt độc lập không thấy yêu cầu đặt đơn
        reply, tc, _ = close()
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse([c for c in tc if c["name"] == "order.create"])
        self.assertNotIn("?", reply)

    def test_callback_in_the_past_rolls_to_next_occurrence(self):
        from src.harness.orchestrator import HarnessOrchestrator as H
        f = lambda at: H._future_callback({"callback_at": at}, "2026-10-15")["callback_at"]
        self.assertEqual(f("2026-01-01T09:00:00"), "2027-01-01T09:00:00")     # "Tết Dương lịch 01/01" nói ngày 15/10 → năm sau
        self.assertEqual(f("2025-12-20T09:00"), "2026-12-20T09:00")
        self.assertEqual(f("2026-10-27T09:00:00"), "2026-10-27T09:00:00")     # tương lai: giữ nguyên

    def test_second_call_on_the_same_day_sees_the_first_one(self):
        """Hai cuộc cùng khách CÙNG NGÀY: cuộc đầu đã kết thúc phải được tính là cuộc trước (không bị coi là cuộc hiện tại, không bị cuộc sau ghi đè)."""
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        t = self.c["normalizer"].normalize("alo", self._channel(), "0911265844")
        ident = self.c["resolver"].resolve(t, memory=self.c["memory"])
        self.orch.finalize_call(ident.customer_id, ON, "call_1", "hotline")
        b = self.c["brief"].build(ident, ON)
        self.assertEqual((b.previous_calls_count, b.product_advised), (1, AP_Y))
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])                # cuộc thứ hai, cùng ngày
        self.orch.finalize_call(ident.customer_id, ON, "call_2", "hotline", trigger="handoff", clear=False)
        self.orch.finalize_call(ident.customer_id, ON, "call_2", "hotline")
        ids = [e.session_id for e in self.c["memory"].get_episodes(ident.customer_id)]
        self.assertEqual([i.split("#")[1] for i in ids], ["1", "2"])                 # hai cuộc, mỗi cuộc đếm một lần (episode giữa cuộc bị ẩn)

    def test_speculative_quote_is_remembered_only_when_the_agent_used_it(self):
        """Báo giá do code CHẠY TRƯỚC (đoán) không được thành "sản phẩm đã tư vấn" nếu agent không nói tới nó (từng ghi nhầm ghế ô tô cho khách hỏi máy lọc)."""
        self._setup()
        guess = {"name": "pricing.get_quote", "args": {"sku": "SKU-MB-CAR"}, "result": {"sku": "SKU-MB-CAR", "final_price_vnd": 4990000, "applied_promos": []}, "speculative": True}
        mem = self.c["memory"]
        self.orch._persist_tool_grounded_facts("C-SPEC", [guess], "Dạ nhà mình có bé nhỏ thì em gợi ý máy có khóa trẻ em ạ.")
        self.assertNotIn("product_advised", mem.get_profile_facts("C-SPEC"))
        self.orch._persist_tool_grounded_facts("C-SPEC", [guess], "Dạ ghế đó giá 4.990.000đ ạ.")
        self.assertEqual(mem.get_profile_facts("C-SPEC").get("product_advised"), "SKU-MB-CAR")

    def test_speculative_targets_need_the_real_product_name(self):
        self._setup()
        t = self.c["normalizer"].normalize("alo", self._channel(), "0911265844")
        b = self.c["brief"].build(self.c["resolver"].resolve(t, memory=self.c["memory"]), ON)
        from src.privacy.pii_vault import PiiVault
        look = lambda text, picked=None: {c["args"]["sku"] for c in self.orch._speculative_lookups(text, None, [], None, b, None, ON, PiiVault(), picked=picked)}
        self.assertEqual(look("Nhà chị có bé nhỏ, ngân sách tầm 5.000.000 thôi em."), set())          # "có bé" không phải tên sản phẩm
        self.assertEqual(look("Em ơi Máy lọc không khí AirPure X bên em giá bao nhiêu?"), {"SKU-AP-X"})   # chưa có bộ đọc (lượt khám phá): vẫn tra trước theo tên
        self.assertEqual(look("phí phát sinh bao nhiêu"), set())                                        # `named` chặn alias "phát" → Fatz
        self.assertEqual(look("màng lọc thay thế AirPure X giá sao em", picked="SKU-AP-FLT-X"), {"SKU-AP-FLT-X"})   # bộ đọc đã kiểm thì dùng bộ đọc

    def test_no_draft_means_no_closing_turn(self):
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        b, _ = self._close()
        self.assertFalse(self.orch.has_open_order(b.customer_id, ON))

    def test_unknown_variant_is_not_ordered(self):
        self._setup(order_gate=True)
        self._run([self._create(RUN2, 1, payment="COD")])             # khách chưa chọn size/màu
        _, close = self._close()
        reply, tc, _ = close()
        self.assertNotIn("?", reply)                                   # không còn ai trả lời: không hỏi
        self.assertEqual(len(self._mock()._ORDERS), 0)
        self.assertFalse([c for c in tc if c["name"] == "order.create"])

    def test_focus_product_keeps_shortlist_top_from_being_main_price(self):
        from src.harness.extractor import extract_claims
        calls = [{"name": "product.shortlist", "args": {}, "result": {"items": [{"sku": "SKU-SS-AX40", "name": "Máy lọc không khí Samsung AX40", "list_price_vnd": 6490000}]}}]
        text = "Ngoài ra còn Máy lọc không khí Samsung AX40 - Giá: 6.490.000 VNĐ."
        self.assertEqual([c["field"] for c in extract_claims(text, calls)], ["price_vnd"])                       # chưa bàn gì: đầu shortlist là chủ đề
        self.assertEqual([c["field"] for c in extract_claims(text, calls, focus_sku="SKU-XM-4P")], ["alt_price_vnd"])


del OrderSyncTest       # không để unittest nạp lại các test của lớp đó từ file này



if __name__ == "__main__":
    unittest.main()


class InventedSkuRepairTest(unittest.TestCase):
    _setup, _run, _mock, _create = ClosingTurnTest._setup, ClosingTurnTest._run, ClosingTurnTest._mock, ClosingTurnTest.__dict__["_create"]

    def test_invented_code_maps_to_last_looked_up_simple_product(self):          # A3: sửa trước rồi mới chặn
        self._setup(order_gate=True)
        self._run([("pricing.get_quote", {"sku": AP_Y, "qty": 1})])
        self._run([self._create("MADE-UP-1", 1, payment=None)])
        self.assertTrue(all(a.get("sku") == AP_Y for a in self.orch._gate_retry_args.values()))
        self.assertTrue(self.orch._gate_retry_args)                                # đơn nháp mở với SKU thật, không bị chặn


class NamedProductTest(unittest.TestCase):
    def test_accessory_name_is_not_read_as_the_main_unit(self):                 # TEST-200
        from types import SimpleNamespace
        from src.harness.orchestrator import HarnessOrchestrator as H
        o = H.__new__(H)
        names = {"SKU-AP-X": "Máy lọc không khí AirPure X", "SKU-AP-FLT-X": "Màng lọc thay thế AirPure X/Y"}
        o._call_log = {"S": [{"name": "catalog.search", "args": {}, "result": {"items": [{"sku": "SKU-AP-X"}, {"sku": "SKU-AP-FLT-X"}]}}]}
        o.retriever = SimpleNamespace(products=[{"sku": k, "name": v} for k, v in names.items()])
        o._product_info = lambda s: {"name": names.get(s, "")}
        o._parent_sku = lambda s: s
        o._readings = {}
        self.assertEqual(o._named_in_call("S", "giao Màng lọc thay thế AirPure X/Y tới Cần Thơ"), "SKU-AP-FLT-X")
        self.assertIsNone(o._named_in_call("S", "giao cái máy hôm trước"))
        o._readings = {"S": SimpleNamespace(product_sku="SKU-AP-FLT-X")}                  # tên nói tắt/ASR méo: dùng SKU bộ đọc đã kiểm
        self.assertEqual(o._named_in_call("S", "màng lọc thay thế AirPure X"), "SKU-AP-FLT-X")

    def test_alias_sound_alike_is_no_longer_a_product(self):                     # "phí phát sinh" từng khớp alias "phát" → Fatz
        from src.harness.orchestrator import HarnessOrchestrator as H
        o = H.__new__(H)
        o._call_log = {"S": [{"name": "pricing.get_quote", "args": {"sku": "SKU-MB-MON"}, "result": {}}]}
        o.retriever = None
        o._product_info = lambda s: {"name": "Máy hâm sữa Fatz 4 chức năng" if s == "SKU-MB-MON" else ""}
        o._parent_sku = lambda s: s
        o._readings = {"S": None}
        self.assertIsNone(o._named_in_call("S", "phí phát sinh bao nhiêu"))


class MovedCallbackTest(unittest.TestCase):
    def test_moved_callback_date_is_told(self):                                  # TEST-29
        from src.harness.orchestrator import HarnessOrchestrator as H
        calls = [{"name": "schedule.callback", "result": {"callback_at": "2026-10-27T08:00", "moved_from": "2026-10-26T08:00:00"}}]
        t = H._say_moved_callback("Dạ em đã ghi nhận lịch gọi lại thứ 2 ngày 26/10 ạ.", calls)
        self.assertIn("27/10", t)
        self.assertIn("nghỉ", t)
        self.assertEqual(H._say_moved_callback("Dạ em hẹn 8:00 ngày 27/10 ạ.", calls), "Dạ em hẹn 8:00 ngày 27/10 ạ.")


class NoBasisReplyTest(unittest.TestCase):
    def test_known_product_is_not_asked_again(self):                             # SC-TV-11
        from types import SimpleNamespace
        from src.harness.orchestrator import HarnessOrchestrator as H
        o = H.__new__(H)
        calls = [{"name": "product.shortlist", "result": {"no_basis": True, "slots_used": {"budget_vnd": 600000}, "items": [{"name": "Áo khoác gió Windbreak", "list_price_vnd": 690000}]}}]
        known = o._no_basis_reply(calls, SimpleNamespace(honorific="chị", product_advised="SKU-JK-WND"))
        self.assertNotIn("sản phẩm nào", known)
        self.assertIn("690.000", known)
        self.assertIn("sản phẩm nào", o._no_basis_reply(calls, SimpleNamespace(honorific="chị", product_advised=None)))


class VariantFromCustomerWordsTest(unittest.TestCase):
    def test_whole_word_match(self):                                             # TEST-179: "L be" không được thành M-BE ("m" trong "mua")
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        self.assertEqual(o._resolve_variant_by_attributes("SKU-JK-DWN", "Ngọc chốt mua Áo phao lông vũ Warmly bản L be"), "SKU-JK-DWN-L-BE")
        self.assertEqual(o._resolve_variant_by_attributes("SKU-SN-TRK", "Giày trekking HikePro size 40 màu trắng"), "SKU-SN-TRK-40-TRANG")


class ReaderProductTest(unittest.TestCase):
    def test_product_must_be_in_the_given_list(self):                            # TEST-44 "combo đó"
        from src.harness.reply_reader import verify
        text = "ok lên đơn combo đó cho anh nhé"
        raw = {"product_sku": "SKU-BDL-AIR", "product_quote": "lên đơn combo đó"}
        y, combo = {"sku": "SKU-AP-Y", "name": "Máy lọc không khí AirPure Y"}, {"sku": "SKU-BDL-AIR", "name": "Combo AirPure Y + 2 màng lọc"}
        self.assertEqual(verify(raw, text, [y, combo]).product_sku, "SKU-BDL-AIR")
        self.assertIsNone(verify(raw, text, [y]).product_sku)                                     # mã ngoài danh sách ứng viên (catalog) → bỏ

    def test_made_up_quote_is_dropped(self):
        from src.harness.reply_reader import verify
        c = [{"sku": "SKU-AP-FLT-X", "name": "Màng lọc thay thế AirPure X/Y"}]
        self.assertIsNone(verify({"product_sku": "SKU-AP-FLT-X", "product_quote": "màng lọc AirPure"}, "phí phát sinh bao nhiêu", c).product_sku)
        self.assertIsNone(verify({"product_sku": "SKU-AP-FLT-X", "product_quote": ""}, "màng lọc thay thế AirPure X", c).product_sku)
        self.assertEqual(verify({"product_sku": "SKU-AP-FLT-X", "product_quote": "màng lọc thay thế AirPure X"}, "màng lọc thay thế AirPure X", c).product_sku, "SKU-AP-FLT-X")

    def test_read_reply_shows_candidates_and_keeps_only_checked_sku(self):     # "giày hai pro": không đoán bừa; có ngữ cảnh RunLite 2 Pro thì LLM chọn mã đó
        from src.harness.reply_reader import read_reply
        from tests.test_reply_reader import ReaderLLM
        cands = [{"sku": "SKU-SN-TRK", "name": "Giày trekking HikePro"}, {"sku": "SKU-SN-RUN2", "name": "Giày chạy bộ RunLite 2 Pro"}]
        seen = []
        llm = ReaderLLM(lambda t: seen.append(t) or {})
        self.assertIsNone(read_reply(llm, "giày hai pro size 42", "", {"candidates": cands}).product_sku)
        self.assertIn("SKU-SN-RUN2 — Giày chạy bộ RunLite 2 Pro", seen[0])
        llm.reader = lambda t: {"product_sku": "SKU-SN-RUN2", "product_quote": "giày hai pro"}
        self.assertEqual(read_reply(llm, "giày hai pro size 42", "", {"candidates": cands}).product_sku, "SKU-SN-RUN2")
        llm.reader = lambda t: {"product_sku": "SKU-SN-RUN9", "product_quote": "giày hai pro"}
        self.assertIsNone(read_reply(llm, "giày hai pro size 42", "", {"candidates": cands}).product_sku)

    def test_candidates_cover_accessories_and_combos(self):                     # ưu tiên đủ: món phụ kiện/combo cùng họ phải có trong danh sách LLM chọn
        import json, os
        from src.harness.reply_reader import product_candidates
        from src.catalog.retriever import DEFAULT_PRODUCTS_PATH
        cat = json.load(open(DEFAULT_PRODUCTS_PATH, encoding="utf-8"))
        cat = cat["products"] if isinstance(cat, dict) else cat
        skus = lambda t, seen=(): {c["sku"] for c in product_candidates(t, cat, list(seen))}
        self.assertTrue({"SKU-AP-FLT-X", "SKU-AP-X"} <= skus("màng lọc thay thế AirPure X"))
        self.assertIn("SKU-BDL-AIR", skus("Combo AirPure Y"))
        self.assertIn("SKU-SN-SOCK", skus("Tất RunLite"))
        self.assertIn("SKU-SN-RUN2", skus("giày hai pro size 42", ["SKU-SN-RUN2"]))
        self.assertTrue(all(c["name"] for c in product_candidates("phí phát sinh bao nhiêu", cat)))

    def test_extra_item_name_must_be_quoted(self):                               # TEST-153
        from src.harness.reply_reader import verify
        text = "Lấy cho Trang một Máy lọc nước RO Karofi 9 lõi kèm thêm một Bộ lõi lọc thay thế RO 1-2-3 (390.000đ) dự phòng"
        r = verify({"extra_items": [{"name": "Bộ lõi lọc thay thế RO 1-2-3", "qty": 1, "quote": "kèm thêm một Bộ lõi lọc thay thế RO 1-2-3"},
                                    {"name": "Bình nước", "qty": 1, "quote": "dự phòng"}]}, text)
        self.assertEqual(r.extra_items, [{"name": "Bộ lõi lọc thay thế RO 1-2-3", "qty": 1}])


class QtyChangeKeepsDraftTest(unittest.TestCase):
    def test_lowering_qty_is_not_walking_away(self):                             # TEST-49
        from types import SimpleNamespace
        from src.harness.order_gate import OrderGate, OrderDraft, OrderKnown, ProductInfo
        g = OrderGate()
        g.begin_turn("S", 1, "mua 2 máy", SimpleNamespace(agrees=False, declines=False, affirmed=[], qty=2, payment="COD"))
        g.evaluate("S", OrderDraft(sku="SKU-SS-AX40", qty=2), OrderKnown(caller_phone="0910388034"), ProductInfo(name="AX40"))
        g.begin_turn("S", 2, "ngại chuyển khoản lắm, giảm xuống lấy 1 chiếc trả COD", SimpleNamespace(agrees=False, declines=True, affirmed=[], qty=1, payment="COD"))
        self.assertNotEqual(g.state("S").abandoned_turn, 2)
        g.begin_turn("S", 3, "thôi không mua nữa", SimpleNamespace(agrees=False, declines=True, affirmed=[], qty=None, payment=None))
        self.assertEqual(g.state("S").abandoned_turn, 3)


class SkuPrefixTest(unittest.TestCase):
    def test_code_without_prefix(self):                                           # TEST-67 "AP-Y"
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        self.assertEqual(o._canonical_sku("AP-Y", "", None), "SKU-AP-Y")
        self.assertEqual(o._canonical_sku("XM-4L", "", None), "SKU-XM-4L")


class ReturnAndPromoTest(unittest.TestCase):
    def setUp(self):
        from tests._helpers import build_components
        self.o = build_components(order_gate=True)["orchestrator"]

    def test_discontinued_model_is_recognised(self):                             # SC-GEN-14 / TEST-11
        from src.harness.orchestrator import fold
        said = lambda t: set(fold(t).split())
        self.assertEqual(self.o._discontinued_named(said("còn bán mẫu máy lọc không khí AirPure X bản 2024 không em?"), "SKU-AP-X"), "SKU-AP-X-2024")
        self.assertIsNone(self.o._discontinued_named(said("máy lọc không khí AirPure X còn không"), "SKU-AP-X"))

    def test_ineligible_reason_is_explained(self):                               # TEST-08
        r = self.o._explain_ineligible({"sku": "SKU-SN-RUN2-43-DEN", "ineligible_promos": [{"promo_code": "RUN-10", "reason": "exclude_variant_size"}]})
        self.assertEqual(r["ineligible_promos"][0]["reason"], "Mã RUN-10 không áp dụng cho size 43")

    def test_exchange_after_return_window_is_refused(self):                      # TEST-111/179/211 cuộc 2
        class L:
            def complete_json(self, msgs):
                return {"days": 12, "quote": "trôi qua 12 hôm"}, {}
        self.o.mcp.execute_tool = (lambda f: lambda name, args, caller="": {"orders": [{"sku": "SKU-SN-CAS-41-DEN", "created_on": "2026-10-08"}]} if name == "order.status" else f(name, args, caller=caller))(self.o.mcp.execute_tool)
        args = {"order_id": "OD1", "action": "exchange_size", "new_variant_sku": "SKU-SN-CAS-42-DEN"}
        late = self.o._return_window_expired(args, ["Từ hôm nhận tới giờ trôi qua 12 hôm mất rồi"], "2026-10-20", L())
        self.assertEqual((late["error"], late["return_days"]), ("return_window_expired", 7))
        class L2(L):
            def complete_json(self, msgs):
                return {"days": 3, "quote": "nhận 3 hôm"}, {}
        self.assertIsNone(self.o._return_window_expired(args, ["nhận 3 hôm thì thấy chật"], "2026-10-20", L2()))


class LateBasketTest(unittest.TestCase):
    _setup, _run, _mock, _create = ClosingTurnTest._setup, ClosingTurnTest._run, ClosingTurnTest._mock, ClosingTurnTest.__dict__["_create"]
    _close, _channel = ClosingTurnTest._close, ClosingTurnTest.__dict__["_channel"]

    def test_basket_quoted_after_the_draft_is_ordered(self):                     # TEST-153: máy + bộ lõi lọc
        self._setup(order_gate=True)
        self._run([self._create("SKU-WF-RO9", 1, payment=None),                     # đơn nháp mở với 1 món, rồi LLM mới báo giá cả giỏ
                   ("pricing.quote_order", {"lines": [{"sku": "SKU-WF-RO9", "qty": 1}, {"sku": "SKU-WF-CORE", "qty": 1}]})])
        self._run([("pricing.get_quote", {"sku": "SKU-WF-RO9", "qty": 1})])         # báo giá lẻ sau đó không bỏ món kia
        _, close = self._close()
        _, tc, _ = close()
        oc = [c for c in tc if c["name"] == "order.create"]
        self.assertEqual({l["sku"] for l in oc[0]["args"]["lines"]}, {"SKU-WF-RO9", "SKU-WF-CORE"})


class ExactNameTest(unittest.TestCase):
    def test_exact_name_of_unlooked_product(self):                               # SC-TV-18 cuộc 3
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        o._call_log = {"S": [{"name": "pricing.get_quote", "args": {"sku": "SKU-XM-4L"}, "result": {}}]}
        o._readings = {"S": None}
        self.assertEqual(o._named_in_call("S", "Đổi sang chốt luôn bản Xiaomi Smart 4 Pro nhé"), "SKU-XM-4P")     # hãng + mẫu khớp tuyệt đối, không cần bộ đọc

    def test_named_product_rules_on_the_real_catalog(self):
        """Thứ tự chung của `_named_in_call` trên catalog thật: tên đầy đủ → hãng+mẫu khớp tuyệt đối (một SKU, không mơ hồ) → bộ đọc."""
        from types import SimpleNamespace
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        o._call_log = {"S": [{"name": "pricing.get_quote", "args": {"sku": "SKU-MB-MON"}, "result": {}}, {"name": "pricing.get_quote", "args": {"sku": "SKU-AP-X"}, "result": {}},
                             {"name": "pricing.get_quote", "args": {"sku": "SKU-BDL-MOM"}, "result": {}}]}
        o._readings = {"S": None}
        self.assertIsNone(o._named_in_call("S", "phí phát sinh bao nhiêu"))                       # "phát" là alias hãng trơn của Fatz
        self.assertIsNone(o._named_in_call("S", "giày hai pro size 42"))                          # "hai pro" là alias hãng trơn của HikePro
        self.assertEqual(o._named_in_call("S", "Lấy cho chị một bộ Spectra S1 4.290.000đ"), "SKU-MB-PUMP1")      # SC-TV-13 cuộc 3: không phải combo
        self.assertIsNone(o._named_in_call("S", "màng lọc thay thế AirPure X"))                   # TEST-200: không quy về máy AirPure X
        o._readings = {"S": SimpleNamespace(product_sku="SKU-AP-FLT-X")}
        self.assertEqual(o._named_in_call("S", "màng lọc thay thế AirPure X"), "SKU-AP-FLT-X")    # bộ đọc chọn màng lọc
        o._readings = {"S": SimpleNamespace(product_sku="SKU-BDL-MOM")}
        self.assertEqual(o._named_in_call("S", "Lấy cho chị một bộ Spectra S1"), "SKU-MB-PUMP1")   # tên gọi chính xác thắng bộ đọc
        o._readings = {"S": SimpleNamespace(product_sku="SKU-SN-RUN2")}
        self.assertEqual(o._named_in_call("S", "giày hai pro size 42"), "SKU-SN-RUN2")            # có ngữ cảnh: bộ đọc quyết


class SessionCarryTest(unittest.TestCase):
    def test_state_follows_the_customer_when_identity_changes_mid_call(self):   # TEST-148: khách chat đọc SĐT ở lượt 3
        from types import SimpleNamespace
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        t = SimpleNamespace(contact_id="zalo.son.test_148")
        o._carry_session(t, "2026-10-15", "call_1", "SESS-ANON-2026-10-15")
        o._customer_texts["SESS-ANON-2026-10-15"] = ["Giày trekking HikePro size 40 màu trắng"]
        o._gate_retry_args["SESS-ANON-2026-10-15"] = {"sku": "SKU-SN-TRK"}
        o.memory.set_working("SESS-ANON-2026-10-15", current_turn=3)
        o._carry_session(t, "2026-10-15", "call_1", "SESS-C099-2026-10-15")
        self.assertEqual(o._customer_texts.get("SESS-C099-2026-10-15"), ["Giày trekking HikePro size 40 màu trắng"])
        self.assertEqual(o._gate_retry_args.get("SESS-C099-2026-10-15"), {"sku": "SKU-SN-TRK"})
        self.assertEqual(o.memory.get_working("SESS-C099-2026-10-15").current_turn, 3)
        o._carry_session(SimpleNamespace(contact_id="zalo.khac"), "2026-10-15", "call_1", "SESS-C100-2026-10-15")   # liên hệ khác: không gộp
        self.assertNotIn("SESS-C100-2026-10-15", o._customer_texts)


class NamedBeatsReaderTest(unittest.TestCase):
    def test_exact_name_wins_over_reader_choice(self):                           # SC-TV-13 cuộc 3: "một bộ Spectra S1" không phải combo
        from types import SimpleNamespace
        from tests._helpers import build_components
        o = build_components(order_gate=True)["orchestrator"]
        sid = "S"
        o._call_log = {sid: [{"name": "pricing.get_quote", "args": {"sku": "SKU-BDL-MOM"}, "result": {}}]}
        o._readings = {sid: SimpleNamespace(product_sku="SKU-BDL-MOM")}               # bộ đọc chọn sai combo: tên hãng + mẫu khách gọi đúng vẫn thắng
        o.order_gate.state(sid).texts = ["Lấy cho chị một bộ Spectra S1 4.290.000đ giao 31 đường Láng"]
        self.assertEqual(o._simple_product_in_play(sid, SimpleNamespace(product_advised=None)), "SKU-MB-PUMP1")


class ReaderComboEndToEndTest(unittest.TestCase):
    """Đường "bộ đọc chỉ ra sản phẩm" từ đầu tới cuối (TEST-44): khách nói "lên đơn combo đó" → đơn nháp mở ĐÚNG combo dù sản phẩm tra gần nhất là máy lẻ."""
    def test_combo_named_by_pointing_opens_the_draft_on_the_combo(self):
        from tests.test_reply_reader import ReaderLLM, burn_early
        from tests.test_order_gate import GateBase, NEW_PHONE

        class Case(GateBase):
            def runTest(self):
                pass
        case = Case()
        case.setUp()
        case.llm = ReaderLLM(lambda t: {})
        case.orch.llm_client = case.llm
        burn_early(case)
        case.turn(NEW_PHONE, "cho chị xem combo với máy AirPure Y", [("pricing.get_quote", {"sku": "SKU-BDL-AIR", "qty": 1}), ("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 1})])
        prompts = []
        case.llm.reader = lambda t: prompts.append(t) or ({"order_intent": "commit", "intent_quote": "lên đơn combo đó", "product_sku": "SKU-BDL-AIR", "product_quote": "combo đó"}
                                                          if "combo đó" in t else {})
        case.turn(NEW_PHONE, "ok lên đơn combo đó cho anh nhé", [])
        self.assertTrue(any("SKU-BDL-AIR — Combo AirPure Y + 2 màng lọc" in p for p in prompts))      # ứng viên tới được LLM
        self.assertEqual([a["sku"] for a in case.orch._gate_retry_args.values()], ["SKU-BDL-AIR"])



class OrderSkuFollowsCustomerTest(unittest.TestCase):
    """_gate_order_create: SKU có thật của LLM chính KHÁC sản phẩm khách gọi chắc chắn → theo khách (lần nhắc mới nhất); không chắc → không ghi đè."""
    def setUp(self):
        from tests.test_reply_reader import ReaderLLM, burn_early
        from tests.test_order_gate import GateBase

        class Case(GateBase):
            def runTest(self):
                pass
        self.case = Case()
        self.case.setUp()
        self.case.llm = ReaderLLM(lambda t: {})
        self.case.orch.llm_client = self.case.llm
        burn_early(self.case)

    def say(self, text, calls=(), reader=None):
        from tests.test_order_gate import NEW_PHONE
        self.case.llm.reader = reader or (lambda t: {})
        return self.case.turn(NEW_PHONE, text, list(calls))

    def order(self, sku):
        return [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": sku, "qty": 1})]

    def draft(self):
        return [a.get("sku") for a in self.case.orch._gate_retry_args.values()]

    def test_named_single_unit_beats_llm_combo(self):
        self.say("cho anh lấy một máy AirPure Y nhé", self.order("SKU-BDL-AIR"))
        self.assertEqual(self.draft(), ["SKU-AP-Y"])

    def test_pointing_at_combo_via_reader_beats_llm_single_unit(self):
        self.say("bên em có những gì", [("pricing.get_quote", {"sku": "SKU-BDL-AIR", "qty": 1}), ("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 1})])
        self.say("ok lấy cái combo đó nha", self.order("SKU-AP-Y"),
                 reader=lambda t: {"product_sku": "SKU-BDL-AIR", "product_quote": "cái combo đó"} if "combo đó" in t else {})
        self.assertEqual(self.draft(), ["SKU-BDL-AIR"])

    def test_latest_mention_wins_when_customer_changes_mind(self):
        self.say("cho chị hỏi máy AirPure Y giá sao", [("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 1})])
        self.say("thôi chị lấy Samsung AX40", self.order("SKU-AP-Y"))
        self.assertEqual(self.draft(), ["SKU-SS-AX40"])

    def test_vague_reply_keeps_llm_sku(self):
        self.say("ok lấy cái đó nhé", self.order("SKU-BDL-AIR"))
        self.assertEqual(self.draft(), ["SKU-BDL-AIR"])

    def test_made_up_reader_quote_does_not_override(self):
        self.say("bên em có những gì", [("pricing.get_quote", {"sku": "SKU-BDL-AIR", "qty": 1}), ("pricing.get_quote", {"sku": "SKU-AP-Y", "qty": 1})])
        self.say("ok chốt cái kia cho anh", self.order("SKU-BDL-AIR"), reader=lambda t: {"product_sku": "SKU-AP-Y", "product_quote": "máy lẻ AirPure Y"})
        self.assertEqual(self.draft(), ["SKU-BDL-AIR"])

    def test_older_conflicting_mention_asks_instead_of_creating(self):
        self.say("cho anh lấy một máy AirPure Y")
        reply, tool_calls, *_ = self.say("ok chốt luôn em", self.order("SKU-BDL-AIR"))
        self.assertEqual(self.draft(), [])
        self.assertFalse(self.case.created(tool_calls))
        sid = next(iter(self.case.orch._readings))
        self.assertEqual(self.case.orch.order_gate.state(sid).last_decision.get("action"), "product_conflict")


    def test_reader_pick_from_an_earlier_turn_still_wins_over_open_draft(self):
        self.say("cho anh lấy một máy AirPure Y", self.order("SKU-AP-Y"))
        self.assertEqual(self.draft(), ["SKU-AP-Y"])
        self.say("bên em có combo nào không", [("pricing.get_quote", {"sku": "SKU-BDL-AIR", "qty": 1})])
        self.say("à thôi anh lấy cái combo đó", reader=lambda t: {"product_sku": "SKU-BDL-AIR", "product_quote": "cái combo đó"} if "combo đó" in t else {})
        self.assertEqual(self.draft(), ["SKU-BDL-AIR"])                                        # bộ điều khiển đơn nháp chạy lại gate: lời khách mới nhất thắng
        sid = next(iter(self.case.orch._readings))
        self.case.orch._readings[sid] = None                                                   # lượt sau không còn kết quả bộ đọc của lượt "combo đó"
        self.assertEqual(self.case.orch._customer_named_product(sid), ("SKU-BDL-AIR", True))
        self.case.orch.order_gate.state(sid).texts.append("")                                 # lượt chốt (không có lời khách)
        self.assertEqual(self.case.orch._customer_named_product(sid), ("SKU-BDL-AIR", False))   # vẫn nhớ theo lượt


class CandidateRankingTest(unittest.TestCase):
    def test_rare_shared_words_rank_above_common_ones(self):                    # "không" (đúng không) có ở nhiều tên → không được đẩy combo ra khỏi 8 ứng viên
        import json
        from src.harness.reply_reader import product_candidates
        from src.catalog.retriever import DEFAULT_PRODUCTS_PATH
        cat = json.load(open(DEFAULT_PRODUCTS_PATH, encoding="utf-8"))
        cat = cat["products"] if isinstance(cat, dict) else cat
        got = [c["sku"] for c in product_candidates("combo đó rẻ hơn đúng không, ok lên đơn combo đó cho anh nhé", cat, ["SKU-AP-Y", "SKU-AP-MINI", "SKU-AP-X"])]
        self.assertLessEqual(len(got), 8)
        self.assertIn("SKU-BDL-AIR", got)



class CommitWithPriceTest(unittest.TestCase):
    """order_intent khi khách nêu giá. LLM ở đây là GIẢ (kịch bản JSON theo đúng nguyên tắc mới của prompt) → test kiểm đi dây: commit + giá → code mở đơn nháp
    với GIÁ CATALOG; mặc cả/hỏi giá → không mở; vừa chốt vừa xin bớt → không mở (trả lời giá trước). LLM thật có theo prompt hay không: scripts/eval_reply_reader.py (cần duyệt)."""
    COMMITS = [("lấy cho anh một máy AirPure Mini giá 3.290.000 nhé, COD", "SKU-AP-MINI"),                 # giá có thể đúng/sai: gate dùng giá catalog
               ("chốt em một máy Xiaomi Smart 4 Lite 1 triệu, giao về nhà chị", "SKU-XM-4L"),              # giá sai hẳn
               ("đặt cho tôi một máy Samsung AX40 giá 6 triệu, chuyển khoản", "SKU-SS-AX40")]
    BARGAINS = ["máy AirPure Mini 2 triệu được không em", "bớt cho chị cái Xiaomi Smart 4 Lite đi, giá đó cao quá", "Samsung AX40 5 triệu thì anh lấy được không"]
    ASKS = ["máy AirPure Mini giá bao nhiêu em", "Xiaomi Smart 4 Lite giờ bán nhiêu", "cho hỏi giá Samsung AX40"]

    @staticmethod
    def fake_reader(text):
        """Mô phỏng bộ đọc làm ĐÚNG prompt mới (để kiểm phần code; không kiểm LLM thật)."""
        t = text.split("Lời khách:")[-1].strip()
        commit = any(v in t for v in ("lấy cho", "chốt em", "đặt cho"))
        price = any(v in t for v in ("được không", "bớt", "bao nhiêu", "bán nhiêu", "hỏi giá"))
        verb = next((v for v in ("lấy cho", "chốt em", "đặt cho") if v in t), "")
        out = {"order_intent": "commit", "intent_quote": verb} if commit else {}
        if price:
            out.update(asks_price_promo=True, price_promo_quote=next(v for v in ("được không", "bớt", "bao nhiêu", "bán nhiêu", "hỏi giá") if v in t))
        return out

    def run_one(self, text, sku):
        from tests.test_reply_reader import ReaderLLM, burn_early
        from tests.test_order_gate import GateBase, NEW_PHONE

        class Case(GateBase):
            def runTest(self):
                pass
        case = Case()
        case.setUp()
        case.llm = ReaderLLM(lambda t: {})
        case.orch.llm_client = case.llm
        burn_early(case)
        case.turn(NEW_PHONE, "cho xem máy lọc không khí", [("pricing.get_quote", {"sku": sku, "qty": 1})])     # agent đã báo giá: vào ngữ cảnh mua
        case.llm.reader = self.fake_reader
        case.turn(NEW_PHONE, text, [])
        return case.orch, list(case.orch._gate_retry_args.values())

    def test_commit_with_price_opens_draft_at_catalog_price(self):
        for text, sku in self.COMMITS:
            o, drafts = self.run_one(text, sku)
            self.assertEqual([d["sku"] for d in drafts], [sku], text)
            self.assertEqual(drafts[0]["price_vnd"], o.mcp.execute_tool("pricing.get_quote", {"sku": sku, "on": "2026-10-15", "qty": 1}, caller="HarnessOrchestrator")["final_price_vnd"], text)

    def test_bargain_or_price_question_does_not_open_draft(self):
        for text, sku in zip(self.BARGAINS + self.ASKS, ["SKU-AP-MINI", "SKU-XM-4L", "SKU-SS-AX40"] * 2):
            _, drafts = self.run_one(text, sku)
            self.assertEqual(drafts, [], text)

    def test_commit_plus_discount_request_answers_price_first(self):
        for text, sku in (("lấy cho anh một máy AirPure Mini, bớt anh 100 nghìn nhé", "SKU-AP-MINI"), ("chốt em một máy Xiaomi Smart 4 Lite, bớt chút đi", "SKU-XM-4L"),
                          ("đặt cho tôi một máy Samsung AX40 nhưng bớt 200k", "SKU-SS-AX40")):
            _, drafts = self.run_one(text, sku)
            self.assertEqual(drafts, [], text)

    def test_prompt_states_the_rules_without_scenario_specifics(self):
        from src.harness.reply_reader import PROMPT
        for rule in ("KỂ CẢ khi khách nêu một con số giá", "Mặc cả = hỏi hoặc đề nghị giá thấp hơn mà KHÔNG có lời chốt", "Vừa chốt vừa xin bớt"):
            self.assertIn(rule, PROMPT)
        self.assertNotRegex(PROMPT, r"\d\.\d{3}\.\d{3}|Spectra|AirPure|SKU-")


if __name__ == "__main__":
    unittest.main()
