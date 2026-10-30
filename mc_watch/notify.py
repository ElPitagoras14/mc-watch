"""Windows notifications: who started playing and which servers went down or came back.

`notices` is pure: it compares two consecutive snapshots, so each event comes from a single
transition and is never repeated. `Notifications` keeps the last snapshot, decides whether to
show anything and hands it to the system on a loop of its own.
"""

import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from mc_watch.models import PlayersMode, ServerStatus, Snapshot, State

APP_NAME = "mc-watch"
# More notices than this from one snapshot are shown as a single one.
GROUP_ABOVE = 3

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notice:
    title: str
    body: str
    server: str  # the server's name; empty in the grouped notice
    address: str | None  # None: the grouped notice, which opens the list


def _joined(prev: ServerStatus, curr: ServerStatus) -> list[str]:
    """Names in `curr` that were not in `prev`, when both lists are complete."""
    if prev.players_mode is not PlayersMode.FULL or curr.players_mode is not PlayersMode.FULL:
        return []
    before = {name.casefold() for name in prev.players}
    return [name for name in curr.players if name.casefold() not in before]


def _notice(prev: ServerStatus, curr: ServerStatus) -> Notice | None:
    name, address = curr.server.name, curr.server.address
    was_online = prev.state is State.ONLINE
    if prev.state is State.QUERYING:
        return None
    if was_online and curr.state in (State.OFFLINE, State.ERROR):
        return Notice(f"{name} se cayó", address, name, address)
    if not was_online and curr.state is State.ONLINE:
        return Notice(f"{name} volvió a estar online", address, name, address)
    if not was_online or curr.state is not State.ONLINE:
        return None
    joined = _joined(prev, curr)
    if joined:
        verb = "entró" if len(joined) == 1 else "entraron"
        return Notice(f"{', '.join(joined)} {verb} a {name}", address, name, address)
    if prev.online == 0 and (curr.online or 0) > 0:
        return Notice(f"Alguien está jugando en {name}", address, name, address)
    return None


def notices(prev: Snapshot, curr: Snapshot) -> list[Notice]:
    """What changed from `prev` to `curr`, in the order of `curr`. Servers that are not in
    `prev` (just added) produce nothing."""
    before = {status.server.address.casefold(): status for status in prev.servers}
    found: list[Notice] = []
    for status in curr.servers:
        previous = before.get(status.server.address.casefold())
        if previous is None:
            continue
        notice = _notice(previous, status)
        if notice is not None:
            found.append(notice)
    return found


def group(found: list[Notice]) -> list[Notice]:
    if len(found) <= GROUP_ABOVE:
        return found
    names = ", ".join(notice.server for notice in found[:GROUP_ABOVE])
    return [Notice(f"{APP_NAME}: {len(found)} novedades", f"{names} y más", "", None)]


SendFn = Callable[[Notice, Callable[[], None]], Awaitable[None]]


class Notifications:
    """Poller subscriber that shows the notices of each snapshot while enabled.

    The last snapshot is kept even while disabled, so enabling shows only what happens from
    then on. Sending runs on a loop of its own: a slow system call never delays the poller.
    """

    def __init__(
        self,
        enabled: bool,
        on_click: Callable[[str | None], None],
        send: SendFn | None = None,
    ) -> None:
        self._enabled = enabled
        self._on_click = on_click
        self._send = send or _desktop_send
        self._last: Snapshot | None = None
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broken = False

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if enabled and not self._enabled:
                self._broken = False  # turning it on again gives the system another chance
            self._enabled = enabled

    def on_snapshot(self, snapshot: Snapshot) -> None:
        with self._lock:
            prev, self._last = self._last, snapshot
            if prev is None or not self._enabled or self._broken:
                return
        for notice in group(notices(prev, snapshot)):
            self._emit(notice)

    def _emit(self, notice: Notice) -> None:
        log.info("Notificación: %s — %s", notice.title, notice.body)

        def clicked() -> None:
            self._on_click(notice.address)

        future = asyncio.run_coroutine_threadsafe(self._run(notice, clicked), self._ensure_loop())
        future.add_done_callback(self._done)

    async def _run(self, notice: Notice, clicked: Callable[[], None]) -> None:
        await self._send(notice, clicked)

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name="notify", daemon=True).start()
                self._loop = loop
            return self._loop

    def _done(self, future: concurrent.futures.Future[None]) -> None:
        error = future.exception()
        if error is None:
            return
        with self._lock:
            if self._broken:
                return
            self._broken = True
        log.warning("No se pueden mostrar notificaciones: %s", error)


_notifier: object | None = None


async def _desktop_send(notice: Notice, clicked: Callable[[], None]) -> None:
    # Imported here: tests and the preview never need WinRT.
    from desktop_notifier import DesktopNotifier

    global _notifier
    if _notifier is None:
        _notifier = DesktopNotifier(app_name=APP_NAME)
    notifier: DesktopNotifier = _notifier  # pyright: ignore[reportAssignmentType]
    await notifier.send(title=notice.title, message=notice.body, on_clicked=clicked)
