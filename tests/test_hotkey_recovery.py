from accio.config import Config
from accio.hotkey import PushToTalk


def test_callback_exception_does_not_propagate_to_listener():
    # an exception escaping into pynput kills its listener thread silently;
    # the wrapper must swallow it
    def boom():
        raise RuntimeError("kaboom")

    ptt = PushToTalk("alt_r", on_start=boom, on_stop=boom)
    ptt._on_press(ptt.key)  # must not raise
    assert ptt._held is True
    ptt._on_release(ptt.key)  # must not raise
    assert ptt._held is False


def test_reset_held_clears_stuck_state():
    events = []
    ptt = PushToTalk("alt_r", on_start=lambda: events.append("start"), on_stop=lambda: events.append("stop"))
    ptt._on_press(ptt.key)
    assert ptt._held is True
    # macOS dropped the release event; watchdog resets
    ptt.reset_held()
    assert ptt._held is False
    # next press starts a fresh recording instead of being swallowed
    ptt._on_press(ptt.key)
    assert events == ["start", "start"]


def test_alive_reflects_listener_state():
    ptt = PushToTalk("alt_r", on_start=lambda: None, on_stop=lambda: None)
    assert ptt.alive is False  # not started


def test_max_recording_seconds_default():
    assert Config().max_recording_seconds == 120.0
