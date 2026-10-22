from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from safe_spending.pipeline.assistant.schemas.assistant_outcome import AssistantOutcome
from safe_spending.pipeline.execution import ExecutionResult
from safe_spending.pipeline.generation import GenerationResult
from safe_spending.pipeline.validation import ValidationResult


class AssistantResult(BaseModel):
    """Everything one question went through, stage by stage, for the trace (plan section 10)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    question: str
    outcome: AssistantOutcome
    generation: GenerationResult
    validation: ValidationResult | None = Field(default=None, description="Only if the model wrote SQL.")
    execution: ExecutionResult | None = Field(default=None, description="Only if the SQL passed validation.")

    @computed_field
    @property
    def sql(self) -> str | None:
        response = self.generation.response
        return response.sql if response else None

    @computed_field
    @property
    def message(self) -> str | None:
        response = self.generation.response
        return response.message if response else None

    @computed_field
    @property
    def cost_usd(self) -> Decimal | None:
        return self.generation.cost_usd

    @computed_field
    @property
    def latency_s(self) -> float:
        return self.generation.latency_s + (self.execution.latency_s if self.execution else 0.0)
