"""Menu-bar app: wires hotkey → record → pipeline worker → paste."""

import rumps

from wisper.audio import Recorder
from wisper.config import Config, load_config
from wisper.context import frontmost_app_name, tone_for_app
from wisper.hotkey import PushToTalk
from wisper.paste import copy_only, paste_text
from wisper.pipeline import Pipeline

IDLE, RECORDING, PROCESSING, LOADING = "🎤", "🔴", "⏳", "…"


def ensure_input_monitoring() -> bool:
    """The global hotkey listener needs Input Monitoring (separate from
    Accessibility, which only covers the paste keystroke). Requesting it
    registers this binary in System Settings → Privacy → Input Monitoring
    so the user can enable it; the grant takes effect on the next launch."""
    try:
        from Quartz import CGPreflightListenEventAccess, CGRequestListenEventAccess

        granted = CGPreflightListenEventAccess()
        print(f"input monitoring granted={granted}")
        if not granted:
            CGRequestListenEventAccess()
            print(
                "Requested Input Monitoring. Enable Wisper in System Settings → "
                "Privacy & Security → Input Monitoring, then restart."
            )
        return granted
    except Exception as e:
        print(f"input monitoring check failed: {e}")
        return False


class WisperApp(rumps.App):
    def __init__(self, cfg: Config):
        super().__init__("Wisper", title=LOADING, quit_button="Quit")
        self.cfg = cfg
        self.recorder = Recorder()
        self.enabled = True
        self.menu = [
            rumps.MenuItem("Enabled", callback=self._toggle_enabled),
            rumps.MenuItem("LLM polish", callback=self._toggle_polish),
        ]
        self.menu["Enabled"].state = True
        self.menu["LLM polish"].state = cfg.llm_polish
        self.pipeline = Pipeline(
            cfg,
            on_ready=self._on_models_ready,
            on_result=self._on_text,
            on_done=self._on_utterance_done,
        )
        ensure_input_monitoring()
        self.hotkey = PushToTalk(cfg.hotkey, self._on_press, self._on_release)
        self.hotkey.start()

    def _on_models_ready(self, llm_available: bool) -> None:
        if not llm_available:
            self.menu["LLM polish"].state = False
        self.title = IDLE
        print("Models loaded. Hold your hotkey and speak.")

    def _on_text(self, text: str) -> None:
        try:
            paste_text(text)
        except Exception as e:
            print(f"Paste failed ({e}); text left on clipboard")
            copy_only(text)

    def _on_utterance_done(self) -> None:
        self.title = IDLE

    def _toggle_enabled(self, item) -> None:
        self.enabled = not self.enabled
        item.state = self.enabled

    def _toggle_polish(self, item) -> None:
        item.state = not item.state
        self.pipeline.polish_enabled = bool(item.state)

    def _on_press(self) -> None:
        if not self.enabled or not self.pipeline.ready:
            return
        self.title = RECORDING
        self.recorder.start()

    def _on_release(self) -> None:
        if not self.pipeline.ready:
            return
        audio = self.recorder.stop()
        if self.recorder.duration(audio) < self.cfg.min_utterance_seconds:
            self.title = IDLE
            return
        self.title = PROCESSING
        # capture tone now, while the target app is still frontmost
        self.pipeline.submit(audio, tone_for_app(frontmost_app_name()))


def main() -> None:
    cfg = load_config()
    WisperApp(cfg).run()
