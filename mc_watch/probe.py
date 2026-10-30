"""The only module that talks to mcstatus. Everything else sees `ProbeResult`."""

import asyncio
import logging
import re
import socket
import time
from collections.abc import Coroutine
from typing import Any

import dns.exception
from mcstatus import BedrockServer, JavaServer
from mcstatus.motd import Motd
from mcstatus.motd.components import (
    AnyFormatting,
    AnyMinecraftColor,
    BedrockFormatting,
    JavaFormatting,
    WebColor,
)

from mc_watch.models import (
    Edition,
    MotdSegment,
    ProbeAsleep,
    ProbeOk,
    ProbeResult,
    ProbeUnreachable,
    ProbeUnresolvable,
    QueryOutcome,
    SamplePlayer,
    ServerConfig,
    ServerInfo,
)

PROBE_TIMEOUT_SECS = 3.0

# A Java proxy that keeps answering while the real server is off (Aternos and similar) announces
# protocol -1 and a version such as "§c● Offline". The protocol alone is not enough: other
# proxies use -1 to show unrelated text.
ASLEEP_PROTOCOL = -1
ASLEEP_KEYWORDS = ("offline", "sleeping")
# lazymc answers the ping itself while the real server is off, starting or stopping, with one of
# its default MOTDs and an otherwise normal version and protocol.
LAZYMC_MOTDS = ("server is sleeping", "server is starting", "server going to sleep")

ICON_PREFIX = "data:image/png;base64,"
_CODES_RE = re.compile(r"§.")

# Hex for the colours mcstatus names: the Java ones plus the Bedrock-only ones.
_COLORS = {
    "BLACK": "#000000",
    "DARK_BLUE": "#0000aa",
    "DARK_GREEN": "#00aa00",
    "DARK_AQUA": "#00aaaa",
    "DARK_RED": "#aa0000",
    "DARK_PURPLE": "#aa00aa",
    "GOLD": "#ffaa00",
    "GRAY": "#aaaaaa",
    "DARK_GRAY": "#555555",
    "BLUE": "#5555ff",
    "GREEN": "#55ff55",
    "AQUA": "#55ffff",
    "RED": "#ff5555",
    "LIGHT_PURPLE": "#ff55ff",
    "YELLOW": "#ffff55",
    "WHITE": "#ffffff",
    "MINECOIN_GOLD": "#ddd605",
    "MATERIAL_QUARTZ": "#e3d4d1",
    "MATERIAL_IRON": "#cecaca",
    "MATERIAL_NETHERITE": "#443a3b",
    "MATERIAL_REDSTONE": "#971607",
    "MATERIAL_COPPER": "#b4684d",
    "MATERIAL_GOLD": "#deb12d",
    "MATERIAL_EMERALD": "#119f36",
    "MATERIAL_DIAMOND": "#2cbaa8",
    "MATERIAL_LAPIS": "#21497b",
    "MATERIAL_AMETHYST": "#9a5cc6",
    "MATERIAL_RESIN": "#eb7214",
}

log = logging.getLogger(__name__)


async def probe(server: ServerConfig, *, query: bool = False) -> ProbeResult:
    """Run one query with the protocol of the server's edition. Never raises (except for
    cancellation). An unknown edition tries both protocols, Java first. With `query`, a Java
    server is also asked for its player list over Query, which never affects the result."""
    match server.edition:
        case Edition.JAVA:
            return await _guarded(_java(server, query), server.address)
        case Edition.BEDROCK:
            return await _guarded(_bedrock(server), server.address)
        case Edition.UNKNOWN:
            return await _detect(server)


async def _guarded(
    attempt: Coroutine[Any, Any, ProbeOk | ProbeAsleep], address: str
) -> ProbeResult:
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
    java = asyncio.create_task(_guarded(_java(server, False), address))
    bedrock = asyncio.create_task(_guarded(_bedrock(server), address))
    try:
        java_result = await java
        # Bedrock would fail to resolve the same host, so there is no point in waiting. A
        # sleeping server answered over Java, so it is Java.
        if isinstance(java_result, ProbeOk | ProbeAsleep | ProbeUnresolvable):
            return java_result
        bedrock_result = await bedrock
        if isinstance(bedrock_result, ProbeOk):
            return bedrock_result
        return ProbeUnreachable()
    finally:
        for task in (java, bedrock):
            task.cancel()
        await asyncio.gather(java, bedrock, return_exceptions=True)


def _strip_codes(text: str) -> str:
    return _CODES_RE.sub("", text)


def _is_asleep(protocol: int, version_name: str, motd: Motd) -> bool:
    plain = _strip_codes(version_name).casefold()
    if protocol == ASLEEP_PROTOCOL and any(word in plain for word in ASLEEP_KEYWORDS):
        return True
    return any(text in motd.to_plain().casefold() for text in LAZYMC_MOTDS)


def _motd_segments(motd: Motd) -> tuple[MotdSegment, ...]:
    """Flatten a parsed MOTD into text runs with their colour and styles.

    Like mcstatus, only `RESET` clears the styles: a colour does not, so bold inherited from
    a parent JSON component survives the colour of its children.
    """
    segments: list[MotdSegment] = []
    color: str | None = None
    bold = italic = underlined = strikethrough = False
    for part in motd.parsed:
        if isinstance(part, str):
            if part:
                segments.append(MotdSegment(part, color, bold, italic, underlined, strikethrough))
        elif isinstance(part, WebColor):
            color = part.hex
        elif isinstance(part, AnyMinecraftColor):
            color = _COLORS.get(part.name)
        elif isinstance(part, AnyFormatting):
            match part:
                case JavaFormatting.BOLD | BedrockFormatting.BOLD:
                    bold = True
                case JavaFormatting.ITALIC | BedrockFormatting.ITALIC:
                    italic = True
                case JavaFormatting.UNDERLINED:
                    underlined = True
                case JavaFormatting.STRIKETHROUGH:
                    strikethrough = True
                case JavaFormatting.RESET | BedrockFormatting.RESET:
                    color = None
                    bold = italic = underlined = strikethrough = False
                case _:
                    pass  # obfuscated text is shown as it comes
        # Invalid codes and translation tags carry no text.
    return tuple(segments)


def _server_info(motd: Motd, version_name: str, icon: str | None) -> ServerInfo:
    return ServerInfo(
        motd=_motd_segments(motd),
        version=_strip_codes(version_name).strip(),
        icon=icon if icon is not None and icon.startswith(ICON_PREFIX) else None,
    )


async def _query_players(java: JavaServer) -> tuple[QueryOutcome, tuple[str, ...]]:
    try:
        response = await java.async_query(tries=1)
    except Exception as error:  # a server without Query is the usual case, not a problem
        log.debug("%s: sin Query (%r)", java.address, error)
        return QueryOutcome.FAILED, ()
    return QueryOutcome.OK, tuple(response.players.list)


async def _java(server: ServerConfig, query: bool) -> ProbeOk | ProbeAsleep:
    started = time.monotonic()
    java = await JavaServer.async_lookup(server.address, timeout=PROBE_TIMEOUT_SECS)
    # Both start together, so Query adds no time to a cycle.
    status_task = asyncio.ensure_future(java.async_status(tries=1))
    query_task = asyncio.ensure_future(_query_players(java)) if query else None
    tasks: list[asyncio.Future[Any]] = [
        task for task in (status_task, query_task) if task is not None
    ]
    try:
        status = await status_task
        if _is_asleep(status.version.protocol, status.version.name, status.motd):
            return ProbeAsleep()
        outcome, names = QueryOutcome.SKIPPED, ()
        if query_task is not None:
            # What is left of the probe's budget, so a mute Query cannot cost the ping result.
            left = PROBE_TIMEOUT_SECS * 0.9 - (time.monotonic() - started)
            try:
                outcome, names = await asyncio.wait_for(query_task, timeout=max(left, 0))
            except TimeoutError:
                outcome = QueryOutcome.FAILED
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return ProbeOk(
        online=status.players.online,
        max=status.players.max,
        latency_ms=status.latency,
        edition=Edition.JAVA,
        info=_server_info(status.motd, status.version.name, status.icon),
        sample=tuple(
            SamplePlayer(player.name, player.id) for player in status.players.sample or ()
        ),
        query=outcome,
        query_players=names,
    )


async def _bedrock(server: ServerConfig) -> ProbeOk:
    bedrock = BedrockServer.lookup(server.address, timeout=PROBE_TIMEOUT_SECS)
    status = await bedrock.async_status(tries=1)
    return ProbeOk(
        online=status.players.online,
        max=status.players.max,
        latency_ms=status.latency,
        edition=Edition.BEDROCK,
        info=_server_info(status.motd, status.version.name, None),
    )
