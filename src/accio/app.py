"""Menu-bar app: wires hotkey → record → pipeline worker → paste.

Threading rule: the pynput listener thread must never touch CoreAudio.
recorder.start()/stop() can block indefinitely when the input device changes
(e.g. Bluetooth earbuds vanishing) — doing that on the listener thread froze
the hotkey until the app was quit. Key events only enqueue; a dedicated audio
worker does the blocking work, and a watchdog recovers from a dead listener or
a missed release event.
"""

import queue
import threading
import time

import rumps

from accio.audio import Recorder
from accio.config import Config, load_config
from accio.context import frontmost_app_name, tone_for_app
from accio.hotkey import PushToTalk
from accio.paste import copy_only, paste_text
from accio.pipeline import Pipeline

IDLE, RECORDING, PROCESSING, LOADING = "🎤", "🔴", "⏳", "…"

WATCHDOG_INTERVAL_SECONDS = 5
# hold a push-to-talk key this long before the mic opens. A key that doubles as
# a typing key (right Shift for a capital) is tapped far faster than this, so
# typing never opens the audio stream — which otherwise thrashes CoreAudio and
# eventually wedges the audio worker.
HOLD_TO_TALK_SECONDS = 0.25


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
                "Requested Input Monitoring. Enable Accio in System Settings → "
                "Privacy & Security → Input Monitoring, then restart."
            )
        return granted
    except Exception as e:
        print(f"input monitoring check failed: {e}")
        return False


class AccioApp(rumps.App):
    def __init__(self, cfg: Config):
        super().__init__("Accio", title=LOADING, quit_button="Quit")
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
        self._recording_since: float | None = None
        self._pending_start = False
        self._start_timer: threading.Timer | None = None
        self._press_lock = threading.Lock()
        self._audio_events: queue.Queue = queue.Queue()
        threading.Thread(target=self._audio_worker, daemon=True).start()
        ensure_input_monitoring()
        self.hotkey = PushToTalk(cfg.hotkey, self._on_press, self._on_release)
        self.hotkey.start()
        self._watchdog_timer = rumps.Timer(self._watchdog, WATCHDOG_INTERVAL_SECONDS)
        self._watchdog_timer.start()

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

    # --- hotkey callbacks: enqueue only, never block the listener thread ---

    def _on_press(self) -> None:
        if not self.enabled or not self.pipeline.ready:
            return
        with self._press_lock:
            if self._pending_start or self._recording_since:
                return
            # defer opening the mic; a quick tap cancels before this fires
            self._pending_start = True
            self._start_timer = threading.Timer(HOLD_TO_TALK_SECONDS, self._begin_recording)
            self._start_timer.start()

    def _begin_recording(self) -> None:
        with self._press_lock:
            if not self._pending_start:  # released within the hold window: a tap
                return
            self._pending_start = False
            self._recording_since = time.time()
        self.title = RECORDING
        self._audio_events.put("start")

    def _on_release(self) -> None:
        with self._press_lock:
            if self._pending_start:  # tapped and let go before the mic opened
                self._pending_start = False
                if self._start_timer is not None:
                    self._start_timer.cancel()
                return
            if not self.pipeline.ready or not self._recording_since:
                return
        self._audio_events.put("stop")

    # --- audio worker: owns all CoreAudio calls, serially ---

    def _audio_worker(self) -> None:
        while True:
            event = self._audio_events.get()
            try:
                if event == "start":
                    self.recorder.start()
                elif event == "stop":
                    audio = self.recorder.stop()
                    self._recording_since = None
                    if self.recorder.duration(audio) < self.cfg.min_utterance_seconds:
                        self.title = IDLE
                        continue
                    self.title = PROCESSING
                    # capture tone now, while the target app is still frontmost
                    self.pipeline.submit(audio, tone_for_app(frontmost_app_name()))
            except Exception as e:
                print(f"Audio worker error on {event!r}: {e}")
                self._recording_since = None
                self.title = IDLE

    # --- watchdog: recover from a dead listener or a missed release event ---

    def _watchdog(self, _timer) -> None:
        if not self.hotkey.alive:
            print("hotkey listener died; restarting it")
            try:
                self.hotkey.stop()
            except Exception:
                pass
            self.hotkey = PushToTalk(self.cfg.hotkey, self._on_press, self._on_release)
            self.hotkey.start()
        if (
            self._recording_since
            and time.time() - self._recording_since > self.cfg.max_recording_seconds
        ):
            print(
                f"recording exceeded {self.cfg.max_recording_seconds}s "
                "(missed release?); forcing stop"
            )
            self.hotkey.reset_held()
            self._audio_events.put("stop")


def main() -> None:
    cfg = load_config()
    AccioApp(cfg).run()
