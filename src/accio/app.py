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

from accio import history
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
# how many past dictations to keep in the menu-bar "Recent" submenu
RECENT_COUNT = 10
# macOS virtual keycodes for our hotkeys (names match accio.hotkey.KEY_MAP),
# used to poll a non-modifier key's physical state (f13). Modifier keys are
# polled by flag mask instead — see _MODIFIER_FLAG — because per-keycode
# CGEventSourceKeyState misreports a held right-modifier as "up".
_HOTKEY_VK = {
    "alt_r": 61, "alt_l": 58,
    "cmd_r": 54, "ctrl_r": 62,
    "shift_r": 60, "shift_l": 56,
    "f13": 105,
}
# hotkey name → the Quartz modifier-flag attribute that is set while it's held.
_MODIFIER_FLAG = {
    "shift_r": "kCGEventFlagMaskShift", "shift_l": "kCGEventFlagMaskShift",
    "alt_r": "kCGEventFlagMaskAlternate", "alt_l": "kCGEventFlagMaskAlternate",
    "cmd_r": "kCGEventFlagMaskCommand",
    "ctrl_r": "kCGEventFlagMaskControl",
}


class _TimestampedStream:
    """Prefix every stdout/stderr line with a timestamp, so a log that ends
    mid-operation pinpoints exactly when — and on which line — it froze."""

    def __init__(self, stream):
        self._stream = stream
        self._at_line_start = True

    def write(self, text: str) -> None:
        if not text:
            return
        stamp = time.strftime("%H:%M:%S ")
        out = []
        for ch in text:
            if self._at_line_start and ch != "\n":
                out.append(stamp)
                self._at_line_start = False
            out.append(ch)
            if ch == "\n":
                self._at_line_start = True
        self._stream.write("".join(out))

    def flush(self) -> None:
        self._stream.flush()


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
        self._recent_slots = [rumps.MenuItem("(empty)") for _ in range(RECENT_COUNT)]
        recent_menu = rumps.MenuItem("Recent")
        for slot in self._recent_slots:
            recent_menu.add(slot)
        self.menu = [
            rumps.MenuItem("Enabled", callback=self._toggle_enabled),
            rumps.MenuItem("LLM polish", callback=self._toggle_polish),
            rumps.MenuItem("Stop", callback=self._stop),
            recent_menu,
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
        self._trigger_names = [
            n.strip() for n in cfg.hotkey.split(",") if n.strip() in _HOTKEY_VK
        ]
        self._release_misses = 0  # consecutive watchdog ticks with no key down
        self._press_lock = threading.Lock()
        self._audio_events: queue.Queue = queue.Queue()
        threading.Thread(target=self._audio_worker, daemon=True).start()
        ensure_input_monitoring()
        self.hotkey = PushToTalk(cfg.hotkey, self._on_press, self._on_release)
        self.hotkey.start()
        self._watchdog_timer = rumps.Timer(self._watchdog, WATCHDOG_INTERVAL_SECONDS)
        self._watchdog_timer.start()
        self._refresh_recent()  # populate from prior sessions' history

    def _on_models_ready(self, llm_available: bool) -> None:
        if not llm_available:
            self.menu["LLM polish"].state = False
        self.title = IDLE
        print("Models loaded. Hold your hotkey and speak.")

    def _on_text(self, text: str, origin: str = "") -> None:
        # only auto-paste if the same app is still focused; if you moved away
        # while it was transcribing, hold the text on the clipboard instead of
        # firing ⌘V into the wrong place. Either way it's saved to history.
        current = frontmost_app_name()
        if self._paste_target_matches(origin, current):
            try:
                paste_text(text)
            except Exception as e:
                print(f"Paste failed ({e}); text left on clipboard")
                copy_only(text)
            pasted = True
        else:
            copy_only(text)
            print(f"focus moved ({origin!r} → {current!r}); held on clipboard")
            self._notify_ready(text)
            pasted = False
        history.append(text, pasted=pasted)
        self._refresh_recent()

    @staticmethod
    def _paste_target_matches(origin: str, current: str) -> bool:
        # no origin recorded → preserve the old always-paste behavior
        return not origin or origin == current

    def _notify_ready(self, text: str) -> None:
        try:
            preview = (text[:40] + "…") if len(text) > 41 else text
            rumps.notification("Accio", "Dictation ready — ⌘V to paste", preview)
        except Exception as e:
            print(f"notification failed ({e}); text is on the clipboard and in Recent")

    def _copy_recent(self, sender) -> None:
        copy_only(getattr(sender, "_full_text", ""))

    def _refresh_recent(self) -> None:
        items = history.recent(RECENT_COUNT)
        for slot, rec in zip(self._recent_slots, items):
            t = rec.get("text", "")
            slot.title = (t[:47] + "…") if len(t) > 48 else (t or "(empty)")
            slot._full_text = t
            slot.set_callback(self._copy_recent)
        for slot in self._recent_slots[len(items):]:
            slot.title = "(empty)"
            slot._full_text = ""
            slot.set_callback(None)  # disable empty slots

    def _on_utterance_done(self) -> None:
        self.title = IDLE

    def _stop(self, _item) -> None:
        # manual equivalent of releasing the hotkey: finalize the current
        # recording (transcribe + paste what was captured) and clear any stuck
        # press state so the next hotkey works. Recovers a missed-release stall.
        with self._press_lock:
            # never opened the mic (still inside the hold window): just cancel
            if self._pending_start:
                self._pending_start = False
                if self._start_timer is not None:
                    self._start_timer.cancel()
            recording = self._recording_since is not None
        self.hotkey.reset_held()  # clear phantom held-key state
        if recording:
            self._audio_events.put("stop")  # worker stops stream, transcribes, pastes
        else:
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
        # recorder.start()/stop() are subprocess-backed and self-healing: they
        # return promptly even when the audio helper wedges (it gets killed and
        # respawned), so no in-process timeout/restart is needed here.
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
                    # capture tone + origin app now, while the target is still
                    # frontmost — origin decides where the result may auto-paste
                    origin = frontmost_app_name()
                    self.pipeline.submit(audio, tone_for_app(origin), origin)
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
        # macOS drops modifier release events (right Shift especially), leaving
        # a recording running until the max-length cap. Catch it faster by
        # polling the trigger's real state: if we think we're recording but the
        # key isn't down for TWO consecutive checks (~10s), the release was
        # missed — stop and keep the audio. Two checks + reading modifier flags
        # (not per-keycode, which misreports a held modifier) avoids truncating
        # someone who is simply still holding the key and speaking.
        if not self._recording_since:
            self._release_misses = 0
        elif self._trigger_names:
            if self._any_trigger_down():
                self._release_misses = 0
            else:
                self._release_misses += 1
                if self._release_misses >= 2:
                    print("trigger key up for two checks; stopping (missed release)")
                    self._release_misses = 0
                    self.hotkey.reset_held()
                    self._audio_events.put("stop")
                    return
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

    def _any_trigger_down(self) -> bool:
        import Quartz

        state = Quartz.kCGEventSourceStateHIDSystemState
        # modifier keys: read the live flag mask (reliable for a held modifier)
        flags = Quartz.CGEventSourceFlagsState(state)
        for name in self._trigger_names:
            attr = _MODIFIER_FLAG.get(name)
            if attr and flags & getattr(Quartz, attr):
                return True
        # non-modifier keys (e.g. f13): per-keycode state is fine
        for name in self._trigger_names:
            if name not in _MODIFIER_FLAG and Quartz.CGEventSourceKeyState(
                state, _HOTKEY_VK[name]
            ):
                return True
        return False


def main() -> None:
    import sys

    sys.stdout = _TimestampedStream(sys.stdout)
    sys.stderr = _TimestampedStream(sys.stderr)
    cfg = load_config()
    AccioApp(cfg).run()
