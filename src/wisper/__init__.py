import sys


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "install":
        from wisper.service import install

        install()
    elif args and args[0] == "uninstall":
        from wisper.service import uninstall

        uninstall()
    else:
        from wisper.app import main as run

        run()
