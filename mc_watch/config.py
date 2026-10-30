import logging
import os
import threading
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import tomlkit
import tomlkit.exceptions
from tomlkit.items import AoT, Table

from mc_watch.models import Edition, ServerConfig

APP_DIR_NAME = "mc-watch"
CONFIG_DIR_ENV = "MC_WATCH_CONFIG_DIR"
CONFIG_FILE_NAME = "config.toml"
DEFAULT_POLL_INTERVAL_SECS = 60
MIN_POLL_INTERVAL_SECS = 30
MAX_NAME_LENGTH = 40

log = logging.getLogger(__name__)

# Every read-modify-write of the file goes through this lock.
_write_lock = threading.Lock()


@dataclass(frozen=True)
class Config:
    poll_interval_secs: int = DEFAULT_POLL_INTERVAL_SECS
    servers: tuple[ServerConfig, ...] = ()
    warnings: tuple[str, ...] = field(default=(), compare=False)
    # False when the file exists but could not be read or parsed: the app must not write it.
    writable: bool = True
    error: str | None = field(default=None, compare=False)


class ConfigWriteError(Exception):
    """The config file could not be updated; it was left as it was."""


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
        message = f"No se pudo leer {path}: {error}"
        return Config(warnings=(message,), writable=False, error=message)

    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        message = f"{path} no es un TOML válido: {error}"
        log.warning("%s; se usan los valores por defecto", message)
        return Config(warnings=(message,), writable=False, error=message)

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
        edition = _parse_edition(table.get("edition"))
        if edition is None:
            warnings.append(
                f"servers #{index} ({name}): edition inválida {table['edition']!r}; se autodetecta"
            )
            edition = Edition.UNKNOWN
        servers.append(ServerConfig(name=name.strip(), address=address, edition=edition))
    return tuple(servers)


def _parse_edition(value: Any) -> Edition | None:
    """`UNKNOWN` when absent, `None` when present but not one of the three values."""
    if value is None:
        return Edition.UNKNOWN
    try:
        return Edition(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class ValidationError:
    field: Literal["name", "address"]
    message: str


def validate_new_server(
    name: str, address: str, existing: Iterable[str]
) -> ServerConfig | ValidationError:
    """Check the add-server form. `existing` are the addresses already in the list."""
    address = address.strip()
    name = name.strip()
    if not address:
        return ValidationError("address", "La dirección es obligatoria")
    if not is_valid_address(address):
        return ValidationError("address", "La dirección no es válida (host o host:puerto)")
    if len(name) > MAX_NAME_LENGTH:
        return ValidationError("name", f"El nombre admite hasta {MAX_NAME_LENGTH} caracteres")
    taken = {other.casefold() for other in existing}
    if address.casefold() in taken:
        return ValidationError("address", "Ese servidor ya está en la lista")
    return ServerConfig(name=name or address, address=address)


def append_server(directory: Path | None, server: ServerConfig) -> None:
    """Add `server` at the end of the file, creating it if needed."""

    def edit(document: tomlkit.TOMLDocument) -> bool:
        entry = tomlkit.table()
        entry["name"] = server.name
        entry["address"] = server.address
        entry["edition"] = server.edition.value
        servers = _servers_array(document)
        if len(servers) > 0 and not servers[-1].as_string().endswith("\n\n"):
            servers[-1].add(tomlkit.nl())
        servers.append(entry)
        return True

    _update(directory, edit)


def set_edition(directory: Path | None, address: str, edition: Edition) -> bool:
    """Record the detected edition of the entry with that address. Returns whether the file
    was written: it is not when the entry is gone or already has that edition."""

    def edit(document: tomlkit.TOMLDocument) -> bool:
        for entry in _servers_array(document):
            fields = cast("dict[str, Any]", entry)
            current = fields.get("address")
            if not isinstance(current, str) or current.strip().casefold() != address.casefold():
                continue
            if fields.get("edition") == edition.value:
                return False
            entry["edition"] = edition.value
            return True
        return False

    return _update(directory, edit)


def _servers_array(document: tomlkit.TOMLDocument) -> list[Table]:
    if "servers" not in document:
        document["servers"] = tomlkit.aot()
    servers = document["servers"]
    if not isinstance(servers, AoT):
        raise ConfigWriteError("servers no es una lista de tablas [[servers]]")
    return cast("list[Table]", servers)


def _update(directory: Path | None, edit: Any) -> bool:
    """Parse the file as it is on disk, apply `edit` and replace the file atomically."""
    path = config_path(directory)
    with _write_lock:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        except (OSError, UnicodeDecodeError) as error:
            raise ConfigWriteError(f"No se pudo leer {path}: {error}") from error
        try:
            document = tomlkit.parse(text)
        except tomlkit.exceptions.TOMLKitError as error:
            raise ConfigWriteError(f"{path} tiene un error de sintaxis") from error

        if not edit(document):
            return False

        temporary = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(tomlkit.dumps(document), encoding="utf-8", newline="")
            os.replace(temporary, path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise ConfigWriteError(f"No se pudo guardar {path}: {error}") from error
        return True
