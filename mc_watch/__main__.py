import logging
import sys

from mc_watch.app import App


def main() -> int:
    try:
        return App().run()
    except Exception:
        logging.getLogger("mc_watch").exception("mc-watch terminó por un error inesperado")
        return 1


if __name__ == "__main__":
    sys.exit(main())
