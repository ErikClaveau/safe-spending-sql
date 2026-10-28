from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from safe_spending.pipeline.synthesis.schemas.synthesis_attempt import SynthesisAttempt


class SynthesisResult(BaseModel):
    """The outcome of writing the answer for one result, with every attempt, for the trace (plan section 10)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    answer: str | None = Field(description="The first valid answer; None if every attempt failed.")
    attempts: tuple[SynthesisAttempt, ...] = Field(min_length=1)
    prompt_version: str
    rows_shown: int = Field(description="Result rows the model was given; fewer than the result's if it was cut.")

    @computed_field
    @property
    def cost_usd(self) -> Decimal | None:
        """Total over the attempts; None if any of them has no known price."""
        costs = [attempt.llm.cost_usd for attempt in self.attempts]
        if any(cost is None for cost in costs):
            return None

        return sum(costs, Decimal(0))

    @computed_field
    @property
    def latency_s(self) -> float:
        return sum(attempt.llm.latency_s for attempt in self.attempts)
