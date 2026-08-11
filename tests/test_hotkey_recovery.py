from accio.config import Config
from accio.hotkey import PushToTalk


def test_callback_exception_does_not_propagate_to_listener():
    # an exception escaping into pynput kills its listener thread silently;
    # the wrapper must swallow it
    def boom():
        raise RuntimeError("kaboom")

    key = next(iter(PushToTalk("alt_r", boom, boom).keys))
    ptt = PushToTalk("alt_r", on_start=boom, on_stop=boom)
    ptt._on_press(key)  # must not raise
    assert ptt._held_key is key
    ptt._on_release(key)  # must not raise
    assert ptt._held_key is None


def test_reset_held_clears_stuck_state():
    events = []
    ptt = PushToTalk("alt_r", on_start=lambda: events.append("start"), on_stop=lambda: events.append("stop"))
    key = next(iter(ptt.keys))
    ptt._on_press(key)
    assert ptt._held_key is key
    # macOS dropped the release event; watchdog resets
    ptt.reset_held()
    assert ptt._held_key is None
    # next press starts a fresh recording instead of being swallowed
    ptt._on_press(key)
    assert events == ["start", "start"]


def test_multiple_keys_any_triggers():
    events = []
    ptt = PushToTalk("alt_r,shift_r", on_start=lambda: events.append("start"), on_stop=lambda: events.append("stop"))
    from accio.hotkey import KEY_MAP
    ptt._on_press(KEY_MAP["shift_r"])  # external keyboard's right shift
    ptt._on_release(KEY_MAP["shift_r"])
    # alt press while shift-hold released does not leak stop
    ptt._on_press(KEY_MAP["alt_r"])
    ptt._on_release(KEY_MAP["alt_r"])
    assert events == ["start", "stop", "start", "stop"]


def test_alive_reflects_listener_state():
    ptt = PushToTalk("alt_r", on_start=lambda: None, on_stop=lambda: None)
    assert ptt.alive is False  # not started


def test_max_recording_seconds_default():
    assert Config().max_recording_seconds == 120.0
