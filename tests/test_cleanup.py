from accio.cleanup import clean


def test_removes_filler_words():
    assert clean("um so I think uh we should ship it") == "So I think we should ship it"


def test_filler_removal_is_case_insensitive():
    assert clean("Um, let's start") == "Let's start"


def test_does_not_remove_fillers_inside_words():
    # "um" inside "column" or "uh" inside "uhuru" must survive
    assert clean("check the column") == "Check the column"


def test_removes_multiword_fillers():
    assert clean("it's you know kind of done") == "It's kind of done"


def test_collapses_whitespace():
    assert clean("hello   world  again") == "Hello world again"


def test_strips_leading_trailing_space():
    assert clean("  hello  ") == "Hello"


def test_capitalizes_first_letter():
    assert clean("hello there") == "Hello there"


def test_empty_input():
    assert clean("") == ""


def test_filler_only_input():
    assert clean("um uh um") == ""


def test_dangling_comma_after_filler_removed():
    assert clean("well, um, let's go") == "Well, let's go"
