from dataclasses import replace

from mc_watch.models import (
    ProbeOk,
    ProbeResult,
    ProbeUnresolvable,
    ServerConfig,
    ServerStatus,
    State,
)

FAILURES_TO_OFFLINE = 2


def initial_status(server: ServerConfig) -> ServerStatus:
    return ServerStatus(server=server, state=State.QUERYING)


def next_status(prev: ServerStatus, result: ProbeResult) -> ServerStatus:
    """Fold one probe result into the previous status. Pure: no I/O."""
    if isinstance(result, ProbeOk):
        return replace(prev, state=State.ONLINE, online=result.online, max=result.max, failures=0)

    if isinstance(result, ProbeUnresolvable):
        return replace(prev, state=State.ERROR, online=None, max=None, failures=0)

    # Unreachable: a single failure keeps the previous state; the second one in a row
    # flips it to offline. A DNS error does not count towards that streak.
    failures = min(prev.failures + 1, FAILURES_TO_OFFLINE)
    if failures >= FAILURES_TO_OFFLINE:
        return replace(prev, state=State.OFFLINE, online=None, max=None, failures=failures)
    return replace(prev, failures=failures)
