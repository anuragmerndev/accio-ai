"""Frontmost-app detection on macOS: tone hint for the polish pass."""

from AppKit import NSWorkspace

APP_TONES = {
    "slack": "chat",
    "discord": "chat",
    "messages": "chat",
    "whatsapp": "chat",
    "telegram": "chat",
    "mail": "email",
    "outlook": "email",
    "gmail": "email",
    "code": "code",
    "cursor": "code",
    "terminal": "code",
    "iterm2": "code",
    "xcode": "code",
    "zed": "code",
}


def frontmost_app_name() -> str:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else ""


def tone_for_app(app_name: str) -> str:
    name = app_name.lower()
    for key, tone in APP_TONES.items():
        if key in name:
            return tone
    return "default"
