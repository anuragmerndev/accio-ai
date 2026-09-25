"""Smart paste: auto-type only when the same app is still focused; otherwise the
text is held (not fired into the wrong place)."""

from accio.app import AccioApp

matches = AccioApp._paste_target_matches


def test_pastes_when_same_app_focused():
    assert matches("Cursor", "Cursor") is True


def test_holds_when_focus_moved():
    assert matches("Cursor", "Slack") is False


def test_no_origin_falls_back_to_paste():
    # unknown origin → preserve the original always-paste behavior
    assert matches("", "Slack") is True
