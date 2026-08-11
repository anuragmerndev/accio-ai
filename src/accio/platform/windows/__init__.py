"""Windows platform backend: paste, foreground-window detection, tray, autostart."""

from accio.platform.windows.context import (  # noqa: F401
    APP_TONES,
    frontmost_app_name,
    tone_for_app,
)
from accio.platform.windows.paste import copy_only, paste_text  # noqa: F401
from accio.platform.windows.service import (  # noqa: F401
    APP_NAME,
    install,
    uninstall,
    start,
    stop,
    restart,
)
from accio.platform.windows.tray import run_tray  # noqa: F401
