"""Local dictation history: append every result and expose the recent ones, so a
dictation is never lost even if it wasn't pasted where you wanted."""

import json
import time
from pathlib import Path

HISTORY_PATH = Path.home() / ".accio" / "history.jsonl"


def append(text: str, pasted: bool = True, path: Path = HISTORY_PATH) -> None:
    if not text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "text": text, "pasted": pasted}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def recent(n: int = 10, path: Path = HISTORY_PATH) -> list[dict]:
    """Most recent first."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return list(reversed(out))
