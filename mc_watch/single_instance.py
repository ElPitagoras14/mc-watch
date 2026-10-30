"""One instance per config directory: a second launch asks the first one to show its panel.

A named mutex says who got there first and a named event carries the "show yourself" signal.
The names include a hash of the config directory, so a dev instance pointed elsewhere with
`MC_WATCH_CONFIG_DIR` lives next to the normal one.
"""

import ctypes
import hashlib
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183
ERROR_ACCESS_DENIED = 5
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0

_kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.OpenEventW.restype = wintypes.HANDLE
_kernel32.SetEvent.argtypes = [wintypes.HANDLE]
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def instance_name(directory: Path) -> str:
    key = str(directory.resolve()).casefold().encode("utf-8")
    return f"Local\\mc-watch-{hashlib.sha1(key).hexdigest()[:8]}"


class Guard:
    """Holds the mutex and the event for as long as the process lives."""

    def __init__(self, mutex: int, event: int) -> None:
        self._mutex = mutex
        self._event = event
        self._closed = threading.Event()

    def serve(self, on_show: Callable[[], None]) -> None:
        """Call `on_show` every time another launch asks for it, on a thread of its own."""
        threading.Thread(
            target=self._wait, args=(on_show,), name="single-instance", daemon=True
        ).start()

    def _wait(self, on_show: Callable[[], None]) -> None:
        while _kernel32.WaitForSingleObject(self._event, INFINITE) == WAIT_OBJECT_0:
            if self._closed.is_set():
                return
            try:
                on_show()
            except Exception:
                log.exception("Falló al mostrar el panel pedido por otra instancia")

    def close(self) -> None:
        self._closed.set()
        _kernel32.SetEvent(self._event)  # wake the waiter so it sees `_closed`
        _kernel32.CloseHandle(self._event)
        _kernel32.CloseHandle(self._mutex)


def _ask_to_show(name: str) -> None:
    event = _kernel32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, f"{name}-show")
    if event:
        _kernel32.SetEvent(event)
        _kernel32.CloseHandle(event)


def acquire(directory: Path) -> Guard | None:
    """The guard if this is the first instance for `directory`; None if one is already running,
    after asking it to show its panel. If uniqueness cannot even be checked it starts anyway:
    not being able to guarantee it must not stop the app."""
    name = instance_name(directory)
    mutex = _kernel32.CreateMutexW(None, False, name)
    error = ctypes.get_last_error()
    if not mutex:
        if error == ERROR_ACCESS_DENIED:  # created by a process with another security context
            _ask_to_show(name)
            return None
        log.warning("No se pudo comprobar si ya hay otra instancia (error %s)", error)
        return Guard(0, _kernel32.CreateEventW(None, False, False, None))
    if error == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(mutex)
        _ask_to_show(name)
        return None
    return Guard(mutex, _kernel32.CreateEventW(None, False, False, f"{name}-show"))
