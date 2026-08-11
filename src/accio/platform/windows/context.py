"""Foreground-window detection on Windows: tone hint for the polish pass.

Uses ctypes to call GetForegroundWindow + GetWindowTextW so the module has no
hard dependency on pywin32. The tone map is shared with the macOS backend —
only the discovery mechanism differs.
"""

import ctypes
from ctypes import wintypes

APP_TONES = {
    "slack": "chat",
    "discord": "chat",
    "messages": "chat",
    "whatsapp": "chat",
    "telegram": "chat",
    "teams": "chat",
    "outlook": "email",
    "mail": "email",
    "gmail": "email",
    "thunderbird": "email",
    "code": "code",
    "cursor": "code",
    "cmd": "code",
    "powershell": "code",
    "windowsterminal": "code",
    "wezterm": "code",
    "alacritty": "code",
    "vscode": "code",
    "iterm2": "code",
    "xcode": "code",
    "zed": "code",
    "notepad": "default",
    "word": "email",
    "onenote": "default",
    "obsidian": "default",
}

_user32 = ctypes.windll.user32
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
_user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
_user32.GetWindowTextLengthW.restype = ctypes.c_int


def frontmost_app_name() -> str:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    title = buffer.value
    # On Windows the window title is the most reliable per-window label we get
    # without a process handle; editors often show "file.py - Visual Studio Code"
    # so we lowercase and let the tone map match against substrings.
    return title


def tone_for_app(app_name: str) -> str:
    name = (app_name or "").lower()
    for key, tone in APP_TONES.items():
        if key in name:
            return tone
    return "default"
