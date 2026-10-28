"""
Nạp audio + VAD (phát hiện tiếng nói) + cắt đoạn cho ASR.

Vì sao cần: Gipformer (RNN-T) luôn in ra chữ kể cả khi đầu vào chỉ là tiếng ồn/khoảng lặng → phải bỏ đoạn không có
tiếng nói TRƯỚC khi đưa vào model, và cắt audio dài thành đoạn ≤ `max_chunk_s` (mặc định 25 giây) tại chỗ năng lượng
thấp nhất để không cắt ngang từ.

Hai bộ VAD (cùng giao diện `detect(wave) -> [(start_sample, end_sample)]`) và `UnionVAD` (hợp của hai bộ, mặc định):
  - `EnergyVAD`  : theo năng lượng khung 20 ms, ngưỡng tự thích nghi theo nền ồn của chính file, KHÔNG cần tải model.
  - `SileroVAD`  : silero qua sherpa-onnx; cần file `silero_vad.onnx` (tải riêng, xem README). Không có file → dùng EnergyVAD.
`default_vad()` (`ASR_VAD=auto`) dùng hợp Silero+năng lượng nếu tìm thấy model Silero, ngược lại EnergyVAD.
"""
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

SAMPLE_RATE = 16000


# --------------------------------------------------------------------------------------------- nạp audio
def load_audio_16k(path: str) -> np.ndarray:
    """Đọc .wav/.mp3/... → float32 mono 16 kHz, giá trị trong [-1, 1]. Dùng PyAV (đã có trong requirements)."""
    import av
    container = av.open(path)
    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        parts: List[np.ndarray] = []
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                parts.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            parts.append(out.to_ndarray().reshape(-1))
    finally:
        container.close()
    if not parts:
        return np.zeros(0, dtype=np.float32)
    return np.clip(np.concatenate(parts).astype(np.float32), -1.0, 1.0)


@dataclass
class Chunk:
    start_s: float
    end_s: float
    samples: np.ndarray

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


# --------------------------------------------------------------------------------------------- năng lượng
def frame_energy_db(wave: np.ndarray, frame: int = 320) -> np.ndarray:
    """Năng lượng (dB tương đối full-scale) theo khung `frame` mẫu (mặc định 20 ms)."""
    n = len(wave) // frame
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    x = wave[: n * frame].reshape(n, frame).astype(np.float64)
    return (10.0 * np.log10(np.mean(x * x, axis=1) + 1e-10)).astype(np.float32)


def _smooth(db: np.ndarray, k: int = 5) -> np.ndarray:
    if len(db) < k:
        return db
    pad = k // 2
    padded = np.pad(db, (pad, pad), mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(padded, k), axis=1)


class EnergyVAD:
    """VAD theo năng lượng với ngưỡng thích nghi.

    Ý tưởng: tiếng nói có độ lệch năng lượng lớn giữa âm tiết và khoảng nghỉ (> ~15 dB), còn tiếng ồn nền dừng (stationary)
    thì năng lượng gần như phẳng. Nên:
      1. ước lượng nền = phân vị 10%, đỉnh = phân vị 95% của năng lượng khung đã làm mượt;
      2. nếu đỉnh − nền < `min_dynamic_db` hoặc đỉnh < `min_peak_db` → KHÔNG có tiếng nói (chỉ ồn/lặng);
      3. còn lại, khung là tiếng nói khi năng lượng > nền + max(`margin_db`, 35% × (đỉnh − nền));
      4. nối các đoạn cách nhau < `min_silence_s`, bỏ đoạn ngắn hơn `min_speech_s`, đệm `pad_s` hai đầu.
    """

    def __init__(self, frame: int = 320, min_dynamic_db: float = 9.0, min_peak_db: float = -55.0,
                 margin_db: float = 6.0, min_silence_s: float = 0.35, min_speech_s: float = 0.2, pad_s: float = 0.15):
        self.frame, self.min_dynamic_db, self.min_peak_db = frame, min_dynamic_db, min_peak_db
        self.margin_db, self.min_silence_s, self.min_speech_s, self.pad_s = margin_db, min_silence_s, min_speech_s, pad_s

    name = "energy"

    def detect(self, wave: np.ndarray) -> List[Tuple[int, int]]:
        db = _smooth(frame_energy_db(wave, self.frame))
        if len(db) == 0:
            return []
        floor, peak = float(np.percentile(db, 10)), float(np.percentile(db, 95))
        if peak < self.min_peak_db or (peak - floor) < self.min_dynamic_db:
            return []
        thr = floor + max(self.margin_db, 0.35 * (peak - floor))
        speech = db > thr
        fps = SAMPLE_RATE / self.frame
        runs: List[List[int]] = []
        start: Optional[int] = None
        for i, s in enumerate(speech):
            if s and start is None:
                start = i
            elif not s and start is not None:
                runs.append([start, i])
                start = None
        if start is not None:
            runs.append([start, len(speech)])
        merged: List[List[int]] = []
        for r in runs:
            if merged and (r[0] - merged[-1][1]) / fps < self.min_silence_s:
                merged[-1][1] = r[1]
            else:
                merged.append(r)
        pad = int(self.pad_s * fps)
        out: List[Tuple[int, int]] = []
        for a, b in merged:
            if (b - a) / fps < self.min_speech_s:
                continue
            a, b = max(0, a - pad), min(len(speech), b + pad)
            out.append((a * self.frame, min(len(wave), b * self.frame)))
        return out


class SileroVAD:
    """Silero VAD qua sherpa-onnx. Cần file `silero_vad.onnx` (không đi kèm; xem README § ASR)."""
    name = "silero"

    def __init__(self, model_path: str, threshold: float = 0.5, min_silence_s: float = 0.35, min_speech_s: float = 0.2,
                 max_speech_s: float = 25.0):
        if not os.path.isfile(model_path):
            raise FileNotFoundError(f"Không có model Silero VAD: {model_path}")
        self.model_path, self.threshold = model_path, threshold
        self.min_silence_s, self.min_speech_s, self.max_speech_s = min_silence_s, min_speech_s, max_speech_s

    def detect(self, wave: np.ndarray) -> List[Tuple[int, int]]:
        import sherpa_onnx
        cfg = sherpa_onnx.VadModelConfig()
        cfg.silero_vad.model = self.model_path
        cfg.silero_vad.threshold = self.threshold
        cfg.silero_vad.min_silence_duration = self.min_silence_s
        cfg.silero_vad.min_speech_duration = self.min_speech_s
        cfg.silero_vad.max_speech_duration = self.max_speech_s
        cfg.silero_vad.window_size = 512
        cfg.sample_rate = SAMPLE_RATE
        vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=max(30, int(len(wave) / SAMPLE_RATE) + 5))
        win = cfg.silero_vad.window_size
        for i in range(0, len(wave), win):
            vad.accept_waveform(wave[i: i + win])
        vad.flush()
        out: List[Tuple[int, int]] = []
        while not vad.empty():
            seg = vad.front
            out.append((int(seg.start), int(seg.start) + len(seg.samples)))
            vad.pop()
        return out


class UnionVAD:
    """Hợp các đoạn của nhiều VAD (nối đoạn cách nhau < `merge_gap_s`). Dùng cho `ASR_VAD=auto`: Silero bắt được tiếng nói trong
    nhiễu trắng rất lớn (SNR 0 dB) mà VAD năng lượng bỏ sót, còn VAD năng lượng bắt được tiếng nói qua kênh điện thoại + tạp âm
    mà Silero bỏ sót (đo ở CHECKING § 11.24). Cả hai đều rỗng khi chỉ có tiếng ồn dừng."""

    def __init__(self, vads, merge_gap_s: float = 0.35):
        self.vads, self.merge_gap = list(vads), int(merge_gap_s * SAMPLE_RATE)
        self.name = "+".join(getattr(v, "name", "?") for v in self.vads)

    def detect(self, wave: np.ndarray) -> List[Tuple[int, int]]:
        ranges = sorted(r for v in self.vads for r in v.detect(wave))
        merged: List[List[int]] = []
        for a, b in ranges:
            if merged and a - merged[-1][1] <= self.merge_gap:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        return [(a, b) for a, b in merged]


SILERO_SHA256_PREFIX = "9e2449e1087496d8"      # silero_vad.onnx, release `asr-models` của k2-fsa/sherpa-onnx, 643.854 byte


def silero_model_path(model_dir: Optional[str] = None) -> Optional[str]:
    """Đường dẫn `silero_vad.onnx` nếu tìm thấy (env ASR_VAD_MODEL, rồi thư mục model), ngược lại None."""
    for c in (os.environ.get("ASR_VAD_MODEL", ""), os.path.join(model_dir, "silero_vad.onnx") if model_dir else ""):
        if c and os.path.isfile(c):
            return c
    return None


def default_vad(model_dir: Optional[str] = None, choice: Optional[str] = None, max_speech_s: float = 25.0):
    """Chọn VAD theo `choice` / env `ASR_VAD`:
      - `silero` : bắt buộc dùng Silero; thiếu file model → FileNotFoundError (không im lặng đổi sang VAD khác);
      - `energy` : VAD theo năng lượng (không cần model);
      - `auto` (mặc định): HỢP của Silero và VAD năng lượng nếu có `silero_vad.onnx` (mỗi VAD bắt được trường hợp VAD kia bỏ sót),
        ngược lại chỉ EnergyVAD (dự phòng).
    """
    choice = (choice or os.environ.get("ASR_VAD") or "auto").strip().lower()
    if choice not in ("auto", "silero", "energy"):
        raise ValueError(f"ASR_VAD không hợp lệ: '{choice}' (chọn: silero | energy | auto)")
    if choice == "energy":
        return EnergyVAD()
    path = silero_model_path(model_dir)
    if path:
        silero = SileroVAD(path, max_speech_s=max_speech_s)
        return silero if choice == "silero" else UnionVAD([silero, EnergyVAD()])
    if choice == "silero":
        raise FileNotFoundError("ASR_VAD=silero nhưng không có silero_vad.onnx (đặt vào model_ASR/ hoặc ASR_VAD_MODEL; xem README § ASR)")
    return EnergyVAD()


# --------------------------------------------------------------------------------------------- cắt đoạn
def split_long_ranges(ranges: List[Tuple[int, int]], energy_db: np.ndarray, frame: int,
                      max_len_s: float = 25.0, search_s: float = 6.0) -> List[Tuple[int, int]]:
    """Cắt đoạn dài hơn `max_len_s` tại khung năng lượng thấp nhất trong `search_s` giây cuối trước giới hạn."""
    max_len = int(max_len_s * SAMPLE_RATE)
    search = int(search_s * SAMPLE_RATE)
    out: List[Tuple[int, int]] = []
    for a, b in ranges:
        while b - a > max_len:
            lo, hi = a + max_len - search, a + max_len
            f0, f1 = max(0, lo // frame), min(len(energy_db), hi // frame)
            cut = a + max_len if f1 <= f0 else (f0 + int(np.argmin(energy_db[f0:f1]))) * frame
            cut = min(max(cut, a + SAMPLE_RATE), b)       # không để đoạn con < 1 giây
            out.append((a, cut))
            a = cut
        if b > a:
            out.append((a, b))
    return out


def make_chunks(wave: np.ndarray, vad=None, max_chunk_s: float = 25.0) -> List[Chunk]:
    """VAD rồi cắt đoạn dài → danh sách `Chunk` (mốc thời gian theo giây trong file gốc). Audio không có tiếng nói → []."""
    vad = vad or EnergyVAD()
    ranges = vad.detect(wave)
    if not ranges:
        return []
    frame = 320
    ranges = split_long_ranges(sorted(ranges), frame_energy_db(wave, frame), frame, max_len_s=max_chunk_s)
    return [Chunk(a / SAMPLE_RATE, b / SAMPLE_RATE, wave[a:b]) for a, b in ranges if b - a >= int(0.1 * SAMPLE_RATE)]
