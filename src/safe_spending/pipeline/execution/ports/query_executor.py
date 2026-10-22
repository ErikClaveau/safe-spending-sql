"""The `QueryExecutor` port: run already-validated SQL as one user, under RLS (ADR-002).

`user_id` comes from the authentication layer, never from the question or the model. The SQL runs
as it is: no rewriting and no user filter.
"""

from typing import Protocol

from safe_spending.pipeline.execution.schemas import ExecutionResult


class QueryExecutor(Protocol):
    def execute(
            self,
            user_id: int,
            sql: str
    ) -> ExecutionResult: ...
