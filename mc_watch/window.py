"""The panel window: a frameless pywebview window anchored to the tray corner."""

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import webview

from mc_watch import winutil

WINDOW_TITLE = "mc-watch"
UI_INDEX = Path(__file__).resolve().parent / "ui" / "index.html"

PANEL_WIDTH = 360
MIN_HEIGHT = 120
MAX_HEIGHT = 600
DEFAULT_HEIGHT = 360
MARGIN = 12
REOPEN_GUARD_SECS = 0.3
BACKGROUND = "#151515"

log = logging.getLogger(__name__)

Payload = dict[str, Any]


def clamp_height(height: float) -> int:
    return min(max(round(height), MIN_HEIGHT), MAX_HEIGHT)


def panel_geometry(area: winutil.Rect, scale: float, height: int) -> tuple[int, int, int, int]:
    """(x, y, width, height) in physical pixels, anchored to the work area's bottom-right.

    The bottom edge stays put when the height changes, so a taller panel grows upwards
    and never slides under the taskbar.
    """
    width_px = round(PANEL_WIDTH * scale)
    height_px = round(height * scale)
    margin = round(MARGIN * scale)
    x = max(area.right - margin - width_px, area.left)
    y = max(area.bottom - margin - height_px, area.top)
    return x, y, width_px, height_px


class ReopenGuard:
    """Ignores a toggle that arrives right after a blur hid the panel.

    Clicking the tray icon takes the focus away from the panel first (so it hides on blur)
    and only then delivers the click, which would reopen it. That click means "close".
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window_secs: float = REOPEN_GUARD_SECS,
    ) -> None:
        self._clock = clock
        self._window_secs = window_secs
        self._hidden_at: float | None = None

    def note_blur_hide(self) -> None:
        self._hidden_at = self._clock()

    def blocks_reopen(self) -> bool:
        return self._hidden_at is not None and self._clock() - self._hidden_at < self._window_secs


class _Api:
    """Methods the page can call through `window.pywebview.api`.

    pywebview walks the public attributes of this object to expose them to JavaScript, and
    recurses endlessly into `window.native`, so the panel is kept under a private name.
    """

    def __init__(self, panel: "Panel") -> None:
        self._panel = panel

    def hide(self) -> None:
        self._panel.hide()

    def on_blur(self) -> None:
        self._panel.on_blur()

    def toggle_pin(self) -> bool:
        return self._panel.toggle_pin()

    def get_snapshot(self) -> Payload:
        return self._panel.get_payload()

    def resize(self, height: float) -> None:
        self._panel.resize(height)

    def add_server(self, name: str, address: str) -> Payload:
        return self._panel.add_server(name, address)

    def refresh(self) -> None:
        self._panel.refresh()

    def refresh_server(self, address: str) -> None:
        self._panel.refresh_server(address)

    def rename_server(self, address: str, name: str) -> Payload:
        return self._panel.rename_server(address, name)

    def change_address(self, address: str, new_address: str) -> Payload:
        return self._panel.change_address(address, new_address)

    def remove_server(self, address: str) -> Payload:
        return self._panel.remove_server(address)

    def save_settings(self, values: Payload) -> Payload:
        return self._panel.save_settings(values)


class Panel:
    def __init__(
        self,
        get_payload: Callable[[], Payload],
        add_server: Callable[[str, str], Payload] | None = None,
        refresh: Callable[[], None] | None = None,
        rename_server: Callable[[str, str], Payload] | None = None,
        change_address: Callable[[str, str], Payload] | None = None,
        remove_server: Callable[[str], Payload] | None = None,
        refresh_server: Callable[[str], None] | None = None,
        save_settings: Callable[[Payload], Payload] | None = None,
    ) -> None:
        self.get_payload = get_payload
        self._add_server = add_server
        self._refresh = refresh
        self._rename_server = rename_server
        self._change_address = change_address
        self._remove_server = remove_server
        self._refresh_server = refresh_server
        self._save_settings = save_settings
        self._lock = threading.RLock()
        self._guard = ReopenGuard()
        self._pinned = False
        self._visible = False
        self._height = DEFAULT_HEIGHT
        self._window: webview.Window | None = None
        self._handle: int | None = None
        self._loaded = threading.Event()

    @property
    def pinned(self) -> bool:
        return self._pinned

    @property
    def visible(self) -> bool:
        return self._visible

    def create(self) -> "webview.Window":
        """Create the (hidden) window. The GUI loop is started by the caller."""
        window = webview.create_window(  # pyright: ignore[reportUnknownMemberType]
            WINDOW_TITLE,
            url=str(UI_INDEX),
            js_api=_Api(self),
            width=PANEL_WIDTH,
            height=DEFAULT_HEIGHT,
            frameless=True,
            easy_drag=False,
            resizable=False,
            hidden=True,
            on_top=False,
            background_color=BACKGROUND,
            zoomable=False,
        )
        if window is None:
            raise RuntimeError("pywebview no pudo crear la ventana del panel")
        window.events.loaded += self._on_loaded
        self._window = window
        return window

    def _on_loaded(self) -> None:
        handle = winutil.find_window(WINDOW_TITLE)
        if handle is None:
            log.warning("No se encontró el handle de la ventana %r", WINDOW_TITLE)
        else:
            self._handle = handle
            winutil.hide_from_taskbar(handle)
            self._place()
        self._loaded.set()
        log.debug("Ventana del panel cargada (hwnd=%s)", handle)

    def wait_loaded(self, timeout: float | None = None) -> bool:
        return self._loaded.wait(timeout)

    def _place(self) -> None:
        if self._handle is None:
            return
        x, y, width, height = panel_geometry(winutil.work_area(), winutil.dpi_scale(), self._height)
        winutil.place_window(self._handle, x, y, width, height)

    def show(self) -> None:
        window = self._window
        if window is None:
            return
        with self._lock:
            self._visible = True
            self._place()
            window.show()
            if self._handle is not None and not winutil.bring_to_front(self._handle):
                log.debug("El panel no obtuvo el foco al mostrarse")

    def hide(self) -> None:
        window = self._window
        if window is None:
            return
        with self._lock:
            self._visible = False
            window.hide()

    def toggle(self) -> None:
        """Left click on the tray icon."""
        with self._lock:
            if self._visible:
                self.hide()
            elif self._guard.blocks_reopen():
                log.debug("Click de la bandeja ignorado: el panel acaba de ocultarse por blur")
            else:
                self.show()

    def on_blur(self) -> None:
        with self._lock:
            if self._pinned or not self._visible:
                return
            self._guard.note_blur_hide()
            self.hide()

    def toggle_pin(self) -> bool:
        with self._lock:
            self._pinned = not self._pinned
            if self._handle is not None:
                winutil.set_topmost(self._handle, self._pinned)
            return self._pinned

    def resize(self, height: float) -> None:
        clamped = clamp_height(height)
        with self._lock:
            if clamped == self._height:
                return
            self._height = clamped
            self._place()

    def add_server(self, name: str, address: str) -> Payload:
        """Called from the page; blocks until the server is detected and saved."""
        if self._add_server is None:
            return {"ok": False, "field": None, "message": "No se pueden agregar servidores"}
        return self._add_server(name, address)

    def rename_server(self, address: str, name: str) -> Payload:
        """Called from the page; blocks until the new name is saved."""
        if self._rename_server is None:
            return {"ok": False, "field": None, "message": "No se puede renombrar"}
        return self._rename_server(address, name)

    def change_address(self, address: str, new_address: str) -> Payload:
        """Called from the page; blocks until the new address is detected and saved."""
        if self._change_address is None:
            return {"ok": False, "field": None, "message": "No se puede cambiar la dirección"}
        return self._change_address(address, new_address)

    def remove_server(self, address: str) -> Payload:
        """Called from the page; blocks until the server is deleted from the file."""
        if self._remove_server is None:
            return {"ok": False, "field": None, "message": "No se puede eliminar"}
        return self._remove_server(address)

    def save_settings(self, values: Payload) -> Payload:
        """Called from the page; blocks until the settings are saved and applied."""
        if self._save_settings is None:
            return {"ok": False, "field": None, "message": "No se pueden guardar los ajustes"}
        return self._save_settings(values)

    def refresh_server(self, address: str) -> None:
        """Called from the page; blocks until that server was polled."""
        if self._refresh_server is not None:
            self._refresh_server(address)

    def refresh(self) -> None:
        """Called from the page: poll every server now."""
        if self._refresh is not None:
            self._refresh()

    def push(self, payload: Payload) -> None:
        """Send fresh data to the page. Safe to call from any thread."""
        self._call_page("render", payload)

    def open_server(self, address: str | None) -> None:
        """Show the panel on that server's detail, or on the list when `address` is None or the
        server is gone. Safe to call from any thread."""
        self._call_page("openDetail", address)
        self.show()

    def _call_page(self, function: str, argument: Any) -> None:
        window = self._window
        if window is None or not self._loaded.is_set():
            return
        try:
            window.evaluate_js(f"window.mcw && window.mcw.{function}({json.dumps(argument)})")
        except Exception:
            log.exception("No se pudo llamar a mcw.%s en la ventana", function)

    def destroy(self) -> None:
        window = self._window
        if window is not None:
            try:
                window.destroy()
            except Exception:
                log.exception("Error al destruir la ventana")
