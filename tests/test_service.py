import plistlib

from wisper.service import LABEL, build_plist


DEPLOY_BIN = "/Users/me/Library/Application Support/wisper/venv/bin/wisper"
DEPLOY_DIR = "/Users/me/Library/Application Support/wisper"


def test_plist_has_label_and_program():
    data = plistlib.loads(build_plist(DEPLOY_BIN, DEPLOY_DIR))
    assert data["Label"] == LABEL
    assert data["ProgramArguments"] == [DEPLOY_BIN]
    assert data["WorkingDirectory"] == DEPLOY_DIR


def test_plist_runs_at_load():
    data = plistlib.loads(build_plist(DEPLOY_BIN, DEPLOY_DIR))
    assert data["RunAtLoad"] is True


def test_plist_unbuffered_and_has_path():
    data = plistlib.loads(build_plist(DEPLOY_BIN, DEPLOY_DIR))
    assert data["EnvironmentVariables"]["PYTHONUNBUFFERED"] == "1"
    assert "/opt/homebrew/bin" in data["EnvironmentVariables"]["PATH"]


def test_plist_logs_under_wisper_dir():
    data = plistlib.loads(build_plist(DEPLOY_BIN, DEPLOY_DIR))
    assert data["StandardOutPath"].endswith("/.wisper/wisper.log")
    assert data["StandardErrorPath"].endswith("/.wisper/wisper.log")


def test_plist_is_valid_bytes():
    assert isinstance(build_plist(DEPLOY_BIN, DEPLOY_DIR), bytes)
