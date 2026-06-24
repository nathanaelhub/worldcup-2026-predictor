"""World Cup 2026 predictor — modeling package.

Layers (see docs/PLAN.md):
    ratings.py     Elo team-strength prior (implemented)
    dixon_coles.py Bivariate-Poisson / Dixon-Coles score model (core implemented; fit = TODO)
    features.py    Pre-match feature engineering (TODO)
    model.py       Outcome + score model wrapper / blend (TODO)
    backtest.py    Walk-forward evaluation, RPS, calibration, betting ROI (RPS implemented)
    simulate.py    Monte Carlo tournament simulation (TODO)
"""
__version__ = "0.1.0"
