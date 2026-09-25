"""Audio-capture subprocess: owns sounddevice/PortAudio so a CoreAudio hang
stays out of the main app.

Why a subprocess and not a thread: recorder.start()/stop() are blocking C calls
(PortAudio → CoreAudio) with no timeout. When the audio HAL wedges they never
return, and a thread stuck in a C call can't be interrupted or reset from
Python — PortAudio is a process-global, so a fresh stream in the same process
hits the same dead library. A subprocess CAN be killed (SIGKILL) and respawned,
so the parent stays responsive no matter what CoreAudio does.

Protocol (parent drives; see accio.audio.Recorder):
  parent → child, text lines on stdin: b"START\n", b"STOP\n", b"QUIT\n"
  child → parent, on STOP, on a clean binary channel (dup of stdout):
      4-byte big-endian length N, then N bytes of little-endian float32 mono PCM
The parent reads that with a timeout; on timeout it samples + SIGKILLs the child.
"""

import os
import struct
import sys

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000


def main() -> None:
    # claim a clean binary channel for the protocol, then point stray stdout
    # (sounddevice/numpy chatter) at stderr so it can't corrupt the framing
    out = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    sys.stdout = sys.stderr

    chunks: list[np.ndarray] = []
    stream: sd.InputStream | None = None

    def on_audio(indata, frames, time_info, status) -> None:
        chunks.append(indata[:, 0].copy())

    # warm CoreAudio now (at startup, while the app is still loading models) so
    # the first real recording doesn't pay the multi-second cold-open cost — that
    # cold latency, not a true hang, is what a tight stop-timeout misfires on.
    try:
        warm = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=on_audio
        )
        warm.start()
        warm.stop()
        warm.close()
        chunks = []
    except Exception as e:
        print(f"recorder warmup failed: {e}", file=sys.stderr)

    while True:
        line = sys.stdin.buffer.readline()
        if not line:  # parent closed the pipe
            break
        cmd = line.strip()
        if cmd == b"START":
            chunks = []
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=on_audio
            )
            stream.start()  # may wedge here; parent detects it at STOP and kills us
        elif cmd == b"STOP":
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
            audio = (
                np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
            )
            data = audio.astype("<f4").tobytes()
            out.write(struct.pack(">I", len(data)))
            out.write(data)
            out.flush()
        elif cmd == b"QUIT":
            break


if __name__ == "__main__":
    main()
