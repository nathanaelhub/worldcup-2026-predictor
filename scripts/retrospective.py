#!/usr/bin/env python3
"""
Post-tournament retrospective (2026 FIFA World Cup, won by Spain over
Argentina, 1-0, July 19 2026).

Three analyses, all reproducible from data/matches.parquet and
static/data/odds_history.json:

1. Knockout-stage walk-forward RPS + outcome accuracy (Round of 32 through
   the Final) vs the Elo and naive-base-rate baselines, exactly the way
   wc2026/backtest.py scores the group stage -- except refit *per match date*,
   since the bracket only reveals each round's opponents once the previous
   round is real. The pre-tournament single-cutoff model can't forecast a QF
   it doesn't know the teams for.
2. Title-favourite tracking: at each odds_history.json refit, who did the
   model favour, and did that match the eventual champion?
3. Calibration: the champion's (and runner-up's) simulated title-win
   probability across the tournament, plus a figure.

    python scripts/retrospective.py

Writes models/retrospective.json and figures/title_odds_trajectory.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from wc2026.backtest import OUTCOMES, _elo_probs, outcome_of, rps  # noqa: E402
from wc2026.dixon_coles import DixonColesModel                    # noqa: E402
from wc2026.fixtures import KNOCKOUT_START, WC, knockout_bracket  # noqa: E402
from wc2026.ratings import Elo                                    # noqa: E402

DATA = ROOT / "data" / "matches.parquet"
ODDS_HISTORY = ROOT / "static" / "data" / "odds_history.json"
OUT = ROOT / "models" / "retrospective.json"
FIGDIR = ROOT / "figures"

CHAMPION = "Spain"
RUNNER_UP = "Argentina"


def _bracket_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """The 31 real knockout ties (R32..Final), each joined to its actual
    played date/score from the results table via the reconstructed bracket."""
    bracket = knockout_bracket(matches)
    pairs = [(t["home"], t["away"]) for rnd in bracket["rounds"] for t in rnd["ties"]]

    df = matches.copy()
    df["date"] = pd.to_datetime(df["date"])
    ko = df[(df.tournament == WC) & (df.date >= KNOCKOUT_START)]

    rows = []
    for home, away in pairs:
        m = ko[((ko.home_team == home) & (ko.away_team == away)) |
               ((ko.home_team == away) & (ko.away_team == home))]
        if m.empty:
            raise SystemExit(
                f"Knockout match {home} v {away} isn't in data/matches.parquet yet -- "
                "the tournament isn't complete in the data. Check data/knockout_overrides.json.")
        rows.append(m.iloc[0])
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def knockout_backtest(matches: pd.DataFrame) -> dict:
    """Walk-forward RPS + outcome accuracy over R32..Final, refitting the
    model (and Elo) once per distinct match date on everything known strictly
    before that date -- so each round's forecast only ever sees the previous
    round's real result, never its own."""
    ko = _bracket_matches(matches)

    naive_base = matches.assign(o=[outcome_of(h, a) for h, a in
                                   zip(matches.home_score, matches.away_score)])["o"] \
        .value_counts(normalize=True)
    naive = (float(naive_base.get("H", .45)), float(naive_base.get("D", .25)),
             float(naive_base.get("A", .30)))

    per_match = []
    for date, day in ko.groupby("date"):
        ref = date - pd.Timedelta(days=1)
        model = DixonColesModel.fit(matches, ref_date=ref)
        elo = Elo().fit(matches[matches.date < date])
        for r in day.itertuples():
            o = outcome_of(int(r.home_score), int(r.away_score))
            neutral = bool(r.neutral)
            ep = _elo_probs(elo, r.home_team, r.away_team, neutral)
            if model.known(r.home_team) and model.known(r.away_team):
                fc = model.forecast(r.home_team, r.away_team, neutral)
                mp = (fc.p_home, fc.p_draw, fc.p_away)
            else:
                mp = ep
            per_match.append({
                "date": date.strftime("%Y-%m-%d"), "home": r.home_team, "away": r.away_team,
                "home_score": int(r.home_score), "away_score": int(r.away_score),
                "shootout_winner": r.shootout_winner if isinstance(r.shootout_winner, str) else None,
                "outcome": o, "model_probs": [round(p, 4) for p in mp],
                "rps_model": round(rps(mp, o), 4), "rps_elo": round(rps(ep, o), 4),
                "rps_naive": round(rps(naive, o), 4),
                "hit": int(OUTCOMES[int(np.argmax(mp))] == o),
            })

    summary = {
        "matches": len(per_match),
        "rps_model": round(float(np.mean([m["rps_model"] for m in per_match])), 4),
        "rps_elo": round(float(np.mean([m["rps_elo"] for m in per_match])), 4),
        "rps_naive": round(float(np.mean([m["rps_naive"] for m in per_match])), 4),
        "outcome_accuracy": round(float(np.mean([m["hit"] for m in per_match])), 3),
    }
    return {"summary": summary, "per_match": per_match}


def favourite_trajectory(history: list[dict]) -> dict:
    """At each historical refit, who was the model's title favourite, and
    did it match the eventual champion?"""
    rows = []
    for entry in history:
        champs = entry["champion"]
        fav, fav_p = max(champs.items(), key=lambda kv: kv[1])
        rows.append({
            "date": entry["date"], "favourite": fav, "favourite_prob": fav_p,
            "champion_correct": fav == CHAMPION,
            "champion_prob": round(champs.get(CHAMPION, 0.0), 4),
            "runner_up_prob": round(champs.get(RUNNER_UP, 0.0), 4),
        })
    pre_knockout = rows[0]
    n_correct = sum(1 for r in rows if r["champion_correct"])
    return {
        "pre_knockout_favourite": pre_knockout["favourite"],
        "pre_knockout_favourite_prob": pre_knockout["favourite_prob"],
        "pre_knockout_favourite_was_champion": pre_knockout["champion_correct"],
        "refits_favouring_champion": n_correct,
        "refits_total": len(rows),
        "trajectory": rows,
    }


def plot_trajectory(history: list[dict], out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dates = [pd.to_datetime(e["date"]) for e in history]
    champ = [e["champion"].get(CHAMPION, 0.0) for e in history]
    runner = [e["champion"].get(RUNNER_UP, 0.0) for e in history]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(dates, champ, marker="o", color="#c8102e", label=f"{CHAMPION} (champion)")
    ax.plot(dates, runner, marker="o", color="#75aadb", label=f"{RUNNER_UP} (runner-up)")
    ax.axhline(0.5, color="grey", linewidth=0.8, linestyle=":")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Simulated title probability")
    ax.set_title("Title odds through the knockouts -- 2026 World Cup")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    FIGDIR.mkdir(exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    if not DATA.exists():
        sys.exit("data/matches.parquet missing -- run `python data/ingest.py` first.")
    matches = pd.read_parquet(DATA)
    matches["date"] = pd.to_datetime(matches["date"])

    print("Walk-forward knockout backtest (refits per match date; a few minutes)...")
    ko = knockout_backtest(matches)
    s = ko["summary"]
    print(f"  {s['matches']} knockout matches | RPS model {s['rps_model']} vs Elo {s['rps_elo']} "
          f"vs naive {s['rps_naive']} | outcome acc {s['outcome_accuracy']:.0%}")

    if not ODDS_HISTORY.exists():
        sys.exit("static/data/odds_history.json missing -- run scripts/track_odds.py first.")
    history = json.loads(ODDS_HISTORY.read_text())
    fav = favourite_trajectory(history)
    print(f"  Pre-knockout favourite: {fav['pre_knockout_favourite']} "
          f"({fav['pre_knockout_favourite_prob']:.1%}) -- "
          f"{'correct' if fav['pre_knockout_favourite_was_champion'] else 'WRONG'}, "
          f"champion was {CHAMPION}")
    print(f"  Refits favouring the eventual champion: "
          f"{fav['refits_favouring_champion']}/{fav['refits_total']}")

    fig_path = FIGDIR / "title_odds_trajectory.png"
    plot_trajectory(history, fig_path)
    print(f"  Wrote {fig_path}")

    # combined pooled record: pre-tournament group-stage backtest (from
    # models/metrics.json, already out-of-sample, single pre-tournament fit
    # since the round-robin schedule is fixed in advance) + this knockout
    # backtest (walk-forward, refit per round, since the bracket only reveals
    # opponents as previous rounds finish). Different methodologies, no
    # overlap in matches -- safe to pool.
    metrics = json.loads((ROOT / "models" / "metrics.json").read_text())
    group = metrics["backtest"]["windows"]["World Cup 2026 (group stage)"]
    combined_matches = group["matches"] + s["matches"]
    combined = {
        "matches": combined_matches,
        "rps_model": round((group["rps_model"] * group["matches"] + s["rps_model"] * s["matches"])
                           / combined_matches, 4),
        "rps_elo": round((group["rps_elo"] * group["matches"] + s["rps_elo"] * s["matches"])
                         / combined_matches, 4),
        "rps_naive": round((group["rps_naive"] * group["matches"] + s["rps_naive"] * s["matches"])
                           / combined_matches, 4),
        "outcome_accuracy": round((group["outcome_accuracy"] * group["matches"]
                                   + s["outcome_accuracy"] * s["matches"]) / combined_matches, 3),
    }

    report = {
        "champion": CHAMPION, "runner_up": RUNNER_UP, "final_score": "Spain 1-0 Argentina",
        "final_date": "2026-07-19",
        "knockout_backtest": ko,
        "favourite_trajectory": fav,
        "group_stage_backtest": group,
        "combined_out_of_sample_record": combined,
    }
    OUT.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {OUT}")
    print(f"\nCombined out-of-sample record ({combined_matches} matches): "
          f"RPS model {combined['rps_model']} vs Elo {combined['rps_elo']} "
          f"vs naive {combined['rps_naive']} | outcome acc {combined['outcome_accuracy']:.0%}")


if __name__ == "__main__":
    main()
