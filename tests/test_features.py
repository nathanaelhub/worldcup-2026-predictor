"""
Tests for pre-match feature engineering.

The load-bearing property is **no leakage**: a fixture's features must depend
only on matches strictly before it. The rest pin down the individual feature
definitions (form, rest, host, Elo, importance) and the neutral-team defaults.
"""
import pandas as pd
import pytest

from wc2026.features import (
    DEFAULT_FORM_GD, DEFAULT_FORM_PTS, FEATURE_COLUMNS, REST_CAP_DAYS,
    build_training_frame, fixture_features,
)

COLS = ["date", "tournament", "home_team", "away_team",
        "home_score", "away_score", "neutral"]


def _m(rows):
    return pd.DataFrame([dict(zip(COLS, r)) for r in rows])


# A's three matches, chronological: two big wins, then the fixture under test.
BASE = _m([
    ("2020-01-01", "friendly", "A", "B", 3, 0, True),
    ("2020-02-01", "friendly", "A", "C", 2, 0, True),
    ("2020-03-01", "friendly", "A", "D", 1, 1, True),
])


# ---------------------------------------------------------------- leakage
def test_training_row_excludes_its_own_match():
    frame = build_training_frame(BASE)
    ad = frame[(frame.home == "A") & (frame.away == "D")].iloc[0]
    # A's form must reflect only the two earlier wins, not the 1-1 being played
    assert ad.form_home_pts == 3.0          # win, win
    assert ad.form_home_gd == 2.5           # +3, +2


def test_training_frame_never_sees_the_future():
    """Every row's Elo diff is the pre-match value: A's advantage grows monotone
    across its three matches because each prior win lifts A's rating."""
    frame = build_training_frame(BASE).sort_values("date")
    a_rows = frame[frame.home == "A"]
    diffs = a_rows.elo_diff.tolist()
    assert diffs == sorted(diffs)           # strictly non-decreasing as A wins
    assert diffs[0] == 0.0                   # first ever match: both at base


def test_fixture_features_are_strictly_before_the_date():
    # a same-day match must NOT be counted (features identical with/without it)
    before = fixture_features(BASE, "A", "D", "2020-03-01", neutral=True)
    with_same_day = fixture_features(
        pd.concat([BASE, _m([("2020-03-01", "friendly", "A", "E", 9, 0, True)])],
                  ignore_index=True),
        "A", "D", "2020-03-01", neutral=True)
    assert before["form_home_pts"] == with_same_day["form_home_pts"] == 3.0
    assert before["form_home_gd"] == with_same_day["form_home_gd"] == 2.5


# ---------------------------------------------------------------- features
def test_form_reflects_a_winning_streak():
    # as of mid-February only the two wins have happened (the 03-01 draw hasn't)
    f = fixture_features(BASE, "A", "Z", "2020-02-15")
    assert f["form_home_pts"] == 3.0        # win, win
    assert f["form_home_gd"] == 2.5
    # once the draw is in the window, form eases off
    later = fixture_features(BASE, "A", "Z", "2020-04-01")
    assert later["form_home_pts"] == pytest.approx(7 / 3)   # win, win, draw
    assert later["form_home_gd"] == pytest.approx(5 / 3)


def test_rest_days_capped_and_measured():
    f = fixture_features(BASE, "A", "Z", "2020-03-01")
    assert f["rest_home"] == 29.0           # 2020-02-01 -> 2020-03-01
    far = fixture_features(BASE, "A", "Z", "2021-01-01")
    assert far["rest_home"] == float(REST_CAP_DAYS)   # long layoff, capped


def test_host_flags():
    f = fixture_features(BASE, "United States", "Canada", "2026-06-15")
    assert f["host_home"] == 1 and f["host_away"] == 1
    g = fixture_features(BASE, "Brazil", "Mexico", "2026-06-15")
    assert g["host_home"] == 0 and g["host_away"] == 1


def test_stronger_team_has_positive_elo_diff():
    f = fixture_features(BASE, "A", "D", "2020-03-15")
    assert f["elo_diff"] > 0                 # A won twice; D has no wins
    assert 0.5 < f["elo_winprob"] <= 1.0


def test_importance_scale():
    wc = fixture_features(BASE, "A", "D", "2026-06-15", tournament="FIFA World Cup")
    fr = fixture_features(BASE, "A", "D", "2026-06-15", tournament="friendly")
    assert wc["importance"] == 4 and fr["importance"] == 1


def test_neutral_flag_passthrough():
    assert fixture_features(BASE, "A", "D", "2020-04-01", neutral=True)["neutral"] == 1
    assert fixture_features(BASE, "A", "D", "2020-04-01", neutral=False)["neutral"] == 0


def test_unknown_team_gets_neutral_priors():
    f = fixture_features(BASE, "Atlantis", "Lemuria", "2020-04-01")
    assert f["form_home_pts"] == DEFAULT_FORM_PTS
    assert f["form_home_gd"] == DEFAULT_FORM_GD
    assert f["elo_diff"] == 0.0             # both unrated -> base
    assert f["rest_home"] == float(REST_CAP_DAYS)


def test_training_frame_has_every_feature_column_and_label():
    frame = build_training_frame(BASE)
    for col in FEATURE_COLUMNS + ["label", "home_goals", "away_goals"]:
        assert col in frame.columns
    assert set(frame.label) <= {"H", "D", "A"}
    assert len(frame) == len(BASE)
