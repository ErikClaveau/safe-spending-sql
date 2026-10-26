"""The rules of the CI gate, over made-up run summaries: the gate must be able to fail (ADR-003)."""

import pytest

from safe_spending.evals.harness.gate import check, latest_complete
from safe_spending.evals.harness.schemas import GateThresholds, RunSummary

QUESTIONS = 90


def run(**overrides):
    fields = dict(
        path="logs/run.eval",
        status="success",
        samples=QUESTIONS,
        completed_samples=QUESTIONS,
        model="claude-sonnet-5-5",
        prompt_version="v3",
        dataset_version="0.5.0",
        refusal_fallback=False,
        accuracy=0.90,
        dev_accuracy=0.89,
        test_accuracy=0.92,
        strict_accuracy=0.70,
    )
    return RunSummary(**{**fields, **overrides})


def problems(summary, **kwargs):
    return check(summary, golden_questions=QUESTIONS, dataset_version="0.5.0", prompt_version="v3", **kwargs)


def test_a_good_run_passes():
    assert problems(run()) == []


def test_the_threshold_is_inclusive_and_a_point_below_fails():
    assert problems(run(accuracy=0.85)) == []

    below = problems(run(accuracy=0.844))
    assert len(below) == 1 and "below the threshold 85%" in below[0]


def test_the_failure_message_shows_dev_test_and_strict_to_help_read_it():
    message = problems(run(accuracy=0.70, dev_accuracy=0.65, test_accuracy=0.80, strict_accuracy=0.5))[0]

    assert "70.0%" in message and "dev 65.0%" in message and "test 80.0%" in message and "strict 50.0%" in message


def test_the_threshold_can_be_changed():
    assert problems(run(accuracy=0.88), thresholds=GateThresholds(min_accuracy=0.90))


def test_a_run_of_another_size_is_not_the_golden_set():
    assert any("golden set has 90" in p for p in problems(run(samples=6, completed_samples=6)))


def test_a_run_on_another_dataset_or_prompt_is_stale():
    assert any("dataset 0.4.0" in p for p in problems(run(dataset_version="0.4.0")))
    assert any("prompt v1" in p for p in problems(run(prompt_version="v1")))


def test_a_run_with_refusal_fallback_does_not_measure_one_model():
    assert any("refusal fallback" in p for p in problems(run(refusal_fallback=True)))


def test_every_problem_is_reported_not_just_the_first():
    assert len(problems(run(accuracy=0.1, prompt_version="v1", dataset_version="0.4.0"))) == 3


@pytest.mark.parametrize("overrides", [
    dict(status="error"),
    dict(status="cancelled"),
    dict(completed_samples=40),
])
def test_an_unfinished_run_is_not_complete(overrides):
    assert not run(**overrides).complete


def test_the_newest_complete_run_is_the_one_judged():
    newest_failed = run(path="c", status="error")
    older_good = run(path="b")
    oldest_good = run(path="a")

    assert latest_complete([newest_failed, older_good, oldest_good], QUESTIONS).path == "b"
    assert latest_complete([], QUESTIONS) is None
    assert latest_complete([run(path="x", status="error")], QUESTIONS) is None


def test_a_limit_experiment_never_stands_in_for_the_whole_set():
    experiment = run(path="newest", samples=6, completed_samples=6, accuracy=1.0)
    full = run(path="full", accuracy=0.86)

    assert latest_complete([experiment, full], QUESTIONS).path == "full"
    assert latest_complete([experiment], QUESTIONS) is None


def test_a_log_from_before_the_split_is_still_judged_by_its_overall_accuracy():
    message = problems(run(accuracy=0.70, dev_accuracy=None, test_accuracy=None))[0]

    assert "dev n/a" in message and "test n/a" in message
