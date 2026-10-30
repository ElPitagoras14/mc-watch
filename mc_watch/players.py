"""Which player names a probe result lets the panel show, and how complete that list is."""

import re
from collections.abc import Iterable

from mc_watch.models import Edition, PlayersMode, ProbeOk, QueryOutcome, SamplePlayer

NULL_UUID = "00000000-0000-0000-0000-000000000000"
NAME_RE = re.compile(r"[A-Za-z0-9_]{3,16}")


def _valid_names(names: Iterable[str]) -> tuple[str, ...]:
    """Keep names that look like real accounts, without repeats, in their original order."""
    seen: set[str] = set()
    valid: list[str] = []
    for name in names:
        key = name.casefold()
        if key in seen or NAME_RE.fullmatch(name) is None:
            continue
        seen.add(key)
        valid.append(name)
    return tuple(valid)


def clean_sample(sample: Iterable[SamplePlayer]) -> tuple[str, ...]:
    """Drop the ping sample entries that are decoration: null UUID, `§` codes or invalid names.
    Big servers such as Hypixel use the sample to show text in the player tooltip."""
    return _valid_names(
        player.name for player in sample if player.id != NULL_UUID and "§" not in player.name
    )


def players_view(result: ProbeOk) -> tuple[PlayersMode, tuple[str, ...]]:
    """The mode and the names to show for an online server."""
    if result.edition is Edition.BEDROCK:
        return (PlayersMode.FULL if result.online == 0 else PlayersMode.HIDDEN), ()
    if result.query is QueryOutcome.OK:
        return PlayersMode.FULL, _valid_names(result.query_players)
    if result.online == 0:
        return PlayersMode.FULL, ()
    names = clean_sample(result.sample)
    if not names:
        return PlayersMode.HIDDEN, ()
    # `>=`: a stale `online` must not turn a complete list into a partial one.
    if len(names) >= result.online:
        return PlayersMode.FULL, names
    return PlayersMode.PARTIAL, names
