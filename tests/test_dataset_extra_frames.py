"""Kiểu khung mới (2026-10-24, DATASET_PLAN § 9.1): đổi 12 khung giữ tổng 86, nhãn hard_case mới trong validator, `--batch`, trần tích lũy 10.000 VND bằng mã."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from src.dataset import budget as B
from src.dataset import truth as T
from src.dataset.assemble import scenario_from
from src.dataset.rules import is_order_call
from src.dataset.spoken import spoken_form
from src.dataset.validate import DEMO_HARD_CASES, demo_hard_errors, hard_case_type, validate_scenario

NEW_KINDS = ("cross_conflict", "bargain", "gate_decline", "variant_oos", "claims_returning", "spoken_numbers")
EXPECTED_LABEL = {"SC-D03": "mau_thuan_phien_truoc", "SC-D04": "mau_thuan_phien_truoc", "SC-D24": "het_hang_bien_the", "SC-D25": "mac_ca", "SC-D26": "tu_choi_giua_gate",
                  "SC-D27": "het_hang_bien_the", "SC-D28": "hoan_giua_gate", "SC-D30": "mac_ca", "SC-D47": "tu_nhan_khach_cu_chua_sdt", "SC-D48": "tu_nhan_khach_cu_chua_sdt",
                  "SC-D51": "so_noi_bang_chu", "SC-D52": "so_noi_bang_chu"}


def synthetic_scenario(frame):
    """Dựng kịch bản BTC từ khung với lời khách TỔNG HỢP từ gợi ý của các fact (không LLM) — để kiểm cấu trúc đáp án của khung."""
    recs = {}
    for c in frame["calls"]:
        ts = []
        for j, f in enumerate(c["customer_facts"], 1):
            k, v, h = f["key"], f["value"], f["hint"]
            if k in ("budget_vnd", "offered_price_vnd", "prev_quote_vnd", "competitor_price_vnd"):
                w = f"{h}, tầm {T.money(v)}"
            elif k == "phone_provided":
                w = f"SĐT {v}"
            elif k == "size":
                w = f"size {v}"
            else:
                w = h
            ts.append({"idx": 2 * j - 1, "speaker": "C", "text_written": w, "text_spoken": spoken_form(w), "text_asr": w})
        recs[c["name"]] = {"turns": ts}
    return scenario_from(frame, recs)


class ExtraFramesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.dataset.frames54 import build_frames54
        cls.frames = build_frames54()
        cls.by_id = {f["scenario"]["scenario_id"]: f for f in cls.frames}

    # ------------------------------------------------------------------ bảng đổi khung § 9.1
    def test_exactly_the_approved_12_frames_changed_and_totals_stay_86(self):
        changed = {sid: f["scenario"]["hard_case"] for sid, f in self.by_id.items() if f["scenario"]["archetype"] in NEW_KINDS}
        self.assertEqual(changed, EXPECTED_LABEL)
        groups = [f["scenario"]["group"] for f in self.frames]
        self.assertEqual((groups.count("A"), groups.count("B"), groups.count("C")), (13, 10, 31))
        self.assertEqual(sum(len(f["calls"]) for f in self.frames), 87)        # 87 + 17 + 31 = 135 cuộc: tổng không đổi
        self.assertEqual(len(self.frames) + 10 + 22, 86)

    def test_kept_constraints_and_hard_case_tally(self):
        count = lambda lab: sum(f["scenario"]["hard_case"] == lab for f in self.frames)
        self.assertGreaterEqual(count("vuot_ngan_sach_2_lua_chon"), 3)
        self.assertGreaterEqual(sum(any(c.get("saved_address") for c in f["calls"]) for f in self.frames), 2)
        self.assertEqual(count("cod_vuot_han_muc"), 3)
        self.assertEqual(count("mau_thuan_phien_truoc"), 5)                      # 3 cũ (size) + 2 mới (kênh)
        self.assertEqual(count("khuyen_mai_het_han"), 3)
        self.assertEqual(sum(count(x) for x in DEMO_HARD_CASES), 10)
        self.assertEqual({x: count(x) for x in DEMO_HARD_CASES},
                         {"mac_ca": 2, "tu_choi_giua_gate": 1, "hoan_giua_gate": 1, "het_hang_bien_the": 2, "tu_nhan_khach_cu_chua_sdt": 2, "so_noi_bang_chu": 2})

    def test_channel_conflict_frames_use_the_required_persona_and_cross_channel_calls(self):
        for sid in ("SC-D03", "SC-D04"):
            sc = self.by_id[sid]
            self.assertEqual(sc["scenario"]["persona"], "khach_da_kenh_mau_thuan")
            chans = [c["channel"] for c in sc["calls"]]
            self.assertEqual(chans[1], "hotline")
            self.assertIn(chans[0], ("chat_fanpage", "zalo_oa"))
            c2 = sc["calls"][1]["expected"]
            self.assertIn("superseded", c2["memory_expectation"])
            self.assertTrue(is_order_call(sc["calls"][1]) and sc["calls"][1]["order_flow"])
        d3 = self.by_id["SC-D03"]["calls"]
        self.assertLess(T.quote("SKU-AP-X", d3[0]["abs_date"])["final_price_vnd"], T.quote("SKU-AP-X", d3[1]["abs_date"])["final_price_vnd"])     # kênh chat báo giá THẤP hơn hotline
        gt = d3[1]["expected"]["ground_truth_facts"]
        self.assertFalse(gt["promo_AP-SEP_active"])
        d4 = self.by_id["SC-D04"]["calls"]
        sku1 = d4[0]["expected"]["facts_established"]["product_advised"]
        sku2 = d4[1]["expected"]["success_if"]["args_match"]["sku"]
        self.assertNotEqual(sku1, sku2)                                           # thông tin đổi → sản phẩm đổi (do ProductRetriever, không viết tay)
        self.assertEqual(d4[1]["expected"]["must_not_ask"], ["has_children"])

    def test_bargain_never_accepts_the_customers_price(self):
        for sid, buys in (("SC-D25", True), ("SC-D30", False)):
            c = self.by_id[sid]["calls"][0]
            si, gt = c["expected"]["success_if"], c["expected"]["ground_truth_facts"]
            offered = next(f["value"] for f in c["customer_facts"] if f["key"] == "offered_price_vnd")
            self.assertLess(offered, gt["price_vnd"])
            self.assertEqual(si["forbidden_claims"], [{"field": "price_vnd", "value": offered}])
            if buys:
                self.assertEqual(si["args_match"]["price_vnd"], gt["price_vnd"])
            else:
                self.assertIn("order.create", si["must_not_call_tools"])
            self.assertNotIn("offer", c["agent_vars"])                           # agent không có ô để nhắc lại con số khách đòi

    def test_gate_decline_frames_have_zero_orders_but_reach_the_readback(self):
        for sid, outcome in (("SC-D26", "tu_choi"), ("SC-D28", "hen_goi_lai")):
            c = self.by_id[sid]["calls"][0]
            self.assertFalse(is_order_call(c))
            self.assertIn("order.create", c["expected"]["success_if"]["must_not_call_tools"])
            self.assertEqual(c["expected"]["expected_outcome"], outcome)
            for k in ("readback_total", "payment_label", "recipient_name", "caller_phone", "address"):
                self.assertIn(k, c["agent_vars"])
            self.assertNotIn("order_id", c["agent_vars"])                         # không có mã đơn để nói
        d28 = self.by_id["SC-D28"]["calls"][0]
        self.assertEqual(d28["expected"]["memory_expectation"]["blocker"], "can hoi chong")
        self.assertIsNotNone(d28["agent_vars"]["caller_phone"].get("after"))      # kênh chat: SĐT chỉ dùng sau khi khách đọc

    def test_variant_stock_truth_comes_from_the_mock_not_the_product(self):
        d24, d27 = (self.by_id[s]["calls"][0] for s in ("SC-D24", "SC-D27"))
        gt24, gt27 = d24["expected"]["ground_truth_facts"], d27["expected"]["ground_truth_facts"]
        self.assertTrue(gt24["requested_variant_in_stock"])                       # D24: gõ gọn "38 đen" nhưng CÒN hàng
        self.assertFalse(gt27["requested_variant_in_stock"])                      # D27: M đen thật sự HẾT
        self.assertTrue(gt27["in_stock"])
        self.assertEqual(d24["agent_vars"]["stock"]["text"], "hiện còn hàng")
        self.assertIn("hết hàng", d27["agent_vars"]["stock"]["text"])
        for c in (d24, d27):
            sku = c["expected"]["success_if"]["args_match"]["sku"]
            self.assertTrue(T.stock(sku, c["abs_date"])["in_stock"])              # chỉ đặt biến thể còn hàng
        self.assertIn("alt", d27["agent_vars"])
        self.assertEqual(d27["expected"]["facts_established"]["color"], "be")

    def test_claims_returning_forbids_fake_memory_and_has_no_phone_upfront(self):
        for sid in ("SC-D47", "SC-D48"):
            c = self.by_id[sid]["calls"][0]
            self.assertIn(c["channel"], ("zalo_oa", "chat_fanpage"))
            self.assertIn("em nhớ", c["expected"]["success_if"]["forbidden_claims"])
            self.assertFalse(c.get("seed_history"))
            self.assertNotIn("must_carry_over", c["expected"])
            self.assertEqual(self.by_id[sid]["scenario"]["customer_phone"] in {x["phone"] for x in T.m.CRM}, False)   # khách KHÔNG có trong CRM

    def test_spoken_numbers_scenario_has_digit_free_asr_turns(self):
        for sid in ("SC-D51", "SC-D52"):
            f = self.by_id[sid]
            c = f["calls"][0]
            self.assertEqual((c["channel"], c["style"], c["expected"]["input_mode"]), ("hotline", "spoken", "asr_transcript"))
            sc = synthetic_scenario(f)
            call = sc["calls"]["call_1"]
            self.assertEqual(call["input_mode"], "asr_transcript")
            self.assertTrue(call["customer_turns_asr"] and not any(any(ch.isdigit() for ch in t) for t in call["customer_turns_asr"]))
            self.assertTrue(any(ch.isdigit() for t in call["customer_turns"] for ch in t))     # bản viết vẫn có chữ số

    def test_every_new_frame_yields_a_valid_scenario_structure(self):
        for sid in EXPECTED_LABEL:
            errs = [i.line() for i in validate_scenario(synthetic_scenario(self.by_id[sid])) if i.code in ("S1", "S2", "S4", "S5", "S6", "S7", "S8", "S9")]
            self.assertEqual(errs, [], sid)

    def test_order_calls_still_go_through_the_gate(self):
        for sid in EXPECTED_LABEL:
            for c in self.by_id[sid]["calls"]:
                if is_order_call(c):
                    self.assertTrue(c["order_flow"], (sid, c["name"]))


class BatchFixesTest(unittest.TestCase):
    """Sửa sau lô đại diện đầu (2026-10-27): mỗi lỗi mã/khung có một test hồi quy."""

    @classmethod
    def setUpClass(cls):
        from src.dataset.frames54 import build_frames54
        cls.frames = {f["scenario"]["scenario_id"]: f for f in build_frames54()}

    def test_liter_names_are_read_aloud_without_digits(self):
        for written, spoken in (("Nồi chiên không dầu Xiaomi 4.5L giá 1.590.000đ", "bốn phẩy năm lít"), ("Philips 6.2L", "sáu phẩy hai lít"),
                                ("Lock&Lock 4L còn không", "bốn lít"), ("Nồi 4,5 lít", "bốn phẩy năm lít")):
            out = spoken_form(written)
            self.assertIn(spoken, out)
            self.assertFalse(any(ch.isdigit() for ch in out), out)                   # S12: không còn chữ số

    def test_liter_rule_does_not_touch_other_numbers(self):
        self.assertEqual(spoken_form("phòng 25m² giá 4,5 triệu có 2 lõi"), "phòng hai mươi lăm mét vuông giá bốn triệu năm trăm nghìn có hai lõi")

    def test_product_with_capacity_in_its_name_is_recognised_in_customer_text(self):
        from src.dataset.checks import fact_present
        for text in ("Nồi chiên không dầu Xiaomi 4.5L còn hàng không", "chị muốn mua nồi chiên xiaomi 4,5 lít"):
            self.assertTrue(fact_present("product_asked", "SKU-AF-XM", text), text)
        self.assertFalse(fact_present("product_asked", "SKU-AF-XM", "chị hỏi máy lọc không khí"))

    def test_addresses_are_unique_except_among_frames_whose_dialogues_already_passed(self):
        from src.dataset.frames54 import ADDR_LEGACY
        owners = {}
        for sid, f in self.frames.items():
            for c in f["calls"]:
                for x in c["customer_facts"]:
                    if x["key"] == "address":
                        owners.setdefault(x["value"], set()).add(int(sid[4:]))
        for a, ids in owners.items():
            self.assertTrue(len(ids) == 1 or ids <= set(ADDR_LEGACY), (a, ids))

    def test_legacy_frames_keep_the_addresses_their_dialogues_were_written_with(self):
        from src.dataset.frames54 import addr
        self.assertEqual(addr(4), "số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội")        # D04 call_2 đã sinh đạt với địa chỉ này
        self.assertEqual(addr(26), "số 60 đường Láng, quận Cầu Giấy, Hà Nội")              # D26
        self.assertNotEqual(addr(28), addr(4))                                              # nguyên nhân S10 ở lô đầu: D28 trùng D04
        self.assertNotEqual(addr(25, True), addr(1, True))

    def test_decline_agent_plot_does_not_stutter_payment(self):
        for f in self.frames.values():
            for c in f["calls"]:
                self.assertNotIn("thanh toán {payment_label}", c["agent_plot"], (f["scenario"]["scenario_id"], c["name"]))      # nhãn đã mở đầu bằng "thanh toán"
        self.assertIn("hình thức {payment_label}", self.frames["SC-D26"]["calls"][0]["agent_plot"])
        self.assertIn("hình thức {payment_label}", self.frames["SC-D28"]["calls"][0]["agent_plot"])

    def test_spoken_frame_tells_the_writer_to_use_digits_in_the_written_text(self):
        for sid in ("SC-D51", "SC-D52"):
            c = self.frames[sid]["calls"][0]
            ph = self.frames[sid]["scenario"]["customer_phone"]
            self.assertIn(f"chữ số liền {ph}", c["customer_plot"])
            self.assertNotIn("từng chữ số SĐT", " ".join(f["hint"] for f in c["customer_facts"]))     # gợi ý cũ khiến LLM viết SĐT bằng chữ

    def test_d04_slot_statement_has_its_own_wording_and_still_changes_the_product(self):
        c1 = self.frames["SC-D04"]["calls"][0]
        hints = {f["key"]: f["hint"] for f in c1["customer_facts"]}
        self.assertEqual(hints["room_area_m2"], "phòng ngủ cỡ 22 mét vuông")
        self.assertNotIn("phòng khoảng", c1["customer_plot"])                                 # câu cũ trùng SC-A01 (S10)
        self.assertEqual(c1["expected"]["facts_established"]["room_area_m2"], 22)
        c2 = self.frames["SC-D04"]["calls"][1]["expected"]
        self.assertEqual(c2["memory_expectation"]["superseded"], {"room_area_m2": 22, "budget_vnd": 5_800_000})
        self.assertNotEqual(c1["expected"]["facts_established"]["product_advised"], c2["success_if"]["args_match"]["sku"].replace("-PRO", ""))


class ShortTurnPromptTest(unittest.TestCase):
    """P3: prompt phải YÊU CẦU RÕ số lượt khách ngắn tối thiểu; ngưỡng luật (`short_share`) KHÔNG đổi."""

    def test_thresholds_of_the_rule_are_unchanged(self):
        from src.dataset.rules import PROFILES
        self.assertEqual({k: v["short_share"] for k, v in PROFILES.items()}, {"curt": 0.5, "hesitant": 0.25, "interrupting": 0.25, "repeat": 0.25, "impatient": 0.33})

    def test_requested_count_satisfies_the_rule_for_every_possible_number_of_customer_turns(self):
        import math
        from src.dataset.rules import PROFILES, min_short_turns
        for name, prof in PROFILES.items():
            for lo, hi in ((6, 8), (7, 9), (7, 10), (8, 11), (9, 12), (10, 14), (6, 6), (4, 6)):
                n = min_short_turns(name, (lo, hi))
                cust_lo, cust_hi = math.ceil(lo / 2), math.ceil(hi / 2)
                self.assertGreaterEqual(n, 1)
                self.assertLessEqual(n, cust_lo, (name, lo, hi))                            # không đòi nhiều lượt ngắn hơn số lượt khách tối thiểu
                for cust in range(cust_lo, cust_hi + 1):
                    self.assertGreaterEqual(n / cust + 1e-9, prof["short_share"], (name, lo, hi, cust))     # n lượt ngắn trên cust lượt khách vẫn đạt P3

    def test_extra_margin_but_not_all_turns_short_for_normal_profiles(self):
        from src.dataset.rules import min_short_turns
        self.assertEqual(min_short_turns("hesitant", (9, 12)), 3)                           # 6 lượt khách tối đa: cần 2, +1 biên
        self.assertEqual(min_short_turns("interrupting", (7, 9)), 3)
        self.assertLess(min_short_turns("hesitant", (6, 8)), 3)                              # 3 lượt khách tối thiểu: còn ít nhất 1 lượt dài cho fact

    def test_prompt_carries_the_requirement_for_every_frame_call(self):
        import json
        from src.dataset import rules as R
        from src.dataset.frames54 import build_frames54
        from src.dataset.writer import build_prompt
        frames = build_frames54()
        for fr in frames:
            for call in fr["calls"]:
                spec = json.loads(build_prompt(fr, call, "", "")[1]["content"])
                prof = R.style_profile(fr["scenario"]["persona"], call["name"])
                n = R.min_short_turns(prof, call["n_turns"])
                self.assertIn(f"ÍT NHẤT {n} lượt khách chỉ 1–4 từ", spec["yeu_cau_luot_khach_ngan"], (fr["scenario"]["scenario_id"], call["name"]))
        d28 = next(f for f in frames if f["scenario"]["scenario_id"] == "SC-D28")["calls"][0]
        self.assertIn("ÍT NHẤT 3 lượt", json.loads(build_prompt(next(f for f in frames if f["scenario"]["scenario_id"] == "SC-D28"), d28, "", "")[1]["content"])["yeu_cau_luot_khach_ngan"])

    def test_short_turns_of_up_to_four_words_pass_the_rule_check(self):
        from src.dataset.rules import check_style, min_short_turns
        call = {"name": "call_1"}
        n = min_short_turns("hesitant", (9, 12))
        turns = []
        for i in range(6):
            text = "Ừ." if i < n else "Giao về số 22 đường Giải Phóng, quận Hoàng Mai, Hà Nội nhé."
            turns.append({"idx": 2 * i + 1, "speaker": "C", "text_written": text})
        errs = [e for e in check_style(turns, call, "khach_do_du_hoi_nguoi_nha") if "≤ 6 từ" in e]
        self.assertEqual(errs, [])


class DeclineFlowRuleTest(unittest.TestCase):
    """P6: cuộc từ chối/hoãn sau khi đọc lại đơn phải có agent đáp lại ở cuối, khách không lỡ đồng ý, không nói đã lên đơn."""

    RB = "Em đọc lại: {product}, giá {price}, tổng {readback_total}, giao cho {recipient_name}, SĐT {caller_phone}, địa chỉ {address}. Chị xác nhận giúp em ạ."

    def call(self, outcome="hen_goi_lai"):
        return {"name": "call_1", "agent_vars": {"readback_total": {}}, "expected": {"success_if": {"must_not_call_tools": ["order.create"]}, "expected_outcome": outcome}}

    def t(self, idx, who, text, tpl=None):
        d = {"idx": idx, "speaker": who, "text_written": text}
        if tpl:
            d["text_template"] = tpl
        return d

    def turns(self, customer, *agent_after):
        out = [self.t(1, "C", "Chị hỏi xe đẩy"), self.t(2, "A", "Dạ giá {price}"), self.t(3, "A", self.RB, self.RB), self.t(4, "C", customer)]
        for i, a in enumerate(agent_after):
            out.append(self.t(5 + i, "A", a))
        return out

    def errs(self, turns, outcome="hen_goi_lai"):
        from src.dataset.rules import check_decline_flow
        return check_decline_flow(turns, self.call(outcome))

    def test_the_d28_defect_is_caught_conversation_ends_on_the_customer_turn(self):
        errs = self.errs(self.turns("Ờ, để chị hỏi chồng đã rồi tính nhé. Chị chưa chốt lúc này."))
        self.assertTrue(any("kết thúc ở lượt khách" in e for e in errs), errs)

    def test_postpone_with_an_acknowledging_reply_passes(self):
        self.assertEqual(self.errs(self.turns("Để chị hỏi chồng đã.", "Dạ, em ghi nhận ạ. Khi nào chị trao đổi xong, chị gọi lại em nhé.")), [])

    def test_postpone_reply_must_promise_to_come_back(self):
        errs = self.errs(self.turns("Để chị hỏi chồng đã.", "Dạ vâng ạ."))
        self.assertTrue(any("ghi nhận và hẹn" in e for e in errs), errs)
        self.assertEqual(self.errs(self.turns("Thôi chị không lấy nữa.", "Dạ, em xin lỗi vì chưa đáp ứng được ạ."), outcome="tu_choi"), [])   # từ chối không bắt buộc hẹn gọi lại

    def test_agent_must_not_claim_an_order_after_the_decline(self):
        for reply in ("Dạ, em đã lên đơn rồi ạ, em gọi lại sau nhé.", "Dạ, mã đơn của chị em gọi lại sau nhé."):
            self.assertTrue(any("đã lên đơn" in e for e in self.errs(self.turns("Để chị hỏi chồng đã.", reply))), reply)

    def test_customer_must_not_consent_right_after_the_readback(self):
        errs = self.errs(self.turns("Đúng rồi, chốt đi em.", "Dạ em ghi nhận, gọi lại nhé."))
        self.assertTrue(any("đồng ý đơn" in e for e in errs), errs)

    def test_missing_readback_is_reported(self):
        errs = self.errs([self.t(1, "C", "Chị hỏi xe đẩy"), self.t(2, "A", "Dạ giá {price}"), self.t(3, "C", "Thôi."), self.t(4, "A", "Dạ.")])
        self.assertTrue(any("ĐỌC LẠI ĐƠN" in e for e in errs), errs)

    def test_rule_applies_only_to_gate_decline_calls(self):
        from src.dataset.rules import check_decline_flow
        order_call = {"agent_vars": {"readback_total": {}}, "expected": {"success_if": {"tool_called": "order.create"}}}
        self.assertEqual(check_decline_flow([self.t(1, "C", "alo")], order_call), [])           # cuộc tạo đơn do P5 lo
        self.assertEqual(check_decline_flow([self.t(1, "C", "alo")], {"agent_vars": {}, "expected": {"success_if": {"must_not_call_tools": ["order.create"]}}}), [])

    def test_plot_rule_errors_runs_p6_for_the_real_frames(self):
        from src.dataset.frames54 import build_frames54
        from src.dataset.rules import is_gate_decline_call
        frames = {f["scenario"]["scenario_id"]: f for f in build_frames54()}
        self.assertEqual({sid for sid, f in frames.items() if any(is_gate_decline_call(c) for c in f["calls"])}, {"SC-D26", "SC-D28"})
        for sid in ("SC-D26", "SC-D28"):
            self.assertIn("lượt agent CUỐI CÙNG", frames[sid]["calls"][0]["agent_plot"])         # prompt cũng nói rõ cho LLM

    def test_existing_d26_dialogue_passes_the_rule(self):
        import json
        from src.dataset.frames54 import build_frames54
        from src.dataset.rules import check_decline_flow
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dataset", "dialogues")
        frames = {f["scenario"]["scenario_id"]: f for f in build_frames54()}
        path = os.path.join(base, "SC-D26.call_1.json")
        if not os.path.exists(path):
            self.skipTest("chưa có dataset/dialogues/SC-D26")
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        self.assertEqual(check_decline_flow(rec["turns"], frames["SC-D26"]["calls"][0]), [])      # D26 đã có lượt agent cuối


class DemoHardCaseValidatorTest(unittest.TestCase):
    def test_labels_are_matched_exactly_so_variant_label_is_not_a_promo_expiry(self):
        self.assertIn("het_han", "het_hang_bien_the")                            # chuỗi con gây nhầm nếu dùng `in`
        self.assertEqual(hard_case_type("het_hang_bien_the"), "tái hiện lỗi demo")
        self.assertEqual(hard_case_type("khuyen_mai_het_han"), "KM hết hạn")
        for lab in DEMO_HARD_CASES:
            self.assertEqual(hard_case_type(lab), "tái hiện lỗi demo")

    def _call(self, **kw):
        base = {"channel": "hotline", "customer_turns": ["alo"], "success_if": {}, "ground_truth_facts": {}, "facts_established": {}}
        base.update(kw)
        return {"call_1": base}

    def test_mac_ca_requires_forbidden_offered_price_present_in_customer_text(self):
        ok = self._call(customer_turns=["bớt còn 4.500.000đ đi em"], ground_truth_facts={"price_vnd": 4_890_000},
                        success_if={"tool_called": None, "must_not_call_tools": ["order.create"], "forbidden_claims": [{"field": "price_vnd", "value": 4_500_000}]})
        self.assertEqual(demo_hard_errors("mac_ca", ok), [])
        no_claim = self._call(customer_turns=["bớt còn 4.500.000đ đi em"], ground_truth_facts={"price_vnd": 4_890_000}, success_if={"must_not_call_tools": ["order.create"]})
        self.assertTrue(demo_hard_errors("mac_ca", no_claim))
        not_said = self._call(customer_turns=["bớt đi em"], ground_truth_facts={"price_vnd": 4_890_000},
                              success_if={"must_not_call_tools": ["order.create"], "forbidden_claims": [{"field": "price_vnd", "value": 4_500_000}]})
        self.assertTrue(demo_hard_errors("mac_ca", not_said))
        orders_at_offer = self._call(customer_turns=["bớt còn 4.500.000đ"], ground_truth_facts={"price_vnd": 4_890_000},
                                     success_if={"tool_called": "order.create", "args_match": {"price_vnd": 4_500_000}, "forbidden_claims": [{"field": "price_vnd", "value": 4_500_000}]})
        self.assertTrue(demo_hard_errors("mac_ca", orders_at_offer))                # đơn ở giá khách đòi là sai

    def test_gate_decline_labels_require_no_order_and_the_right_outcome(self):
        base = dict(success_if={"must_not_call_tools": ["order.create"]}, facts_established={"payment": "COD"})
        self.assertEqual(demo_hard_errors("tu_choi_giua_gate", self._call(expected_outcome="tu_choi", **base)), [])
        self.assertTrue(demo_hard_errors("tu_choi_giua_gate", self._call(expected_outcome="hen_goi_lai", **base)))
        self.assertEqual(demo_hard_errors("hoan_giua_gate", self._call(expected_outcome="hen_goi_lai", memory_expectation={"blocker": "can hoi chong"}, **base)), [])
        self.assertTrue(demo_hard_errors("hoan_giua_gate", self._call(expected_outcome="hen_goi_lai", **base)))                   # thiếu blocker
        self.assertTrue(demo_hard_errors("tu_choi_giua_gate", self._call(expected_outcome="tu_choi", success_if={}, facts_established={"payment": "COD"})))   # cho phép tạo đơn
        self.assertTrue(demo_hard_errors("tu_choi_giua_gate", self._call(expected_outcome="tu_choi", success_if=base["success_if"], facts_established={})))    # chưa tới bước gate

    def test_variant_label_requires_variant_level_truth(self):
        good = self._call(ground_truth_facts={"in_stock": True, "requested_variant_in_stock": False}, facts_established={"variant_sku": "SKU-X-1"},
                          success_if={"tool_called": "order.create", "args_match": {"sku": "SKU-X-1"}})
        self.assertEqual(demo_hard_errors("het_hang_bien_the", good), [])
        self.assertTrue(demo_hard_errors("het_hang_bien_the", self._call(ground_truth_facts={"in_stock": True}, facts_established={"variant_sku": "SKU-X-1"},
                                                                          success_if={"tool_called": "order.create", "args_match": {"sku": "SKU-X-1"}})))

    def test_returning_claim_label_needs_chat_claim_and_forbidden_fake_memory(self):
        ok = self._call(channel="zalo_oa", customer_turns=["Chị là khách cũ, mua hồi tháng trước"], success_if={"forbidden_claims": ["em nhớ"]})
        self.assertEqual(demo_hard_errors("tu_nhan_khach_cu_chua_sdt", ok), [])
        self.assertTrue(demo_hard_errors("tu_nhan_khach_cu_chua_sdt", self._call(channel="hotline", customer_turns=["Chị là khách cũ"], success_if={"forbidden_claims": ["em nhớ"]})))
        self.assertTrue(demo_hard_errors("tu_nhan_khach_cu_chua_sdt", self._call(channel="zalo_oa", customer_turns=["Cho chị hỏi giá"], success_if={"forbidden_claims": ["em nhớ"]})))
        self.assertTrue(demo_hard_errors("tu_nhan_khach_cu_chua_sdt", self._call(channel="zalo_oa", customer_turns=["Chị là khách cũ"], success_if={})))

    def test_spoken_label_needs_digit_free_asr_with_a_spoken_phone(self):
        words = "không chín không không không hai không không năm mốt"
        ok = self._call(input_mode="asr_transcript", customer_turns_asr=[f"số của tôi là {words}"])
        self.assertEqual(demo_hard_errors("so_noi_bang_chu", ok), [])
        self.assertTrue(demo_hard_errors("so_noi_bang_chu", self._call(input_mode="asr_transcript", customer_turns_asr=["số của tôi là 0900020051"])))
        self.assertTrue(demo_hard_errors("so_noi_bang_chu", self._call(input_mode="clean", customer_turns_asr=[f"số của tôi là {words}"])))
        self.assertTrue(demo_hard_errors("so_noi_bang_chu", self._call(input_mode="asr_transcript", customer_turns_asr=["giá bốn triệu rưỡi"])))        # thiếu SĐT bằng chữ

    def test_validate_scenario_routes_demo_labels_before_the_generic_branches(self):
        spec = {"scenario_id": "X", "level": "M1", "persona": "p", "hard_case": "het_hang_bien_the", "customer_phone": "0900020024", "customer_name": "A", "honorific": "anh",
                "notes": "", "calls": {"call_1": {"channel": "hotline", "call_date": "2026-10-15", "customer_turns": ["alo"], "ground_truth_facts": {}, "success_if": {},
                                                   "expected_outcome": "hen_goi_lai"}}}
        msgs = [i.message for i in validate_scenario(spec) if i.code == "S7"]
        self.assertEqual(len(msgs), 1)
        self.assertIn("het_hang_bien_the", msgs[0])                               # không phải câu lỗi của nhánh "KM hết hạn"


class CumulativeBudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = os.path.join(self.tmp.name, "generation_runs.jsonl")

    def write(self, *spent):
        with open(self.ledger, "w", encoding="utf-8") as fh:
            for s in spent:
                fh.write(json.dumps({"run": "auto", "spent_vnd": s}) + "\n")

    def test_hard_cap_is_a_constant_in_code(self):
        self.assertEqual(B.HARD_CAP_VND, 10_000.0)
        self.assertGreater(B.ONE_CALL_MARGIN_VND, 0)

    def test_the_real_ledger_already_counts_previous_spend(self):
        self.assertGreater(B.spent_total(), 1000)                                 # 10 mẫu đã tiêu ~1.470 VND → tính vào trần 10.000

    def test_empty_ledger_gives_requested_cap_up_to_the_remaining(self):
        self.assertEqual(B.spent_total(self.ledger), 0.0)
        self.assertEqual(B.run_cap(500, self.ledger), 500)
        self.assertEqual(B.run_cap(1e9, self.ledger), B.HARD_CAP_VND - B.ONE_CALL_MARGIN_VND)      # không nâng được trần bằng cờ

    def test_cap_shrinks_with_spend_and_never_allows_going_over_in_total(self):
        self.write(3000, 4500.5)
        self.assertAlmostEqual(B.spent_total(self.ledger), 7500.5)
        self.assertAlmostEqual(B.run_cap(1e9, self.ledger), 10_000 - 7500.5 - B.ONE_CALL_MARGIN_VND)
        self.assertEqual(B.run_cap(100, self.ledger), 100)                        # hạ trần thì được

    def test_exhausted_ledger_refuses_to_run(self):
        self.write(9_950)                                                         # còn 50 < biên một lần gọi
        with self.assertRaises(B.CumulativeBudgetExhausted):
            B.run_cap(500, self.ledger)
        self.write(10_500)
        with self.assertRaises(B.CumulativeBudgetExhausted):
            B.run_cap(1, self.ledger)
        self.assertEqual(B.remaining(self.ledger), 0.0)

    def test_non_positive_request_is_rejected(self):
        with self.assertRaises(ValueError):
            B.run_cap(0, self.ledger)

    def test_record_run_only_appends(self):
        self.write(100)
        B.record_run({"run": "auto", "spent_vnd": 25.5}, self.ledger)
        with open(self.ledger, encoding="utf-8") as fh:
            self.assertEqual(len([l for l in fh if l.strip()]), 2)
        self.assertAlmostEqual(B.spent_total(self.ledger), 125.5)


class GenerateScriptTest(unittest.TestCase):
    """Chạy `scripts/generate_dataset_text.py` với sổ cái và thư mục ra tạm — KHÔNG gọi LLM thật."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "generate_dataset_text.py")
        spec = importlib.util.spec_from_file_location("generate_dataset_text", path)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = os.path.join(self.tmp.name, "ledger.jsonl")
        self.out = os.path.join(self.tmp.name, "out")
        p = mock.patch.object(B, "LEDGER_PATH", self.ledger)
        p.start()
        self.addCleanup(p.stop)

    def ledger_rows(self):
        with open(self.ledger, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def run_main(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = self.mod.main(["--out", self.out, *args])
        return rc, buf.getvalue()

    def test_select_batch_takes_the_first_n_pending_frames_in_order(self):
        from src.dataset.frames54 import build_frames54
        frames = build_frames54()
        self.assertEqual([f["scenario"]["scenario_id"] for f in self.mod.select_batch(frames, set(), 10)], [f"SC-D{i:02d}" for i in range(1, 11)])
        kept = {f"SC-D{i:02d}/{c['name']}" for f in frames[:3] for i in [int(f["scenario"]["scenario_id"][4:])] for c in f["calls"]}
        self.assertEqual(self.mod.select_batch(frames, kept, 10)[0]["scenario"]["scenario_id"], "SC-D04")           # khung đã xong được bỏ qua
        partial = {"SC-D01/call_1"}                                              # còn call_2 → vẫn chưa xong
        self.assertEqual(self.mod.select_batch(frames, partial, 1)[0]["scenario"]["scenario_id"], "SC-D01")
        self.assertEqual(len(self.mod.select_batch(frames, set(), 0)), 54)

    def test_unresolved_dialogues_do_not_count_for_duplicate_checks(self):
        turn = {"speaker": "C", "text_written": "Giao về số 22 đường Giải Phóng"}
        existing = {"SC-A/call_1": {"meta": {"ok": True}, "turns": [turn]}, "SC-B/call_1": {"meta": {"ok": False}, "turns": [turn]},
                    "SC-C/call_1": {"turns": [turn, {"speaker": "A", "text_written": "dạ"}]}}
        self.assertEqual([k for k, _ in self.mod.customer_lines(existing)], ["SC-A/call_1", "SC-C/call_1"])        # bản chưa đạt bị loại; thiếu meta coi là đạt

    def test_dry_run_lists_a_batch_of_10_and_spends_nothing(self):
        rc, out = self.run_main("--set", "frames54", "--dry-run")
        self.assertEqual(rc, 0)
        self.assertIn("lô lần này: 10 khung", out)
        self.assertIn("SC-D01, SC-D02", out)
        self.assertNotIn("SC-D11", out)
        self.assertFalse(os.path.exists(self.ledger))
        self.assertEqual(os.listdir(os.path.join(self.out, "dialogues")), [])

    def test_batch_flag_changes_the_batch_size(self):
        rc, out = self.run_main("--set", "frames54", "--dry-run", "--batch", "3")
        self.assertIn("lô lần này: 3 khung → SC-D01, SC-D02, SC-D03", out)

    def test_exhausted_cumulative_cap_stops_before_any_llm_is_created(self):
        with open(self.ledger, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"run": "x", "spent_vnd": 9_990}) + "\n")
        with mock.patch("src.llm.client.LLMClient", side_effect=AssertionError("không được tạo LLM client khi đã hết trần")):
            rc, out = self.run_main("--set", "frames54", "--max-cost-vnd", "5000")
        self.assertEqual(rc, 4)
        self.assertIn("chạm trần tích lũy", out)
        self.assertEqual(len(self.ledger_rows()), 1)                                  # không ghi thêm gì

    def test_run_cap_is_clamped_to_remaining_and_spend_is_always_recorded(self):
        from src.llm.cost_tracker import BudgetExceeded
        with open(self.ledger, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"run": "x", "spent_vnd": 9_500}) + "\n")
        seen = {}

        class Tracker:
            cumulative_usd_cost = 0.0

            def _vnd_rate(self):
                return 1.0

            def set_hard_cap(self, v):
                seen["cap"] = v

        class FakeLLM:
            available = True
            model = "fake"
            cost_tracker = Tracker()

            def __init__(self, **kw):
                pass

            def complete_json(self, messages):
                self.cost_tracker.cumulative_usd_cost = 12.5                   # đã tiêu 12,5 VND rồi mới chạm trần giữa chừng
                raise BudgetExceeded(12.5, seen["cap"])

        with mock.patch("src.llm.client.LLMClient", FakeLLM):
            rc, out = self.run_main("--set", "frames54", "--max-cost-vnd", "5000", "--batch", "2")
        self.assertEqual(rc, 3)
        self.assertAlmostEqual(seen["cap"], 10_000 - 9_500 - B.ONE_CALL_MARGIN_VND)    # 400, không phải 5000
        rows = self.ledger_rows()
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[1]["spent_vnd"], 12.5)                        # chi phí đã tiêu được ghi nốt dù dừng giữa chừng
        self.assertIsNotNone(rows[1]["stopped"])
        self.assertEqual(rows[1]["set"], "frames54")
        self.assertLessEqual(B.spent_total(), 10_000)


if __name__ == "__main__":
    unittest.main()
