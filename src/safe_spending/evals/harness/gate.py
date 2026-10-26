"""The CI gate (ADR-003): Inspect AI measures, pytest decides whether the last measurement is good enough.

Inspect leaves one log per run in `logs/`. The gate reads the newest *complete* run of the golden-set
task (a `--limit 6` run proves nothing), checks that it was made with the code and data of today and
under the evaluation protocol, and compares its accuracy with the threshold. Everything here that
judges is a pure function over a `RunSummary`, so the rules are tested without any log.
"""

from collections.abc import Iterable, Sequence
from pathlib import Path

from inspect_ai.log import EvalLog, read_eval_log

from safe_spending.evals.harness.schemas import GateThresholds, RunSummary

TASK = "golden_set"
HEADLINE = "execution_accuracy"
STRICT = "execution_accuracy_strict"


def summarize(
        header: EvalLog,
        path: Path
) -> RunSummary:
    meta = header.eval.metadata or {}
    headline = _metrics(header, HEADLINE)

    return RunSummary(
        path=str(path),
        status=header.status,
        samples=header.eval.dataset.samples or 0,
        completed_samples=header.results.completed_samples if header.results else 0,
        model=meta["model"],
        prompt_version=meta["prompt_version"],
        dataset_version=meta["dataset_version"],
        refusal_fallback=meta["refusal_fallback"],
        accuracy=headline["accuracy"],
        dev_accuracy=headline.get("dev"),
        test_accuracy=headline.get("test"),
        strict_accuracy=_metrics(header, STRICT)["accuracy"],
    )


def discover(logs_dir: Path) -> list[RunSummary]:
    """Every golden-set run in `logs_dir`, newest first (log names start with their timestamp)."""
    summaries = []
    for path in sorted(logs_dir.glob("*.eval"), reverse=True):
        header = read_eval_log(str(path), header_only=True)
        if header.eval.task == TASK and header.results is not None:
            summaries.append(summarize(header, path))

    return summaries


def latest_complete(
        summaries: Iterable[RunSummary],
        golden_questions: int
) -> RunSummary | None:
    """The newest run that finished and covered every question; `--limit` experiments are skipped, not judged."""
    return next((s for s in summaries if s.complete and s.samples == golden_questions), None)


def check(
        run: RunSummary,
        *,
        golden_questions: int,
        dataset_version: str,
        prompt_version: str,
        thresholds: GateThresholds = GateThresholds()
) -> list[str]:
    """Why the run does not pass the gate; empty when it does."""
    problems = []

    if run.samples != golden_questions:
        problems.append(f"the run has {run.samples} questions and the golden set has {golden_questions}: run it again")
    if run.dataset_version != dataset_version:
        problems.append(f"the run used dataset {run.dataset_version}, the repository has {dataset_version}")
    if run.prompt_version != prompt_version:
        problems.append(f"the run used prompt {run.prompt_version}, the code uses {prompt_version}: run it again")
    if run.refusal_fallback:
        problems.append("the run had refusal fallback on: evals must measure one model (ADR-003)")
    if run.accuracy < thresholds.min_accuracy:
        problems.append(
            f"accuracy {run.accuracy:.1%} is below the threshold {thresholds.min_accuracy:.0%} "
            f"(dev {_percent(run.dev_accuracy)}, test {_percent(run.test_accuracy)}, strict {run.strict_accuracy:.1%})"
        )

    return problems


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _metrics(
        header: EvalLog,
        scorer: str
) -> dict[str, float]:
    for score in header.results.scores:
        if score.name == scorer:
            return {name: metric.value for name, metric in score.metrics.items()}
    raise ValueError(f"the log has no scorer {scorer!r}")
