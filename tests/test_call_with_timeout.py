"""_call_with_timeout guards the app against a wedged CoreAudio call: it must
return promptly on a hang, pass results through, and re-raise exceptions."""

import time

import pytest

from accio.app import _call_with_timeout


def test_returns_result_on_success():
    ok, value, elapsed = _call_with_timeout(lambda: 42, timeout=1.0)
    assert ok is True
    assert value == 42
    assert elapsed < 1.0


def test_times_out_on_a_wedged_call():
    ok, value, elapsed = _call_with_timeout(lambda: time.sleep(5), timeout=0.2)
    assert ok is False  # abandoned; the sleeping thread is left to die
    assert value is None
    assert elapsed < 1.0  # returned promptly, did not wait the full 5s


def test_reraises_exception():
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        _call_with_timeout(boom, timeout=1.0)
