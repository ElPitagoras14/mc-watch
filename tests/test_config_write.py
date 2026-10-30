import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mc_watch.config import (
    MAX_NAME_LENGTH,
    Config,
    ConfigWriteError,
    Settings,
    ValidationError,
    append_server,
    config_path,
    load_config,
    save_settings,
    set_edition,
    validate_new_server,
)
from mc_watch.models import Edition, ServerConfig


class EditionParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)

    def load(self, content: str) -> Config:
        config_path(self.directory).write_text(content, encoding="utf-8")
        return load_config(self.directory)

    def test_explicit_edition_is_read(self) -> None:
        config = self.load(
            '[[servers]]\nname = "A"\naddress = "a.example.com"\nedition = "bedrock"\n'
        )
        self.assertEqual(config.servers[0].edition, Edition.BEDROCK)

    def test_missing_edition_is_unknown(self) -> None:
        config = self.load('[[servers]]\nname = "A"\naddress = "a.example.com"\n')
        self.assertEqual(config.servers[0].edition, Edition.UNKNOWN)
        self.assertEqual(config.warnings, ())

    def test_invalid_edition_is_unknown_with_warning(self) -> None:
        config = self.load('[[servers]]\nname = "A"\naddress = "a.example.com"\nedition = "x"\n')
        self.assertEqual(config.servers[0].edition, Edition.UNKNOWN)
        self.assertEqual(len(config.warnings), 1)

    def test_valid_and_missing_file_are_writable(self) -> None:
        self.assertTrue(self.load('[[servers]]\nname = "A"\naddress = "a.example.com"\n').writable)
        config_path(self.directory).unlink()
        missing = load_config(self.directory)
        self.assertTrue(missing.writable)
        self.assertIsNone(missing.error)

    def test_invalid_toml_is_not_writable_and_reports_the_error(self) -> None:
        config = self.load("esto no es toml [")
        self.assertFalse(config.writable)
        self.assertEqual(config.servers, ())
        self.assertIn("config.toml", config.error or "")

    def test_unreadable_file_is_not_writable(self) -> None:
        config_path(self.directory).write_bytes(b"\xff\xfe\x00")
        self.assertFalse(load_config(self.directory).writable)


class ValidateNewServerTest(unittest.TestCase):
    def assert_error(self, result: object, field: str) -> ValidationError:
        self.assertIsInstance(result, ValidationError)
        assert isinstance(result, ValidationError)
        self.assertEqual(result.field, field)
        return result

    def test_valid_server_is_trimmed(self) -> None:
        result = validate_new_server("  Survival ", " play.example.com ", [])
        self.assertEqual(result, ServerConfig("Survival", "play.example.com"))

    def test_empty_address(self) -> None:
        self.assert_error(validate_new_server("A", "   ", []), "address")

    def test_invalid_port(self) -> None:
        self.assert_error(validate_new_server("A", "play.example.com:70000", []), "address")

    def test_empty_name_uses_the_address(self) -> None:
        result = validate_new_server("", "play.example.com", [])
        self.assertEqual(result, ServerConfig("play.example.com", "play.example.com"))

    def test_long_name_is_rejected(self) -> None:
        self.assert_error(
            validate_new_server("x" * (MAX_NAME_LENGTH + 1), "a.example.com", []), "name"
        )
        ok = validate_new_server("x" * MAX_NAME_LENGTH, "a.example.com", [])
        self.assertIsInstance(ok, ServerConfig)

    def test_duplicate_ignores_case(self) -> None:
        error = self.assert_error(
            validate_new_server("A", "Play.Example.com", ["play.example.com"]), "address"
        )
        self.assertIn("ya está", error.message)


class WriteConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name) / "nested"
        self.path = self.directory / "config.toml"

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def test_creates_directory_and_file(self) -> None:
        append_server(self.directory, ServerConfig("A", "a.example.com", Edition.JAVA))
        self.assertEqual(
            load_config(self.directory).servers,
            (ServerConfig("A", "a.example.com", Edition.JAVA),),
        )

    def test_keeps_comments_and_appends_with_three_fields(self) -> None:
        original = (
            "# mi config\npoll_interval_secs = 30\n\n"
            '[[servers]]\nname = "H"  # el grande\naddress = "mc.hypixel.net"\n'
        )
        self.directory.mkdir()
        self.path.write_text(original, encoding="utf-8")

        append_server(self.directory, ServerConfig("Isla", "isla.example.com", Edition.BEDROCK))

        text = self.read()
        self.assertTrue(text.startswith(original))
        self.assertIn('name = "Isla"\naddress = "isla.example.com"\nedition = "bedrock"', text)
        config = load_config(self.directory)
        self.assertEqual(config.poll_interval_secs, 30)
        self.assertEqual([s.name for s in config.servers], ["H", "Isla"])

    def test_unknown_edition_is_written_explicitly(self) -> None:
        append_server(self.directory, ServerConfig("A", "a.example.com", Edition.UNKNOWN))
        self.assertIn('edition = "unknown"', self.read())

    def test_set_edition_on_a_hand_written_entry(self) -> None:
        self.directory.mkdir()
        self.path.write_text(
            '[[servers]]\nname = "H" # c\naddress = "mc.hypixel.net"\n\n'
            '[[servers]]\nname = "B"\naddress = "b.example.com"\n',
            encoding="utf-8",
        )

        self.assertTrue(set_edition(self.directory, "MC.hypixel.net", Edition.JAVA))

        servers = load_config(self.directory).servers
        self.assertEqual([s.edition for s in servers], [Edition.JAVA, Edition.UNKNOWN])
        self.assertIn('name = "H" # c', self.read())

    def test_set_edition_without_entry_does_not_write(self) -> None:
        self.directory.mkdir()
        original = '[[servers]]\nname = "B"\naddress = "b.example.com"\n'
        self.path.write_text(original, encoding="utf-8")
        self.assertFalse(set_edition(self.directory, "otro.example.com", Edition.JAVA))
        self.assertEqual(self.read(), original)

    def test_set_edition_with_the_same_value_does_not_write(self) -> None:
        append_server(self.directory, ServerConfig("A", "a.example.com", Edition.JAVA))
        before = self.read()
        self.assertFalse(set_edition(self.directory, "a.example.com", Edition.JAVA))
        self.assertEqual(self.read(), before)

    def test_broken_file_on_disk_aborts_and_stays_identical(self) -> None:
        self.directory.mkdir()
        broken = b"[[servers\nname = \xc3\xa1 [ roto"
        self.path.write_bytes(broken)

        with self.assertRaises(ConfigWriteError):
            append_server(self.directory, ServerConfig("A", "a.example.com", Edition.JAVA))
        with self.assertRaises(ConfigWriteError):
            set_edition(self.directory, "a.example.com", Edition.JAVA)

        self.assertEqual(self.path.read_bytes(), broken)
        self.assertFalse(self.path.with_name("config.toml.tmp").exists())

    def test_failed_replace_leaves_the_file_as_it_was(self) -> None:
        append_server(self.directory, ServerConfig("A", "a.example.com", Edition.JAVA))
        before = self.path.read_bytes()

        with (
            mock.patch("mc_watch.config.os.replace", side_effect=PermissionError("denegado")),
            self.assertRaises(ConfigWriteError) as raised,
        ):
            append_server(self.directory, ServerConfig("B", "b.example.com", Edition.JAVA))

        self.assertIn("denegado", str(raised.exception))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.path.with_name("config.toml.tmp").exists())

    def test_picks_up_manual_edits_made_after_startup(self) -> None:
        append_server(self.directory, ServerConfig("A", "a.example.com", Edition.JAVA))
        self.path.write_text(self.read() + "# agregado a mano\n", encoding="utf-8")
        append_server(self.directory, ServerConfig("B", "b.example.com", Edition.JAVA))
        self.assertIn("# agregado a mano", self.read())


if __name__ == "__main__":
    unittest.main()


class SaveSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.path = config_path(self.directory)

    def test_new_keys_go_above_the_servers(self) -> None:
        servers = '[[servers]]\nname = "A"\naddress = "a.example.com"\n'
        self.path.write_text(servers, encoding="utf-8")
        self.assertTrue(save_settings(self.directory, Settings(True, 120, 5)))
        self.assertEqual(
            self.path.read_text(encoding="utf-8"),
            "notifications = true\npoll_interval_secs = 120\nmax_visible_servers = 5\n\n" + servers,
        )
        config = load_config(self.directory)
        self.assertEqual(config.settings, Settings(True, 120, 5))
        self.assertEqual(len(config.servers), 1)

    def test_existing_keys_are_updated_in_place(self) -> None:
        self.path.write_text(
            "# intervalo\npoll_interval_secs = 60  # segundos\nnotifications = false\n\n"
            '[[servers]]\nname = "A"\naddress = "a.example.com"\n',
            encoding="utf-8",
        )
        save_settings(self.directory, Settings(True, 90, 8))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("# intervalo\npoll_interval_secs = 90  # segundos\n", text)
        self.assertIn("notifications = true\nmax_visible_servers = 8\n\n[[servers]]", text)
        self.assertFalse(save_settings(self.directory, Settings(True, 90, 8)))
