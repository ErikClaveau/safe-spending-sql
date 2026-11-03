# ADR-005: The LLM queries only a semantic layer of movement-level views

> 🇪🇸 Español: [../es/adr/0005-capa-semantica.md](../es/adr/0005-capa-semantica.md)

**Status:** Accepted (amended on 2026-10-03, see "Amendments")
**Date:** 2026-10-01
**Decides:** Erik Claveau
**Related:** ADR-001 (PostgreSQL), ADR-002 (isolation with RLS), ADR-008 (dates and currencies)

## Context

In text-to-SQL, a good part of the errors are not syntactic but semantic: summing without taking the sign into account, forgetting to subtract refunds, mixing currencies, counting transfers between own accounts as spending or inventing a category name. If the LLM queries the base tables, it has to get those business rules right on every query. And a semantic error produces a plausible but wrong figure, which is the worst possible failure in a financial assistant.

Inherited constraints:

- **ADR-002.** Isolation is imposed by RLS and the LLM does not know the `user_id`. The views must use `security_invoker = true`, which requires `app_reader` to have `SELECT` on the base tables.
- **Audience.** Questions arrive in Spanish, but the repository must be understandable to English readers.
- **Methodology.** The main metric is execution accuracy, and the project follows an improvement methodology guided by error analysis.

## Decision

### 1. Views only

The LLM works exclusively on a semantic layer of views. The base tables are not described to it and it cannot reference them. The restriction is imposed as follows:

- The `SchemaProvider` describes only the semantic views.
- The validator (sqlglot) rejects any query that references an object outside the view allowlist. sqlglot **only validates, never rewrites** the SQL (ADR-002).
- `app_reader` keeps `SELECT` on the base tables because `security_invoker` requires it. The restriction to views is **not** imposed by the `GRANT`s.

If the validator failed and a query on a base table got to run, RLS would still filter by user. The impact would be on answer quality, not on isolation.

### 2. Movement-level granularity

All the initial views have one row per movement. No aggregate views (for example, monthly spending by category) are created unless error analysis shows a recurring failure category that an aggregate view would solve. Every view that is added must come with the metric that justifies it.

### 3. Three views with explicit sign conventions

| View | Contents | Amount column | Convention |
|---|---|---|---|
| `v_movimientos` | All movements | `importe_eur` | Natural sign: negative goes out, positive comes in |
| `v_gastos` | All non-internal debits (purchases, direct debits, fees, Bizum and transfers sent, cash withdrawals) and refunds | `gasto_eur` | Positive for spending and negative for refunds; `SUM(gasto_eur)` is net spending |
| `v_ingresos` | All non-internal credits except refunds (pay, Bizum and transfers received, other income) | `ingreso_eur` | Positive |

- Transfers between own accounts (`counterparty_account_id` set) are the only movements excluded from `v_gastos` and `v_ingresos`.
- **Invariant:** every non-internal movement belongs to exactly one of the two views. Therefore `SUM(ingreso_eur) - SUM(gasto_eur)` equals the real change in balance. Verified with a SQL test.
- The amount column has a different name in each view so that the sign convention can be read in the name itself and is not confused when combining views.

### 4. Language: tables in English, views in Spanish

- **Base tables in English** (engineering layer, aligned with NextGenPSD2 names).
- **Semantic views and columns in Spanish** (product layer, in the language of the questions). The views also work as a translation layer.
- **Data dictionary in English** in `docs/data-dictionary.md`, with each view and column, its type and its meaning. A CI test checks that every column of the semantic views appears in the dictionary.

Planned columns (initial version, adjustable after error analysis):

| Column | Meaning |
|---|---|
| `id_movimiento` | Movement identifier; needed for traceability and numeric verification |
| `fecha` | Movement date: the charge date (ADR-008) |
| `importe_eur` / `gasto_eur` / `ingreso_eur` | Amount in euros according to each view's convention |
| `importe_original`, `divisa_original` | The operation's original amount and currency (all accounts are in euros) |
| `categoria`, `grupo_categoria` | Category and group, with values from a closed list |
| `comercio` | Normalised merchant name (companies only) |
| `contraparte` | Payer or payee as it appears in the movement (includes people in Bizum and transfers) |
| `concepto` | Original concept (`description_raw`); **untrusted** text |
| `medio_pago` | Card, direct debit, transfer, Bizum, etc. |
| `cuenta` | Masked IBAN of the account, derived from the full synthetic IBAN in `accounts` |

No view exposes `user_id` (ADR-002).

### 5. Schema description for the LLM

- The documentation lives in the database, with `COMMENT ON VIEW` and `COMMENT ON COLUMN` in Spanish, versioned in the migrations.
- The `SchemaProvider` obtains it by introspection, so the description and the real schema cannot diverge.
- The `SchemaProvider` includes the **closed list of values** of `categoria` and `grupo_categoria`, to avoid filters with invented names that return 0 rows without an error.
- Each evaluation experiment records the **semantic schema version** next to the commit, model, prompt and dataset version.

## Options considered

### Option A: The LLM queries the base tables

**Pros:** maximum flexibility; no extra layer to maintain.

**Cons:** the LLM has to resolve signs, refunds, currencies and internal transfers on every query; more joins, more surface for error and silent semantic errors.

### Option B: Semantic views only (chosen)

**Pros:** business rules are resolved once and tested; a smaller schema in the language of the questions; better schema linking.

**Cons:** the views must be maintained; a question the views do not cover cannot be answered until they are extended.

### Option C: Mixed (views and tables)

**Rejected.** It gives the model two ways to answer the same thing, and it will tend to choose the wrong one precisely in the hard cases.

### Alternatives rejected within option B

- **A single `v_movimientos` view with a type column.** A simpler schema, but it hands back to the LLM the responsibility of filtering and applying the signs correctly on every query.
- **Aggregate views from the start.** They limit the answerable questions (filters by day, amount or payment method do not fit a monthly aggregate) and open the door to double counting when combined with detail views. Postponed until error analysis justifies them.
- **Views with the owner's permissions (no `security_invoker`) to impose "views only" through `GRANT`s.** It would require redesigning ADR-002's RLS policies to apply to the views' owner. It adds no isolation, because a query on base tables is also protected by RLS.

## Trade-off analysis

The semantic layer moves complexity from the LLM to SQL written and tested by a person. That exchange is favourable because the error it avoids, a plausible but wrong figure, is hard for the user to detect and is exactly what the project wants to eliminate. The cost is a loss of flexibility for unforeseen questions, and it is managed with the error analysis cycle: if a category of questions fails for lack of coverage, the semantic layer is extended and the effect measured.

## Consequences

**Easier**
- The most frequent questions reduce to simple aggregations over one view.
- Business rules are tested with SQL tests independent of the LLM.
- An English reader understands the tables directly and the views through the dictionary.

**Harder**
- The views, their comments and the dictionary must be kept in sync (the latter verified in CI).
- The data generator must produce the information needed to classify each movement: operation type, refunds linked to their purchase and identifiable internal transfers.

**To revisit**
- **ADR-008 (done):** `fecha` is the charge date and the conversion to euros uses the rate of the operation date.
- **Week 4 (done):** the sqlglot allowlist includes exactly the semantic views, and **functions** go from a blocklist to an allowlist (`allowed_functions.py`). A blocklist stopped `dblink` and not `dblink_exec`, and let `query_to_xml('SELECT …')` through, which runs text as SQL and skips the views. Of 50 direct attacks, 34 got through; now 11 do, all harmless or bounded by the timeout and the row cap. The 444 statements the model actually wrote in the logs still pass.
- **Week 6:** language of the README and the ADRs for English readers (done: English first, with a Spanish mirror in `docs/es/`).

## Next steps

1. [x] Rename the base-table columns to English in the data model (migration `0001`).
2. [x] Implement `v_movimientos`, `v_gastos` and `v_ingresos` with `security_invoker = true` and their `COMMENT ON` (migration `0002`, 2026-10-06).
3. [x] SQL tests of the business rules: refunds subtract, internal transfers excluded, invariant of belonging to exactly one view and conversion to euros (`tests/db/test_semantic_views.py`).
4. [x] Create `docs/data-dictionary.md` and the CI test that verifies that all columns are documented (both ways: nothing undocumented and nothing documented that no longer exists).
5. [ ] Implement the `SchemaProvider` by introspection, with the closed category lists.
6. [ ] Add the semantic schema version to the experiment metadata and the traces.

## Amendments

### 2026-10-03: complete classification of non-internal movements

While designing the generator's category taxonomy an ambiguity was found: if received Bizum counted as income but sent ones did not count as spending, the question "how much did I save?" gave a wrong result. It is agreed:

- `v_gastos` includes all non-internal debits, also Bizum and transfers to third parties and cash withdrawals, plus refunds with negative sign.
- `v_ingresos` includes all non-internal credits except refunds.
- Internal transfers are identified by `counterparty_account_id` and are the only movements outside both views.
- The invariant of belonging to exactly one view is added, verified in CI.

### 2026-10-06: implementation decisions of migration `0002`

- **The sign of `amount_eur` is fixed by the operation type**, with a `CHECK` constraint on `transactions` (`transactions_sign_matches_tx_code`): `CARD_PURCHASE`, `DIRECT_DEBIT`, `TRANSFER_OUT`, `BIZUM_OUT`, `FEE` and `ATM_WITHDRAWAL` are negative; `CARD_REFUND`, `TRANSFER_IN`, `BIZUM_IN` and `SALARY` are positive; zero is impossible. This is what guarantees in the database that every non-internal movement falls in exactly one view. The generator must respect it.
- **`v_gastos` and `v_ingresos` carry `gasto_original` and `ingreso_original`** (with the same sign convention as their euro column) instead of `importe_original`, so that the sign convention can still be read in the name of each amount column. `v_movimientos` keeps `importe_original` with natural sign.
- **`medio_pago`** is computed with the function `medio_pago_de(tx_code)`, the single source for the three views. `app_reader` only has `EXECUTE` on it.
- **`cuenta`** shows the country code, asterisks and the last 4 digits of the IBAN.
- **`fecha`** is `booking_date` (ADR-008).
