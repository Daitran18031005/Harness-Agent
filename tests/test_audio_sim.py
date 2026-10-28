"""Giả lập kênh điện thoại + tiếng ồn môi trường (src/channels/audio_sim.py) và chọn VAD (ASR_VAD)."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np

from src.channels import audio_vad
from src.channels.audio_sim import SR, active_power, mix_at_snr, parse_spec, phone_channel, simulate
from src.channels.audio_vad import EnergyVAD, SileroVAD, UnionVAD, default_vad, make_chunks

RNG = np.random.default_rng(3)


def speechlike(seconds=4.0, amp=0.3):
    t = np.arange(int(seconds * SR)) / SR
    carrier = sum(np.sin(2 * np.pi * 130 * k * t) / k for k in range(1, 12)) + 0.5 * np.sin(2 * np.pi * 5000 * t)
    env = np.clip(np.sin(2 * np.pi * 3 * t), 0, None) ** 0.7
    return (amp * carrier * env / 3).astype(np.float32)


def band_power(x, lo, hi):
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return float(spec[(f >= lo) & (f < hi)].sum())


class ParseSpecTest(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_spec("phone+codec+babble@10"), ("babble", 10.0, True, True))
        self.assertEqual(parse_spec("white@-3"), ("white", -3.0, False, False))
        self.assertEqual(parse_spec("phone"), (None, None, True, False))

    def test_invalid(self):
        for bad in ("codec", "white", "rain@5", "phone+@@"):
            with self.assertRaises(ValueError, msg=bad):
                parse_spec(bad)


class ChannelTest(unittest.TestCase):
    def test_phone_removes_high_frequencies(self):
        x = speechlike()
        y = phone_channel(x)
        self.assertEqual(len(y), len(x))
        self.assertLess(band_power(y, 4000, 8000), 1e-3 * band_power(x, 4000, 8000))     # 5 kHz bị loại
        self.assertGreater(band_power(y, 300, 3400), 0.5 * band_power(x, 300, 3400))     # tiếng nói trong băng giữ lại

    def test_codec_adds_quantization_noise_but_keeps_signal(self):
        x = phone_channel(speechlike())
        y = phone_channel(speechlike(), codec=True)
        self.assertEqual(len(x), len(y))
        err = np.mean((x - y) ** 2) / np.mean(x ** 2)
        self.assertGreater(err, 1e-6)          # có biến dạng
        self.assertLess(err, 0.05)             # nhưng vẫn là cùng tín hiệu


class NoiseTest(unittest.TestCase):
    def test_snr_is_respected_relative_to_active_speech(self):
        speech = np.concatenate([np.zeros(SR, np.float32), speechlike(), np.zeros(SR, np.float32)])
        for snr in (0, 10, 20):
            noisy = mix_at_snr(speech, RNG.normal(0, 1, len(speech)).astype(np.float32), snr)
            noise = noisy - speech
            measured = 10 * np.log10(active_power(speech) / np.mean(noise.astype(np.float64) ** 2))
            self.assertAlmostEqual(measured, snr, delta=0.5)

    def test_simulate_pads_noise_only_ends_and_is_deterministic(self):
        speech = speechlike()
        a = simulate(speech, "street@5", seed=4)
        b = simulate(speech, "street@5", seed=4)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(len(a), len(speech) + 2 * int(1.5 * SR))
        self.assertTrue(np.all(np.abs(a) <= 1.0))
        self.assertGreater(np.std(a[: int(1.4 * SR)]), 0)                  # đoạn đệm có tiếng ồn, không phải im lặng số

    def test_each_noise_kind_runs_and_differs(self):
        speech = speechlike(2.0)
        pool = [speechlike(3.0, 0.2), speechlike(3.0, 0.25)]
        outs = {k: simulate(speech, f"phone+{k}@10", seed=1, pool=pool) for k in ("white", "babble", "street", "cafe")}
        keys = list(outs)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                self.assertFalse(np.allclose(outs[keys[i]], outs[keys[j]]), (keys[i], keys[j]))

    def test_noise_only_padding_is_removed_by_vad_for_moderate_snr(self):
        speech = speechlike(5.0)
        chunks = make_chunks(simulate(speech, "white@10", seed=2), EnergyVAD())
        self.assertGreaterEqual(len(chunks), 1)
        self.assertGreater(chunks[0].start_s, 1.0)                         # đầu 1,5 s chỉ có nhiễu bị bỏ


class VadSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_energy_choice_never_needs_model(self):
        with mock.patch.dict(os.environ, {"ASR_VAD": "energy"}):
            self.assertIsInstance(default_vad(self.tmp), EnergyVAD)

    def test_auto_falls_back_to_energy_when_model_missing(self):
        with mock.patch.dict(os.environ, {"ASR_VAD": "auto"}):
            os.environ.pop("ASR_VAD_MODEL", None)
            self.assertIsInstance(default_vad(self.tmp), EnergyVAD)

    def test_silero_requested_but_missing_is_an_error_not_a_silent_fallback(self):
        with mock.patch.dict(os.environ, {"ASR_VAD": "silero"}):
            os.environ.pop("ASR_VAD_MODEL", None)
            with self.assertRaises(FileNotFoundError):
                default_vad(self.tmp)

    def test_invalid_choice(self):
        with self.assertRaises(ValueError):
            default_vad(self.tmp, choice="webrtc")

    def test_auto_is_union_of_silero_and_energy_when_file_present(self):
        with open(os.path.join(self.tmp, "silero_vad.onnx"), "wb") as fh:
            fh.write(b"x")
        vad = default_vad(self.tmp, choice="auto")
        self.assertIsInstance(vad, UnionVAD)
        self.assertEqual(vad.name, "silero+energy")
        self.assertIsInstance(default_vad(self.tmp, choice="silero"), SileroVAD)

    def test_union_merges_overlapping_and_adjacent_ranges(self):
        class Fixed:
            def __init__(self, r, name):
                self.r, self.name = r, name

            def detect(self, wave):
                return self.r
        u = UnionVAD([Fixed([(0, 1000), (50000, 60000)], "a"), Fixed([(500, 2000), (60400, 70000), (200000, 210000)], "b")])
        self.assertEqual(u.detect(None), [(0, 2000), (50000, 70000), (200000, 210000)])


MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "model_ASR"))
SILERO = os.path.join(MODEL_DIR, "silero_vad.onnx")


@unittest.skipUnless(os.path.isfile(SILERO), "chưa có silero_vad.onnx")
class SileroRealTest(unittest.TestCase):
    def test_hash_matches_recorded_value(self):
        from src.channels.offline_asr import sha256_prefix
        self.assertEqual(sha256_prefix(SILERO, len(audio_vad.SILERO_SHA256_PREFIX)), audio_vad.SILERO_SHA256_PREFIX)

    def test_noise_only_gives_no_chunks_and_speech_is_found(self):
        vad = SileroVAD(SILERO)
        self.assertEqual(make_chunks(RNG.normal(0, 0.05, 6 * SR).astype(np.float32), vad), [])
        audio = os.path.join(os.path.dirname(MODEL_DIR), "BTC-Data-Vong1-TEAMS", "asr", "audio", "D03.mp3")
        if os.path.isfile(audio):
            wave = audio_vad.load_audio_16k(audio)
            chunks = make_chunks(simulate(wave, "white@5", seed=1), vad, max_chunk_s=20.0)
            self.assertGreaterEqual(sum(c.duration_s for c in chunks), 0.8 * len(wave) / SR)
            self.assertTrue(all(c.duration_s <= 20.0 + 1e-6 for c in chunks))


if __name__ == "__main__":
    unittest.main()
