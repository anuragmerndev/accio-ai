"""Config loading: ~/.accio/config.toml merged over defaults, plus dictionary.json.

Defaults are platform-aware so a fresh install works without a config file on
both macOS (MLX-backed) and Windows (CTranslate2-backed). The shape of the
dataclass stays populated by all platforms so users can copy config.toml
between platforms and just flip `asr_backend`.
"""

import json
import platform
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from accio.cleanup import DEFAULT_FILLERS

CONFIG_DIR = Path.home() / ".accio"


def _default_asr_backend() -> str:
    # MLX is Apple-Silicon only; on Windows (or any non-darwin) we fall back to
    # the CTranslate2-based faster-whisper backend so the first launch works
    # without requiring the user to install Apple-only wheels.
    if sys.platform == "darwin" and platform.machine() in {"arm64", "aarch64"}:
        return "parakeet"
    return "faster_whisper"


def _default_models() -> tuple[str, str, str]:
    """Return (parakeet_model, whisper_model, llm_model) for this platform."""
    if sys.platform == "darwin" and platform.machine() in {"arm64", "aarch64"}:
        return (
            "mlx-community/parakeet-tdt-0.6b-v2",
            "mlx-community/whisper-large-v3-turbo",
            "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        )
    # On Windows/other Parakeet-MLX is unavailable, so the whisper model carries
    # the load via faster-whisper. `large-v3` runs on CPU; users with NVIDIA GPUs
    # can switch to `large-v3` compute_type=float16 in their config.toml.
    return (
        "mlx-community/parakeet-tdt-0.6b-v2",  # unused unless user switches to parakeet
        "large-v3",
        "qwen2.5:1.5b",  # Ollama tag — default llm_backend is ollama on Windows
    )


@dataclass
class Config:
    asr_backend: str = field(default_factory=_default_asr_backend)
    asr_model: str = ""  # filled in __post_init__
    whisper_model: str = ""  # filled in __post_init__
    polish_languages: list[str] = field(default_factory=lambda: ["en"])
    romanize_languages: list[str] = field(default_factory=list)  # e.g. ["hi"] -> Hinglish
    romanize_model: str = "llama3.2"
    llm_model: str = ""  # filled in __post_init__
    llm_polish: bool = True
    llm_backend: str = "mlx"  # "mlx" or "ollama"
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    hotkey: str = "alt_r"
    min_utterance_seconds: float = 0.3
    # skip audio too quiet to be speech — stops Whisper's "Thank you" silence
    # hallucination from being pasted (peak amplitude, 0..1)
    min_peak_amplitude: float = 0.02
    # watchdog force-stops a recording after this long — recovers the stuck
    # red state when the OS drops the hotkey's release event
    max_recording_seconds: float = 120.0
    filler_words: list[str] = field(default_factory=lambda: list(DEFAULT_FILLERS))
    dictionary: dict[str, str] = field(default_factory=dict)
    # faster-whisper knobs; only used when asr_backend == "faster_whisper"
    faster_whisper_device: str = "auto"  # "cpu", "cuda", or "auto"
    faster_whisper_compute_type: str = "int8"  # int8, int8_float16, float16, float32

    def __post_init__(self) -> None:
        # Defaults that depend on platform are filled here so the dataclass
        # stays serialisable when we introduce a toml writer later on.
        if not self.asr_model or not self.whisper_model or not self.llm_model:
            parakeet, whisper, llm = _default_models()
            self.asr_model = self.asr_model or parakeet
            self.whisper_model = self.whisper_model or whisper
            self.llm_model = self.llm_model or llm
        # On Windows there is no MLX runtime — flip the default polish backend
        # to Ollama unless the user has overridden llm_backend explicitly.
        if sys.platform != "darwin" and self.llm_backend == "mlx":
            self.llm_backend = "ollama"


def load_config(path: Path | None = None) -> Config:
    path = CONFIG_DIR / "config.toml" if path is None else path
    cfg = Config()
    if path.exists():
        data = tomllib.loads(path.read_text())
        for key, value in data.items():
            if key in Config.__dataclass_fields__:
                setattr(cfg, key, value)
    dict_path = path.parent / "dictionary.json"
    if dict_path.exists():
        cfg.dictionary = json.loads(dict_path.read_text())
    # Re-run post-init side-effects in case toml explicitly cleared one of the
    # model fields so the platforms still land on a valid default.
    cfg.__post_init__()
    return cfg
