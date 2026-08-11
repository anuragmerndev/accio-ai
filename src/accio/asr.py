"""Local ASR. Multiple backends, picked by config:

- ParakeetTranscriber: fastest, English-only (Parakeet TDT v2, MLX)
- WhisperTranscriber: 100+ languages incl. Hindi/Hinglish, auto-detect per utterance (MLX)
- FasterWhisperTranscriber: cross-platform Whisper via CTranslate2 — the
  default on Windows where Apple MLX is unavailable. Supports CPU and
  NVIDIA CUDA.

All transcribers take in-memory float32 audio (1-D mono) and return
(text, language_code).
"""

import numpy as np


class ParakeetTranscriber:
    def __init__(self, model_name: str):
        from parakeet_mlx import from_pretrained

        self.model = from_pretrained(model_name)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        import mlx.core as mx
        from parakeet_mlx.audio import get_logmel

        if len(audio) == 0:
            return "", "en"
        data = mx.array(audio.astype(np.float32))
        mel = get_logmel(data, self.model.preprocessor_config)
        result = self.model.generate(mel)[0]
        return result.text.strip(), "en"


class WhisperTranscriber:
    def __init__(self, model_name: str):
        import mlx_whisper

        self._transcribe = mlx_whisper.transcribe
        self.model_name = model_name
        # first call compiles/loads; warm up so the first dictation isn't slow
        self._transcribe(np.zeros(16_000, dtype=np.float32), path_or_hf_repo=model_name)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if len(audio) == 0:
            return "", "en"
        result = self._transcribe(
            audio.astype(np.float32),
            path_or_hf_repo=self.model_name,
            condition_on_previous_text=False,
        )
        return result["text"].strip(), result.get("language", "en")


class FasterWhisperTranscriber:
    """Cross-platform Whisper via CTranslate2. Uses CTranslate2's C++ runtime so
    it works on Windows where MLX is unavailable. Falls back to CPU when no
    CUDA device is present.

    `compute_type` is kept configurable: `int8` (lightest, fastest on CPU,
    default on Windows) through to `float16` (NVIDIA GPU)."""

    def __init__(self, model_name: str, device: str = "auto", compute_type: str = "int8"):
        from faster_whisper import WhisperModel

        if device == "auto":
            device = self._detect_device()
        self.model_name = model_name
        self._model = WhisperModel(model_name, device=device, compute_type=compute_type)
        # warm up so the first dictation isn't slow
        self._model.transcribe(np.zeros(16_000, dtype=np.float32), language=None)

    @staticmethod
    def _detect_device() -> str:
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if len(audio) == 0:
            return "", "en"
        segments, info = self._model.transcribe(
            audio.astype(np.float32),
            language=None,  # auto-detect
            condition_on_previous_text=False,
            beam_size=1,  # greedy: fast and matches mlx-whisper's default flow
        )
        text = " ".join(seg.text for seg in segments).strip()
        language = getattr(info, "language", "en") or "en"
        return text, language


def make_transcriber(cfg):
    if cfg.asr_backend == "faster_whisper":
        return FasterWhisperTranscriber(
            cfg.whisper_model,
            device=cfg.faster_whisper_device,
            compute_type=cfg.faster_whisper_compute_type,
        )
    if cfg.asr_backend == "whisper":
        return WhisperTranscriber(cfg.whisper_model)
    return ParakeetTranscriber(cfg.asr_model)


# backwards-compatible name for the original backend
class Transcriber(ParakeetTranscriber):
    def transcribe(self, audio: np.ndarray) -> str:  # type: ignore[override]
        return super().transcribe(audio)[0]
