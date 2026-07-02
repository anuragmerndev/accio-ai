"""Single-worker pipeline: all MLX work stays on one thread.

MLX GPU streams are thread-local — loading models on one thread and running
inference on another raises "There is no Stream(gpu, 0) in current thread".
A persistent worker thread owns load + inference; utterances arrive via queue.
"""

import queue
import threading
from collections.abc import Callable

import numpy as np

from wisper.cleanup import clean
from wisper.config import Config
from wisper.dictionary import apply_dictionary


class Pipeline:
    def __init__(
        self,
        cfg: Config,
        on_ready: Callable[[bool], None],
        on_result: Callable[[str], None],
        on_done: Callable[[], None],
    ):
        """on_ready(llm_available) fires after models load; on_result(text) per
        utterance with non-empty text; on_done() after each utterance regardless.
        All callbacks run on the worker thread."""
        self.cfg = cfg
        self.on_ready = on_ready
        self.on_result = on_result
        self.on_done = on_done
        self.polish_enabled = cfg.llm_polish
        self._jobs: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        threading.Thread(target=self._worker, daemon=True).start()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    def submit(self, audio: np.ndarray, tone: str) -> None:
        self._jobs.put((audio, tone))

    def _worker(self) -> None:
        from wisper.asr import make_transcriber

        transcriber = make_transcriber(self.cfg)
        polisher = None
        if self.cfg.llm_polish:
            try:
                from wisper.polish import make_polisher

                polisher = make_polisher(self.cfg)
            except Exception as e:
                print(f"LLM polish unavailable ({e}); continuing with rules only")
        romanizer = None
        if self.cfg.romanize_languages:
            try:
                from wisper.romanize import Romanizer

                romanizer = Romanizer(self.cfg.romanize_model, self.cfg.ollama_url)
            except Exception as e:
                print(f"Romanization unavailable ({e}); non-Latin scripts paste as-is")
        self._ready.set()
        self.on_ready(polisher is not None)

        while True:
            audio, tone = self._jobs.get()
            try:
                text, language = transcriber.transcribe(audio)
                if text and romanizer is not None and language in self.cfg.romanize_languages:
                    text = romanizer.romanize(text)
                text = clean(text, self.cfg.filler_words)
                text = apply_dictionary(text, self.cfg.dictionary)
                # the polish model is only trustworthy in configured languages;
                # other languages get rules-only cleanup
                if (
                    text
                    and polisher is not None
                    and self.polish_enabled
                    and language in self.cfg.polish_languages
                ):
                    text = polisher.polish(text, tone)
                if text:
                    self.on_result(text)
            except Exception as e:
                print(f"Pipeline error: {e}")
            finally:
                self.on_done()
