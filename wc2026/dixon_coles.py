"""
Bivariate-Poisson / Dixon-Coles score model.

Each team has a latent attack and defense strength; expected goals are

    log λ_home = μ + home_adv·(not neutral) + attack_home − defense_away
    log λ_away = μ                          + attack_away − defense_home

Strengths are fit by **time-weighted Poisson regression** (exponential half-life,
so recent form dominates), and the low-score dependence is captured by the
**Dixon-Coles τ correction** with ρ estimated by maximum likelihood. From the
fitted λ's the full P(home=i, away=j) score matrix follows in closed form, and
every market (1X2, correct score, over/under, BTTS) is a sum over its cells.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import poisson

MAX_GOALS = 10


# ----------------------------------------------------------------- score matrix
def _dc_tau(i: int, j: int, lh: float, la: float, rho: float) -> float:
    """Dixon-Coles correction for the four low-score cells."""
    if i == 0 and j == 0:
        return 1.0 - lh * la * rho
    if i == 0 and j == 1:
        return 1.0 + lh * rho
    if i == 1 and j == 0:
        return 1.0 + la * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lambda_home: float, lambda_away: float,
                 rho: float = -0.05, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Full P(i, j) score matrix with the Dixon-Coles correction, normalized."""
    h = poisson.pmf(np.arange(max_goals + 1), lambda_home)
    a = poisson.pmf(np.arange(max_goals + 1), lambda_away)
    m = np.outer(h, a)
    for i in (0, 1):
        for j in (0, 1):
            m[i, j] *= _dc_tau(i, j, lambda_home, lambda_away, rho)
    return m / m.sum()


@dataclass
class MatchForecast:
    p_home: float
    p_draw: float
    p_away: float
    top_scores: list[tuple[str, float]]
    exp_home_goals: float
    exp_away_goals: float
    p_over_2_5: float
    p_btts: float


def forecast(lambda_home: float, lambda_away: float, rho: float = -0.05) -> MatchForecast:
    """Collapse a score matrix into the standard betting markets."""
    m = score_matrix(lambda_home, lambda_away, rho)
    idx = np.arange(m.shape[0])
    p_home = float(np.tril(m, -1).sum())
    p_draw = float(np.trace(m))
    p_away = float(np.triu(m, 1).sum())

    flat = sorted(((i, j, m[i, j]) for i in idx for j in idx), key=lambda x: -x[2])
    top = [(f"{i}-{j}", round(float(p), 4)) for i, j, p in flat[:5]]
    over = float(sum(m[i, j] for i in idx for j in idx if i + j > 2))
    btts = float(sum(m[i, j] for i in idx for j in idx if i > 0 and j > 0))
    return MatchForecast(
        p_home=round(p_home, 4), p_draw=round(p_draw, 4), p_away=round(p_away, 4),
        top_scores=top,
        exp_home_goals=round(float((m.sum(axis=1) * idx).sum()), 2),
        exp_away_goals=round(float((m.sum(axis=0) * idx).sum()), 2),
        p_over_2_5=round(over, 4), p_btts=round(btts, 4),
    )


# -------------------------------------------------------------------- the model
@dataclass
class DixonColesModel:
    intercept: float = 0.0
    home_adv: float = 0.0
    rho: float = -0.05
    attack: dict[str, float] = field(default_factory=dict)
    defense: dict[str, float] = field(default_factory=dict)
    teams: set[str] = field(default_factory=set)

    # ---- fitting ----
    @classmethod
    def fit(cls, matches: pd.DataFrame, ref_date=None, half_life_days: int = 730,
            since: str = "2014-01-01", min_matches: int = 8) -> "DixonColesModel":
        import statsmodels.api as sm
        import statsmodels.formula.api as smf

        df = matches.copy()
        df["date"] = pd.to_datetime(df["date"])
        ref = pd.to_datetime(ref_date) if ref_date is not None else df["date"].max()
        df = df[(df["date"] >= since) & (df["date"] <= ref)]

        # keep teams with enough recent matches, then matches between kept teams
        counts = pd.concat([df["home_team"], df["away_team"]]).value_counts()
        keep = set(counts[counts >= min_matches].index)
        df = df[df["home_team"].isin(keep) & df["away_team"].isin(keep)]

        # exponential time weight
        age_days = (ref - df["date"]).dt.days
        w = np.exp(-np.log(2) * age_days / half_life_days)

        # long format: one row per team-in-match (their goals scored)
        home = pd.DataFrame({
            "goals": df["home_score"].values, "team": df["home_team"].values,
            "opponent": df["away_team"].values,
            "is_home": (~df["neutral"].astype(bool)).astype(int).values, "w": w.values})
        away = pd.DataFrame({
            "goals": df["away_score"].values, "team": df["away_team"].values,
            "opponent": df["home_team"].values,
            "is_home": np.zeros(len(df), dtype=int), "w": w.values})
        long = pd.concat([home, away], ignore_index=True)

        model = smf.glm("goals ~ C(team) + C(opponent) + is_home",
                        data=long, family=sm.families.Poisson(),
                        freq_weights=long["w"]).fit()

        # unpack coefficients into attack (team) / defense (opponent) dicts
        params = model.params
        teams = sorted(keep)
        attack = {t: 0.0 for t in teams}
        defense = {t: 0.0 for t in teams}
        for name, val in params.items():
            if name.startswith("C(team)[T."):
                attack[name[len("C(team)[T."):-1]] = float(val)
            elif name.startswith("C(opponent)[T."):
                # opponent coef raises the scorer's goals -> weaker defense; flip sign
                defense[name[len("C(opponent)[T."):-1]] = -float(val)

        self = cls(intercept=float(params["Intercept"]),
                   home_adv=float(params["is_home"]),
                   attack=attack, defense=defense, teams=set(teams))
        self.rho = self._estimate_rho(df)
        return self

    def _estimate_rho(self, df: pd.DataFrame) -> float:
        """MLE of the Dixon-Coles low-score correction on the fitted lambdas."""
        rows = [(r.home_team, r.away_team, int(r.home_score), int(r.away_score),
                 bool(r.neutral)) for r in df.itertuples()
                if r.home_team in self.teams and r.away_team in self.teams]

        def neg_ll(rho: float) -> float:
            ll = 0.0
            for h, a, hs, as_, neu in rows:
                lh, la = self.expected_goals(h, a, neu)
                tau = _dc_tau(min(hs, 2), min(as_, 2), lh, la, rho) if (hs <= 1 and as_ <= 1) else 1.0
                p = poisson.pmf(hs, lh) * poisson.pmf(as_, la) * max(tau, 1e-9)
                ll += np.log(max(p, 1e-12))
            return -ll

        res = minimize_scalar(neg_ll, bounds=(-0.2, 0.0), method="bounded")
        return float(res.x)

    # ---- prediction ----
    def expected_goals(self, home: str, away: str, neutral: bool = True) -> tuple[float, float]:
        lh = np.exp(self.intercept + self.attack.get(home, 0.0)
                    - self.defense.get(away, 0.0) + (0.0 if neutral else self.home_adv))
        la = np.exp(self.intercept + self.attack.get(away, 0.0)
                    - self.defense.get(home, 0.0))
        return float(lh), float(la)

    def forecast(self, home: str, away: str, neutral: bool = True) -> MatchForecast:
        lh, la = self.expected_goals(home, away, neutral)
        return forecast(lh, la, self.rho)

    def known(self, team: str) -> bool:
        return team in self.teams

    # ---- persistence ----
    def to_dict(self) -> dict:
        return {"intercept": self.intercept, "home_adv": self.home_adv, "rho": self.rho,
                "attack": self.attack, "defense": self.defense, "teams": sorted(self.teams)}

    def save(self, path) -> None:
        import json
        from pathlib import Path
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path) -> "DixonColesModel":
        import json
        from pathlib import Path
        d = json.loads(Path(path).read_text())
        return cls(intercept=d["intercept"], home_adv=d["home_adv"], rho=d["rho"],
                   attack=d["attack"], defense=d["defense"], teams=set(d["teams"]))
