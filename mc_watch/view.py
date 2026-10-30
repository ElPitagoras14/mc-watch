"""Turns a `Snapshot` into the JSON-able dict that `mcw.render()` receives in the UI."""

from dataclasses import asdict
from typing import Any

from mc_watch.config import Settings
from mc_watch.models import ServerStatus, Snapshot


def _server_payload(status: ServerStatus) -> dict[str, Any]:
    info = status.info
    return {
        "name": status.server.name,
        "address": status.server.address,
        "edition": status.server.edition.value,
        "state": status.state.value,
        "online": status.online,
        "max": status.max,
        "latency_ms": status.latency_ms,
        "version": info.version if info else None,
        "motd": [asdict(segment) for segment in info.motd] if info else [],
        "icon": info.icon if info else None,
        "players_mode": status.players_mode.value if status.players_mode else None,
        "players": list(status.players),
        "asleep": status.asleep,
    }


def snapshot_payload(
    snapshot: Snapshot,
    *,
    config_path: str,
    version: str,
    config_error: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    return {
        "servers": [_server_payload(status) for status in snapshot.servers],
        "updated_at": snapshot.updated_at,
        "config_path": config_path,
        "config_error": config_error,
        "version": version,
        "settings": asdict(settings or Settings()),
    }
