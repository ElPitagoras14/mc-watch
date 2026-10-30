import threading
import time
import unittest
from collections.abc import Callable

from mc_watch.models import PlayersMode, ServerConfig, ServerStatus, Snapshot, State
from mc_watch.notify import Notice, Notifications, group, notices

SURVIVAL = ServerConfig("Survival", "play.example.com")


def status(
    state: State,
    online: int | None = None,
    mode: PlayersMode | None = None,
    players: tuple[str, ...] = (),
    server: ServerConfig = SURVIVAL,
) -> ServerStatus:
    return ServerStatus(
        server=server, state=state, online=online, max=20, players_mode=mode, players=players
    )


def snap(*statuses: ServerStatus) -> Snapshot:
    return Snapshot(servers=statuses, updated_at=1.0)


def titles(prev: ServerStatus, curr: ServerStatus) -> list[str]:
    return [notice.title for notice in notices(snap(prev), snap(curr))]


class NoticesTest(unittest.TestCase):
    def test_someone_is_playing(self) -> None:
        self.assertEqual(
            titles(
                status(State.ONLINE, 0, PlayersMode.HIDDEN),
                status(State.ONLINE, 2, PlayersMode.HIDDEN),
            ),
            ["Alguien está jugando en Survival"],
        )

    def test_joined_replaces_someone_is_playing(self) -> None:
        self.assertEqual(
            titles(
                status(State.ONLINE, 0, PlayersMode.FULL),
                status(State.ONLINE, 1, PlayersMode.FULL, ("Ana",)),
            ),
            ["Ana entró a Survival"],
        )

    def test_joined_ignores_case(self) -> None:
        self.assertEqual(
            titles(
                status(State.ONLINE, 1, PlayersMode.FULL, ("ana",)),
                status(State.ONLINE, 2, PlayersMode.FULL, ("Ana", "Beto")),
            ),
            ["Beto entró a Survival"],
        )

    def test_partial_sample_never_joins(self) -> None:
        self.assertEqual(
            titles(
                status(State.ONLINE, 23, PlayersMode.PARTIAL, ("Ana",)),
                status(State.ONLINE, 23, PlayersMode.PARTIAL, ("Beto",)),
            ),
            [],
        )

    def test_down_and_back(self) -> None:
        online = status(State.ONLINE, 0, PlayersMode.FULL)
        self.assertEqual(titles(online, status(State.OFFLINE)), ["Survival se cayó"])
        self.assertEqual(titles(online, status(State.ERROR)), ["Survival se cayó"])
        self.assertEqual(titles(status(State.OFFLINE), online), ["Survival volvió a estar online"])

    def test_first_answer_and_new_servers_are_silent(self) -> None:
        playing = status(State.ONLINE, 3, PlayersMode.FULL, ("Ana", "Beto", "Caro"))
        self.assertEqual(titles(status(State.QUERYING), playing), [])
        self.assertEqual(notices(snap(), snap(playing)), [])

    def test_more_than_three_are_grouped(self) -> None:
        found = [Notice(f"S{n} se cayó", "", f"S{n}", f"s{n}") for n in range(4)]
        self.assertEqual(
            group(found), [Notice("mc-watch: 4 novedades", "S0, S1, S2 y más", "", None)]
        )
        self.assertEqual(group(found[:3]), found[:3])


class NotificationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sent: list[Notice] = []
        self.done = threading.Semaphore(0)
        self.failing = False

    async def send(self, notice: Notice, clicked: Callable[[], None]) -> None:
        try:
            if self.failing:
                raise OSError("bloqueadas")
            self.sent.append(notice)
        finally:
            self.done.release()

    def test_disabled_tracks_snapshots_and_enabling_shows_only_new_events(self) -> None:
        notifications = Notifications(False, lambda _: None, self.send)
        notifications.on_snapshot(snap(status(State.OFFLINE)))
        notifications.on_snapshot(snap(status(State.ONLINE, 0, PlayersMode.FULL)))
        notifications.set_enabled(True)
        notifications.on_snapshot(snap(status(State.ONLINE, 0, PlayersMode.FULL)))
        notifications.on_snapshot(snap(status(State.OFFLINE)))

        self.assertTrue(self.done.acquire(timeout=2))
        self.assertEqual([n.title for n in self.sent], ["Survival se cayó"])

    def test_a_failing_system_is_logged_once(self) -> None:
        self.failing = True
        notifications = Notifications(True, lambda _: None, self.send)
        notifications.on_snapshot(snap(status(State.OFFLINE)))
        with self.assertLogs("mc_watch.notify", "WARNING") as logs:
            notifications.on_snapshot(snap(status(State.ONLINE, 0)))
            self.assertTrue(self.done.acquire(timeout=2))
            time.sleep(0.1)  # the failure is noted in the future's callback, right after
            notifications.on_snapshot(snap(status(State.OFFLINE)))
        self.assertFalse(self.done.acquire(timeout=0.2))  # nothing else was attempted
        self.assertEqual(len([r for r in logs.records if r.levelname == "WARNING"]), 1)


if __name__ == "__main__":
    unittest.main()
