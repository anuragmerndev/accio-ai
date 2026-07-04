"""Deterministic transcript cleanup: filler removal and whitespace normalization."""

import re

DEFAULT_FILLERS = ["um", "uh", "erm", "uhm", "you know", "i mean", "like,"]


def clean(text: str, fillers: list[str] | None = None) -> str:
    fillers = DEFAULT_FILLERS if fillers is None else fillers
    for filler in sorted(fillers, key=len, reverse=True):
        # match the filler with optional trailing comma, as whole words
        pattern = rf"\b{re.escape(filler)}\b,?"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # drop commas orphaned at the start after filler removal
    text = re.sub(r"^\s*,\s*", "", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text:
        text = text[0].upper() + text[1:]
    return text
