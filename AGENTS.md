# AGENTS.md

All project rules for AI coding agents (Codex and others) live in **[CLAUDE.md](CLAUDE.md)**.
Read it fully before making any change. It is the single source of truth, and this file intentionally contains no rules of its own.

Key points, for orientation only (CLAUDE.md wins on any difference):

- Plan first, wait for the owner's approval, then code. One branch and PR per task. No automatic merging to `main`.
- Decisions are recorded in `docs/suunnitelma.md` (decision register). Do not silently override an approved decision.
- Money is stored as integers (`*_cents`, `*_e4`) and calculated with `Decimal`. Never use float for money.
- **No employer information, ever:** nothing about the owner's current or former employers (names, systems, internal terms, customers, routes, prices, processes, screenshots, data) in code, data, docs, commits, PRs or issues.
- Demo data only: every company and person name is fictional and contains "Demo".
