"""Dictation history: append + recent (newest first), unicode-safe."""

from accio import history


def test_append_and_recent_newest_first(tmp_path):
    p = tmp_path / "history.jsonl"
    history.append("first", pasted=True, path=p)
    history.append("दूसरा kaam", pasted=False, path=p)  # Hinglish/Devanagari
    got = history.recent(10, path=p)
    assert [r["text"] for r in got] == ["दूसरा kaam", "first"]
    assert got[0]["pasted"] is False


def test_recent_caps_and_handles_missing(tmp_path):
    p = tmp_path / "history.jsonl"
    assert history.recent(10, path=p) == []  # no file yet
    for i in range(15):
        history.append(f"line {i}", path=p)
    got = history.recent(5, path=p)
    assert [r["text"] for r in got] == [f"line {i}" for i in (14, 13, 12, 11, 10)]


def test_empty_text_not_recorded(tmp_path):
    p = tmp_path / "history.jsonl"
    history.append("", path=p)
    assert history.recent(10, path=p) == []
