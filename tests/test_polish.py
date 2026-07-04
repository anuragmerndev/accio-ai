from accio.polish import TONE_HINTS, build_prompt, sanitize_output


def test_prompt_contains_transcript_and_tone():
    prompt = build_prompt("hello world", "email")
    assert "hello world" in prompt
    assert TONE_HINTS["email"] in prompt


def test_unknown_tone_falls_back_to_default():
    prompt = build_prompt("hi", "some-unknown-app-kind")
    assert TONE_HINTS["default"] in prompt


def test_sanitize_strips_quotes_and_whitespace():
    assert sanitize_output('  "Hello there."  ') == "Hello there."


def test_sanitize_takes_first_paragraph_only():
    # guard against chatty models appending explanations
    assert sanitize_output("Fixed text.\n\nNote: I removed fillers.") == "Fixed text."


def test_sanitize_rejects_empty():
    assert sanitize_output("   ") == ""
