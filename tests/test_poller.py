import asyncio
import threading
import time
import unittest

from mc_watch.models import (
    Edition,
    ProbeOk,
    ProbeResult,
    ProbeUnreachable,
    ServerConfig,
    Snapshot,
    State,
)
from mc_watch.poller import Poller

A = ServerConfig("A", "a.example.com")
B = ServerConfig("B", "b.example.com")
C = ServerConfig("C", "c.example.com")
OK = ProbeOk(online=3, max=20, latency_ms=10.0)


async def always_ok(_: ServerConfig, *, query: bool = False) -> ProbeResult:
    return OK


class Collector:
    """Subscriber that lets a test wait for the Nth snapshot."""

    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []
        self._condition = threading.Condition()

    def __call__(self, snapshot: Snapshot) -> None:
        with self._condition:
            self.snapshots.append(snapshot)
            self._condition.notify_all()

    def wait_for(self, count: int, timeout: float = 5.0) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: len(self.snapshots) >= count, timeout)


class PollerTest(unittest.TestCase):
    def make(self, poller: Poller) -> Poller:
        self.addCleanup(poller.stop)
        return poller

    def test_snapshot_before_first_cycle_is_querying(self) -> None:
        poller = self.make(Poller([A, B], 0.05, always_ok))

        snapshot = poller.snapshot()

        self.assertIsNone(snapshot.updated_at)
        self.assertEqual([s.state for s in snapshot.servers], [State.QUERYING, State.QUERYING])

    def test_publishes_snapshots_every_cycle(self) -> None:
        poller = self.make(Poller([A, B], 0.05, always_ok))
        collector = Collector()
        poller.subscribe(collector)

        poller.start()

        self.assertTrue(collector.wait_for(3), "debían publicarse al menos 3 ciclos")
        last = collector.snapshots[-1]
        self.assertIsNotNone(last.updated_at)
        self.assertEqual([s.state for s in last.servers], [State.ONLINE, State.ONLINE])
        self.assertEqual(poller.snapshot(), collector.snapshots[-1])

    def test_stop_terminates_the_thread(self) -> None:
        poller = self.make(Poller([A], 0.05, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        collector.wait_for(1)
        self.assertTrue(poller.is_running)

        poller.stop()

        self.assertFalse(poller.is_running)

    def test_stop_interrupts_a_long_interval_wait(self) -> None:
        poller = self.make(Poller([A], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        collector.wait_for(1)

        started = time.monotonic()
        poller.stop()

        self.assertLess(time.monotonic() - started, 2)
        self.assertFalse(poller.is_running)

    def test_stop_without_start_is_a_noop(self) -> None:
        Poller([A], 1, always_ok).stop()

    def test_servers_are_probed_concurrently(self) -> None:
        async def slow(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            await asyncio.sleep(0.3)
            return OK

        poller = self.make(Poller([A, B, C], 3600, slow))
        collector = Collector()
        poller.subscribe(collector)

        started = time.monotonic()
        poller.start()
        self.assertTrue(collector.wait_for(1))
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.8, "tres consultas de 0.3 s en paralelo no pueden sumar 0.9 s")

    def test_slow_server_does_not_delay_the_others_results(self) -> None:
        async def mixed(server: ServerConfig, *, query: bool = False) -> ProbeResult:
            if server is B:
                return ProbeUnreachable()
            return OK

        poller = self.make(Poller([A, B], 3600, mixed))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        states = {s.server.name: s.state for s in collector.snapshots[0].servers}
        self.assertEqual(states, {"A": State.ONLINE, "B": State.QUERYING})

    def test_cycles_are_scheduled_start_to_start(self) -> None:
        starts: list[float] = []

        async def timed(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            starts.append(time.monotonic())
            await asyncio.sleep(0.1)
            return OK

        poller = self.make(Poller([A], 0.3, timed))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(3))

        gaps = [later - earlier for earlier, later in zip(starts, starts[1:], strict=False)]
        for gap in gaps[:2]:
            # Sleeping the full interval after each cycle would give ~0.4 s.
            self.assertGreater(gap, 0.25)
            self.assertLess(gap, 0.37)

    def test_state_machine_is_applied_across_cycles(self) -> None:
        results: list[ProbeResult] = [OK, ProbeUnreachable(), ProbeUnreachable()]

        async def scripted(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            return results.pop(0) if results else ProbeUnreachable()

        poller = self.make(Poller([A], 0.03, scripted))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(3))

        states = [snapshot.servers[0].state for snapshot in collector.snapshots[:3]]
        self.assertEqual(states, [State.ONLINE, State.ONLINE, State.OFFLINE])

    def test_probe_function_that_raises_is_treated_as_unreachable(self) -> None:
        async def broken(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            raise RuntimeError("bug")

        poller = self.make(Poller([A], 0.03, broken))
        collector = Collector()
        poller.subscribe(collector)

        with self.assertLogs("mc_watch.poller", level="ERROR"):
            poller.start()
            self.assertTrue(collector.wait_for(2), "el poller debe seguir vivo")

        self.assertTrue(poller.is_running)
        self.assertEqual(collector.snapshots[0].servers[0].state, State.QUERYING)

    def test_failing_subscriber_does_not_stop_the_poller(self) -> None:
        poller = self.make(Poller([A], 0.03, always_ok))

        def bad(_: Snapshot) -> None:
            raise RuntimeError("suscriptor roto")

        collector = Collector()
        poller.subscribe(bad)
        poller.subscribe(collector)

        with self.assertLogs("mc_watch.poller", level="ERROR"):
            poller.start()
            self.assertTrue(collector.wait_for(2))

        self.assertTrue(poller.is_running)

    def test_no_servers_still_publishes(self) -> None:
        poller = self.make(Poller([], 0.05, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()

        self.assertTrue(collector.wait_for(1))
        self.assertEqual(collector.snapshots[0].servers, ())
        self.assertIsNotNone(collector.snapshots[0].updated_at)


class PollerAddTest(unittest.TestCase):
    def make(self, poller: Poller) -> Poller:
        self.addCleanup(poller.stop)
        return poller

    def test_add_publishes_the_new_row_without_resetting_the_age(self) -> None:
        poller = self.make(Poller([A], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        poller.add(B, ProbeOk(online=4, max=20, latency_ms=5.0))

        self.assertTrue(collector.wait_for(2))
        added = collector.snapshots[1]
        self.assertEqual([s.server.name for s in added.servers], ["A", "B"])
        self.assertEqual(added.servers[1].state, State.ONLINE)
        self.assertEqual((added.servers[1].online, added.servers[1].max), (4, 20))
        self.assertEqual(added.updated_at, collector.snapshots[0].updated_at)
        self.assertEqual(poller.snapshot(), added)

    def test_add_pins_the_detected_edition(self) -> None:
        poller = self.make(Poller([], 3600, always_ok))
        poller.start()

        poller.add(A, ProbeOk(online=1, max=10, latency_ms=5.0, edition=Edition.BEDROCK))

        self.assertEqual(poller.snapshot().servers[0].server.edition, Edition.BEDROCK)

    def test_add_with_unreachable_result_starts_with_one_failure(self) -> None:
        poller = self.make(Poller([], 3600, always_ok))
        poller.start()

        poller.add(A, ProbeUnreachable())

        status = poller.snapshot().servers[0]
        self.assertEqual((status.state, status.failures), (State.QUERYING, 1))
        self.assertEqual(status.server.edition, Edition.UNKNOWN)

    def test_added_server_is_probed_in_the_next_cycle(self) -> None:
        probed: set[str] = set()

        async def recording(server: ServerConfig, *, query: bool = False) -> ProbeResult:
            probed.add(server.name)
            return OK

        poller = self.make(Poller([A], 0.05, recording))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        poller.add(B, OK)
        count = len(collector.snapshots)
        self.assertTrue(collector.wait_for(count + 2))

        self.assertEqual(probed, {"A", "B"})

    def test_server_added_during_a_cycle_is_not_lost(self) -> None:
        async def slow(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            await asyncio.sleep(0.3)
            return OK

        poller = self.make(Poller([A], 3600, slow))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        time.sleep(0.1)  # the first cycle is in flight

        poller.add(B, OK)
        self.assertTrue(collector.wait_for(2))

        final = collector.snapshots[-1]
        self.assertIsNotNone(final.updated_at, "el segundo snapshot cierra el ciclo")
        self.assertEqual([s.server.name for s in final.servers], ["A", "B"])
        self.assertEqual([s.state for s in final.servers], [State.ONLINE, State.ONLINE])

    def test_rename_and_remove_publish_without_moving_updated_at(self) -> None:
        poller = self.make(Poller([A, B], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        cycle = collector.snapshots[0]

        poller.rename("B.example.com", "Beta")
        poller.remove("a.example.com")

        self.assertEqual([s.server.name for s in poller.snapshot().servers], ["Beta"])
        self.assertEqual(poller.snapshot().updated_at, cycle.updated_at)

    def test_rename_and_remove_during_a_cycle_survive_its_end(self) -> None:
        async def slow(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            await asyncio.sleep(0.3)
            return OK

        poller = self.make(Poller([A, B], 3600, slow))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        time.sleep(0.1)  # the first cycle is in flight

        poller.rename("b.example.com", "Beta")
        poller.remove("a.example.com")
        self.assertTrue(collector.wait_for(3))

        final = collector.snapshots[-1]
        self.assertIsNotNone(final.updated_at, "el último snapshot cierra el ciclo")
        self.assertEqual(
            [(s.server.name, s.state) for s in final.servers], [("Beta", State.ONLINE)]
        )

    def test_change_address_keeps_the_place_and_starts_the_status_over(self) -> None:
        poller = self.make(Poller([A, B, C], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        moved = ServerConfig("B", "new.example.com:25566")

        poller.change_address("b.example.com", moved, ProbeUnreachable())

        servers = poller.snapshot().servers
        self.assertEqual(
            [s.server.address for s in servers],
            ["a.example.com", "new.example.com:25566", "c.example.com"],
        )
        self.assertEqual((servers[1].state, servers[1].failures), (State.QUERYING, 1))
        self.assertEqual(servers[1].players, ())
        self.assertEqual(poller.snapshot().updated_at, collector.snapshots[0].updated_at)

    def test_change_address_during_a_cycle_is_not_overwritten_by_it(self) -> None:
        async def slow(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            await asyncio.sleep(0.3)
            return OK

        poller = self.make(Poller([A], 3600, slow))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        time.sleep(0.1)  # the first cycle is in flight

        poller.change_address(
            "a.example.com", ServerConfig("A", "new.example.com"), ProbeUnreachable()
        )
        self.assertTrue(collector.wait_for(2))

        final = collector.snapshots[-1]
        self.assertIsNotNone(final.updated_at, "el último snapshot cierra el ciclo")
        self.assertEqual(
            [(s.server.address, s.state) for s in final.servers],
            [("new.example.com", State.QUERYING)],
        )

    def test_refresh_server_probes_only_that_server_and_keeps_updated_at(self) -> None:
        probed: list[str] = []
        answer = [OK]

        async def recording(server: ServerConfig, *, query: bool = False) -> ProbeResult:
            probed.append(server.name)
            return answer[0]

        poller = self.make(Poller([A, B], 3600, recording))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        cycle = collector.snapshots[0]
        probed.clear()
        answer[0] = ProbeOk(online=9, max=20, latency_ms=5.0)

        poller.refresh_server("B.example.com")

        self.assertEqual(probed, ["B"])
        servers = poller.snapshot().servers
        self.assertEqual([s.online for s in servers], [3, 9])
        self.assertEqual(poller.snapshot().updated_at, cycle.updated_at)

    def test_probe_asks_for_query_only_when_the_status_wants_it(self) -> None:
        asked: dict[str, bool] = {}

        async def recording(server: ServerConfig, *, query: bool = False) -> ProbeResult:
            asked[server.name] = query
            return OK

        java = ServerConfig("J", "j.example.com", Edition.JAVA)
        poller = self.make(Poller([A, java], 3600, recording))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        self.assertEqual(asked, {"A": False, "J": True})

    def test_submit_runs_a_coroutine_on_the_poller_loop(self) -> None:
        poller = self.make(Poller([], 3600, always_ok))
        poller.start()

        async def where() -> str:
            return threading.current_thread().name

        self.assertEqual(poller.submit(where()).result(timeout=2), "poller")

    def test_submit_and_add_require_a_running_poller(self) -> None:
        poller = Poller([], 3600, always_ok)

        async def noop() -> None: ...

        with self.assertRaises(RuntimeError):
            poller.submit(noop())
        with self.assertRaises(RuntimeError):
            poller.add(A, OK)


class PollerRefreshTest(unittest.TestCase):
    def make(self, poller: Poller) -> Poller:
        self.addCleanup(poller.stop)
        return poller

    def test_refresh_runs_a_cycle_right_away(self) -> None:
        poller = self.make(Poller([A], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        started = time.monotonic()
        poller.refresh()

        self.assertTrue(collector.wait_for(2, timeout=2))
        self.assertLess(time.monotonic() - started, 1)

    def test_refresh_during_a_cycle_is_ignored(self) -> None:
        async def slow(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            await asyncio.sleep(0.3)
            return OK

        poller = self.make(Poller([A], 3600, slow))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        time.sleep(0.1)  # the first cycle is in flight

        poller.refresh()
        self.assertTrue(collector.wait_for(1))
        time.sleep(0.5)

        self.assertEqual(len(collector.snapshots), 1)

    def test_next_periodic_cycle_counts_from_the_manual_one(self) -> None:
        starts: list[float] = []

        async def timed(_: ServerConfig, *, query: bool = False) -> ProbeResult:
            starts.append(time.monotonic())
            return OK

        poller = self.make(Poller([A], 0.5, timed))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        time.sleep(0.2)
        poller.refresh()
        self.assertTrue(collector.wait_for(3, timeout=3))

        manual_to_next = starts[2] - starts[1]
        # Counting from the first cycle it would be ~0.3 s.
        self.assertGreater(manual_to_next, 0.45)

    def test_shorter_interval_cycles_right_away_when_already_due(self) -> None:
        poller = self.make(Poller([A], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))
        time.sleep(0.3)

        started = time.monotonic()
        poller.set_interval(0.2)

        self.assertTrue(collector.wait_for(2, timeout=2))
        self.assertLess(time.monotonic() - started, 0.15)

    def test_longer_interval_does_not_cycle_early(self) -> None:
        poller = self.make(Poller([A], 0.4, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        poller.set_interval(3600)
        time.sleep(0.8)

        self.assertEqual(len(collector.snapshots), 1)

    def test_refresh_without_a_running_poller_is_a_noop(self) -> None:
        Poller([A], 1, always_ok).refresh()

    def test_stop_still_interrupts_the_wait(self) -> None:
        poller = self.make(Poller([A], 3600, always_ok))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(1))

        started = time.monotonic()
        poller.stop()

        self.assertLess(time.monotonic() - started, 2)
        self.assertFalse(poller.is_running)


if __name__ == "__main__":
    unittest.main()
