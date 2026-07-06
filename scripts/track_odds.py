#!/usr/bin/env python3
"""
Append the latest simulated title odds to the odds history.

Runs in CI right after scripts/train.py. History accumulates deploy-over-
deploy without writing to the repo: the previous deploy's history is fetched
from the live site, merged with whatever is committed locally, and today's
snapshot is upserted — keyed by the simulation's as_of date, so reruns on the
same data replace their entry instead of duplicating it. The merged file
ships with the next deploy.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_URL = "https://nathanaelhub.github.io/worldcup-2026-predictor/data/odds_history.json"


def snapshot(sim: dict) -> dict:
    """One history entry: every simulated team's championship probability."""
    return {"date": sim["as_of"],
            "champion": {t: p["champion"] for t, p in sim["teams"].items()}}


def merge(*histories: list[dict]) -> list[dict]:
    """Union by date — later arguments win a collision. Sorted by date."""
    by_date: dict[str, dict] = {}
    for hist in histories:
        for entry in hist:
            by_date[entry["date"]] = entry
    return [by_date[d] for d in sorted(by_date)]


def fetch_live() -> list[dict]:
    try:
        with urllib.request.urlopen(LIVE_URL, timeout=10) as r:
            return json.load(r)
    except Exception as e:   # first deploy, offline dev box, or a transient
        print(f"[track_odds] live history unavailable ({e}) — using local only")
        return []


def main() -> None:
    sim_path = ROOT / "models" / "simulation.json"
    if not sim_path.exists():
        sys.exit("models/simulation.json missing — run scripts/train.py first.")
    sim = json.loads(sim_path.read_text())

    local_path = ROOT / "static" / "data" / "odds_history.json"
    local = json.loads(local_path.read_text()) if local_path.exists() else []
    # committed history beats the live site's on a date collision — the repo
    # is where corrections land (e.g. entries recomputed after a bracket fix);
    # the live copy only contributes days accumulated since the last commit
    history = merge(fetch_live(), local, [snapshot(sim)])

    out = json.dumps(history, indent=1)
    (ROOT / "models" / "odds_history.json").write_text(out)
    local_path.write_text(out)
    print(f"[track_odds] {len(history)} snapshots: "
          f"{history[0]['date']} → {history[-1]['date']}")


if __name__ == "__main__":
    main()
