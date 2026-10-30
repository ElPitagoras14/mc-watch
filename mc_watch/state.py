from dataclasses import replace

from mc_watch.models import (
    Edition,
    ProbeAsleep,
    ProbeOk,
    ProbeResult,
    ProbeUnresolvable,
    QueryOutcome,
    ServerConfig,
    ServerStatus,
    State,
)
from mc_watch.players import players_view

FAILURES_TO_OFFLINE = 2
# Online cycles between two Query attempts once the server failed to answer one.
QUERY_RETRY_CYCLES = 10


def initial_status(server: ServerConfig) -> ServerStatus:
    return ServerStatus(server=server, state=State.QUERYING)


def wants_query(status: ServerStatus) -> bool:
    """Whether the next probe of this server should also try Query (Java only)."""
    return status.server.edition is Edition.JAVA and status.query_wait == 0


def _query_state(prev: ServerStatus, outcome: QueryOutcome) -> tuple[bool | None, int]:
    """`(query_capable, query_wait)` after a probe that ended with `outcome`."""
    match outcome:
        case QueryOutcome.OK:
            return True, 0
        case QueryOutcome.FAILED:
            return False, QUERY_RETRY_CYCLES - 1
        case QueryOutcome.SKIPPED:
            return prev.query_capable, max(prev.query_wait - 1, 0)


def _without_detail(status: ServerStatus) -> ServerStatus:
    """Drop what describes an online server; used as soon as it stops being online."""
    return replace(
        status,
        online=None,
        max=None,
        info=None,
        latency_ms=None,
        players_mode=None,
        players=(),
        asleep=False,
    )


def _pin_edition(server: ServerConfig, edition: Edition) -> ServerConfig:
    # A server of unknown edition gets pinned to whichever protocol answered.
    return replace(server, edition=edition) if server.edition is Edition.UNKNOWN else server


def next_status(prev: ServerStatus, result: ProbeResult) -> ServerStatus:
    """Fold one probe result into the previous status. Pure: no I/O."""
    if isinstance(result, ProbeOk):
        mode, players = players_view(result)
        query_capable, query_wait = _query_state(prev, result.query)
        return replace(
            prev,
            server=_pin_edition(prev.server, result.edition),
            state=State.ONLINE,
            online=result.online,
            max=result.max,
            failures=0,
            info=result.info,
            latency_ms=result.latency_ms,
            players_mode=mode,
            players=players,
            asleep=False,
            query_capable=query_capable,
            query_wait=query_wait,
        )

    if isinstance(result, ProbeAsleep):
        # A definite answer, not a failure: offline right away, without waiting for a second one.
        return replace(
            _without_detail(prev),
            server=_pin_edition(prev.server, result.edition),
            state=State.OFFLINE,
            failures=0,
            asleep=True,
        )

    if isinstance(result, ProbeUnresolvable):
        return replace(_without_detail(prev), state=State.ERROR, failures=0)

    # Unreachable: a single failure keeps the previous state; the second one in a row
    # flips it to offline. A DNS error does not count towards that streak.
    failures = min(prev.failures + 1, FAILURES_TO_OFFLINE)
    if failures >= FAILURES_TO_OFFLINE:
        return replace(_without_detail(prev), state=State.OFFLINE, failures=failures)
    return replace(prev, failures=failures)
