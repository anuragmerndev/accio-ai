"""Personal dictionary: replace misheard terms with the user's preferred spelling."""

import re


def apply_dictionary(text: str, terms: dict[str, str]) -> str:
    for spoken, written in terms.items():
        pattern = rf"\b{re.escape(spoken)}\b"
        text = re.sub(pattern, written, text, flags=re.IGNORECASE)
    return text
