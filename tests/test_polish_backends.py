from wisper.config import Config
from wisper.polish import SYSTEM_PROMPT, build_messages


def test_messages_include_system_and_fewshot_and_transcript():
    msgs = build_messages("hello world", "chat")
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert "hello world" in msgs[-1]["content"]


def test_config_backend_defaults():
    cfg = Config()
    assert cfg.llm_backend == "mlx"
    assert cfg.ollama_model == "llama3.2"
    assert cfg.ollama_url == "http://localhost:11434"
