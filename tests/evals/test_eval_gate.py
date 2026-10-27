"""The CI gate (ADR-003): the newest complete run of each gated task in logs/ must reach its threshold.

Golden set: accuracy of at least 85%. Isolation set: leak rate 0. Injection set: injection rate 0, with the
traps reaching the model often enough for that 0 to mean something. It judges measurements that Inspect
already made; it never calls the model. Without a log a test is skipped, so a plain `pytest` works on a fresh
clone. In CI set REQUIRE_EVAL_LOG=1 so that a missing log fails instead of letting the gate pass by not running.

    uv run --env-file .env inspect eval src/safe_spending/evals/harness/golden_task.py --max-samples 4
    uv run --env-file .env inspect eval src/safe_spending/evals/harness/isolation_task.py --max-samples 4
    uv run --env-file .env inspect eval src/safe_spending/evals/harness/injection_task.py --max-samples 4
"""

import os
from pathlib import Path

import pytest

from safe_spending.evals.adversarial import load_injection_set, load_isolation_set
from safe_spending.evals.harness.gate import (
    GOLDEN_TASK,
    INJECTION_TASK,
    ISOLATION_TASK,
    check,
    check_injection,
    check_isolation,
    discover,
    latest_complete,
)
from safe_spending.pipeline.generation import PROMPT_VERSION
from safe_spending.pipeline.synthesis import PROMPT_VERSION as SYNTHESIS_PROMPT_VERSION

LOGS_DIR = Path(os.environ.get("EVAL_LOGS_DIR", Path(__file__).resolve().parents[2] / "logs"))


def latest_run(task, questions):
    run = latest_complete(discover(LOGS_DIR, task), questions) if LOGS_DIR.is_dir() else None
    if run is None:
        message = f"no complete {task} eval log in {LOGS_DIR}: run the Inspect task first"
        if os.environ.get("REQUIRE_EVAL_LOG"):
            pytest.fail(message)
        pytest.skip(message)

    return run


def test_the_latest_complete_run_reaches_the_accuracy_threshold(golden):
    run = latest_run(GOLDEN_TASK, len(golden.questions))

    problems = check(
        run,
        golden_questions=len(golden.questions),
        dataset_version=golden.dataset_version,
        prompt_version=PROMPT_VERSION,
    )

    assert not problems, f"{run.path}:\n  " + "\n  ".join(problems)


def test_the_latest_complete_isolation_run_has_no_leak():
    isolation = load_isolation_set()
    run = latest_run(ISOLATION_TASK, len(isolation.questions))

    problems = check_isolation(
        run,
        questions=len(isolation.questions),
        dataset_version=isolation.dataset_version,
        prompt_version=PROMPT_VERSION,
    )

    assert not problems, f"{run.path}:\n  " + "\n  ".join(problems)


def test_the_latest_complete_injection_run_has_no_successful_injection():
    injection = load_injection_set()
    run = latest_run(INJECTION_TASK, len(injection.questions))

    problems = check_injection(
        run,
        questions=len(injection.questions),
        dataset_version=injection.dataset_version,
        prompt_version=PROMPT_VERSION,
        synthesis_prompt_version=SYNTHESIS_PROMPT_VERSION,
    )

    assert not problems, f"{run.path}:\n  " + "\n  ".join(problems)
