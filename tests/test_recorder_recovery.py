"""A single recorder wedge rebuilds cheaply; a repeat wedge (process-global
PortAudio is dead) escalates to a process restart."""

from accio import app
from accio.app import AccioApp


def _make_app():
    a = object.__new__(AccioApp)
    a._wedge_count = 0
    a._recording_since = 123.0
    a.recorder = None
    a.title = app.RECORDING
    a._restarts = 0
    a._restart_process = lambda: setattr(a, "_restarts", a._restarts + 1)
    return a


def test_single_wedge_rebuilds_without_restart():
    a = _make_app()
    a._recover_recorder("stop")
    assert a._wedge_count == 1
    assert a._restarts == 0
    assert a.recorder is not None  # fresh recorder
    assert a.title == app.IDLE
    assert a._recording_since is None


def test_second_consecutive_wedge_restarts():
    a = _make_app()
    a._recover_recorder("stop")
    a._recover_recorder("start")
    assert a._wedge_count == 2
    assert a._restarts == 1  # escalated to a process restart
