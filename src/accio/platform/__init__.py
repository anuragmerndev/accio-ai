"""Platform dispatch: import paste, context, tray, and service from the right OS module.

Keeping platform-specific code behind this facade lets the rest of accio stay
OS-agnostic. Adding a new platform means landing an implementation module here
and wiring it into the dispatcher below.
"""

import sys

_IS_DARWIN = sys.platform == "darwin"
_IS_WINDOWS = sys.platform == "win32"

if _IS_DARWIN:
    from accio.platform.darwin import context, paste, service, tray  # noqa: F401
elif _IS_WINDOWS:
    from accio.platform.windows import context, paste, service, tray  # noqa: F401
else:
    raise RuntimeError(
        f"Accio has no platform backend for {sys.platform!r}. "
        "Only macOS (darwin) and Windows (win32) are supported."
    )


def current_platform() -> str:
    """Return the active platform label ('darwin' or 'windows')."""
    if _IS_DARWIN:
        return "darwin"
    if _IS_WINDOWS:
        return "windows"
    return sys.platform


__all__ = ["context", "paste", "service", "tray", "current_platform"]
