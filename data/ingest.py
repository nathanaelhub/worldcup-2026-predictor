#!/usr/bin/env python3
"""
Data ingestion for the World Cup 2026 predictor.

Pulls the canonical international-football dataset (every men's international
since 1872) plus the penalty-shootout history, and writes a tidy match table the
rest of the pipeline trains on. Both sources are public CSVs — no auth, no Kaggle.

    python data/ingest.py            # -> data/matches.parquet
    python data/ingest.py --refresh  # re-download even if cached

Source: https://github.com/martj42/international_results
"""
from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).parent / "raw"
BASE = "https://raw.githubusercontent.com/martj42/international_results/master"
FILES = {
    "results": f"{BASE}/results.csv",       # date, home/away team + score, tournament, venue, neutral
    "shootouts": f"{BASE}/shootouts.csv",   # penalty-shootout winners (for knockout modeling)
}


def _load(name: str, refresh: bool) -> pd.DataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / f"{name}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    # fetch via requests (bundles CA certs) rather than pandas' urllib path
    resp = requests.get(FILES[name], timeout=30)
    resp.raise_for_status()
    cache.write_text(resp.text)
    return pd.read_csv(StringIO(resp.text))


def build(refresh: bool = False) -> pd.DataFrame:
    results = _load("results", refresh)
    shootouts = _load("shootouts", refresh)

    df = results.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df = df.dropna(subset=["home_score", "away_score"]).reset_index(drop=True)
    df[["home_score", "away_score"]] = df[["home_score", "away_score"]].astype(int)

    df["neutral"] = df["neutral"].astype(str).str.lower().isin(["true", "1"])
    df["is_world_cup"] = df["tournament"].eq("FIFA World Cup")
    df["result"] = (df["home_score"] > df["away_score"]).map({True: "H", False: None})
    df.loc[df["home_score"] == df["away_score"], "result"] = "D"
    df.loc[df["home_score"] < df["away_score"], "result"] = "A"

    # attach shootout winner where a match went to penalties (knockout tie-breaks)
    so = shootouts.copy()
    so["date"] = pd.to_datetime(so["date"])
    df = df.merge(
        so[["date", "home_team", "away_team", "winner"]].rename(columns={"winner": "shootout_winner"}),
        on=["date", "home_team", "away_team"], how="left",
    )

    out = Path(__file__).parent / "matches.parquet"
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df):,} matches ({df['year'].min()}–{df['year'].max()}) -> {out}")
    print(f"  World Cup matches: {int(df['is_world_cup'].sum()):,}")
    print(f"  shootouts linked:  {int(df['shootout_winner'].notna().sum()):,}")
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest international football results")
    ap.add_argument("--refresh", action="store_true", help="re-download source CSVs")
    build(refresh=ap.parse_args().refresh)


if __name__ == "__main__":
    main()
