"""
Giả lập điều kiện thu âm thực tế để thử ASR/VAD (CHỈ DÙNG ĐỂ ĐO — nhiễu TỔNG HỢP, không thay thế ghi âm thật).

Công thức mô tả bằng chuỗi, ví dụ `phone+codec+babble@10`:
  - tiếng ồn (đặt SNR sau dấu @, dB, đo so với công suất của đoạn CÓ tiếng nói):
      white    nhiễu Gaussian trắng
      babble   tạp âm nhiều người nói: trộn 5 đoạn lời nói của hội thoại KHÁC, đảo ngược thời gian (không nghe ra chữ) và so le
      street   tiếng đường phố: nhiễu nâu (rất nhiều bass) + vài lần xe chạy qua (điều biên chậm) + còi xe
      cafe     tiếng quán: babble + tiếng lách cách (xung ngắn tắt dần)
  - kênh điện thoại:
      phone    băng thông 300–3400 Hz, hạ xuống 8 kHz rồi nâng lại 16 kHz
      codec    nén G.711 µ-law 8-bit (lượng tử hóa phi tuyến) ở 8 kHz — đi kèm `phone`
Thứ tự áp dụng: trộn tiếng ồn (ở phía người gọi) → kênh điện thoại (băng thông + codec) — giống đường đi thật của cuộc gọi.
Hai đầu được đệm `pad_s` giây CHỈ CÓ tiếng ồn để thử VAD.
"""
import re
from typing import List, Optional, Tuple

import numpy as np

SR = 16000
NOISE_KINDS = ("white", "babble", "street", "cafe")


def parse_spec(spec: str) -> Tuple[Optional[str], Optional[float], bool, bool]:
    """'phone+codec+babble@10' → (noise_kind, snr_db, phone, codec). Ném ValueError nếu cú pháp sai."""
    noise, snr, phone, codec = None, None, False, False
    for tok in [t.strip().lower() for t in spec.split("+") if t.strip()]:
        m = re.fullmatch(r"([a-z]+)(?:@(-?\d+(?:\.\d+)?))?", tok)
        if not m:
            raise ValueError(f"cú pháp nhiễu sai: '{tok}' (vd: white@10, phone, phone+codec+babble@10)")
        name, val = m.group(1), m.group(2)
        if name == "phone":
            phone = True
        elif name == "codec":
            codec = True
        elif name in NOISE_KINDS:
            if val is None:
                raise ValueError(f"'{name}' cần SNR, vd {name}@10")
            noise, snr = name, float(val)
        else:
            raise ValueError(f"không biết loại '{name}' (white|babble|street|cafe|phone|codec)")
    if codec and not phone:
        raise ValueError("`codec` phải đi cùng `phone`")
    return noise, snr, phone, codec


def active_power(wave: np.ndarray, frame: int = 320) -> float:
    """Công suất trung bình của các khung CÓ tiếng nói (khung năng lượng trong 20 dB dưới đỉnh); bỏ qua khoảng lặng."""
    n = len(wave) // frame
    if n == 0:
        return float(np.mean(wave.astype(np.float64) ** 2) + 1e-12)
    p = np.mean(wave[: n * frame].reshape(n, frame).astype(np.float64) ** 2, axis=1)
    hot = p > p.max() * 0.01
    return float(p[hot].mean() + 1e-12)


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    noise = noise[: len(speech)] if len(noise) >= len(speech) else np.resize(noise, len(speech))
    scale = np.sqrt(active_power(speech) / (10 ** (snr_db / 10)) / (float(np.mean(noise.astype(np.float64) ** 2)) + 1e-12))
    return speech + (noise * scale).astype(np.float32)


def _lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec[freqs > cutoff_hz] = 0
    return np.fft.irfft(spec, len(x))


def white_noise(n: int, rng) -> np.ndarray:
    return rng.normal(0, 1, n).astype(np.float32)


def street_noise(n: int, rng) -> np.ndarray:
    brown = np.cumsum(rng.normal(0, 1, n))
    brown -= np.convolve(brown, np.ones(4000) / 4000, mode="same")           # bỏ trôi rất chậm, giữ nhiều bass
    out = brown / (np.std(brown) + 1e-9)
    t = np.arange(n) / SR
    for _ in range(max(2, int(n / SR / 4))):                                  # xe chạy qua: cụm nhiễu thấp điều biên hình chuông
        c, w = rng.uniform(0, n / SR), rng.uniform(1.0, 2.5)
        swell = np.exp(-((t - c) / w) ** 2)
        out += 2.5 * swell * _lowpass(rng.normal(0, 1, n), 900)
    for _ in range(max(1, int(n / SR / 8))):                                  # còi xe
        s = rng.uniform(0, max(0.1, n / SR - 0.6))
        seg = (t >= s) & (t < s + 0.5)
        out[seg] += 1.2 * (np.sin(2 * np.pi * 420 * t[seg]) + np.sin(2 * np.pi * 530 * t[seg]))
    return out.astype(np.float32)


def babble_noise(n: int, rng, pool: List[np.ndarray]) -> np.ndarray:
    """Trộn 5 đoạn lời nói khác (đảo ngược thời gian, so le) → tạp âm giống quán đông/văn phòng, không nghe ra chữ."""
    if not pool:
        return white_noise(n, rng)
    out = np.zeros(n, dtype=np.float64)
    for k in range(5):
        src = pool[int(rng.integers(0, len(pool)))][::-1]
        off = int(rng.integers(0, max(1, len(src))))
        seg = np.resize(np.roll(src, off), n)
        out += seg * rng.uniform(0.5, 1.0)
    return (out / (np.std(out) + 1e-9)).astype(np.float32)


def cafe_noise(n: int, rng, pool: List[np.ndarray]) -> np.ndarray:
    out = babble_noise(n, rng, pool).astype(np.float64)
    t = np.arange(int(0.12 * SR)) / SR
    for _ in range(max(2, int(n / SR / 3))):                                  # lách cách thìa/ly: xung cao tần tắt rất nhanh
        pos = int(rng.integers(0, max(1, n - len(t))))
        out[pos: pos + len(t)] += 2.0 * np.sin(2 * np.pi * rng.uniform(2500, 5000) * t) * np.exp(-t * 60)
    return out.astype(np.float32)


def phone_channel(wave: np.ndarray, codec: bool = False) -> np.ndarray:
    """Băng thông điện thoại: lọc 300–3400 Hz, hạ 8 kHz (và nén µ-law 8-bit nếu `codec`), rồi nâng lại 16 kHz."""
    from scipy.signal import resample_poly
    spec = np.fft.rfft(wave.astype(np.float64))
    freqs = np.fft.rfftfreq(len(wave), 1 / SR)
    spec[(freqs < 300) | (freqs > 3400)] = 0
    band = np.fft.irfft(spec, len(wave))
    down = resample_poly(band, 1, 2)
    if codec:
        mu = 255.0
        x = np.clip(down / (np.max(np.abs(down)) + 1e-9), -1, 1)
        comp = np.sign(x) * np.log1p(mu * np.abs(x)) / np.log1p(mu)
        q = np.round((comp + 1) / 2 * 255) / 255 * 2 - 1                     # 8 bit
        down = np.sign(q) * ((1 + mu) ** np.abs(q) - 1) / mu * (np.max(np.abs(down)) + 1e-9)
    up = resample_poly(down, 2, 1)
    up = up[: len(wave)] if len(up) >= len(wave) else np.pad(up, (0, len(wave) - len(up)))
    return up.astype(np.float32)


def simulate(wave: np.ndarray, spec: str, seed: int = 1, pool: Optional[List[np.ndarray]] = None, pad_s: float = 1.5) -> np.ndarray:
    """Áp công thức `spec` lên `wave` (float32 mono 16 kHz). `pool`: các lời nói khác cho babble/cafe."""
    noise_kind, snr, phone, codec = parse_spec(spec)
    rng = np.random.default_rng(seed)
    pad = np.zeros(int(pad_s * SR), np.float32)
    x = np.concatenate([pad, wave.astype(np.float32), pad])
    if noise_kind:
        n = len(x)
        noise = {"white": lambda: white_noise(n, rng), "street": lambda: street_noise(n, rng),
                 "babble": lambda: babble_noise(n, rng, pool or []), "cafe": lambda: cafe_noise(n, rng, pool or [])}[noise_kind]()
        x = mix_at_snr(x, noise, snr)
    if phone:
        x = phone_channel(x, codec)
    return np.clip(x, -1.0, 1.0).astype(np.float32)
