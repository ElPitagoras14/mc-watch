"""Start with Windows, at the user's choice: a value in the user's `Run` registry key.

Nothing machine-wide, and off by default. The registry entry is the only source of truth: if
the user deletes it by hand, the tray menu shows it. From source it is not offered, since it
would register a developer's interpreter and working directory.
"""

import logging
import sys
import winreg
from dataclasses import dataclass, field

APP_NAME = "mc-watch"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

log = logging.getLogger(__name__)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def command_for(executable: str) -> str:
    return f'"{executable}"'


@dataclass
class Autostart:
    """Access to the autostart entry. Writing raises `OSError`."""

    frozen: bool = field(default_factory=is_frozen)
    executable: str = field(default_factory=lambda: sys.executable)
    run_key: str = RUN_KEY

    @property
    def available(self) -> bool:
        return self.frozen

    @property
    def wanted(self) -> str:
        return command_for(self.executable)

    def current(self) -> str | None:
        """What is registered right now, or None."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.run_key) as key:
                value, _ = winreg.QueryValueEx(key, APP_NAME)
        except FileNotFoundError:
            return None
        return str(value)

    def is_enabled(self) -> bool:
        """Never raises: a registry that cannot be read counts as off."""
        try:
            return self.current() is not None
        except OSError:
            return False

    def enable(self) -> None:
        if not self.available:
            raise OSError("el autostart solo está disponible en el ejecutable")
        if self.current() == self.wanted:
            return
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, self.run_key, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, self.wanted)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self.run_key, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.enable()
        else:
            self.disable()

    def refresh(self) -> bool:
        """On startup: if it is on and points elsewhere, point it here.

        Returns True when it rewrote the entry. Never creates one that did not exist.
        """
        if not self.available:
            return False
        current = self.current()
        if current is None or current == self.wanted:
            return False
        self.enable()
        return True
