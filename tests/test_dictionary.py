from wisper.dictionary import apply_dictionary


TERMS = {"anurag": "Anurag", "wisper": "Wisper", "java script": "JavaScript"}


def test_replaces_known_term():
    assert apply_dictionary("ask anurag about it", TERMS) == "ask Anurag about it"


def test_replacement_is_case_insensitive_on_match():
    assert apply_dictionary("Anurag said hi", TERMS) == "Anurag said hi"


def test_multiword_term():
    assert apply_dictionary("I write java script daily", TERMS) == "I write JavaScript daily"


def test_word_boundaries_respected():
    # "wisper" inside "whisperer"-like word must not match
    assert apply_dictionary("the wispering wind", TERMS) == "the wispering wind"


def test_empty_terms_is_noop():
    assert apply_dictionary("hello world", {}) == "hello world"


def test_multiple_occurrences():
    assert apply_dictionary("wisper is wisper", TERMS) == "Wisper is Wisper"
