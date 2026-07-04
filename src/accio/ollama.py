"""Minimal client for a local Ollama daemon."""

import json
import urllib.request


def chat(url: str, model: str, messages: list[dict[str, str]], timeout: float = 30) -> str:
    body = json.dumps(
        {"model": model, "stream": False, "keep_alive": "30m", "messages": messages}
    ).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["message"]["content"]
