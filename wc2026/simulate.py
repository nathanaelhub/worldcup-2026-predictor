"""
Monte Carlo tournament simulation (M5).

Simulate the full 2026 format (48 teams, 12 groups of 4 -> 32-team knockout)
many thousands of times to get each team's probability of advancing through each
round and winning the cup. See docs/PLAN.md §5.

Knockout tie handling: 90-min score matrix -> extra-time (scaled lambdas) ->
penalty shootout (calibrated from shootouts.csv history).
"""
from __future__ import annotations


def simulate_tournament(model, groups: dict, n_sims: int = 50_000):
    """TODO (M5): return per-team probabilities {team: {advance, qf, sf, final, win}}."""
    raise NotImplementedError("tournament Monte Carlo — see docs/PLAN.md M5")
