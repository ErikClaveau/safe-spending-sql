from pydantic import Field

from safe_spending.evals.harness.schemas.run_summary import RunSummary


class AccuracyRun(RunSummary):
    """A golden-set run: how many questions the assistant got right."""

    accuracy: float = Field(description="Headline execution accuracy over every question.")
    dev_accuracy: float | None = Field(
        default=None,
        description="None in logs made before the dev/test split."
    )
    test_accuracy: float | None = None
    strict_accuracy: float
