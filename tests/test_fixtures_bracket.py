"""
Regression tests for the knockout bracket structure.

The R32 draw order was once off by one slot (South Africa–Canada filed last
instead of third), which silently corrupted every derived Round-of-16 pairing
after the first. These tests pin the cascade to the real, played R16 ties so a
bad draw file can't ship quietly again.
"""
import pandas as pd
import pytest

from wc2026.fixtures import knockout_bracket, _merge_overrides


def _matches(rows):
    return pd.DataFrame(rows, columns=[
        "date", "tournament", "home_team", "away_team",
        "home_score", "away_score", "neutral", "shootout_winner"])


# the one knockout result the upstream dataset already has; the other 18
# come from the overrides file, so this exercises the merge for real
UPSTREAM = _matches([
    ("2026-06-28", "FIFA World Cup", "South Africa", "Canada", 0, 1, True, None)])


def test_r16_pairings_match_the_real_bracket():
    """Winners of consecutive R32 ties must meet exactly as they really did."""
    bracket = knockout_bracket(UPSTREAM)
    r16 = bracket["rounds"][1]["ties"]
    pairings = {frozenset((t["home"], t["away"])) for t in r16}
    for real in [("Paraguay", "France"), ("Canada", "Morocco"),
                 ("Portugal", "Spain"), ("United States", "Belgium"),
                 ("Brazil", "Norway"), ("Mexico", "England"),
                 ("Argentina", "Egypt"), ("Switzerland", "Colombia")]:
        assert frozenset(real) in pairings, f"missing real R16 tie {real}"


def test_played_r16_results_cascade_to_quarter_finals():
    bracket = knockout_bracket(UPSTREAM)
    qf = bracket["rounds"][2]["ties"]
    qf_teams = {t for tie in qf for t in (tie["home"], tie["away"]) if t}
    # France–Morocco and Norway–England are the two decided quarter-finals
    assert {"France", "Morocco", "Norway", "England"} <= qf_teams
    # Brazil lost its R16 — it must appear nowhere past that round
    assert "Brazil" not in qf_teams


def test_dataset_beats_override_for_the_same_fixture():
    results = {frozenset(("Brazil", "Norway")): {"Brazil": 9, "Norway": 0, "so": None}}
    _merge_overrides(results)
    # the pre-existing (dataset) entry must survive untouched
    assert results[frozenset(("Brazil", "Norway"))]["Brazil"] == 9
    # and fixtures absent from the dataset are filled from the override file
    assert results[frozenset(("Canada", "Morocco"))]["Morocco"] == 3
