import unittest

from mc_watch import winutil
from mc_watch.window import (
    DEFAULT_HEIGHT,
    MARGIN,
    MAX_HEIGHT,
    MIN_HEIGHT,
    PANEL_WIDTH,
    ReopenGuard,
    clamp_height,
    panel_geometry,
)

AREA = winutil.Rect(0, 0, 1920, 1040)  # 1080p with a 40 px taskbar at the bottom


class ClampHeightTest(unittest.TestCase):
    def test_inside_the_range_is_kept(self) -> None:
        self.assertEqual(clamp_height(300), 300)

    def test_below_minimum_is_raised(self) -> None:
        self.assertEqual(clamp_height(10), MIN_HEIGHT)

    def test_above_maximum_is_lowered(self) -> None:
        self.assertEqual(clamp_height(5000), MAX_HEIGHT)

    def test_fractions_are_rounded(self) -> None:
        self.assertEqual(clamp_height(300.6), 301)

    def test_default_is_inside_the_range(self) -> None:
        self.assertEqual(clamp_height(DEFAULT_HEIGHT), DEFAULT_HEIGHT)


class PanelGeometryTest(unittest.TestCase):
    def test_anchored_to_bottom_right_of_the_work_area(self) -> None:
        x, y, width, height = panel_geometry(AREA, 1.0, 300)

        self.assertEqual((width, height), (PANEL_WIDTH, 300))
        self.assertEqual(x + width, AREA.right - MARGIN)
        self.assertEqual(y + height, AREA.bottom - MARGIN)

    def test_bottom_edge_stays_put_when_the_height_changes(self) -> None:
        _, y_short, _, h_short = panel_geometry(AREA, 1.0, 250)
        _, y_tall, _, h_tall = panel_geometry(AREA, 1.0, 550)

        self.assertEqual(y_short + h_short, y_tall + h_tall)
        self.assertLess(y_tall, y_short, "un panel más alto crece hacia arriba")

    def test_never_overlaps_the_taskbar(self) -> None:
        _, y, _, height = panel_geometry(AREA, 1.0, MAX_HEIGHT)
        self.assertLessEqual(y + height, AREA.bottom)

    def test_scales_with_dpi(self) -> None:
        x, y, width, height = panel_geometry(AREA, 1.5, 300)

        self.assertEqual((width, height), (540, 450))
        self.assertEqual(x + width, AREA.right - round(MARGIN * 1.5))
        self.assertEqual(y + height, AREA.bottom - round(MARGIN * 1.5))

    def test_stays_inside_a_small_work_area(self) -> None:
        small = winutil.Rect(0, 0, 300, 200)
        x, y, _, _ = panel_geometry(small, 1.0, MAX_HEIGHT)
        self.assertGreaterEqual(x, small.left)
        self.assertGreaterEqual(y, small.top)

    def test_respects_a_work_area_that_does_not_start_at_the_origin(self) -> None:
        # Taskbar on the left: the work area starts at x=60.
        area = winutil.Rect(60, 0, 1920, 1080)
        x, _, width, _ = panel_geometry(area, 1.0, 300)
        self.assertEqual(x + width, area.right - MARGIN)
        self.assertGreaterEqual(x, area.left)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class ReopenGuardTest(unittest.TestCase):
    def test_does_not_block_before_any_blur(self) -> None:
        self.assertFalse(ReopenGuard(FakeClock()).blocks_reopen())

    def test_blocks_right_after_a_blur_hide(self) -> None:
        clock = FakeClock()
        guard = ReopenGuard(clock, window_secs=0.3)
        guard.note_blur_hide()
        clock.now += 0.1
        self.assertTrue(guard.blocks_reopen())

    def test_stops_blocking_after_the_window(self) -> None:
        clock = FakeClock()
        guard = ReopenGuard(clock, window_secs=0.3)
        guard.note_blur_hide()
        clock.now += 0.31
        self.assertFalse(guard.blocks_reopen())


if __name__ == "__main__":
    unittest.main()
