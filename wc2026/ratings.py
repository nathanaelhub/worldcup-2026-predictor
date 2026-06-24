"""
World-football Elo ratings.

A from-scratch, reproducible Elo (in the eloratings.net spirit): goal-difference
weighted updates and tournament-importance K-factors. Feeding the model our *own*
ratings (rather than a scraped black box) keeps the whole pipeline auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# tournament importance -> base K (eloratings.net style)
K_BY_IMPORTANCE = {
    "FIFA World Cup": 60,
    "FIFA World Cup qualification": 40,
    "UEFA Euro": 50, "Copa América": 50,
    "friendly": 20,
}
DEFAULT_K = 30
HOME_ADV = 100.0          # Elo points added to the non-neutral home side


@dataclass
class Elo:
    base: float = 1500.0
    ratings: dict[str, float] = field(default_factory=dict)

    def get(self, team: str) -> float:
        return self.ratings.get(team, self.base)

    @staticmethod
    def _expected(r_a: float, r_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))

    @staticmethod
    def _gd_multiplier(goal_diff: int) -> float:
        """eloratings.net goal-difference weighting."""
        g = abs(goal_diff)
        if g <= 1:
            return 1.0
        if g == 2:
            return 1.5
        return (11 + g) / 8.0

    def update_match(self, home: str, away: str, hs: int, as_: int,
                     tournament: str = "friendly", neutral: bool = False) -> None:
        adv = 0.0 if neutral else HOME_ADV
        exp_home = self._expected(self.get(home) + adv, self.get(away))
        score_home = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
        k = K_BY_IMPORTANCE.get(tournament, DEFAULT_K) * self._gd_multiplier(hs - as_)
        delta = k * (score_home - exp_home)
        self.ratings[home] = self.get(home) + delta
        self.ratings[away] = self.get(away) - delta

    def fit(self, matches: pd.DataFrame) -> "Elo":
        """Replay matches in date order to build current ratings."""
        for m in matches.sort_values("date").itertuples():
            self.update_match(m.home_team, m.away_team, int(m.home_score),
                              int(m.away_score), getattr(m, "tournament", "friendly"),
                              bool(getattr(m, "neutral", False)))
        return self

    def win_probability(self, home: str, away: str, neutral: bool = False) -> float:
        adv = 0.0 if neutral else HOME_ADV
        return self._expected(self.get(home) + adv, self.get(away))
