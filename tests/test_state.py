import unittest

from mc_watch.models import (
    Edition,
    MotdSegment,
    PlayersMode,
    ProbeAsleep,
    ProbeOk,
    ProbeUnreachable,
    ProbeUnresolvable,
    QueryOutcome,
    SamplePlayer,
    ServerConfig,
    ServerInfo,
    State,
)
from mc_watch.state import QUERY_RETRY_CYCLES, initial_status, next_status, wants_query

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


JAVA = ServerConfig("Survival", "play.example.com", Edition.JAVA)
INFO = ServerInfo(motd=(MotdSegment("Hola", color="#55ff55"),), version="1.21.4")
RICH = ProbeOk(
    online=2,
    max=20,
    latency_ms=45.0,
    info=INFO,
    sample=(SamplePlayer("Steve", "1"), SamplePlayer("Alex", "2")),
)
ASLEEP = ProbeAsleep()


class DetailTest(unittest.TestCase):
    def test_online_exposes_info_latency_and_players(self) -> None:
        status = next_status(initial_status(JAVA), RICH)
        self.assertEqual(status.info, INFO)
        self.assertEqual(status.latency_ms, 45.0)
        self.assertEqual(status.players_mode, PlayersMode.FULL)
        self.assertEqual(status.players, ("Steve", "Alex"))
        self.assertFalse(status.asleep)

    def test_offline_drops_the_detail(self) -> None:
        online = next_status(initial_status(JAVA), RICH)
        status = next_status(next_status(online, FAIL), FAIL)
        self.assertIsNone(status.info)
        self.assertIsNone(status.latency_ms)
        self.assertIsNone(status.players_mode)
        self.assertEqual(status.players, ())


class AsleepTest(unittest.TestCase):
    def test_online_to_asleep_is_offline_in_one_cycle(self) -> None:
        online = next_status(initial_status(JAVA), RICH)
        status = next_status(online, ASLEEP)
        self.assertEqual(status.state, State.OFFLINE)
        self.assertTrue(status.asleep)
        self.assertIsNone(status.online)
        self.assertIsNone(status.info)
        self.assertEqual(status.failures, 0)

    def test_unknown_edition_asleep_is_pinned_to_java(self) -> None:
        status = next_status(initial_status(SERVER), ASLEEP)
        self.assertEqual(status.server.edition, Edition.JAVA)
        self.assertEqual(status.state, State.OFFLINE)

    def test_one_failure_keeps_it_asleep_and_two_clear_the_flag(self) -> None:
        asleep = next_status(next_status(initial_status(JAVA), RICH), ASLEEP)
        first = next_status(asleep, FAIL)
        self.assertEqual(first.state, State.OFFLINE)
        self.assertTrue(first.asleep, "un fallo aislado no demuestra que despertó")
        second = next_status(first, FAIL)
        self.assertEqual(second.state, State.OFFLINE)
        self.assertFalse(second.asleep)


def with_query(outcome: QueryOutcome) -> ProbeOk:
    return ProbeOk(online=2, max=20, latency_ms=45.0, query=outcome)


class QueryTest(unittest.TestCase):
    def test_java_asks_for_query_until_told_otherwise(self) -> None:
        self.assertTrue(wants_query(initial_status(JAVA)))

    def test_bedrock_never_asks_for_query(self) -> None:
        bedrock = ServerConfig("B", "bedrock.example.com", Edition.BEDROCK)
        status = next_status(initial_status(bedrock), ProbeOk(1, 10, 30.0, Edition.BEDROCK))
        self.assertFalse(wants_query(status))

    def test_query_ok_marks_it_capable_and_keeps_asking(self) -> None:
        status = next_status(initial_status(JAVA), with_query(QueryOutcome.OK))
        self.assertIs(status.query_capable, True)
        self.assertTrue(wants_query(status))

    def test_query_failure_pauses_it_and_retries_on_the_tenth_online_cycle(self) -> None:
        status = next_status(initial_status(JAVA), with_query(QueryOutcome.FAILED))
        self.assertIs(status.query_capable, False)
        for cycle in range(1, QUERY_RETRY_CYCLES):
            self.assertFalse(wants_query(status), f"ciclo {cycle}")
            status = next_status(status, with_query(QueryOutcome.SKIPPED))
        self.assertTrue(wants_query(status), "el décimo ciclo online reintenta")

    def test_offline_cycles_do_not_count_towards_the_retry(self) -> None:
        status = next_status(initial_status(JAVA), with_query(QueryOutcome.FAILED))
        for _ in range(5):
            status = next_status(status, FAIL)
        self.assertEqual(status.query_wait, QUERY_RETRY_CYCLES - 1)
        self.assertFalse(wants_query(status))


if __name__ == "__main__":
    unittest.main()
