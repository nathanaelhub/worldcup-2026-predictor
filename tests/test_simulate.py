"""
Tests for the tournament Monte Carlo.

Toy four-team brackets keep them fast (a few thousand sims each) while still
covering the invariants that matter: probabilities that must sum to fixed
totals, real results that must survive every simulation, monotonic round
progression, and seeded determinism.
"""
import math

import pytest

from wc2026.dixon_coles import DixonColesModel
from wc2026.simulate import simulate_bracket

N = 4000


def _model() -> DixonColesModel:
    # Brazil strong, Panama weak, the rest average
    return DixonColesModel(
        intercept=0.1, home_adv=0.25, rho=-0.06,
        attack={"Brazil": 0.6, "France": 0.2, "Japan": 0.0, "Panama": -0.4},
        defense={"Brazil": 0.5, "France": 0.2, "Japan": 0.0, "Panama": -0.3},
        teams={"Brazil", "France", "Japan", "Panama"},
    )


def _tie(home, away, winner=None, played=False):
    return {"home": home, "away": away, "played": played,
            "home_score": None, "away_score": None, "winner": winner}


def _bracket(t1, t2):
    return {"rounds": [
        {"round": "Semi-finals", "ties": [t1, t2]},
        {"round": "Final", "ties": [_tie(None, None)]},
    ]}


def test_probabilities_have_the_right_totals():
    res = simulate_bracket(_model(), _bracket(_tie("Brazil", "Panama"),
                                              _tie("France", "Japan")),
                           n_sims=N, seed=7)
    teams = res["teams"]
    assert set(teams) == {"Brazil", "Panama", "France", "Japan"}
    # exactly one champion and two finalists per simulation (output is
    # rounded to 4 decimals, so allow that much slack per team)
    assert math.isclose(sum(t["champion"] for t in teams.values()), 1.0, abs_tol=1e-3)
    assert math.isclose(sum(t["final"] for t in teams.values()), 2.0, abs_tol=1e-3)
    # per team: winning the cup requires reaching the final
    for t in teams.values():
        assert t["champion"] <= t["final"] + 2e-4


def test_stronger_team_is_more_likely_champion():
    res = simulate_bracket(_model(), _bracket(_tie("Brazil", "Panama"),
                                              _tie("France", "Japan")),
                           n_sims=N, seed=7)
    teams = res["teams"]
    assert teams["Brazil"]["champion"] > teams["Panama"]["champion"]
    assert teams["Brazil"]["champion"] > teams["Japan"]["champion"]


def test_played_tie_keeps_its_real_winner_every_time():
    upset = _tie("Brazil", "Panama", winner="Panama", played=True)
    res = simulate_bracket(_model(), _bracket(upset, _tie("France", "Japan")),
                           n_sims=N, seed=7)
    teams = res["teams"]
    assert teams["Panama"]["final"] == 1.0     # advanced in all sims
    assert teams["Brazil"]["final"] == 0.0     # eliminated in all sims


def test_played_deep_round_overrides_sampling():
    bracket = {"rounds": [
        {"round": "Semi-finals", "ties": [
            _tie("Brazil", "Panama", winner="Brazil", played=True),
            _tie("France", "Japan", winner="Japan", played=True),
        ]},
        {"round": "Final", "ties": [
            _tie("Brazil", "Japan", winner="Japan", played=True),
        ]},
    ]}
    res = simulate_bracket(_model(), bracket, n_sims=500, seed=7)
    assert res["teams"]["Japan"]["champion"] == 1.0
    assert res["teams"]["Brazil"]["champion"] == 0.0


def test_seeded_runs_are_deterministic():
    bracket = _bracket(_tie("Brazil", "Panama"), _tie("France", "Japan"))
    a = simulate_bracket(_model(), bracket, n_sims=1500, seed=42)
    b = simulate_bracket(_model(), bracket, n_sims=1500, seed=42)
    assert a == b


def test_elo_fallback_for_unfitted_teams():
    model = DixonColesModel(intercept=0.1, teams=set())  # knows nobody
    elo = {"Atlantis": 1900, "Lemuria": 1350, "Mu": 1500, "Ys": 1500}
    res = simulate_bracket(model, _bracket(_tie("Atlantis", "Lemuria"),
                                           _tie("Mu", "Ys")),
                           n_sims=N, seed=7, elo=elo)
    teams = res["teams"]
    assert teams["Atlantis"]["champion"] > teams["Lemuria"]["champion"]
    # everyone still gets simulated (4-decimal output rounding -> small slack)
    assert math.isclose(sum(t["champion"] for t in teams.values()), 1.0, abs_tol=1e-3)


def test_sixteen_tie_bracket_uses_full_round_names():
    ties = [_tie(f"T{i}", f"T{i+1}") for i in range(0, 32, 2)]
    bracket = {"rounds": [{"round": "Round of 32", "ties": ties}]}
    model = DixonColesModel(intercept=0.1, teams=set())
    res = simulate_bracket(model, bracket, n_sims=200, seed=1)
    sample = next(iter(res["teams"].values()))
    assert list(sample) == ["r16", "qf", "sf", "final", "champion"]
