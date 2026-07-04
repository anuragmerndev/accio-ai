"""Romanize Devanagari transcripts into natural Hinglish via a local LLM.

Deterministic transliterators can't do schwa deletion ("kala meet'inga teena"),
and Qwen 1.5B swaps words; llama3.2 via Ollama produces natural Hinglish.
On any failure the original Devanagari text is returned unchanged.
"""

from accio import ollama
from accio.polish import sanitize_output

SYSTEM_PROMPT = (
    "You convert Hindi text from Devanagari to natural romanized Hinglish, the way "
    "Indians type Hindi in Latin letters. Do not translate to English. Keep English "
    "words as-is. Reply with the romanized text only."
)

FEW_SHOTS = [
    ("कल मुझे ऑफिस जाना है", "kal mujhe office jaana hai"),
    ("क्या तुमने रिपोर्ट भेज दी?", "kya tumne report bhej di?"),
]


def build_messages(text: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for devanagari, roman in FEW_SHOTS:
        messages.append({"role": "user", "content": devanagari})
        messages.append({"role": "assistant", "content": roman})
    messages.append({"role": "user", "content": text})
    return messages


class Romanizer:
    def __init__(self, model_name: str, url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.url = url
        ollama.chat(url, model_name, build_messages("नमस्ते"))  # warm + fail fast

    def romanize(self, text: str) -> str:
        try:
            result = sanitize_output(ollama.chat(self.url, self.model_name, build_messages(text)))
            return result if result else text
        except Exception as e:
            print(f"Romanization failed ({e}); keeping original script")
            return text
