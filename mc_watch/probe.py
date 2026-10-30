"""The only module that talks to mcstatus. Everything else sees `ProbeResult`."""

import asyncio
import logging
import socket
from collections.abc import Coroutine
from typing import Any

import dns.exception
from mcstatus import BedrockServer, JavaServer

from mc_watch.models import (
    Edition,
    ProbeOk,
    ProbeResult,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
)

PROBE_TIMEOUT_SECS = 3.0

log = logging.getLogger(__name__)


async def probe(server: ServerConfig) -> ProbeResult:
    """Run one query with the protocol of the server's edition. Never raises (except for
    cancellation). An unknown edition tries both protocols, Java first."""
    match server.edition:
        case Edition.JAVA:
            return await _guarded(_java(server), server.address)
        case Edition.BEDROCK:
            return await _guarded(_bedrock(server), server.address)
        case Edition.UNKNOWN:
            return await _detect(server)


async def _guarded(attempt: Coroutine[Any, Any, ProbeOk], address: str) -> ProbeResult:
    """Bound one attempt by the timeout and map every failure to a `ProbeResult`."""
    try:
        return await asyncio.wait_for(attempt, timeout=PROBE_TIMEOUT_SECS)
    # gaierror is an OSError subclass, so it has to be caught before it.
    except socket.gaierror as error:
        log.info("%s: el host no resuelve (%s)", address, error)
        return ProbeUnresolvable()
    except TimeoutError:
        log.info("%s: sin respuesta en %.0f s", address, PROBE_TIMEOUT_SECS)
        return ProbeUnreachable()
    except (OSError, ValueError, dns.exception.DNSException) as error:
        log.info("%s: consulta fallida: %r", address, error)
        return ProbeUnreachable()
    except Exception:
        # mcstatus does not document its exceptions: a parsing bug must look like an
        # unreachable server, not take the poller down.
        log.exception("%s: error inesperado en la consulta", address)
        return ProbeUnreachable()


async def _detect(server: ServerConfig) -> ProbeResult:
    """Both attempts start together but Java has priority, so the result is the same as
    trying Java and then Bedrock while taking one timeout instead of two."""
    address = server.address
    java = asyncio.create_task(_guarded(_java(server), address))
    bedrock = asyncio.create_task(_guarded(_bedrock(server), address))
    try:
        java_result = await java
        # Bedrock would fail to resolve the same host, so there is no point in waiting.
        if isinstance(java_result, ProbeOk | ProbeUnresolvable):
            return java_result
        bedrock_result = await bedrock
        if isinstance(bedrock_result, ProbeOk):
            return bedrock_result
        return ProbeUnreachable()
    finally:
        for task in (java, bedrock):
            task.cancel()
        await asyncio.gather(java, bedrock, return_exceptions=True)


async def _java(server: ServerConfig) -> ProbeOk:
    java = await JavaServer.async_lookup(server.address, timeout=PROBE_TIMEOUT_SECS)
    status = await java.async_status(tries=1)
    return ProbeOk(
        online=status.players.online,
        max=status.players.max,
        latency_ms=status.latency,
        edition=Edition.JAVA,
    )


async def _bedrock(server: ServerConfig) -> ProbeOk:
    bedrock = BedrockServer.lookup(server.address, timeout=PROBE_TIMEOUT_SECS)
    status = await bedrock.async_status(tries=1)
    return ProbeOk(
        online=status.players.online,
        max=status.players.max,
        latency_ms=status.latency,
        edition=Edition.BEDROCK,
    )
