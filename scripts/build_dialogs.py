"""Tạo transcript chuẩn (KHÔNG tạo audio) cho việc sinh audio + đo ASR, từ các cuộc gọi của bộ đánh giá `team_eval`.

    python scripts/build_dialogs.py                 # → dialogs/ground_truth.json + dialogs/README.md

Nguồn: lời khách = `customer_turns` của kịch bản; lời agent = `agent_text` THẬT trong trace lần đo `runs/m1_final2/full.jsonl` (không gọi LLM).
Định dạng: đúng `BTC-Data-Vong1-TEAMS/asr/ground_truth.json` (id, vùng miền/giới tính, noisy, turns[idx, speaker, text, entities], full_text, entities) + vài trường
thêm (channel, call_date, persona, hard_case, expected, system_result, text_written). `text` là dạng ĐỌC THÀNH LỜI (số viết bằng chữ, `src/dataset/spoken.py`).
Chọn 45 cuộc phủ đủ ngữ cảnh (persona × kênh × kết cục × ca khó), cả cuộc hệ thống đạt lẫn trượt; ưu tiên hotline vì dùng để sinh audio."""
import collections, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTC = os.path.join(HERE, "BTC-Data-Vong1-TEAMS")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(BTC, "eval"))
import mock_tools  # noqa: E402
import reference_eval as ref  # noqa: E402
from src.dataset.spoken import spoken_form  # noqa: E402
from src.harness.order_gate import detect_payment  # noqa: E402
from src.memory.memory_extractor import extract_easy_slots  # noqa: E402

TRACE = os.path.join(HERE, "runs", "m1_final2", "full.jsonl")
OUT_DIR = os.path.join(HERE, "dialogs")
N_DIALOGS, MAX_CHAT, N_NOISY = 45, 9, 12
GREETING = "Dạ shop BTC xin nghe, em có thể giúp gì cho mình ạ?"
AGENT_CLAIMS = ("price_vnd", "total_vnd", "in_stock", "warranty_months", "return_days", "exchange_fee_vnd", "delivery_days", "cod_limit_vnd", "restock_date")
CUSTOMER_SLOTS = ("room_area_m2", "budget_vnd", "has_children")
REGIONS = ("bac", "trung", "nam")


def expected_of(spec):
    return (spec.get("success_if") or {}).get("tool_called") or spec.get("expected_outcome") or "khac"


def customer_entities(text):
    ent = {k: v for k, v in extract_easy_slots(text).items() if k in CUSTOMER_SLOTS}
    phones = re.findall(r"(?<!\d)0\d{9}(?!\d)", text)
    if phones:
        ent["phone"] = phones[-1]
    pay = detect_payment(text)
    if pay:
        ent["payment"] = pay
    return ent


def agent_entities(row):
    ent = {}
    for c in row.get("claims") or []:
        if c["field"] in AGENT_CLAIMS:
            ent.setdefault(c["field"], [])
            if c["value"] not in ent[c["field"]]:
                ent[c["field"]].append(c["value"])
    ent = {k: (v[0] if len(v) == 1 else v) for k, v in ent.items()}
    if "price_vnd" in ent:
        sku = next((tc["args"]["sku"] for tc in reversed(row.get("tool_calls") or [])
                    if tc.get("name") in ("pricing.get_quote", "order.create") and isinstance((tc.get("args") or {}).get("sku"), str)), None)
        if sku:
            ent["sku"] = sku
    order = re.search(r"\bOD\d{6}\b", row.get("agent_text") or "")
    if order:
        ent["order_id"] = order.group(0)
    return ent


def region_of(scen, texts):
    text = " ".join(texts)
    r = mock_tools._region_of(text)          # mock trả "bac" cả khi KHÔNG có địa danh nào → chỉ nhận "bac" khi lời khách có địa danh miền Bắc
    if r == "bac" and not re.search(r"hà nội|hải phòng|quảng ninh|nam định|bắc ninh|thái nguyên|hải dương|thái bình|ninh bình|vĩnh phúc|hưng yên|bắc giang|thanh hóa|nghệ an", text.lower()):
        return None
    return r


def main():
    scenarios = ref.load_scenarios(os.path.join(BTC, "test_set", "team_eval"))
    trace = ref.load_trace(TRACE)
    cands = []
    for sid, s in sorted(scenarios.items()):
        for call, spec in sorted(s["calls"].items()):
            rows = [r for r in trace.get((sid, call), []) if (r.get("customer_text") or "").strip()]      # bỏ lượt chốt (không có lời khách)
            if len(rows) < 2 or len(rows) != len(spec.get("customer_turns") or []):
                continue
            earlier = [r for c in sorted(s["calls"]) if c < call for r in trace.get((sid, c), [])]
            ok, reasons = ref.check_call(spec, trace.get((sid, call), []), ref.created_order_ids(earlier))
            hard = s.get("hard_case") if isinstance(s.get("hard_case"), str) else ("-" if not s.get("hard_case") else "co")
            cands.append({"sid": sid, "call": call, "spec": spec, "scen": s, "rows": rows, "channel": spec.get("channel", "hotline"),
                          "feat": {("persona", s.get("persona")), ("expected", expected_of(spec)), ("hard", hard), ("channel", spec.get("channel", "hotline")),
                                   ("later_call", call != "call_1"), ("result", "dat" if ok is not False else "truot")},
                          "result": "dat" if ok is not False else "truot", "reasons": reasons or []})

    # chọn tham lam: mỗi lần lấy cuộc mang nhiều giá trị ngữ cảnh CHƯA có nhất; giới hạn số cuộc chat; mỗi kịch bản tối đa 1 cuộc
    picked, seen, used_sid, n_chat = [], collections.Counter(), set(), 0
    while len(picked) < N_DIALOGS:
        best = max((c for c in cands if c["sid"] not in used_sid and (c["channel"] == "hotline" or n_chat < MAX_CHAT)),
                   key=lambda c: (sum(1.0 / (1 + seen[f]) for f in c["feat"]), -len(c["rows"]), c["sid"]), default=None)
        if best is None:
            break
        picked.append(best)
        used_sid.add(best["sid"])
        n_chat += best["channel"] != "hotline"
        seen.update(best["feat"])
    picked.sort(key=lambda c: (c["sid"], c["call"]))

    dialogues, noisy_left, rr = [], N_NOISY, 0
    for i, c in enumerate(picked, 1):
        s, spec = c["scen"], c["spec"]
        cust_texts = [r["customer_text"] for r in c["rows"]]
        region = region_of(s, cust_texts)
        if region is None:
            region, rr = REGIONS[rr % 3], rr + 1
        hon = str(s.get("honorific") or "")
        gender = "m" if hon.startswith("anh") and "/" not in hon else ("f" if hon.startswith(("chị", "cô")) else "mf"[i % 2])
        noisy = c["channel"] == "hotline" and noisy_left > 0 and i % 3 == 0
        noisy_left -= noisy
        turns = []

        def add(speaker, written, ent):
            turns.append({"idx": len(turns) + 1, "speaker": speaker, "text": spoken_form(written), "entities": ent, "text_written": written})
        if c["channel"] == "hotline":
            add("A", GREETING, {})
        for r in c["rows"]:
            add("C", r["customer_text"], customer_entities(r["customer_text"]))
            add("A", r["agent_text"], agent_entities(r))
        merged = collections.OrderedDict()
        for t in turns:
            for k, v in t["entities"].items():
                for x in (v if isinstance(v, list) else [v]):
                    if x not in merged.setdefault(k, []):
                        merged[k].append(x)
        dialogues.append({
            "id": f"T{i:02d}", "customer_region": region, "customer_gender": gender, "agent_gender": "f", "agent_region": "bac",
            "scenario_ref": f"{c['sid']} {c['call']}", "noisy": bool(noisy),
            "note": f"{s.get('persona')} — {expected_of(spec)}" + (f" — ca khó: {s['hard_case']}" if isinstance(s.get("hard_case"), str) else ""),
            "channel": c["channel"], "call_date": c["rows"][0].get("call_date") or spec.get("call_date"), "persona": s.get("persona"),
            "hard_case": s.get("hard_case"), "expected": expected_of(spec),
            "system_result": c["result"], "system_fail_reasons": c["reasons"],
            "entities": {k: (v[0] if len(v) == 1 else v) for k, v in merged.items()},
            "n_turns": len(turns), "turns": turns, "full_text": " ".join(t["text"] for t in turns)})

    # tự kiểm
    assert len(dialogues) >= 40, len(dialogues)
    for d in dialogues:
        assert {t["speaker"] for t in d["turns"]} == {"A", "C"} and all(t["text"].strip() for t in d["turns"]), d["id"]
        assert d["full_text"] == " ".join(t["text"] for t in d["turns"])
    digits = [(d["id"], t["idx"], re.findall(r"\S*\d\S*", t["text"])[:3]) for d in dialogues for t in d["turns"] if re.search(r"\d", t["text"])]

    os.makedirs(OUT_DIR, exist_ok=True)
    gt = {"description": (f"{len(dialogues)} hội thoại chuẩn (transcript, CHƯA có audio) dựng từ bộ đánh giá team_eval: lời khách từ kịch bản, lời agent từ trace lần đo "
                          "runs/m1_final2 (gpt-4o-mini). Cùng định dạng asr/ground_truth.json của BTC; dùng để sinh audio (TTS/thu âm) và đo WER/CER/Entity Accuracy."),
          "hypotheses_format": "như asr/ground_truth.json của BTC: {\"T01\": {\"text\": \"…\", \"entities\": {…}, \"turns\": [{\"idx\": 1, \"speaker\": \"A|C\", \"text\": \"…\"}]}}",
          "normalization_rule": ("Trước khi tính WER/CER: lowercase, NFC, bỏ dấu câu, gộp khoảng trắng. `text` viết số bằng chữ như lời nói (src/dataset/spoken.py); "
                                 "`text_written` là câu gốc có chữ số. Entity so exact-match sau ITN."),
          "reference_date": "2026-10-15", "dialogues": dialogues}
    with open(os.path.join(OUT_DIR, "ground_truth.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(gt, f, ensure_ascii=False, indent=1)

    cnt = lambda key: collections.Counter(str(d[key]) for d in dialogues).most_common()
    table = lambda title, rows: [f"| {title} | Số hội thoại |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in rows] + [""]
    n_turns, n_words = sum(d["n_turns"] for d in dialogues), sum(len(d["full_text"].split()) for d in dialogues)
    lines = [
        "# dialogs/ — transcript chuẩn để sinh audio và đo ASR", "",
        f"`ground_truth.json`: **{len(dialogues)} hội thoại, {n_turns} lượt, {n_words:,} từ** (≈ {n_words / 150:.0f} phút nếu đọc 150 từ/phút). **Chưa có audio.**".replace(",", "."), "",
        "- Tạo bằng `python scripts/build_dialogs.py` (không gọi LLM, chạy lại cho cùng kết quả).",
        "- Lời khách: `customer_turns` của kịch bản `test_set/team_eval`. Lời agent: câu trả lời thật của hệ thống trong `runs/m1_final2/full.jsonl`.",
        "- Định dạng theo `BTC-Data-Vong1-TEAMS/asr/ground_truth.json`; `text` là dạng đọc thành lời (số viết bằng chữ), `text_written` là câu gốc.",
        "- Cuộc hotline có thêm câu chào mở đầu của agent (như mẫu BTC). Lượt chốt không có lời khách của bộ chấm bị bỏ.",
        "- `system_result` = `dat`/`truot`: kết quả chấm của cuộc đó ở lần đo; cuộc `truot` có thể chứa lời agent sai (xem `system_fail_reasons`).",
        "- Vùng miền của khách suy từ địa chỉ trong lời khách (nếu có), còn lại chia đều Bắc/Trung/Nam; giới tính theo cách xưng hô; `noisy` là NHÃN dự kiến để trộn nhiễu khi sinh audio.",
        "", "## Phân bố", ""]
    lines += table("Kênh", cnt("channel")) + table("Vùng miền khách", cnt("customer_region")) + table("Kết cục kỳ vọng", cnt("expected"))
    lines += table("Kết quả hệ thống ở lần đo", cnt("system_result")) + table("Có nhiễu (dự kiến)", cnt("noisy")) + table("Kiểu khách", cnt("persona"))
    lines += table("Ca khó", collections.Counter(str(d["hard_case"]) for d in dialogues).most_common())
    lines += ["## Hạn chế", "",
              "- Lời agent do model sinh: dài và trang trọng hơn người nói thật; có câu liệt kê nhiều sản phẩm.",
              f"- Cuộc qua Zalo/Fanpage ({sum(d['channel'] != 'hotline' for d in dialogues)} cuộc) vốn là tin nhắn; đưa vào để đủ ngữ cảnh.",
              f"- {len(digits)} lượt còn ký tự số sau khi đổi sang dạng đọc (mã, đơn vị lạ) — liệt kê khi chạy script; cần xem lại trước khi thu âm.",
              "- Entity lấy bằng luật (slot của khách, claim của agent trong trace), chưa có người duyệt."]
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(dialogues)} hội thoại, {n_turns} lượt, {n_words} từ → {OUT_DIR}")
    print("còn chữ số trong text:", len(digits), digits[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
