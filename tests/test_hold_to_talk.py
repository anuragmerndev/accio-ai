"""Right Shift doubles as a typing key: a quick tap must never open the mic,
only a deliberate hold should start recording."""

import threading
import time

from accio import app
from accio.app import AccioApp


def _make_app():
    # bypass rumps/pipeline/hotkey wiring in __init__; wire only what the
    # press/release state machine touches
    a = object.__new__(AccioApp)
    a.enabled = True
    a._recording_since = None
    a._pending_start = False
    a._start_timer = None
    a._press_lock = threading.Lock()
    a._audio_events = __import__("queue").Queue()
    a.title = app.IDLE

    class _Ready:
        ready = True

    a.pipeline = _Ready()
    return a


def _events(a):
    out = []
    while not a._audio_events.empty():
        out.append(a._audio_events.get())
    return out


def test_quick_tap_never_opens_mic(monkeypatch):
    monkeypatch.setattr(app, "HOLD_TO_TALK_SECONDS", 0.2)
    a = _make_app()
    a._on_press()
    a._on_release()  # released well within the hold window
    time.sleep(0.3)  # let the (cancelled) timer's window pass
    assert _events(a) == []
    assert a._recording_since is None


def test_hold_starts_and_stops(monkeypatch):
    monkeypatch.setattr(app, "HOLD_TO_TALK_SECONDS", 0.05)
    a = _make_app()
    a._on_press()
    time.sleep(0.15)  # held past the threshold → mic opens
    assert a._recording_since is not None
    a._on_release()
    assert _events(a) == ["start", "stop"]
