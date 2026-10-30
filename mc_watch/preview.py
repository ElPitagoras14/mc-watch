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
from mc_watch.models import (
    Edition,
    MotdSegment,
    PlayersMode,
    ServerConfig,
    ServerInfo,
    ServerStatus,
    Snapshot,
    State,
)
from mc_watch.view import snapshot_payload

UI_DIR = Path(__file__).resolve().parent / "ui"
UI_FILES = ("styles.css", "app.js")
INJECTION_POINT = '<script src="app.js"></script>'

# A 16x16 grass-and-dirt tile, standing in for a server icon.
ICON = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAANElEQVR4nGOImGZCEmKgvYbKUCsgSn"
    "TRgzAIchlIUg3SQJJqIJeBJNVQJ5HkjVFPDw5PAwBj0QQ+8IyoNAAAAABJRU5ErkJggg=="
)


def _online(
    name: str,
    address: str,
    online: int,
    max_players: int,
    mode: PlayersMode,
    players: tuple[str, ...] = (),
    *,
    motd: tuple[MotdSegment, ...] = (),
    edition: Edition = Edition.JAVA,
    icon: str | None = ICON,
    version: str = "Paper 1.21.4",
) -> ServerStatus:
    return ServerStatus(
        ServerConfig(name, address, edition),
        State.ONLINE,
        online,
        max_players,
        info=ServerInfo(motd=motd, version=version, icon=icon),
        latency_ms=42.0,
        players_mode=mode,
        players=players,
    )


def _detail_servers() -> list[ServerStatus]:
    green, gold, aqua = "#55ff55", "#ffaa00", "#55ffff"
    return [
        _online(
            "Survival",
            "play.example.com",
            3,
            20,
            PlayersMode.FULL,
            ("Steve", "Alex", "Notch"),
            motd=(
                MotdSegment("Bienvenidos a ", green),
                MotdSegment("Survival", gold, bold=True),
                MotdSegment("\nTemporada 4 · ", None, italic=True),
                MotdSegment("tienda", aqua, underlined=True),
            ),
        ),
        _online(
            "Vacío",
            "vacio.example.com",
            0,
            20,
            PlayersMode.FULL,
            motd=(MotdSegment("Nadie por aquí"),),
        ),
        _online(
            "Parcial",
            "parcial.example.com",
            23,
            100,
            PlayersMode.PARTIAL,
            ("Dream", "Technoblade", "Sapnap", "Georgenotfound", "Karl_Jacobs"),
            motd=(MotdSegment("Muestra parcial", gold),),
        ),
        _online("Oculto", "oculto.example.com", 12840, 50000, PlayersMode.HIDDEN),
        _online(
            "Isla",
            "isla.example.com",
            4,
            10,
            PlayersMode.HIDDEN,
            motd=(MotdSegment("Bedrock"),),
            edition=Edition.BEDROCK,
            icon=None,
            version="1.21.50",
        ),
        ServerStatus(
            ServerConfig("Aternos", "mecotronicos.aternos.me", Edition.JAVA),
            State.OFFLINE,
            asleep=True,
        ),
        _online(
            "MOTD con marcado",
            "marcado.example.com",
            1,
            20,
            PlayersMode.FULL,
            ("Steve",),
            motd=(MotdSegment("<img src=x onerror=alert(1)> <b>negrita</b>", "#ff5555"),),
            icon=None,
        ),
        _online(
            "Sin permisos de escritura",
            "readonly.example.com",
            2,
            20,
            PlayersMode.FULL,
            ("Steve", "Alex"),
        ),
    ]


def _scenario(
    label: str,
    statuses: list[ServerStatus],
    updated_at: float | None,
    config_error: str | None = None,
) -> dict[str, Any]:
    snapshot = Snapshot(servers=tuple(statuses), updated_at=updated_at)
    payload = snapshot_payload(
        snapshot,
        config_path=str(config_path()),
        version=__version__,
        config_error=config_error,
    )
    return {"label": label, "payload": payload}


def scenarios(now: float) -> list[dict[str, Any]]:
    mixed = [
        ServerStatus(
            ServerConfig("Survival", "play.example.com", Edition.JAVA), State.ONLINE, 12, 20
        ),
        ServerStatus(
            ServerConfig("Creativo", "creativo.example.com:25570", Edition.JAVA), State.QUERYING
        ),
        ServerStatus(ServerConfig("Minijuegos", "mini.example.com", Edition.JAVA), State.OFFLINE),
        ServerStatus(
            ServerConfig("Servidor roto", "no-existe.invalid", Edition.UNKNOWN), State.ERROR
        ),
        ServerStatus(
            ServerConfig("Isla", "isla.example.com", Edition.BEDROCK), State.ONLINE, 3, 10
        ),
        ServerStatus(ServerConfig("Recién agregado", "nuevo.example.com"), State.QUERYING),
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
        _scenario("Detalle", _detail_servers(), now - 12),
        _scenario("Vacío", [], now - 5),
        _scenario("Muchos (scroll)", many, now - 75),
        _scenario("Antes del 1er ciclo", starting, None),
        _scenario(
            "Config con error",
            [],
            now - 5,
            config_error=f"{config_path()} no es un TOML válido: Expected '=' (at line 3)",
        ),
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
