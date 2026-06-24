# Data sources

| Source | File(s) | What it provides | Auth |
|---|---|---|---|
| [martj42/international_results](https://github.com/martj42/international_results) | `results.csv` | Every men's international 1872–present: teams, score, tournament, venue, neutral flag (~49k matches) | None |
| ↳ same repo | `shootouts.csv` | Penalty-shootout winners — needed to model knockout tie-breaks | None |
| ↳ same repo | `goalscorers.csv` | Goal-level data (minute, penalty flag) for future enrichment | None |
| World Football Elo (eloratings.net) | — | Team strength ratings; re-implemented in `wc2026/ratings.py` for reproducibility | None |
| Closing bookmaker odds (e.g. football-data.co.uk, an odds API) | — | **Evaluation benchmark** — de-vigged into the closing-line probabilities we measure RPS against | Public / API key |
| Transfermarkt | — | Squad market values (optional strength feature) | Scrape |

`data/ingest.py` pulls the first two automatically and caches them under
`data/raw/`. Everything else is optional enrichment described in
[`PLAN.md`](./PLAN.md).

## Notes / caveats

- Team names drift over time (e.g. historical name changes); the source ships a
  `former_names.csv` to normalize. Reconcile before joining external ratings.
- International data is sparse per team vs club football — partial pooling of
  team ratings matters (PLAN.md §2).
- The 2026 hosts (USA, Canada, Mexico) get a real home-advantage term; everyone
  else plays effectively neutral.
