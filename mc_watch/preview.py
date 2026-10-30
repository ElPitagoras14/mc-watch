"""Open the panel in a browser with sample data, without the tray or any network.

Usage: uv run python -m mc_watch.preview [--no-open]
"""

import argparse
import json
import shutil
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any

from mc_watch import __version__
from mc_watch.config import config_path
from mc_watch.models import ServerConfig, ServerStatus, Snapshot, State
from mc_watch.view import snapshot_payload

UI_DIR = Path(__file__).resolve().parent / "ui"
UI_FILES = ("styles.css", "app.js")
INJECTION_POINT = '<script src="app.js"></script>'


def _scenario(label: str, statuses: list[ServerStatus], updated_at: float | None) -> dict[str, Any]:
    snapshot = Snapshot(servers=tuple(statuses), updated_at=updated_at)
    payload = snapshot_payload(snapshot, config_path=str(config_path()), version=__version__)
    return {"label": label, "payload": payload}


def scenarios(now: float) -> list[dict[str, Any]]:
    mixed = [
        ServerStatus(ServerConfig("Survival", "play.example.com"), State.ONLINE, 12, 20),
        ServerStatus(ServerConfig("Creativo", "creativo.example.com:25570"), State.QUERYING),
        ServerStatus(ServerConfig("Minijuegos", "mini.example.com"), State.OFFLINE),
        ServerStatus(ServerConfig("Servidor roto", "no-existe.invalid"), State.ERROR),
    ]
    cycle = [State.ONLINE, State.OFFLINE, State.ERROR, State.QUERYING]
    many = [
        ServerStatus(
            ServerConfig(f"Servidor {n}", f"s{n}.example.com"),
            cycle[n % 4],
            *((n, 50) if cycle[n % 4] is State.ONLINE else (None, None)),
        )
        for n in range(1, 13)
    ]
    starting = [
        ServerStatus(ServerConfig("Survival", "play.example.com"), State.QUERYING),
        ServerStatus(ServerConfig("Creativo", "creativo.example.com"), State.QUERYING),
    ]
    return [
        _scenario("Cuatro estados", mixed, now - 12),
        _scenario("Vacío", [], now - 5),
        _scenario("Muchos (scroll)", many, now - 75),
        _scenario("Antes del 1er ciclo", starting, None),
    ]


def build_preview(directory: Path, now: float | None = None) -> Path:
    """Write a self-contained copy of the UI with the sample scenarios; return its index."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in UI_FILES:
        shutil.copy(UI_DIR / name, directory / name)

    data = json.dumps(scenarios(time.time() if now is None else now), ensure_ascii=False)
    # A server name containing "</script>" must not be able to close the tag.
    data = data.replace("</", "<\\/")
    injected = f"<script>window.__MCW_PREVIEW__ = {data};</script>\n  {INJECTION_POINT}"

    html = (UI_DIR / "index.html").read_text(encoding="utf-8")
    if INJECTION_POINT not in html:
        raise RuntimeError(f"index.html ya no contiene {INJECTION_POINT!r}")
    index = directory / "index.html"
    index.write_text(html.replace(INJECTION_POINT, injected), encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Abre el panel en el navegador con datos de ejemplo."
    )
    parser.add_argument("--no-open", action="store_true", help="solo genera los archivos")
    args = parser.parse_args(argv)

    index = build_preview(Path(tempfile.mkdtemp(prefix="mc-watch-preview-")))
    print(index.as_uri())
    if not args.no_open:
        webbrowser.open(index.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
