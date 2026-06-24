# World Cup 2026 Predictor

A quant-style match predictor for the 2026 FIFA World Cup. It outputs **win /
draw / loss probabilities and a full score distribution** for any fixture, is
scored with a **proper scoring rule** (Ranked Probability Score), and is
benchmarked against an Elo model and the naive base rate. The dashboard predicts
the **upcoming group-stage fixtures** and keeps an honest, **out-of-sample track
record** against the games already played.

> **It works today.** The data pipeline, time-weighted Dixon-Coles model, backtest,
> and dashboard are all live. On the 48 group games played so far it called
> **62.5% correctly out-of-sample**, beating both baselines on RPS. Full quant
> roadmap (feature blend, tournament Monte Carlo) in **[`docs/PLAN.md`](docs/PLAN.md)**.

## The model

Each nation gets a latent **attack** and **defense** strength, fit by
**time-weighted Poisson regression** (exponential half-life so recent form
dominates) with a home-advantage term and the **Dixon-Coles low-score
correlation** ρ estimated by maximum likelihood:

```
log λ_home = μ + home_adv·(not neutral) + attack_home − defense_away
log λ_away = μ                          + attack_away − defense_home
```

The fitted λ's give the full `P(home=i, away=j)` score matrix, from which every
market (1X2, correct score, over/under, both-teams-to-score) follows.

## Backtest (out-of-sample, RPS — lower is better)

Each window refits using only matches *before* the tournament, then predicts it.

| Tournament | Matches | Model | Elo | Naive | Outcome acc |
|---|---|:---:|:---:|:---:|:---:|
| World Cup 2022 | 64 | **0.214** | 0.216 | 0.236 | 53% |
| World Cup 2026 (group stage so far) | 48 | **0.155** | 0.173 | 0.206 | **62%** |
| **Pooled** | 112 | **0.189** | 0.197 | 0.223 | 57% |

The model beats both baselines on RPS in every window. (Numbers regenerate into
`models/metrics.json` whenever you retrain.)

## Stack

- **Python 3.12** — pandas / NumPy / SciPy / **statsmodels** (the Poisson GLM)
- **Modeling** — time-weighted Dixon-Coles bivariate Poisson + from-scratch Elo
- **Flask** — dashboard API + vanilla-JS frontend
- **Data** — [martj42 international results](https://github.com/martj42/international_results)
  (~49k matches, no auth) + penalty-shootout history
- **Deploy** — Render (`render.yaml`)

## Run

```bash
cd worldcup-2026-predictor
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python data/ingest.py     # pull results + shootouts -> data/matches.parquet
python scripts/train.py   # fit model, backtest, write models/*.json   (~30s)
python app.py             # -> http://localhost:8000
```

The dashboard has three tabs:
- **Upcoming fixtures** — every remaining group match, predicted by the full model
- **Track record** — games already played, scored by the *pre-tournament* model
  (a fair out-of-sample test) vs the actual result, with a running hit rate
- **Match lab** — pick any two nations for a full forecast

## Project structure

```
worldcup-2026-predictor/
├── app.py                 # Flask dashboard API
├── data/ingest.py         # public CSV sources -> data/matches.parquet
├── wc2026/
│   ├── dixon_coles.py     # time-weighted Dixon-Coles model        [implemented]
│   ├── ratings.py         # Elo team strength + fallback           [implemented]
│   ├── fixtures.py        # group reconstruction + upcoming games  [implemented]
│   ├── backtest.py        # walk-forward RPS vs baselines          [implemented]
│   ├── features.py        # extra pre-match features               [roadmap]
│   ├── model.py           # GBM feature blend                      [roadmap]
│   └── simulate.py        # tournament Monte Carlo                  [roadmap]
├── scripts/train.py       # fit + backtest + write models/*.json
├── models/                # committed artifacts so the app runs out of the box
├── static/                # vanilla-JS dashboard
├── docs/PLAN.md           # full quant strategy
└── render.yaml
```

## Honesty notes

Every headline number is from an **out-of-sample backtest** shown next to its
baselines — never the training fit. The track-record tab specifically uses a model
trained *before* those matches. **Not** modeled: injuries, red cards, and
in-tournament squad changes. Groups are *reconstructed* from played fixtures, so
group letters are inferred, not official.
