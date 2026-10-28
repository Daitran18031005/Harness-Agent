"""Luật sinh/kiểm lời thoại P1–P4 (src/dataset/rules.py): mỗi luật có ca vi phạm (phải bắt) và ca hợp lệ (không báo nhầm)."""
import unittest

from src.dataset import rules as R


def C(idx, text, states=None, **kw):
    return {"idx": idx, "speaker": "C", "text_written": text, "states": states or [], **kw}


def A(idx, text, template=None):
    return {"idx": idx, "speaker": "A", "text_written": text, "text_template": template or text}


def call(facts=None, agent_vars=None, channel="hotline", style="normal", plot="khách hỏi máy lọc không khí", name="call_1"):
    return {"name": name, "channel": channel, "style": style, "customer_plot": plot, "goal": "hỏi giá",
            "customer_facts": facts or [], "agent_vars": agent_vars or {}}


class OutsidePlotTest(unittest.TestCase):                                  # P1
    def test_competitor_not_in_plot_is_caught(self):
        errs = R.check_outside_plot([C(1, "Bên khác báo rẻ hơn đó em.")], call())
        self.assertTrue(any("đối thủ" in e for e in errs))

    def test_competitor_allowed_when_fact_or_plot_has_it(self):
        facts = [{"key": "competitor_price_vnd", "value": 4500000, "hint": "bên khác 4,5 triệu"}]
        self.assertEqual(R.check_outside_plot([C(1, "Bên khác báo 4,5 triệu thôi.")], call(facts)), [])
        self.assertEqual(R.check_outside_plot([C(1, "Chỗ khác rẻ hơn.")], call(plot="khách so giá với chỗ khác")), [])

    def test_child_cue_uses_diacritics_so_con_nho_is_not_con_nhỏ(self):
        self.assertEqual(R.check_outside_plot([C(1, "Anh hỏi hôm qua, bên em còn nhớ anh không?")], call()), [])
        errs = R.check_outside_plot([C(1, "Nhà chị có con nhỏ nữa.")], call())
        self.assertTrue(any("trẻ nhỏ" in e for e in errs))
        facts = [{"key": "has_children", "value": True, "hint": "nhà có bé"}]
        self.assertEqual(R.check_outside_plot([C(1, "Nhà chị có con nhỏ nữa.")], call(facts)), [])

    def test_area_budget_size_color_phone(self):
        for text, key in (("Phòng 40m² nhà chị.", "diện tích"), ("Ngân sách tầm 6 triệu thôi.", "ngân sách"), ("Lấy size 42 nhé.", "size"),
                          ("Chị thích màu hồng.", "màu"), ("Số chị 0900011122 nhé.", "SĐT")):
            errs = R.check_outside_plot([C(1, text)], call())
            self.assertTrue(any(key in e for e in errs), text)

    def test_phone_allowed_when_provided_or_scenario(self):
        facts = [{"key": "phone_provided", "value": "0900011122", "hint": ""}]
        self.assertEqual(R.check_outside_plot([C(1, "Số chị 0900011122 nhé.")], call(facts)), [])
        self.assertEqual(R.check_outside_plot([C(1, "Số chị 0900011122 nhé.")], call(), scenario_phone="0900011122"), [])

    def test_money_must_come_from_facts_or_agent(self):
        facts = [{"key": "budget_vnd", "value": 5000000, "hint": "5 triệu"}]
        self.assertEqual(R.check_outside_plot([C(1, "Tầm 5 triệu thôi.")], call(facts)), [])
        errs = R.check_outside_plot([C(1, "Cái này 2 triệu thôi mà.")], call(facts))
        self.assertTrue(any("số tiền" in e for e in errs))
        turns = [A(1, "Dạ giá 4.890.000đ ạ."), C(2, "Bốn triệu tám à? Hơi đắt, 4,9 triệu.")]
        self.assertEqual(R.check_outside_plot(turns, call()), [])         # số khách nhắc lại số agent vừa nói (làm tròn ≤ 12%)


class AnswerAllQuestionsTest(unittest.TestCase):                            # P2
    VARS = {"price": {"text": "4.890.000đ", "desc": "giá cuối"}, "stock": {"text": "hiện còn hàng", "desc": "tình trạng tồn kho (còn hàng/hết hàng)"}}

    def test_asked_topics_needs_a_question(self):
        self.assertEqual(R.asked_topics("Máy này giá bao nhiêu, còn hàng không?"), {"price", "stock"})
        self.assertEqual(R.asked_topics("Giá đó hơi chát, thôi lấy đi."), set())
        self.assertEqual(R.asked_topics("Giá vẫn vậy đúng không?"), {"price"})
        self.assertEqual(R.asked_topics("Có COD không em?"), {"payment"})

    def test_missing_stock_answer_is_caught(self):
        turns = [C(1, "Giá bao nhiêu, còn hàng không em?"), A(2, "Dạ giá 4.890.000đ ạ.", "Dạ giá {price} ạ.")]
        errs = R.check_answers_all_questions(turns, call(agent_vars=self.VARS))
        self.assertEqual(len(errs), 1)
        self.assertIn("stock", errs[0])

    def test_all_answered_via_placeholders(self):
        turns = [C(1, "Giá bao nhiêu, còn hàng không em?"), A(2, "Dạ giá 4.890.000đ, hiện còn hàng ạ.", "Dạ giá {price}, {stock} ạ.")]
        self.assertEqual(R.check_answers_all_questions(turns, call(agent_vars=self.VARS)), [])

    def test_stock_question_without_stock_var_flags_the_frame(self):
        turns = [C(1, "Còn hàng không em?"), A(2, "Dạ còn hàng ạ.")]
        errs = R.check_answers_all_questions(turns, call(agent_vars={"price": self.VARS["price"]}))
        self.assertTrue(any("KHÔNG có ô trống tồn kho" in e for e in errs))

    def test_deferral_counts_as_an_answer(self):
        turns = [C(1, "Máy này có chữa được viêm vú không, giá bao nhiêu?"), A(2, "Dạ phần này em xin phép chuyển nhân viên tư vấn hỗ trợ mình ạ.")]
        self.assertEqual(R.check_answers_all_questions(turns, call(agent_vars=self.VARS)), [])

    def test_confirmation_about_gift_is_not_a_price_question(self):
        turns = [C(1, "Giá đã gồm quà tặng như em nói chứ?"), A(2, "Dạ đúng rồi ạ, có quà tặng.", "Dạ đúng rồi ạ, có quà {gift}.")]
        self.assertEqual(R.check_answers_all_questions(turns, call(agent_vars=self.VARS)), [])


class StyleTest(unittest.TestCase):                                         # P3
    def test_profile_assignment_is_deterministic_and_persona_based(self):
        self.assertEqual(R.style_profile("khach_so_gia", "call_1"), "hesitant")
        self.assertEqual(R.style_profile("khach_da_kenh_fb_hotline", "call_2"), "interrupting")
        self.assertEqual(R.style_profile("bat_ky", "call_3"), "impatient")
        self.assertEqual(R.style_profile("khach_het_kien_nhan", "call_1"), "impatient")
        self.assertEqual(R.style_profile("persona_la", "call_1"), R.style_profile("persona_la", "call_1"))

    def test_uniformly_long_polite_turns_fail(self):
        long_turns = [C(i, "Dạ chị muốn hỏi về chiếc máy lọc không khí cho phòng ngủ nhà chị ạ, em tư vấn giúp chị nhé.") for i in (1, 3, 5)]
        errs = R.check_style(long_turns, call(), "khach_so_gia")
        self.assertTrue(any("≤ 6 từ" in e for e in errs))
        self.assertTrue(any("lịch sự" in e for e in errs))
        self.assertTrue(any("ngập ngừng" in e or "phong cách" in e for e in errs))

    def test_hesitant_curt_mix_passes(self):
        turns = [C(1, "Ờ, máy lọc không khí á... giá sao em?"), C(3, "À. Để chị xem."), C(5, "Ừm, chị lấy cái đó, giao ngày mai được không?")]
        self.assertEqual(R.check_style(turns, call(), "khach_so_gia"), [])

    def test_repeat_profile_requires_ask_to_repeat_and_agent_repeats_info(self):
        persona = next(p for p in ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8") if R.style_profile(p, "call_1") == "repeat")
        ok = [C(1, "Máy lọc giá sao?"), A(2, "Dạ giá {price} ạ.", "Dạ giá {price} ạ."), C(3, "Hả? Em nói lại giúp chị."), A(4, "Dạ giá {price} ạ.", "Dạ giá {price} ạ."), C(5, "Ừ lấy.")]
        self.assertEqual(R.check_style(ok, call(), persona), [])
        bad = ok[:3] + [A(4, "Dạ em có quà tặng ạ.", "Dạ em có quà {gift} ạ."), C(5, "Ừ lấy.")]
        self.assertTrue(any("nhắc lại" in e for e in R.check_style(bad, call(), persona)))


class ChannelStyleTest(unittest.TestCase):                                  # P4
    def test_teencode_only_on_chat_channels(self):
        self.assertTrue(R.check_channel_style([C(1, "ok")], call(channel="hotline", style="teencode")))
        self.assertEqual(R.check_channel_style([C(1, "Giá sao em?")], call(channel="zalo_oa", style="teencode")), [])

    def test_hotline_text_has_no_chat_abbreviations(self):
        errs = R.check_channel_style([C(1, "Cái này ko có hả em")], call(channel="hotline"))
        self.assertTrue(any("viết tắt" in e for e in errs))
        self.assertEqual(R.check_channel_style([C(1, "Cái này không có hả em")], call(channel="hotline")), [])
        self.assertEqual(R.check_channel_style([C(1, "ko có hả em")], call(channel="chat_fanpage")), [])

    def test_hotline_must_not_have_text_asr(self):
        errs = R.check_channel_style([C(1, "Giá sao em", text_asr="gia sao em")], call(channel="hotline"))
        self.assertTrue(any("text_asr" in e for e in errs))


class SpecsStockVarTest(unittest.TestCase):
    def test_single_sku_call_gets_a_real_stock_var(self):
        from src.dataset.specs import _with_stock_var, var
        out = _with_stock_var({"product": var("AirPure Y", "tên", ("sku", "SKU-AP-Y"))}, "2026-10-15")
        self.assertIn("stock", out)
        self.assertEqual(out["stock"]["text"], "hiện còn hàng")
        oos = _with_stock_var({"product": var("Xiaomi 4 Pro", "tên", ("sku", "SKU-XM-4P"))}, "2026-10-15")
        self.assertIn("hết hàng", oos["stock"]["text"])
        self.assertIn("19/10", oos["stock"]["text"])                       # ngày có lại hàng lấy từ mock_tools

    def test_two_skus_or_no_date_leave_vars_untouched(self):
        from src.dataset.specs import _with_stock_var, var
        two = {"a": var("x", "d", ("sku", "SKU-AP-Y")), "b": var("y", "d", ("sku", "SKU-AP-X"))}
        self.assertNotIn("stock", _with_stock_var(two, "2026-10-15"))
        self.assertNotIn("stock", _with_stock_var({"a": var("x", "d", ("sku", "SKU-AP-Y"))}, ""))


class OrderFlowTest(unittest.TestCase):                                     # P5
    CALL = {"name": "call_2", "channel": "hotline", "style": "normal", "customer_plot": "", "goal": "", "customer_facts": [],
            "agent_vars": {}, "expected": {"success_if": {"tool_called": "order.create"}}}
    RB = "Dạ em đọc lại đơn: {product}, giá {price}, tổng {readback_total}; giao cho {recipient_name}, SĐT {caller_phone}, địa chỉ {address}; {payment_label}. Mình xác nhận đặt đơn chứ ạ?"
    RBW = "Dạ em đọc lại đơn: máy lọc, giá 4.890.000đ, tổng 4.890.000đ; giao cho Thu, SĐT 0900010001, địa chỉ số 12 Nguyễn Trãi; thanh toán khi nhận hàng (COD). Mình xác nhận đặt đơn chứ ạ?"

    def good(self):
        return [A(1, "Dạ mình cho em xin tên người nhận và địa chỉ giao hàng ạ?"),
                C(2, "Giao cho Thu, số 12 Nguyễn Trãi nhé.", ["recipient_name", "address"]),
                A(3, "Dạ em xác nhận số điện thoại nhận hàng là số mình đang gọi, và mình thanh toán COD hay chuyển khoản ạ?"),
                C(4, "Số này, COD.", ["payment"]),
                A(5, self.RBW, self.RB),
                C(6, "ok em"),
                A(7, "Dạ em đã lên đơn, mã đơn OD600001, giao trong 2 ngày ạ.", "Dạ em đã lên đơn, mã đơn {order_id}, giao trong {delivery_days} ngày ạ.")]

    def test_good_flow_passes(self):
        self.assertEqual(R.check_order_flow(self.good(), self.CALL), [])

    def test_non_order_calls_are_ignored(self):
        self.assertEqual(R.check_order_flow(self.good()[:2], {**self.CALL, "expected": {"success_if": {"tool_called": "order.status"}}}), [])

    def test_missing_readback(self):
        turns = [t for i, t in enumerate(self.good()) if i not in (4, 5)]
        errs = R.check_order_flow(turns, self.CALL)
        self.assertTrue(any("ĐỌC LẠI ĐƠN" in e for e in errs))

    def test_order_id_without_explicit_consent(self):
        turns = self.good()
        turns[5] = C(6, "Ừm để chị xem đã.")
        errs = R.check_order_flow(turns, self.CALL)
        self.assertTrue(any("đồng ý RÕ RÀNG" in e for e in errs))

    def test_created_claim_before_consent(self):
        turns = self.good()
        turns[0] = A(1, "Dạ em đã lên đơn rồi, mình cho em xin tên và địa chỉ ạ?")
        self.assertTrue(any("trước khi khách đồng ý" in e for e in R.check_order_flow(turns, self.CALL)))

    def test_agent_must_close_right_after_consent(self):
        turns = self.good()
        turns.insert(6, A(7, "Dạ em kiểm tra tồn kho một chút ạ."))
        turns.insert(7, C(8, "ừ"))
        errs = R.check_order_flow(turns, self.CALL)
        self.assertTrue(errs)

    def test_checklist_info_must_be_asked_or_stated_before_readback(self):
        turns = [A(1, "Dạ em đọc lại đơn nhé.", self.RB.replace("Mình xác nhận", "Mình xác nhận")), C(2, "ok"), A(3, "Dạ mã đơn {order_id}", "Dạ mã đơn {order_id}")]
        turns[0] = A(1, self.RBW, self.RB)
        errs = R.check_order_flow(turns, self.CALL)
        self.assertTrue(any("địa chỉ" in e for e in errs))
        self.assertTrue(any("tên người nhận" in e for e in errs))

    def test_saved_address_is_confirmed_not_restated(self):
        call = {**self.CALL, "saved_address": True}
        turns = [A(1, "Dạ em xin xác nhận giao về địa chỉ số 12 Nguyễn Trãi như lần trước, số điện thoại này, thanh toán COD, người nhận Thu, đúng không ạ?"),
                 C(2, "đúng rồi em"), A(3, self.RBW, self.RB), C(4, "ok"), A(5, "Dạ mã đơn {order_id} ạ", "Dạ mã đơn {order_id} ạ")]
        self.assertEqual(R.check_order_flow(turns, call), [])
        turns[1] = C(2, "đúng, số 12 Nguyễn Trãi", ["address"])
        self.assertTrue(any("KHÔNG đọc lại địa chỉ" in e for e in R.check_order_flow(turns, call)))


class OrderFlowFramesTest(unittest.TestCase):
    def test_every_order_call_in_sample10_has_the_gate_vars_and_facts(self):
        from src.dataset.specs import build_sample10
        n = 0
        for fr in build_sample10():
            for c in fr["calls"]:
                if R.is_order_call(c):
                    n += 1
                    self.assertTrue(c["order_flow"])
                    for k in ("readback_total", "payment_label", "recipient_name", "caller_phone", "address", "order_id"):
                        self.assertIn(k, c["agent_vars"], (fr["scenario"]["scenario_id"], k))
                    self.assertIn("recipient_name", {f["key"] for f in c["customer_facts"]})
        self.assertGreaterEqual(n, 7)

    def test_prompt_contains_order_flow_steps_only_for_order_calls(self):
        import json
        from src.dataset.specs import build_sample10
        from src.dataset.writer import build_prompt
        frames = build_sample10()
        a01 = frames[0]
        spec1 = json.loads(build_prompt(a01, a01["calls"][0], "", "")[1]["content"])
        spec2 = json.loads(build_prompt(a01, a01["calls"][1], "", "x")[1]["content"])
        self.assertNotIn("quy_trinh_dat_don", spec1)
        self.assertIn("quy_trinh_dat_don", spec2)


class PromptTest(unittest.TestCase):
    def test_prompt_carries_new_rules_and_style_profile(self):
        import json
        from src.dataset.specs import build_sample10
        from src.dataset.writer import RULES, build_prompt
        fr = build_sample10()[0]
        msgs = build_prompt(fr, fr["calls"][0], "style", "")
        spec = json.loads(msgs[1]["content"])
        self.assertIn("phong_cach_hoi_thoai", spec)
        joined = " ".join(RULES)
        self.assertIn("CHỈ nói thông tin có trong", joined)
        self.assertIn("TRẢ LỜI ĐỦ", joined)
        self.assertIn("ĐA DẠNG GIỌNG KHÁCH", joined)


if __name__ == "__main__":
    unittest.main()
