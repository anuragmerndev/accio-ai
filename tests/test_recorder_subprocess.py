"""The subprocess-backed Recorder: correct framing on a clean stop, and a
kill+respawn (not a hang) when the audio helper wedges in a C call."""

import sys
import time

import numpy as np

from accio import audio
from accio.audio import Recorder

# a well-behaved fake helper: on STOP it returns 8 known float32 samples,
# framed exactly like accio.recorder_proc (4-byte big-endian length + payload).
FAKE_OK = r"""
import os, sys, struct
import numpy as np
out = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
sys.stdout = sys.stderr
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        break
    c = line.strip()
    if c == b"STOP":
        a = np.arange(8, dtype="<f4").tobytes()
        out.write(struct.pack(">I", len(a))); out.write(a); out.flush()
    elif c == b"QUIT":
        break
"""

# a wedged helper: never answers STOP (simulates a stuck CoreAudio call).
FAKE_WEDGE = r"""
import sys, time
while True:
    line = sys.stdin.buffer.readline()
    if not line:
        break
    if line.strip() == b"STOP":
        time.sleep(60)
"""


def test_clean_stop_returns_framed_audio():
    r = Recorder(proc_cmd=[sys.executable, "-u", "-c", FAKE_OK])
    r.start()
    audio_out = r.stop()
    assert list(audio_out) == list(np.arange(8, dtype=np.float32))


def test_wedged_helper_is_killed_and_respawned(monkeypatch):
    monkeypatch.setattr(audio, "IO_TIMEOUT_SECONDS", 0.3)
    r = Recorder(proc_cmd=[sys.executable, "-u", "-c", FAKE_WEDGE])
    r.monkeypatched_no_sample = True
    monkeypatch.setattr(Recorder, "_capture_wedge_stack", lambda self: None)
    r.start()
    old_pid = r._proc.pid
    t0 = time.time()
    audio_out = r.stop()  # helper never answers → times out, kills, respawns
    elapsed = time.time() - t0
    assert len(audio_out) == 0  # dropped this recording, did not hang
    assert elapsed < 3.0  # returned promptly instead of waiting on the C call
    assert r._proc.pid != old_pid  # a fresh helper is ready for the next take
    assert r._alive()


def test_duration():
    r = Recorder(proc_cmd=[sys.executable, "-u", "-c", FAKE_OK])
    assert r.duration(np.zeros(16_000, dtype=np.float32)) == 1.0
