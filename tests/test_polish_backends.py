import sys

from accio.config import Config
from accio.polish import FEW_SHOTS, SYSTEM_PROMPT, build_messages


def test_messages_include_system_and_fewshot_and_transcript():
    msgs = build_messages("hello world", "chat")
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    roles = [m["role"] for m in msgs]
    assert roles == ["system"] + ["user", "assistant"] * len(FEW_SHOTS) + ["user"]
    assert "hello world" in msgs[-1]["content"]


def test_config_ollama_defaults_stable_across_platforms():
    cfg = Config()
    assert cfg.ollama_model == "llama3.2"
    assert cfg.ollama_url == "http://localhost:11434"


def test_config_default_backend_is_reachable_on_this_platform():
    # MLX is darwin-only; on Windows the post-init flip in Config ensures users
    # get Ollama out of the box.
    if sys.platform != "darwin":
        assert Config().llm_backend == "ollama"
