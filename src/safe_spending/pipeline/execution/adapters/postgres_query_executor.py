"""`QueryExecutor` over `run_as_user`: read-only transaction, identity first, role timeout (ADR-002).

A database complaint about the SQL (a bad column, the role's `statement_timeout`) comes back as an
`ExecutionResult` with the error, because it is an expected outcome of running model-written SQL.
Anything else propagates on purpose: a non-int user id or an identity that did not take is a bug or
a security failure, not something to hand to the model.
"""

import time

import psycopg

from safe_spending.db.query import DEFAULT_MAX_ROWS, run_as_user
from safe_spending.pipeline.execution.ports import QueryExecutor
from safe_spending.pipeline.execution.schemas import ExecutionErrorKind, ExecutionResult


class PostgresQueryExecutor(QueryExecutor):
    def __init__(
            self,
            dbname: str | None = None,
            *,
            max_rows: int = DEFAULT_MAX_ROWS
    ) -> None:
        self._dbname = dbname
        self._max_rows = max_rows

    def execute(
            self,
            user_id: int,
            sql: str
    ) -> ExecutionResult:
        started = time.perf_counter()
        try:
            result = run_as_user(
                user_id=user_id,
                sql=sql,
                dbname=self._dbname,
                max_rows=self._max_rows
            )
        except psycopg.errors.QueryCanceled as error:
            return self._failed(
                kind=ExecutionErrorKind.TIMEOUT,
                error=error,
                started=started
            )
        except psycopg.Error as error:
            return self._failed(
                kind=ExecutionErrorKind.DATABASE_ERROR,
                error=error,
                started=started
            )

        return ExecutionResult(
            result=result,
            latency_s=time.perf_counter() - started
        )

    @staticmethod
    def _failed(
            kind: ExecutionErrorKind,
            error: psycopg.Error,
            started: float
    ) -> ExecutionResult:
        return ExecutionResult(
            error_kind=kind,
            error=str(error).strip(),
            latency_s=time.perf_counter() - started
        )
