from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.golden import ResultTable, to_table
from safe_spending.pipeline.assistant import AssistantOutcome, AssistantResult


class AssistantRun(BaseModel):
    """What the solver stores in the sample for the scorers: the assistant's answer, flattened."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    outcome: AssistantOutcome
    table: ResultTable | None = Field(description="The result when the query ran, else none.")
    message: str | None
    sql: str | None
    cost_usd: float | None = Field(description="None when the model has no known price.")
    latency_s: float
    trace: dict = Field(description="The whole AssistantResult as JSON, for the log.")

    @classmethod
    def from_result(
            cls,
            result: AssistantResult
    ) -> "AssistantRun":
        table = to_table(result=result.execution.result) if result.execution and result.execution.ok else None
        return cls(
            outcome=result.outcome,
            table=table,
            message=result.message,
            sql=result.sql,
            cost_usd=float(result.cost_usd) if result.cost_usd is not None else None,
            latency_s=result.latency_s,
            trace=result.model_dump(mode="json"),
        )
