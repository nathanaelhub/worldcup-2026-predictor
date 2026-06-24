# World Cup 2026 Predictor — Quant Strategy

This document is the technical plan for a match-prediction system for the 2026
FIFA World Cup. The bar is deliberately set at "quant desk", not "Kaggle demo":
every model is scored with a **proper scoring rule**, every result is measured
against the **bookmaker closing line** (the market we're trying to beat), and the
headline deliverable is a **calibrated probability**, not a single guessed score.

---

## 1. What we predict

For any match between two national teams we output:

1. **Outcome probabilities** — `P(home win)`, `P(draw)`, `P(away win)`.
   In knockout rounds, also `P(advance)` after extra time + penalties.
2. **A full score distribution** — `P(home goals = i, away goals = j)` for all
   `i, j`, from which we derive the most likely scoreline, expected goals,
   over/under 2.5, both-teams-to-score, and clean-sheet probabilities.
3. **Tournament probabilities** — via Monte Carlo simulation of the whole
   bracket: each team's chance to escape the group, reach each round, and lift
   the trophy.

The single guessed scoreline that a casual predictor cares about is just the
mode of (2). We treat the distribution as the real output.

---

## 2. Modeling approach

We build up in layers so every layer has a baseline to beat.

### Layer 0 — Ratings (the prior)
- **World Football Elo** as a strong, well-understood team-strength prior.
- A from-scratch Elo re-implementation (so the ratings are reproducible, not
  scraped magic) with goal-difference-weighted updates and tournament-importance
  K-factors, validated to within a few points of eloratings.net.
- FIFA ranking and (optionally) squad market value as auxiliary strength signals.

### Layer 1 — Bivariate Poisson / Dixon-Coles (the core)
The workhorse of football modeling. Each team `t` has a latent **attack** `α_t`
and **defense** `β_t`. Expected goals:

```
log λ_home = μ + home_adv + α_home − β_away
log λ_away = μ          + α_away − β_home
```

Goals are modeled as (near-)independent Poisson, with the **Dixon-Coles τ
correction** that inflates/deflates the four low-score cells (0-0, 1-0, 0-1, 1-1)
to fix the known independence failure at low scores. Matches are **time-weighted**
(exponential half-life ~2 years) so recent form dominates and 1990s results barely
count. Parameters fit by weighted maximum likelihood.

This yields the entire `P(i, j)` score matrix in closed form → every derived
market (1X2, correct score, O/U, BTTS) is just a sum over cells.

### Layer 2 — Feature model + blend
A gradient-boosted model (or Bayesian hierarchical bivariate Poisson in PyMC for
the "show-off" version) on engineered features:
- Elo difference, FIFA-rank difference, recent form (rolling goals for/against,
  points), rest days, travel, **host advantage** (2026 is co-hosted by USA /
  Canada / Mexico — a real, codable edge), confederation, tournament importance,
  squad value, set-piece/xG priors where available.

The feature model and the Dixon-Coles model are **blended** (logarithmic opinion
pool, weight tuned on validation RPS). Blending two decent-but-different models
almost always beats either alone.

### Knockouts
Group stage allows draws; knockouts don't. We model 90-minute goals with the
score matrix, then handle a tie as: extra-time goals (scaled-down λ) → penalty
shootout (calibrated ~coin-flip with a small favourite edge estimated from the
`shootouts.csv` history).

---

## 3. Data

| Source | What it gives | Access |
|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | Every international match 1872–present (scores, tournament, venue, neutral flag) | Public CSV, no auth |
| ↳ `shootouts.csv` | Penalty-shootout winners | Public CSV |
| ↳ `goalscorers.csv` | Goal-level data (timing, penalties) | Public CSV |
| World Football Elo (eloratings.net) | Team strength ratings | Snapshot / re-implemented |
| FIFA / Elo rankings | Auxiliary strength feature | Public |
| Closing bookmaker odds (e.g. football-data.co.uk, odds API) | **Evaluation benchmark** | Public / API |
| Transfermarkt squad market values | Strong strength feature | Optional scrape |

The base results file alone is **~49,000 matches through mid-2026**, which is
plenty to fit team ratings and validate on past tournaments. Everything else is
enrichment.

---

## 4. Validation — the part that makes it quant

No random k-fold. Football is a time series; we only ever predict the future.

- **Walk-forward backtest.** Re-fit ratings/model using only matches *before*
  each target date and predict forward. Evaluate specifically on the **2014,
  2018, 2022 World Cups** and recent **Euros / Copa América** (out-of-sample
  tournaments the model never trained on).
- **Primary metric: Ranked Probability Score (RPS).** The standard proper
  scoring rule for ordered 1X2 football forecasts (Constantinou & Fenton 2012) —
  it rewards getting the *probabilities* right, not just the winner, and respects
  the ordering home > draw > away. Lower is better.
- **Supporting metrics:** multiclass log loss, Brier score, **calibration /
  reliability curves** (a forecast of 60% should win ~60% of the time), exact-score
  hit rate, and "correct result" rate.
- **The real benchmark is the market.** We de-vig bookmaker closing odds into
  probabilities and compare our RPS to the closing line's RPS. Beating the closing
  line is the football analogue of generating alpha — most public models do *not*,
  and being honest about that is the point.
- **Betting-style evaluation.** Simulate flat-stake and fractional-Kelly staking
  against historical closing odds; report ROI / yield, hit rate, max drawdown, and
  a Sharpe-like ratio. This reframes "is the model good?" as "does it have edge vs
  a real market?" — the quant framing.

A model that loses to the closing line but beats Elo is still a *good portfolio
result* as long as we say so plainly.

---

## 5. Tournament simulation

Monte Carlo (50k+ runs) of the full 2026 format (48 teams, 12 groups of 4, then
a 32-team knockout):
- Simulate every group match → apply real FIFA tie-breakers → seed the bracket.
- Simulate knockouts with the extra-time/penalty logic above.
- Aggregate: each team's `P(advance from group)`, `P(reach QF/SF/final)`,
  `P(win the cup)`, plus the most likely bracket and "Cinderella" upset odds.

This is the flagship, shareable artifact (a probability table / bracket viz).

---

## 6. Deliverable surface

A small Flask app (same family as the fraud-detection project):
- Pick two teams + context (group vs knockout, neutral/host) → predicted score
  distribution, 1X2 probabilities, most likely scorelines, and a confidence read.
- A tournament-simulator view showing each team's title odds.
- An honest model card: data window, model, backtested RPS vs the closing line.

---

## 7. Build milestones

| # | Milestone | Output |
|---|---|---|
| M0 | **Data layer** | `data/ingest.py` pulls results + shootouts + ratings → tidy `matches.parquet` |
| M1 | **Baselines** | Elo-only and plain Poisson; RPS measured vs bookmaker line |
| M2 | **Dixon-Coles core** | Time-weighted bivariate Poisson + τ; full score matrices; calibration curves |
| M3 | **Features + blend** | Gradient-boosted feature model, log-pool blend, tuned on val RPS |
| M4 | **Walk-forward backtest** | RPS / log loss / ROI vs closing odds across 2014/18/22 WCs + Euros/Copa |
| M5 | **Tournament sim** | Monte Carlo bracket → per-team title probabilities |
| M6 | **App + deploy** | Flask UI + Render deploy, honest model card |

---

## 8. Honesty guardrails (lessons from the F1 project)

- Every headline number comes from an **out-of-sample backtest**, never the
  training fit, and is always shown next to a **baseline** (Elo and the bookmaker
  line).
- The README states plainly what's modeled vs not (e.g. injuries, red cards, and
  in-tournament squad morale are *not* modeled).
- No fabricated accuracy. If the model can't beat the closing line, the README
  says so — that's still a legitimate, interesting result.
