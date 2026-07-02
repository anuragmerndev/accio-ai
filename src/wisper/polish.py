"""Optional LLM polish pass: tone, self-corrections, punctuation via a small local model."""

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


def sanitize_output(text: str) -> str:
    text = text.strip().split("\n\n")[0].strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text.strip()


class Polisher:
    def __init__(self, model_name: str):
        from mlx_lm import load

        self.model, self.tokenizer = load(model_name)

    def polish(self, transcript: str, tone: str = "default") -> str:
        from mlx_lm import generate

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_prompt(
                    "um so the meeting is at three no wait four pm", "default"
                ),
            },
            {"role": "assistant", "content": "The meeting is at 4 pm."},
            {"role": "user", "content": build_prompt(transcript, tone)},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        raw = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=512)
        result = sanitize_output(raw)
        # a polish pass must never destroy the transcript
        return result if result else transcript
