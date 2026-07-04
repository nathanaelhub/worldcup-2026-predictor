"""
Monte Carlo tournament simulation (M5).

Simulate the knockout bracket from its *current real state* thousands of times
to get each team's probability of reaching every round and winning the cup.
Played ties keep their real result in every simulation; unplayed ties are
sampled from the Dixon-Coles score matrix (Elo fallback for unfitted teams).

Knockout tie handling: 90-min sample from the DC matrix -> if level, extra
time as a 30-minute Poisson (rho off — the low-score correction isn't
calibrated for part-matches) -> if still level, a penalty shootout, treated as
a fair coin (`p_home_shootout` overrides; calibrating it from shootout history
is a follow-up).

The group stage resolved before this landed, so simulation starts at the
bracket; see docs/PLAN.md §5 for the original full-format plan.
"""
from __future__ import annotations

import numpy as np

from .dixon_coles import score_matrix

# Elo fallback — same parameterization the dashboard API uses for teams
# outside the fitted pool.
BASE_TOTAL_GOALS, SUPREMACY_PER_100 = 2.6, 0.35
ET_FRACTION = 1 / 3          # extra time adds 30 minutes to a 90-minute match

# What winning each successive round earns you, deepest bracket first.
ROUND_KEYS = ["r16", "qf", "sf", "final", "champion"]


class _MatchSampler:
    """Samples match outcomes, caching each pairing's score distribution."""

    def __init__(self, model, elo: dict | None, rng: np.random.Generator,
                 p_home_shootout: float = 0.5):
        self.model = model
        self.elo = elo or {}
        self.rng = rng
        self.p_home_shootout = p_home_shootout
        self._cdf: dict[tuple, tuple[np.ndarray, int]] = {}

    def _lambdas(self, home: str, away: str) -> tuple[float, float, float]:
        if self.model.known(home) and self.model.known(away):
            lh, la = self.model.expected_goals(home, away, neutral=True)
            return lh, la, self.model.rho
        sup = (self.elo.get(home, 1500) - self.elo.get(away, 1500)) / 100.0 * SUPREMACY_PER_100
        return (max(0.2, BASE_TOTAL_GOALS / 2 + sup / 2),
                max(0.2, BASE_TOTAL_GOALS / 2 - sup / 2), 0.0)

    def _cumulative(self, key: tuple, lh: float, la: float, rho: float):
        cached = self._cdf.get(key)
        if cached is None:
            m = score_matrix(lh, la, rho)
            cached = (np.cumsum(m.ravel()), m.shape[1])
            self._cdf[key] = cached
        return cached

    def goals(self, home: str, away: str, extra_time: bool = False) -> tuple[int, int]:
        lh, la, rho = self._lambdas(home, away)
        if extra_time:
            key, lh, la, rho = (home, away, "et"), lh * ET_FRACTION, la * ET_FRACTION, 0.0
        else:
            key = (home, away, "ft")
        cdf, width = self._cumulative(key, lh, la, rho)
        idx = int(np.searchsorted(cdf, self.rng.random()))
        return idx // width, idx % width

    def knockout_winner(self, home: str, away: str) -> str:
        hg, ag = self.goals(home, away)
        if hg != ag:
            return home if hg > ag else away
        eh, ea = self.goals(home, away, extra_time=True)
        if eh != ea:
            return home if eh > ea else away
        return home if self.rng.random() < self.p_home_shootout else away


def simulate_bracket(model, bracket: dict, elo: dict | None = None,
                     n_sims: int = 10_000, seed: int | None = None,
                     p_home_shootout: float = 0.5) -> dict:
    """Monte Carlo the knockout bracket from its current real state.

    `bracket` is the `knockout` dict fixtures.py builds ({"rounds": [{"round",
    "ties": [{"home", "away", "played", "winner", ...}]}]}); the first round's
    ties define the field. Played ties (in any round) keep their real winner in
    every simulation. Works on any power-of-two bracket, so tests can use toy
    fields.

    Returns {"n_sims", "teams": {team: {round_key: probability}}} where the
    round keys are the tail of ROUND_KEYS sized to the bracket depth
    (16 first-round ties -> r16/qf/sf/final/champion).
    """
    rounds = bracket["rounds"]
    first = rounds[0]["ties"]
    n_rounds = (2 * len(first)).bit_length() - 1
    keys = ROUND_KEYS[-n_rounds:]

    rng = np.random.default_rng(seed)
    sampler = _MatchSampler(model, elo, rng, p_home_shootout)
    teams = [t for tie in first for t in (tie["home"], tie["away"]) if t]
    counts = {t: dict.fromkeys(keys, 0) for t in teams}

    for _ in range(n_sims):
        winners = []
        for tie in first:
            w = tie["winner"] if tie["played"] else sampler.knockout_winner(tie["home"], tie["away"])
            counts[w][keys[0]] += 1
            winners.append(w)

        for depth, key in enumerate(keys[1:], start=1):
            real = rounds[depth]["ties"] if depth < len(rounds) else []
            nxt = []
            for i in range(0, len(winners), 2):
                a, b = winners[i], winners[i + 1]
                tie = real[i // 2] if i // 2 < len(real) else None
                # a played real tie is only reachable when its feeders are real
                # too, so the pairing always matches — but check to be safe
                if tie and tie["played"] and {tie["home"], tie["away"]} == {a, b}:
                    w = tie["winner"]
                else:
                    w = sampler.knockout_winner(a, b)
                counts[w][key] += 1
                nxt.append(w)
            winners = nxt

    probs = {t: {k: round(v / n_sims, 4) for k, v in c.items()}
             for t, c in sorted(counts.items())}
    return {"n_sims": n_sims, "teams": probs}
