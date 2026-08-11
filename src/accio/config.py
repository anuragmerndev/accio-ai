"""Config loading: ~/.accio/config.toml merged over defaults, plus dictionary.json."""

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from accio.cleanup import DEFAULT_FILLERS

CONFIG_DIR = Path.home() / ".accio"


@dataclass
class Config:
    asr_backend: str = "parakeet"  # "parakeet" (fast, English) or "whisper" (multilingual)
    asr_model: str = "mlx-community/parakeet-tdt-0.6b-v2"
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"
    polish_languages: list[str] = field(default_factory=lambda: ["en"])
    romanize_languages: list[str] = field(default_factory=list)  # e.g. ["hi"] → Hinglish
    romanize_model: str = "llama3.2"
    llm_model: str = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
    llm_polish: bool = True
    llm_backend: str = "mlx"  # "mlx" or "ollama"
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    hotkey: str = "alt_r,shift_r"
    min_utterance_seconds: float = 0.3
    # skip audio too quiet to be speech — stops Whisper's "Thank you" silence
    # hallucination from being pasted (peak amplitude, 0..1)
    min_peak_amplitude: float = 0.02
    # watchdog force-stops a recording after this long — recovers the stuck
    # 🔴 state when macOS drops the hotkey's release event
    max_recording_seconds: float = 120.0
    filler_words: list[str] = field(default_factory=lambda: list(DEFAULT_FILLERS))
    dictionary: dict[str, str] = field(default_factory=dict)


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
    return cfg
