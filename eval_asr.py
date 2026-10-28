"""
Đo WER/CER/Entity Accuracy cho module ASR local (faster-whisper hoặc Gipformer, chọn bằng --backend / ASR_BACKEND) trên 12 hội thoại mẫu
của BTC (BTC-Data-Vong1-TEAMS/asr/ground_truth.json) — hiện chỉ có transcript thật cho
D01-D04 (8 hội thoại còn lại BTC giữ để chấm mù, audio của cả 12 sẽ phát ngày chấm thi).

Chuẩn hóa trước khi tính WER/CER (theo đúng "normalization_rule" trong ground_truth.json):
lowercase, Unicode NFC, bỏ dấu câu, gộp khoảng trắng. KHÔNG quy đổi số<->chữ ở bước này —
ground truth viết số bằng chữ (vd "năm triệu hai trăm nghìn"), ASR tiếng Việt nói chuyện
thường cũng ra số dạng chữ, nên so sánh ở cùng dạng chữ là hợp lý và nhất quán với cách
reference_eval.py (BTC) tự viết hàm wer_cer() của họ (không ITN hai bên).

Entity Accuracy: CHỈ kiểm được các entity DẠNG SỐ (price_vnd, room_area_m2, budget_vnd,
delivery_days, warranty_months, size_old/new, các loại phí...) bằng cách chạy hypothesis
qua RequestNormalizer thật (ITN có sẵn) rồi tìm chuỗi số trong văn bản đã chuẩn hóa. Entity
phi số (sku, order_id, phone, blocker, payment, color) không kiểm được bằng substring match
đáng tin cậy (cần NLU/NER riêng ngoài phạm vi ASR) — báo "skipped", không giả vờ đã kiểm.

Không có audio -> báo "chưa có audio, sẵn sàng khi BTC phát file", không lỗi.
"""
import os
import sys
import json
import re
import unicodedata
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "asr", "ground_truth.json")
AUDIO_DIR = os.path.join(HERE, "BTC-Data-Vong1-TEAMS", "asr", "audio")
REPORT_PATH = os.path.join(HERE, "runs", "asr_report.json")


def normalize_for_wer(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\sàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _edit_distance(a: list, b: list) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def wer(hyp: str, ref: str) -> float:
    ref_words = ref.split()
    if not ref_words:
        return 0.0 if not hyp.split() else 1.0
    return _edit_distance(hyp.split(), ref_words) / len(ref_words)


def cer(hyp: str, ref: str) -> float:
    ref_chars = list(ref.replace(" ", ""))
    hyp_chars = list(hyp.replace(" ", ""))
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return _edit_distance(hyp_chars, ref_chars) / len(ref_chars)


NUMERIC_ENTITY_KEYS = {
    "price_vnd", "room_area_m2", "budget_vnd", "delivery_days", "warranty_months",
    "competitor_price_vnd", "min_free_ship_vnd", "bulky_fee_vnd", "exchange_fee_vnd",
    "size_old", "size_new", "promo_vnd",
}


def check_entities(normalized_hyp_text: str, entities: dict) -> dict:
    checked, skipped = {}, []
    for key, value in entities.items():
        if key not in NUMERIC_ENTITY_KEYS or not isinstance(value, (int, float)) or isinstance(value, bool):
            skipped.append(key)
            continue
        candidates = {str(int(value)), f"{int(value):,}".replace(",", "."), f"{int(value):,}"}
        checked[key] = any(c in normalized_hyp_text for c in candidates)
    return {"checked": checked, "skipped_non_numeric": skipped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio-dir", default=AUDIO_DIR)
    ap.add_argument("--backend", choices=["whisper", "gipformer"], default=None,
                    help="backend ASR (mặc định theo biến môi trường ASR_BACKEND, nếu không có là whisper). So sánh đầy đủ: scripts/compare_asr.py")
    args = ap.parse_args()
    if args.backend:
        os.environ["ASR_BACKEND"] = args.backend

    if not os.path.exists(GT_PATH):
        print(f"[ASR-EVAL] Không tìm thấy {GT_PATH}")
        sys.exit(1)

    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt = json.load(f)

    from src.channels.offline_asr import transcribe_audio

    results = {}
    for d in gt["dialogues"]:
        did = d["id"]
        ref_text = normalize_for_wer(d["full_text"])
        audio_path = None
        for ext in (".wav", ".mp3"):
            p = os.path.join(args.audio_dir, did + ext)
            if os.path.exists(p):
                audio_path = p
                break

        if not audio_path:
            results[did] = {"status": "chưa có audio, sẵn sàng khi BTC phát file"}
            print(f"[{did}] chưa có audio, sẵn sàng khi BTC phát file")
            continue

        hyp_raw = transcribe_audio(audio_path)
        if not hyp_raw:
            results[did] = {"status": "ASR không khả dụng hoặc transcribe thất bại — xem log [ASR]"}
            print(f"[{did}] ASR không khả dụng hoặc transcribe thất bại")
            continue

        hyp_text = normalize_for_wer(hyp_raw)
        w = wer(hyp_text, ref_text)
        c = cer(hyp_text, ref_text)
        # ITN thật (chữ → số) TRƯỚC khi tìm số trong giả thuyết — trước đây tìm thẳng trên văn bản chưa ITN nên model ra chữ
        # (Gipformer: "bốn triệu tám trăm...") luôn bị chấm sai dù đọc đúng.
        from src.channels.asr_postprocess import normalize_transcript
        ent = check_entities(normalize_transcript(hyp_raw).normalized_text, d.get("entities_multi", d.get("entities", {})))
        results[did] = {
            "status": "ok", "wer": round(w, 4), "cer": round(c, 4),
            "hypothesis": hyp_raw, "reference": d["full_text"], "entities": ent
        }
        print(f"[{did}] WER={w:.2%}  CER={c:.2%}  entities_checked={ent['checked']}")

    ok_results = [r for r in results.values() if r.get("status") == "ok"]
    summary = {
        "n_dialogues_total": len(gt["dialogues"]),
        "n_with_audio_evaluated": len(ok_results),
        "avg_wer": round(sum(r["wer"] for r in ok_results) / len(ok_results), 4) if ok_results else None,
        "avg_cer": round(sum(r["cer"] for r in ok_results) / len(ok_results), 4) if ok_results else None,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "dialogues": results}, f, ensure_ascii=False, indent=2)

    print("\n--- TỔNG HỢP ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"-> Báo cáo đầy đủ: {REPORT_PATH}")


if __name__ == "__main__":
    main()
