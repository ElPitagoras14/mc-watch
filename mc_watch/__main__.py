import logging
import sys

from mc_watch.app import App
from mc_watch.config import config_dir
from mc_watch.single_instance import acquire
from mc_watch.winutil import enable_per_monitor_dpi


def main() -> int:
    enable_per_monitor_dpi()
    try:
        guard = acquire(config_dir())
        if guard is None:
            return 0  # another instance has the tray icon; it was asked to show its panel
        return App(guard=guard).run()
    except Exception:
        logging.getLogger("mc_watch").exception("mc-watch terminó por un error inesperado")
        return 1


if __name__ == "__main__":
    sys.exit(main())
