"""The only module that talks to mcstatus. Everything else sees `ProbeResult`."""

import asyncio
import logging
import socket

import dns.exception
from mcstatus import JavaServer

from mc_watch.models import (
    ProbeOk,
    ProbeResult,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
)

PROBE_TIMEOUT_SECS = 3.0

log = logging.getLogger(__name__)


async def probe(server: ServerConfig) -> ProbeResult:
    """Run one Server List Ping. Never raises (except for cancellation)."""
    try:
        return await asyncio.wait_for(_query(server), timeout=PROBE_TIMEOUT_SECS)
    # gaierror is an OSError subclass, so it has to be caught before it.
    except socket.gaierror as error:
        log.info("%s: el host no resuelve (%s)", server.address, error)
        return ProbeUnresolvable()
    except TimeoutError:
        log.info("%s: sin respuesta en %.0f s", server.address, PROBE_TIMEOUT_SECS)
        return ProbeUnreachable()
    except (OSError, ValueError, dns.exception.DNSException) as error:
        log.info("%s: consulta fallida: %r", server.address, error)
        return ProbeUnreachable()
    except Exception:
        # mcstatus does not document its exceptions: a parsing bug must look like an
        # unreachable server, not take the poller down.
        log.exception("%s: error inesperado en la consulta", server.address)
        return ProbeUnreachable()


async def _query(server: ServerConfig) -> ProbeOk:
    java = await JavaServer.async_lookup(server.address, timeout=PROBE_TIMEOUT_SECS)
    status = await java.async_status(tries=1)
    return ProbeOk(
        online=status.players.online,
        max=status.players.max,
        latency_ms=status.latency,
    )
