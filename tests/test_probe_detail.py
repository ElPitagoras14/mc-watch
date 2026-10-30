"""What `probe` reads besides the player count: sleeping servers, MOTD, icon and Query."""

import asyncio
import time
import unittest
from types import SimpleNamespace
from typing import Any
from unittest import mock

from mcstatus.motd import Motd

from mc_watch import probe as probe_module
from mc_watch.models import (
    Edition,
    MotdSegment,
    ProbeAsleep,
    ProbeOk,
    ProbeUnreachable,
    QueryOutcome,
    SamplePlayer,
)
from tests.test_probe import SERVER, UNKNOWN, fake_java, hang, response

PNG = "data:image/png;base64,iVBORw0KGgo="


def patch_java(test: unittest.TestCase, status: Any, query: Any = None) -> None:
    java = fake_java(status)
    if query is not None:
        java.async_query = query
    patcher = mock.patch.object(
        probe_module.JavaServer, "async_lookup", mock.AsyncMock(return_value=java)
    )
    patcher.start()
    test.addCleanup(patcher.stop)


class AsleepTest(unittest.IsolatedAsyncioTestCase):
    async def test_aternos_offline_response_is_asleep(self) -> None:
        # What mecotronicos.aternos.me answered while it was switched off.
        asleep = response(
            0, 20, protocol=-1, version="§c● Offline", motd="§cThis server is offline."
        )
        patch_java(self, mock.AsyncMock(return_value=asleep))
        self.assertEqual(await probe_module.probe(SERVER), ProbeAsleep())

    async def test_protocol_minus_one_without_keyword_is_online(self) -> None:
        patch_java(
            self,
            mock.AsyncMock(return_value=response(2, 20, protocol=-1, version="Mantenimiento")),
        )
        self.assertIsInstance(await probe_module.probe(SERVER), ProbeOk)

    async def test_unknown_edition_asleep_does_not_wait_for_bedrock(self) -> None:
        asleep = response(0, 20, protocol=-1, version="§c● Offline")
        patch_java(self, mock.AsyncMock(return_value=asleep))
        bedrock_server = mock.MagicMock()
        bedrock_server.async_status = hang
        started = time.monotonic()
        with mock.patch.object(
            probe_module.BedrockServer, "lookup", mock.MagicMock(return_value=bedrock_server)
        ):
            result = await probe_module.probe(UNKNOWN)
        self.assertEqual(result, ProbeAsleep(Edition.JAVA))
        self.assertLess(time.monotonic() - started, 1)


class MotdTest(unittest.TestCase):
    def segments(self, raw: Any, *, bedrock: bool = False) -> tuple[MotdSegment, ...]:
        motd = Motd.parse(raw, bedrock=bedrock)
        return probe_module._motd_segments(motd)  # pyright: ignore[reportPrivateUsage]

    def test_color_and_bold(self) -> None:
        self.assertEqual(
            self.segments("§aHola §lmundo"),
            (MotdSegment("Hola ", "#55ff55"), MotdSegment("mundo", "#55ff55", bold=True)),
        )

    def test_reset_clears_color_and_styles(self) -> None:
        self.assertEqual(
            self.segments("§c§lA§rB"),
            (MotdSegment("A", "#ff5555", bold=True), MotdSegment("B")),
        )

    def test_color_does_not_clear_styles(self) -> None:
        self.assertEqual(
            self.segments("§lA§bB"),
            (MotdSegment("A", None, bold=True), MotdSegment("B", "#55ffff", bold=True)),
        )

    def test_json_motd_with_extra_and_web_color(self) -> None:
        raw = {
            "text": "a",
            "color": "red",
            "extra": [{"text": "b", "bold": True, "color": "#ff8800"}, "c"],
        }
        self.assertEqual(
            self.segments(raw),
            (
                MotdSegment("a", "#ff5555"),
                MotdSegment("b", "#ff8800", bold=True),
                MotdSegment("c"),
            ),
        )

    def test_all_four_styles(self) -> None:
        self.assertEqual(
            self.segments("§l§o§n§mX"), (MotdSegment("X", None, True, True, True, True),)
        )

    def test_markup_stays_literal_text(self) -> None:
        markup = "<img src=x onerror=alert(1)>"
        self.assertEqual(self.segments(markup), (MotdSegment(markup),))


class InfoTest(unittest.IsolatedAsyncioTestCase):
    async def probe_with(self, **kwargs: Any) -> ProbeOk:
        patch_java(self, mock.AsyncMock(return_value=response(**kwargs)))
        result = await probe_module.probe(SERVER)
        assert isinstance(result, ProbeOk)
        return result

    async def test_png_icon_is_kept(self) -> None:
        self.assertEqual((await self.probe_with(icon=PNG)).info.icon, PNG)

    async def test_icon_in_another_format_is_dropped(self) -> None:
        result = await self.probe_with(icon="data:image/svg+xml;base64,PHN2Zz4=")
        self.assertIsNone(result.info.icon)

    async def test_version_loses_its_formatting_codes(self) -> None:
        self.assertEqual(
            (await self.probe_with(version="§aPaper 1.21.4")).info.version, "Paper 1.21.4"
        )

    async def test_sample_is_mapped(self) -> None:
        sample = [SimpleNamespace(name="Steve", id="uuid-1")]
        self.assertEqual(
            (await self.probe_with(sample=sample)).sample, (SamplePlayer("Steve", "uuid-1"),)
        )


class QueryTest(unittest.IsolatedAsyncioTestCase):
    async def test_query_ok_returns_the_names(self) -> None:
        query = mock.AsyncMock(
            return_value=SimpleNamespace(players=SimpleNamespace(list=["Steve", "Alex"]))
        )
        patch_java(self, mock.AsyncMock(return_value=response(2, 20)), query)

        result = await probe_module.probe(SERVER, query=True)

        assert isinstance(result, ProbeOk)
        self.assertEqual(result.query, QueryOutcome.OK)
        self.assertEqual(result.query_players, ("Steve", "Alex"))
        query.assert_awaited_once_with(tries=1)

    async def test_mute_query_does_not_cost_the_ping_result(self) -> None:
        patch_java(self, mock.AsyncMock(return_value=response(2, 20)), hang)
        started = time.monotonic()
        with mock.patch.object(probe_module, "PROBE_TIMEOUT_SECS", 0.3):
            result = await probe_module.probe(SERVER, query=True)
        assert isinstance(result, ProbeOk)
        self.assertEqual(result.query, QueryOutcome.FAILED)
        self.assertLess(time.monotonic() - started, 0.5)

    async def test_failed_status_cancels_query(self) -> None:
        cancelled = asyncio.Event()

        async def query(**_: Any) -> None:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        patch_java(self, mock.AsyncMock(side_effect=ConnectionRefusedError()), query)
        self.assertEqual(await probe_module.probe(SERVER, query=True), ProbeUnreachable())
        self.assertTrue(cancelled.is_set())

    async def test_status_and_query_run_together(self) -> None:
        async def slow_status(**_: Any) -> SimpleNamespace:
            await asyncio.sleep(0.2)
            return response(2, 20)

        async def slow_query(**_: Any) -> SimpleNamespace:
            await asyncio.sleep(0.2)
            return SimpleNamespace(players=SimpleNamespace(list=["Steve"]))

        patch_java(self, slow_status, slow_query)
        started = time.monotonic()
        result = await probe_module.probe(SERVER, query=True)
        assert isinstance(result, ProbeOk)
        self.assertEqual(result.query, QueryOutcome.OK)
        self.assertLess(time.monotonic() - started, 0.35, "no deben correr uno tras otro")


if __name__ == "__main__":
    unittest.main()
