#!/usr/bin/env python3
"""
World Cup 2026 predictor — dashboard API.

Serves the trained artifacts (run `python scripts/train.py` first):
  - upcoming matchday-3 group fixtures, predicted by the full Dixon-Coles model
  - recent group games predicted by the PRE-tournament model (honest, out-of-sample)
    vs the actual results, with a running hit rate
  - a free-form "match lab" for any two nations
  - the model card (backtested RPS vs baselines)
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from wc2026.dixon_coles import DixonColesModel, forecast   # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="")
M = ROOT / "models"

BASE_TOTAL_GOALS, SUPREMACY_PER_100 = 2.6, 0.35


@lru_cache(maxsize=1)
def artifacts():
    """Load all trained artifacts once. Returns None if training hasn't run."""
    needed = ["dc_model.json", "dc_pretournament.json", "elo.json", "fixtures.json", "metrics.json"]
    if not all((M / f).exists() for f in needed):
        return None
    return {
        "full": DixonColesModel.load(M / "dc_model.json"),
        "pre": DixonColesModel.load(M / "dc_pretournament.json"),
        "elo": json.loads((M / "elo.json").read_text()),
        "fixtures": json.loads((M / "fixtures.json").read_text()),
        "metrics": json.loads((M / "metrics.json").read_text()),
    }


def _elo_forecast(elo: dict, home: str, away: str, neutral: bool):
    adv = 0.0 if neutral else 100.0
    sup = (elo.get(home, 1500) + adv - elo.get(away, 1500)) / 100.0 * SUPREMACY_PER_100
    return forecast(max(0.2, BASE_TOTAL_GOALS / 2 + sup / 2),
                    max(0.2, BASE_TOTAL_GOALS / 2 - sup / 2))


def _predict(model, elo, home, away, neutral=True) -> dict:
    """One match -> JSON, using Dixon-Coles when both teams are known, else Elo."""
    if model.known(home) and model.known(away):
        fc, src = model.forecast(home, away, neutral), "dixon-coles"
    else:
        fc, src = _elo_forecast(elo, home, away, neutral), "elo-fallback"
    fav = home if fc.p_home >= fc.p_away else away
    return {
        "home": home, "away": away,
        "p_home": fc.p_home, "p_draw": fc.p_draw, "p_away": fc.p_away,
        "most_likely_score": fc.top_scores[0][0], "top_scores": fc.top_scores,
        "exp_goals": [fc.exp_home_goals, fc.exp_away_goals],
        "p_over_2_5": fc.p_over_2_5, "p_btts": fc.p_btts,
        "favorite": fav, "source": src,
    }


def _pred_outcome(p: dict) -> str:
    return max((("H", p["p_home"]), ("D", p["p_draw"]), ("A", p["p_away"])), key=lambda x: x[1])[0]


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/metrics")
def metrics():
    a = artifacts()
    if a is None:
        return jsonify({"ready": False})
    return jsonify({"ready": True, **a["metrics"], "as_of": a["fixtures"]["as_of"]})


@app.route("/api/teams")
def teams():
    a = artifacts()
    if a is None:
        return jsonify({"ready": False, "teams": []})
    known = a["full"].teams
    ranked = sorted(a["elo"].items(), key=lambda kv: -kv[1])
    return jsonify({"ready": True,
                    "teams": [{"team": t, "elo": round(r), "known": t in known} for t, r in ranked]})


@app.route("/api/upcoming")
def upcoming():
    a = artifacts()
    if a is None:
        return jsonify({"ready": False, "fixtures": []})
    out = []
    for fx in a["fixtures"]["upcoming"]:
        p = _predict(a["full"], a["elo"], fx["home"], fx["away"], neutral=True)
        out.append({**p, "group": fx["group"]})
    out.sort(key=lambda x: x["group"])
    return jsonify({"ready": True, "fixtures": out})


@app.route("/api/recent")
def recent():
    """Recent group games predicted by the PRE-tournament model (out-of-sample)."""
    a = artifacts()
    if a is None:
        return jsonify({"ready": False, "results": []})
    rows, correct = [], 0
    for r in a["fixtures"]["recent"]:
        p = _predict(a["pre"], a["elo"], r["home"], r["away"], neutral=r.get("neutral", True))
        actual = "H" if r["home_score"] > r["away_score"] else "D" if r["home_score"] == r["away_score"] else "A"
        hit = _pred_outcome(p) == actual
        correct += hit
        rows.append({
            "date": r["date"], "group": r["group"],
            "home": r["home"], "away": r["away"],
            "score": f"{r['home_score']}-{r['away_score']}",
            "p_home": p["p_home"], "p_draw": p["p_draw"], "p_away": p["p_away"],
            "pred": p["favorite"] if _pred_outcome(p) != "D" else "Draw",
            "actual": actual, "correct": hit,
        })
    acc = round(correct / len(rows), 3) if rows else 0.0
    return jsonify({"ready": True, "results": rows, "accuracy": acc, "n": len(rows)})


@app.route("/api/predict", methods=["POST"])
def predict():
    a = artifacts()
    if a is None:
        return jsonify({"error": "Run `python scripts/train.py` first."}), 400
    body = request.get_json() or {}
    home, away = body.get("home"), body.get("away")
    if not home or not away:
        return jsonify({"error": "home and away required"}), 400
    return jsonify(_predict(a["full"], a["elo"], home, away, bool(body.get("neutral", True))))


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
