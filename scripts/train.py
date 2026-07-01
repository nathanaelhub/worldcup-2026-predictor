#!/usr/bin/env python3
"""
Fit the World Cup model and write every artifact the dashboard serves.

    python scripts/train.py

Outputs (models/):
    dc_model.json          Dixon-Coles fit on all data        (predict upcoming + picker)
    dc_pretournament.json  Dixon-Coles fit before 2026-06-11   (honest predicted-vs-actual)
    elo.json               Elo ratings (team ranking + fallback)
    fixtures.json          reconstructed groups, upcoming fixtures, recent results
    metrics.json           walk-forward backtest + model card
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from wc2026.backtest import evaluate_tournaments          # noqa: E402
from wc2026.dixon_coles import DixonColesModel            # noqa: E402
from wc2026.fixtures import (knockout_bracket, recent_results,  # noqa: E402
                             reconstruct_groups, upcoming_fixtures)
from wc2026.ratings import Elo                            # noqa: E402

DATA = ROOT / "data" / "matches.parquet"
OUT = ROOT / "models"
WC2026_START = "2026-06-11"


def main() -> None:
    if not DATA.exists():
        sys.exit("data/matches.parquet missing — run `python data/ingest.py` first.")
    OUT.mkdir(exist_ok=True)
    matches = pd.read_parquet(DATA)
    print(f"Loaded {len(matches):,} matches ({matches['year'].min()}–{matches['year'].max()})")

    # Elo (team ranking + unknown-team fallback)
    elo = Elo().fit(matches)
    (OUT / "elo.json").write_text(json.dumps(
        {t: round(r, 1) for t, r in sorted(elo.ratings.items(), key=lambda kv: -kv[1])}, indent=2))

    # Dixon-Coles: full (for upcoming + picker) and pre-tournament (for fair vs-actual)
    print("Fitting Dixon-Coles (full)…")
    full = DixonColesModel.fit(matches)
    full.save(OUT / "dc_model.json")
    print("Fitting Dixon-Coles (pre-tournament cutoff)…")
    pre = DixonColesModel.fit(matches, ref_date=pd.to_datetime(WC2026_START) - pd.Timedelta(days=1))
    pre.save(OUT / "dc_pretournament.json")

    # Fixtures: groups, upcoming (matchday 3), recent played games
    fixtures = {
        "as_of": matches["date"].max().strftime("%Y-%m-%d"),
        "groups": reconstruct_groups(matches),
        "upcoming": upcoming_fixtures(matches),
        "recent": recent_results(matches),
        "knockout": knockout_bracket(matches),
    }
    (OUT / "fixtures.json").write_text(json.dumps(fixtures, indent=2))
    print(f"Groups: {len(fixtures['groups'])} | upcoming fixtures: {len(fixtures['upcoming'])} "
          f"| recent played: {len(fixtures['recent'])}")

    # Walk-forward backtest on out-of-sample tournaments
    print("Backtesting (each window refits on prior data — a few minutes)…")
    windows = [
        {"name": "World Cup 2022", "start": "2022-11-20", "end": "2022-12-18", "tournament": "FIFA World Cup"},
        {"name": "World Cup 2026 (group stage so far)", "start": WC2026_START, "tournament": "FIFA World Cup"},
    ]
    report = evaluate_tournaments(matches, windows)

    card = {
        "data": {"matches": int(len(matches)),
                 "window": f"{int(matches['year'].min())}–{int(matches['year'].max())}",
                 "source": "martj42/international_results"},
        "model": "Time-weighted Dixon-Coles bivariate Poisson",
        "fitted_teams": len(full.teams), "home_adv": round(full.home_adv, 3), "rho": round(full.rho, 3),
        "backtest": report,
    }
    (OUT / "metrics.json").write_text(json.dumps(card, indent=2))

    # mirror artifacts to the static site so the client-side dashboard stays in sync
    import shutil
    web = ROOT / "static" / "data"
    web.mkdir(parents=True, exist_ok=True)
    for f in ["dc_model.json", "dc_pretournament.json", "elo.json", "fixtures.json", "metrics.json"]:
        shutil.copy(OUT / f, web / f)

    print("\n=== Backtest (RPS — lower is better) ===")
    for name, v in report["windows"].items():
        print(f"  {name}: {v['matches']} matches | "
              f"RPS model {v['rps_model']} vs Elo {v['rps_elo']} vs naive {v['rps_naive']} | "
              f"outcome acc {v['outcome_accuracy']:.0%}")
    if "pooled" in report:
        p = report["pooled"]
        print(f"  POOLED: RPS model {p['rps_model']} vs Elo {p['rps_elo']} vs naive {p['rps_naive']} "
              f"| outcome acc {p['outcome_accuracy']:.0%}")
    print(f"\nArtifacts written to {OUT}/")


if __name__ == "__main__":
    main()
