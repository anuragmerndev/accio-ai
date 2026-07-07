"""Microphone capture: start on hotkey press, stop on release, return float32 mono."""

import threading

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._on_audio,
            )
            self._stream.start()

    def _on_audio(self, indata, frames, time_info, status) -> None:
        self._chunks.append(indata[:, 0].copy())

    def stop(self) -> np.ndarray:
        with self._lock:
            stream, self._stream = self._stream, None
            if stream is None:
                return np.zeros(0, dtype=np.float32)
            try:
                stream.stop()
                stream.close()
            except Exception as e:
                # device vanished mid-recording (Bluetooth earbuds sleeping);
                # keep whatever audio was captured rather than dying
                print(f"recorder stop error (device change?): {e}")
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)

    def duration(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate
