import plistlib

from accio.service import LABEL, build_info_plist, launcher_script


def test_info_plist_identifies_app():
    data = plistlib.loads(build_info_plist())
    assert data["CFBundleName"] == "Accio"
    assert data["CFBundleExecutable"] == "accio-launch"
    assert data["CFBundleIdentifier"].endswith(".launcher")


def test_info_plist_has_no_dock_icon():
    # a thin launcher that exits after kickstart shouldn't linger in the Dock
    data = plistlib.loads(build_info_plist())
    assert data["LSUIElement"] is True


def test_launcher_kickstarts_the_agent():
    script = launcher_script()
    assert script.startswith("#!/bin/bash")
    assert f"gui/$(id -u)/{LABEL}" in script
    assert "kickstart -k" in script
