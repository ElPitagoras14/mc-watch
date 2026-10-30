import logging
import logging.handlers
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mc_watch.log import LOG_FILE_NAME, LOGGER_NAME, setup_logging


class SetupLoggingTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # Cleanups run in reverse: close the log file before deleting its directory.
        self.addCleanup(self._reset_logger)
        self.directory = Path(tmp.name)

    @staticmethod
    def _reset_logger() -> None:
        logger = logging.getLogger(LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def test_writes_to_rotating_file(self) -> None:
        setup_logging(self.directory)
        logging.getLogger(LOGGER_NAME).info("hola desde el test")
        for handler in logging.getLogger(LOGGER_NAME).handlers:
            handler.flush()

        log_file = self.directory / LOG_FILE_NAME
        self.assertTrue(log_file.exists())
        self.assertIn("hola desde el test", log_file.read_text(encoding="utf-8"))
        self.assertTrue(
            any(
                isinstance(h, logging.handlers.RotatingFileHandler)
                for h in logging.getLogger(LOGGER_NAME).handlers
            )
        )

    def test_works_without_stderr(self) -> None:
        with mock.patch.object(sys, "stderr", None):
            setup_logging(self.directory)
            logging.getLogger(LOGGER_NAME).warning("sin consola")

        handlers = logging.getLogger(LOGGER_NAME).handlers
        self.assertFalse(
            any(
                isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
                for h in handlers
            )
        )
        self.assertEqual(len(handlers), 1)

    def test_unwritable_directory_falls_back_to_stderr(self) -> None:
        blocker = self.directory / "ocupado"
        blocker.write_text("no soy un directorio", encoding="utf-8")

        setup_logging(blocker / "sub")

        handlers = logging.getLogger(LOGGER_NAME).handlers
        self.assertEqual(len(handlers), 1)
        self.assertNotIsInstance(handlers[0], logging.FileHandler)

    def test_debug_env_raises_level(self) -> None:
        with mock.patch.dict("os.environ", {"MC_WATCH_DEBUG": "1"}):
            setup_logging(self.directory)
        self.assertEqual(logging.getLogger(LOGGER_NAME).level, logging.DEBUG)

    def test_default_level_is_info(self) -> None:
        with mock.patch.dict(os.environ):
            os.environ.pop("MC_WATCH_DEBUG", None)
            setup_logging(self.directory)
        self.assertEqual(logging.getLogger(LOGGER_NAME).level, logging.INFO)


if __name__ == "__main__":
    unittest.main()
