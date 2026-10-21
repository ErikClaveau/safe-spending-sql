# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Text-to-SQL assistant over **synthetic** personal banking data (Postgres RLS isolation, traceable numbers, published eval harness). The repository is in **week 2 of 6** (plan §14): the design is done and the database layer is being built. What exists:

- `docs/` — design, written in Spanish (keep new docs/ADRs in Spanish unless the language decision in the plan §14 week 6 changes it).
- `lab/rls/` — disposable RLS lab that validated ADR-002 (its own Postgres, own tests). Not part of the product.
- `src/safe_spending/db/` — the real database layer: `settings`, `bootstrap`, `config_checks`, `sqlfile` and the Alembic environment with migrations `0001` (base tables, RLS, grants) and `0002` (semantic views, `COMMENT ON`, sign `CHECK`).
- `src/safe_spending/generator/` — the synthetic data generator, slice 3 of 4 in progress (one archetype, recurring payments and card purchases, Parquet + manifest, and `scenarios/`: seven scripted scenarios for users 1-7; `traps/`: injection traps with canary words for the adversarial users 16-20; `fx/`: exchange-rate series and fee; refunds in `events/refunds.py`; `savings/`: the optional savings account and the transfers between a user's own accounts). `src/safe_spending/db/loader.py` loads it into Postgres as `app_loader`. `src/safe_spending/clock/` is the `Clock` port (`FixedClock`, `SystemClock`). `src/safe_spending/schemas/` (manifest contract) and `tables.py` (operational vs label table names) are shared by generator and loader on purpose: neither may import the other.
- `src/safe_spending/db/query.py` — `run_as_user`: runs a query as one user with the ADR-002 semantics (read-only transaction, `set_config` first, identity confirmed); the base of the week-3 `QueryExecutor`.
- `evals/golden/` and `src/safe_spending/evals/golden/` — the golden set v0 (90 Spanish questions with reference SQL) and its tooling; see `docs/golden-set.md`.
- `tests/db/`, `tests/generator/`, `tests/evals/` — tests of the real schema, the loader, the generator and the golden set.

Generator work still to do (design in `docs/generator-design.md`): all archetypes, calendar/holidays, regular Bizum, baseline foreign-currency purchases (rest of slice 3); statistical report and dataset card (slice 4). The reproducibility gate exists as a test (`dataset/manifest.json`); there is no CI runner yet. Not built yet: the adversarial sets, the rest of the 150-200 functional questions, the pipeline (LLM, sqlglot validator, executor, API) and CI.

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
uv run safe-spending-generate            # dataset -> data/dataset (Parquet + manifest.json; data/ is git-ignored)
uv run safe-spending-load --reset        # verify manifest, then load as app_loader (--reset empties the tables first)
uv run safe-spending-generate --update-reference-manifest   # after an intended data change: refresh dataset/manifest.json (bump dataset_version first)
uv run safe-spending-golden show GS-001 # run golden questions on a reference database built from scratch (also: refresh, check; --no-rebuild reuses it)

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
- **Generator rules:** amounts are integer cents, never `float`; every user and stage has its own `SeedSequence` stream (`generator/rng.py`: append new stages, never reorder), so adding a user or changing one stage never alters other data (tested); the pipeline never reads the system date (use the `Clock` port); `description_raw` uses its own stream; labels never go to Postgres (the loader only knows the five operational tables). Put generator resources in `generator/resources/`, not in a folder called `data/` (git-ignored).
- **Reproducibility gate:** the data is not in the repository, only the fingerprint of the official dataset (`dataset/manifest.json`: version, seed, configuration hash, and rows and SHA-256 of each Parquet file). `tests/generator/test_reference_manifest.py` regenerates the dataset and fails if any of it differs, so a change in the data is always a decision. After an intended change (generator code, config, a catalog or a dependency): bump `dataset_version` in `config.yaml`, run `uv run safe-spending-generate --update-reference-manifest`, then refresh the golden set (`dataset_version` in `golden_v0.yaml` and `safe-spending-golden refresh`). Byte-identical Parquet depends on the pinned pyarrow in `uv.lock`; if the hashes change on another machine without the data having changed, investigate before refreshing.
- **Scenarios** (`generator/scenarios/`): the user -> scenario map is fixed in `config.yaml` (validated: functional users only). An injector receives the user's baseline events and the `Stage.SCENARIOS` stream and returns the new event list plus a `scenarios` row whose `params` JSON is the ground truth by construction; events it adds or rewrites carry `scenario_id` into `tx_labels`. Scenarios that only remove data (recent sign-up, zero category) tag nothing. Users with a recent sign-up have short history on purpose, so invariants about full history (28 pays, savings rate) exclude them. Bump `dataset_version` whenever generated data changes.
- **Traps** (`generator/traps/`): users of the `eval_adversarial` split only. Each gets one incoming Bizum or transfer of every `TrapType` (plus 0-3 repeats) whose concept holds an injection text from `resources/traps.yaml` and a unique canary (`CNR` + 3-digit user id + 4 random chars; the user id makes cross-user clashes impossible). A trap is a real movement (counts in `v_ingresos`); its `tx_labels` row has `is_trap`, `trap_type` and `canary`. Concept limits (Bizum 35, transfer 140; the Bizum one is provisional) and the per-code statement limits live in `config.yaml`; the injector raises if a limit would cut a canary, and a test checks every template against the limits. Never put a canary in a template, a catalog or a doc: it must exist only in generated data.
- **Foreign currency and refunds:** `Event.amount_cents` is always the euro amount; a payment in another currency also carries `foreign` (currency, signed minor units, rate). **A rate is units of the currency per 1 EUR, applied on the operation (value) date: `amount_eur = amount / rate`**, rounded half to even (`money.convert_to_eur_cents`). The daily series (`fx/series.py`) has one stream per currency code (`stream(..., extra=...)`), so it depends neither on the other currencies nor on the end date. A foreign payment comes with a separate `FEE` movement (rate and minimum in `config.yaml`, no merchant). Foreign merchants (`currency: GBP`) are appended at the end of `merchants.yaml` so no existing id moves, and `Catalog.merchants_in` returns euro merchants unless asked otherwise, so they never enter anyone's habitual purchases. Refunds (`events/refunds.py`) draw four numbers per refundable purchase whatever the outcome, link to their purchase by `key`/`refund_of_key` (resolved to `tx_labels.refund_of_tx_id` in the pipeline), and `drop_orphan_refunds` removes any whose purchase a scenario dropped.
- **Savings and internal transfers** (`generator/savings/`): a user has one current account (`user_id * 10 + 1`) and, if they can afford to save and win the draw, a savings account (`user_id * 10 + 2`). A transfer is **two movements** of equal amount and opposite sign, one `TRANSFER_OUT` and one `TRANSFER_IN`, on the same day, each on one account and with `counterparty_account_id` pointing to the other (`Event.internal`, `Event.account`); they are the only movements the semantic views leave out of `v_gastos` and `v_ingresos`, so a test over generated data must expect `everything - gastos - ingresos == internal`. The plan is sized top-down from what the user can save (`savings_capacity_cents`), the monthly deposit follows each regular pay (not the extra ones) and a return is only possible from a balance, which is tracked so it never goes below zero. **Savings are built after the scenarios**, from the pays the user really has: building them before breaks the balance for a recent sign-up. It has its own stream (`Stage.SAVINGS`), so it changes no other movement. Invariants over income, spending or counts of `TRANSFER_OUT` must exclude `counterparty_account_id IS NOT NULL`.
- **Golden set** (`evals/golden/`): `golden_v0.yaml` is edited by hand; `expected_v0.json` is generated (`safe-spending-golden refresh`), never edited. Every reference SQL obeys the assistant's own rules (one SELECT, only the three semantic views, a LIMIT, no user filter) and spending is net (`v_gastos`, refunds negative). Before accepting a question, run `show` and read the result critically: a SQL that runs can still answer the wrong thing (a partial month, a period with no data, an empty result for the wrong reason). Answers are checked against the truth by a route that does not use the views (`scenarios.params` and the raw generated movements): a disagreement is a semantic-layer or SQL bug, not an assistant bug. Changing the generator or its config means bumping `dataset_version` in `config.yaml` and `golden_v0.yaml` and refreshing the expected file. The reference database (`safe_spending_golden`, tests use `safe_spending_golden_test`) is built from scratch by `evals/golden/dataset.py`, so answers never depend on the development database.
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
