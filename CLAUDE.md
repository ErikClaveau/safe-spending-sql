# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Text-to-SQL assistant over **synthetic** personal banking data (Postgres RLS isolation, traceable numbers, published eval harness). The repository is currently **design-only**: there is no source code, build, lint or test tooling yet, so there are no commands to run. Everything lives in `docs/` (written in Spanish; keep new docs/ADRs consistent with that unless the language decision in the plan §14 week 6 changes it).

Source of truth, in order:
- `docs/proyecto-1-asistente-gastos-final.md` — living project plan (goals, architecture, security, evals, ADR status table §12, changelog §18). Update its changelog and the ADR table whenever a decision changes.
- `docs/adr/` — ADR-001 (Postgres only), ADR-002 (isolation via RLS only), ADR-005 (semantic views layer). ADR-003/004/006/007/009/010 are still pending.
- `docs/generator-design.md` — synthetic data generator design.

## Architecture (planned)

Request flow: classify intent → generate SQL → static validation (sqlglot) → execute under RLS in a read-only transaction with timeout → synthesize answer → verify every number in the answer exists in the SQL result. Hexagonal design with ports: `LLMProvider`, `SQLGenerator`, `SQLValidator`, `QueryExecutor`, `SchemaProvider`, `TraceSink`, `Clock`. Stack: Python, FastAPI, PostgreSQL ≥ 15, sqlglot, Docker Compose, GitHub Actions.

## Invariants that must not be broken

- **Isolation is enforced only by Postgres RLS (ADR-002).** Generated SQL is never rewritten to add a user filter; sqlglot only validates (SELECT-only, allowlist of semantic views, `LIMIT` required, no dangerous functions).
- `user_id` comes from the API auth layer, never from the question or LLM output. The executor opens a read-only transaction, runs `set_config('app.user_id', %s, true)` (transaction-local), then runs the query as-is. The RLS policy uses `NULLIF(current_setting('app.user_id', true), '')::int`, so it fails closed (0 rows) when unset.
- Three DB roles: `app_owner` (migrations), `app_loader` (synthetic data load, `BYPASSRLS`, never used by the API), `app_reader` (only API role; SELECT only, no `BYPASSRLS`).
- **The LLM sees only the semantic views** `v_movimientos`, `v_gastos`, `v_ingresos` (Spanish names, `security_invoker = true`, none expose `user_id`); base tables are in English. Every non-internal transaction belongs to exactly one of `v_gastos`/`v_ingresos` (CI invariant). Docs for the LLM live in `COMMENT ON` (Spanish); the English data dictionary is `docs/data-dictionary.md`, verified in CI.
- Numbers in answers are always computed by SQL, never by the LLM. LLM-as-judge is used only for prose quality.
- The generator's output DB contains only what a real bank would have; archetypes, scenarios, traps and refund links go in separate label files (`tx_labels`, `user_labels`, `scenarios`) that are never loaded into the app DB. Generator = pure function (config + seed → Parquet + `manifest.json`), per-user/per-stage `SeedSequence` streams, frozen "today" = 2026-09-15 (via the `Clock` port). User id splits: 1–15 functional golden-set scenarios, 16–20 data-injection traps (canary words), 21–100 population.
- Synthetic data only — never real, own, or anonymized transactions.

## Eval targets (release gates)

Cross-user leak rate = 0 and successful injection (canary) rate = 0 on the adversarial set; 100% of answer numbers traceable to SQL results; execution accuracy ≥ 85% (to be re-set after the week-3 baseline). Planned CI: tests + smoke evals (~30 questions) + full adversarial set block merges.
