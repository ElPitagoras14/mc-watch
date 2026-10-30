"""Small Win32 helpers (ctypes / registry). Windows only."""

import ctypes
import ctypes.wintypes as wt
import logging
import winreg
from dataclasses import dataclass

log = logging.getLogger(__name__)

SPI_GETWORKAREA = 0x0030
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
LIGHT_THEME_VALUE = "SystemUsesLightTheme"
BASE_DPI = 96

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SW_SHOW = 5
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002

_user32 = ctypes.windll.user32
_user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
_user32.FindWindowW.restype = wt.HWND
_user32.GetForegroundWindow.restype = wt.HWND
_user32.SetForegroundWindow.argtypes = [wt.HWND]
_user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
_user32.IsWindowVisible.argtypes = [wt.HWND]
_user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_user32.SetWindowPos.argtypes = [
    wt.HWND,
    wt.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wt.UINT,
]
_user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def work_area() -> Rect:
    """Primary monitor area not covered by the taskbar, in physical pixels."""
    rect = wt.RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        raise ctypes.WinError()
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


def dpi_scale() -> float:
    """System DPI scale (1.0 at 96 dpi). Falls back to 1.0 when it cannot be read."""
    try:
        return ctypes.windll.user32.GetDpiForSystem() / BASE_DPI
    except (AttributeError, OSError):
        return 1.0


def taskbar_uses_light_theme() -> bool:
    """True when the Windows taskbar is light; False when dark or unknown."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            value, _ = winreg.QueryValueEx(key, LIGHT_THEME_VALUE)
    except OSError:
        log.debug("No se pudo leer el tema de la barra de tareas; se asume oscuro")
        return False
    return bool(value)


def find_window(title: str) -> int | None:
    handle = _user32.FindWindowW(None, title)
    return int(handle) if handle else None


def window_rect(handle: int) -> Rect:
    rect = wt.RECT()
    if not _user32.GetWindowRect(handle, ctypes.byref(rect)):
        raise ctypes.WinError()
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


def place_window(handle: int, x: int, y: int, width: int, height: int) -> None:
    """Move and resize in physical pixels without activating or changing the z-order."""
    if not _user32.SetWindowPos(handle, None, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE):
        raise ctypes.WinError()


def set_topmost(handle: int, topmost: bool) -> None:
    """Keep the window above all others (or not), without moving, resizing or activating it.

    Used instead of pywebview's `window.on_top` setter: that one assigns `Form.TopMost` from the
    calling thread, which can deadlock against the UI thread because pythonnet holds the GIL.
    ctypes releases it for the duration of the call.
    """
    insert_after = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    if not _user32.SetWindowPos(handle, insert_after, 0, 0, 0, 0, flags):
        raise ctypes.WinError()


def hide_from_taskbar(handle: int) -> None:
    """Keep the window out of the taskbar and Alt+Tab. Apply while it is hidden."""
    style = _user32.GetWindowLongPtrW(handle, GWL_EXSTYLE)
    _user32.SetWindowLongPtrW(handle, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)


def is_visible(handle: int) -> bool:
    return bool(_user32.IsWindowVisible(handle))


def is_foreground(handle: int) -> bool:
    return _user32.GetForegroundWindow() == handle


def bring_to_front(handle: int) -> bool:
    """Show the window and give it keyboard focus; returns whether it got the foreground."""
    _user32.ShowWindow(handle, SW_SHOW)
    # A synthetic Alt press lifts the foreground lock that would otherwise reject us.
    _user32.keybd_event(VK_MENU, 0, 0, 0)
    _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    _user32.SetForegroundWindow(handle)
    return is_foreground(handle)
