"""Config loading: ~/.wisper/config.toml merged over defaults, plus dictionary.json."""

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from wisper.cleanup import DEFAULT_FILLERS

CONFIG_DIR = Path.home() / ".wisper"


@dataclass
class Config:
    asr_model: str = "mlx-community/parakeet-tdt-0.6b-v2"
    llm_model: str = "mlx-community/Qwen2.5-1.5B-Instruct-4bit"
    llm_polish: bool = True
    llm_backend: str = "mlx"  # "mlx" or "ollama"
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    hotkey: str = "alt_r"
    min_utterance_seconds: float = 0.3
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
