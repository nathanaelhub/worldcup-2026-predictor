"""
Model wrapper + blend (Layer 2).

Combines the Dixon-Coles score model with a feature-based gradient-boosted model
via a logarithmic opinion pool, with the blend weight tuned on validation RPS.
Exposes one clean `predict(home, away, context)` the app and backtest both call.

TODO — see docs/PLAN.md §2 Layer 2:
    - GBM (or PyMC hierarchical bivariate Poisson) on engineered features
    - log-pool blend weight tuned against validation RPS
    - persistence to models/ (params + metrics.json), like the F1 project
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Prediction:
    p_home: float
    p_draw: float
    p_away: float
    score_distribution: dict        # "i-j" -> probability
    most_likely_score: str


class WorldCupModel:
    """Unified interface over the rating prior, the Dixon-Coles core, and the blend."""

    def fit(self, matches):
        raise NotImplementedError("model fit/blend — see docs/PLAN.md M3")

    def predict(self, home: str, away: str, neutral: bool = True,
                knockout: bool = False) -> Prediction:
        raise NotImplementedError("model predict — see docs/PLAN.md M3")

    def save(self, path: str):
        raise NotImplementedError

    @classmethod
    def load(cls, path: str) -> "WorldCupModel":
        raise NotImplementedError
