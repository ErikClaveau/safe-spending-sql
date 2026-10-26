from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.db.query_result import QueryResult
from safe_spending.pipeline.execution.schemas.execution_error_kind import ExecutionErrorKind


class ExecutionResult(BaseModel):
    """What running a query produced: rows, or the database's complaint, plus how long it took."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    result: QueryResult | None = Field(
        default=None,
        description="Set when the query ran."
    )
    error_kind: ExecutionErrorKind | None = None
    error: str | None = Field(
        default=None,
        description="The database's message, for the trace and the retry."
    )
    latency_s: float

    @property
    def ok(self) -> bool:
        return self.result is not None

    @model_validator(mode="after")
    def _rows_or_error(self) -> Self:
        if (self.result is None) == (self.error is None) or (self.error is None) != (self.error_kind is None):
            raise ValueError("an execution has either a result, or an error with its kind")

        return self
