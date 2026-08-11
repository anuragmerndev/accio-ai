"""App entrypoint: dispatch to the per-platform tray.

Keeping the tray UI behind this dispatcher lets `accio` (the console script)
and `python -m accio` both work on macOS and Windows without leaking platform
imports into each other.
"""

from accio.platform import tray


def main() -> None:
    tray.run_tray()
