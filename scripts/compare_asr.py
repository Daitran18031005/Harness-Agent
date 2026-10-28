"""
So sánh các backend/biến thể ASR trên CÙNG bộ file, không tốn API OpenAI.

    python scripts/compare_asr.py                                   # gipformer(silero) / gipformer(energy) / whisper-base trên D01–D04
    python scripts/compare_asr.py --noise white@10,phone,phone+codec,phone+babble@10,phone+street@10,phone+cafe@10
    python scripts/compare_asr.py --backends gipformer:silero,whisper:small          # biến thể: gipformer:<VAD>, whisper:<cỡ model>
    python scripts/compare_asr.py --manifest asr/audio_real/manifest.json            # thêm file nhóm tự thu (khi có)

Mỗi backend/biến thể chạy trong MỘT TIẾN TRÌNH RIÊNG để đo RAM (peak working set) và thời gian nạp model công bằng.
Công thức nhiễu (xem src/channels/audio_sim.py): white|babble|street|cafe @SNR dB, phone (300–3400 Hz, 8 kHz), codec (µ-law 8-bit).
TẤT CẢ NHIỄU LÀ TỔNG HỢP, không thay thế ghi âm thật. Nguồn tiếng nói luôn là audio TTS sạch, giọng Bắc, n = 4 file (D01–D04).

Chỉ số (mọi WER/CER là micro-average = tổng lỗi / tổng số từ chuẩn, giống `reference_eval.wer_cer` của BTC):
  - WER/CER "thô"      : chuẩn hóa ĐÚNG như BTC (lowercase, NFC, bỏ dấu câu, gộp khoảng trắng); KHÔNG quy đổi số.
  - WER/CER "ITN 2 vế" : cả transcript chuẩn lẫn giả thuyết cùng qua ITN của dự án (chữ→số, bỏ dấu phân cách nghìn) rồi mới chuẩn hóa.
  - entity số tiền / SĐT: thực thể theo TỪNG LƯỢT trong ground truth có xuất hiện (sau ITN) trong giả thuyết không.
  - entity BTC          : trích thực thể từ giả thuyết (`extract_hypothesis_entities`) rồi so exact với `entities` cấp hội thoại của
                          ground truth, ĐÚNG như `reference_eval.wer_cer` (giá trị là list → khớp bất kỳ). Luật trích được viết khi đã
                          thấy D01–D04 → số này là TRONG-TẬP.
  - RTF = thời gian nhận dạng / độ dài audio (bỏ lần chạy khởi động); RAM = peak working set của tiến trình; load = thời gian nạp model.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, CODE_DIR)

GT_PATH = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr", "ground_truth.json")
AUDIO_DIR = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr", "audio")
MONEY_KEYS = {"price_vnd", "budget_vnd", "competitor_price_vnd", "min_free_ship_vnd", "bulky_fee_vnd", "exchange_fee_vnd", "promo_vnd"}
SCOPE = "trên audio TTS sạch, giọng Bắc, n = 4 file"
DEV_SET = {"D01", "D02", "D03", "D04"}     # tập phát triển: luật ITN/entity/bảng SKU được viết SAU KHI xem các hội thoại này (config/asr_rules.lock.json)
DEV_NOTE = ("entity BTC / entity số tiền / SĐT trên D01–D04 là **trong tập phát triển (D01–D04), luật viết sau khi xem dữ liệu** — "
            "không phải khả năng khái quát; số trên audio/hội thoại chưa từng thấy được báo riêng ở dòng 'tập chưa thấy'.")


def add_noise(wave, snr_db: float, seed: int, pad_s: float = 1.5):
    """(giữ để tương thích) nhiễu trắng + đệm — tương đương simulate(wave, 'white@snr')."""
    from src.channels.audio_sim import simulate
    return simulate(wave, f"white@{snr_db}", seed, pad_s=pad_s)


# ------------------------------------------------------------------------------------------ worker
def run_worker(args) -> int:
    variant = args.variant or None
    if args.backend == "gipformer" and variant:
        os.environ["ASR_VAD"] = variant
    if args.backend == "whisper" and variant:
        os.environ["ASR_MODEL"] = variant
    os.environ["ASR_NUM_THREADS"] = str(args.threads)
    if args.backend == "whisper":
        import ctranslate2  # noqa: F401  nạp TRƯỚC numpy/torch: tránh lỗi OMP #15 (hai bản libiomp5md.dll) trên Windows
    import numpy as np  # noqa: F401
    import psutil
    from src.channels import offline_asr
    from src.channels.audio_sim import simulate
    from src.channels.audio_vad import load_audio_16k
    if args.backend == "whisper" and args.whisper_device == "cpu":
        offline_asr._force_cpu = True
    proc = psutil.Process()
    rss0 = proc.memory_info().rss                       # sau khi nạp thư viện, TRƯỚC khi nạp model
    t0 = time.perf_counter()
    backend = offline_asr.get_backend(args.backend)
    backend.load()
    if args.backend == "gipformer":
        backend._vad_obj()                              # nạp luôn VAD (Silero thiếu model → lỗi rõ ràng ngay)
    load_s = time.perf_counter() - t0
    rss_loaded = proc.memory_info().rss
    items = json.load(open(args.items, encoding="utf-8"))
    cache: Dict[str, Any] = {}

    def wave_of(path):
        if path not in cache:
            cache[path] = load_audio_16k(path)
        return cache[path]

    def audio_for(it):
        if not it.get("noise"):
            return it["path"] if args.backend == "whisper" else wave_of(it["path"])
        pool = [wave_of(p) for p in it.get("pool", [])]
        return simulate(wave_of(it["path"]), it["noise"], seed=it.get("seed", 1), pool=pool)

    try:                                                 # khởi động (khởi tạo lười của thư viện) — không tính vào RTF
        backend.transcribe_detail(audio_for(items[0]))
    except Exception:
        pass
    results = {}
    for it in items:
        try:
            res = backend.transcribe_detail(audio_for(it))
            results[it["id"]] = {"text": res.text, "decode_s": res.decode_s, "duration_s": res.duration_s,
                                 "speech_s": res.speech_s, "n_words_timed": len(res.words)}
        except Exception as e:                           # ghi lỗi, không làm hỏng cả lượt đo
            results[it["id"]] = {"error": f"{type(e).__name__}: {e}"}
    info = proc.memory_info()
    device = "cpu"
    if args.backend == "whisper":
        device = "/".join(offline_asr._device_and_compute_type())
    vad = getattr(getattr(backend, "_vad", None), "name", None)
    out = {"backend": args.backend, "variant": variant, "vad": vad, "threads": args.threads, "device": device, "load_s": load_s,
           "init_s": getattr(backend, "load_s", None), "ram_peak_mb": getattr(info, "peak_wset", info.rss) / 1e6,
           "ram_before_load_mb": rss0 / 1e6, "ram_after_load_delta_mb": (rss_loaded - rss0) / 1e6,
           "ram_after_decode_delta_mb": (info.rss - rss0) / 1e6, "results": results}
    with open(args.worker_out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return 0


# ------------------------------------------------------------------------------------------ chỉ số
def _edit_distance(a: list, b: list) -> int:
    dp = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, len(b) + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[-1]


def error_counts(ref: str, hyp: str) -> Dict[str, int]:
    return {"w_err": _edit_distance(ref.split(), hyp.split()), "w_n": len(ref.split()),
            "c_err": _edit_distance(list(ref.replace(" ", "")), list(hyp.replace(" ", ""))), "c_n": len(ref.replace(" ", ""))}


def entity_scores(gt: Dict[str, Any], hyp_text: str) -> Dict[str, Any]:
    from src.channels.asr_postprocess import extract_hypothesis_entities, money_values, normalize_transcript
    norm = normalize_transcript(hyp_text).normalized_text
    digits = "".join(ch for ch in norm if ch.isdigit() or ch == " ")
    money, phones = money_values(hyp_text), set(w for w in digits.split() if len(w) == 10 and w.startswith("0"))
    m_ok = m_n = p_ok = p_n = 0
    for turn in gt["turns"]:
        for k, v in turn.get("entities", {}).items():
            if k in MONEY_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                m_n += 1
                m_ok += int(int(v) in money)
            elif k == "phone":
                p_n += 1
                p_ok += int(str(v) in phones)
    hyp_ent = extract_hypothesis_entities(hyp_text, "2026-10-15")
    b_ok = b_n = 0
    wrong = {}
    for k, v in gt.get("entities", {}).items():
        vals = v if isinstance(v, list) else [v]
        ok = int(any(str(hyp_ent.get(k)) == str(x) for x in vals))
        b_n, b_ok = b_n + 1, b_ok + ok
        if not ok:
            wrong[k] = {"gt": v, "hyp": hyp_ent.get(k)}
    return {"money_ok": m_ok, "money_n": m_n, "phone_ok": p_ok, "phone_n": p_n, "btc_ok": b_ok, "btc_n": b_n, "btc_wrong": wrong}


def score_backend(report: Dict[str, Any], items: List[Dict[str, Any]], gts: Dict[str, Any]) -> Dict[str, Any]:
    from src.channels.asr_postprocess import canonical_numbers, wer_normalize
    per = {}
    for it in items:
        r = report["results"].get(it["id"], {})
        if "error" in r or "text" not in r:
            per[it["id"]] = {"error": r.get("error", "không có kết quả"), "attrs": it["attrs"]}
            continue
        gt = gts[it["gt_id"]]
        ref_raw, hyp_raw = wer_normalize(gt["full_text"]), wer_normalize(r["text"])
        ref_itn, hyp_itn = wer_normalize(canonical_numbers(gt["full_text"])), wer_normalize(canonical_numbers(r["text"]))
        per[it["id"]] = {"attrs": it["attrs"], "raw": error_counts(ref_raw, hyp_raw), "itn": error_counts(ref_itn, hyp_itn),
                         "entities": entity_scores(gt, r["text"]), "decode_s": r["decode_s"], "duration_s": r["duration_s"],
                         "n_words": len(r["text"].split()), "hypothesis": r["text"]}
    return per


def pct(a, b):
    return None if not b else round(100.0 * a / b, 1)


def aggregate(per: Dict[str, Any], select) -> Dict[str, Any]:
    rows = [v for k, v in per.items() if "error" not in v and select(v["attrs"])]
    if not rows:
        return {"n": 0}
    agg: Dict[str, Any] = {"n": len(rows)}
    for kind in ("raw", "itn"):
        agg[f"wer_{kind}"] = pct(sum(r[kind]["w_err"] for r in rows), sum(r[kind]["w_n"] for r in rows))
        agg[f"cer_{kind}"] = pct(sum(r[kind]["c_err"] for r in rows), sum(r[kind]["c_n"] for r in rows))
    for key in ("money", "phone", "btc"):
        agg[f"ent_{key}"] = pct(sum(r["entities"][f"{key}_ok"] for r in rows), sum(r["entities"][f"{key}_n"] for r in rows))
        agg[f"ent_{key}_n"] = sum(r["entities"][f"{key}_n"] for r in rows)
    agg["rtf"] = round(sum(r["decode_s"] for r in rows) / max(1e-9, sum(r["duration_s"] for r in rows)), 3)
    agg["audio_s"] = round(sum(r["duration_s"] for r in rows), 1)
    return agg


def fmt(v, suffix="%"):
    return "—" if v is None else f"{v}{suffix}"


def groups_for(items: List[Dict[str, Any]]):
    g = [(f"TTS sạch ({SCOPE}) [tập phát triển]", lambda a: a["source"] == "tts" and not a.get("noise") and a.get("split") == "dev"),
         ("TTS sạch — TẬP CHƯA THẤY (báo riêng)", lambda a: a["source"] == "tts" and not a.get("noise") and a.get("split") == "unseen")]
    for spec in dict.fromkeys(i["noise"] for i in items if i.get("noise")):
        g.append((f"TTS + {spec} (nhiễu tổng hợp) [tập phát triển]", lambda a, s=spec: a.get("noise") == s and a.get("split") == "dev"))
        g.append((f"TTS + {spec} — TẬP CHƯA THẤY (báo riêng)", lambda a, s=spec: a.get("noise") == s and a.get("split") == "unseen"))
    g += [("nhóm tự thu · Nam", lambda a: a["source"] == "real" and a["region"] == "nam"),
          ("nhóm tự thu · Trung", lambda a: a["source"] == "real" and a["region"] == "trung"),
          ("nhóm tự thu · Bắc", lambda a: a["source"] == "real" and a["region"] == "bac"),
          ("nhóm tự thu · có nhiễu thật", lambda a: a["source"] == "real" and a["noisy"]),
          ("nhóm tự thu · không nhiễu", lambda a: a["source"] == "real" and not a["noisy"])]
    return g


def render(reports: Dict[str, Any], scored: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    names = list(reports)
    out = [f"> Mọi số trong báo cáo này: **{SCOPE}** (nguồn tiếng nói D01–D04); nhiễu/kênh điện thoại là **mô phỏng**. "
           "Cần đo lại khi có dataset ≥ 20 file (giọng Nam/Trung, nhiễu thật). **Kết quả VAD chỉ trên nhiễu giả lập — cần kiểm lại trên ghi âm điện thoại thật.**",
           "", "> " + DEV_NOTE, "",
           "## Cấu hình đo", "", "| backend | VAD | thiết bị | số luồng | nạp model (s) | RAM trước nạp (MB) | RAM tăng sau nạp (MB) | RAM tăng sau khi chạy (MB) | RAM peak (MB) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        r = reports[n]
        out.append(f"| {n} | {r.get('vad') or '—'} | {r['device']} | {r['threads']} | {r['load_s']:.2f} | {r['ram_before_load_mb']:.0f} | "
                   f"{r['ram_after_load_delta_mb']:.0f} | {r['ram_after_decode_delta_mb']:.0f} | {r['ram_peak_mb']:.0f} |")
    out += ["", "## Kết quả theo điều kiện (micro-average; n = số file)", ""]
    out += ["| điều kiện | n | audio (s) | backend | WER thô | WER ITN 2 vế | CER thô | entity số tiền | entity SĐT | entity BTC | RTF |", "|" + "---|" * 11]
    groups = groups_for(items)
    for gname, sel in groups:
        for n in names:
            a = aggregate(scored[n], sel)
            if not a["n"]:
                continue
            out.append(f"| {gname} | {a['n']} | {a['audio_s']} | {n} | {fmt(a['wer_raw'])} | {fmt(a['wer_itn'])} | {fmt(a['cer_raw'])} | "
                       f"{fmt(a['ent_money'])} (n={a['ent_money_n']}) | {fmt(a['ent_phone'])} (n={a['ent_phone_n']}) | "
                       f"{fmt(a['ent_btc'])} (n={a['ent_btc_n']}) | {a['rtf']} |")
    missing = [g for g, sel in groups if not any(aggregate(scored[n], sel)["n"] for n in names)]
    if missing:
        out += ["", "Nhóm CHƯA có dữ liệu (không bịa số): " + "; ".join(missing)]
    out += ["", "## Từng file (WER thô)", "", "| file | điều kiện | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for i in list(next(iter(scored.values()))):
        row = [i, next(iter(scored.values()))[i]["attrs"].get("noise") or ("sạch" if next(iter(scored.values()))[i]["attrs"]["source"] == "tts" else "thu thật")]
        for n in names:
            v = scored[n][i]
            row.append(f"LỖI: {v['error']}" if "error" in v else f"{100.0 * v['raw']['w_err'] / v['raw']['w_n']:.1f}% (n_từ={v['n_words']})")
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def build_items(args, gts: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    paths = {}
    for gid in gts:
        for ext in (".wav", ".mp3"):
            p = os.path.join(args.audio_dir, gid + ext)
            if os.path.isfile(p):
                paths[gid] = p
                break
    specs = [s for s in (args.noise or "").split(",") if s.strip()]
    if args.add_noise_snr is not None:
        specs.append(f"white@{args.add_noise_snr:g}")
    from src.channels.audio_sim import parse_spec
    for s in specs:
        parse_spec(s)                                     # báo lỗi cú pháp sớm
    for gid, p in paths.items():
        items.append({"id": gid, "gt_id": gid, "path": p, "noise": None, "attrs": {"source": "tts", "region": "bac", "noisy": False, "noise": None, "split": "dev" if gid in DEV_SET else "unseen"}})
        for si, spec in enumerate(specs):
            items.append({"id": f"{gid}~{spec}", "gt_id": gid, "path": p, "noise": spec, "seed": 11 + si,
                          "pool": [q for k, q in paths.items() if k != gid],
                          "attrs": {"source": "tts", "region": "bac", "noisy": True, "noise": spec, "split": "dev" if gid in DEV_SET else "unseen"}})
    if args.manifest:
        base = os.path.dirname(os.path.abspath(args.manifest))
        for m in json.load(open(args.manifest, encoding="utf-8")):
            if m.get("gt_id") not in gts:
                print(f"[bỏ qua] {m.get('file')}: gt_id không có trong ground_truth.json", file=sys.stderr)
                continue
            path = os.path.join(base, m["file"])
            if not os.path.isfile(path):
                print(f"[bỏ qua] thiếu file {path}", file=sys.stderr)
                continue
            items.append({"id": os.path.splitext(m["file"])[0], "gt_id": m["gt_id"], "path": path, "noise": None,
                          "attrs": {"source": "real", "region": m.get("region", "?"), "noisy": bool(m.get("noisy", False)), "noise": None,
                                "split": "dev" if m["gt_id"] in DEV_SET else "unseen"}})
    return items


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", default=AUDIO_DIR)
    ap.add_argument("--backends", default="gipformer:silero,gipformer:energy,whisper:base",
                    help="danh sách backend[:biến thể], gipformer:<silero|energy> (VAD) hoặc whisper:<base|small|...> (cỡ model)")
    ap.add_argument("--threads", type=int, default=2, help="số luồng CPU cho mỗi backend (mặc định 2, như máy tham chiếu)")
    ap.add_argument("--whisper-device", choices=["cpu", "auto"], default="cpu", help="cpu = so công bằng với gipformer (CPU)")
    ap.add_argument("--noise", default="", help="danh sách công thức nhiễu cách nhau bằng dấu phẩy, vd white@10,phone,phone+babble@10")
    ap.add_argument("--add-noise-snr", type=float, default=None, help="(cũ) thêm nhiễu trắng ở SNR này = --noise white@<snr>")
    ap.add_argument("--manifest", default=None, help="manifest file nhóm tự thu: [{file, gt_id, region, noisy}] cạnh file audio")
    ap.add_argument("--out", default=os.path.join(CODE_DIR, "runs", "asr_compare"))
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--backend", help=argparse.SUPPRESS)
    ap.add_argument("--variant", default="", help=argparse.SUPPRESS)
    ap.add_argument("--items", help=argparse.SUPPRESS)
    ap.add_argument("--worker-out", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        return run_worker(args)

    sys.stdout.reconfigure(encoding="utf-8")
    gts = {d["id"]: d for d in json.load(open(GT_PATH, encoding="utf-8"))["dialogues"]}
    items = build_items(args, gts)
    if not items:
        print("Không có file audio nào để đo (kiểm --audio-dir / --manifest).")
        return 1
    os.makedirs(args.out, exist_ok=True)
    items_path = os.path.join(args.out, "items.json")
    json.dump(items, open(items_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    reports, scored = {}, {}
    for spec in [b.strip() for b in args.backends.split(",") if b.strip()]:
        name, _, variant = spec.partition(":")
        label = f"{name}({variant})" if variant else name
        wout = os.path.join(args.out, f"worker_{label.replace('(', '_').replace(')', '')}.json")
        cmd = [sys.executable, os.path.abspath(__file__), "--worker", "--backend", name, "--variant", variant, "--items", items_path,
               "--worker-out", wout, "--threads", str(args.threads), "--whisper-device", args.whisper_device]
        print(f"[compare_asr] chạy '{label}' trong tiến trình riêng ...", flush=True)
        if os.path.exists(wout):
            os.remove(wout)
        proc = subprocess.run(cmd, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=CODE_DIR)
        if proc.returncode != 0 or not os.path.isfile(wout):
            print(f"[compare_asr] '{label}' thất bại (mã {proc.returncode}) — bỏ qua.")
            continue
        reports[label] = json.load(open(wout, encoding="utf-8"))
        scored[label] = score_backend(reports[label], items, gts)
    if not reports:
        return 1
    text = render(reports, scored, items)
    print("\n" + text)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump({"args": vars(args), "scope": SCOPE, "reports": {k: {kk: vv for kk, vv in v.items() if kk != "results"} for k, v in reports.items()},
                   "scored": scored}, fh, ensure_ascii=False, indent=1)
    print(f"\n-> {os.path.join(args.out, 'report.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
