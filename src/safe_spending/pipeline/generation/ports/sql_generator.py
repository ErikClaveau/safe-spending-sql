"""The `SQLGenerator` port: from a question to a structured, still untrusted, response (ADR-006).

It never executes anything and never decides whether the SQL is safe: that is the validator's job
(sqlglot) and, for isolation, Postgres RLS (ADR-002). When an earlier answer was rejected or failed to
run, the caller passes it back as `corrections` so the model can fix it (self-correction).
"""

from collections.abc import Sequence
from typing import Protocol

from safe_spending.pipeline.generation.schemas import Correction, GenerationResult


class SQLGenerator(Protocol):
    def generate(
            self,
            question: str,
            corrections: Sequence[Correction] = ()
    ) -> GenerationResult: ...
