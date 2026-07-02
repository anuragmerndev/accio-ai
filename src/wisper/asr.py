"""Local ASR on MLX. Two backends:

- ParakeetTranscriber: fastest, English-only (Parakeet TDT v2)
- WhisperTranscriber: 100+ languages incl. Hindi/Hinglish, auto-detect per utterance

Both take in-memory float32 audio and return (text, language_code).
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


def make_transcriber(cfg):
    if cfg.asr_backend == "whisper":
        return WhisperTranscriber(cfg.whisper_model)
    return ParakeetTranscriber(cfg.asr_model)


# backwards-compatible name for the original backend
class Transcriber(ParakeetTranscriber):
    def transcribe(self, audio: np.ndarray) -> str:  # type: ignore[override]
        return super().transcribe(audio)[0]
