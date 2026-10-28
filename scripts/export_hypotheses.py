"""
Xuất `asr/hypotheses.json` theo định dạng BTC từ một thư mục audio, rồi chấm bằng `wer_cer` CHÍNH THỨC của BTC (không sửa script).

    python scripts/export_hypotheses.py --backend gipformer
    python scripts/export_hypotheses.py --backend gipformer --audio-dir asr/audio --out-dir runs/asr_hypotheses/gipformer

Tên file audio = id hội thoại (D01.mp3, …). Mốc thời gian lượt thoại đọc từ `<id>.segments.json` cạnh audio (xem
`src/channels/asr_hypotheses.py`); không có file đó thì KHÔNG xuất `turns` (không đoán người nói).
Lưu ý định dạng văn bản: Gipformer ra số bằng CHỮ (cùng dạng với transcript chuẩn của BTC nên không phải đổi); backend ra chữ SỐ
(whisper) cần đổi số→chữ trước khi nộp, việc này chưa làm — xem docs/PLAN.md bước 16a.
"""
import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

BTC_ASR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default=os.environ.get("ASR_BACKEND", "gipformer"))
    ap.add_argument("--audio-dir", default=os.path.join(BTC_ASR, "audio"))
    ap.add_argument("--gt", default=os.path.join(BTC_ASR, "ground_truth.json"))
    ap.add_argument("--out-dir", default=None, help="mặc định runs/asr_hypotheses/<backend>")
    ap.add_argument("--call-date", default="2026-10-15", help="ngày tham chiếu để ITN ngày tương đối")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    from src.channels.asr_hypotheses import build_entry
    from src.channels.offline_asr import ASRModelError, get_backend

    out_dir = args.out_dir or os.path.join(CODE_DIR, "runs", "asr_hypotheses", args.backend)
    os.makedirs(out_dir, exist_ok=True)
    try:
        backend = get_backend(args.backend)
        backend.load()
    except (ASRModelError, ValueError) as e:
        print(f"[export_hypotheses] không dùng được backend '{args.backend}': {e}")
        return 2

    ids = []
    if os.path.isfile(args.gt):
        ids = [d["id"] for d in json.load(open(args.gt, encoding="utf-8"))["dialogues"]]
    hyps, notes_all = {}, {}
    for did in ids:
        audio = next((os.path.join(args.audio_dir, did + e) for e in (".wav", ".mp3") if os.path.isfile(os.path.join(args.audio_dir, did + e))), None)
        if not audio:
            print(f"[{did}] chưa có audio — bỏ qua")
            continue
        result = backend.transcribe_detail(audio)
        entry, notes = build_entry(result, audio, args.call_date)
        hyps[did], notes_all[did] = entry, notes
        print(f"[{did}] {len(result.text.split())} từ, RTF {result.rtf:.3f}, entities: {sorted(entry['entities'])}"
              + (f", turns: {len(entry['turns'])}" if "turns" in entry else "") + (f"  ({'; '.join(notes)})" if notes else ""))
    if not hyps:
        print("Không có file audio nào khớp id trong ground_truth.json.")
        return 1

    with open(os.path.join(out_dir, "hypotheses.json"), "w", encoding="utf-8") as fh:
        json.dump(hyps, fh, ensure_ascii=False, indent=1)
    if os.path.isfile(args.gt):
        shutil.copyfile(args.gt, os.path.join(out_dir, "ground_truth.json"))   # bản sao để chạy reference_eval --asr <out-dir>
    print(f"\n-> {os.path.join(out_dir, 'hypotheses.json')}")

    sys.path.insert(0, os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "eval"))
    try:
        import reference_eval
        rep = reference_eval.wer_cer(out_dir)
        if rep:
            rep.pop("per_dialogue", None)
            print("\nBTC wer_cer (script chính thức, chưa đổi gì):")
            print(json.dumps(rep, ensure_ascii=False, indent=1))
            print("\n(!) entity_accuracy trên D01–D04 là TRONG TẬP PHÁT TRIỂN (luật viết sau khi xem dữ liệu); "
                  "số trên tập chưa thấy phải báo riêng. Khóa luật: config/asr_rules.lock.json")
    except Exception as e:
        print(f"(không chạy được reference_eval.wer_cer: {e})")
    print(f"\nTái lập: python BTC-Data-Vong1-TEAMS/eval/reference_eval.py --asr {os.path.relpath(out_dir, CODE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
