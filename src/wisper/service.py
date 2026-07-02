"""Launch-at-login via a macOS LaunchAgent.

The dev repo lives under ~/Desktop, a TCC-protected folder that background
launchd agents cannot read — the venv Python there wedges during interpreter
startup. So `wisper install` deploys a self-contained copy (its own venv, with
the package and dependencies installed non-editable) under Application Support,
outside any protected folder, and points the launch agent at that copy.

Re-run `wisper install` after code changes to redeploy the snapshot.
"""

import plistlib
import subprocess
from pathlib import Path

LABEL = "com.anuragmerndev.wisper"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / ".wisper" / "wisper.log"
DEPLOY_DIR = Path.home() / "Library" / "Application Support" / "wisper"
DEPLOY_VENV = DEPLOY_DIR / "venv"


def build_plist(executable: str, working_dir: str) -> bytes:
    # PATH is set explicitly because launchd's default omits Homebrew/uv;
    # working_dir must be outside TCC-protected folders or launchd can't chdir.
    return plistlib.dumps(
        {
            "Label": LABEL,
            "ProgramArguments": [executable],
            "WorkingDirectory": working_dir,
            "RunAtLoad": True,
            "KeepAlive": {"Crashed": True},
            "StandardOutPath": str(LOG_PATH),
            "StandardErrorPath": str(LOG_PATH),
            "EnvironmentVariables": {
                "PYTHONUNBUFFERED": "1",
                "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            },
            "ProcessType": "Interactive",
        }
    )


def _deploy() -> Path:
    """Install a standalone copy outside protected folders. Returns its binary."""
    project_dir = Path(__file__).resolve().parents[2]
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Deploying a standalone copy to {DEPLOY_DIR} ...")
    subprocess.run(["uv", "venv", str(DEPLOY_VENV), "--python", "3.12"], check=True)
    subprocess.run(
        [
            "uv", "pip", "install",
            "--python", str(DEPLOY_VENV / "bin" / "python"),
            str(project_dir),
        ],
        check=True,
    )
    return DEPLOY_VENV / "bin" / "wisper"


def install() -> None:
    executable = _deploy()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(build_plist(str(executable), str(DEPLOY_DIR)))
    # bootout is a no-op if not loaded; ignore its failure, then load fresh
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{_uid()}", str(PLIST_PATH)], check=True)
    print(f"Installed launch agent at {PLIST_PATH}")
    print("Wisper will now start automatically at login.")


def uninstall() -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print("Removed the launch agent. Wisper will no longer start at login.")
    print(f"(The deployed copy at {DEPLOY_DIR} was left in place; delete it to fully remove.)")


def _uid() -> int:
    import os

    return os.getuid()
