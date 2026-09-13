"""Microphone capture, isolated in a subprocess.

The recorder drives a helper process (accio.recorder_proc) that owns
sounddevice/PortAudio. All the parent ever does is write a command and read the
result off a pipe with a timeout — it never calls CoreAudio, so a CoreAudio hang
can't wedge the app. If the helper wedges, the parent samples it for diagnosis,
SIGKILLs it, and respawns — the one recovery a stuck C call actually allows.
"""

import datetime
import os
import select
import struct
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
# a START/STOP round-trip is near-instant; longer means the helper wedged in a
# CoreAudio call and must be killed rather than waited on.
IO_TIMEOUT_SECONDS = 5.0


class Recorder:
    def __init__(self, sample_rate: int = SAMPLE_RATE, proc_cmd: list[str] | None = None):
        self.sample_rate = sample_rate
        # -u: unbuffered child stdio so our framed bytes arrive promptly
        self._cmd = proc_cmd or [sys.executable, "-u", "-m", "accio.recorder_proc"]
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._spawn()

    def _spawn(self) -> None:
        self._proc = subprocess.Popen(
            self._cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            bufsize=0,  # unbuffered: we frame the stream ourselves
        )

    def _kill_and_respawn(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=2)
            except Exception:
                pass
        self._spawn()

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        with self._lock:
            if not self._alive():
                self._spawn()
            try:
                self._proc.stdin.write(b"START\n")
                self._proc.stdin.flush()
            except Exception as e:
                print(f"recorder start: helper pipe broke ({e}); respawning")
                self._kill_and_respawn()

    def stop(self) -> np.ndarray:
        with self._lock:
            if not self._alive():
                self._spawn()
                return np.zeros(0, dtype=np.float32)
            try:
                self._proc.stdin.write(b"STOP\n")
                self._proc.stdin.flush()
            except Exception as e:
                print(f"recorder stop: helper pipe broke ({e}); respawning")
                self._kill_and_respawn()
                return np.zeros(0, dtype=np.float32)
            audio = self._read_audio(IO_TIMEOUT_SECONDS)
            if audio is None:  # helper wedged in CoreAudio
                self._capture_wedge_stack()
                self._kill_and_respawn()
                return np.zeros(0, dtype=np.float32)
            return audio

    def _read_audio(self, timeout: float) -> np.ndarray | None:
        import time

        fd = self._proc.stdout.fileno()
        deadline = time.time() + timeout
        header = self._read_exact(fd, 4, deadline)
        if header is None:
            return None
        (n,) = struct.unpack(">I", header)
        # payload can be a few MB for a long take; reading a ready pipe is fast,
        # so a small fixed extension past the header deadline is plenty
        payload = self._read_exact(fd, n, deadline + 5)
        if payload is None:
            return None
        return np.frombuffer(payload, dtype="<f4").copy()

    @staticmethod
    def _read_exact(fd: int, n: int, deadline: float) -> bytes | None:
        import time

        buf = b""
        while len(buf) < n:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            r, _, _ = select.select([fd], [], [], remaining)
            if not r:
                return None
            chunk = os.read(fd, n - len(buf))
            if not chunk:  # EOF: helper died
                return None
            buf += chunk
        return buf

    def _capture_wedge_stack(self) -> None:
        # snapshot the wedged helper's native stack before killing it, so the
        # exact CoreAudio call it's stuck in is on record for next time
        pid = self._proc.pid if self._proc else None
        if pid is None:
            return
        out = Path.home() / ".accio" / f"wedge-{datetime.datetime.now():%Y%m%d-%H%M%S}.txt"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w") as f:
                subprocess.run(
                    ["sample", str(pid), "2"], stdout=f, stderr=subprocess.DEVNULL, timeout=8
                )
            print(f"recorder helper wedged; native stack captured → {out}")
        except Exception as e:
            print(f"recorder helper wedged; could not sample it ({e})")

    def duration(self, audio: np.ndarray) -> float:
        return len(audio) / self.sample_rate
