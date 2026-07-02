"""Menu-bar app: wires hotkey → record → transcribe → clean → polish → paste."""

import threading

import rumps

from wisper.asr import Transcriber
from wisper.audio import Recorder
from wisper.cleanup import clean
from wisper.config import Config, load_config
from wisper.context import frontmost_app_name, tone_for_app
from wisper.dictionary import apply_dictionary
from wisper.hotkey import PushToTalk
from wisper.paste import copy_only, paste_text

IDLE, RECORDING, PROCESSING, LOADING = "🎤", "🔴", "⏳", "…"


class WisperApp(rumps.App):
    def __init__(self, cfg: Config):
        super().__init__("Wisper", title=LOADING, quit_button="Quit")
        self.cfg = cfg
        self.recorder = Recorder()
        self.transcriber: Transcriber | None = None
        self.polisher = None
        self.enabled = True
        self.menu = [
            rumps.MenuItem("Enabled", callback=self._toggle_enabled),
            rumps.MenuItem("LLM polish", callback=self._toggle_polish),
        ]
        self.menu["Enabled"].state = True
        self.menu["LLM polish"].state = cfg.llm_polish
        threading.Thread(target=self._load_models, daemon=True).start()
        self.hotkey = PushToTalk(cfg.hotkey, self._on_press, self._on_release)
        self.hotkey.start()

    def _load_models(self) -> None:
        self.transcriber = Transcriber(self.cfg.asr_model)
        if self.cfg.llm_polish:
            try:
                from wisper.polish import make_polisher

                self.polisher = make_polisher(self.cfg)
            except Exception as e:
                print(f"LLM polish unavailable ({e}); continuing with rules only")
                self.menu["LLM polish"].state = False
        self.title = IDLE
        print("Models loaded. Hold your hotkey and speak.")

    def _toggle_enabled(self, item) -> None:
        self.enabled = not self.enabled
        item.state = self.enabled

    def _toggle_polish(self, item) -> None:
        item.state = not item.state

    def _on_press(self) -> None:
        if not self.enabled or self.transcriber is None:
            return
        self.title = RECORDING
        self.recorder.start()

    def _on_release(self) -> None:
        if self.transcriber is None:
            return
        audio = self.recorder.stop()
        if self.recorder.duration(audio) < self.cfg.min_utterance_seconds:
            self.title = IDLE
            return
        self.title = PROCESSING
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio) -> None:
        try:
            text = self.transcriber.transcribe(audio)
            text = clean(text, self.cfg.filler_words)
            text = apply_dictionary(text, self.cfg.dictionary)
            if text and self.polisher is not None and self.menu["LLM polish"].state:
                tone = tone_for_app(frontmost_app_name())
                text = self.polisher.polish(text, tone)
            if text:
                try:
                    paste_text(text)
                except Exception as e:
                    print(f"Paste failed ({e}); text left on clipboard")
                    copy_only(text)
        except Exception as e:
            print(f"Pipeline error: {e}")
        finally:
            self.title = IDLE


def main() -> None:
    cfg = load_config()
    WisperApp(cfg).run()
