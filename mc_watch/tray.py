"""The tray icon: online-server count, tooltip and menu. Built on pystray."""

import logging
from collections.abc import Callable

import pystray  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image, ImageDraw, ImageFont

from mc_watch import winutil
from mc_watch.models import Snapshot, State

ICON_SIZE = 64
MAX_SINGLE_DIGIT = 9
DARK_TASKBAR_COLOR = (255, 255, 255, 255)
LIGHT_TASKBAR_COLOR = (27, 27, 27, 255)
FONT_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf")
APP_NAME = "mc-watch"

log = logging.getLogger(__name__)


def online_count(snapshot: Snapshot) -> int:
    return sum(1 for status in snapshot.servers if status.state is State.ONLINE)


def icon_label(snapshot: Snapshot) -> str | None:
    """The number drawn on the icon, or None for the plain glyph.

    No number without servers, nor before the first cycle ends (every server would read as
    "not online" when it simply has not been asked yet).
    """
    if not snapshot.servers or snapshot.updated_at is None:
        return None
    online = online_count(snapshot)
    return str(online) if online <= MAX_SINGLE_DIGIT else f"{MAX_SINGLE_DIGIT}+"


def tooltip(snapshot: Snapshot) -> str:
    if snapshot.updated_at is None and snapshot.servers:
        return f"{APP_NAME} — consultando…"
    return f"{APP_NAME} — {online_count(snapshot)}/{len(snapshot.servers)} online"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def render_icon(label: str | None, light_taskbar: bool) -> Image.Image:
    """A 64x64 RGBA icon: `label` centered in the taskbar-contrasting color."""
    color = LIGHT_TASKBAR_COLOR if light_taskbar else DARK_TASKBAR_COLOR
    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    if label is None:
        # Plain glyph: a ring with a dot.
        draw.ellipse((6, 6, 58, 58), outline=color, width=7)
        draw.ellipse((24, 24, 40, 40), fill=color)
        return image

    limit = ICON_SIZE - 4
    size = 62
    while True:
        font = _load_font(size)
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        width, height = right - left, bottom - top
        if (width <= limit and height <= limit) or size <= 12:
            break
        size -= 2
    x = (ICON_SIZE - width) / 2 - left
    y = (ICON_SIZE - height) / 2 - top
    draw.text((x, y), label, font=font, fill=color)
    return image


class Tray:
    def __init__(
        self,
        *,
        on_toggle: Callable[[], None],
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._last_key: tuple[str | None, str, bool] | None = None
        light = winutil.taskbar_uses_light_theme()
        menu = pystray.Menu(
            # Left click runs the first *default* item, visible or not: it toggles the panel.
            pystray.MenuItem("Alternar", self._safe(on_toggle), default=True, visible=False),
            pystray.MenuItem("Abrir mc-watch", self._safe(on_open)),
            pystray.MenuItem("Salir", self._safe(on_quit)),
        )
        self._icon = pystray.Icon(APP_NAME, render_icon(None, light), APP_NAME, menu)

    @staticmethod
    def _safe(action: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                action()
            except Exception:
                log.exception("Falló una acción del menú de la bandeja")

        return run

    def start(self) -> None:
        """Run the icon's event loop on its own thread."""
        self._icon.run_detached()  # pyright: ignore[reportUnknownMemberType]

    def update(self, snapshot: Snapshot) -> None:
        """Refresh the icon and tooltip. Only touches the shell when something changed."""
        light = winutil.taskbar_uses_light_theme()
        label, title = icon_label(snapshot), tooltip(snapshot)
        key = (label, title, light)
        if key == self._last_key:
            return
        self._last_key = key
        self._icon.icon = render_icon(label, light)
        self._icon.title = title

    def stop(self) -> None:
        self._icon.stop()
