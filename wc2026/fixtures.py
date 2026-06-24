"""
World Cup 2026 fixtures.

The results feed only contains *played* matches, so we reconstruct the group
structure from who has played whom (each group of four is a connected component),
then enumerate each group's round-robin to find the fixtures that haven't been
played yet — those are the upcoming matches the dashboard predicts.
"""
from __future__ import annotations

from itertools import combinations

import pandas as pd

WC = "FIFA World Cup"


def _wc_group_matches(matches: pd.DataFrame, season_start="2026-06-01") -> pd.DataFrame:
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[(df.tournament == WC) & (df.date >= season_start)]


def reconstruct_groups(matches: pd.DataFrame) -> dict[str, list[str]]:
    """Infer the groups as connected components of teams that have played."""
    wc = _wc_group_matches(matches)
    teams = set(wc.home_team) | set(wc.away_team)
    parent = {t: t for t in teams}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in wc.itertuples():
        parent[find(r.home_team)] = find(r.away_team)

    comps: dict[str, list[str]] = {}
    for t in teams:
        comps.setdefault(find(t), []).append(t)

    # label A, B, C... deterministically by the group's alphabetically-first nation
    labelled = {}
    for i, members in enumerate(sorted(comps.values(), key=lambda m: sorted(m)[0])):
        labelled[chr(ord("A") + i)] = sorted(members)
    return labelled


def upcoming_fixtures(matches: pd.DataFrame) -> list[dict]:
    """Round-robin pairings within each reconstructed group not yet played."""
    wc = _wc_group_matches(matches)
    played = {frozenset((r.home_team, r.away_team)) for r in wc.itertuples()}
    out = []
    for group, members in reconstruct_groups(matches).items():
        for a, b in combinations(members, 2):
            if frozenset((a, b)) not in played:
                out.append({"home": a, "away": b, "group": group})
    return out


def recent_results(matches: pd.DataFrame, limit: int | None = None) -> list[dict]:
    """Played WC group matches (most recent first) for the predicted-vs-actual view."""
    wc = _wc_group_matches(matches).sort_values("date", ascending=False)
    groups = {t: g for g, members in reconstruct_groups(matches).items() for t in members}
    rows = []
    for r in wc.itertuples():
        rows.append({
            "date": pd.to_datetime(r.date).strftime("%Y-%m-%d"),
            "home": r.home_team, "away": r.away_team,
            "home_score": int(r.home_score), "away_score": int(r.away_score),
            "neutral": bool(r.neutral),
            "group": groups.get(r.home_team, "?"),
        })
    return rows[:limit] if limit else rows
