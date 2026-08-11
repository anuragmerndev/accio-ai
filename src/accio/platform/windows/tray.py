"""Windows system-tray app: wires hotkey to record to pipeline worker to paste.

Ports the macOS rumps bar to pystray. The threading rule from the darwin tray
translates directly: never block the pynput listener thread with mic calls.
Audio work runs on a dedicated worker; a watchdog recovers from a missed
hotkey release event.
"""

import queue
import threading
import time

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from accio.audio import Recorder
from accio.config import Config, load_config
from accio.context import frontmost_app_name, tone_for_app
from accio.hotkey import PushToTalk
from accio.paste import copy_only, paste_text
from accio.pipeline import Pipeline

IDLE, RECORDING, PROCESSING, LOADING = "idle", "recording", "processing", "loading"

WATCHDOG_INTERVAL_SECONDS = 5


def _make_icon_bitmap(state: str) -> Image.Image:
    """Build a 64x64 tray icon at the right state. Monochrome by design so it
    reads on both light and dark taskbar themes."""
    colour = {
        IDLE: "#888888",
        RECORDING: "#d83232",
        PROCESSING: "#c8a32a",
        LOADING: "#444444",
    }.get(state, "#888888")
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=colour)
    return img


class AccioTray:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.recorder = Recorder()
        self.enabled = True
        self.pipeline = Pipeline(
            cfg,
            on_ready=self._on_models_ready,
            on_result=self._on_text,
            on_done=self._on_utterance_done,
        )
        self._recording_since: float | None = None
        self._audio_events: queue.Queue = queue.Queue()
        threading.Thread(target=self._audio_worker, daemon=True).start()

        self.hotkey = PushToTalk(cfg.hotkey, self._on_press, self._on_release)
        self.hotkey.start()

        self._watchdog_stop = threading.Event()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog, daemon=True, name="accio-watchdog"
        )
        self._watchdog_thread.start()

        self.icon = Icon(
            "accio",
            icon=_make_icon_bitmap(LOADING),
            title="Accio",
            menu=Menu(
                MenuItem(
                    lambda _: f"Enabled ({'on' if self.enabled else 'off'})",
                    self._toggle_enabled,
                ),
                MenuItem(
                    lambda _: f"LLM polish ({'on' if self.pipeline.polish_enabled else 'off'})",
                    self._toggle_polish,
                ),
                Menu.SEPARATOR,
                MenuItem("Quit", self._quit),
            ),
        )

    # --- pipeline callbacks (worker thread) ----------------------------------

    def _on_models_ready(self, llm_available: bool) -> None:
        if not llm_available:
            self.pipeline.polish_enabled = False
        self.icon.icon = _make_icon_bitmap(IDLE)
        print("Models loaded. Hold your hotkey and speak.")

    def _on_text(self, text: str) -> None:
        try:
            paste_text(text)
        except Exception as e:
            print(f"Paste failed ({e}); text left on clipboard")
            copy_only(text)

    def _on_utterance_done(self) -> None:
        self.icon.icon = _make_icon_bitmap(IDLE)

    # --- tray menu actions ---------------------------------------------------

    def _toggle_enabled(self, _icon, _item) -> None:
        self.enabled = not self.enabled

    def _toggle_polish(self, _icon, _item) -> None:
        self.pipeline.polish_enabled = not self.pipeline.polish_enabled

    def _quit(self, _icon, _item) -> None:
        self._watchdog_stop.set()
        try:
            self.hotkey.stop()
        except Exception:
            pass
        self.icon.stop()

    # --- hotkey callbacks (enqueue only, never block the listener thread) ----

    def _on_press(self) -> None:
        if not self.enabled or not self.pipeline.ready or self._recording_since:
            return
        self._recording_since = time.time()
        self.icon.icon = _make_icon_bitmap(RECORDING)
        self._audio_events.put("start")

    def _on_release(self) -> None:
        if not self.pipeline.ready or not self._recording_since:
            return
        self._audio_events.put("stop")

    # --- audio worker: owns all sounddevice calls, serially ------------------

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
                        self.icon.icon = _make_icon_bitmap(IDLE)
                        continue
                    self.icon.icon = _make_icon_bitmap(PROCESSING)
                    # capture tone now, while the target app is still foregrounded
                    self.pipeline.submit(audio, tone_for_app(frontmost_app_name()))
            except Exception as e:
                print(f"Audio worker error on {event!r}: {e}")
                self._recording_since = None
                self.icon.icon = _make_icon_bitmap(IDLE)

    # --- watchdog: recover from a dead listener or a missed release event ----

    def _watchdog(self) -> None:
        while not self._watchdog_stop.wait(WATCHDOG_INTERVAL_SECONDS):
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


def run_tray() -> None:
    cfg = load_config()
    AccioTray(cfg).icon.run()
