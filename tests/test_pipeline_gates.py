from accio.pipeline import needs_romanization, should_polish


def test_hindi_devanagari_is_romanized():
    assert needs_romanization("कल मीटिंग तीन बजे है", "hi", ["hi"]) is True


def test_english_mistagged_as_hindi_is_not_romanized():
    # accent flake: Whisper tags English speech as "hi" — must not romanize
    assert needs_romanization("the demo is on Wednesday", "hi", ["hi"]) is False


def test_unconfigured_language_is_not_romanized():
    assert needs_romanization("कल मीटिंग", "hi", []) is False


def test_english_tagged_en_is_polished():
    assert should_polish("hello world", "en", ["en"]) is True


def test_english_mistagged_as_hindi_is_still_polished():
    # the live bug: raw "no wait Wednesday" pasted because polish was skipped
    assert should_polish("the demos on Tuesday. No wait, Wednesday.", "hi", ["en"]) is True


def test_devanagari_is_not_polished():
    assert should_polish("कल मीटिंग तीन बजे है", "hi", ["en"]) is False


def test_mixed_hinglish_output_after_romanize_is_polishable():
    assert should_polish("kal meeting teen baje hai", "hi", ["en"]) is True
