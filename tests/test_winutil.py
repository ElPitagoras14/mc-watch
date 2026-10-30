import unittest
from unittest import mock

from mc_watch import winutil


class TaskbarThemeTest(unittest.TestCase):
    def test_returns_a_bool_without_raising(self) -> None:
        self.assertIsInstance(winutil.taskbar_uses_light_theme(), bool)

    def test_light_theme_value(self) -> None:
        for value, expected in ((1, True), (0, False)):
            with (
                self.subTest(value=value),
                mock.patch.object(winutil.winreg, "OpenKey") as open_key,
                mock.patch.object(winutil.winreg, "QueryValueEx", return_value=(value, 4)),
            ):
                open_key.return_value.__enter__.return_value = object()
                self.assertIs(winutil.taskbar_uses_light_theme(), expected)

    def test_missing_registry_value_assumes_dark(self) -> None:
        with mock.patch.object(winutil.winreg, "OpenKey", side_effect=FileNotFoundError):
            self.assertIs(winutil.taskbar_uses_light_theme(), False)


class WorkAreaTest(unittest.TestCase):
    def test_work_area_is_a_non_empty_rectangle(self) -> None:
        area = winutil.work_area()
        self.assertGreater(area.width, 0)
        self.assertGreater(area.height, 0)

    def test_rect_dimensions(self) -> None:
        rect = winutil.Rect(10, 20, 110, 220)
        self.assertEqual((rect.width, rect.height), (100, 200))


class DpiScaleTest(unittest.TestCase):
    def test_scale_is_positive(self) -> None:
        self.assertGreater(winutil.dpi_scale(), 0)

    def test_falls_back_to_one_when_unavailable(self) -> None:
        with mock.patch.object(winutil.ctypes, "windll") as windll:
            windll.user32.GetDpiForSystem.side_effect = AttributeError
            self.assertEqual(winutil.dpi_scale(), 1.0)


if __name__ == "__main__":
    unittest.main()
