"""The menu Stop button finalizes a stuck recording (processes captured audio)
rather than discarding it, and clears pending/held state."""

import queue
import threading

from accio import app
from accio.app import AccioApp


class _Hotkey:
    def __init__(self):
        self.reset_calls = 0

    def reset_held(self):
        self.reset_calls += 1


def _make_app():
    a = object.__new__(AccioApp)
    a._recording_since = None
    a._pending_start = False
    a._start_timer = None
    a._press_lock = threading.Lock()
    a._audio_events = queue.Queue()
    a.hotkey = _Hotkey()
    a.title = app.IDLE
    return a


def _events(a):
    out = []
    while not a._audio_events.empty():
        out.append(a._audio_events.get())
    return out


def test_stop_finalizes_active_recording():
    a = _make_app()
    a._recording_since = 123.0  # mic is open, waiting on a missed release
    a._stop(None)
    # queues a stop so the worker transcribes + pastes the captured audio
    assert _events(a) == ["stop"]
    assert a.hotkey.reset_calls == 1


def test_stop_cancels_pending_tap_without_recording():
    a = _make_app()
    a._pending_start = True
    cancelled = []
    a._start_timer = type("T", (), {"cancel": lambda self: cancelled.append(True)})()
    a._stop(None)
    assert a._pending_start is False
    assert cancelled == [True]
    assert _events(a) == []  # nothing to process
    assert a.title == app.IDLE
