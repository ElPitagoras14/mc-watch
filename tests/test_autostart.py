import contextlib
import unittest
import winreg

from mc_watch.autostart import Autostart

TEST_KEY = r"Software\mc-watch-test\Run"


class AutostartTest(unittest.TestCase):
    def tearDown(self) -> None:
        for sub in (TEST_KEY, r"Software\mc-watch-test"):
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)

    def auto(self, exe: str = r"C:\a\mc-watch.exe", frozen: bool = True) -> Autostart:
        return Autostart(frozen=frozen, executable=exe, run_key=TEST_KEY)

    def test_enable_and_disable(self) -> None:
        auto = self.auto()
        self.assertFalse(auto.is_enabled())
        auto.set_enabled(True)
        self.assertTrue(auto.is_enabled())
        self.assertEqual(auto.current(), r'"C:\a\mc-watch.exe"')
        auto.set_enabled(False)
        self.assertFalse(auto.is_enabled())
        auto.set_enabled(False)  # turning it off twice is not an error

    def test_refresh_follows_the_executable_but_never_creates(self) -> None:
        self.assertFalse(self.auto().refresh())
        self.assertFalse(self.auto().is_enabled())

        self.auto(r"C:\a\mc-watch.exe").enable()
        moved = self.auto(r"C:\b\mc-watch.exe")
        self.assertTrue(moved.refresh())
        self.assertFalse(moved.refresh())
        self.assertEqual(moved.current(), r'"C:\b\mc-watch.exe"')

    def test_not_offered_from_source(self) -> None:
        auto = self.auto(frozen=False)
        self.assertFalse(auto.available)
        with self.assertRaises(OSError):
            auto.enable()
        self.assertFalse(auto.is_enabled())


if __name__ == "__main__":
    unittest.main()
