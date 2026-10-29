# Golden set v0

> 🇪🇸 Español: [es/golden-set.md](es/golden-set.md)

The golden set is the specification of what the assistant must be able to answer: questions in Spanish about the evaluation users, each with the SQL that gives the right answer over the semantic views. It is the base of the *execution accuracy* metric (plan §9) and of the week 3 baseline.

## Where it is

| File | Contents |
|---|---|
| `evals/golden/golden_v0.yaml` | The questions. Edited by hand. |
| `evals/golden/expected_v0.json` | The expected answer of each question with SQL. **Generated, never edited by hand.** |
| `src/safe_spending/evals/golden/` | Models, SQL rules, result comparison and the command. |
| `tests/evals/` | The tests that watch over it. |

## Composition (v0, dataset 0.5.0)

152 questions, 144 with reference SQL, all about the functional users 1-15. The first 90 are the original v0; GS-091 to GS-114 (week 5) are 24 more on recurring payments, written with a concrete figure, date or name and the period in view; GS-115 to GS-133 are 19 of compound filters (amount, weekday, merchant and period at once); GS-134 to GS-152 are 19 of income versus spending (surplus, savings, averages and percentages).

| Category | Questions | Expected behaviour |
|---|---|---|
| Simple aggregate | 17 | SQL and one figure (including real zeros) |
| Temporal comparison | 9 | SQL with two periods |
| Ranking | 8 | SQL with `ORDER BY` and `LIMIT` |
| Compound filter | 27 | SQL with several filters |
| Income versus spending | 28 | Signed aggregate, combining the two views |
| Recurring | 33 | Subscriptions, direct debits, rent and pay |
| Currency | 6 | Payments in pounds, fee and exchange rate (user 6) |
| Refunds | 7 | Purchases minus refunds (user 7 and the population) |
| Transfers between own accounts | 5 | That count neither as spending nor as income |
| Ambiguous | 4 | `clarify`: ask for clarification or state the assumption |
| No data | 4 | `no_data`: say there is no data, without inventing |
| Out of domain | 4 | `refuse`: polite refusal |

Difficulty: 36 easy, 89 medium and 27 hard. 36 questions are anchored to one of the seven scripted scenarios. Users 1-7 have a scenario (subscriptions, job change, recent sign-up, zeroed category, anomalous month, London and Amazon) and 8-15 are ordinary users; those with a savings account are used for the transfers.

Left out of v0, and work for the following weeks: the adversarial set (isolation and data with canaries, week 4) and reaching the 150-200 functional questions of the plan.

## Conventions

- **Net spending.** "I spent" is `v_gastos.gasto_eur`, where refunds count as negative (ADR-005).
- **"Today" is 2026-09-15.** "This year" is 2026, "last month" is August 2026, "this quarter" runs from July to today (partial) and "the previous quarter" is April-June 2026.
- **Periods** are written as `fecha >= first day AND fecha < day after the last`.
- **`fecha` is the charge date.** Which date the view exposes is settled by ADR-008.
- **Transfers between own accounts are neither spending nor income.** They only appear in `v_movimientos`.
- **€0 is not "no data".** A period with movements but no spending in a category gives 0; a period with no movements at all has no data.
- **The reference SQL obeys the same rules as the assistant:** a single `SELECT` statement, only `v_movimientos`, `v_gastos` or `v_ingresos`, with `LIMIT`, never filtering by user (isolation is RLS's job) and with no dangerous functions.

## Dev / test split

Improving prompts and documentation against the same questions used to measure raises the figure by fitting those questions. So 47 of the 152 (`evals/golden/splits_v0.yaml`) are **test**: they are scored every round and published with the rest, but no change is decided on a test question. The remaining 105 are **dev**. The original 26 have not moved: the 21 test questions added in week 5 (GS-093, 096, 099, 102, 105, 108, 111 and 114 in recurring; GS-115, 118, 121, 124, 127, 130 and 133 in compound filter; GS-136, 139, 142, 145, 148 and 151 in income versus spending) are what the same rule derives for the new questions, and the file only appends them at the end.

The rule is mechanical, so that nobody chooses: within each category, in id order, one question in three (the 3rd, 6th, 9th…). `derive_test_ids` implements it and `tests/evals/test_splits.py` checks that the frozen file is still exactly what the rule gives. Growing the set means a new set (v1), not editing this file. `-T split=dev` or `-T split=test` run only one part, and each log breaks accuracy down by split.

## Each question

`id` (GS-001…, stable and never reused), `question`, `user_id`, `category`, `difficulty`, `behavior` (`answer`, `clarify`, `no_data` or `refuse`), `reference_sql`, `ordered` (whether row order is part of the answer), `scenario_id` and `notes`. The category fixes the behaviour: ambiguous is `clarify`, no data is `no_data` and out of domain is `refuse`; the rest answer. The `no_data` ones carry SQL that counts movements in the period and must give 0.

The comparison (`matches`) ignores row order unless `ordered` is `true`, ignores column names and tolerates one cent.

## How it is checked

1. **Structure:** contiguous ids, categories and difficulties spread out, functional users, anchors to real scenarios.
2. **SQL rules:** with negative controls (another table, no `LIMIT`, a user filter, `pg_sleep`, several statements…). It is the seed of the week 4 validator.
3. **Execution under RLS** as `app_reader`, with the same semantics the executor will have (`db/query.py`): read-only transaction, `set_config` as the first statement and a check that it took.
4. **Drift:** the result must match `expected_v0.json`, which stores the dataset version and the configuration hash. If the data, the generator or the semantic layer change without anyone deciding it, it fails.
5. **Truth by another route (generator design §6.3):** the answers of the scenario questions are checked against `scenarios.params`, and others against the generator's raw movements summed in Python. A disagreement points to an error in the semantic layer or the SQL, not in the LLM.

## How to add or change a question

1. Write the question in `golden_v0.yaml` with the next id.
2. Look at the result: `uv run safe-spending-golden show GS-0XX`. Read it critically: SQL that does not fail does not mean it answers well (a partial month, a period with no data or an empty result for the wrong reason are the typical errors).
3. Regenerate the expected answers: `uv run safe-spending-golden refresh`.
4. Check everything: `uv run safe-spending-golden check` and `uv run pytest tests/evals`.
5. Commit the YAML and `expected_v0.json` together.

If you change the generator or its configuration, bump `dataset_version` in `config.yaml` and in `golden_v0.yaml`, update the dataset fingerprint with `uv run safe-spending-generate --update-reference-manifest` and repeat step 3: the change in figures is visible in the diff of `expected_v0.json`, one line per question.
