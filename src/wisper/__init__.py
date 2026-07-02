import sys

_COMMANDS = {"install", "uninstall", "start", "stop", "restart"}


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else None
    if cmd in _COMMANDS:
        import wisper.service as service

        # `restart` is just `start` (kickstart -k restarts if already running)
        getattr(service, "start" if cmd == "restart" else cmd)()
    else:
        from wisper.app import main as run

        run()
