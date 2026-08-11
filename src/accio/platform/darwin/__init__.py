"""macOS platform backend: paste, frontmost-app detection, tray, launch-at-login."""

from accio.platform.darwin.context import (  # noqa: F401
    APP_TONES,
    frontmost_app_name,
    tone_for_app,
)
from accio.platform.darwin.paste import copy_only, paste_text  # noqa: F401
from accio.platform.darwin.service import (  # noqa: F401
    LABEL,
    APP_NAME,
    install,
    uninstall,
    start,
    stop,
    restart,
    build_plist,
    build_info_plist,
    launcher_script,
)
from accio.platform.darwin.tray import run_tray  # noqa: F401
