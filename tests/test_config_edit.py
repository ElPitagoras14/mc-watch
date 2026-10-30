"""Renaming and removing entries of `config.toml`."""

import tempfile
import unittest
from pathlib import Path

from mc_watch.config import (
    MAX_NAME_LENGTH,
    ConfigWriteError,
    ValidationError,
    config_path,
    load_config,
    normalize_name,
    remove_server,
    set_name,
)

THREE = """# mi config
poll_interval_secs = 30

# primero
[[servers]]
name = "A"
address = "a.example.com"

# segundo
[[servers]]
name = "B"
address = "b.example.com"

# tercero
[[servers]]
name = "C"
address = "c.example.com"
"""

WITHOUT_B = """# mi config
poll_interval_secs = 30

# primero
[[servers]]
name = "A"
address = "a.example.com"

# tercero
[[servers]]
name = "C"
address = "c.example.com"
"""


class NormalizeNameTest(unittest.TestCase):
    def test_empty_name_uses_the_address(self) -> None:
        self.assertEqual(normalize_name("   ", "a.example.com"), "a.example.com")

    def test_long_name_is_rejected(self) -> None:
        result = normalize_name("x" * (MAX_NAME_LENGTH + 1), "a.example.com")
        self.assertIsInstance(result, ValidationError)


class EditTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.path = config_path(self.directory)

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def names(self) -> list[str]:
        return [server.name for server in load_config(self.directory).servers]


class SetNameTest(EditTestCase):
    def test_changes_only_that_name(self) -> None:
        self.write(THREE)
        self.assertTrue(set_name(self.directory, "b.example.com", "Beta"))
        self.assertEqual(self.read(), THREE.replace('name = "B"', 'name = "Beta"'))

    def test_the_same_name_does_not_write(self) -> None:
        self.write(THREE)
        before = self.path.stat().st_mtime_ns
        self.assertFalse(set_name(self.directory, "b.example.com", "B"))
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_without_entry_raises_and_does_not_write(self) -> None:
        self.write(THREE)
        with self.assertRaises(ConfigWriteError):
            set_name(self.directory, "z.example.com", "Zeta")
        self.assertEqual(self.read(), THREE)

    def test_the_middle_entry_goes_and_the_others_keep_their_comments(self) -> None:
        self.write(THREE)
        self.assertTrue(remove_server(self.directory, "b.example.com"))
        self.assertEqual(self.read(), WITHOUT_B)
        self.assertEqual(self.names(), ["A", "C"])

    def test_the_first_entry(self) -> None:
        self.write(THREE)
        remove_server(self.directory, "a.example.com")
        self.assertTrue(
            self.read().startswith("# mi config\npoll_interval_secs = 30\n\n# segundo\n[[servers]]")
        )
        self.assertNotIn("# primero", self.read())
        self.assertEqual(self.names(), ["B", "C"])

    def test_the_last_entry(self) -> None:
        self.write(THREE)
        remove_server(self.directory, "c.example.com")
        self.assertNotIn("# tercero", self.read())
        self.assertTrue(self.read().endswith('address = "b.example.com"\n'))
        self.assertEqual(self.names(), ["A", "B"])

    def test_the_only_entry_keeps_the_other_settings(self) -> None:
        self.write(
            'poll_interval_secs = 30\n\n[[servers]]\nname = "A"\naddress = "a.example.com"\n'
        )
        remove_server(self.directory, "a.example.com")
        self.assertEqual(self.read(), "poll_interval_secs = 30\n")
        self.assertEqual(load_config(self.directory).servers, ())

    def test_an_entry_that_is_gone_does_not_write(self) -> None:
        self.write(THREE)
        before = self.path.stat().st_mtime_ns
        self.assertFalse(remove_server(self.directory, "z.example.com"))
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(self.read(), THREE)

    def test_broken_file_on_disk_aborts_and_stays_identical(self) -> None:
        broken = b"[[servers]\nname = "
        self.path.write_bytes(broken)
        with self.assertRaises(ConfigWriteError):
            remove_server(self.directory, "a.example.com")
        self.assertEqual(self.path.read_bytes(), broken)


if __name__ == "__main__":
    unittest.main()
