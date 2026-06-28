"""
Projected knockout bracket.

The group stage may not be finished, so we project a final table: actual points
and goals from played group games, plus *expected* points and goals (from the
model) for the games still to play. From that table we take the 12 group winners,
12 runners-up, and the 8 best third-placed teams — the 32-team knockout field —
then power-seed them 1..32 by Elo into a standard single-elimination bracket.

The bracket itself (who beats whom) is predicted client-side, so it stays live;
this module only decides *which 32 teams* go in and *in what order*.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .fixtures import reconstruct_groups, upcoming_fixtures


def _standings(matches: pd.DataFrame, groups: dict, model) -> dict:
    """Per-team {pts, gf, ga} = played results + expected value of remaining games."""
    team2grp = {t: g for g, ts in groups.items() for t in ts}
    st = {t: {"pts": 0.0, "gf": 0.0, "ga": 0.0} for ts in groups.values() for t in ts}

    wc = matches[(matches.tournament == "FIFA World Cup") & (matches.date >= "2026-06-01")]
    for r in wc.itertuples():
        if r.home_team not in team2grp:
            continue
        hs, as_ = int(r.home_score), int(r.away_score)
        st[r.home_team]["gf"] += hs; st[r.home_team]["ga"] += as_
        st[r.away_team]["gf"] += as_; st[r.away_team]["ga"] += hs
        st[r.home_team]["pts"] += 3 if hs > as_ else 1 if hs == as_ else 0
        st[r.away_team]["pts"] += 3 if as_ > hs else 1 if hs == as_ else 0

    # expected value of the games still to play
    for fx in upcoming_fixtures(matches):
        h, a = fx["home"], fx["away"]
        if not (model.known(h) and model.known(a)):
            continue
        fc = model.forecast(h, a, neutral=True)
        st[h]["pts"] += 3 * fc.p_home + fc.p_draw
        st[a]["pts"] += 3 * fc.p_away + fc.p_draw
        st[h]["gf"] += fc.exp_home_goals; st[h]["ga"] += fc.exp_away_goals
        st[a]["gf"] += fc.exp_away_goals; st[a]["ga"] += fc.exp_home_goals
    return st


def _rank(teams: list[str], st: dict) -> list[str]:
    return sorted(teams, key=lambda t: (-st[t]["pts"], -(st[t]["gf"] - st[t]["ga"]), -st[t]["gf"]))


def _bracket_order(n: int) -> list[int]:
    """Standard single-elimination seed positions (1 vs n, 2 in the far half…)."""
    seeds = [1]
    while len(seeds) < n:
        m = len(seeds) * 2 + 1
        seeds = [s for x in seeds for s in (x, m - x)]
    return seeds


def build(matches: pd.DataFrame, model, elo: dict) -> dict:
    groups = reconstruct_groups(matches)
    st = _standings(matches, groups, model)

    winners, runners, thirds = [], [], []
    for g, teams in groups.items():
        ranked = _rank(teams, st)
        winners.append((ranked[0], g, "1st"))
        runners.append((ranked[1], g, "2nd"))
        thirds.append((ranked[2], g, "3rd"))

    best_thirds = sorted(thirds, key=lambda x: (-st[x[0]]["pts"],
                         -(st[x[0]]["gf"] - st[x[0]]["ga"]), -st[x[0]]["gf"]))[:8]
    field = winners + runners + best_thirds          # 12 + 12 + 8 = 32

    # power-seed 1..32 by Elo, then drop into the standard bracket order
    by_strength = sorted(field, key=lambda x: -elo.get(x[0], 1500))
    seed_of = {name: i + 1 for i, (name, _, _) in enumerate(by_strength)}
    order = _bracket_order(32)
    seat = {s: by_strength[s - 1][0] for s in order}
    seeds_in_order = [seat[s] for s in order]

    qualifiers = [{"name": n, "group": g, "pos": p, "seed": seed_of[n]}
                  for n, g, p in field]
    n_complete = sum(1 for g, ts in groups.items()
                     if all(st[t]["pts"] == int(st[t]["pts"]) for t in ts))
    return {
        "seeds": seeds_in_order,
        "qualifiers": sorted(qualifiers, key=lambda q: q["seed"]),
        "groups_complete": n_complete,
        "projected": n_complete < len(groups),
    }
