import asyncio
import threading
import time
import unittest

from mc_watch.models import (
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


async def always_ok(_: ServerConfig) -> ProbeResult:
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
        async def slow(_: ServerConfig) -> ProbeResult:
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
        async def mixed(server: ServerConfig) -> ProbeResult:
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

        async def timed(_: ServerConfig) -> ProbeResult:
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

        async def scripted(_: ServerConfig) -> ProbeResult:
            return results.pop(0) if results else ProbeUnreachable()

        poller = self.make(Poller([A], 0.03, scripted))
        collector = Collector()
        poller.subscribe(collector)
        poller.start()
        self.assertTrue(collector.wait_for(3))

        states = [snapshot.servers[0].state for snapshot in collector.snapshots[:3]]
        self.assertEqual(states, [State.ONLINE, State.ONLINE, State.OFFLINE])

    def test_probe_function_that_raises_is_treated_as_unreachable(self) -> None:
        async def broken(_: ServerConfig) -> ProbeResult:
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


if __name__ == "__main__":
    unittest.main()
