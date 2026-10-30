import asyncio
import concurrent.futures
import contextlib
import logging
import threading
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import replace
from typing import Any, Protocol

from mc_watch.models import (
    ProbeResult,
    ProbeUnreachable,
    ServerConfig,
    ServerStatus,
    Snapshot,
    State,
)
from mc_watch.probe import probe
from mc_watch.state import initial_status, next_status, wants_query


def _keys(statuses: Sequence[ServerStatus]) -> list[tuple[str, int]]:
    """Identify each tracked server by its address and, when a hand-written config repeats one,
    by its position among the entries that share it."""
    seen: Counter[str] = Counter()
    keys: list[tuple[str, int]] = []
    for status in statuses:
        address = status.server.address.casefold()
        keys.append((address, seen[address]))
        seen[address] += 1
    return keys


class ProbeFn(Protocol):
    def __call__(
        self, server: ServerConfig, /, *, query: bool = False
    ) -> Awaitable[ProbeResult]: ...


Subscriber = Callable[[Snapshot], None]

STOP_JOIN_TIMEOUT_SECS = 5.0
ADD_TIMEOUT_SECS = 5.0
REFRESH_ONE_TIMEOUT_SECS = 10.0

log = logging.getLogger(__name__)


class Poller:
    """Probes every server each cycle on its own thread and publishes snapshots.

    Cycles are scheduled start to start: with a 60 s interval a new cycle begins 60 s
    after the previous one began, however long the previous one took.
    """

    def __init__(
        self,
        servers: Sequence[ServerConfig],
        interval_secs: float,
        probe_fn: ProbeFn = probe,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._interval_secs = interval_secs
        self._probe_fn = probe_fn
        self._clock = clock
        self._statuses = [initial_status(server) for server in servers]
        self._updated_at: float | None = None
        self._lock = threading.Lock()
        self._snapshot = Snapshot(servers=tuple(self._statuses), updated_at=None)
        self._subscribers: list[Subscriber] = []
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._refresh_event: asyncio.Event | None = None
        self._reschedule_event: asyncio.Event | None = None
        self._cycling = False
        self._ready = threading.Event()

    def snapshot(self) -> Snapshot:
        with self._lock:
            return self._snapshot

    def subscribe(self, callback: Subscriber) -> None:
        """`callback` runs on the poller thread after every cycle."""
        with self._lock:
            self._subscribers.append(callback)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def submit[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Run `coro` on the poller's loop. Safe to call from any thread."""
        loop = self._running_loop()
        if loop is None:
            coro.close()
            raise RuntimeError("El poller no está en ejecución")
        return asyncio.run_coroutine_threadsafe(coro, loop)

    def add(self, server: ServerConfig, result: ProbeResult) -> None:
        """Start tracking `server`, seeded with a probe `result` already obtained, and publish
        a snapshot right away. Returns once the snapshot is out. Safe to call from any thread."""

        def apply() -> None:
            status = next_status(initial_status(server), result)
            self._statuses = [*self._statuses, status]
            log.info("%s (%s): agregado, %s", server.name, server.address, status.state.value)
            self._publish_membership()

        self._on_loop(apply)

    def rename(self, address: str, name: str) -> None:
        """Change the displayed name of the server with that address (the first one, ignoring
        case) and publish a snapshot right away. Safe to call from any thread."""

        def apply() -> None:
            index = self._index_of(address)
            if index is None:
                return
            status = self._statuses[index]
            server = replace(status.server, name=name)
            self._statuses[index] = replace(status, server=server)
            log.info("%s: renombrado a %r", address, name)
            self._publish_membership()

        self._on_loop(apply)

    def remove(self, address: str) -> None:
        """Stop tracking the server with that address (the first one, ignoring case) and publish
        a snapshot right away. A probe of it that is still in flight is discarded. Safe to call
        from any thread."""

        def apply() -> None:
            index = self._index_of(address)
            if index is None:
                return
            status = self._statuses.pop(index)
            log.info("%s (%s): eliminado", status.server.name, address)
            self._publish_membership()

        self._on_loop(apply)

    def _on_loop(self, action: Callable[[], None]) -> None:
        """Run `action` on the poller's loop, so it never interleaves with the merge that ends a
        cycle, and wait for it."""
        loop = self._running_loop()
        if loop is None:
            raise RuntimeError("El poller no está en ejecución")
        done: concurrent.futures.Future[None] = concurrent.futures.Future()

        def run() -> None:
            try:
                action()
                done.set_result(None)
            except BaseException as error:
                done.set_exception(error)

        loop.call_soon_threadsafe(run)
        done.result(timeout=ADD_TIMEOUT_SECS)

    def _index_of(self, address: str) -> int | None:
        key = address.casefold()
        for index, status in enumerate(self._statuses):
            if status.server.address.casefold() == key:
                return index
        return None

    def _publish_membership(self) -> None:
        # No cycle ended, so the age shown in the panel must not reset.
        self._publish(Snapshot(servers=tuple(self._statuses), updated_at=self._updated_at))

    def refresh(self) -> None:
        """Ask for a cycle right now. Ignored while a cycle is running (its snapshot is about
        to be published anyway) and when the poller is not running. Safe from any thread."""
        loop = self._running_loop()
        if loop is None:
            return
        # The loop may close between the check above and the call.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._request_refresh)

    def refresh_server(self, address: str) -> None:
        """Probe only the server with that address now and publish the result. Returns when it
        is done (a probe takes a few seconds at most). Raises `RuntimeError` when the poller is
        not running. Safe to call from any thread."""
        self.submit(self._refresh_one(address)).result(timeout=REFRESH_ONE_TIMEOUT_SECS)

    async def _refresh_one(self, address: str) -> None:
        index = self._index_of(address)
        if index is None:
            return
        status = self._statuses[index]
        try:
            result = await self._probe_fn(status.server, query=wants_query(status))
        except Exception:
            log.error("La función de sondeo falló para %s", address, exc_info=True)
            result = ProbeUnreachable()
        # The server may have been renamed or removed while the probe was in flight.
        index = self._index_of(address)
        if index is None:
            return
        self._statuses[index] = next_status(self._statuses[index], result)
        # No cycle ended, so the age shown in the panel must not reset.
        self._publish_membership()

    def _request_refresh(self) -> None:
        if self._cycling or self._refresh_event is None:
            return
        log.debug("Ciclo a demanda")
        self._refresh_event.set()

    def _running_loop(self) -> asyncio.AbstractEventLoop | None:
        loop = self._loop
        if not self.is_running or loop is None or loop.is_closed():
            return None
        return loop

    def start(self) -> None:
        if self.is_running:
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="poller", daemon=True)
        self._thread.start()
        self._ready.wait()

    def stop(self) -> None:
        thread = self._thread
        if thread is None:
            return
        loop, stop_event = self._loop, self._stop_event
        if loop is not None and stop_event is not None and not loop.is_closed():
            # The loop may close between the check above and the call.
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(stop_event.set)
        thread.join(timeout=STOP_JOIN_TIMEOUT_SECS)
        if thread.is_alive():
            log.warning("El hilo del poller no terminó en %.0f s", STOP_JOIN_TIMEOUT_SECS)

    def _run(self) -> None:
        try:
            asyncio.run(self._main())
        except Exception:
            log.exception("El poller terminó por un error inesperado")

    async def _main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_event = stop_event = asyncio.Event()
        self._refresh_event = refresh_event = asyncio.Event()
        self._reschedule_event = reschedule_event = asyncio.Event()
        self._ready.set()

        while not stop_event.is_set():
            started = time.monotonic()
            self._cycling = True
            try:
                await self._cycle()
            finally:
                self._cycling = False
            # A new interval wakes the wait up to count it again from this cycle's start.
            while not stop_event.is_set():
                remaining = self._interval_secs - (time.monotonic() - started)
                woken_by = await self._wait_for_next_cycle(
                    [stop_event, refresh_event, reschedule_event], max(remaining, 0)
                )
                if woken_by is not reschedule_event:
                    break

    @staticmethod
    async def _wait_for_next_cycle(
        events: list[asyncio.Event], timeout: float
    ) -> asyncio.Event | None:
        """Sleep until `timeout` elapses or one of `events` is set. Returns that event, cleared
        (None on timeout)."""
        waiters = {asyncio.ensure_future(event.wait()): event for event in events}
        try:
            done, _ = await asyncio.wait(
                waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for waiter in waiters:
                waiter.cancel()
        woken_by = next((waiters[waiter] for waiter in done), None)
        for event in events[1:]:  # the stop event stays set
            event.clear()
        return woken_by

    def set_interval(self, interval_secs: float) -> None:
        """Change the interval. The next cycle is scheduled again from the start of the last
        one. Safe to call from any thread, also when the poller is not running."""
        self._interval_secs = interval_secs
        loop, event = self._running_loop(), self._reschedule_event
        if loop is None or event is None:
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(event.set)

    async def _cycle(self) -> None:
        started = time.monotonic()
        current = list(self._statuses)
        log.debug("Inicia el ciclo de sondeo (%d servidores)", len(current))

        results = await asyncio.gather(
            *(self._probe_fn(status.server, query=wants_query(status)) for status in current),
            return_exceptions=True,
        )

        updated: list[ServerStatus] = []
        for prev, result in zip(current, results, strict=True):
            if isinstance(result, BaseException):
                if not isinstance(result, Exception):
                    raise result  # cancellation and the like must propagate
                log.error(
                    "La función de sondeo falló para %s", prev.server.address, exc_info=result
                )
                result = ProbeUnreachable()
            status = next_status(prev, result)
            if status.state is not prev.state:
                log.info(
                    "%s (%s): %s -> %s",
                    prev.server.name,
                    prev.server.address,
                    prev.state.value,
                    status.state.value,
                )
            updated.append(status)

        # `add`, `rename` and `remove` ran on this loop while the probes were in flight, so the
        # live list decides who is tracked and how it is named; the cycle only brings the state.
        results_by_key = dict(zip(_keys(current), updated, strict=True))
        merged: list[ServerStatus] = []
        for key, live in zip(_keys(self._statuses), self._statuses, strict=True):
            fresh = results_by_key.get(key)
            if fresh is None:
                merged.append(live)
            else:
                merged.append(replace(fresh, server=replace(fresh.server, name=live.server.name)))
        self._statuses = merged
        self._updated_at = self._clock()
        snapshot = Snapshot(servers=tuple(self._statuses), updated_at=self._updated_at)

        online = sum(1 for status in snapshot.servers if status.state is State.ONLINE)
        log.info(
            "Ciclo terminado en %.2f s: %d/%d online",
            time.monotonic() - started,
            online,
            len(snapshot.servers),
        )
        self._publish(snapshot)

    def _publish(self, snapshot: Snapshot) -> None:
        with self._lock:
            self._snapshot = snapshot
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(snapshot)
            except Exception:
                log.exception("Un suscriptor del poller falló")
