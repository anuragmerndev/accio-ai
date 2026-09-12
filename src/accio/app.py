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
# opening/closing the mic should be near-instant; longer means a CoreAudio call
# has wedged (audio-daemon/device hiccup). A wedged C call can't be interrupted
# from Python, so we abandon that call and rebuild the recorder instead of
# freezing the whole app forever.
RECORDER_TIMEOUT_SECONDS = 5.0
# macOS virtual keycodes for the modifier keys we support as hotkeys, used to
# poll real physical key state (CGEventSourceKeyState) and catch a dropped
# release event. Names match accio.hotkey.KEY_MAP.
_HOTKEY_VK = {
    "alt_r": 61, "alt_l": 58,
    "cmd_r": 54, "ctrl_r": 62,
    "shift_r": 60, "shift_l": 56,
    "f13": 105,
}


def _call_with_timeout(fn, timeout: float):
    """Run fn() on a throwaway thread, waiting up to `timeout`. Returns
    (ok, result, elapsed). On timeout the thread is abandoned (a blocked
    CoreAudio C call is uninterruptible), so the caller must discard whatever
    fn was operating on rather than reuse it."""
    box: dict = {}

    def run():
        try:
            box["value"] = fn()
        except Exception as e:  # surfaced on the caller thread below
            box["error"] = e

    t = threading.Thread(target=run, daemon=True)
    t0 = time.time()
    t.start()
    t.join(timeout)
    elapsed = time.time() - t0
    if t.is_alive():
        return False, None, elapsed
    if "error" in box:
        raise box["error"]
    return True, box.get("value"), elapsed


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
        self.menu = [
            rumps.MenuItem("Enabled", callback=self._toggle_enabled),
            rumps.MenuItem("LLM polish", callback=self._toggle_polish),
            rumps.MenuItem("Stop", callback=self._stop),
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
        self._wedge_count = 0  # consecutive recorder wedges; triggers restart
        self._trigger_vks = [
            _HOTKEY_VK[n.strip()]
            for n in cfg.hotkey.split(",")
            if n.strip() in _HOTKEY_VK
        ]
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
        print("→ paste")
        t0 = time.time()
        try:
            paste_text(text)
        except Exception as e:
            print(f"Paste failed ({e}); text left on clipboard")
            copy_only(text)
        print(f"← paste {time.time() - t0:.2f}s")

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
        while True:
            event = self._audio_events.get()
            try:
                if event == "start":
                    ok, _, dt = _call_with_timeout(
                        self.recorder.start, RECORDER_TIMEOUT_SECONDS
                    )
                    if not ok:
                        self._recover_recorder("start")
                    else:
                        self._wedge_count = 0
                        if dt > 0.5:
                            print(f"recorder.start slow: {dt:.2f}s")
                elif event == "stop":
                    ok, audio, dt = _call_with_timeout(
                        self.recorder.stop, RECORDER_TIMEOUT_SECONDS
                    )
                    self._recording_since = None
                    if not ok:
                        self._recover_recorder("stop")
                        continue
                    self._wedge_count = 0
                    if dt > 0.5:
                        print(f"recorder.stop slow: {dt:.2f}s")
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

    def _recover_recorder(self, where: str) -> None:
        # a CoreAudio call wedged. First try a cheap rebuild in case it was a
        # transient hiccup; the fresh Recorder still shares the process-global
        # PortAudio library, so if that library itself is wedged the very next
        # start/stop wedges too. On a repeat wedge, only a process restart clears
        # it — launchd relaunches us with a fresh audio subsystem.
        # ponytail: each wedge leaks one blocked daemon thread; the escalating
        # restart caps the damage. Killing a thread mid-C-call isn't safe.
        self._wedge_count += 1
        print(
            f"recorder.{where} wedged (>{RECORDER_TIMEOUT_SECONDS}s); "
            f"rebuilding recorder (wedge #{self._wedge_count}), dropping this recording"
        )
        self.recorder = Recorder()
        self._recording_since = None
        self.title = IDLE
        if self._wedge_count >= 2:
            print("audio subsystem wedged repeatedly; restarting the app to reset it")
            self._restart_process()

    def _restart_process(self) -> None:
        import os

        from accio import service

        try:
            service.start()  # launchctl kickstart -k: launchd kills + relaunches us
        except Exception as e:
            # not under launchd (dev run) or kickstart failed: abort so the
            # LaunchAgent's KeepAlive(Crashed) relaunches a clean process
            print(f"kickstart failed ({e}); aborting for relaunch")
            os.abort()

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
        # a recording running until the max-length cap. Catch it fast by polling
        # the key's real physical state: if we think we're recording but no
        # trigger key is actually down, the release was missed — stop now and
        # keep the audio, instead of holding the mic open for the full cap (a
        # long-stale stream is what wedges CoreAudio on close).
        if self._recording_since and self._trigger_vks and not self._any_trigger_down():
            print("no trigger key down but still recording (missed release); stopping")
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
        from Quartz import (
            CGEventSourceKeyState,
            kCGEventSourceStateCombinedSessionState,
        )

        return any(
            CGEventSourceKeyState(kCGEventSourceStateCombinedSessionState, vk)
            for vk in self._trigger_vks
        )


def main() -> None:
    import sys

    sys.stdout = _TimestampedStream(sys.stdout)
    sys.stderr = _TimestampedStream(sys.stderr)
    cfg = load_config()
    AccioApp(cfg).run()
