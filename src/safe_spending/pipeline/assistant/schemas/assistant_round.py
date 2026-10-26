from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.execution import ExecutionResult
from safe_spending.pipeline.generation import Correction, GenerationResult
from safe_spending.pipeline.validation import ValidationResult


class AssistantRound(BaseModel):
    """An earlier try of the same question whose SQL had to be written again, with what went wrong."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    generation: GenerationResult
    validation: ValidationResult | None = Field(
        default=None,
        description="Set if the model wrote SQL."
    )
    execution: ExecutionResult | None = Field(
        default=None,
        description="Set if the SQL passed validation."
    )
    correction: Correction = Field(description="What was fed back to the model for the next try.")
