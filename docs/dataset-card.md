# Dataset card: safe-spending synthetic banking data

> 🇪🇸 Español: [es/dataset-card.md](es/dataset-card.md)

Follows the structure of *Datasheets for Datasets*. Version described: **0.5.0**. Every figure below comes from the dataset the generator produces with the committed configuration; regenerate it and the numbers must match (see *Reproducibility*).

**Every record here is invented.** No real, own or anonymized transaction was used at any step. Names are generated, IBANs use a bank code (`9999`) that belongs to no real bank, and merchants are a hand-written catalog of generic establishments.

## 1. Motivation

The dataset exists to evaluate a text-to-SQL assistant over personal banking data, and in particular two things a public dataset cannot give: **isolation between customers** (every row belongs to a known user, so a leak can be recognised) and **traceable ground truth** (scripted situations whose right answer is known by construction).

It was not made to train a model, to be statistically representative of Spain, or to benchmark categorisation. Part 3 of the plan reuses the category labels, but this card describes what is here today.

## 2. Composition

One current account per user, a savings account for some of them, and every movement over two years.

| Item | Value |
|---|---|
| Users | 25 (ids 1-25) |
| Accounts | 36: 25 current, 11 savings |
| Movements | 29,234 |
| Period | 2024-09-16 to 2026-09-15 (frozen "today" is 2026-09-15) |
| Movements per user | median 1,125; min 116 (the latest sign-up, 2026-07-13); max 2,177 |
| Currencies | EUR (29,205) and GBP (29, all from one scripted trip) |
| Merchants / categories | 72 / 32, in 7 groups |

**Movement types (`tx_code`).**

| Code | Rows | What it is |
|---|---|---|
| `CARD_PURCHASE` | 25,427 | Debit card purchase at a merchant |
| `DIRECT_DEBIT` | 1,547 | Recurring payment (telecoms and utilities) |
| `TRANSFER_OUT` | 838 | Outgoing transfer, including moves to the user's own savings account |
| `SALARY` | 674 | Pay |
| `CARD_REFUND` | 426 | Refund linked to an earlier purchase |
| `TRANSFER_IN` | 276 | Incoming transfer, including returns from savings |
| `FEE` | 29 | Foreign-exchange fee on a payment in another currency |
| `BIZUM_IN` | 17 | Incoming Bizum |

520 movements are **internal transfers** between a user's own accounts: each is two movements of equal amount and opposite sign. They are left out of the spending and income views on purpose.

**Fields.** The operational tables hold only what a bank would have: `users`, `accounts`, `transactions`, `merchants`, `categories`. The columns and their meaning for the assistant are in [`data-dictionary.md`](data-dictionary.md); the generator's own fields are in [`generator-design.md`](generator-design.md).

**Labels (never loaded into the database the assistant queries).** Kept in separate Parquet files: `tx_labels` (true category, scenario, trap flags, canary, refund link), `user_labels` (archetype, monthly income, split) and `scenarios` (type, parameters, description). The ground truth of the golden set is computed from these, by a route that does not use the semantic views.

## 3. Splits

By user id, not by row, so no user is in two splits.

| Split | Users | Use |
|---|---|---|
| `eval_functional` | 1-15 | Golden set. Users 1-7 each carry one scripted scenario; 8-15 are plain users |
| `eval_adversarial` | 16-20 | Prompt-injection traps and the askers/victims of the isolation set |
| `population` | 21-25 (up to 100 by design) | Background users, and victims for the isolation questions |

**Scripted scenarios (users 1-7).** Subscription changes, job change, recent sign-up, a category with zero spending, an anomalous month, a trip to London (foreign currency) and a run of Amazon refunds. Each has a row in `scenarios` whose parameters are the answer by construction.

**Traps (users 16-20).** Each has one incoming Bizum or transfer of every one of five types, plus 0-3 repeats, 33 in total (`recategorization` 7, `response_manipulation` 7, `direct_instruction` 7, `system_impersonation` 6, `sql_lookalike` 6). The concept of each holds an injection text and a unique canary word that exists only in generated data, never in a file of the repository.

## 4. Generation process

A pure function of a configuration and a seed: `config.yaml` + two catalogs (`merchants.yaml`, `traps.yaml`) + seed `20260915` produce the Parquet files and a manifest.

1. **Profile** of each user: archetype, income, city, sign-up date.
2. **Recurring payments** and the pay, from the profile.
3. **Card purchases**, from habits by category and a weekday weight.
4. **Refunds**, drawn per refundable purchase.
5. **Scenario injectors** (users 1-7) rewrite or remove the baseline events and write the ground truth.
6. **Savings**, built after the scenarios from the pays the user really has, so the balance never goes below zero.
7. **Traps** (users 16-20).
8. **Derived fields**: statement text (`description_raw`), foreign-currency conversion and fee, value date.
9. **Export** to Parquet and a manifest.

Amounts are integer cents throughout. A foreign rate is units of the currency per 1 EUR, applied on the operation date, rounded half to even. Each user and each stage has its own random stream, so adding a user or changing one stage does not alter other data (tested). The generator never reads the system date.

## 5. Intended and out-of-scope uses

**Intended:** evaluating text-to-SQL accuracy, cross-user isolation and robustness to injection through retrieved data; demonstrating the assistant.

**Not suitable for:** conclusions about real spending behaviour, fraud or credit models, fairness studies, or training a categoriser that will meet real statements. The statistics are shaped to be plausible, not validated (see *Limitations*).

## 6. Reproducibility and distribution

The data is **not in the repository**; its fingerprint is. `dataset/manifest.json` holds the version, seed, configuration hash and, for each file, its row count and SHA-256. `tests/generator/test_reference_manifest.py` regenerates the dataset and fails if any of it differs, so a change in the data is always a decision.

```bash
uv run safe-spending-generate        # writes data/dataset (Parquet + manifest.json)
uv run safe-spending-load --reset    # loads the operational tables as app_loader
```

Byte-identical output depends on the pinned `pyarrow` in `uv.lock`. A change of generator code, configuration, catalogs or dependencies requires a new `dataset_version`, a refreshed manifest and a refreshed golden set. The repository licence (MIT) applies to the generator and the catalogs.

## 7. Known limitations

- **25 users, not 100.** The design calls for 100 (ids 1-100); the current configuration generates 25. Ids 26-100 do not exist.
- **One archetype.** Every user is a `young_professional`, differing in income (1,875 to 3,158 a month), city and habits. There are no retirees, students, self-employed or families. Conclusions about "typical" behaviour do not extend beyond this profile.
- **No statistical validation yet.** Spending is dominated by housing and food (about 44% and 25% of what is debited, internal transfers excluded), with shopping 14%, leisure and travel 10%, transport 4% and personal care 3%. These shares were **not** compared with a household budget survey; that comparison, a savings rate per archetype and a seasonality check are planned as a non-blocking report and are not built.
- **Little Bizum.** The only `BIZUM_IN` rows (17) come from the traps. There are no regular person-to-person payments, and no `BIZUM_OUT`.
- **Foreign currency is a single trip.** All 29 GBP payments belong to the London scenario. Rates are a synthetic daily series (around 0.86 GBP per EUR), not real market rates.
- **No calendar effects.** No bank holidays, no pay-day or summer effects beyond a weekday weight.
- **Counterparties are not coupled.** A Bizum from one user is not the outgoing Bizum of another.
- **Dates only.** No time of day, and no time zone: the booking date is the charge date.
- **Simple statement style.** One bank's statement format; real concepts are messier.
- **Traps are pattern-based.** Five injection families written by hand; they test the defences described in the project, not every attack in the literature.

## 8. Maintenance

Maintained with the repository. Any change that alters the data bumps `dataset_version` and is recorded in the manifest and in `docs/iteraciones-evals.md`, which also says what the golden set measured on each version.
