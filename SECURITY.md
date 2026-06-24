# Security Policy

This is a personal data-science project. It trains on public datasets and serves
read-only predictions; it stores no user data and requires no secrets to run.

## Reporting a vulnerability

If you find a security issue (for example in the Flask app or a dependency),
please email **njjohnson1@mail.lipscomb.edu** rather than opening a public issue.
I'll acknowledge within a few days.

## Scope notes

- The base pipeline uses only public, no-auth CSV sources.
- Any optional API keys (e.g. an odds provider) belong in `.env`, which is
  gitignored — never commit real keys.
