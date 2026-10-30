import asyncio
import socket
import time
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

import dns.exception
from mcstatus.motd import Motd

from mc_watch import probe as probe_module
from mc_watch.models import (
    Edition,
    MotdSegment,
    ProbeOk,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
    ServerInfo,
)

SERVER = ServerConfig(name="Survival", address="play.example.com", edition=Edition.JAVA)
BEDROCK = ServerConfig(name="Isla", address="isla.example.com", edition=Edition.BEDROCK)
UNKNOWN = ServerConfig(name="Nuevo", address="nuevo.example.com")


def fake_java(status: Any) -> mock.MagicMock:
    java = mock.MagicMock()
    java.async_status = status
    return java


INFO = ServerInfo(motd=(MotdSegment("Hola"),), version="1.21.4")


def response(
    online: int = 7,
    max_players: int = 20,
    latency: float = 12.5,
    *,
    protocol: int = 767,
    version: str = "1.21.4",
    motd: Any = "Hola",
    icon: str | None = None,
    sample: list[Any] | None = None,
    bedrock: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        players=SimpleNamespace(online=online, max=max_players, sample=sample),
        version=SimpleNamespace(name=version, protocol=protocol),
        motd=Motd.parse(motd, bedrock=bedrock),
        icon=icon,
        latency=latency,
    )


class ProbeTest(unittest.IsolatedAsyncioTestCase):
    def patch_lookup(self, lookup: mock.AsyncMock) -> None:
        patcher = mock.patch.object(probe_module.JavaServer, "async_lookup", lookup)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_ok_response(self) -> None:
        status = mock.AsyncMock(return_value=response(7, 20, 12.5))
        lookup = mock.AsyncMock(return_value=fake_java(status))
        self.patch_lookup(lookup)

        result = await probe_module.probe(SERVER)

        self.assertEqual(result, ProbeOk(online=7, max=20, latency_ms=12.5, info=INFO))
        lookup.assert_awaited_once_with("play.example.com", timeout=3.0)
        status.assert_awaited_once_with(tries=1)

    async def test_address_with_port_is_passed_through(self) -> None:
        status = mock.AsyncMock(return_value=response())
        lookup = mock.AsyncMock(return_value=fake_java(status))
        self.patch_lookup(lookup)

        await probe_module.probe(ServerConfig("X", "example.com:25599", Edition.JAVA))

        lookup.assert_awaited_once_with("example.com:25599", timeout=3.0)

    async def test_gaierror_is_unresolvable(self) -> None:
        status = mock.AsyncMock(side_effect=socket.gaierror(11001, "getaddrinfo failed"))
        self.patch_lookup(mock.AsyncMock(return_value=fake_java(status)))

        self.assertEqual(await probe_module.probe(SERVER), ProbeUnresolvable())

    async def test_timeout_is_unreachable(self) -> None:
        status = mock.AsyncMock(side_effect=TimeoutError())
        self.patch_lookup(mock.AsyncMock(return_value=fake_java(status)))

        self.assertEqual(await probe_module.probe(SERVER), ProbeUnreachable())

    async def test_connection_refused_is_unreachable(self) -> None:
        status = mock.AsyncMock(side_effect=ConnectionRefusedError())
        self.patch_lookup(mock.AsyncMock(return_value=fake_java(status)))

        self.assertEqual(await probe_module.probe(SERVER), ProbeUnreachable())

    async def test_invalid_response_is_unreachable(self) -> None:
        status = mock.AsyncMock(side_effect=ValueError("respuesta inválida"))
        self.patch_lookup(mock.AsyncMock(return_value=fake_java(status)))

        self.assertEqual(await probe_module.probe(SERVER), ProbeUnreachable())

    async def test_dns_library_error_is_unreachable(self) -> None:
        lookup = mock.AsyncMock(side_effect=dns.exception.Timeout())
        self.patch_lookup(lookup)

        self.assertEqual(await probe_module.probe(SERVER), ProbeUnreachable())

    async def test_unexpected_exception_is_unreachable_and_logged(self) -> None:
        status = mock.AsyncMock(side_effect=RuntimeError("bug de parseo"))
        self.patch_lookup(mock.AsyncMock(return_value=fake_java(status)))

        with self.assertLogs("mc_watch.probe", level="ERROR"):
            result = await probe_module.probe(SERVER)

        self.assertEqual(result, ProbeUnreachable())

    async def test_overall_timeout_covers_a_hanging_server(self) -> None:
        async def hang(**_: Any) -> None:
            await asyncio.sleep(10)

        self.patch_lookup(mock.AsyncMock(return_value=fake_java(hang)))

        with mock.patch.object(probe_module, "PROBE_TIMEOUT_SECS", 0.05):
            result = await asyncio.wait_for(probe_module.probe(SERVER), timeout=2)

        self.assertEqual(result, ProbeUnreachable())

    async def test_cancellation_is_not_swallowed(self) -> None:
        async def hang(**_: Any) -> None:
            await asyncio.sleep(10)

        self.patch_lookup(mock.AsyncMock(return_value=fake_java(hang)))

        task = asyncio.create_task(probe_module.probe(SERVER))
        await asyncio.sleep(0.01)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task


async def hang(**_: Any) -> None:
    await asyncio.sleep(10)


class BedrockProbeTest(unittest.IsolatedAsyncioTestCase):
    def patch_lookup(self, status: Any) -> mock.MagicMock:
        server = mock.MagicMock()
        server.async_status = status
        lookup = mock.MagicMock(return_value=server)
        patcher = mock.patch.object(probe_module.BedrockServer, "lookup", lookup)
        patcher.start()
        self.addCleanup(patcher.stop)
        return lookup

    async def test_ok_response(self) -> None:
        status = mock.AsyncMock(return_value=response(3, 10, 40.0, bedrock=True))
        lookup = self.patch_lookup(status)

        result = await probe_module.probe(BEDROCK)

        self.assertEqual(result, ProbeOk(3, 10, 40.0, Edition.BEDROCK, INFO))
        lookup.assert_called_once_with("isla.example.com", timeout=3.0)
        status.assert_awaited_once_with(tries=1)

    async def test_timeout_is_unreachable(self) -> None:
        self.patch_lookup(mock.AsyncMock(side_effect=TimeoutError()))
        self.assertEqual(await probe_module.probe(BEDROCK), ProbeUnreachable())

    async def test_gaierror_is_unresolvable(self) -> None:
        self.patch_lookup(mock.AsyncMock(side_effect=socket.gaierror(11001, "getaddrinfo failed")))
        self.assertEqual(await probe_module.probe(BEDROCK), ProbeUnresolvable())

    async def test_bedrock_server_is_not_probed_as_java(self) -> None:
        self.patch_lookup(mock.AsyncMock(return_value=response(bedrock=True)))
        java_lookup = mock.AsyncMock()
        with mock.patch.object(probe_module.JavaServer, "async_lookup", java_lookup):
            await probe_module.probe(BEDROCK)
        java_lookup.assert_not_awaited()


class DetectTest(unittest.IsolatedAsyncioTestCase):
    def patch_protocols(self, java: Any, bedrock: Any) -> None:
        java_patch = mock.patch.object(
            probe_module.JavaServer,
            "async_lookup",
            mock.AsyncMock(return_value=fake_java(java)),
        )
        bedrock_server = mock.MagicMock()
        bedrock_server.async_status = bedrock
        bedrock_patch = mock.patch.object(
            probe_module.BedrockServer, "lookup", mock.MagicMock(return_value=bedrock_server)
        )
        for patcher in (java_patch, bedrock_patch):
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_only_java_answers(self) -> None:
        self.patch_protocols(mock.AsyncMock(return_value=response(5, 20)), hang)
        result = await probe_module.probe(UNKNOWN)
        self.assertEqual(result, ProbeOk(5, 20, 12.5, Edition.JAVA, INFO))

    async def test_only_bedrock_answers(self) -> None:
        self.patch_protocols(
            mock.AsyncMock(side_effect=ConnectionRefusedError()),
            mock.AsyncMock(return_value=response(2, 10, 30.0, bedrock=True)),
        )
        result = await probe_module.probe(UNKNOWN)
        self.assertEqual(result, ProbeOk(2, 10, 30.0, Edition.BEDROCK, INFO))

    async def test_java_wins_when_both_answer(self) -> None:
        self.patch_protocols(
            mock.AsyncMock(return_value=response(5, 20)),
            mock.AsyncMock(return_value=response(1, 10, bedrock=True)),
        )
        result = await probe_module.probe(UNKNOWN)
        assert isinstance(result, ProbeOk)
        self.assertEqual(result.edition, Edition.JAVA)

    async def test_java_wins_even_if_bedrock_answers_first(self) -> None:
        async def slow_java(**_: Any) -> SimpleNamespace:
            await asyncio.sleep(0.05)
            return response(5, 20)

        self.patch_protocols(slow_java, mock.AsyncMock(return_value=response(1, 10, bedrock=True)))
        result = await probe_module.probe(UNKNOWN)
        self.assertEqual(result, ProbeOk(5, 20, 12.5, Edition.JAVA, INFO))

    async def test_unresolvable_does_not_wait_for_bedrock(self) -> None:
        self.patch_protocols(mock.AsyncMock(side_effect=socket.gaierror(11001, "x")), hang)
        started = time.monotonic()
        result = await probe_module.probe(UNKNOWN)
        self.assertEqual(result, ProbeUnresolvable())
        self.assertLess(time.monotonic() - started, 1)

    async def test_nobody_answers_takes_one_timeout_not_two(self) -> None:
        self.patch_protocols(hang, hang)
        started = time.monotonic()
        with mock.patch.object(probe_module, "PROBE_TIMEOUT_SECS", 0.2):
            result = await probe_module.probe(UNKNOWN)
        elapsed = time.monotonic() - started
        self.assertEqual(result, ProbeUnreachable())
        self.assertLess(elapsed, 0.35, "los dos intentos deben correr en paralelo")

    async def test_cancellation_cancels_both_attempts(self) -> None:
        self.patch_protocols(hang, hang)
        task = asyncio.create_task(probe_module.probe(UNKNOWN))
        await asyncio.sleep(0.02)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    unittest.main()
