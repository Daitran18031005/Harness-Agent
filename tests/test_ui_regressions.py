"""Hồi quy từ các lỗi người dùng THẤY trên UI demo (ảnh chụp 2026-10-22). Test cũ dùng lời khách viết hoa chuẩn do chính mã viết ra nên không bắt được:
tên gõ thường/đứng cuối câu địa chỉ, hỏi lặp, khách từ chối/mặc cả giữa đơn, hết hàng, tên khách không được nhớ, xưng hô LLM tự đoán, rào cản không cập nhật, đổi kênh."""
import unittest

from tests.test_order_gate import GateBase, NEW_PHONE, SKU39, order

RO10, RO10_PRICE = "SKU-WF-RO10", 6890000


def order_ro10(price=RO10_PRICE, **kw):
    return ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": RO10, "qty": 1, "price_vnd": price, **kw})


class NameRecognitionTest(GateBase):
    def test_name_at_the_end_of_the_address_is_understood_and_not_asked_again(self):
        """Ảnh 1–3: "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại" → agent hỏi lại tên 3 lần."""
        self.turn(NEW_PHONE, "cho tôi 39 đen đi", [order()])
        txt, tc, meta = self.turn(NEW_PHONE, "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại", [])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_name"]["status"], "stated")
        self.assertEqual(ev["fields"]["address"]["status"], "stated")
        self.assertEqual(ev["missing"], ["payment"])
        self.assertNotIn("tên người nhận", txt)
        txt, tc, meta = self.turn(NEW_PHONE, "COD", [])
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        self.assertIn("Đại", txt)
        self.assertNotIn("hồ chí minh, Đại", txt)                                 # tên không dính vào địa chỉ khi đọc lại đơn
        self.assertEqual(self.llm.calls, 1)

    def test_lowercase_name_next_to_payment_is_understood(self):
        """Ảnh 2: "đại, COD" rồi "đại" — tên gõ thường không được nhận."""
        self.turn(NEW_PHONE, "cho tôi 39 đen đi", [order()])
        self.turn(NEW_PHONE, "giao về 45/1 đường 10 phường linh đông hồ chí minh", [])
        txt, tc, meta = self.turn(NEW_PHONE, "đại, COD", [])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_name"]["status"], "stated")
        self.assertEqual(ev["fields"]["payment"]["status"], "stated")
        self.assertNotIn("tên người nhận", txt)

    def test_extract_helpers(self):
        from src.harness.order_gate import extract_recipient_name as n
        self.assertEqual(n("đại", True), "Đại")
        self.assertEqual(n("trần quang đại", True), "Trần Quang Đại")
        self.assertIsNone(n("ok", True))
        self.assertIsNone(n("để suy nghĩ đã", True))
        self.assertIsNone(n("đại", False))                                        # gate không chờ tên và không có cụm dẫn → không đoán


class PhoneAffirmedBeforeAskedTest(GateBase):
    ADDR = "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại"

    def test_dung_sdt_said_before_the_gate_first_asks_counts_as_confirmation(self):
        """ui_replay_7 lượt 6–7: LLM tự hỏi SĐT, khách đáp "đúng sdt, …" trước khi gate hỏi lần đầu → gate đừng hỏi lại SĐT."""
        self.turn(NEW_PHONE, "ok lấy 39 đen", [])
        txt, tc, meta = self.turn(NEW_PHONE, self.ADDR, [order()])
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["fields"]["recipient_phone"]["status"], "confirmed")
        self.assertEqual(ev["to_confirm"], [])
        self.assertNotIn("số điện thoại", txt)
        _, _, meta = self.turn(NEW_PHONE, "đại, COD", [])                         # lượt sau không bị hỏi lại SĐT dù khách không nhắc tới nó
        self.assertEqual(meta["order_gate"][-1]["to_confirm"], [])

    def test_negated_or_other_number_does_not_count(self):
        from src.harness.order_gate import OrderGate
        g = OrderGate()
        for i, t in enumerate(("không đúng sdt, số khác", "sai sdt rồi", "chưa chắc số này đúng", "ok lấy 39 đen")):
            g.begin_turn("s", i, t)
        self.assertFalse(g.state("s").phone_ok)
        g.begin_turn("s", 9, "đúng số này, giao về Hà Nội")
        self.assertTrue(g.state("s").phone_ok)


class ReaskIgnoresInfoGivenThisTurnTest(GateBase):
    def test_address_given_this_turn_is_not_treated_as_unanswered(self):
        """ui_replay_9 lượt 6: khách vừa đưa địa chỉ, LLM hỏi lại địa chỉ → reask đổi thành "Nếu anh/chị chưa tiện cho em địa chỉ thì không sao" (sai sự thật)."""
        self.turn(NEW_PHONE, "ok lấy 39 đen", [("inventory.check", {"sku": "SKU-SN-CAS-39-DEN"})], "Dạ anh/chị cho em biết tên người nhận, địa chỉ giao hàng ạ?")
        txt, _, _ = self.turn(NEW_PHONE, "đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại", [], "Dạ em cảm ơn. Anh/chị cho em xin địa chỉ giao hàng ạ?")
        self.assertNotIn("chưa tiện", txt)

    def test_reask_still_softens_when_the_customer_really_did_not_answer(self):
        self.turn(NEW_PHONE, "ok lấy 39 đen", [("inventory.check", {"sku": "SKU-SN-CAS-39-DEN"})], "Dạ anh/chị cho em biết địa chỉ giao hàng ạ?")
        txt, _, _ = self.turn(NEW_PHONE, "ừ", [], "Dạ anh/chị cho em xin địa chỉ giao hàng ạ?")
        self.assertIn("chưa tiện", txt)


class ShortlistNoBasisTest(GateBase):
    """ui_replay D: khách đang hỏi máy lọc nước, nói "phòng 20m², có bé 3 tuổi" → shortlist nhóm máy lọc nước điểm 0 (không luật nào áp dụng) mà agent vẫn nói
    "UF Sunhouse phù hợp phòng 20m² và an toàn cho trẻ nhỏ". Kết quả tool phải nói rõ KHÔNG có căn cứ."""
    TEXT = "phòng nhà tôi hai mươi mét vuông, có bé ba tuổi"

    def result(self, category):
        _, tc, _ = self.turn(NEW_PHONE, self.TEXT, [("product.shortlist", {"category": category})])
        return next(c for c in tc if c["name"] == "product.shortlist")["result"]

    def test_category_where_no_rule_applies_is_flagged_no_basis(self):
        r = self.result("máy lọc nước")
        self.assertTrue(r["no_basis"])
        self.assertEqual(r["decision"], {"mode": "no_basis"})
        self.assertIn("KHÔNG được nói sản phẩm 'phù hợp'", r["instruction"])

    def test_category_where_rules_match_is_not_flagged(self):
        r = self.result("máy lọc không khí")
        self.assertNotIn("no_basis", r)
        self.assertTrue(any(i["matched"] for i in r["items"]))

    def test_no_slots_at_all_is_not_flagged(self):
        _, tc, _ = self.turn(NEW_PHONE, "cho mình xem máy lọc nước", [("product.shortlist", {"category": "máy lọc nước"})])
        self.assertNotIn("no_basis", next(c for c in tc if c["name"] == "product.shortlist")["result"])


class RepeatedQuestionTest(GateBase):
    def test_same_question_is_rephrased_then_dropped_never_repeated_forever(self):
        """Ảnh 2–3 và 5–9: agent hỏi cùng một câu liên tục."""
        self.turn(NEW_PHONE, "cho tôi 39 đen đi", [order()])
        actions, texts = [], []
        for _ in range(5):
            txt, _tc, meta = self.turn(NEW_PHONE, "ừ", [], "Dạ vâng ạ.")
            ev = (meta.get("order_gate") or [{}])[-1]
            actions.append(ev.get("action"))
            texts.append(txt)
            if ev.get("action") == "give_up":
                break
        self.assertIn("give_up", actions)
        self.assertTrue(any("chưa ghi nhận được" in t for t in texts))            # lần hỏi lại có đổi cách nói + ví dụ
        self.assertTrue(any("Nguyễn Văn A" in t for t in texts))
        self.assertLessEqual(actions.count("ask"), 2)
        txt, _tc, meta = self.turn(NEW_PHONE, "cảm ơn em", [], "Dạ vâng ạ.")      # sau khi bỏ đơn nháp: không còn nối câu hỏi nào
        self.assertFalse(meta.get("order_gate"))
        self.assertNotIn("địa chỉ", txt.lower())


class DeclineAndBargainTest(GateBase):
    def test_customer_declining_or_bargaining_cancels_the_draft_and_no_question_is_appended(self):
        """Ảnh 5–9: "không, mắc quá tôi muốn giảm thêm 90k" / "hiện tại chưa cần, sẽ gọi lại sau" mà agent vẫn xin địa chỉ + tên người nhận."""
        self.turn(NEW_PHONE, "lấy máy lọc nước RO Kangaroo 10 lõi", [order_ro10()], "Dạ em lên đơn ạ.")
        for text in ("không, mắc quá tôi muốn giảm thêm 90k", "hiện tại chưa cần, sẽ gọi lại sau"):
            txt, _tc, meta = self.turn(NEW_PHONE, text, [], "Dạ em hiểu ạ, em gợi ý mẫu rẻ hơn nhé.")
            self.assertFalse(meta.get("order_gate"), text)
            self.assertNotIn("địa chỉ", txt.lower(), text)
            self.assertNotIn("tên người nhận", txt.lower(), text)

    def test_offering_a_lower_price_does_not_open_an_order(self):
        """Ảnh 5: "mắc quá vậy? 6tr8 lấy luôn" → agent đáp "em chưa thể tạo đơn được, cho em xin địa chỉ…" (không hiểu mặc cả)."""
        txt, tc, meta = self.turn(NEW_PHONE, "mắc quá vậy? 6tr8 lấy luôn", [order_ro10(price=6800000)], "Dạ em lên đơn ạ.")
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["action"], "price_mismatch")
        self.assertIn("6.890.000đ", txt)
        self.assertNotIn("địa chỉ", txt.lower())
        self.assertEqual([c for c in tc if c["name"] == "order.create"], [])
        self.assertNotIn(self._sid(), self.orch._gate_retry_args)                # không giữ đơn nháp với giá sai

    def test_llm_price_slip_without_bargaining_is_corrected_silently(self):
        txt, tc, meta = self.turn(NEW_PHONE, "lấy máy lọc nước RO Kangaroo 10 lõi", [order_ro10(price=6000000)], "Dạ em lên đơn ạ.")
        ev = meta["order_gate"][-1]
        self.assertIn(ev["action"], ("ask", "ask_confirm"))                       # không coi là mặc cả
        self.assertEqual(self.orch._gate_retry_args[self._sid()]["price_vnd"], RO10_PRICE)

    def _sid(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        return f"SESS-{self.c['resolver'].resolve(t).customer_id}-2026-10-15"


class OutOfStockTest(GateBase):
    def test_out_of_stock_variant_is_not_ordered_and_no_address_is_requested(self):
        """Ảnh 1: agent nói "không có sẵn trong kho" nhưng vẫn xin SĐT/địa chỉ/tên."""
        txt, tc, meta = self.turn(NEW_PHONE, "vậy cho tôi 38 xám đi", [order(sku="SKU-SN-RUN2-38-XAM", price_vnd=1521000)], "Dạ em lên đơn ạ.")
        ev = meta["order_gate"][-1]
        self.assertEqual(ev["action"], "out_of_stock")
        self.assertIn("hết hàng", txt)
        self.assertNotIn("địa chỉ", txt.lower())


class CustomerNameAndAddressingTest(GateBase):
    def _brief(self, date="2026-10-15"):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        ident = self.c["resolver"].resolve(t)
        return ident, self.c["brief"].build(ident, date)

    def test_self_introduced_name_is_remembered_and_llm_does_not_guess_gender(self):
        """Ảnh 5–8: "tôi tên Đại" → Call Brief vẫn "Quý khách"; LLM tự gọi "anh Đại" rồi lượt sau lại "anh/chị"."""
        txt, _tc, _m = self.turn(NEW_PHONE, "tôi tên Đại", [], "Dạ em chào anh Đại! Mình cần hỗ trợ gì ạ?")
        self.assertIn("anh/chị Đại", txt)
        self.assertNotIn("anh Đại", txt.replace("anh/chị Đại", ""))
        ident, brief = self._brief()
        self.assertEqual(self.c["memory"].get_profile_facts(ident.customer_id).get("customer_name"), "Đại")
        self.assertEqual(brief.customer_name, "Đại")                              # lượt/cuộc sau Call Brief đã có tên

    def test_stated_honorific_is_used_and_kept(self):
        txt, _tc, _m = self.turn(NEW_PHONE, "anh muốn hỏi máy lọc nước, tôi tên Nam", [], "Dạ em chào chị Nam ạ.")
        self.assertIn("anh Nam", txt)
        _, brief = self._brief()
        self.assertEqual((brief.honorific, brief.customer_name), ("anh", "Nam"))

    def test_crm_name_is_not_overwritten_by_a_self_introduction(self):
        self.turn("0984726714", "tôi tên Đại", [], "Dạ vâng ạ.")
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0984726714")
        ident = self.c["resolver"].resolve(t)
        self.assertEqual(self.c["brief"].build(ident, "2026-10-15").customer_name, "Hoa")

    def test_extract_customer_name(self):
        from src.memory.memory_extractor import extract_customer_name as n
        self.assertEqual(n("tôi tên Đại"), "Đại")
        self.assertEqual(n("mình tên là lan nhé"), "Lan")
        self.assertEqual(n("tôi là Đại, hôm trước tôi có gọi"), "Đại")
        self.assertIsNone(n("tôi là vị khách hôm mười lăm tháng mười"))


class LiveBlockerTest(GateBase):
    def test_blocker_and_objection_are_recorded_immediately_not_only_at_the_end_of_the_call(self):
        """Ảnh 4: Call Brief "Rào cản: Không có" dù khách nói "hiện chưa đủ tiền, đợi vài hôm nữa" / "mắc quá"."""
        self.turn(NEW_PHONE, "hiện chưa đủ tiền, đợi vài hôm nữa", [], "Dạ em hiểu ạ.")
        from src.channels.normalizer import InputChannel
        ident = self.c["resolver"].resolve(self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE))
        facts = self.c["memory"].get_profile_facts(ident.customer_id)
        self.assertEqual(facts.get("blocker"), "chua du tien")
        self.assertEqual(self.c["brief"].build(ident, "2026-10-15").blocker, "chua du tien")
        self.turn(NEW_PHONE, "mắc quá vậy", [], "Dạ ạ.")
        self.assertEqual(self.c["memory"].get_profile_facts(ident.customer_id).get("objection"), "gia cao")

    def test_blocker_detection_phrases(self):
        from src.memory.memory_extractor import detect_blocker as b
        for text, code in (("để chị hỏi chồng đã", "can hoi chong"), ("hiện tại chưa cần, sẽ gọi lại sau", "de suy nghi"), ("để tôi xem chỗ khác", "so sanh gia"),
                           ("hiện chưa đủ tiền", "chua du tien"), ("hỏi bố mẹ đã", "can hoi nguoi nha")):
            self.assertEqual(b(text), code, text)
        self.assertIsNone(b("máy lọc nước 10 lõi giá như nào?"))


class CrossChannelHintsTest(GateBase):
    def test_agent_is_told_to_ask_for_the_previous_phone_when_a_new_contact_claims_earlier_contact(self):
        """Ảnh 7–9: khách nói "hôm trước tôi đã hỏi…" ở kênh khác nhưng hồ sơ trống; agent không hỏi SĐT để nối hồ sơ."""
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("tôi là Đại, hôm trước tôi có gọi để tư vấn máy lọc nước", InputChannel.HOTLINE, NEW_PHONE)
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")
        msgs = self.orch._build_llm_messages(t, brief, [], "2026-10-15", NEW_PHONE)
        ctx = msgs[-2]["content"]
        self.assertIn("số cuộc gọi trước: 0", ctx)                                           # trạng thái do code ghi, không dò từ khóa lời khách
        system = msgs[0]["content"]
        self.assertIn("SĐT/tài khoản", system)
        self.assertIn("TRẢ LỜI câu hỏi hiện tại", system)                                    # ui_replay C: chỉ hỏi SĐT mà bỏ câu "còn hàng không"

    def test_chat_channel_without_phone_asks_for_it(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("máy lọc nước 10 lõi giá bao nhiêu", InputChannel.ZALO, "zalo_demo_1")
        brief = self.c["brief"].build(self.c["resolver"].resolve(t), "2026-10-15")
        ctx = self.orch._build_llm_messages(t, brief, [], "2026-10-15", None)[-2]["content"]
        self.assertIn("xin SĐT", ctx)

    def test_phone_given_in_chat_links_the_anonymous_profile(self):
        from src.channels.normalizer import InputChannel
        t1 = self.c["normalizer"].normalize("tôi quan tâm máy lọc nước", InputChannel.ZALO, "zalo_demo_2")
        a = self.c["resolver"].resolve(t1, memory=self.c["memory"])
        t2 = self.c["normalizer"].normalize("số điện thoại của tôi là 0911223344", InputChannel.ZALO, "zalo_demo_2")
        b = self.c["resolver"].resolve(t2, memory=self.c["memory"])
        t3 = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, "0911223344")
        c = self.c["resolver"].resolve(t3, memory=self.c["memory"])
        self.assertEqual(b.customer_id, c.customer_id)                            # đã đọc SĐT trong chat → gọi hotline bằng SĐT đó nhận ra cùng khách


class EmptySearchIsNotOutOfStockTest(GateBase):
    def test_keyword_search_with_no_result_does_not_mean_out_of_stock(self):
        """Ảnh 1 / replay A: "38 đen" còn 5 nhưng catalog.search("38 đen") rỗng → agent nói "không có sẵn trong kho"."""
        calls = [("catalog.search", {"sku": "SKU-SN-RUN2"}), ("catalog.search", {"query": "38 đen"})]
        _txt, tc, _m = self.turn(NEW_PHONE, "thế 38 đen có không?", calls, "Dạ còn ạ.")
        second = tc[1]["result"]
        self.assertEqual(second["items"][0]["variants"][0], {"variant_sku": "SKU-SN-RUN2-38-DEN", "size": 38, "color": "den", "price_delta_vnd": 0, "in_stock": True, "qty": 5})
        self.assertEqual(second["matched_variant"]["variant_sku"], "SKU-SN-RUN2-38-DEN")
        self.assertTrue(second["matched_variant"]["in_stock"])
        self.assertIn("in_stock=True", second["note"])

    def test_truly_out_of_stock_variant_is_reported_as_such(self):
        calls = [("catalog.search", {"sku": "SKU-SN-RUN2"}), ("catalog.search", {"query": "38 xám"})]
        _txt, tc, _m = self.turn(NEW_PHONE, "vậy cho tôi 38 xám đi", calls, "Dạ ạ.")
        self.assertFalse(tc[1]["result"]["matched_variant"]["in_stock"])

    def test_d_with_stroke_is_stripped_so_color_den_matches_variant_den(self):
        """NFKD không tách "đ": "đen" không bao giờ khớp màu "den" của catalog (lỗi tiềm ẩn ở tầng 2 của bộ sửa SKU)."""
        from src.harness.orchestrator import HarnessOrchestrator as H
        self.assertEqual(H._strip_diacritics("Đen"), "den")
        self.assertEqual(self.orch._resolve_variant_by_attributes("SKU-SN-RUN2", "cho tôi 38 đen đi"), "SKU-SN-RUN2-38-DEN")

    def test_size_that_does_not_exist_lists_the_real_sizes(self):
        calls = [("catalog.search", {"sku": "SKU-SN-RUN2"}), ("catalog.search", {"query": "xám 37"})]
        _txt, tc, _m = self.turn(NEW_PHONE, "có xám 37 ko?", calls, "Dạ ạ.")
        r = tc[1]["result"]
        self.assertEqual(r["items"], [])
        self.assertNotIn("37", r["available_sizes"])
        self.assertIn("38", r["available_sizes"])
        self.assertIn("xam", r["available_colors"])

    def test_empty_search_without_context_warns_the_llm_not_to_conclude(self):
        _txt, tc, _m = self.turn(NEW_PHONE, "có sản phẩm gì tên lạ không", [("catalog.search", {"query": "zzz lạ"})], "Dạ ạ.")
        self.assertIn("KHÔNG được kết luận hết hàng", tc[0]["result"]["note"])


class ReplyCleanupTest(unittest.TestCase):
    def test_enforce_reply_replaces_the_llms_half_said_gate_sentences_instead_of_duplicating(self):
        """Replay A: "Dạ em xin xác nhận lại: số điện thoại…, đúng không ạ? … xác nhận lại … ạ ạ?" — LLM nói dở rồi gate nối thêm cùng nội dung."""
        from src.harness.order_gate import OrderGate
        dec = {"allow": False, "action": "ask", "say": "Dạ mình cho em xin mình chọn size và màu nào ạ?", "must_contain": ["size"]}
        llm = "Dạ em đã ghi nhận ạ. Dạ em xin xác nhận lại: số điện thoại 0986886113, đúng không ạ? Anh cho em xin xác nhận lại kích cỡ và màu sắc nhé."
        out = OrderGate.enforce_reply(llm, dec)
        self.assertEqual(out, "Dạ em đã ghi nhận ạ. " + dec["say"])
        self.assertNotIn("ạ ạ", out)

    def test_ask_sentences_do_not_double_the_polite_particle(self):
        from src.harness.order_gate import ASK
        for v in ASK.values():
            self.assertFalse(v.endswith(" ạ"), v)

    def test_bare_pronouns_follow_the_known_addressing(self):
        from types import SimpleNamespace
        from src.harness.orchestrator import HarnessOrchestrator as H
        unknown = SimpleNamespace(customer_name="Đại", honorific="anh/chị", addressing=lambda: "anh/chị Đại")
        self.assertEqual(H._fix_addressing("Dạ em chào anh Đại! Em rất vui được hỗ trợ anh, chị cứ hỏi nhé; anh/chị Đại ạ.", unknown),
                         "Dạ em chào anh/chị Đại! Em rất vui được hỗ trợ anh/chị, anh/chị cứ hỏi nhé; anh/chị Đại ạ.")
        known = SimpleNamespace(customer_name="Đại", honorific="anh", addressing=lambda: "anh Đại")
        self.assertEqual(H._fix_addressing("Dạ chào chị Đại ạ", known), "Dạ chào anh Đại ạ")


class VariantFromCustomerWordsTest(GateBase):
    def test_parent_sku_from_the_llm_is_resolved_to_the_variant_the_customer_named(self):
        """Replay A: khách đã nói "38 đen" nhưng LLM gọi order.create với SKU cha → gate hỏi lại "chọn size và màu nào" mãi."""
        parent_order = ("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-RUN2", "qty": 1, "price_vnd": 1521000})
        self.turn(NEW_PHONE, "vậy cho tôi 38 xám đi", [], "Dạ ạ.")
        _t, tc, meta = self.turn(NEW_PHONE, "ok lấy 38 đen", [parent_order], "Dạ ạ.")
        ev = meta["order_gate"][-1]
        self.assertNotIn("item", ev["missing"])
        self.assertEqual(self.orch._gate_retry_args[self._sid()]["sku"], "SKU-SN-RUN2-38-DEN")           # lần nhắc gần nhất ("đen") thắng "xám"

    def test_a_missing_variant_is_asked_in_its_own_sentence(self):
        _t, tc, meta = self.turn(NEW_PHONE, "lấy giày RunLite 2 Pro", [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-RUN2", "qty": 1, "price_vnd": 1521000})], "Dạ ạ.")
        say = meta["order_gate"][-1]["say"]
        self.assertIn("mình chọn size và màu nào ạ?", say)
        self.assertNotIn("xin mình chọn", say)

    def test_readback_says_the_colour_with_diacritics(self):
        a = dict(recipient_name="Đại", address="<ADDR_1>", payment="COD")
        self.turn(NEW_PHONE, "lấy 38 đen, giao cho Đại, giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội, COD",
                  [("order.create", {"customer_phone": "CURRENT_CUSTOMER", "sku": "SKU-SN-RUN2-38-DEN", "qty": 1, "price_vnd": 1521000, **a})], "Dạ ạ.")
        txt, _tc, meta = self.turn(NEW_PHONE, "đúng rồi", [], "Dạ ạ.")
        self.assertEqual(meta["order_gate"][-1]["action"], "readback")
        self.assertIn("màu đen", txt)
        self.assertNotIn("màu den", txt)

    def _sid(self):
        from src.channels.normalizer import InputChannel
        t = self.c["normalizer"].normalize("alo", InputChannel.HOTLINE, NEW_PHONE)
        return f"SESS-{self.c['resolver'].resolve(t).customer_id}-2026-10-15"


class UiDateTest(unittest.TestCase):
    def test_call_date_is_validated_and_normalised(self):
        """Ảnh 3–4, 9: UI nhận "2026-15-10" và "2026-11-1" mà không báo lỗi."""
        from src.common.dates import normalize_call_date as n
        self.assertEqual(n("2026-11-1"), "2026-11-01")
        self.assertEqual(n(" 2026-10-15 "), "2026-10-15")
        self.assertIsNone(n("2026-15-10"))
        self.assertIsNone(n("15/10/2026"))
        self.assertIsNone(n(""))


class AddressTrailingNameTest(unittest.TestCase):
    def test_person_name_after_the_last_comma_is_not_part_of_the_address(self):
        from src.privacy.pii_vault import detect_addresses
        for text, want in (("đúng sdt, 45/1 đường 10 khu phố 3 phường linh đông hồ chí minh, Đại", "45/1 đường 10 khu phố 3 phường linh đông hồ chí minh"),
                           ("giao về số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội", "số 12 đường Nguyễn Trãi, quận Thanh Xuân, Hà Nội"),
                           ("giao về số 9 đường Quang Trung, TP. Thanh Hóa, Thanh Hóa", "số 9 đường Quang Trung, TP. Thanh Hóa, Thanh Hóa"),
                           ("giao về 3 phố Huế, quận Hai Bà Trưng, Hà Nội, Hùng nhé", "3 phố Huế, quận Hai Bà Trưng, Hà Nội")):
            self.assertEqual([text[a:b] for a, b in detect_addresses(text)], [want], text)


if __name__ == "__main__":
    unittest.main()
