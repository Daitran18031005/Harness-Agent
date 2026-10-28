"""
Dev/test helper (KHÔNG thuộc src/ — không phải pipeline sản xuất): sinh audio thử tiếng
Việt cho 4 hội thoại ground truth D01-D04 bằng TTS, để tự kiểm thử eval_asr.py ngay bây
giờ khi BTC-Data-Vong1-TEAMS/asr/ chưa có file âm thanh thật (BTC chỉ phát audio ngày chấm).

Thứ tự ưu tiên: edge-tts (online, giọng vi-VN-HoaiMyNeural, chất lượng tốt) -> gTTS (online,
Google, dự phòng). Không có giọng tiếng Việt SAPI offline nào trên Windows ở máy build này
(đã kiểm tra) nên không có lựa chọn offline thật — nếu cả hai lỗi (không có mạng), báo rõ và
KHÔNG tạo file; eval_asr.py khi đó tự báo "chưa có audio" cho từng hội thoại, không crash.

Ghi ra đúng BTC-Data-Vong1-TEAMS/asr/audio/{id}.wav|mp3 — cùng tên BTC sẽ dùng, nên khi có
file thật chỉ cần thay file, không cần đổi code.
"""
import os
import sys
import json
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("generate_test_audio")

HERE = os.path.dirname(os.path.abspath(__file__))
GT_PATH = os.path.join(HERE, "..", "BTC-Data-Vong1-TEAMS", "asr", "ground_truth.json")
AUDIO_DIR = os.path.join(HERE, "..", "BTC-Data-Vong1-TEAMS", "asr", "audio")

EDGE_VOICE = "vi-VN-HoaiMyNeural"


async def _try_edge_tts(text: str, out_path: str) -> bool:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        await communicate.save(out_path)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        logger.warning("[TTS] edge-tts thất bại (%s) — thử gTTS.", e)
        return False


def _try_gtts(text: str, out_path: str) -> bool:
    try:
        from gtts import gTTS
        gTTS(text=text, lang="vi").save(out_path)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception as e:
        logger.warning("[TTS] gTTS cũng thất bại (%s) — không có mạng? Bỏ qua, không tạo file.", e)
        return False


async def main():
    if not os.path.exists(GT_PATH):
        print(f"[TTS] Không tìm thấy {GT_PATH}")
        sys.exit(1)

    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt = json.load(f)

    os.makedirs(AUDIO_DIR, exist_ok=True)
    created = []
    for d in gt["dialogues"]:
        did = d["id"]
        text = d["full_text"]
        mp3_path = os.path.join(AUDIO_DIR, f"{did}.mp3")
        if os.path.exists(mp3_path) or os.path.exists(os.path.join(AUDIO_DIR, f"{did}.wav")):
            print(f"[{did}] đã có file audio — bỏ qua (không ghi đè file BTC/đã tạo trước).")
            continue

        ok = await _try_edge_tts(text, mp3_path)
        if not ok:
            ok = _try_gtts(text, mp3_path)
        if ok:
            print(f"[{did}] đã sinh {mp3_path}")
            created.append(did)
        else:
            print(f"[{did}] KHÔNG sinh được audio (hết lựa chọn TTS, có thể do không có mạng).")

    if not created:
        print("\n[TTS] Không tạo được audio nào — eval_asr.py sẽ báo 'chưa có audio' cho các hội thoại, không lỗi.")
    else:
        print(f"\n[TTS] Đã sinh {len(created)} file audio thử: {created}")


if __name__ == "__main__":
    asyncio.run(main())
