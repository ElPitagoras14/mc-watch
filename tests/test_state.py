import unittest

from mc_watch.models import (
    Edition,
    ProbeOk,
    ProbeUnreachable,
    ProbeUnresolvable,
    ServerConfig,
    State,
)
from mc_watch.state import initial_status, next_status

SERVER = ServerConfig(name="Survival", address="play.example.com")
OK = ProbeOk(online=3, max=20, latency_ms=42.0)
FAIL = ProbeUnreachable()
DNS = ProbeUnresolvable()


class NextStatusTest(unittest.TestCase):
    def test_starts_querying(self) -> None:
        status = initial_status(SERVER)
        self.assertEqual(status.state, State.QUERYING)
        self.assertIsNone(status.online)

    def test_first_success_is_online_with_player_count(self) -> None:
        status = next_status(initial_status(SERVER), OK)
        self.assertEqual(status.state, State.ONLINE)
        self.assertEqual((status.online, status.max), (3, 20))

    def test_isolated_failure_keeps_online(self) -> None:
        online = next_status(initial_status(SERVER), OK)
        status = next_status(online, FAIL)
        self.assertEqual(status.state, State.ONLINE)
        self.assertEqual((status.online, status.max), (3, 20))

    def test_two_consecutive_failures_go_offline(self) -> None:
        online = next_status(initial_status(SERVER), OK)
        status = next_status(next_status(online, FAIL), FAIL)
        self.assertEqual(status.state, State.OFFLINE)

    def test_offline_exposes_no_player_count(self) -> None:
        online = next_status(initial_status(SERVER), OK)
        status = next_status(next_status(online, FAIL), FAIL)
        self.assertIsNone(status.online)
        self.assertIsNone(status.max)

    def test_first_failure_after_start_stays_querying(self) -> None:
        status = next_status(initial_status(SERVER), FAIL)
        self.assertEqual(status.state, State.QUERYING)

    def test_second_failure_after_start_goes_offline(self) -> None:
        status = next_status(next_status(initial_status(SERVER), FAIL), FAIL)
        self.assertEqual(status.state, State.OFFLINE)

    def test_success_resets_the_failure_streak(self) -> None:
        online = next_status(initial_status(SERVER), OK)
        after_one_failure = next_status(online, FAIL)
        recovered = next_status(after_one_failure, OK)
        status = next_status(recovered, FAIL)
        self.assertEqual(status.state, State.ONLINE, "un fallo tras recuperarse no basta")

    def test_offline_recovers_in_the_same_cycle(self) -> None:
        offline = next_status(next_status(initial_status(SERVER), FAIL), FAIL)
        status = next_status(offline, OK)
        self.assertEqual(status.state, State.ONLINE)
        self.assertEqual(status.failures, 0)

    def test_offline_stays_offline_on_more_failures(self) -> None:
        offline = next_status(next_status(initial_status(SERVER), FAIL), FAIL)
        status = next_status(next_status(offline, FAIL), FAIL)
        self.assertEqual(status.state, State.OFFLINE)

    def test_unresolvable_host_is_error_without_second_failure(self) -> None:
        status = next_status(initial_status(SERVER), DNS)
        self.assertEqual(status.state, State.ERROR)

    def test_unresolvable_from_online_is_error_and_drops_count(self) -> None:
        online = next_status(initial_status(SERVER), OK)
        status = next_status(online, DNS)
        self.assertEqual(status.state, State.ERROR)
        self.assertIsNone(status.online)

    def test_error_recovers_to_online(self) -> None:
        error = next_status(initial_status(SERVER), DNS)
        self.assertEqual(next_status(error, OK).state, State.ONLINE)

    def test_dns_error_does_not_count_towards_offline(self) -> None:
        error = next_status(initial_status(SERVER), DNS)
        first_failure = next_status(error, FAIL)
        self.assertEqual(first_failure.state, State.ERROR)
        self.assertEqual(next_status(first_failure, FAIL).state, State.OFFLINE)

    def test_server_is_preserved(self) -> None:
        server = next_status(initial_status(SERVER), OK).server
        self.assertEqual((server.name, server.address), (SERVER.name, SERVER.address))

    def test_unknown_edition_is_pinned_to_java(self) -> None:
        status = next_status(initial_status(SERVER), OK)
        self.assertEqual(status.server.edition, Edition.JAVA)

    def test_unknown_edition_is_pinned_to_bedrock(self) -> None:
        bedrock = ProbeOk(online=1, max=10, latency_ms=30.0, edition=Edition.BEDROCK)
        status = next_status(initial_status(SERVER), bedrock)
        self.assertEqual(status.server.edition, Edition.BEDROCK)
        self.assertEqual(status.server.address, SERVER.address)

    def test_failure_does_not_touch_the_edition(self) -> None:
        self.assertEqual(next_status(initial_status(SERVER), FAIL).server.edition, Edition.UNKNOWN)
        self.assertEqual(next_status(initial_status(SERVER), DNS).server.edition, Edition.UNKNOWN)

    def test_known_edition_never_changes(self) -> None:
        java = ServerConfig("Survival", "play.example.com", Edition.JAVA)
        bedrock = ProbeOk(online=1, max=10, latency_ms=30.0, edition=Edition.BEDROCK)
        status = next_status(initial_status(java), bedrock)
        self.assertEqual(status.server.edition, Edition.JAVA)


if __name__ == "__main__":
    unittest.main()
