"""The CI gate (ADR-003): the newest complete golden-set run in logs/ must reach the accuracy threshold.

It judges a measurement that Inspect already made; it never calls the model. Without a log it is skipped,
so a plain `pytest` works on a fresh clone. In CI set REQUIRE_EVAL_LOG=1 so that a missing log fails
instead of letting the gate pass by not running.

    uv run --env-file .env inspect eval src/safe_spending/evals/harness/golden_task.py --max-samples 4
"""

import os
from pathlib import Path

import pytest

from safe_spending.evals.harness.gate import check, discover, latest_complete
from safe_spending.pipeline.generation import PROMPT_VERSION

LOGS_DIR = Path(os.environ.get("EVAL_LOGS_DIR", Path(__file__).resolve().parents[2] / "logs"))


def test_the_latest_complete_run_reaches_the_accuracy_threshold(golden):
    run = latest_complete(discover(LOGS_DIR), len(golden.questions)) if LOGS_DIR.is_dir() else None
    if run is None:
        message = f"no complete golden_set eval log in {LOGS_DIR}: run the Inspect task first"
        if os.environ.get("REQUIRE_EVAL_LOG"):
            pytest.fail(message)
        pytest.skip(message)

    problems = check(
        run,
        golden_questions=len(golden.questions),
        dataset_version=golden.dataset_version,
        prompt_version=PROMPT_VERSION,
    )

    assert not problems, f"{run.path}:\n  " + "\n  ".join(problems)
