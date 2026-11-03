# ADR-008: Dates and currencies

> 🇪🇸 Español: [../es/adr/0008-fechas-y-divisas.md](../es/adr/0008-fechas-y-divisas.md)

**Status:** Accepted
**Date:** 2026-10-28
**Decides:** Erik Claveau
**Related:** ADR-005 (semantic layer), ADR-004 (model), `docs/generator-design.md`

## Context

Three things must give the same result today and a month from now, so that the evals can be compared and the demo is reproducible:

- What "today" is for a question like "how much did I spend this month?".
- Which date of a movement the model sees, when a card purchase is charged 0 to 3 days after it is made.
- How a payment in pounds is converted to euros, and at what exchange rate.

Without a rule, the same question would give a different figure depending on the day it runs, the date chosen or the rate applied.

## Decision

**Today.** The reference date is frozen (2026-09-15) and enters through the `Clock` port: `FixedClock` in evals and the demo, `SystemClock` in a real deployment. Nothing in `src/` reads the system date except `SystemClock`. The assistant receives "today" in the prompt (of the SQL generator and of the synthesizer) and writes the dates itself. The validator **rejects `now()` and `current_date`** (ADR-005, function allowlist), so a SQL never depends on the database's clock.

**Dates only.** No time and no time zone. Periods are written as `fecha >= '2026-03-01' AND fecha < '2026-04-01'` (the day after the last).

**The exposed date is the charge date.** `fecha`, in the three views, is `booking_date`: the statement's date (credit date in `v_ingresos`). The value date (`value_date`) exists in the base table and is **not** exposed.

**Euros.** All accounts are in euros. A payment in another currency keeps its original amount and currency (`importe_original` and `divisa_original`; `gasto_original` in `v_gastos`) and `importe_eur` is computed when the movement is generated:

- `amount_eur = amount / rate`, with the rate in **units of currency per 1 EUR**, applied on the **operation date** (`value_date`), rounded half-even to cents (`money.convert_to_eur_cents`).
- The exchange fee is a separate `FEE` movement, in euros and without a merchant (1.75 % of the amount, minimum €0.50).
- The rates are **synthetic**: a daily series per currency, a seeded random walk with its own stream per currency, so it depends neither on the others nor on the end date. Real ECB rates are not used.
- The applied rate is not exposed in the views: the assistant reads `importe_eur` and does not recompute conversions.

## Options considered

| Question | Options | Chosen |
|---|---|---|
| "Today" | System clock · `Clock` port with a fixed date | `Clock` |
| Time and zone | Timestamps with zone · dates only | Dates only |
| Exposed date | Charge · value · both | Charge |
| Exchange rate | The operation date's · the charge's · the real ECB's | The operation's, synthetic |

- **System clock:** rejected because each run would be another measurement and the golden set would stop being stable.
- **Timestamps with zone:** the generator design uses dates only and no golden question needs the time; adding a zone would open midnight errors without adding anything.
- **Charge date:** it is the one that appears on a statement, and the one `v_gastos` and `v_ingresos` use to group by month.
- **Both dates:** more complete, but it forces the model to choose between two almost equal columns; left for when a question asks for it.
- **Real ECB rate:** rejected for reproducibility and because it is out of scope at this stage.

## Consequences

**Easier**
- Same reference date, same results: the evals can be compared between runs and the golden set is stable.
- Without time zones or times, there is one less source of ambiguity. Numeric verification compares an answer's dates by day, month and year (ADR-005).
- The model cannot depend on the database's clock.

**Harder**
- **A purchase is counted in the month of its charge.** A purchase made on 30 August and charged on 1 September counts in September; the assistant cannot answer "what did I buy on day X" by operation date. The golden set computes its truth with the charge date, so there is no internal contradiction, but the limitation exists and how much it matters has not been measured.
- The conversion cannot be audited from the assistant: neither the rate nor the value date is in the views.
- With "today" frozen mid-month, the current month and quarter are partial on purpose (they serve to test incomplete periods). The demo must say that "today" is 15 September 2026.

**To revisit**
- If a real question needs "when did I make the purchase", expose a `fecha_operacion` column (migration, `COMMENT ON`, data dictionary and golden set).
- `SystemClock` uses `date.today()`, the server's local time. In a real deployment the zone (Europe/Madrid) would have to be set so that "today" does not change day at midnight depending on where it runs.

## Next steps

1. [x] `Clock` port with `FixedClock` and `SystemClock`.
2. [x] Conversion to euros with a per-1-EUR rate, the operation date and half-even rounding (`tests/generator/test_fx.py`).
3. [x] Validator without `now()` or `current_date`.
4. [ ] Decide whether to expose `fecha_operacion` when the golden set grows to 150-200 questions.
