from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from safe_spending.pipeline.assistant.schemas.assistant_outcome import AssistantOutcome
from safe_spending.pipeline.assistant.schemas.assistant_round import AssistantRound
from safe_spending.pipeline.assistant.schemas.stage_latency import StageLatency
from safe_spending.pipeline.execution import ExecutionResult
from safe_spending.pipeline.generation import GenerationResult
from safe_spending.pipeline.synthesis import SynthesisResult
from safe_spending.pipeline.validation import ValidationResult


class AssistantResult(BaseModel):
    """Everything one question went through, stage by stage, for the trace (plan section 10).

    `generation`, `validation` and `execution` are those of the final try. If the SQL had to be
    corrected, the earlier tries are in `corrections`, oldest first.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    question: str
    outcome: AssistantOutcome
    generation: GenerationResult
    validation: ValidationResult | None = Field(default=None, description="Only if the model wrote SQL.")
    execution: ExecutionResult | None = Field(default=None, description="Only if the SQL passed validation.")
    corrections: tuple[AssistantRound, ...] = Field(default=(), description="Earlier tries, oldest first.")
    synthesis: SynthesisResult | None = Field(default=None, description="Only if the query ran and a synthesizer is set.")

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
    def answer(self) -> str | None:
        """The text for the user, when a synthesizer wrote it."""
        return self.synthesis.answer if self.synthesis else None

    @computed_field
    @property
    def cost_usd(self) -> Decimal | None:
        """Total over every try and the synthesis; None if any of them has no known price."""
        costs = [generation.cost_usd for generation in self._generations()]
        if self.synthesis:
            costs.append(self.synthesis.cost_usd)
        if any(cost is None for cost in costs):
            return None

        return sum(costs, Decimal(0))

    @computed_field
    @property
    def latency_by_stage(self) -> StageLatency:
        executions = [r.execution for r in self.corrections] + [self.execution]

        return StageLatency(
            generation_s=sum(generation.latency_s for generation in self._generations()),
            execution_s=sum(execution.latency_s for execution in executions if execution),
            synthesis_s=self.synthesis.latency_s if self.synthesis else 0.0
        )

    @computed_field
    @property
    def latency_s(self) -> float:
        return self.latency_by_stage.total_s

    def _generations(self) -> list[GenerationResult]:
        return [r.generation for r in self.corrections] + [self.generation]
