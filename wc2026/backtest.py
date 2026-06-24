"""
Walk-forward evaluation.

Primary metric: the Ranked Probability Score (RPS) — the proper scoring rule for
ordered 1X2 football forecasts (Constantinou & Fenton, 2012). We evaluate on
out-of-sample tournaments (the model only ever trains on earlier matches) and
always report two baselines: an Elo→goals model and the naive base rate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .dixon_coles import DixonColesModel, forecast
from .ratings import Elo

OUTCOMES = ("H", "D", "A")
BASE_TOTAL_GOALS = 2.6
SUPREMACY_PER_100 = 0.35


def rps(probs, outcome: str) -> float:
    """Ranked Probability Score for one ordered 3-way forecast (lower = better)."""
    p = np.asarray(probs, dtype=float)
    obs = np.zeros(3)
    obs[OUTCOMES.index(outcome)] = 1.0
    return float(np.sum((np.cumsum(p) - np.cumsum(obs)) ** 2) / 2.0)


def devig(odds_h, odds_d, odds_a):
    """Bookmaker decimal odds -> implied probabilities, margin removed."""
    raw = np.array([1 / odds_h, 1 / odds_d, 1 / odds_a])
    return tuple(round(float(x), 4) for x in raw / raw.sum())


def outcome_of(hs: int, as_: int) -> str:
    return "H" if hs > as_ else "D" if hs == as_ else "A"


def _elo_probs(elo: Elo, home: str, away: str, neutral: bool):
    """Elo baseline: map the rating gap to expected goals, then a score matrix."""
    adv = 0.0 if neutral else 100.0
    sup = (elo.get(home) + adv - elo.get(away)) / 100.0 * SUPREMACY_PER_100
    lh = max(0.2, BASE_TOTAL_GOALS / 2 + sup / 2)
    la = max(0.2, BASE_TOTAL_GOALS / 2 - sup / 2)
    fc = forecast(lh, la)
    return (fc.p_home, fc.p_draw, fc.p_away)


def evaluate_tournaments(matches: pd.DataFrame, windows: list[dict]) -> dict:
    """For each window {name, start, tournament}, fit on matches strictly before
    `start`, predict that tournament's matches, and score model vs baselines.

    `windows` example: [{"name": "World Cup 2022", "start": "2022-11-20",
                         "tournament": "FIFA World Cup", "end": "2022-12-18"}]
    """
    # naive base rate from all matches (home/draw/away frequencies)
    base = matches.assign(o=[outcome_of(h, a) for h, a in
                            zip(matches.home_score, matches.away_score)])["o"].value_counts(normalize=True)
    naive = (float(base.get("H", .45)), float(base.get("D", .25)), float(base.get("A", .30)))

    report = {"naive_base_rate": {"H": round(naive[0], 3), "D": round(naive[1], 3),
                                  "A": round(naive[2], 3)}, "windows": {}}
    for win in windows:
        start = pd.to_datetime(win["start"])
        end = pd.to_datetime(win.get("end", "2100-01-01"))
        test = matches[(matches.date >= start) & (matches.date <= end)
                       & (matches.tournament == win["tournament"])]
        if test.empty:
            continue
        model = DixonColesModel.fit(matches, ref_date=start - pd.Timedelta(days=1))
        elo = Elo().fit(matches[matches.date < start])

        m_rps, e_rps, n_rps, m_hit = [], [], [], []
        for r in test.itertuples():
            o = outcome_of(int(r.home_score), int(r.away_score))
            neutral = bool(r.neutral)
            if model.known(r.home_team) and model.known(r.away_team):
                fc = model.forecast(r.home_team, r.away_team, neutral)
                mp = (fc.p_home, fc.p_draw, fc.p_away)
            else:
                mp = _elo_probs(elo, r.home_team, r.away_team, neutral)
            m_rps.append(rps(mp, o))
            e_rps.append(rps(_elo_probs(elo, r.home_team, r.away_team, neutral), o))
            n_rps.append(rps(naive, o))
            m_hit.append(int(OUTCOMES[int(np.argmax(mp))] == o))

        report["windows"][win["name"]] = {
            "matches": len(test),
            "rps_model": round(float(np.mean(m_rps)), 4),
            "rps_elo": round(float(np.mean(e_rps)), 4),
            "rps_naive": round(float(np.mean(n_rps)), 4),
            "outcome_accuracy": round(float(np.mean(m_hit)), 3),
        }

    # pooled across all windows
    if report["windows"]:
        w = report["windows"].values()
        tot = sum(v["matches"] for v in w)
        report["pooled"] = {
            "matches": tot,
            "rps_model": round(sum(v["rps_model"] * v["matches"] for v in w) / tot, 4),
            "rps_elo": round(sum(v["rps_elo"] * v["matches"] for v in w) / tot, 4),
            "rps_naive": round(sum(v["rps_naive"] * v["matches"] for v in w) / tot, 4),
            "outcome_accuracy": round(sum(v["outcome_accuracy"] * v["matches"] for v in w) / tot, 3),
        }
    return report
