# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Text-to-SQL assistant over **synthetic** personal banking data (Postgres RLS isolation, traceable numbers, published eval harness). The repository is in **week 2 of 6** (plan §14): the design is done and the database layer is being built. What exists:

- `docs/` — design, written in Spanish (keep new docs/ADRs in Spanish unless the language decision in the plan §14 week 6 changes it).
- `lab/rls/` — disposable RLS lab that validated ADR-002 (its own Postgres, own tests). Not part of the product.
- `src/safe_spending/db/` — the real database layer: `settings`, `bootstrap`, `config_checks`, `sqlfile` and the Alembic environment with migrations `0001` (base tables, RLS, grants) and `0002` (semantic views, `COMMENT ON`, sign `CHECK`).
- `tests/db/` — tests of the real schema.

Not built yet: the data generator and loader, the golden set, the pipeline (LLM, sqlglot, executor, API) and CI.

Code, comments and test names are in **English**; `docs/` and the Spanish semantic layer (view/column names, `COMMENT ON` for the LLM) are in Spanish.

Source of truth, in order:
- `docs/proyecto-1-asistente-gastos-final.md` — living project plan (goals, architecture, security, evals, ADR status table §12, changelog §18). Update its changelog and the ADR table whenever a decision changes.
- `docs/adr/` — ADR-001 (Postgres only), ADR-002 (isolation via RLS only, **accepted**, with lab results), ADR-005 (semantic views layer). ADR-003/004/006/007/008/009/010 are still pending.
- `docs/generator-design.md` — synthetic data generator design.

## Commands

Requires Docker and `uv`. Run from the repo root.

```bash
uv sync                                  # install the project (editable) and dev deps
docker compose up -d --wait              # development Postgres
uv run safe-spending-bootstrap           # database, roles and empty schema (idempotent)
uv run alembic upgrade head              # apply migrations as app_owner
uv run pytest                            # real suite in tests/ (uses database safe_spending_test)
uv run pytest tests/db/test_migrations.py::test_downgrade_and_upgrade_round_trip   # one test

docker compose -f lab/rls/docker-compose.yml up -d --wait   # RLS lab Postgres
uv run pytest lab/rls/tests              # lab suite (separate Postgres; not run by plain `pytest`)
```

Connection settings come from env vars with development defaults (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_ADMIN_USER`, `DB_ADMIN_PASSWORD`, `DB_<ROLE>_PASSWORD`); see `src/safe_spending/db/settings.py`. The dev and lab compose files must not publish the same host port: check `DB_PORT` before running the real suite, or it can hit the lab's Postgres and alter its roles (same role names).

## Database conventions

- **Migrations are hand-written SQL run through Alembic** (no SQLAlchemy models, no autogenerate: it cannot express RLS, policies, `security_invoker` views or `COMMENT ON`). Each revision in `src/safe_spending/db/alembic/versions/` calls `run_sql_file("NNNN_name.sql")` and its `.down.sql`; the SQL lives in `src/safe_spending/db/alembic/sql/`. Migrations run as `app_owner` with `search_path = app`.
- **Roles and the empty schema are created by `bootstrap`, not by migrations** (roles are cluster-level and need the superuser). Never connect as `postgres` in tests or app code, except `bootstrap` and test cleanup: a superuser bypasses RLS, so a test run as it proves nothing.
- Every new table with user data needs a `user_id` column, `ENABLE` + `FORCE ROW LEVEL SECURITY` and an `aislamiento_usuario` policy `TO app_reader` (same shape as in `0001`). `config_checks` discovers tables by the `user_id` column and views by schema, and `tests/db/test_schema_config.py` fails if any is missing a policy, `FORCE` or `security_invoker`.
- Grants are explicit per table (no default privileges). `app_reader` needs `SELECT` on base tables because views are `security_invoker`; the sqlglot allowlist, not `GRANT`s, keeps the LLM on the views.
- The sign of `amount_eur` is fixed by `tx_code` (`CHECK`), which is what makes every non-internal movement fall in exactly one of `v_gastos`/`v_ingresos`; the generator must respect it. Every column of every semantic view must be in `docs/data-dictionary.md` (test-enforced, both ways) and have a `COMMENT ON`.
- Tests that break the configuration on purpose use the `remigrate` fixture, which drops the whole `app` schema and migrates again (a downgrade alone leaves objects added outside migrations).

## Architecture (planned)

Request flow: classify intent → generate SQL → static validation (sqlglot) → execute under RLS in a read-only transaction with timeout → synthesize answer → verify every number in the answer exists in the SQL result. Hexagonal design with ports: `LLMProvider`, `SQLGenerator`, `SQLValidator`, `QueryExecutor`, `SchemaProvider`, `TraceSink`, `Clock`. Stack: Python, FastAPI, PostgreSQL ≥ 15, sqlglot, Docker Compose, GitHub Actions.

## Invariants that must not be broken

- **Isolation is enforced only by Postgres RLS (ADR-002).** Generated SQL is never rewritten to add a user filter; sqlglot only validates (SELECT-only, allowlist of semantic views, `LIMIT` required, no dangerous functions, **no `SET`**).
- `user_id` comes from the API auth layer, never from the question or LLM output. The executor opens an explicit `BEGIN READ ONLY`, runs `set_config('app.user_id', %s, true)` (transaction-local) as its first statement, then runs the query as-is. The RLS policy uses `NULLIF(current_setting('app.user_id', true), '')::int`, so it fails closed (0 rows) when unset.
- **Write protection comes from the `GRANT`s** (`app_reader` has only `SELECT`), not from read-only mode: the lab showed `app_reader` can leave read-only mode before the first query and can reset `default_transaction_read_only` for its session. Read-only mode is a second layer; the executor's `set_config` first statement locks it for the real flow.
- `FORCE ROW LEVEL SECURITY` and `security_invoker` are independent layers; keep both.
- Three DB roles: `app_owner` (migrations), `app_loader` (synthetic data load, `BYPASSRLS`, never used by the API), `app_reader` (only API role; SELECT only, no `BYPASSRLS`).
- **The LLM sees only the semantic views** `v_movimientos`, `v_gastos`, `v_ingresos` (Spanish names, `security_invoker = true`, none expose `user_id`); base tables are in English. Every non-internal transaction belongs to exactly one of `v_gastos`/`v_ingresos` (CI invariant). Docs for the LLM live in `COMMENT ON` (Spanish); the English data dictionary is `docs/data-dictionary.md`, verified in CI.
- Numbers in answers are always computed by SQL, never by the LLM. LLM-as-judge is used only for prose quality.
- The generator's output DB contains only what a real bank would have; archetypes, scenarios, traps and refund links go in separate label files (`tx_labels`, `user_labels`, `scenarios`) that are never loaded into the app DB. Generator = pure function (config + seed → Parquet + `manifest.json`), per-user/per-stage `SeedSequence` streams, frozen "today" = 2026-09-15 (via the `Clock` port). User id splits: 1–15 functional golden-set scenarios, 16–20 data-injection traps (canary words), 21–100 population.
- Synthetic data only — never real, own, or anonymized transactions.

## Eval targets (release gates)

Cross-user leak rate = 0 and successful injection (canary) rate = 0 on the adversarial set; 100% of answer numbers traceable to SQL results; execution accuracy ≥ 85% (to be re-set after the week-3 baseline). Planned CI: tests + smoke evals (~30 questions) + full adversarial set block merges.
