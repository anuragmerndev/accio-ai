from pathlib import Path

from accio.config import Config, load_config


def test_defaults_when_no_file(tmp_path: Path):
    cfg = load_config(tmp_path / "nope.toml")
    assert cfg.asr_model == "mlx-community/parakeet-tdt-0.6b-v2"
    assert cfg.llm_polish is True
    assert cfg.min_utterance_seconds == 0.3
    assert cfg.min_peak_amplitude == 0.02
    assert "um" in cfg.filler_words


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
    for name in ("asr_model", "llm_model", "llm_polish", "filler_words", "hotkey", "dictionary"):
        assert name in fields
