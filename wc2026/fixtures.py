"""
World Cup 2026 fixtures.

The results feed only contains *played* matches, so we reconstruct the group
structure from who has played whom (each group of four is a connected component),
then enumerate each group's round-robin to find the fixtures that haven't been
played yet — those are the upcoming matches the dashboard predicts.
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import pandas as pd

WC = "FIFA World Cup"
KO_PATH = Path(__file__).resolve().parent.parent / "data" / "knockout_r32.json"
KNOCKOUT_START = "2026-06-28"   # group stage ends 06-27; knockouts are cross-group


def _wc_group_matches(matches: pd.DataFrame, season_start="2026-06-01") -> pd.DataFrame:
    """Group-stage matches only — excluding knockouts, which are cross-group and
    would otherwise merge groups in the connected-component reconstruction."""
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df[(df.tournament == WC) & (df.date >= season_start) & (df.date < KNOCKOUT_START)]


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


ROUND_NAMES = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Final"]


def knockout_bracket(matches: pd.DataFrame) -> dict:
    """The real knockout bracket, cascading actual results from the dataset.

    The R32 draw comes from data/knockout_r32.json (bracket order, matches 73-88);
    consecutive ties feed the next round. Each round's teams are the *real*
    winners of the previous round, and a tie's score is filled in once the dataset
    contains that match — so the whole bracket auto-advances with reality. Slots
    whose feeders haven't finished stay null (TBD); the app fills those with model
    predictions on the Predicted tab, and leaves them blank on the Live tab.
    """
    empty = {"rounds": [{"round": r, "ties": []} for r in ROUND_NAMES]}
    if not KO_PATH.exists():
        return empty
    spec = json.loads(KO_PATH.read_text())

    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    ko = df[(df.tournament == WC) & (df.date >= KNOCKOUT_START)]
    results = {}
    for r in ko.itertuples():
        so = r.shootout_winner if isinstance(r.shootout_winner, str) else None
        results[frozenset((r.home_team, r.away_team))] = {
            r.home_team: int(r.home_score), r.away_team: int(r.away_score), "so": so}

    def make_tie(home, away):
        res = results.get(frozenset((home, away))) if home and away else None
        if res:
            hs, as_ = res[home], res[away]
            winner = home if hs > as_ else away if as_ > hs else res.get("so")
            return {"home": home, "away": away, "played": True,
                    "home_score": hs, "away_score": as_, "winner": winner}
        return {"home": home, "away": away, "played": False,
                "home_score": None, "away_score": None, "winner": None}

    r32 = [make_tie(h, a) for h, a in spec["ties"]]
    rounds = [{"round": "Round of 32", "ties": r32}]
    prev = r32
    for name in ROUND_NAMES[1:]:
        cur = [make_tie(prev[i]["winner"], prev[i + 1]["winner"])
               for i in range(0, len(prev), 2)]
        rounds.append({"round": name, "ties": cur})
        prev = cur
    return {"rounds": rounds}
