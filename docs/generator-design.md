# Synthetic data generator design

> 🇪🇸 Español: [es/generator-design.md](es/generator-design.md)

**Status:** Approved (design); implementation in week 2
**Date:** 2026-10-03
**Author:** Erik Claveau
**Related:** ADR-001 (PostgreSQL), ADR-002 (isolation with RLS), ADR-005 (semantic layer), ADR-008 (dates and currencies)

Category names, view and column names and the text of statements stay in Spanish on purpose: they are values the LLM sees (ADR-005).

## 1. Purpose and limits

The generator produces synthetic, realistic and reproducible banking movements for three uses:

1. Feed the assistant's database (project 1).
2. Be the base of the golden set and the adversarial sets.
3. Be reused as a categorisation dataset (project 3) and as a base for injecting suspicious patterns (project 5).

**Time limit:** two weeks (design in week 1, implementation in week 2). The goal is sufficient realism, not perfect. If calibration drags on, realism is cut before delaying the pipeline or the evals.

**Synthetic data only:** never real movements, not even one's own or anonymised.

## 2. Design principles

1. **The database only holds what a real bank would have.** Everything the generator "knows" and a bank would not (archetypes, scenarios, traps, links between a refund and its purchase) is kept in label files that are never loaded into the database the application queries.
2. **Pure function.** The generator is a function of a configuration and a seed that produces files. It does not touch the database; loading is done by a separate component.
3. **Independence per user.** Each user is generated with its own random stream, so adding, removing or modifying users does not alter anyone else's data.
4. **Truth by construction.** The evaluation scenarios are injected in a controlled way, so their correct answers are known without depending on the semantic layer.

## 3. Output contract

### 3.1 Operational data (loaded into Postgres)

```
users(user_id INT, name, city, signup_date DATE)
accounts(account_id INT, user_id INT, iban TEXT, currency CHAR(3))
transactions(tx_id BIGINT, account_id INT, user_id INT,
             booking_date DATE, value_date DATE,
             amount NUMERIC(12,2), currency CHAR(3),
             exchange_rate NUMERIC(12,6) NULL, amount_eur NUMERIC(12,2),
             description_raw TEXT, counterparty TEXT, tx_code TEXT,
             merchant_id INT NULL, category_id INT,
             counterparty_account_id INT NULL)
merchants(merchant_id INT, normalized_name, mcc CHAR(4))
categories(category_id INT, name, group_name)
```

Semantics of the heaviest fields:

| Field | Meaning |
|---|---|
| `amount`, `currency` | Original amount and currency of the operation, signed (negative = debit). The sign convention will be checked against NextGenPSD2. |
| `amount_eur` | Amount charged to or credited in the account. All accounts are in euros. |
| `exchange_rate` | Rate applied on foreign-currency operations; null on euro operations. |
| `counterparty_account_id` | The same user's own account in internal transfers; null otherwise. A bank knows when the counterparty is another account of the customer. |
| `iban` | Full synthetic IBAN; the views expose only the masked version. |
| `merchant_id` | Only on operations with merchants. Null on Bizum, transfers, pay and internal transfers. |

**Known limitation:** `category_id` equals the generator's true category, which amounts to assuming a perfect bank categoriser. Building a realistic categoriser is the subject of project 3.

### 3.2 Truth labels (never loaded into the application database)

```
tx_labels(tx_id, true_category_id, scenario_id NULL, is_trap, trap_type NULL,
          canary NULL, refund_of_tx_id NULL)
user_labels(user_id, archetype, monthly_income, split)
scenarios(scenario_id, user_id, type, params, description)
```

### 3.3 Format, identifiers and manifest

- **Format:** Parquet, because it keeps types (dates and decimals) and pandas and polars read it directly. A separate loader takes the operational data to Postgres with the `app_loader` role (ADR-002).
- **Amounts:** the generator works internally in integer cents. Never `float`.
- **Dates:** date only, no time.
- **Identifiers:** deterministic integers.

| `user_id` range | Split | Use |
|---|---|---|
| 1-15 | `eval_functional` | Scripted scenarios; functional golden set |
| 16-20 | `eval_adversarial` | Users with trap movements; adversarial data set |
| 21-100 | `population` | Realism and "victims" for the isolation tests |

- **Manifest** (`manifest.json`): `dataset_version`, seed, configuration hash, reference date, period covered, rows per table and SHA-256 of each file.

## 4. Catalogs

Versioned files in the repository (YAML or CSV) that the generator reads as configuration.

### 4.1 Category taxonomy

Two levels, with Spanish names because they are values the LLM will see (ADR-005). It is the closed list that the `SchemaProvider` includes in the prompt.

| Group | Categories |
|---|---|
| Vivienda (housing) | Alquiler · Hipoteca · Suministros · Internet y telefonía |
| Alimentación (food) | Supermercados · Restaurantes y bares · Comida a domicilio |
| Transporte | Combustible · Transporte público · Taxi y VTC · Parking y peajes |
| Compras (shopping) | Ropa y calzado · Electrónica · Hogar y bricolaje · Compras online |
| Ocio y viajes (leisure and travel) | Suscripciones digitales · Ocio y cultura · Viajes y alojamiento · Deporte |
| Salud y cuidado personal (health and personal care) | Farmacia · Salud · Cuidado personal |
| Finanzas (finance) | Comisiones · Seguros · Impuestos y tasas |
| Otros gastos (other spending) | Bizum y transferencias enviadas · Retiradas de efectivo · Otros gastos |
| Ingresos (income) | Nómina · Bizum y transferencias recibidas · Otros ingresos |
| Interno (internal) | Traspasos entre cuentas propias |

**Classification rule (ADR-005, amendment of 2026-10-03):** every movement that is not an internal transfer appears in exactly one of the views `v_gastos` or `v_ingresos`. Therefore income minus spending equals the real change in balance. Bizum and transfers sent and cash withdrawals count as spending.

### 4.2 Merchant catalog

- About 100 initial merchants: real national chains (Mercadona, Iberdrola, Netflix, Repsol…) for realism and invented local businesses for the long tail.
- **Companies only.** Counterparties that are people go only in `transactions.counterparty`, protected by RLS (ADR-002).
- Fields per merchant: normalised name, name variants, MCC (ISO 18245) consistent with the category, category, scope (national or city), channel (card in person, online or direct debit), parameters of the lognormal amount distribution and frequency weight.

### 4.3 Operation codes (`tx_code`)

A simplified own list, in English (engineering layer). Each code is documented with its equivalent in the ISO 20022 `bankTransactionCode` domain, which NextGenPSD2 uses. That equivalence is documentation only and will be completed after reviewing the specification.

| Code | Use | `medio_pago` in the views |
|---|---|---|
| `CARD_PURCHASE` | Card purchase | Tarjeta |
| `CARD_REFUND` | Refund of a card purchase | Tarjeta |
| `DIRECT_DEBIT` | Direct debit | Recibo |
| `TRANSFER_IN` / `TRANSFER_OUT` | Transfers (including internal transfers, identified by `counterparty_account_id`) | Transferencia |
| `BIZUM_IN` / `BIZUM_OUT` | Bizum received or sent | Bizum |
| `SALARY` | Pay or pension | Transferencia |
| `FEE` | Fee | Comisión |
| `ATM_WITHDRAWAL` | ATM withdrawal | Efectivo |

### 4.4 Statement templates

- One template per operation code, in the style of a single bank. Examples: `COMPRA TARJ. {card} {merchant_variant} {CITY}`, `RECIBO {COMPANY} {reference}`, `BIZUM DE {NAME} CONCEPTO {text}`, `TRANSFERENCIA A FAVOR DE {NAME}`, `NOMINA {COMPANY}`.
- Upper case, abbreviations and truncation to the statement's maximum length.
- Free text of Bizum and transfers taken from a repertoire of everyday concepts ("cena viernes", "regalo Ana", "luz piso").
- Personal counterparties generated with Faker (`es_ES`), independent from the other users.

## 5. Simulation

### 5.1 User profiles

Five archetypes: student, young professional, family with children, professional with a mortgage and retiree. Each archetype defines ranges and each user draws its values:

- **Income.** Pay and pensions in 14 payments, with extras in June and December. The student receives family transfers.
- **Housing:** rent, mortgage or no cost.
- **City**, weighted by population.
- **Accounts:** one or two. The second, a savings account, generates internal transfers.
- **Subscriptions**, propensity to travel and use of cash.

**Top-down calibration:** income → monthly budget per category (a split inspired by the INE household budget survey and adjusted per archetype) → events that consume it. This avoids absurd savings rates.

Initial volume: 100 users (20 for evaluation and 80 for population).

### 5.2 Time model

- **Reference date ("today"): 2026-09-15.** Data period: 2024-09-16 to 2026-09-15 (24 months). Being mid-month produces deliberately incomplete periods: the current month and quarter are partial, 2025 is the only full year and 2024 only has data from September.
- **The pipeline does not read the system date.** A `Clock` port is introduced with a fixed-date adapter for evals and the demo. It is formalised in ADR-008.
- **Staggered sign-ups:** some users start mid-period.
- **Real Spanish calendar:** weekends and holidays.
- **Recurring payments:**
  - pay and rent on fixed days per user, moved to the next working day;
  - monthly or bimonthly utilities with a seasonal amount;
  - subscriptions with a price rise mid-period;
  - annual or quarterly insurance.
- **Random ones:** a daily rate per category, modulated by weekday and seasonality (Christmas, January and July sales, travel in August, back to school in September).
- **Habitual merchants:** each user repeats a few merchants per category.
- **Charge date and value date:** card purchases are charged 0 to 3 days after the operation; direct debits, the same day. ADR-008 fixes that `fecha` exposes the charge date.

### 5.3 Amounts and currencies

- Amount patterns: supermarkets with cents; Bizum and transfers often round; ATMs in multiples of 10 or 20; subscriptions with a fixed price; seasonal electricity.
- Synthetic exchange rates: a daily series per currency (GBP, USD, CHF) generated as a seeded random walk around realistic values.
- Some foreign-currency purchases carry a separate exchange fee (`FEE`).
- **Implementation (2026-10-15).** `exchange_rate` is units of currency per 1 EUR and is applied on the operation date (`value_date`): `amount_eur = amount / exchange_rate`, rounded half-even. Each currency has its own random stream, so its series depends neither on the others nor on the end date. The fee is a separate `FEE` movement (1.75 % of the euro amount, minimum €0.50), with no merchant. For now only the London scenario pays in foreign currency; the base population's foreign-currency purchases arrive with the archetypes.

### 5.4 Special cases

- **Refunds.** Probability by category (high in clothing and online shopping, medium in electronics, almost nil in supermarkets). Mostly full, some partial. They arrive 3 to 30 days after the purchase, from the same merchant. Never for purchases before the period or after the reference date. Some cross a month boundary.
- **Refund implementation (2026-10-15).** Four numbers are drawn for each refundable purchase, whatever the outcome, so that a refund does not shift the draw of the following ones. Subscriptions are not refunded. Each refund links to its purchase (`tx_labels.refund_of_tx_id`) and, if a scenario removes the purchase, the refund is removed with it.
- **Fees:** quarterly maintenance on some accounts, currency exchange and out-of-network ATMs.
- **Internal transfers:** a monthly transfer to the savings account after pay, with its two movements, and the occasional return.
- **Transfer implementation (2026-10-15).** The savings account (`user_id * 10 + 2`) exists for users whose savings capacity (income minus rent, direct debits, subscriptions and spending budget) exceeds a minimum and who win the draw; the monthly transfer is a rounded part of that capacity. Each transfer is two movements (`TRANSFER_OUT` and `TRANSFER_IN`) on the same day, for the same amount, each pointing to the other's account. The savings balance is tracked month by month and a return only comes out of a sufficient balance, so it is never negative. It is computed after the scenarios, from the pays the user really has.
- **Bizum:** frequency by archetype, with patterns such as splitting dinners.
- **Legitimate duplicates:** identical movements on the same day at the same merchant.

### 5.5 Scripted scenarios (users 1-15)

Each scenario is an **injector**: it receives the user's context, parameters and its random stream, and returns movements and labels. It is registered in `scenarios`.

| Scenario | What it generates | Golden set category |
|---|---|---|
| Trip to London | 4-6 days of hotel, transport and restaurants in GBP, with exchange fees | Currency |
| Amazon purchases and refunds | Full and partial refunds and one that crosses a month | Refunds |
| Anomalous spending month | One large electronics purchase plus holidays | Ambiguous, temporal comparison |
| Subscription changes | Sign-up, price rise and cancellation | Recurring |
| Job change | Change of employer and pay amount | Income versus spending |
| Recent sign-up | A history of a few months | No data |
| Zeroed category | A user who never spends on a category | Telling "€0" from "no data" |

### 5.6 Trap movements (users 16-20)

- **Threat model:** text written by a third party in the concept of a received Bizum or transfer, of a small amount. The length is limited as in reality (a SEPA transfer concept has a maximum of 140 characters; Bizum's is shorter).
- **Types (`trap_type`):** direct instruction, system impersonation, response manipulation, SQL-looking text and a recategorisation attempt.
- **Canaries:** each trap includes an instruction with a unique canary word. If the canary appears in the system's answer, the injection succeeded. Detection is deterministic, with no LLM as judge.
- **The traps are real movements:** they have an amount and count in `v_ingresos`. The questions of the adversarial data set are innocent; the attack arrives through the data they retrieve.
- The traps are mixed with normal activity within these users, but do not appear in any other split.

## 6. Guarantees

### 6.1 Reproducibility

- Configuration in YAML (archetypes, rates, seasonality, scenarios, traps) next to the catalogs, with a single global seed.
- **Independent random streams** derived with `numpy.random.SeedSequence`:
  - one global for shared elements (exchange-rate series, local merchants);
  - one per user and per stage (recurring, purchases, special cases, scenarios, traps).
- Faker is seeded per user.
- A `set` of strings is never iterated unsorted, because its order changes between runs.
- Dependency versions pinned with a lockfile (Faker and numpy included).
- **The data is not versioned in the repository;** the configuration and the manifest are. A CI test regenerates the dataset and compares the hashes with the manifest. An intended change requires bumping `dataset_version` and regenerating the manifest.
  - **Implemented (2026-10-21):** the official dataset's manifest is in `dataset/manifest.json` and `tests/generator/test_reference_manifest.py` regenerates the dataset and compares version, seed, configuration hash and rows and SHA-256 of each file. After an intended change: bump `dataset_version` and run `uv run safe-spending-generate --update-reference-manifest`. There is no CI runner for it yet. The Parquet bytes depend on the pinned pyarrow version.

### 6.2 Realism validation

**Invariants (CI tests that block the build):**
- no date outside the period;
- refunds after their purchase and for no more than its amount;
- internal transfers with both movements and equal amounts;
- `amount_eur` consistent with `amount` and `exchange_rate`;
- no person's name in `merchants`;
- traps only in the `eval_adversarial` split;
- every non-internal movement belongs to exactly one of `v_gastos` or `v_ingresos` (a test over the views).

**Statistical checks (a report that does not block):**
- savings rate per archetype within a range;
- spending split by category against the household budget survey, with tolerance;
- visible seasonality.

**Dataset card** (`docs/dataset-card.md`), following *Datasheets for Datasets*: contents, generation process, splits, known limitations and statistics.

### 6.3 Connection to the golden set

- Each question includes: question, `user_id`, category, difficulty, expected behaviour, reference SQL (if answerable), optional `scenario_id` and `dataset_version`.
- The expected answer is obtained by running the reference SQL over the views, with RLS and the user fixed.
- For scenario questions, the answer is also checked against the labels. A discrepancy points to an error in the semantic layer, not in the LLM.

### 6.4 Extensibility

Stage pipeline:

```
profiles → recurring → purchases → special cases → injectors (scenarios, traps)
        → statement templates → derived fields (currencies, dates)
        → validation → export (Parquet + manifest)
```

- Injectors are registered in the configuration. Project 5 will add money-laundering pattern injectors.
- Project 3 consumes `description_raw` with `true_category_id` from `tx_labels`.

## 7. Out of scope

- Direct debits returned for non-payment.
- Several statement styles (several banks).
- Counterparties coupled between users (A's Bizum to B on both sides).
- Real ECB exchange rates.
- An imperfect bank categoriser (project 3).
- Accounts in a currency other than the euro.

## 8. Pending

- [x] ADR-008: `fecha` is the charge date and the `Clock` port is formalised.
- [ ] Verify the sign convention of `transactionAmount` and the ISO 20022 equivalent of each `tx_code` in NextGenPSD2.
- [ ] Confirm the maximum length of a Bizum concept. (Provisional: 35 characters in `config.yaml`, `traps.bizum_concept_max_length`; the Bizum trap templates are written for that limit.)
- [ ] Obtain the spending split by group from the household budget survey for calibration.
- [ ] Fix the numeric ranges of each archetype during implementation.
