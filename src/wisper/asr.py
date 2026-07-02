"""Local ASR via Parakeet on MLX. Model loads once, transcribes in-memory audio."""

import mlx.core as mx
import numpy as np
from parakeet_mlx import from_pretrained
from parakeet_mlx.audio import get_logmel


class Transcriber:
    def __init__(self, model_name: str):
        self.model = from_pretrained(model_name)

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) == 0:
            return ""
        data = mx.array(audio.astype(np.float32))
        mel = get_logmel(data, self.model.preprocessor_config)
        result = self.model.generate(mel)[0]
        return result.text.strip()
