import asyncio
import contextlib
import logging
import threading
import time
from collections.abc import Awaitable, Callable, Sequence

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
        self._lock = threading.Lock()
        self._snapshot = Snapshot(servers=tuple(self._statuses), updated_at=None)
        self._subscribers: list[Subscriber] = []
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
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
        self._stop_event = asyncio.Event()
        self._ready.set()

        while not self._stop_event.is_set():
            started = time.monotonic()
            await self._cycle()
            remaining = self._interval_secs - (time.monotonic() - started)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=max(remaining, 0))
            except TimeoutError:
                continue

    async def _cycle(self) -> None:
        started = time.monotonic()
        log.debug("Inicia el ciclo de sondeo (%d servidores)", len(self._statuses))

        results = await asyncio.gather(
            *(self._probe_fn(status.server) for status in self._statuses),
            return_exceptions=True,
        )

        updated: list[ServerStatus] = []
        for prev, result in zip(self._statuses, results, strict=True):
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

        self._statuses = updated
        snapshot = Snapshot(servers=tuple(updated), updated_at=self._clock())
        with self._lock:
            self._snapshot = snapshot
            subscribers = list(self._subscribers)

        online = sum(1 for status in updated if status.state is State.ONLINE)
        log.info(
            "Ciclo terminado en %.2f s: %d/%d online",
            time.monotonic() - started,
            online,
            len(updated),
        )
        for callback in subscribers:
            try:
                callback(snapshot)
            except Exception:
                log.exception("Un suscriptor del poller falló")
