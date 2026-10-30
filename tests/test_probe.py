import asyncio
import socket
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

import dns.exception

from mc_watch import probe as probe_module
from mc_watch.models import (
    ProbeOk,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
)

SERVER = ServerConfig(name="Survival", address="play.example.com")


def fake_java(status: Any) -> mock.MagicMock:
    java = mock.MagicMock()
    java.async_status = status
    return java


def response(online: int = 7, max_players: int = 20, latency: float = 12.5) -> SimpleNamespace:
    return SimpleNamespace(players=SimpleNamespace(online=online, max=max_players), latency=latency)


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

        self.assertEqual(result, ProbeOk(online=7, max=20, latency_ms=12.5))
        lookup.assert_awaited_once_with("play.example.com", timeout=3.0)
        status.assert_awaited_once_with(tries=1)

    async def test_address_with_port_is_passed_through(self) -> None:
        status = mock.AsyncMock(return_value=response())
        lookup = mock.AsyncMock(return_value=fake_java(status))
        self.patch_lookup(lookup)

        await probe_module.probe(ServerConfig("X", "example.com:25599"))

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


if __name__ == "__main__":
    unittest.main()
