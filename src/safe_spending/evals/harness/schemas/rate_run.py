from pydantic import Field

from safe_spending.evals.harness.schemas.run_summary import RunSummary


class RateRun(RunSummary):
    """An adversarial run: how often the attack worked (the leak rate or the injection rate; the gate is 0)."""

    rate: float = Field(description="Share of questions where the attack succeeded.")
    reached: float | None = Field(
        default=None,
        description="Share of questions where the trap was in the rows the model got; only the injection task has it."
    )
    synthesis_prompt_version: str | None = Field(
        default=None,
        description="Only for runs that synthesize an answer; None in logs that did not record it."
    )
