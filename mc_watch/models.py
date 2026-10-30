from dataclasses import dataclass
from enum import Enum


class State(Enum):
    QUERYING = "querying"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class Edition(Enum):
    JAVA = "java"
    BEDROCK = "bedrock"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ServerConfig:
    name: str
    address: str
    edition: Edition = Edition.UNKNOWN


@dataclass(frozen=True)
class ProbeOk:
    online: int
    max: int
    latency_ms: float
    edition: Edition = Edition.JAVA


@dataclass(frozen=True)
class ProbeUnreachable:
    """Timeout, refused connection or invalid response."""


@dataclass(frozen=True)
class ProbeUnresolvable:
    """The host name does not resolve."""


ProbeResult = ProbeOk | ProbeUnreachable | ProbeUnresolvable


@dataclass(frozen=True)
class ServerStatus:
    server: ServerConfig
    state: State
    online: int | None = None
    max: int | None = None
    failures: int = 0


@dataclass(frozen=True)
class Snapshot:
    """Result of one polling cycle; `updated_at` is None until the first cycle ends."""

    servers: tuple[ServerStatus, ...]
    updated_at: float | None
