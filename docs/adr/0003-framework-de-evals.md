# ADR-003: Inspect AI to measure and pytest as the CI gate

> 🇪🇸 Español: [../es/adr/0003-framework-de-evals.md](../es/adr/0003-framework-de-evals.md)

**Status:** Accepted
**Date:** 2026-10-21
**Decides:** Erik Claveau
**Related:** ADR-002 (isolation), ADR-004 (model), ADR-006 (LLM output)

## Context

The project is judged by its metrics: execution accuracy, cross-user leak, successful injections, numeric traceability and cost (plan §2.3). Two different things are needed:

- **Measure and analyse.** Run the golden set with every model or prompt change, compare runs, see question by question which SQL was generated and why it failed (the week 5 error analysis) and publish an iteration table.
- **Block.** A binary gate in CI: leak = 0, canaries = 0 and accuracy above the threshold.

The golden set v0 already exists (`evals/golden/`, 90 questions with reference SQL), a per-user runner (`run_as_user`) and a truth check by a route that does not use the views (`scenarios.params`).

## Decision

- **Inspect AI** runs the evals. The golden set is exposed as a task; the pipeline is the *solver* and the *scorer* compares the query result with the truth. Each run leaves a per-sample log, with a viewer and comparison between runs.
- **pytest** is only the CI gate. It reads the result of the latest run (or runs the smoke subset) and fails if leak or canaries are not 0 or accuracy drops below the threshold.
- Each run is anchored to the commit SHA, the model, the prompt version, the dataset version and the semantic schema version (plan §9.3), in the log metadata.
- The security scorers (leak, canaries) are own code with access to Postgres; Inspect does not impose how scoring is done.

## Measurement protocol

Fixed on 2026-10-22 when building the first task:

- **Main metric, tolerant of extra columns.** An answer is correct if some ordered subset of its columns matches the reference result (same rows, one-cent tolerance). A column nobody asked for, such as a difference or a percentage, does not penalise. The **strict metric** (exactly equal columns, as in benchmarks) is also published, to compare with the literature and see how much is lost to shape.
- **Behaviours.** `refuse` requires a refusal; `clarify` accepts a question or an answer that states its assumption (until ADR-010 decides); `no_data` requires a query whose result is empty or zero, or a refusal that does not invent data.
- **Value equivalences.** A month written `2026-03-01` equals `2026-03`, and in the tolerant metric the same columns in another order do not penalise. These rules were refined on 2026-10-26 after seeing the baseline failures, so the original baseline and the re-scored one are both published (`docs/iteraciones-evals.md`).
- **Split.** 26 of the 90 questions are test, chosen by a mechanical rule and frozen (`evals/golden/splits_v0.yaml`). Decisions about what to change are made only from dev failures; test is scored and published every round. See `docs/golden-set.md`.
- **One model per measurement.** In the evals the provider's *fallback* on refusals is off: all answers come from the measured model and a refusal counts as a generation failure. In the application and the demo it stays on.
- **Threshold.** The CI gate requires a tolerant accuracy of **85 %** over the 90 questions (dev and test together), inclusive. The initial target is kept after the baseline (90.0 % in week 3). With 90 questions the standard error is about 3 points, so the margin is narrow and an isolated drop of one or two questions can be noise: repeat with `--epochs 3` before looking for a cause.
- **The gate.** `tests/evals/test_eval_gate.py` reads the most recent log of the task that covers all the questions (a run with `--limit` does not count) and fails if it does not reach the threshold, if it was made with a different prompt or dataset version than the code's, or if the *fallback* was on. It does not call the model. With no log at all it is skipped, so that `pytest` works in a clean clone; with `REQUIRE_EVAL_LOG=1` (in CI) a missing log is a failure, so the gate cannot pass by not running.
- **Logs.** Each run leaves an Inspect log in `logs/` (ignored by Git) with the SQL, the result and the full trace of each question. Published results are summarised in the README and in the iteration table.
- **Running:** `uv run --env-file .env inspect eval src/safe_spending/evals/harness/golden_task.py --max-samples 4`.

## Options considered

| Option | Custom metrics | History and comparison | Error viewer | Effort this week | Portfolio |
|---|---|---|---|---|---|
| **Inspect AI** | Yes (Python scorers) | Yes, versionable logs | Yes | Medium: adapt the golden set | High |
| Own pytest | Yes | To build | To build | Low | Low |
| promptfoo | Limited against Postgres with RLS | Yes | Yes | Medium | Medium |

Own pytest can record metrics in JSON, but history, comparison and viewer would have to be built by hand, and they are precisely what matters most in the error analysis. promptfoo fits poorly with scorers that query a database with RLS.

## Consequences

**Easier**
- An iteration table with metrics (week 5) from the logs.
- Inspecting failures per sample without building tools.

**Harder**
- One more dependency and a task model to learn.
- The Inspect output format that pytest reads must be fixed.
- Logs must be treated as artifacts (what is versioned and what is not).

**To revisit**
- If adapting the golden set turns out disproportionate, scope is cut before delaying the baseline (plan §14 rule).

## Next steps

1. [x] Add `inspect-ai` as a development dependency.
2. [x] Inspect task over `golden_v0.yaml` with an execution accuracy scorer.
3. [x] pytest test that reads the result and applies the thresholds (`tests/evals/test_eval_gate.py`). Pending: the leak and canary thresholds, when the adversarial set exists (week 4).
