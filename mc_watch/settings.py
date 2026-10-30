"""Saving the settings dialog: validate, write `config.toml` and apply without restarting."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mc_watch.config import (
    MAX_POLL_INTERVAL_SECS,
    MAX_VISIBLE_SERVERS,
    MIN_POLL_INTERVAL_SECS,
    MIN_VISIBLE_SERVERS,
    Config,
    ConfigWriteError,
    Settings,
    save_settings,
)
from mc_watch.notify import Notifications
from mc_watch.poller import Poller

log = logging.getLogger(__name__)

Reply = dict[str, Any]


def _error(message: str, field: str | None = None) -> Reply:
    return {"ok": False, "field": field, "message": message}


def _whole(value: Any, low: int, high: int) -> int | None:
    """`value` when it is a whole number in `low`-`high`. JSON numbers arrive as int or float."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if value != int(value) or not low <= value <= high:
        return None
    return int(value)


class SettingsManager:
    def __init__(
        self,
        directory: Path,
        config: Config,
        poller: Poller,
        notifications: Notifications,
        on_change: Callable[[], None] = lambda: None,
    ) -> None:
        self._directory = directory
        self._config = config
        self._poller = poller
        self._notifications = notifications
        self._on_change = on_change
        self._lock = threading.Lock()
        self._current = config.settings

    @property
    def current(self) -> Settings:
        return self._current

    def save(self, raw: dict[str, Any]) -> Reply:
        """Called from the page with the dialog's values. Never raises."""
        try:
            with self._lock:
                reply = self._save(raw)
        except Exception:
            log.exception("Error inesperado al guardar los ajustes")
            return _error("No se pudieron guardar los ajustes")
        if reply["ok"]:
            self._on_change()
        return reply

    def _save(self, raw: dict[str, Any]) -> Reply:
        notifications = raw.get("notifications")
        if not isinstance(notifications, bool):
            return _error("Valor inválido", "notifications")
        interval = _whole(
            raw.get("poll_interval_secs"), MIN_POLL_INTERVAL_SECS, MAX_POLL_INTERVAL_SECS
        )
        if interval is None:
            message = f"Entre {MIN_POLL_INTERVAL_SECS} y {MAX_POLL_INTERVAL_SECS}"
            return _error(message, "poll_interval_secs")
        visible = _whole(raw.get("max_visible_servers"), MIN_VISIBLE_SERVERS, MAX_VISIBLE_SERVERS)
        if visible is None:
            return _error(
                f"Entre {MIN_VISIBLE_SERVERS} y {MAX_VISIBLE_SERVERS}", "max_visible_servers"
            )
        if not self._config.writable:
            return _error(self._config.error or "No se puede escribir la configuración")

        settings = Settings(notifications, interval, visible)
        try:
            save_settings(self._directory, settings)
        except ConfigWriteError as error:
            log.warning("No se pudieron guardar los ajustes: %s", error)
            return _error(str(error))

        self._current = settings
        self._notifications.set_enabled(settings.notifications)
        self._poller.set_interval(settings.poll_interval_secs)
        log.info(
            "Ajustes guardados: notificaciones %s, intervalo %d s, %d visibles",
            "sí" if settings.notifications else "no",
            settings.poll_interval_secs,
            settings.max_visible_servers,
        )
        return {"ok": True}
