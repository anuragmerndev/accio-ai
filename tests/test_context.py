from accio.context import tone_for_app


def test_chat_apps():
    assert tone_for_app("Slack") == "chat"
    assert tone_for_app("Messages") == "chat"


def test_email_apps():
    assert tone_for_app("Mail") == "email"


def test_code_apps():
    assert tone_for_app("Visual Studio Code") == "code"
    assert tone_for_app("iTerm2") == "code"


def test_unknown_app_is_default():
    assert tone_for_app("Safari") == "default"
    assert tone_for_app("") == "default"
