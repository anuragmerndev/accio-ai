"""Regression test for the MLX thread-local stream bug: submitting utterances
from a different thread than the one that loaded the models must work."""

import subprocess
import threading
import wave
from pathlib import Path

import numpy as np
import pytest

from accio.config import Config
from accio.pipeline import Pipeline


@pytest.mark.slow
def test_pipeline_transcribes_across_threads(tmp_path: Path):
    wav = tmp_path / "utterance.wav"
    subprocess.run(
        ["say", "-o", str(wav), "--data-format=LEI16@16000", "testing the pipeline"],
        check=True,
    )
    w = wave.open(str(wav))
    audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0

    results: list[str] = []
    done = threading.Event()
    cfg = Config(llm_polish=False)
    pipe = Pipeline(
        cfg,
        on_ready=lambda llm: None,
        on_result=results.append,
        on_done=done.set,
    )

    # submit from the main thread — the bug fired whenever the inference
    # thread differed from the loading thread
    while not pipe.ready:
        pass
    pipe.submit(audio, "default")
    assert done.wait(timeout=120), "pipeline never finished"
    assert results, "no transcription produced"
    assert "pipeline" in results[0].lower()

    # second utterance must also work (stream reuse)
    done.clear()
    results.clear()
    pipe.submit(audio, "default")
    assert done.wait(timeout=60)
    assert "pipeline" in results[0].lower()
