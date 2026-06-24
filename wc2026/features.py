"""
Pre-match feature engineering (Layer 2).

Every feature must be knowable BEFORE kickoff — no leakage. See docs/PLAN.md §2.

Planned features (TODO):
    elo_diff              home Elo (+ host adv) minus away Elo
    fifa_rank_diff        ranking gap
    form_home/away        rolling points & goal diff over last N internationals
    rest_days, travel     days since last match, confederation distance
    host_advantage        2026 co-hosts USA / Canada / Mexico
    tournament_importance friendly < qualifier < major
    squad_value_diff      Transfermarkt market value (optional enrichment)
"""
from __future__ import annotations

HOSTS_2026 = {"United States", "Canada", "Mexico"}


def build_features(matches, elo, as_of=None):
    """TODO (M3): return a leakage-safe feature frame for the given fixtures."""
    raise NotImplementedError("feature engineering — see docs/PLAN.md M3")
