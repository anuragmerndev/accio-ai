"""The watchdog catches a dropped key-release event fast by polling physical
key state, instead of waiting for the max-length cap."""

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
    a._trigger_vks = [60]  # right shift
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


def test_missed_release_stops_when_key_not_down():
    a = _make_app(key_down=False)  # we think we're recording, but nothing is held
    a._watchdog(None)
    assert _events(a) == ["stop"]
    assert a.hotkey.reset_calls == 1


def test_key_still_held_keeps_recording():
    a = _make_app(key_down=True)  # legitimately holding to talk
    a._watchdog(None)
    assert _events(a) == []  # not stopped
