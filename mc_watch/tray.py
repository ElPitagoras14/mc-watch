"""The tray icon: online-server count, tooltip and menu. Built on pystray."""

import ctypes
import logging
import time
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

import pystray  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image, ImageDraw, ImageFont
from pystray._util import win32  # pyright: ignore[reportMissingTypeStubs]

from mc_watch import winutil
from mc_watch.models import Snapshot, State

ICON_SIZE = 64
MAX_SINGLE_DIGIT = 9
DARK_TASKBAR_COLOR = (255, 255, 255, 255)
LIGHT_TASKBAR_COLOR = (27, 27, 27, 255)
FONT_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf")
APP_NAME = "mc-watch"
APP_ICON_COLOR = (63, 185, 80, 255)  # the UI's green: readable on a light or dark Explorer
FOREGROUND_WAIT_SECS = 0.5

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


def app_icon() -> Image.Image:
    """The plain glyph in the app's own color, for the .exe and its shortcuts."""
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((24, 24, 232, 232), outline=APP_ICON_COLOR, width=28)
    draw.ellipse((96, 96, 160, 160), fill=APP_ICON_COLOR)
    return image


# pystray ships no types: as `Any` the checker does not flag every internal attribute.
_PystrayIcon: Any = pystray.Icon


def _force_foreground(hwnd: int) -> None:
    """Make `hwnd` the foreground window even if Windows resists.

    `SetForegroundWindow` fails silently when the process did not receive the last user input,
    which depends on how it was launched: from a terminal it works, with a double click in
    Explorer it does not. Without foreground the menu draws but does not highlight what is under
    the mouse. Attaching to the foreground thread's input queue allows it.
    """
    user32: Any = ctypes.windll.user32  # pyright: ignore[reportUnknownMemberType]
    kernel32: Any = ctypes.windll.kernel32  # pyright: ignore[reportUnknownMemberType]
    mine = kernel32.GetCurrentThreadId()
    front = user32.GetForegroundWindow()
    theirs = user32.GetWindowThreadProcessId(front, None) if front else 0
    attached = bool(theirs and theirs != mine and user32.AttachThreadInput(mine, theirs, True))
    try:
        win32.SetForegroundWindow(hwnd)
        # The switch is asynchronous: a menu opened before `hwnd` is active draws unhighlighted.
        deadline = time.monotonic() + FOREGROUND_WAIT_SECS
        while user32.GetForegroundWindow() != hwnd and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        if attached:
            user32.AttachThreadInput(mine, theirs, False)


class _WindowsIcon(_PystrayIcon):
    """pystray opens the menu on a different window from the one it brings to the front.

    `Icon._run` creates two windows, `_hwnd` and `_menu_hwnd`. Before opening the menu it calls
    `SetForegroundWindow(_hwnd)` but passes `_menu_hwnd` as the menu's owner, and Windows needs
    the owner to be the foreground window. With pywebview's message loop on the main thread and
    the tray on another, the menu would be dead.
    """

    # Left click toggles the panel. It is not the default menu item's action: that one is
    # "Abrir mc-watch", drawn in bold, and choosing it from the menu always opens.
    on_left_click: Callable[[], None] | None = None

    def _on_notify(self, wparam: int, lparam: int) -> None:
        if lparam == win32.WM_LBUTTONUP and self.on_left_click is not None:
            self.on_left_click()
            return
        if lparam != win32.WM_RBUTTONUP or not self._menu_handle:
            super()._on_notify(wparam, lparam)  # pyright: ignore[reportUnknownMemberType]
            return

        # pystray only evaluates `checked` when it builds the menu: do it fresh, now.
        self.update_menu()
        _force_foreground(self._menu_hwnd)
        point = wintypes.POINT()
        win32.GetCursorPos(ctypes.byref(point))
        hmenu, descriptors = self._menu_handle
        index = win32.TrackPopupMenuEx(
            hmenu,
            win32.TPM_RIGHTALIGN | win32.TPM_BOTTOMALIGN | win32.TPM_RETURNCMD,
            point.x,
            point.y,
            self._menu_hwnd,
            None,
        )
        # KB135788: without this the menu can stay open when dismissed by clicking outside.
        win32.PostMessage(self._menu_hwnd, 0x0000, 0, 0)  # WM_NULL
        if index > 0:
            descriptors[index - 1](self)


class Tray:
    def __init__(
        self,
        *,
        on_toggle: Callable[[], None],
        on_open: Callable[[], None],
        on_refresh: Callable[[], None],
        on_quit: Callable[[], None],
        on_autostart: Callable[[], None],
        autostart_on: Callable[[], bool],
        autostart_available: bool,
    ) -> None:
        self._last_key: tuple[str | None, str, bool] | None = None
        light = winutil.taskbar_uses_light_theme()
        menu = pystray.Menu(
            pystray.MenuItem("Abrir mc-watch", self._safe(on_open), default=True),
            pystray.MenuItem("Actualizar ahora", self._safe(on_refresh)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Arrancar con la sesión",
                self._safe(on_autostart),
                checked=lambda _item: autostart_on(),  # pyright: ignore[reportUnknownLambdaType]
                enabled=autostart_available,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._safe(on_quit)),
        )
        self._icon = _WindowsIcon(APP_NAME, render_icon(None, light), APP_NAME, menu)
        self._icon.on_left_click = self._safe(on_toggle)

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
