import platform
import sys
from pathlib import Path

from accio.config import Config, load_config


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(tmp_path / "nope.toml")
    assert cfg.min_utterance_seconds == 0.3
    assert cfg.min_peak_amplitude == 0.02
    assert "um" in cfg.filler_words
    # the MLX-backed defaults are filled in by __post_init__; the windows
    # tracker just verifies they still land on a sensible non-empty string
    assert cfg.asr_model
    assert cfg.whisper_model


def test_default_backend_matches_platform():
    """Sanity: the default ASR backend is reachable from this platform."""
    if sys.platform == "darwin" and platform.machine() in {"arm64", "aarch64"}:
        assert Config().asr_backend == "parakeet"
    else:
        assert Config().asr_backend == "faster_whisper"


def test_default_llm_backend_matches_platform():
    if sys.platform != "darwin":
        # MLX-only runtime; the install must not require the user to touch
        # config.toml to fall back to Ollama.
        assert Config().llm_backend == "ollama"
    else:
        assert Config().llm_backend == "mlx"


def test_file_overrides_defaults(tmp_path: Path):
    p = tmp_path / "config.toml"
    p.write_text('llm_polish = false\nasr_model = "other/model"\n')
    cfg = load_config(p)
    assert cfg.llm_polish is False
    assert cfg.asr_model == "other/model"
    # untouched keys keep defaults
    assert cfg.min_utterance_seconds == 0.3


def test_dictionary_loads_from_json(tmp_path: Path):
    (tmp_path / "dictionary.json").write_text('{"accio": "Accio"}')
    cfg = load_config(tmp_path / "config.toml")
    assert cfg.dictionary == {"accio": "Accio"}


def test_missing_dictionary_is_empty(tmp_path: Path):
    cfg = load_config(tmp_path / "config.toml")
    assert cfg.dictionary == {}


def test_config_is_dataclass_with_expected_fields():
    fields = Config.__dataclass_fields__
    for name in (
        "asr_model",
        "whisper_model",
        "llm_model",
        "llm_polish",
        "llm_backend",
        "filler_words",
        "hotkey",
        "dictionary",
        "faster_whisper_device",
        "faster_whisper_compute_type",
    ):
        assert name in fields
