"""Launch-at-login: re-export the platform backend.

The platform dispatcher picks the macOS LaunchAgent or Windows Startup folder
implementation based on sys.platform at import time.
"""

from accio.platform import service

install = service.install
uninstall = service.uninstall
start = service.start
stop = service.stop
restart = service.restart

# macOS extras used by the upstream test suite. These attributes exist on the
# darwin backend; on other platforms they are None so importing `accio.service`
# never crashes on a non-darwin machine.
build_plist = getattr(service, "build_plist", None)
build_info_plist = getattr(service, "build_info_plist", None)
launcher_script = getattr(service, "launcher_script", None)
LABEL = getattr(service, "LABEL", None)
APP_NAME = getattr(service, "APP_NAME", None)

__all__ = [
    "install",
    "uninstall",
    "start",
    "stop",
    "restart",
    "build_plist",
    "build_info_plist",
    "launcher_script",
    "LABEL",
    "APP_NAME",
]
