"""The `SQLGenerator` port: from a question to a structured, still untrusted, response (ADR-006).

It never executes anything and never decides whether the SQL is safe: that is the validator's job
(sqlglot) and, for isolation, Postgres RLS (ADR-002).
"""

from typing import Protocol

from safe_spending.pipeline.generation.schemas import GenerationResult


class SQLGenerator(Protocol):
    def generate(
            self,
            question: str
    ) -> GenerationResult: ...
