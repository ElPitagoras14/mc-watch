import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from mc_watch.models import ServerConfig

APP_DIR_NAME = "mc-watch"
CONFIG_DIR_ENV = "MC_WATCH_CONFIG_DIR"
CONFIG_FILE_NAME = "config.toml"
DEFAULT_POLL_INTERVAL_SECS = 60
MIN_POLL_INTERVAL_SECS = 30

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    poll_interval_secs: int = DEFAULT_POLL_INTERVAL_SECS
    servers: tuple[ServerConfig, ...] = ()
    warnings: tuple[str, ...] = field(default=(), compare=False)


def config_dir() -> Path:
    override = os.environ.get(CONFIG_DIR_ENV)
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / APP_DIR_NAME


def config_path(directory: Path | None = None) -> Path:
    return (directory or config_dir()) / CONFIG_FILE_NAME


def is_valid_address(address: str) -> bool:
    """`host` or `host:port`, with the port in 1-65535."""
    if not address or any(char.isspace() for char in address):
        return False
    if address.count(":") > 1:
        return False
    host, separator, port = address.partition(":")
    if not host:
        return False
    if not separator:
        return True
    return port.isascii() and port.isdigit() and 1 <= int(port) <= 65535


def load_config(directory: Path | None = None) -> Config:
    """Read the config file. Never writes it and never raises on bad content."""
    path = config_path(directory)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        log.info("No existe %s; se inicia sin servidores", path)
        return Config()
    except OSError as error:
        log.warning("No se pudo leer %s: %s", path, error)
        return Config(warnings=(f"No se pudo leer {path}: {error}",))

    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        message = f"{path} no es un TOML válido: {error}"
        log.warning("%s; se usan los valores por defecto", message)
        return Config(warnings=(message,))

    warnings: list[str] = []
    interval = _parse_interval(data.get("poll_interval_secs"), warnings)
    servers = _parse_servers(data.get("servers"), warnings)
    for warning in warnings:
        log.warning("%s", warning)
    log.info("Configuración cargada: %d servidor(es), intervalo %d s", len(servers), interval)
    return Config(poll_interval_secs=interval, servers=servers, warnings=tuple(warnings))


def _parse_interval(value: Any, warnings: list[str]) -> int:
    if value is None:
        return DEFAULT_POLL_INTERVAL_SECS
    if isinstance(value, bool) or not isinstance(value, int):
        warnings.append(
            f"poll_interval_secs debe ser un entero; se usa {DEFAULT_POLL_INTERVAL_SECS}"
        )
        return DEFAULT_POLL_INTERVAL_SECS
    if value < MIN_POLL_INTERVAL_SECS:
        warnings.append(
            f"poll_interval_secs={value} es menor al mínimo; se usa {MIN_POLL_INTERVAL_SECS}"
        )
        return MIN_POLL_INTERVAL_SECS
    return value


def _parse_servers(value: Any, warnings: list[str]) -> tuple[ServerConfig, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        warnings.append("servers debe ser una lista de tablas [[servers]]")
        return ()

    servers: list[ServerConfig] = []
    for index, entry in enumerate(cast("list[Any]", value), start=1):
        if not isinstance(entry, dict):
            warnings.append(f"servers #{index}: no es una tabla; se ignora")
            continue
        table = cast("dict[str, Any]", entry)
        name = table.get("name")
        address = table.get("address")
        if not isinstance(name, str) or not name.strip():
            warnings.append(f"servers #{index}: falta name; se ignora")
            continue
        if not isinstance(address, str) or not address.strip():
            warnings.append(f"servers #{index} ({name}): falta address; se ignora")
            continue
        address = address.strip()
        if not is_valid_address(address):
            warnings.append(f"servers #{index} ({name}): address inválida {address!r}; se ignora")
            continue
        servers.append(ServerConfig(name=name.strip(), address=address))
    return tuple(servers)
