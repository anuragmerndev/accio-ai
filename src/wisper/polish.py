"""Optional LLM polish pass: tone, self-corrections, punctuation via a small local model.

Two interchangeable backends, both fully local:
- MlxPolisher: mlx-lm in-process (default, no daemon needed)
- OllamaPolisher: local Ollama daemon over localhost HTTP
"""

import json
import urllib.request

TONE_HINTS = {
    "chat": "Keep it casual and short, like a chat message.",
    "email": "Use a clear, professional tone suitable for email.",
    "code": "Preserve technical terms, identifiers, and symbols exactly as spoken.",
    "default": "Use a natural, neutral tone.",
}

SYSTEM_PROMPT = (
    "You clean up dictated speech. Fix punctuation and capitalization, remove filler "
    "words and false starts, and apply self-corrections (if the speaker corrects "
    "themselves, keep only the correction). Do not add, summarize, or explain "
    "anything. Reply with the cleaned text only."
)


def build_prompt(transcript: str, tone: str) -> str:
    hint = TONE_HINTS.get(tone, TONE_HINTS["default"])
    return f"{hint}\n\nDictated speech:\n{transcript}"


# few-shot pairs teaching the correction patterns small models get wrong:
# "no wait Y", "no not X, Y", and bare "no Y" replacements
FEW_SHOTS = [
    ("um so the meeting is at three no wait four pm", "The meeting is at 4 pm."),
    (
        "Let's do the launch on Tuesday. No, not Tuesday. On Thursday.",
        "Let's do the launch on Thursday.",
    ),
    ("Make the header green, no orange.", "Make the header orange."),
]


def build_messages(transcript: str, tone: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for spoken, cleaned in FEW_SHOTS:
        messages.append({"role": "user", "content": build_prompt(spoken, "default")})
        messages.append({"role": "assistant", "content": cleaned})
    messages.append({"role": "user", "content": build_prompt(transcript, tone)})
    return messages


def sanitize_output(text: str) -> str:
    text = text.strip().split("\n\n")[0].strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text.strip()


class MlxPolisher:
    def __init__(self, model_name: str):
        from mlx_lm import load

        self.model, self.tokenizer = load(model_name)

    def polish(self, transcript: str, tone: str = "default") -> str:
        from mlx_lm import generate

        prompt = self.tokenizer.apply_chat_template(
            build_messages(transcript, tone), tokenize=False, add_generation_prompt=True
        )
        raw = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=512)
        result = sanitize_output(raw)
        # a polish pass must never destroy the transcript
        return result if result else transcript


class OllamaPolisher:
    def __init__(self, model_name: str, url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.url = url.rstrip("/")
        self._chat("ping", "default")  # warm the model and fail fast if daemon is down

    def _chat(self, transcript: str, tone: str) -> str:
        body = json.dumps(
            {
                "model": self.model_name,
                "stream": False,
                "keep_alive": "30m",
                "messages": build_messages(transcript, tone),
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.url}/api/chat", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)["message"]["content"]

    def polish(self, transcript: str, tone: str = "default") -> str:
        result = sanitize_output(self._chat(transcript, tone))
        return result if result else transcript


# backwards-compatible name for the default backend
Polisher = MlxPolisher


def make_polisher(cfg):
    if cfg.llm_backend == "ollama":
        return OllamaPolisher(cfg.ollama_model, cfg.ollama_url)
    return MlxPolisher(cfg.llm_model)
