"""The watchdog catches a dropped key-release event by polling physical key
state — but only after two consecutive 'up' checks, so it never truncates
someone who is still holding the key and speaking."""

import queue
import time

from accio.app import AccioApp


class _Hotkey:
    alive = True

    def __init__(self):
        self.reset_calls = 0

    def reset_held(self):
        self.reset_calls += 1


def _make_app(key_down: bool):
    a = object.__new__(AccioApp)
    a.hotkey = _Hotkey()
    a._recording_since = time.time()  # recent, so the max-length cap doesn't fire
    a._trigger_names = ["shift_r"]
    a._release_misses = 0
    a._audio_events = queue.Queue()
    a._any_trigger_down = lambda: key_down

    class _Cfg:
        max_recording_seconds = 120.0

    a.cfg = _Cfg()
    return a


def _events(a):
    out = []
    while not a._audio_events.empty():
        out.append(a._audio_events.get())
    return out


def test_missed_release_stops_after_two_checks():
    a = _make_app(key_down=False)
    a._watchdog(None)
    assert _events(a) == []  # one miss: not yet
    a._watchdog(None)
    assert _events(a) == ["stop"]  # second consecutive miss: stop, keep audio
    assert a.hotkey.reset_calls == 1


def test_key_still_held_never_stops_and_resets():
    a = _make_app(key_down=False)
    a._watchdog(None)  # one miss
    a._any_trigger_down = lambda: True  # user is holding and speaking
    a._watchdog(None)
    assert a._release_misses == 0  # streak reset
    a._watchdog(None)
    assert _events(a) == []  # never truncated


def test_streak_resets_when_not_recording():
    a = _make_app(key_down=False)
    a._watchdog(None)  # one miss
    a._recording_since = None
    a._watchdog(None)
    assert a._release_misses == 0
