"""Launch-at-login via a macOS LaunchAgent.

The dev repo lives under ~/Desktop, a TCC-protected folder that background
launchd agents cannot read — the venv Python there wedges during interpreter
startup. So `accio install` deploys a self-contained copy (its own venv, with
the package and dependencies installed non-editable) under Application Support,
outside any protected folder, and points the launch agent at that copy.

Re-run `accio install` after code changes to redeploy the snapshot.
"""

import plistlib
import subprocess
from pathlib import Path

LABEL = "com.anuragmerndev.accio"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / ".accio" / "accio.log"
DEPLOY_DIR = Path.home() / "Library" / "Application Support" / "accio"
DEPLOY_VENV = DEPLOY_DIR / "venv"
# user-facing Spotlight app; "Accio" — the Summoning Charm. Internal LABEL and
# the `accio` CLI stay unchanged.
APP_NAME = "Accio"
APP_PATH = Path.home() / "Applications" / f"{APP_NAME}.app"


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


def build_info_plist() -> bytes:
    return plistlib.dumps(
        {
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": f"{LABEL}.launcher",
            "CFBundleExecutable": "accio-launch",
            "CFBundlePackageType": "APPL",
            "CFBundleVersion": "1.0",
            "CFBundleShortVersionString": "1.0",
            # thin launcher: kickstart the agent, then exit — no Dock presence
            "LSUIElement": True,
        }
    )


def launcher_script() -> str:
    # (re)start the background agent; -k restarts it if already running so a
    # Spotlight launch always leaves a fresh, healthy instance
    return (
        "#!/bin/bash\n"
        f"exec launchctl kickstart -k gui/$(id -u)/{LABEL}\n"
    )


def build_app_bundle() -> None:
    """Write ~/Applications/Accio.app — a Spotlight-searchable launcher."""
    macos = APP_PATH / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (APP_PATH / "Contents" / "Info.plist").write_bytes(build_info_plist())
    launcher = macos / "accio-launch"
    launcher.write_text(launcher_script())
    launcher.chmod(0o755)
    print(f"Created {APP_PATH} (search '{APP_NAME}' in Spotlight to start it)")


def _deploy() -> Path:
    """Install a standalone copy outside protected folders. Returns its binary."""
    project_dir = Path(__file__).resolve().parents[2]
    DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Deploying a standalone copy to {DEPLOY_DIR} ...")
    # --clear makes redeploys idempotent (replace any existing venv)
    subprocess.run(
        ["uv", "venv", str(DEPLOY_VENV), "--python", "3.12", "--clear"], check=True
    )
    subprocess.run(
        [
            "uv", "pip", "install",
            "--python", str(DEPLOY_VENV / "bin" / "python"),
            str(project_dir),
        ],
        check=True,
    )
    return DEPLOY_VENV / "bin" / "accio"


def install() -> None:
    executable = _deploy()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(build_plist(str(executable), str(DEPLOY_DIR)))
    build_app_bundle()
    # bootout is a no-op if not loaded; ignore its failure, then load fresh
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{_uid()}", str(PLIST_PATH)], check=True)
    print(f"Installed launch agent at {PLIST_PATH}")
    print("Accio will now start automatically at login.")


def uninstall() -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], capture_output=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    if APP_PATH.exists():
        import shutil

        shutil.rmtree(APP_PATH)
    print("Removed the launch agent and Accio.app. It will no longer start at login.")
    print(f"(The deployed copy at {DEPLOY_DIR} was left in place; delete it to fully remove.)")


def start() -> None:
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{_uid()}/{LABEL}"], check=True)
    print("Accio (re)started.")


def stop() -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], capture_output=True)
    print("Accio stopped (until next login, or `accio start`).")


def _uid() -> int:
    import os

    return os.getuid()
