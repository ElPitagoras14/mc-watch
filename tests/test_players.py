import unittest

from mc_watch.models import Edition, PlayersMode, ProbeOk, QueryOutcome, SamplePlayer
from mc_watch.players import NULL_UUID, clean_sample, players_view


def player(name: str, uuid: str = "11111111-1111-1111-1111-111111111111") -> SamplePlayer:
    return SamplePlayer(name=name, id=uuid)


def ok(
    online: int,
    *,
    edition: Edition = Edition.JAVA,
    sample: tuple[SamplePlayer, ...] = (),
    query: QueryOutcome = QueryOutcome.SKIPPED,
    query_players: tuple[str, ...] = (),
) -> ProbeOk:
    return ProbeOk(
        online=online,
        max=100,
        latency_ms=10.0,
        edition=edition,
        sample=sample,
        query=query,
        query_players=query_players,
    )


class CleanSampleTest(unittest.TestCase):
    def test_drops_null_uuid(self) -> None:
        self.assertEqual(clean_sample([player("Steve", NULL_UUID), player("Alex")]), ("Alex",))

    def test_drops_names_outside_the_length_range(self) -> None:
        sample = [player("ab"), player("abc"), player("a" * 16), player("a" * 17)]
        self.assertEqual(clean_sample(sample), ("abc", "a" * 16))

    def test_drops_repeats_ignoring_case(self) -> None:
        self.assertEqual(
            clean_sample([player("Steve"), player("STEVE"), player("Alex")]), ("Steve", "Alex")
        )


class PlayersViewTest(unittest.TestCase):
    def test_query_ok_is_full(self) -> None:
        result = ok(2, query=QueryOutcome.OK, query_players=("Steve", "Alex"))
        self.assertEqual(players_view(result), (PlayersMode.FULL, ("Steve", "Alex")))

    def test_sample_equal_to_online_is_full(self) -> None:
        result = ok(2, sample=(player("Steve"), player("Alex")))
        self.assertEqual(players_view(result), (PlayersMode.FULL, ("Steve", "Alex")))

    def test_sample_smaller_than_online_is_partial(self) -> None:
        result = ok(23, sample=(player("Steve"), player("Alex")))
        self.assertEqual(players_view(result), (PlayersMode.PARTIAL, ("Steve", "Alex")))

    def test_decorative_sample_is_hidden(self) -> None:
        result = ok(40000, sample=(player("§7Tienda", NULL_UUID), player("§bWeb")))
        self.assertEqual(players_view(result), (PlayersMode.HIDDEN, ()))

    def test_empty_server_is_full_without_names(self) -> None:
        self.assertEqual(players_view(ok(0)), (PlayersMode.FULL, ()))

    def test_bedrock_with_players_is_hidden(self) -> None:
        self.assertEqual(players_view(ok(4, edition=Edition.BEDROCK)), (PlayersMode.HIDDEN, ()))


if __name__ == "__main__":
    unittest.main()
