import logging
import logging.handlers
import os
import sys
from pathlib import Path

LOGGER_NAME = "mc_watch"
LOG_FILE_NAME = "mc-watch.log"
DEBUG_ENV = "MC_WATCH_DEBUG"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(directory: Path) -> None:
    """Log to a rotating file in `directory` and to stderr when a console exists."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    logger.setLevel(logging.DEBUG if os.environ.get(DEBUG_ENV) == "1" else logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(FORMAT)

    file_error: OSError | None = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            directory / LOG_FILE_NAME,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as error:
        file_error = error
    else:
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Without a console (the windowed .exe) sys.stderr is None.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if file_error is not None:
        logger.warning("No se pudo abrir el archivo de log en %s: %s", directory, file_error)
