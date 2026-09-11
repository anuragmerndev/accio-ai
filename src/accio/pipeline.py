"""Single-worker pipeline: all MLX work stays on one thread.

MLX GPU streams are thread-local — loading models on one thread and running
inference on another raises "There is no Stream(gpu, 0) in current thread".
A persistent worker thread owns load + inference; utterances arrive via queue.
"""

import queue
import threading
import time
from collections.abc import Callable

import numpy as np

from accio.cleanup import clean
from accio.config import Config
from accio.dictionary import apply_dictionary


def _devanagari_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters)


def needs_romanization(text: str, language: str, romanize_languages: list[str]) -> bool:
    """Romanize only when Devanagari is actually present — a flaky 'hi' tag on
    Latin-script English must not send English text through the romanizer."""
    return language in romanize_languages and _devanagari_ratio(text) > 0.2


def should_polish(text: str, language: str, polish_languages: list[str]) -> bool:
    """Polish when the tag says a supported language OR the text is
    overwhelmingly Latin script (accents often mistag English speech)."""
    if language in polish_languages:
        return True
    return _devanagari_ratio(text) == 0.0 and text.isascii()


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
        from accio.asr import make_transcriber

        transcriber = make_transcriber(self.cfg)
        polisher = None
        if self.cfg.llm_polish:
            try:
                from accio.polish import make_polisher

                polisher = make_polisher(self.cfg)
            except Exception as e:
                print(f"LLM polish unavailable ({e}); continuing with rules only")
        romanizer = None
        if self.cfg.romanize_languages:
            try:
                from accio.romanize import Romanizer

                romanizer = Romanizer(self.cfg.romanize_model, self.cfg.ollama_url)
            except Exception as e:
                print(f"Romanization unavailable ({e}); non-Latin scripts paste as-is")
        self._ready.set()
        self.on_ready(polisher is not None)

        while True:
            audio, tone = self._jobs.get()
            try:
                import numpy as np

                peak = float(np.abs(audio).max()) if len(audio) else 0.0
                if peak < self.cfg.min_peak_amplitude:
                    # too quiet to be speech: skip so Whisper's silence
                    # hallucination ("Thank you.") never reaches the cursor
                    print(f"skipped: no speech (peak={peak:.4f})")
                    continue
                print("→ transcribe")
                t0 = time.time()
                text, language = transcriber.transcribe(audio)
                print(f"← transcribe {time.time() - t0:.2f}s")
                # gate on the script actually present, not just Whisper's
                # language tag — accents make the tag flaky (English speech
                # tagged "hi" was skipping polish entirely)
                romanized = text and romanizer is not None and needs_romanization(
                    text, language, self.cfg.romanize_languages
                )
                if romanized:
                    text = romanizer.romanize(text)
                text = clean(text, self.cfg.filler_words)
                text = apply_dictionary(text, self.cfg.dictionary)
                polished = (
                    text
                    and polisher is not None
                    and self.polish_enabled
                    and should_polish(text, language, self.cfg.polish_languages)
                )
                if polished:
                    print("→ polish")
                    t0 = time.time()
                    text = polisher.polish(text, tone)
                    print(f"← polish {time.time() - t0:.2f}s")
                print(
                    f"utterance: lang={language} tone={tone} peak={peak:.3f} "
                    f"romanize={bool(romanized)} polish={bool(polished)}"
                )
                if text:
                    self.on_result(text)
            except Exception as e:
                print(f"Pipeline error: {e}")
            finally:
                self.on_done()
