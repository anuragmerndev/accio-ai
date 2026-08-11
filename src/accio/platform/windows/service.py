"""Windows autostart: drop a launcher (.lnk or .bat) into the Startup folder.

This mirrors the macOS LaunchAgent workflow: `accio install` deploys a launcher
into the per-user Startup folder so Accio boots at login. No Administrator
privileges required — Startup folder is per-user.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "Accio"
_STARTUP_DIR = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
LAUNCHER_PATH = _STARTUP_DIR / f"{APP_NAME}.bat"
LOG_PATH = Path.home() / ".accio" / "accio.log"
DEPLOY_DIR = Path.home() / "AppData" / "Local" / "Accio"
DEPLOY_VENV = DEPLOY_DIR / "venv"


def _python_exe() -> Path:
    # When Accio has been installed via `accio install`, the deploy venv owns its
    # python; otherwise the venv of the currently running interpreter is correct.
    deploy_python = DEPLOY_VENV / "Scripts" / "python.exe"
    if deploy_python.exists():
        return deploy_python
    return Path(sys.executable)


def _launcher_script() -> str:
    python = _python_exe()
    # `python -m accio` invokes accio.main() (the tray entrypoint). We avoid the
    # `accio` console-script wrapper because pip-generated wrappers inject a
    # shim that can hang the parent process on Windows when launched from the
    # Startup folder without a console window.
    return (
        "@echo off\r\n"
        f'start "" "{python}" -m accio\r\n'
    )


def install() -> None:
    _STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    project_dir = Path(__file__).resolve().parents[4]
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Deploying a standalone copy to {DEPLOY_DIR} ...")
    # Frozen lockfile keeps the deployed install reproducible; --no-editable
    # makes the deploy copy self-contained so the dev repo can move freely.
    subprocess.run(
        ["uv", "sync", "--frozen", "--no-dev", "--no-editable"],
        check=True,
        cwd=project_dir,
        env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(DEPLOY_VENV)},
    )

    LAUNCHER_PATH.write_text(_launcher_script(), encoding="ascii")
    print(f"Installed launcher at {LAUNCHER_PATH}")
    print(f"{APP_NAME} will now start automatically at login.")


def uninstall() -> None:
    if LAUNCHER_PATH.exists():
        LAUNCHER_PATH.unlink()
    print(f"Removed {LAUNCHER_PATH}. Accio will no longer start at login.")
    print(f"(The deployed copy at {DEPLOY_DIR} was left in place; delete it to fully remove.)")


def start() -> None:
    # Best-effort non-blocking launch — the Startup folder copy takes over on
    # next reboot; for ad-hoc launches we invoke the deploy python directly.
    python = _python_exe()
    subprocess.Popen([str(python), "-m", "accio"])
    print("Accio started (background).")


def stop() -> None:
    # The dotenv-clean way of stopping is to close the tray app; on Windows we
    # also leave a `stop` stub that ends any orphaned accio python processes
    # by name. Skipped here to avoid killing unrelated interpreters — the
    # tray owns its own lifetime.
    print("Stop the Accio tray to quit. There is no separate background agent on Windows.")


def restart() -> None:
    stop()
    start()
