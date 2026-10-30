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


class QueryOutcome(Enum):
    SKIPPED = "skipped"
    OK = "ok"
    FAILED = "failed"


class PlayersMode(Enum):
    FULL = "full"
    PARTIAL = "partial"
    HIDDEN = "hidden"


@dataclass(frozen=True)
class MotdSegment:
    text: str
    color: str | None = None  # "#rrggbb"
    bold: bool = False
    italic: bool = False
    underlined: bool = False
    strikethrough: bool = False


@dataclass(frozen=True)
class SamplePlayer:
    name: str
    id: str


@dataclass(frozen=True)
class ServerInfo:
    motd: tuple[MotdSegment, ...] = ()
    version: str = ""
    icon: str | None = None  # only "data:image/png;base64,..."


@dataclass(frozen=True)
class ProbeOk:
    online: int
    max: int
    latency_ms: float
    edition: Edition = Edition.JAVA
    info: ServerInfo = ServerInfo()
    sample: tuple[SamplePlayer, ...] = ()
    query: QueryOutcome = QueryOutcome.SKIPPED
    query_players: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbeUnreachable:
    """Timeout, refused connection or invalid response."""


@dataclass(frozen=True)
class ProbeUnresolvable:
    """The host name does not resolve."""


@dataclass(frozen=True)
class ProbeAsleep:
    """A Java proxy answered, but the server behind it is switched off (Aternos and similar)."""

    edition: Edition = Edition.JAVA


ProbeResult = ProbeOk | ProbeAsleep | ProbeUnreachable | ProbeUnresolvable


@dataclass(frozen=True)
class ServerStatus:
    server: ServerConfig
    state: State
    online: int | None = None
    max: int | None = None
    failures: int = 0
    info: ServerInfo | None = None
    latency_ms: float | None = None
    players_mode: PlayersMode | None = None
    players: tuple[str, ...] = ()
    asleep: bool = False
    # None until Query was tried; `query_wait` counts online cycles left before retrying a failure.
    query_capable: bool | None = None
    query_wait: int = 0


@dataclass(frozen=True)
class Snapshot:
    """Result of one polling cycle; `updated_at` is None until the first cycle ends."""

    servers: tuple[ServerStatus, ...]
    updated_at: float | None
