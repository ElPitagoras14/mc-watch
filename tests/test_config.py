import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mc_watch.config import (
    DEFAULT_POLL_INTERVAL_SECS,
    MIN_POLL_INTERVAL_SECS,
    config_dir,
    config_path,
    is_valid_address,
    load_config,
)
from mc_watch.models import ServerConfig


class ConfigLocationTest(unittest.TestCase):
    def test_default_location_is_appdata(self) -> None:
        env = {"APPDATA": r"C:\Users\x\AppData\Roaming"}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("MC_WATCH_CONFIG_DIR", None)
            self.assertEqual(config_dir(), Path(r"C:\Users\x\AppData\Roaming") / "mc-watch")
            self.assertEqual(config_path().name, "config.toml")

    def test_directory_can_be_overridden(self) -> None:
        with mock.patch.dict(os.environ, {"MC_WATCH_CONFIG_DIR": r"D:\tmp\mcw"}):
            self.assertEqual(config_dir(), Path(r"D:\tmp\mcw"))
            self.assertEqual(config_path(), Path(r"D:\tmp\mcw") / "config.toml")


class LoadConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.path = self.directory / "config.toml"

    def write(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    def test_valid_file_keeps_order(self) -> None:
        self.write(
            '[[servers]]\nname = "Survival"\naddress = "play.example.com"\n\n'
            '[[servers]]\nname = "Creativo"\naddress = "mc.example.com:25570"\n'
        )
        config = load_config(self.directory)
        self.assertEqual(
            config.servers,
            (
                ServerConfig("Survival", "play.example.com"),
                ServerConfig("Creativo", "mc.example.com:25570"),
            ),
        )

    def test_default_interval(self) -> None:
        self.write('[[servers]]\nname = "A"\naddress = "a.example.com"\n')
        self.assertEqual(load_config(self.directory).poll_interval_secs, DEFAULT_POLL_INTERVAL_SECS)
        self.assertEqual(DEFAULT_POLL_INTERVAL_SECS, 60)

    def test_interval_is_used(self) -> None:
        self.write("poll_interval_secs = 90\n")
        self.assertEqual(load_config(self.directory).poll_interval_secs, 90)

    def test_low_interval_is_raised_to_minimum(self) -> None:
        self.write("poll_interval_secs = 5\n")
        config = load_config(self.directory)
        self.assertEqual(config.poll_interval_secs, MIN_POLL_INTERVAL_SECS)
        self.assertEqual(MIN_POLL_INTERVAL_SECS, 30)
        self.assertTrue(config.warnings)

    def test_non_integer_interval_falls_back_to_default(self) -> None:
        self.write('poll_interval_secs = "rápido"\n')
        config = load_config(self.directory)
        self.assertEqual(config.poll_interval_secs, DEFAULT_POLL_INTERVAL_SECS)
        self.assertTrue(config.warnings)

    def test_high_interval_is_lowered_to_maximum(self) -> None:
        self.write("poll_interval_secs = 86400\n")
        self.assertEqual(load_config(self.directory).poll_interval_secs, 3600)

    def test_settings_default_when_absent(self) -> None:
        self.write('[[servers]]\nname = "A"\naddress = "a.example.com"\n')
        config = load_config(self.directory)
        self.assertFalse(config.notifications)
        self.assertEqual(config.max_visible_servers, 8)

    def test_invalid_settings_fall_back(self) -> None:
        self.write('notifications = "sí"\nmax_visible_servers = 50\n')
        config = load_config(self.directory)
        self.assertFalse(config.notifications)
        self.assertEqual(config.max_visible_servers, 20)
        self.assertEqual(len(config.warnings), 2)

    def test_missing_file_starts_without_servers(self) -> None:
        config = load_config(self.directory)
        self.assertEqual(config.servers, ())
        self.assertEqual(config.poll_interval_secs, DEFAULT_POLL_INTERVAL_SECS)
        self.assertFalse(self.path.exists(), "no debe crear el archivo")

    def test_syntax_error_uses_defaults_and_leaves_file_intact(self) -> None:
        broken = 'poll_interval_secs = 90\n[[servers\nname = "A"\n'
        self.write(broken)
        before = self.path.read_bytes()

        config = load_config(self.directory)

        self.assertEqual(config.servers, ())
        self.assertEqual(config.poll_interval_secs, DEFAULT_POLL_INTERVAL_SECS)
        self.assertTrue(config.warnings)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_utf8_is_treated_as_invalid(self) -> None:
        self.path.write_bytes(b"\xff\xfe\x00name")
        config = load_config(self.directory)
        self.assertEqual(config.servers, ())

    def test_entry_without_address_is_ignored(self) -> None:
        self.write(
            '[[servers]]\nname = "Uno"\naddress = "uno.example.com"\n\n'
            '[[servers]]\nname = "Sin dirección"\n\n'
            '[[servers]]\nname = "Tres"\naddress = "tres.example.com"\n'
        )
        config = load_config(self.directory)
        self.assertEqual([s.name for s in config.servers], ["Uno", "Tres"])
        self.assertEqual(len(config.warnings), 1)

    def test_entry_without_name_is_ignored(self) -> None:
        self.write('[[servers]]\naddress = "a.example.com"\n')
        self.assertEqual(load_config(self.directory).servers, ())

    def test_entry_with_out_of_range_port_is_ignored(self) -> None:
        self.write(
            '[[servers]]\nname = "Alto"\naddress = "a.example.com:70000"\n\n'
            '[[servers]]\nname = "Cero"\naddress = "b.example.com:0"\n\n'
            '[[servers]]\nname = "Bien"\naddress = "c.example.com:25565"\n'
        )
        self.assertEqual([s.name for s in load_config(self.directory).servers], ["Bien"])

    def test_servers_that_is_not_a_list_is_ignored(self) -> None:
        self.write('servers = "no soy una lista"\n')
        config = load_config(self.directory)
        self.assertEqual(config.servers, ())
        self.assertTrue(config.warnings)


class AddressTest(unittest.TestCase):
    def test_valid_addresses(self) -> None:
        for address in ("example.com", "example.com:1", "example.com:65535", "10.0.0.5:25565"):
            with self.subTest(address=address):
                self.assertTrue(is_valid_address(address))

    def test_invalid_addresses(self) -> None:
        for address in (
            "",
            ":25565",
            "example.com:",
            "example.com:abc",
            "example.com:0",
            "example.com:65536",
            "example.com:-1",
            "a b.com",
            "a:1:2",
        ):
            with self.subTest(address=address):
                self.assertFalse(is_valid_address(address))


if __name__ == "__main__":
    unittest.main()
