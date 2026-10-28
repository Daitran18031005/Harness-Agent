"""Pipeline sinh dataset văn bản (không gọi LLM thật): khung xác định, ô trống, text_spoken, kiểm S1–S14, sinh lại khi lỗi, trần chi phí."""
import copy
import unittest

from src.dataset import specs, truth as T
from src.dataset.assemble import review_markdown, scenario_from
from src.dataset.validate import (call_dates, distribution, hard_case_type, validate_dialogue, validate_scenario)
from src.dataset.writer import DialogueWriter, GREETING, assemble_turns, check_customer_facts, teencodify


class FakeLLM:
    """complete_json trả lần lượt các đầu ra dựng sẵn; ghi nhận số lần gọi và chi phí giả."""
    model = "fake-model"

    def __init__(self, outputs, cost=1.0):
        self.outputs, self.calls, self.cost, self.spent_vnd = list(outputs), [], cost, 0.0

    def complete_json(self, messages):
        self.calls.append(messages)
        self.spent_vnd += self.cost
        return self.outputs.pop(0), {"completion_tokens": 100, "prompt_tokens": 100, "reasoning_tokens": 10}


def spent(llm):
    return llm.spent_vnd


A01_C1 = {"turns": [
    {"speaker": "C", "text": "Ờ, chị muốn hỏi máy lọc không khí cho phòng ngủ.", "states": []},
    {"speaker": "A", "text": "Dạ em chào chị Thu ạ, phòng nhà mình rộng khoảng bao nhiêu mét vuông và nhà có bé nhỏ không ạ?", "states": []},
    {"speaker": "C", "text": "Phòng khoảng 25m², nhà chị có bé 2 tuổi, ngân sách tầm 5 triệu thôi em.", "states": ["room_area_m2", "has_children", "budget_vnd"]},
    {"speaker": "A", "text": "Dạ em gợi ý {product} giá {price}, hơi vượt ngân sách {overage} nhưng có khóa an toàn trẻ em; đang tặng {gift} đến hết {promo_end} ạ.", "states": []},
    {"speaker": "C", "text": "Ừm, để chị hỏi chồng đã.", "states": ["blocker"]},
    {"speaker": "A", "text": "Dạ vâng ạ, chị cho em xin số điện thoại để hotline gọi lại mình nhé.", "states": []},
    {"speaker": "C", "text": "Số chị 0900010001 nha.", "states": ["phone_provided"]},
    {"speaker": "A", "text": "Dạ em ghi nhận rồi ạ, cảm ơn chị.", "states": []},
]}


class FrameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = specs.build_sample10()

    def test_ten_frames_cover_required_structures(self):
        self.assertEqual(len(self.frames), 10)
        groups = [f["scenario"]["group"] for f in self.frames]
        self.assertEqual((groups.count("A"), groups.count("B"), groups.count("C")), (3, 2, 5))
        self.assertEqual(sorted(len(f["calls"]) for f in self.frames), [1, 1, 1, 1, 1, 2, 2, 2, 3, 3])
        types = {hard_case_type(f["scenario"]["hard_case"]) for f in self.frames}
        self.assertTrue({"đổi ý", "mâu thuẫn với phiên trước", "KM hết hạn", "hỏi ngoài tài liệu"} <= types)
        channels = {c["channel"] for f in self.frames for c in f["calls"]}
        self.assertEqual(channels, {"hotline", "chat_fanpage", "zalo_oa"})

    def test_truths_come_from_mock_tools(self):
        by = {f["scenario"]["scenario_id"]: f for f in self.frames}
        a01 = by["SC-A01"]["calls"][1]
        self.assertEqual(a01["expected"]["success_if"]["args_match"]["price_vnd"], T.quote("SKU-AP-Y", "2026-10-17")["final_price_vnd"])
        b01 = by["SC-B01"]["calls"][2]
        self.assertEqual(b01["expected"]["ground_truth_facts"]["extra_payment_vnd"], 219000)           # 1.690.000 + 50.000 − 1.521.000
        self.assertEqual(by["SC-C04"]["calls"][0]["agent_vars"]["cod_limit"]["text"], "10.000.000đ")
        self.assertEqual(by["SC-A03"]["calls"][1]["expected"]["ground_truth_facts"]["promo_PUMP-GIFT_active"], False)

    def test_frames_are_deterministic(self):
        again = specs.build_sample10()
        self.assertEqual(self.frames, again)

    def test_every_frame_scenario_passes_scenario_rules_once_turns_exist(self):
        """Ghép kịch bản từ khung + lời thoại giả: không có LỖI S1–S9 nào."""
        for fr in self.frames:
            dialogues = {}
            for call in fr["calls"]:
                turns = []
                for i, f in enumerate(call["customer_facts"], 1):
                    pass
                cust_text = " ".join(f["hint"] for f in call["customer_facts"]) or "alo"
                turns = [{"idx": 1, "speaker": "C", "text_written": cust_text, "text_spoken": "x", "entities": {}, "states": [f["key"] for f in call["customer_facts"]]}]
                if call["style"] == "teencode":
                    turns[0]["text_asr"] = teencodify(cust_text)
                dialogues[call["name"]] = {"turns": turns}
            sc = scenario_from(fr, dialogues)
            errs = [i.line() for i in validate_scenario(sc, {sc["customer_phone"]: [sc["scenario_id"]]}) if i.severity == "LỖI"]
            self.assertEqual(errs, [], fr["scenario"]["scenario_id"])


class AssembleTest(unittest.TestCase):
    def setUp(self):
        self.frame = specs.a01()
        self.call = self.frame["calls"][0]

    def test_placeholders_filled_entities_and_spoken(self):
        turns, err = assemble_turns(A01_C1["turns"], self.call)
        self.assertEqual(err, [])
        agent = [t for t in turns if t["speaker"] == "A"]
        self.assertIn("5.200.000đ", agent[1]["text_written"])
        self.assertNotIn("{", " ".join(t["text_written"] for t in turns))
        self.assertEqual(agent[1]["entities"]["sku"], "SKU-AP-Y")
        self.assertEqual(agent[1]["entities"]["price_vnd"], 5200000)
        self.assertEqual(agent[1]["entities"]["promo_expiry"], "2026-10-22")
        self.assertIn("năm triệu hai trăm nghìn", agent[1]["text_spoken"])
        cust = [t for t in turns if t["speaker"] == "C"]
        self.assertEqual(cust[1]["entities"], {"room_area_m2": 25, "has_children": True, "budget_vnd": 5000000})
        self.assertEqual(cust[3]["entities"], {"phone": "0900010001"})
        self.assertIn("không chín không không không một không không không một", cust[3]["text_spoken"].replace("  ", " ") if False else cust[3]["text_spoken"])
        self.assertEqual(check_customer_facts(turns, self.call), [])

    def test_hotline_opening_adds_fixed_greeting(self):
        call2 = specs.a01()["calls"][1]
        turns, _ = assemble_turns([{"speaker": "C", "text": "Alo", "states": []}], call2)
        self.assertEqual((turns[0]["speaker"], turns[0]["text_written"]), ("A", GREETING))
        self.assertIn("bê tê xê", turns[0]["text_spoken"])

    def test_unknown_placeholder_and_speaker_are_structural_errors(self):
        _, err = assemble_turns([{"speaker": "A", "text": "giá {gia_bia} ạ"}, {"speaker": "X", "text": "?"}], self.call)
        self.assertTrue(any("ô trống không có trong danh sách" in e for e in err))
        self.assertTrue(any("speaker lạ" in e for e in err))

    def test_missing_or_mislabelled_customer_fact_detected(self):
        bad = copy.deepcopy(A01_C1["turns"])
        bad[2]["text"] = "Phòng nhà chị rộng lắm, nhà có bé, ngân sách tầm 5 triệu."          # thiếu 25m² nhưng gắn nhãn room_area_m2
        turns, _ = assemble_turns(bad, self.call)
        errs = check_customer_facts(turns, self.call)
        self.assertTrue(any("room_area_m2" in e for e in errs))

    def test_teencode_is_deterministic_and_keeps_numbers(self):
        s = "Em ơi quạt đứng Senko còn hàng không, giá bao nhiêu vậy? Lấy 1 cái 590k nhé"
        self.assertEqual(teencodify(s), teencodify(s))
        out = teencodify(s)
        self.assertIn("590k", out)
        self.assertNotRegex(out, r"[àáạảãăâđêôơư]")


class QualityFixesTest(unittest.TestCase):
    def test_dedupe_repeated_category_phrase(self):
        from src.dataset.writer import dedupe_phrase
        self.assertEqual(dedupe_phrase("Máy lọc không khí Máy lọc không khí AirPure Y hiện giá"), "Máy lọc không khí AirPure Y hiện giá")
        self.assertEqual(dedupe_phrase("Dạ dạ em chào chị"), "Dạ dạ em chào chị")                    # < 3 từ: không đụng

    def test_agent_cannot_use_address_before_customer_says_it(self):
        call = specs.b01()["calls"][1]                                                          # call_2: khách đọc địa chỉ ở lượt sau
        bad = [{"speaker": "C", "text": "Anh lấy size 41 màu đen", "states": []},
               {"speaker": "A", "text": "Dạ em giao về {address} nhé anh", "states": []},
               {"speaker": "C", "text": "Giao về số 45 đường Lê Văn Sỹ, quận 3", "states": ["address"]}]
        _, errs = assemble_turns(bad, call)
        self.assertTrue(any("CHƯA nói 'address'" in e for e in errs), errs)
        good = [bad[0], {"speaker": "C", "text": "Giao về số 45 đường Lê Văn Sỹ, quận 3", "states": ["address"]},
                {"speaker": "A", "text": "Dạ em giao về {address} nhé anh", "states": []}]
        self.assertEqual(assemble_turns(good, call)[1], [e for e in assemble_turns(good, call)[1] if "CHƯA nói" not in e])

    def test_forbidden_claims_do_not_collide_with_a_proper_refusal(self):
        fc = specs.c02()["calls"][0]["expected"]["success_if"]["forbidden_claims"]
        refusal = "em không thể khẳng định máy chữa được tắc tia sữa hay viêm vú, chị nên hỏi bác sĩ"
        self.assertFalse([c for c in fc if c.lower() in refusal])

    def test_address_variables_never_identical_across_scenarios(self):
        addrs = [v["text"] for f in specs.build_sample10() for c in f["calls"] for k, v in c["agent_vars"].items() if k == "address"]
        by_scenario = {}
        for f in specs.build_sample10():
            by_scenario[f["scenario"]["scenario_id"]] = {v["text"] for c in f["calls"] for k, v in c["agent_vars"].items() if k == "address"}
        flat = [next(iter(a)) for a in by_scenario.values() if a]
        self.assertEqual(len(flat), len(set(flat)))

    def test_teencode_scenario_asks_llm_for_accented_text(self):
        call = specs.c05()["calls"][0]
        self.assertIn("CÓ DẤU", call["customer_plot"])
        self.assertNotIn("kiểu teencode", call["customer_plot"].split("VIẾT")[0])


class DialogueRulesTest(unittest.TestCase):
    def rec(self, turns, **extra):
        return {"scenario_id": "SC-X", "call": "call_1", "turns": turns, **extra}

    def t(self, idx, sp, written, spoken=None, template=None):
        d = {"idx": idx, "speaker": sp, "text": written, "text_written": written, "text_spoken": spoken if spoken is not None else written.lower(), "entities": {}}
        if template:
            d["text_template"] = template
        return d

    def test_s11_agent_digits_outside_placeholders_rejected(self):
        r = self.rec([self.t(1, "C", "alo"), self.t(2, "A", "Dạ giá 5.200.000đ ạ", "dạ giá năm triệu hai trăm nghìn ạ", template="Dạ giá 5.200.000đ ạ"),
                      self.t(3, "C", "ok"), self.t(4, "C", "ok2")])
        codes = [i.code for i in validate_dialogue(r)]
        self.assertIn("S11", codes)
        self.assertIn("S10", codes)                                                # lượt 3 và 4 cùng người nói

    def test_s11_unfilled_placeholder_rejected(self):
        r = self.rec([self.t(1, "A", "Dạ giá {price} ạ", template="Dạ giá {price} ạ")] + [self.t(i, "C" if i % 2 == 0 else "A", "câu số " + str(i)) for i in range(2, 7)])
        self.assertIn("S11", [i.code for i in validate_dialogue(r)])

    def test_s12_spoken_must_round_trip_numbers(self):
        r = self.rec([self.t(1, "A", "Giá 5.200.000đ", "giá năm triệu"), self.t(2, "C", "ok"), self.t(3, "A", "ừ"), self.t(4, "C", "ok2"), self.t(5, "A", "a"), self.t(6, "C", "ok3")])
        self.assertIn("S12", [i.code for i in validate_dialogue(r)])

    def test_s13_customer_turns_must_match_dialogue(self):
        r = self.rec([self.t(1, "C", "alo"), self.t(2, "A", "dạ"), self.t(3, "C", "giá"), self.t(4, "A", "dạ"), self.t(5, "C", "ok")])
        self.assertIn("S13", [i.code for i in validate_dialogue(r, {"customer_turns": ["alo", "khác", "ok"]})])
        self.assertNotIn("S13", [i.code for i in validate_dialogue(r, {"customer_turns": ["alo", "giá", "ok"]})])

    def test_s10_duplicate_customer_lines_across_scenarios(self):
        r = self.rec([self.t(1, "C", "cho chị hỏi máy lọc không khí phòng ngủ"), self.t(2, "A", "dạ"), self.t(3, "C", "giá bao nhiêu em"), self.t(4, "A", "dạ"), self.t(5, "C", "ok")])
        issues = validate_dialogue(r, None, [("SC-Y/call_1", "cho chị hỏi máy lọc không khí phòng ngủ")])
        self.assertTrue(any(i.code == "S10" and "trùng" in i.message for i in issues))


class ScenarioRulesTest(unittest.TestCase):
    def base(self):
        return {"scenario_id": "SC-T", "level": "M1", "persona": "khach_so_gia", "hard_case": None, "customer_phone": "0900019999", "customer_name": "A",
                "honorific": "anh", "notes": "n", "calls": {"call_1": {"channel": "hotline", "call_date": "2026-10-15", "customer_turns": ["phòng 25m², bé nhỏ", "ok"],
                                                                        "expected_outcome": "hen_goi_lai"}}}

    def codes(self, spec, phones=None):
        return [i.code for i in validate_scenario(spec, phones) if i.severity == "LỖI"]

    def test_clean_scenario_has_no_errors(self):
        self.assertEqual(self.codes(self.base()), [])

    def test_s3_fact_not_in_customer_text(self):
        s = self.base()
        s["calls"]["call_1"]["facts_established"] = {"room_area_m2": 30}
        self.assertIn("S3", self.codes(s))

    def test_s4_wrong_price_and_wrong_promo_state(self):
        s = self.base()
        s["calls"]["call_1"].update({"facts_established": {"product_advised": "SKU-AP-Y", "promo_code": "GIFT-FILTER"},
                                     "ground_truth_facts": {"price_vnd": 1234567, "promo_active": False}})
        self.assertEqual(self.codes(s).count("S4"), 2)

    def test_s5_unknown_tool_and_sku(self):
        s = self.base()
        s["calls"]["call_1"]["success_if"] = {"tool_called": "order.fly", "args_match": {"sku": "SKU-NOPE"}}
        s2 = self.base()
        s2["calls"]["call_1"]["success_if"] = {"tool_called": "order.create", "args_match": {"sku": "SKU-NOPE"}}
        self.assertIn("S5", self.codes(s))
        self.assertIn("S5", self.codes(s2))

    def test_s6_carry_over_must_come_from_earlier_facts(self):
        s = self.base()
        s["calls"]["call_2"] = {"channel": "hotline", "days_later": 1, "customer_turns": ["alo"], "must_carry_over": ["order_id"]}
        self.assertIn("S6", self.codes(s))

    def test_s7_hard_case_structure(self):
        s = self.base()
        s["hard_case"] = "mau_thuan_phien_truoc"
        self.assertIn("S7", self.codes(s))
        s2 = self.base()
        s2["hard_case"] = "khuyen_mai_het_han"
        self.assertIn("S7", self.codes(s2))

    def test_s8_s9_channel_identity_and_phone_rules(self):
        s = self.base()
        s["calls"]["call_1"].update({"channel": "chat_fanpage", "channel_identity": "zalo_x"})
        self.assertIn("S8", self.codes(s))
        s2 = self.base()
        s2["customer_phone"] = "0912345678"
        self.assertIn("S9", self.codes(s2))
        s3 = self.base()
        s3["calls"]["call_1"]["customer_turns"] = ["số em 0987654321 nhé", "ok"]
        self.assertIn("S9", self.codes(s3))
        self.assertIn("S9", self.codes(self.base(), {"0900019999": ["SC-T", "SC-U"]}))

    def test_s2_dates_must_increase(self):
        s = self.base()
        s["calls"]["call_2"] = {"channel": "hotline", "call_date": "2026-10-01", "customer_turns": ["alo"]}
        self.assertIn("S2", self.codes(s))
        self.assertEqual(list(call_dates(s).values()), ["2026-10-15", "2026-10-01"])


class WriterTest(unittest.TestCase):
    def setUp(self):
        self.frame = specs.a01()
        self.call = self.frame["calls"][0]

    def writer(self, outputs, cost=1.0, cap=100.0, retries=2):
        llm = FakeLLM(outputs, cost)
        return DialogueWriter(llm, cap, spent, {"khach_do_du_hoi_nguoi_nha": "lịch sự"}, retries=retries), llm

    def test_good_first_attempt(self):
        w, llm = self.writer([A01_C1])
        rec = w.write_call(self.frame, self.call, "", [])
        self.assertTrue(rec["meta"]["ok"])
        self.assertEqual(rec["meta"]["attempts"], 1)
        self.assertEqual(len(llm.calls), 1)

    def test_bad_attempt_is_regenerated_with_error_feedback(self):
        bad = copy.deepcopy(A01_C1)
        bad["turns"][3]["text"] = "Dạ em gợi ý {product} giá 5.200.000đ ạ."           # số ngoài ô trống
        w, llm = self.writer([bad, A01_C1])
        rec = w.write_call(self.frame, self.call, "", [])
        self.assertTrue(rec["meta"]["ok"])
        self.assertEqual(rec["meta"]["attempts"], 2)
        self.assertIn("LOI_LAN_TRUOC_PHAI_SUA", llm.calls[1][1]["content"])             # lỗi lần 1 được đưa vào prompt lần 2
        self.assertFalse(w.log[0]["ok"])
        self.assertTrue(w.log[1]["ok"])

    def test_gives_up_after_retries_and_records_unresolved(self):
        bad = copy.deepcopy(A01_C1)
        bad["turns"][2]["states"] = []
        bad["turns"][2]["text"] = "Phòng nhà chị rộng lắm."
        w, llm = self.writer([bad, bad, bad], retries=2)
        rec = w.write_call(self.frame, self.call, "", [])
        self.assertFalse(rec["meta"]["ok"])
        self.assertEqual(rec["meta"]["attempts"], 3)
        self.assertTrue(rec["meta"]["unresolved"])

    def test_cost_cap_stops_before_next_call(self):
        from src.eval.runner import BudgetExceeded
        bad = copy.deepcopy(A01_C1)
        bad["turns"][2]["text"] = "ngắn"
        w, llm = self.writer([bad, bad, A01_C1], cost=60.0, cap=100.0)
        with self.assertRaises(BudgetExceeded):
            w.write_call(self.frame, self.call, "", [])
        self.assertEqual(len(llm.calls), 2)                                              # lần 3 bị chặn bởi trần, không gọi thêm

    def test_prompt_contains_rules_facts_and_no_answer_leak(self):
        w, llm = self.writer([A01_C1])
        w.write_call(self.frame, self.call, "", [])
        prompt = llm.calls[0][1]["content"]
        for needle in ("fact_khach_phai_noi", "o_trong_agent", "{price}", "TUYỆT ĐỐI không viết chữ số"):
            self.assertIn(needle, prompt)
        self.assertNotIn("5.200.000", prompt)                                            # giá thật không đưa cho LLM (chỉ ô trống)


class ReviewTest(unittest.TestCase):
    def test_review_renders_both_written_and_spoken(self):
        frame = specs.a01()
        turns, _ = assemble_turns(A01_C1["turns"], frame["calls"][0])
        rec = {"scenario_id": "SC-A01", "call": "call_1", "turns": turns, "meta": {"attempts": 1, "ok": True}}
        md = review_markdown([{"scenario": frame["scenario"], "calls": frame["calls"][:1]}], {"SC-A01/call_1": rec}, {}, [], 12.3, "fake")
        self.assertIn("năm triệu hai trăm nghìn", md)
        self.assertIn("5.200.000đ", md)
        self.assertIn("| # | ai | written | spoken | entities |", md)


if __name__ == "__main__":
    unittest.main()
