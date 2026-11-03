# CI

> 🇪🇸 Español: [es/ci.md](es/ci.md)

Two levels in GitHub Actions (`.github/workflows/`). The first blocks every PR and costs nothing; the second calls the model and only runs when asked.

| Level | Workflow | When | What it does | Cost |
|---|---|---|---|---|
| 1 | `tests.yml` | Every PR and every push to `main` | Postgres 16 as a service, `uv sync --locked` and `uv run pytest` (the whole suite) | 0 |
| 2 | `evals.yml` | By hand, or on a PR labelled `run-evals` | Golden set, isolation set and injection set against the real model, then the gates with `REQUIRE_EVAL_LOG=1` | ~$2 per run |

## Why two levels

The Inspect logs are in `logs/`, which is not versioned. In a clean checkout there is no log and the gates in `tests/evals/test_eval_gate.py` are skipped (a plain `pytest` must work in a new clone). For the gate to block, the workflow has to **measure before judging**: run the three tasks and then run the test with `REQUIRE_EVAL_LOG=1`, which turns a missing log into a failure. That calls the API on every run, which is why it does not run on every push.

Level 2 runs the **whole** golden set rather than a ~30-question smoke: the accuracy gate requires the log to cover the full set, and accepting a subset would weaken that rule. A quick smoke remains a future improvement, with its own gate.

## Level 2 gates

`tests/evals/test_eval_gate.py` reads them from the latest full log of each task:

| Task | Condition |
|---|---|
| `golden_set` | accuracy ≥ 85 % |
| `isolation_set` | leak rate = 0 |
| `injection_set` | injection rate = 0, with the trap in the model's rows in at least 50 % of the questions |

Each one also requires the whole set, the current `dataset_version` and prompt, and no *refusal fallback*.

## Setup

1. In the repository: Settings > Secrets and variables > Actions > New repository secret, `ANTHROPIC_API_KEY`. Only synthetic data goes to the API.
2. Create the `run-evals` label (Issues > Labels).
3. To run the evals: put the label on the PR, or Actions > evals > Run workflow.

## How spending is bounded

- PRs from forks do not receive secrets: they cannot spend the key. `pull_request_target` is not used.
- `concurrency` with `cancel-in-progress`: a new push cancels the running execution on that branch.
- `timeout-minutes: 45`.
- Logs are kept 14 days as an artifact (`inspect-logs`) to open with `uv run inspect view`.

## A limit to know about

A job skipped for lacking the label counts as passed for GitHub. If a branch protection rule on `main` marks `evals` as required, a PR **without** the label would pass anyway. So the real requirement is a matter of process: the `run-evals` label and a green result are required before merging to `main`. Closing it mechanically would need the job to always run and decide inside whether to spend, or a separate workflow on `main`.

## What has been verified on GitHub

- **Level 1:** the whole suite passes on Linux, reproducibility manifest included. The first run failed because `tests/db/conftest.py` dropped the `safe_spending_test` schema before `bootstrap` created the database (on a clean Postgres it does not exist); it now runs `bootstrap` first.
- **Level 2:** the three gates (golden, isolation and injection) pass on GitHub with the real pipeline. Before that there were two failures that were not the gates': a key saved with a trailing space or newline (the SDK reports it as `Connection error`; two earlier steps now detect it without spending) and an `UnboundLocalError` in the golden scorer (`observed = observed(...)`), which made every sample fail when scored. CI caught it because no test ran the scorers; `tests/evals/test_task_scoring.py` now runs them with an invented sample.

## Details that cost a run

- `inspect eval` exits with code 0 even if the task is interrupted without completing any sample: the step stays green and the failure surfaces in *Gates*. The *Logs left by Inspect* step and the gate's message (which lists what is in `logs/`) are there to read it.
- A spending limit on the Anthropic account (`You have reached your specified API usage limits`) interrupts the tasks the same way. It is set in the Anthropic console, not in the repository.
