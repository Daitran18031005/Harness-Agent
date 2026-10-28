"""
Offline ASR: speech-to-text tiếng Việt chạy local, chọn backend bằng biến môi trường `ASR_BACKEND`:
  - `gipformer` (MẶC ĐỊNH từ 2026-10-21): Gipformer 1.5 68M RNN-T (G-Group AI Lab, MIT) qua sherpa-onnx, ONNX int8, CPU, không tốn API.
    VAD chọn bằng `ASR_VAD=silero|energy|auto` (auto: Silero nếu có `silero_vad.onnx`, ngược lại VAD năng lượng).
  - `whisper`   : faster-whisper (model theo `ASR_MODEL`, mặc định `base`) — DỰ PHÒNG: không đặt ASR_BACKEND mà Gipformer không
    nạp được thì tự rơi về whisper (có cảnh báo). Luật quay lại whisper: xem docs/PLAN.md bước 16a.
Mọi lỗi (thiếu model, sai hash, thiếu ffmpeg, load fail) -> `transcribe_audio` log cảnh báo RÕ NGUYÊN NHÂN và trả "" — KHÔNG
crash pipeline; caller (UI/eval_asr.py) phải tự xử lý transcript rỗng bằng cách cho nhập tay. Muốn bắt lỗi chi tiết thì gọi
`get_backend(name).load()` / `.transcribe_detail()` trực tiếp (ném `ASRModelError`).

Giao diện chung của backend: `name`, `is_available()`, `transcribe(path) -> str`, `transcribe_detail(path) -> ASRResult`.
Tự chọn device="cuda" cho whisper nếu có GPU (qua ctranslate2), fallback "cpu".
[INTEGRATION POINT: LOCAL ASR MODEL]
"""
import os
import time
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("harness.asr")

_model = None
_model_size = None
_available = None  # None = chưa kiểm tra, True/False = đã biết kết quả
_force_cpu = False  # bật thật khi phát hiện CUDA runtime (cuBLAS/cuDNN) thiếu dù GPU có driver


def _patch_av_compat():
    """Vá tương thích: faster-whisper 1.2.1 gọi av.open(..., metadata_errors='ignore'),
    nhưng bản PyAV mới nhất có wheel cho Python 3.14 (19.x) đã bỏ tham số này (lỗi thật đã
    gặp: TypeError: open() got an unexpected keyword argument 'metadata_errors'). Không có
    bản av cũ nào có sẵn wheel cho cp314 để downgrade, nên vá tương thích ở đây thay vì bắt
    toàn bộ ASR fail. Nếu av không có vấn đề này (version khác), bỏ qua lặng lẽ."""
    try:
        import av
        _original_open = av.open  # built-in Cython function, inspect.signature() không dùng được

        def _patched_open(*args, **kwargs):
            try:
                return _original_open(*args, **kwargs)
            except TypeError:
                # PyAV mới bỏ tham số metadata_errors -> thử lại không có nó.
                kwargs.pop("metadata_errors", None)
                return _original_open(*args, **kwargs)

        av.open = _patched_open
    except Exception as e:
        logger.debug("[ASR] _patch_av_compat bỏ qua (%s).", e)


_patch_av_compat()


def _device_and_compute_type():
    if _force_cpu:
        return "cpu", "int8"
    try:
        import ctranslate2
        # get_cuda_device_count() chỉ xác nhận driver NVIDIA có GPU, KHÔNG đảm bảo runtime
        # CUDA (cuBLAS/cuDNN .dll) đã cài đủ — lỗi thật đã gặp: model load "thành công" với
        # device=cuda nhưng transcribe() mới fail vì thiếu cublas64_12.dll. Nên vẫn thử cuda
        # trước, nhưng transcribe_audio() có cơ chế rơi về cpu tự động nếu cuda fail thật.
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception as e:
        logger.info("[ASR] không phát hiện GPU qua ctranslate2 (%s) — dùng CPU.", e)
    return "cpu", "int8"


def _get_model(model_size: str):
    global _model, _model_size, _available
    if _model is not None and _model_size == model_size:
        return _model
    try:
        # Môi trường conda `nlp_env` có 3 bản libiomp5md.dll (ctranslate2, torch, MKL của numpy): lần nhận dạng đầu tiên của
        # whisper làm tiến trình THOÁT với "OMP: Error #15" (đã gặp 2026-10-21). Cho phép nạp trùng — cách Intel ghi là
        # "không được hỗ trợ" nhưng là cách chuẩn để chạy ctranslate2 cạnh numpy/torch; kết quả được đối chiếu với báo cáo cũ.
        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
        from faster_whisper import WhisperModel
        device, compute_type = _device_and_compute_type()
        _model = WhisperModel(model_size, device=device, compute_type=compute_type,
                              cpu_threads=int(os.environ.get("ASR_NUM_THREADS", "0") or 0))   # 0 = mặc định của ctranslate2
        _model_size = model_size
        _available = True
        logger.info("[ASR] faster-whisper ENABLED (model=%s, device=%s, compute_type=%s)", model_size, device, compute_type)
        return _model
    except Exception as e:
        logger.warning("[ASR] faster-whisper unavailable/failed to load (%s) — ASR DISABLED, cần nhập tay.", e)
        _available = False
        return None


def _transcribe_whisper(audio_path: str, model_size: Optional[str] = None) -> str:
    """(backend whisper) Nhận đường dẫn file .wav/.mp3, trả về transcript tiếng Việt có dấu.
    Trả '' nếu ASR không khả dụng hoặc lỗi bất kỳ (không bao giờ raise)."""
    global _model, _force_cpu
    model_size = model_size or os.environ.get("ASR_MODEL", "base")
    if not audio_path or not os.path.exists(audio_path):
        logger.warning("[ASR] audio_path không tồn tại (%s) — trả transcript rỗng.", audio_path)
        return ""

    model = _get_model(model_size)
    if model is None:
        return ""

    try:
        segments, _info = model.transcribe(audio_path, language="vi", vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
    except Exception as e:
        if not _force_cpu:
            # Khả năng cuda thiếu runtime (cuBLAS/cuDNN) dù driver có GPU -> rơi về CPU, thử lại 1 lần.
            logger.warning("[ASR] transcribe lỗi trên device hiện tại (%s) — thử lại bằng CPU.", e)
            _force_cpu = True
            _model = None
            model = _get_model(model_size)
            if model is not None:
                try:
                    segments, _info = model.transcribe(audio_path, language="vi", vad_filter=True)
                    return " ".join(seg.text.strip() for seg in segments).strip()
                except Exception as e2:
                    logger.warning("[ASR] transcribe thất bại cả trên CPU cho %s (%s) — trả transcript rỗng, cần nhập tay.", audio_path, e2)
                    return ""
        logger.warning("[ASR] transcribe thất bại cho %s (%s) — trả transcript rỗng, cần nhập tay.", audio_path, e)
        return ""


def _whisper_available(model_size: Optional[str] = None) -> bool:
    """(backend whisper) Kiểm tra ASR có dùng được không, không transcribe thật (dùng cho UI hiện trạng thái)."""
    global _available
    if _available is not None:
        return _available
    return _get_model(model_size or os.environ.get("ASR_MODEL", "base")) is not None


# =====================================================================================================
# Giao diện backend chung + Gipformer
# =====================================================================================================
class ASRModelError(RuntimeError):
    """Thiếu file model / sai hash / không khởi tạo được backend — thông điệp nói rõ cách khắc phục."""


@dataclass
class ASRResult:
    text: str                                                    # transcript (whisper: có dấu câu; gipformer: chữ thường, không dấu câu)
    words: List[Tuple[str, float, float]] = field(default_factory=list)   # (từ, bắt đầu s, kết thúc s) — chỉ khi backend có mốc thời gian theo token
    segments: List[Dict[str, object]] = field(default_factory=list)       # [{"start","end","text"}] theo đoạn VAD / đoạn whisper
    duration_s: float = 0.0                                      # độ dài audio
    speech_s: float = 0.0                                        # tổng thời lượng đoạn có tiếng nói (sau VAD)
    decode_s: float = 0.0                                        # thời gian chạy ASR (không gồm nạp model)
    backend: str = ""

    @property
    def rtf(self) -> float:
        return self.decode_s / self.duration_s if self.duration_s else 0.0


DEFAULT_BACKEND = "gipformer"      # đổi từ "whisper" ngày 2026-10-21 (quyết định của nhóm); whisper còn là dự phòng — xem PLAN 16a


def _backend_name(name: Optional[str] = None) -> str:
    raw = (name or os.environ.get("ASR_BACKEND") or DEFAULT_BACKEND).strip().lower()
    return {"faster-whisper": "whisper", "faster_whisper": "whisper", "fw": "whisper", "gip": "gipformer"}.get(raw, raw)


class WhisperASR:
    """Backend cũ (faster-whisper) bọc theo giao diện chung. Không thay đổi hành vi của `_transcribe_whisper`."""
    name = "whisper"

    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or os.environ.get("ASR_MODEL", "base")

    def load(self):
        if _get_model(self.model_size) is None:
            raise ASRModelError("faster-whisper không khả dụng (thiếu model/thư viện) — xem log [ASR].")
        return self

    def is_available(self) -> bool:
        return _whisper_available(self.model_size)

    def transcribe_detail(self, audio_path: str) -> ASRResult:
        self.load()
        model = _get_model(self.model_size)
        t0 = time.perf_counter()
        segments, info = model.transcribe(audio_path, language="vi", vad_filter=True)
        segs = [{"start": float(sg.start), "end": float(sg.end), "text": sg.text.strip()} for sg in segments]
        decode_s = time.perf_counter() - t0
        return ASRResult(text=" ".join(x["text"] for x in segs).strip(), segments=segs,
                         duration_s=float(getattr(info, "duration", 0.0) or 0.0),
                         speech_s=sum(x["end"] - x["start"] for x in segs), decode_s=decode_s, backend=self.name)

    def transcribe(self, audio_path: str) -> str:
        return _transcribe_whisper(audio_path, self.model_size)


# Hash SHA-256 (16 ký tự đầu) của gipformer1.5-68M-rnnt, do thành viên nhóm kiểm khi tải về (2026-10-21).
GIPFORMER_FILES: Dict[str, str] = {
    "encoder.int8.onnx": "b528768939c7711a",
    "decoder.int8.onnx": "e0a156b5454722a5",
    "joiner.int8.onnx": "12636559d135315f",
    "tokens.txt": "f536d03c2e95ebd2",
    "bpe.model": "289dbb44527c13c4",
}
GIPFORMER_HF_REPO = "g-group-ai-lab/gipformer1.5-68M-rnnt"
CODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_GIPFORMER_DIR = os.path.join(CODE_DIR, "model_ASR")
_HASH_CACHE: Dict[Tuple[str, int, int], str] = {}


def sha256_prefix(path: str, n: int = 16) -> str:
    """16 ký tự đầu SHA-256 của file (nhớ theo đường dẫn+kích thước+mtime để không băm lại 71 MB mỗi lần)."""
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _HASH_CACHE:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        _HASH_CACHE[key] = h.hexdigest()
    return _HASH_CACHE[key][:n]


class GipformerASR:
    """Gipformer 1.5 68M RNN-T (Zipformer transducer offline, ONNX int8) qua sherpa-onnx.

    Đặc điểm model (đã kiểm): token CHỮ HOA, không chữ số, không dấu câu; khi đầu vào chỉ có tiếng ồn vẫn in ra chữ
    → luôn qua VAD (bỏ đoạn lặng/ồn) và cắt đoạn ≤ `max_chunk_s` trước khi nhận dạng. Đầu ra được đưa về chữ thường
    (giữ dấu); ITN/che PII do `RequestNormalizer` làm ở bước sau (xem `asr_postprocess.py`).
    """
    name = "gipformer"

    def __init__(self, model_dir: Optional[str] = None, num_threads: Optional[int] = None, vad=None,
                 max_chunk_s: Optional[float] = None):
        self.model_dir = os.path.abspath(model_dir or os.environ.get("GIPFORMER_MODEL_DIR") or DEFAULT_GIPFORMER_DIR)
        self.num_threads = num_threads or int(os.environ.get("ASR_NUM_THREADS", "0") or 0) or min(4, os.cpu_count() or 2)
        # 20 s: trên 4 file thử, RAM đỉnh ~760 MB (25 s: ~985 MB) và WER không đổi trong sai số; đổi bằng ASR_MAX_CHUNK_S (≤ 30)
        self.max_chunk_s = float(max_chunk_s or os.environ.get("ASR_MAX_CHUNK_S") or 20.0)
        self._vad = vad
        self._recognizer = None
        self.load_s: Optional[float] = None

    # -- model ---------------------------------------------------------------------------------------
    def verify_files(self) -> None:
        """Thiếu file hoặc sai SHA-256 → ASRModelError nêu từng file và cách tải."""
        missing, wrong = [], []
        for fname, expected in GIPFORMER_FILES.items():
            path = os.path.join(self.model_dir, fname)
            if not os.path.isfile(path):
                missing.append(fname)
            elif sha256_prefix(path, len(expected)) != expected:
                wrong.append(f"{fname} (băm {sha256_prefix(path, len(expected))}, mong đợi {expected})")
        if missing or wrong:
            parts = []
            if missing:
                parts.append("THIẾU file: " + ", ".join(missing))
            if wrong:
                parts.append("SAI SHA-256: " + "; ".join(wrong))
            raise ASRModelError(
                f"Model Gipformer không hợp lệ trong '{self.model_dir}' — " + " | ".join(parts) +
                f". Tải lại: huggingface-cli download {GIPFORMER_HF_REPO} --local-dir model_ASR "
                f"(hoặc đặt GIPFORMER_MODEL_DIR). Xem README § ASR.")

    def load(self) -> "GipformerASR":
        if self._recognizer is not None:
            return self
        self.verify_files()
        try:
            import sherpa_onnx
        except ImportError as e:
            raise ASRModelError("Chưa cài sherpa-onnx — chạy: pip install -r requirements.txt") from e
        t0 = time.perf_counter()
        d = self.model_dir
        try:
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=os.path.join(d, "encoder.int8.onnx"), decoder=os.path.join(d, "decoder.int8.onnx"),
                joiner=os.path.join(d, "joiner.int8.onnx"), tokens=os.path.join(d, "tokens.txt"),
                num_threads=self.num_threads, sample_rate=16000, feature_dim=80, decoding_method="greedy_search")
        except Exception as e:
            raise ASRModelError(f"sherpa-onnx không khởi tạo được Gipformer: {e}") from e
        self.load_s = time.perf_counter() - t0
        logger.info("[ASR] Gipformer 1.5 ENABLED (threads=%d, load=%.2fs, vad=%s)", self.num_threads, self.load_s,
                    getattr(self._vad_obj(), "name", "?"))
        return self

    def is_available(self) -> bool:
        try:
            self.load()
            return True
        except ASRModelError as e:
            logger.warning("[ASR] Gipformer không khả dụng: %s", e)
            return False

    def _vad_obj(self):
        if self._vad is None:
            from src.channels.audio_vad import SILERO_SHA256_PREFIX, default_vad, silero_model_path
            try:
                self._vad = default_vad(self.model_dir, max_speech_s=self.max_chunk_s)
            except FileNotFoundError as e:
                raise ASRModelError(str(e)) from e
            path = silero_model_path(self.model_dir)
            if getattr(self._vad, "name", "") == "silero" and path and sha256_prefix(path, len(SILERO_SHA256_PREFIX)) != SILERO_SHA256_PREFIX:
                self._vad = None
                raise ASRModelError(f"silero_vad.onnx sai SHA-256 (mong đợi {SILERO_SHA256_PREFIX}…): {path}")
        return self._vad

    # -- nhận dạng -----------------------------------------------------------------------------------
    def transcribe_detail(self, audio, vad=None) -> ASRResult:
        """`audio`: đường dẫn file hoặc mảng numpy float32 mono 16 kHz. Không có tiếng nói → text rỗng."""
        import numpy as np
        from src.channels.audio_vad import SAMPLE_RATE, load_audio_16k, make_chunks
        self.load()
        wave = load_audio_16k(audio) if isinstance(audio, str) else np.asarray(audio, dtype=np.float32)
        duration = len(wave) / SAMPLE_RATE
        chunks = make_chunks(wave, vad or self._vad_obj(), self.max_chunk_s)
        if not chunks:
            return ASRResult(text="", duration_s=duration, backend=self.name)
        t0 = time.perf_counter()
        streams = []
        for ch in chunks:                                   # tuần tự từng đoạn: nhanh bằng/hơn decode_streams theo lô và
            st = self._recognizer.create_stream()           # RAM đỉnh ~0,5 GB thay vì ~1,15 GB (đo 2026-10-21, 4 file D01–D04)
            st.accept_waveform(SAMPLE_RATE, ch.samples)
            self._recognizer.decode_stream(st)
            streams.append(st)
        decode_s = time.perf_counter() - t0
        words: List[Tuple[str, float, float]] = []
        segments, texts = [], []
        for ch, st in zip(chunks, streams):
            res = st.result
            text = " ".join(res.text.lower().split())
            if not text:
                continue
            texts.append(text)
            segments.append({"start": round(ch.start_s, 3), "end": round(ch.end_s, 3), "text": text})
            words.extend(self._words(res, ch.start_s, ch.end_s))
        return ASRResult(text=" ".join(texts), words=words, segments=segments, duration_s=duration,
                         speech_s=sum(c.duration_s for c in chunks), decode_s=decode_s, backend=self.name)

    @staticmethod
    def _words(res, offset: float, chunk_end: float) -> List[Tuple[str, float, float]]:
        """Ghép token BPE (token bắt đầu bằng khoảng trắng = từ mới) thành từ kèm mốc thời gian (giây trong file gốc)."""
        toks, tss = list(res.tokens), list(res.timestamps)
        if not toks or len(toks) != len(tss):
            return []
        groups: List[List[int]] = []
        for i, tok in enumerate(toks):
            if tok.startswith(" ") or not groups:
                groups.append([i])
            else:
                groups[-1].append(i)
        out = []
        for gi, idxs in enumerate(groups):
            start = offset + tss[idxs[0]]
            end = offset + tss[groups[gi + 1][0]] if gi + 1 < len(groups) else min(offset + tss[idxs[-1]] + 0.3, chunk_end)
            out.append(("".join(toks[i] for i in idxs).strip().lower(), round(start, 3), round(max(end, start), 3)))
        return out

    def transcribe(self, audio_path: str) -> str:
        return self.transcribe_detail(audio_path).text


_BACKENDS: Dict[str, object] = {}


def get_backend(name: Optional[str] = None):
    """Backend theo tên (`whisper` | `gipformer`; mặc định lấy `ASR_BACKEND`, nếu không có là `whisper`). Dùng chung một instance."""
    key = _backend_name(name)
    if key not in _BACKENDS:
        if key == "gipformer":
            _BACKENDS[key] = GipformerASR()
        elif key == "whisper":
            _BACKENDS[key] = WhisperASR()
        else:
            raise ValueError(f"ASR_BACKEND không hợp lệ: '{key}' (chọn: whisper | gipformer)")
    return _BACKENDS[key]


def _gipformer_or_none():
    """(backend Gipformer đã nạp, None) hoặc (None, lý do) khi không dùng được."""
    try:
        be = get_backend("gipformer")
        be.load()
        be._vad_obj()          # kiểm tra luôn VAD đã chọn (ASR_VAD=silero thiếu model → lỗi rõ ràng, không im lặng)
        return be, None
    except ASRModelError as e:
        return None, str(e)


def transcribe_audio(audio_path: str, model_size: Optional[str] = None) -> str:
    """Nhận đường dẫn file .wav/.mp3, trả về transcript tiếng Việt (backend theo `ASR_BACKEND`, mặc định gipformer).
    Không đặt ASR_BACKEND mà Gipformer không dùng được (thiếu/sai model) → rơi về whisper kèm cảnh báo; đặt rõ
    `ASR_BACKEND=gipformer` mà lỗi thì KHÔNG đổi ngầm. Trả '' nếu không có tiếng nói hoặc lỗi bất kỳ (không bao giờ raise)."""
    try:
        backend = _backend_name()
        explicit = bool(os.environ.get("ASR_BACKEND"))
        if backend == "whisper":
            return _transcribe_whisper(audio_path, model_size)
        if not audio_path or not os.path.exists(audio_path):
            logger.warning("[ASR] audio_path không tồn tại (%s) — trả transcript rỗng.", audio_path)
            return ""
        if backend == "gipformer":
            be, why = _gipformer_or_none()
            if be is None:
                if explicit:
                    logger.warning("[ASR] Gipformer lỗi: %s — trả transcript rỗng, cần nhập tay.", why)
                    return ""
                logger.warning("[ASR] Gipformer không dùng được (%s) — RƠI VỀ whisper (dự phòng).", why)
                return _transcribe_whisper(audio_path, model_size)
            return be.transcribe(audio_path)
        return get_backend(backend).transcribe(audio_path)
    except Exception as e:
        logger.warning("[ASR] backend '%s' lỗi: %s — trả transcript rỗng, cần nhập tay.", _backend_name(), e)
        return ""


def is_available(model_size: Optional[str] = None) -> bool:
    """Backend hiện chọn (hoặc dự phòng whisper khi ASR_BACKEND không đặt) có dùng được không (không transcribe thật)."""
    try:
        backend = _backend_name()
        if backend == "whisper":
            return _whisper_available(model_size)
        if backend == "gipformer":
            be, why = _gipformer_or_none()
            if be is not None:
                return True
            logger.warning("[ASR] Gipformer không khả dụng: %s", why)
            return False if os.environ.get("ASR_BACKEND") else _whisper_available(model_size)
        return bool(get_backend(backend).is_available())
    except Exception as e:
        logger.warning("[ASR] kiểm tra backend lỗi: %s", e)
        return False
