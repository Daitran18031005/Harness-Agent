"""Test backend ASR Gipformer: kiểm tra model (sha256), chọn backend, hậu xử lý chữ HOA → ITN → PII, VAD/cắt đoạn,
gán lượt thoại theo mốc thời gian. Các test cần model thật tự bỏ qua khi `model_ASR/` chưa đủ file hợp lệ."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.channels import offline_asr
from src.channels.asr_hypotheses import assign_words_to_turns, build_entry, load_turn_segments
from src.channels.asr_postprocess import (canonical_numbers, extract_hypothesis_entities, money_values,
                                          normalize_transcript, to_lower_vi, wer_normalize)
from src.channels.audio_vad import EnergyVAD, SAMPLE_RATE, frame_energy_db, make_chunks, split_long_ranges
from src.privacy.pii_vault import PiiVault

CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
D01 = os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr", "audio", "D01.mp3")


def _model_ok() -> bool:
    try:
        offline_asr.GipformerASR().verify_files()
        import sherpa_onnx  # noqa: F401
        return True
    except Exception:
        return False


MODEL_OK = _model_ok()
RNG = np.random.default_rng(7)


def speech_like(seconds: float, amp: float = 0.3, floor: float = 0.0) -> np.ndarray:
    """Tín hiệu giống tiếng nói: hài (f0 ~ 130 Hz) điều biên theo âm tiết ~4 Hz, có tạp âm nền thấp."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    carrier = sum(np.sin(2 * np.pi * 130 * k * t) / k for k in range(1, 8))
    envelope = floor + (1 - floor) * np.clip(np.sin(2 * np.pi * 4 * t), 0, None) ** 0.7   # floor>0: nghỉ giữa âm tiết nông hơn khoảng lặng thật
    return (amp * carrier * envelope / 2 + RNG.normal(0, 0.002, len(t))).astype(np.float32)


def silence(seconds: float, noise: float = 0.002) -> np.ndarray:
    return RNG.normal(0, noise, int(seconds * SAMPLE_RATE)).astype(np.float32)


class ModelFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_missing_files_reports_each_one_and_how_to_download(self):
        with open(os.path.join(self.tmp, "tokens.txt"), "w") as fh:
            fh.write("x")
        with self.assertRaises(offline_asr.ASRModelError) as cm:
            offline_asr.GipformerASR(model_dir=self.tmp).load()
        msg = str(cm.exception)
        for name in ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "bpe.model"):
            self.assertIn(name, msg)
        self.assertIn("huggingface-cli download g-group-ai-lab/gipformer1.5-68M-rnnt", msg)

    def test_wrong_hash_is_rejected(self):
        for name in offline_asr.GIPFORMER_FILES:
            with open(os.path.join(self.tmp, name), "wb") as fh:
                fh.write(b"khong phai model that")
        with self.assertRaises(offline_asr.ASRModelError) as cm:
            offline_asr.GipformerASR(model_dir=self.tmp).verify_files()
        self.assertIn("SAI SHA-256", str(cm.exception))

    @unittest.skipUnless(MODEL_OK, "chưa có model_ASR hợp lệ")
    def test_real_model_files_pass_verification(self):
        offline_asr.GipformerASR().verify_files()                 # 5 hash khớp giá trị nhóm đã ghi


class BackendSelectionTest(unittest.TestCase):
    def setUp(self):
        offline_asr._BACKENDS.clear()
        self.addCleanup(offline_asr._BACKENDS.clear)

    def test_default_backend_is_gipformer_and_whisper_stays_selectable(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ASR_BACKEND", None)
            self.assertEqual(offline_asr._backend_name(), "gipformer")
            self.assertIsInstance(offline_asr.get_backend(), offline_asr.GipformerASR)
        with mock.patch.dict(os.environ, {"ASR_BACKEND": "whisper"}):
            self.assertIsInstance(offline_asr.get_backend(), offline_asr.WhisperASR)

    def test_gipformer_selected_by_env(self):
        with mock.patch.dict(os.environ, {"ASR_BACKEND": "gipformer"}):
            self.assertIsInstance(offline_asr.get_backend(), offline_asr.GipformerASR)

    def test_unknown_backend_raises_in_get_backend_but_not_in_transcribe_audio(self):
        with mock.patch.dict(os.environ, {"ASR_BACKEND": "khong-co"}):
            with self.assertRaises(ValueError):
                offline_asr.get_backend()
            self.assertEqual(offline_asr.transcribe_audio(D01), "")   # không bao giờ raise

    def test_explicit_gipformer_with_missing_model_gives_empty_transcript_not_crash_and_no_silent_switch(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.dict(os.environ, {"ASR_BACKEND": "gipformer", "GIPFORMER_MODEL_DIR": tmp}), \
                mock.patch.object(offline_asr, "_transcribe_whisper", return_value="whisper nói") as wh:
            self.assertEqual(offline_asr.transcribe_audio(D01), "")
            self.assertFalse(offline_asr.is_available())
            wh.assert_not_called()                                     # người dùng chọn rõ → không đổi ngầm sang whisper

    def test_unset_backend_with_missing_model_falls_back_to_whisper(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.dict(os.environ, {"GIPFORMER_MODEL_DIR": tmp}), \
                mock.patch.object(offline_asr, "_transcribe_whisper", return_value="whisper nói") as wh, \
                mock.patch.object(offline_asr, "_whisper_available", return_value=True):
            os.environ.pop("ASR_BACKEND", None)
            self.assertEqual(offline_asr.transcribe_audio(D01), "whisper nói")
            wh.assert_called_once()
            self.assertTrue(offline_asr.is_available())

    def test_explicit_silero_without_model_is_a_clear_error_not_silent_energy(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        asr = offline_asr.GipformerASR(model_dir=tmp)
        with mock.patch.dict(os.environ, {"ASR_VAD": "silero"}):
            os.environ.pop("ASR_VAD_MODEL", None)
            with self.assertRaises(offline_asr.ASRModelError):
                asr._vad_obj()


class PostprocessTest(unittest.TestCase):
    """Đầu ra Gipformer là CHỮ HOA, không chữ số → chữ thường → ITN của bước 7."""

    def _amounts(self, text):
        return money_values(text)

    def test_lowercase_keeps_vietnamese_diacritics(self):
        self.assertEqual(to_lower_vi("  DẠ  EM  CHÀO  CHỊ "), "dạ em chào chị")

    def test_money_in_uppercase(self):
        self.assertEqual(normalize_transcript("BỐN TRIỆU TÁM TRĂM CHÍN MƯƠI NGHÌN").normalized_text, "4.890.000")
        self.assertEqual(self._amounts("BỐN TRIỆU TÁM TRĂM CHÍN MƯƠI NGHÌN"), {4890000})

    def test_k_suffix_in_uppercase(self):
        self.assertEqual(self._amounts("NĂM TRĂM K"), {500000})
        self.assertEqual(self._amounts("GIẢM NĂM TRĂM K THÔI EM"), {500000})

    def test_phone_digits_in_uppercase_become_10_digit_number(self):
        turn = normalize_transcript("SỐ NÀY KHÔNG CHÍN TÁM HAI BA BỐN NĂM SÁU BẢY TÁM NHÉ")
        self.assertIn("0982345678", turn.normalized_text)
        self.assertEqual(extract_hypothesis_entities("KHÔNG CHÍN TÁM HAI BA BỐN NĂM SÁU BẢY TÁM")["phone"], "0982345678")

    def test_phone_is_masked_by_pii_vault_after_itn(self):
        vault = PiiVault()
        turn = normalize_transcript("SỐ ĐIỆN THOẠI LÀ KHÔNG CHÍN TÁM HAI BA BỐN NĂM SÁU BẢY TÁM")
        masked = vault.mask_text(turn.normalized_text, caller_phone="0900000001")
        self.assertNotIn("0982345678", masked)
        self.assertRegex(masked, r"<PHONE_\d+>")

    def test_room_area_and_delivery_entities(self):
        ent = extract_hypothesis_entities("PHÒNG CHỊ KHOẢNG HAI MƯƠI LĂM MÉT VUÔNG")
        self.assertEqual(ent.get("room_area_m2"), 25)           # int, không phải 25.0 (BTC so sánh chuỗi)

    def test_price_role_from_context(self):
        ent = extract_hypothesis_entities("DẠ MẪU Y GIÁ NĂM TRIỆU HAI TRĂM NGHÌN Ạ")
        self.assertEqual(ent.get("price_vnd"), 5200000)

    def test_spoken_order_id(self):
        ent = extract_hypothesis_entities("MÃ ĐƠN CỦA CHỊ LÀ Ô ĐÊ BA MỘT HAI BỐN NĂM SÁU")
        self.assertEqual(ent.get("order_id"), "OD312456")

    def test_canonical_numbers_unifies_digits_and_words(self):
        self.assertEqual(canonical_numbers("giá năm triệu hai trăm nghìn"), canonical_numbers("giá 5.200.000"))
        self.assertEqual(canonical_numbers("giá 5,200,000 đồng"), "giá 5200000 đồng")

    def test_wer_normalize_matches_btc_rule(self):
        self.assertEqual(wer_normalize("Dạ, giá là 5.000.000đ!"), "dạ giá là 5 000 000đ")


class VadTest(unittest.TestCase):
    def test_white_noise_only_gives_no_chunks(self):
        for sigma in (0.003, 0.02, 0.1):                        # từ rất nhỏ đến rất to
            wave = RNG.normal(0, sigma, 8 * SAMPLE_RATE).astype(np.float32)
            self.assertEqual(make_chunks(wave, EnergyVAD()), [], f"sigma={sigma}")

    def test_slowly_fluctuating_noise_gives_no_chunks(self):
        walk = np.cumsum(RNG.normal(0, 0.02, 8 * 50))           # biên độ nền dao động nhẹ (±vài dB)
        gain = np.repeat(0.03 * np.exp(np.clip(walk, -0.4, 0.4)), SAMPLE_RATE // 50)
        wave = (RNG.normal(0, 1, len(gain)) * gain).astype(np.float32)
        self.assertEqual(make_chunks(wave, EnergyVAD()), [])

    def test_digital_silence_and_empty_audio(self):
        self.assertEqual(make_chunks(np.zeros(5 * SAMPLE_RATE, dtype=np.float32), EnergyVAD()), [])
        self.assertEqual(make_chunks(np.zeros(0, dtype=np.float32), EnergyVAD()), [])

    def test_speech_between_silences_is_found_with_margins(self):
        wave = np.concatenate([silence(2.0), speech_like(3.0), silence(2.0)])
        chunks = make_chunks(wave, EnergyVAD())
        self.assertEqual(len(chunks), 1)
        self.assertGreater(chunks[0].start_s, 1.5)
        self.assertLess(chunks[0].end_s, 5.7)
        self.assertGreater(chunks[0].duration_s, 2.8)

    def test_speech_buried_in_loud_noise_is_still_found(self):
        noise = RNG.normal(0, 0.03, 10 * SAMPLE_RATE).astype(np.float32)
        wave = noise.copy()
        wave[3 * SAMPLE_RATE: 6 * SAMPLE_RATE] += speech_like(3.0, amp=0.9)
        chunks = make_chunks(wave, EnergyVAD())
        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(all(2.5 < c.start_s < 6.5 for c in chunks))

    def test_long_audio_is_split_into_chunks_of_at_most_max_len(self):
        parts = []
        for _ in range(10):                                      # 10 × (7 s nói + 0.5 s nghỉ) ≈ 75 s liền mạch
            parts += [speech_like(7.0), silence(0.5)]
        wave = np.concatenate(parts)
        chunks = make_chunks(wave, EnergyVAD(min_silence_s=2.0), max_chunk_s=25.0)   # ép coi như một đoạn dài
        self.assertGreater(len(chunks), 2)
        self.assertTrue(all(c.duration_s <= 25.0 + 1e-6 for c in chunks))
        self.assertAlmostEqual(sum(c.duration_s for c in chunks), 75.0, delta=3.0)   # không mất tiếng nói

    def test_split_cuts_at_lowest_energy_point(self):
        wave = np.concatenate([speech_like(9.0, floor=0.3), silence(0.4), speech_like(9.0, floor=0.3)])
        db = frame_energy_db(wave, 320)
        out = split_long_ranges([(0, len(wave))], db, 320, max_len_s=10.0, search_s=3.0)
        self.assertEqual(len(out), 2)
        cut_s = out[0][1] / SAMPLE_RATE
        self.assertTrue(8.9 <= cut_s <= 9.5, cut_s)              # cắt trong khoảng nghỉ, không cắt ngang tiếng nói


class TurnAssignmentTest(unittest.TestCase):
    SEGS = [{"idx": 1, "speaker": "A", "start": 0.0, "end": 3.0},
            {"idx": 2, "speaker": "C", "start": 3.2, "end": 6.0}]
    WORDS = [("dạ", 0.1, 0.4), ("chào", 0.5, 0.9), ("alo", 3.3, 3.6), ("chị", 3.7, 4.0), ("muốn", 4.1, 4.4)]

    def test_words_go_to_turn_containing_them(self):
        turns = assign_words_to_turns(self.WORDS, self.SEGS)
        self.assertEqual([t["idx"] for t in turns], [1, 2])
        self.assertEqual(turns[0]["text"], "dạ chào")
        self.assertEqual(turns[1]["text"], "alo chị muốn")
        self.assertEqual([t["speaker"] for t in turns], ["A", "C"])

    def test_word_far_from_any_turn_is_dropped(self):
        turns = assign_words_to_turns(self.WORDS + [("ồn", 20.0, 20.2)], self.SEGS)
        self.assertNotIn("ồn", " ".join(t["text"] for t in turns))

    def test_no_segments_file_means_no_turns(self):
        res = offline_asr.ASRResult(text="dạ chào", words=self.WORDS, backend="gipformer")
        entry, notes = build_entry(res, audio_path=None)
        self.assertNotIn("turns", entry)
        self.assertTrue(any("không xuất turns" in n for n in notes))

    def test_backend_without_word_times_means_no_turns(self):
        res = offline_asr.ASRResult(text="dạ chào", words=[], backend="whisper")
        entry, notes = build_entry(res, segments=self.SEGS)
        self.assertNotIn("turns", entry)
        self.assertTrue(any("không có mốc thời gian theo từ" in n for n in notes))

    def test_turns_exported_with_idx_when_metadata_exists(self):
        res = offline_asr.ASRResult(text="dạ chào alo chị muốn", words=self.WORDS, backend="gipformer")
        entry, _ = build_entry(res, segments=self.SEGS)
        self.assertEqual([t["idx"] for t in entry["turns"]], [1, 2])
        self.assertEqual(set(entry["turns"][0]), {"idx", "speaker", "start", "end", "text", "entities"})

    def test_load_segments_file_next_to_audio(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        audio = os.path.join(tmp, "D99.wav")
        self.assertIsNone(load_turn_segments(audio))
        with open(os.path.join(tmp, "D99.segments.json"), "w", encoding="utf-8") as fh:
            json.dump({"id": "D99", "segments": self.SEGS}, fh)
        self.assertEqual([s["idx"] for s in load_turn_segments(audio)], [1, 2])
        with open(os.path.join(tmp, "D99.segments.json"), "w", encoding="utf-8") as fh:
            json.dump({"segments": [{"speaker": "A", "start": 0, "end": 1}]}, fh)          # thiếu idx
        self.assertIsNone(load_turn_segments(audio))


@unittest.skipUnless(MODEL_OK, "chưa có model_ASR hợp lệ / sherpa-onnx")
class GipformerRealModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asr = offline_asr.GipformerASR(num_threads=2)
        cls.asr.load()

    def test_noise_only_audio_gives_empty_transcript(self):
        for sigma in (0.01, 0.05):
            wave = RNG.normal(0, sigma, 6 * SAMPLE_RATE).astype(np.float32)
            res = self.asr.transcribe_detail(wave)
            self.assertEqual(res.text, "", f"sigma={sigma}")
            self.assertEqual(res.words, [])

    @unittest.skipUnless(os.path.isfile(D01), "thiếu D01.mp3")
    def test_known_dialogue_is_lowercase_with_word_times(self):
        res = self.asr.transcribe_detail(D01)
        self.assertEqual(res.text, res.text.lower())
        self.assertIn("hai mươi lăm mét vuông", res.text)
        self.assertIn("năm triệu hai trăm nghìn", res.text)
        starts = [w[1] for w in res.words]
        self.assertEqual(starts, sorted(starts))
        self.assertGreater(len(res.words), 50)
        self.assertLess(res.rtf, 0.5)
        self.assertIn(5200000, money_values(res.text))           # ITN từ chữ → số tiền

    @unittest.skipUnless(os.path.isfile(D01), "thiếu D01.mp3")
    def test_turn_plumbing_with_real_word_timestamps(self):
        """Kiểm ĐƯỜNG ỐNG gán lượt (không phải tách người nói): D01 là một giọng đọc liền cả hội thoại, nên mốc lượt được
        dựng tạm từ số từ của ground truth × mốc từ do model trả. Chỉ dùng trong test; công cụ xuất KHÔNG làm vậy."""
        gt = json.load(open(os.path.join(CODE_DIR, "BTC-Data-Vong1-TEAMS", "asr", "ground_truth.json"), encoding="utf-8"))
        d01 = next(d for d in gt["dialogues"] if d["id"] == "D01")
        res = self.asr.transcribe_detail(D01)
        words, segs, pos = res.words, [], 0
        for t in d01["turns"]:
            n = len(wer_normalize(t["text"]).split())
            chunk = words[pos: pos + n]
            segs.append({"idx": t["idx"], "speaker": t["speaker"], "start": chunk[0][1], "end": chunk[-1][2]})
            pos += n
        entry, _ = build_entry(res, segments=segs, call_date="2026-10-15")
        self.assertEqual([t["idx"] for t in entry["turns"]], [t["idx"] for t in d01["turns"]])
        by_idx = {t["idx"]: t for t in entry["turns"]}
        self.assertEqual(by_idx[5]["entities"].get("price_vnd"), 5200000)     # lượt 5: "giá năm triệu hai trăm nghìn"
        self.assertEqual(by_idx[2]["entities"].get("room_area_m2"), 25)
        self.assertEqual(by_idx[4]["entities"].get("budget_vnd"), 5000000)
        joined = " ".join(t["text"] for t in entry["turns"])
        self.assertGreater(len(joined.split()), 0.9 * len(res.text.split()))   # gần như không mất từ

    @unittest.skipUnless(os.path.isfile(D01), "thiếu D01.mp3")
    def test_noise_padding_does_not_add_words(self):
        from src.channels.audio_vad import load_audio_16k
        speech = load_audio_16k(D01)
        padded = np.concatenate([RNG.normal(0, 0.01, 3 * SAMPLE_RATE).astype(np.float32), speech,
                                 RNG.normal(0, 0.01, 3 * SAMPLE_RATE).astype(np.float32)])
        a, b = self.asr.transcribe_detail(speech).text, self.asr.transcribe_detail(padded).text
        self.assertLessEqual(abs(len(a.split()) - len(b.split())), 6)


if __name__ == "__main__":
    unittest.main()
