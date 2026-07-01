"""
Unit tests for the Dixon-Coles model core.

These pin down the math the whole dashboard rests on: the score matrix is a
proper probability distribution, the low-score correction does what the paper
says, every derived market is consistent with the matrix, and a model survives
a save/load round-trip unchanged. No fitting here — fitting needs the full
dataset and is exercised by scripts/train.py.
"""
import math

import numpy as np
import pytest

from wc2026.dixon_coles import (
    MAX_GOALS,
    DixonColesModel,
    _dc_tau,
    forecast,
    score_matrix,
)


# ------------------------------------------------------------- score matrix
def test_score_matrix_is_a_distribution():
    m = score_matrix(1.4, 1.1, rho=-0.08)
    assert m.shape == (MAX_GOALS + 1, MAX_GOALS + 1)
    assert np.all(m >= 0)
    assert math.isclose(m.sum(), 1.0, abs_tol=1e-12)


def test_rho_zero_reduces_to_independent_poisson():
    """With rho = 0 every tau is 1, so the matrix is the plain product model."""
    from scipy.stats import poisson

    lh, la = 1.7, 0.9
    m = score_matrix(lh, la, rho=0.0)
    h = poisson.pmf(np.arange(MAX_GOALS + 1), lh)
    a = poisson.pmf(np.arange(MAX_GOALS + 1), la)
    expected = np.outer(h, a)
    expected /= expected.sum()
    assert np.allclose(m, expected)


def test_negative_rho_boosts_low_draws():
    """Dixon-Coles' point: real football has more 0-0/1-1 than independent
    Poisson predicts. Negative rho must raise those cells."""
    plain = score_matrix(1.3, 1.2, rho=0.0)
    corrected = score_matrix(1.3, 1.2, rho=-0.1)
    assert corrected[0, 0] > plain[0, 0]
    assert corrected[1, 1] > plain[1, 1]
    # and pull mass out of the adjacent 1-0 / 0-1 cells
    assert corrected[1, 0] < plain[1, 0]
    assert corrected[0, 1] < plain[0, 1]


def test_tau_only_touches_the_four_low_score_cells():
    assert _dc_tau(2, 0, 1.5, 1.0, -0.1) == 1.0
    assert _dc_tau(0, 2, 1.5, 1.0, -0.1) == 1.0
    assert _dc_tau(3, 3, 1.5, 1.0, -0.1) == 1.0


def test_swapping_teams_transposes_the_matrix():
    m_ab = score_matrix(1.6, 1.0, rho=-0.07)
    m_ba = score_matrix(1.0, 1.6, rho=-0.07)
    assert np.allclose(m_ab, m_ba.T)


# ------------------------------------------------------------------ markets
def test_forecast_outcome_probs_sum_to_one():
    fc = forecast(1.5, 1.2)
    assert math.isclose(fc.p_home + fc.p_draw + fc.p_away, 1.0, abs_tol=2e-4)


def test_forecast_markets_match_the_matrix():
    lh, la, rho = 1.5, 1.2, -0.05
    m = score_matrix(lh, la, rho)
    idx = np.arange(m.shape[0])
    fc = forecast(lh, la, rho)

    over = sum(m[i, j] for i in idx for j in idx if i + j > 2)
    btts = sum(m[i, j] for i in idx for j in idx if i > 0 and j > 0)
    assert math.isclose(fc.p_over_2_5, over, abs_tol=1e-4)
    assert math.isclose(fc.p_btts, btts, abs_tol=1e-4)

    # top_scores: 5 entries, descending, led by the argmax of the matrix
    assert len(fc.top_scores) == 5
    probs = [p for _, p in fc.top_scores]
    assert probs == sorted(probs, reverse=True)
    i, j = np.unravel_index(m.argmax(), m.shape)
    assert fc.top_scores[0][0] == f"{i}-{j}"


def test_forecast_expected_goals_near_lambdas():
    """Truncation at MAX_GOALS and the DC correction shift the mean only
    slightly for realistic lambdas."""
    fc = forecast(1.8, 0.9)
    assert fc.exp_home_goals == pytest.approx(1.8, abs=0.05)
    assert fc.exp_away_goals == pytest.approx(0.9, abs=0.05)


def test_home_and_away_probs_mirror_under_team_swap():
    ab, ba = forecast(1.6, 1.0), forecast(1.0, 1.6)
    assert ab.p_home == pytest.approx(ba.p_away, abs=1e-4)
    assert ab.p_away == pytest.approx(ba.p_home, abs=1e-4)
    assert ab.p_draw == pytest.approx(ba.p_draw, abs=1e-4)


# -------------------------------------------------------------------- model
def _toy_model() -> DixonColesModel:
    return DixonColesModel(
        intercept=0.1, home_adv=0.25, rho=-0.06,
        attack={"Brazil": 0.5, "Panama": -0.3},
        defense={"Brazil": 0.4, "Panama": -0.2},
        teams={"Brazil", "Panama"},
    )


def test_expected_goals_uses_the_link_function():
    m = _toy_model()
    lh, la = m.expected_goals("Brazil", "Panama", neutral=True)
    assert lh == pytest.approx(math.exp(0.1 + 0.5 - (-0.2)))
    assert la == pytest.approx(math.exp(0.1 + (-0.3) - 0.4))


def test_home_advantage_multiplies_home_goals_only():
    m = _toy_model()
    lh_n, la_n = m.expected_goals("Brazil", "Panama", neutral=True)
    lh_h, la_h = m.expected_goals("Brazil", "Panama", neutral=False)
    assert lh_h == pytest.approx(lh_n * math.exp(m.home_adv))
    assert la_h == pytest.approx(la_n)


def test_stronger_team_is_favourite():
    fc = _toy_model().forecast("Brazil", "Panama")
    assert fc.p_home > fc.p_away


def test_unknown_team_reported_and_defaults_to_average():
    m = _toy_model()
    assert not m.known("Atlantis")
    lh, la = m.expected_goals("Atlantis", "Atlantis")
    assert lh == la == pytest.approx(math.exp(m.intercept))


def test_save_load_round_trip(tmp_path):
    m = _toy_model()
    path = tmp_path / "model.json"
    m.save(path)
    loaded = DixonColesModel.load(path)

    assert loaded.teams == m.teams
    assert loaded.rho == pytest.approx(m.rho)
    original, restored = m.forecast("Brazil", "Panama"), loaded.forecast("Brazil", "Panama")
    assert restored == original
