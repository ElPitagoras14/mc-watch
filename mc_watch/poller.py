import asyncio
import concurrent.futures
import contextlib
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from typing import Any

from mc_watch.models import (
    ProbeResult,
    ProbeUnreachable,
    ServerConfig,
    ServerStatus,
    Snapshot,
    State,
)
from mc_watch.probe import probe
from mc_watch.state import initial_status, next_status

ProbeFn = Callable[[ServerConfig], Awaitable[ProbeResult]]
Subscriber = Callable[[Snapshot], None]

STOP_JOIN_TIMEOUT_SECS = 5.0
ADD_TIMEOUT_SECS = 5.0

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
        loop = self._running_loop()
        if loop is None:
            raise RuntimeError("El poller no está en ejecución")
        done: concurrent.futures.Future[None] = concurrent.futures.Future()

        def apply() -> None:
            try:
                status = next_status(initial_status(server), result)
                self._statuses = [*self._statuses, status]
                log.info("%s (%s): agregado, %s", server.name, server.address, status.state.value)
                # No cycle ended, so the age shown in the panel must not reset.
                self._publish(Snapshot(servers=tuple(self._statuses), updated_at=self._updated_at))
                done.set_result(None)
            except BaseException as error:
                done.set_exception(error)

        loop.call_soon_threadsafe(apply)
        done.result(timeout=ADD_TIMEOUT_SECS)

    def refresh(self) -> None:
        """Ask for a cycle right now. Ignored while a cycle is running (its snapshot is about
        to be published anyway) and when the poller is not running. Safe from any thread."""
        loop = self._running_loop()
        if loop is None:
            return
        # The loop may close between the check above and the call.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._request_refresh)

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
        self._ready.set()

        while not stop_event.is_set():
            started = time.monotonic()
            self._cycling = True
            try:
                await self._cycle()
            finally:
                self._cycling = False
            remaining = self._interval_secs - (time.monotonic() - started)
            await self._wait_for_next_cycle(stop_event, refresh_event, max(remaining, 0))

    @staticmethod
    async def _wait_for_next_cycle(
        stop_event: asyncio.Event, refresh_event: asyncio.Event, timeout: float
    ) -> None:
        """Sleep until the interval elapses, a refresh is requested or the poller stops."""
        waiters = [
            asyncio.ensure_future(stop_event.wait()),
            asyncio.ensure_future(refresh_event.wait()),
        ]
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiter in waiters:
                waiter.cancel()
        refresh_event.clear()

    async def _cycle(self) -> None:
        started = time.monotonic()
        # Servers added while the probes are in flight are appended to `self._statuses` by
        # `add()`, so the cycle works on a copy and keeps whatever was appended after it.
        current = list(self._statuses)
        log.debug("Inicia el ciclo de sondeo (%d servidores)", len(current))

        results = await asyncio.gather(
            *(self._probe_fn(status.server) for status in current),
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

        self._statuses = [*updated, *self._statuses[len(current) :]]
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
