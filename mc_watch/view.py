"""Turns a `Snapshot` into the JSON-able dict that `mcw.render()` receives in the UI."""

from typing import Any

from mc_watch.models import Snapshot


def snapshot_payload(snapshot: Snapshot, *, config_path: str, version: str) -> dict[str, Any]:
    return {
        "servers": [
            {
                "name": status.server.name,
                "address": status.server.address,
                "state": status.state.value,
                "online": status.online,
                "max": status.max,
            }
            for status in snapshot.servers
        ],
        "updated_at": snapshot.updated_at,
        "config_path": config_path,
        "version": version,
    }
