"""
Pre-match feature engineering (Layer 2).

Every feature is knowable BEFORE kickoff — it is computed only from matches
strictly earlier than the fixture, so a training frame built here carries no
leakage. See docs/PLAN.md §2.

Features per fixture:
    elo_diff        home Elo minus away Elo (point-in-time)
    elo_winprob     Elo win probability for the home side (includes venue)
    form_home_pts   avg points/game over the home side's last N internationals
    form_away_pts   ... the away side
    form_home_gd    avg goal difference over the home side's last N
    form_away_gd    ... the away side
    rest_home       days since the home side's previous match (capped)
    rest_away       ... the away side
    host_home       home side is a 2026 co-host (USA / Canada / Mexico)
    host_away       away side is a 2026 co-host
    neutral         neutral-venue flag
    importance      tournament weight (friendly 1 … World Cup 4)

Two entry points share one feature definition:
    build_training_frame(matches)  -> one leakage-safe row per historical match,
                                      labelled, for fitting a model or backtest.
    fixture_features(...)          -> the same features for a single (future)
                                      fixture, for prediction.
"""
from __future__ import annotations

from collections import defaultdict, deque

import pandas as pd

from .ratings import Elo

HOSTS_2026 = {"United States", "Canada", "Mexico"}

# tournament -> ordinal stakes (friendly lowest, the World Cup highest)
IMPORTANCE = {
    "friendly": 1,
    "FIFA World Cup qualification": 2,
    "UEFA Euro qualification": 2,
    "UEFA Nations League": 2,
    "African Cup of Nations": 3,
    "Copa América": 3,
    "UEFA Euro": 3,
    "FIFA World Cup": 4,
}
DEFAULT_IMPORTANCE = 2

FORM_WINDOW = 10
REST_CAP_DAYS = 60          # a longer layoff tells us little more than this
DEFAULT_FORM_PTS = 1.0      # neutral prior for a team with no prior matches
DEFAULT_FORM_GD = 0.0

FEATURE_COLUMNS = [
    "elo_diff", "elo_winprob", "form_home_pts", "form_away_pts",
    "form_home_gd", "form_away_gd", "rest_home", "rest_away",
    "host_home", "host_away", "neutral", "importance",
]


def _points(gf: int, ga: int) -> int:
    return 3 if gf > ga else 1 if gf == ga else 0


def _form(records, n: int) -> tuple[float, float]:
    """(avg points, avg goal diff) over the most recent ``n`` (points, gd) records."""
    recent = list(records)[-n:]
    if not recent:
        return DEFAULT_FORM_PTS, DEFAULT_FORM_GD
    return (sum(p for p, _ in recent) / len(recent),
            sum(g for _, g in recent) / len(recent))


def _rest(last_date, date) -> float:
    if last_date is None:
        return float(REST_CAP_DAYS)
    return float(min((date - last_date).days, REST_CAP_DAYS))


def _label(hs: int, as_: int) -> str:
    return "H" if hs > as_ else "D" if hs == as_ else "A"


def build_training_frame(matches: pd.DataFrame, form_window: int = FORM_WINDOW) -> pd.DataFrame:
    """One leakage-safe feature row per historical match, in date order.

    A single forward pass: each row's features are read from state accumulated
    by *earlier* matches only, then the match folds into that state (point-in-
    time Elo, rolling form, last-match date). Every row carries the H/D/A label
    and both scores, so the frame is ready for an outcome or a score model.
    """
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    elo = Elo()
    form: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))
    last: dict[str, pd.Timestamp] = {}

    rows = []
    for m in df.itertuples():
        home, away = m.home_team, m.away_team
        hs, as_ = int(m.home_score), int(m.away_score)
        neutral = bool(getattr(m, "neutral", False))
        tour = getattr(m, "tournament", "friendly")

        fp, fgd = _form(form[home], form_window)
        ap, agd = _form(form[away], form_window)
        rows.append({
            "date": m.date, "home": home, "away": away,
            "elo_diff": elo.get(home) - elo.get(away),
            "elo_winprob": elo.win_probability(home, away, neutral),
            "form_home_pts": fp, "form_away_pts": ap,
            "form_home_gd": fgd, "form_away_gd": agd,
            "rest_home": _rest(last.get(home), m.date),
            "rest_away": _rest(last.get(away), m.date),
            "host_home": int(home in HOSTS_2026),
            "host_away": int(away in HOSTS_2026),
            "neutral": int(neutral),
            "importance": IMPORTANCE.get(tour, DEFAULT_IMPORTANCE),
            "home_goals": hs, "away_goals": as_,
            "label": _label(hs, as_),
        })

        # fold this match into the state only AFTER its row is recorded
        elo.update_match(home, away, hs, as_, tour, neutral)
        form[home].append((_points(hs, as_), hs - as_))
        form[away].append((_points(as_, hs), as_ - hs))
        last[home] = last[away] = m.date

    return pd.DataFrame(rows)


def fixture_features(matches: pd.DataFrame, home: str, away: str, date,
                     neutral: bool = True, elo: Elo | None = None,
                     tournament: str = "FIFA World Cup",
                     form_window: int = FORM_WINDOW) -> dict:
    """Features for a single (possibly future) fixture, using only matches
    strictly before ``date``.

    ``elo`` should be ratings fit on that same prior history; when omitted it is
    fit here from the matches before ``date`` (convenient, but O(history) — pass
    a pre-fit Elo when scoring many fixtures).
    """
    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    date = pd.to_datetime(date)
    prior = df[df["date"] < date].sort_values("date")

    if elo is None:
        elo = Elo().fit(prior)

    def team_form(team):
        rec = deque(maxlen=form_window)
        for m in prior[(prior.home_team == team) | (prior.away_team == team)].itertuples():
            if m.home_team == team:
                rec.append((_points(int(m.home_score), int(m.away_score)),
                            int(m.home_score) - int(m.away_score)))
            else:
                rec.append((_points(int(m.away_score), int(m.home_score)),
                            int(m.away_score) - int(m.home_score)))
        return _form(rec, form_window)

    def team_rest(team):
        t = prior[(prior.home_team == team) | (prior.away_team == team)]
        return _rest(t["date"].max() if len(t) else None, date)

    fp, fgd = team_form(home)
    ap, agd = team_form(away)
    return {
        "elo_diff": elo.get(home) - elo.get(away),
        "elo_winprob": elo.win_probability(home, away, neutral),
        "form_home_pts": fp, "form_away_pts": ap,
        "form_home_gd": fgd, "form_away_gd": agd,
        "rest_home": team_rest(home), "rest_away": team_rest(away),
        "host_home": int(home in HOSTS_2026), "host_away": int(away in HOSTS_2026),
        "neutral": int(neutral),
        "importance": IMPORTANCE.get(tournament, DEFAULT_IMPORTANCE),
    }
