from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from safe_spending.pipeline.generation.schemas.generation_attempt import GenerationAttempt
from safe_spending.pipeline.generation.schemas.generator_response import GeneratorResponse


class GenerationResult(BaseModel):
    """The outcome of generating for one question, with every attempt, for the trace (plan section 10)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    response: GeneratorResponse | None = Field(description="The first valid response; None if every attempt failed.")
    attempts: tuple[GenerationAttempt, ...] = Field(min_length=1)
    prompt_version: str
    schema_version: str = Field(description="`SemanticSchema.version` the prompt was built from.")

    @computed_field
    @property
    def cost_usd(self) -> Decimal | None:
        """Total over the attempts; None if any of them has no known price."""
        costs = [attempt.llm.cost_usd for attempt in self.attempts if attempt.llm]
        if any(cost is None for cost in costs):
            return None

        return sum(costs, Decimal(0))

    @computed_field
    @property
    def latency_s(self) -> float:
        return sum(attempt.llm.latency_s for attempt in self.attempts if attempt.llm)
