import unittest

from PIL import Image, ImageStat

from mc_watch.models import ServerConfig, ServerStatus, Snapshot, State
from mc_watch.tray import icon_label, online_count, render_icon, tooltip

UPDATED = 1730000000.0


def snapshot(states: list[State], updated_at: float | None = UPDATED) -> Snapshot:
    servers = tuple(
        ServerStatus(ServerConfig(f"S{n}", f"s{n}.example.com"), state)
        for n, state in enumerate(states)
    )
    return Snapshot(servers=servers, updated_at=updated_at)


def opaque_pixels(image: Image.Image) -> int:
    # histogram()[0] counts fully transparent pixels; every other bucket is (partly) opaque.
    return sum(image.getchannel("A").histogram()[1:])


def mean_color(image: Image.Image) -> tuple[float, float, float]:
    """Average RGB over the pixels that are not fully transparent."""
    # The alpha channel works as the mask: only its non-zero pixels are counted.
    red, green, blue = ImageStat.Stat(image.convert("RGB"), mask=image.getchannel("A")).mean
    return red, green, blue


class IconLabelTest(unittest.TestCase):
    def test_counts_only_online_servers(self) -> None:
        shot = snapshot([State.ONLINE, State.ONLINE, State.OFFLINE])
        self.assertEqual(online_count(shot), 2)
        self.assertEqual(icon_label(shot), "2")

    def test_none_online_shows_zero(self) -> None:
        shot = snapshot([State.OFFLINE, State.ERROR])
        self.assertEqual(icon_label(shot), "0")

    def test_three_online(self) -> None:
        self.assertEqual(icon_label(snapshot([State.ONLINE] * 3)), "3")

    def test_ten_or_more_collapse_to_nine_plus(self) -> None:
        self.assertEqual(icon_label(snapshot([State.ONLINE] * 9)), "9")
        self.assertEqual(icon_label(snapshot([State.ONLINE] * 10)), "9+")
        self.assertEqual(icon_label(snapshot([State.ONLINE] * 12)), "9+")

    def test_no_servers_has_no_number(self) -> None:
        self.assertIsNone(icon_label(snapshot([])))

    def test_no_number_before_the_first_cycle(self) -> None:
        shot = snapshot([State.QUERYING, State.QUERYING], updated_at=None)
        self.assertIsNone(icon_label(shot))


class TooltipTest(unittest.TestCase):
    def test_online_over_total(self) -> None:
        shot = snapshot([State.ONLINE, State.ONLINE, State.OFFLINE])
        self.assertEqual(tooltip(shot), "mc-watch — 2/3 online")

    def test_before_the_first_cycle(self) -> None:
        shot = snapshot([State.QUERYING], updated_at=None)
        self.assertEqual(tooltip(shot), "mc-watch — consultando…")

    def test_without_servers(self) -> None:
        self.assertEqual(tooltip(snapshot([])), "mc-watch — 0/0 online")


class RenderIconTest(unittest.TestCase):
    def test_size_for_zero_three_and_twelve_servers(self) -> None:
        for count in (0, 3, 12):
            with self.subTest(online=count):
                label = icon_label(snapshot([State.ONLINE] * count + [State.OFFLINE]))
                image = render_icon(label, light_taskbar=False)
                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.mode, "RGBA")
                self.assertGreater(opaque_pixels(image), 0)

    def test_plain_glyph_size(self) -> None:
        image = render_icon(None, light_taskbar=False)
        self.assertEqual(image.size, (64, 64))
        self.assertGreater(opaque_pixels(image), 0)

    def test_different_numbers_draw_different_images(self) -> None:
        zero = render_icon("0", light_taskbar=False)
        three = render_icon("3", light_taskbar=False)
        self.assertNotEqual(zero.tobytes(), three.tobytes())

    def test_plain_glyph_differs_from_a_number(self) -> None:
        self.assertNotEqual(
            render_icon(None, light_taskbar=False).tobytes(),
            render_icon("0", light_taskbar=False).tobytes(),
        )

    def test_light_taskbar_uses_dark_ink_and_dark_taskbar_light_ink(self) -> None:
        dark_ink = mean_color(render_icon("3", light_taskbar=True))
        light_ink = mean_color(render_icon("3", light_taskbar=False))
        self.assertLess(sum(dark_ink) / 3, 80)
        self.assertGreater(sum(light_ink) / 3, 175)

    def test_two_characters_fit_inside_the_canvas(self) -> None:
        image = render_icon("9+", light_taskbar=False)
        left, top, right, bottom = image.getchannel("A").getbbox() or (0, 0, 0, 0)
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(right, 64)
        self.assertLessEqual(bottom, 64)
        self.assertGreater(right - left, 20, "el texto no debe quedar diminuto")


if __name__ == "__main__":
    unittest.main()
