import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from mc_watch.config import Config, ConfigWriteError, Settings, config_path, load_config
from mc_watch.settings import SettingsManager

VALID: dict[str, Any] = {"notifications": True, "poll_interval_secs": 120, "max_visible_servers": 5}


class SettingsManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.path = config_path(self.directory)
        self.poller = mock.Mock()
        self.notifications = mock.Mock()
        self.changed = mock.Mock()

    def make(self, config: Config | None = None) -> SettingsManager:
        return SettingsManager(
            self.directory,
            config or load_config(self.directory),
            self.poller,
            self.notifications,
            self.changed,
        )

    def assert_nothing_applied(self) -> None:
        self.poller.set_interval.assert_not_called()
        self.notifications.set_enabled.assert_not_called()
        self.changed.assert_not_called()

    def test_valid_values_are_written_and_applied(self) -> None:
        manager = self.make()

        self.assertEqual(manager.save(VALID), {"ok": True})

        self.assertEqual(load_config(self.directory).settings, Settings(True, 120, 5))
        self.assertEqual(manager.current, Settings(True, 120, 5))
        self.poller.set_interval.assert_called_once_with(120)
        self.notifications.set_enabled.assert_called_once_with(True)
        self.changed.assert_called_once()

    def test_out_of_range_interval_is_rejected(self) -> None:
        reply = self.make().save({**VALID, "poll_interval_secs": 10})

        self.assertEqual(reply["field"], "poll_interval_secs")
        self.assertEqual(reply["message"], "Entre 30 y 3600")
        self.assertFalse(self.path.exists())
        self.assert_nothing_applied()

    def test_decimals_and_booleans_are_not_numbers(self) -> None:
        manager = self.make()
        self.assertEqual(
            manager.save({**VALID, "max_visible_servers": 4.5})["field"], "max_visible_servers"
        )
        self.assertEqual(
            manager.save({**VALID, "max_visible_servers": True})["field"], "max_visible_servers"
        )
        self.assertTrue(manager.save({**VALID, "max_visible_servers": 4.0})["ok"])

    def test_unwritable_config_is_reported_without_applying(self) -> None:
        config = Config(writable=False, error="config.toml no es un TOML válido")

        reply = self.make(config).save(VALID)

        self.assertEqual(reply["message"], "config.toml no es un TOML válido")
        self.assert_nothing_applied()

    def test_write_error_is_reported_without_applying(self) -> None:
        manager = self.make()
        with mock.patch("mc_watch.settings.save_settings", side_effect=ConfigWriteError("roto")):
            reply = manager.save(VALID)

        self.assertEqual(reply, {"ok": False, "field": None, "message": "roto"})
        self.assertEqual(manager.current, Settings())
        self.assert_nothing_applied()


if __name__ == "__main__":
    unittest.main()
