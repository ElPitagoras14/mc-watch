"""Adding servers from the panel and persisting what the poller detects about them."""

import logging
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from mc_watch.config import (
    Config,
    ConfigWriteError,
    ValidationError,
    append_server,
    normalize_name,
    remove_server,
    set_address,
    set_edition,
    set_name,
    validate_new_server,
)
from mc_watch.models import Edition, ProbeOk, ProbeResult, ProbeUnresolvable, Snapshot
from mc_watch.poller import Poller, ProbeFn
from mc_watch.probe import probe

DETECT_TIMEOUT_SECS = 10.0

log = logging.getLogger(__name__)

Reply = dict[str, Any]


def _error(message: str, field: str | None = None) -> Reply:
    return {"ok": False, "field": field, "message": message}


class ServerManager:
    def __init__(
        self,
        directory: Path,
        config: Config,
        poller: Poller,
        probe_fn: ProbeFn = probe,
    ) -> None:
        self._directory = directory
        self._config = config
        self._poller = poller
        self._probe_fn = probe_fn
        self._lock = threading.Lock()
        # Last edition known for each address, to spot servers that were just detected.
        self._editions = {s.address.casefold(): s.edition for s in config.servers}

    def add_server(self, name: str, address: str) -> Reply:
        """Validate, detect the edition, save and start tracking. Blocks for up to a few
        seconds; the page awaits it. Never raises."""
        try:
            with self._lock:
                return self._add(name, address)
        except Exception:
            log.exception("Error inesperado al agregar %r", address)
            return _error("No se pudo agregar el servidor")

    def _add(self, name: str, address: str) -> Reply:
        existing = [status.server.address for status in self._poller.snapshot().servers]
        server = validate_new_server(name, address, existing)
        if isinstance(server, ValidationError):
            return _error(server.message, server.field)
        if not self._config.writable:
            return _error(self._config.error or "No se puede escribir la configuración")

        candidate = server

        async def detect() -> ProbeResult:
            return await self._probe_fn(candidate)

        future = self._poller.submit(detect())
        try:
            result = future.result(timeout=DETECT_TIMEOUT_SECS)
        except TimeoutError:
            future.cancel()
            return _error("La detección tardó demasiado")
        if isinstance(result, ProbeUnresolvable):
            return _error("No se encontró el host", "address")

        edition = result.edition if isinstance(result, ProbeOk) else Edition.UNKNOWN
        server = replace(server, edition=edition)
        try:
            append_server(self._directory, server)
        except ConfigWriteError as error:
            log.warning("No se pudo guardar %s: %s", server.address, error)
            return _error(str(error))

        # Before `poller.add`, whose snapshot reaches `on_snapshot` on another thread.
        self._editions[server.address.casefold()] = edition
        self._poller.add(server, result)
        log.info("Servidor agregado: %s (%s), %s", server.name, server.address, edition.value)
        return {"ok": True}

    def rename_server(self, address: str, name: str) -> Reply:
        """Save the new name and show it right away. Never raises."""
        try:
            with self._lock:
                return self._rename(address, name)
        except Exception:
            log.exception("Error inesperado al renombrar %r", address)
            return _error("No se pudo renombrar el servidor", "name")

    def _rename(self, address: str, name: str) -> Reply:
        if not self._config.writable:
            return _error(self._config.error or "No se puede escribir la configuración", "name")
        normalized = normalize_name(name, address)
        if isinstance(normalized, ValidationError):
            return _error(normalized.message, "name")
        try:
            set_name(self._directory, address, normalized)
        except ConfigWriteError as error:
            log.warning("No se pudo renombrar %s: %s", address, error)
            return _error(str(error), "name")
        self._poller.rename(address, normalized)
        return {"ok": True, "name": normalized}

    def change_address(self, address: str, new_address: str) -> Reply:
        """Move the server to another address: validate, detect the edition there, save and
        start its status over. Blocks for up to a few seconds; the page awaits it. Never raises."""
        try:
            with self._lock:
                return self._change_address(address, new_address)
        except Exception:
            log.exception("Error inesperado al cambiar la dirección de %r", address)
            return _error("No se pudo cambiar la dirección del servidor", "address")

    def _change_address(self, address: str, new_address: str) -> Reply:
        statuses = self._poller.snapshot().servers
        key = address.casefold()
        current = next((s.server for s in statuses if s.server.address.casefold() == key), None)
        if current is None:
            return _error("El servidor ya no está en la lista", "address")
        new_address = new_address.strip()
        if new_address == current.address:
            return {"ok": True, "address": current.address, "name": current.name}

        others = [s.server.address for s in statuses if s.server is not current]
        server = validate_new_server("", new_address, others)
        if isinstance(server, ValidationError):
            return _error(server.message, server.field)
        if not self._config.writable:
            return _error(self._config.error or "No se puede escribir la configuración", "address")

        candidate = server

        async def detect() -> ProbeResult:
            return await self._probe_fn(candidate)

        future = self._poller.submit(detect())
        try:
            result = future.result(timeout=DETECT_TIMEOUT_SECS)
        except TimeoutError:
            future.cancel()
            return _error("La detección tardó demasiado", "address")
        if isinstance(result, ProbeUnresolvable):
            return _error("No se encontró el host", "address")

        edition = result.edition if isinstance(result, ProbeOk) else Edition.UNKNOWN
        # A server named after its address would keep showing one that is gone.
        name = new_address if current.name == current.address else current.name
        try:
            set_address(
                self._directory,
                current.address,
                new_address,
                edition,
                name if name != current.name else None,
            )
        except ConfigWriteError as error:
            log.warning("No se pudo cambiar la dirección de %s: %s", current.address, error)
            return _error(str(error), "address")

        # Before `poller.change_address`, whose snapshot reaches `on_snapshot` on another thread.
        self._editions.pop(current.address.casefold(), None)
        self._editions[new_address.casefold()] = edition
        self._poller.change_address(
            current.address, replace(server, name=name, edition=edition), result
        )
        log.info("%s: dirección cambiada a %s, %s", current.address, new_address, edition.value)
        return {"ok": True, "address": new_address, "name": name}

    def remove_server(self, address: str) -> Reply:
        """Delete the server from the file and stop tracking it. Never raises."""
        try:
            with self._lock:
                return self._remove(address)
        except Exception:
            log.exception("Error inesperado al eliminar %r", address)
            return _error("No se pudo eliminar el servidor")

    def _remove(self, address: str) -> Reply:
        if not self._config.writable:
            return _error(self._config.error or "No se puede escribir la configuración")
        try:
            # False when the entry is gone from the file already: it is gone either way.
            remove_server(self._directory, address)
        except ConfigWriteError as error:
            log.warning("No se pudo eliminar %s: %s", address, error)
            return _error(str(error))
        self._editions.pop(address.casefold(), None)
        self._poller.remove(address)
        return {"ok": True}

    def on_snapshot(self, snapshot: Snapshot) -> None:
        """Poller subscriber: save the edition of servers that were unknown until now."""
        for status in snapshot.servers:
            server = status.server
            key = server.address.casefold()
            previous = self._editions.get(key)
            if server.edition is previous:
                continue
            self._editions[key] = server.edition
            if previous is not Edition.UNKNOWN or not self._config.writable:
                continue
            try:
                if set_edition(self._directory, server.address, server.edition):
                    log.info("%s: edición detectada, %s", server.address, server.edition.value)
            except ConfigWriteError as error:
                log.warning("No se pudo guardar la edición de %s: %s", server.address, error)
