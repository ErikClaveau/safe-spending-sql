"""The `SQLValidator` port: static checks on SQL that nobody trusts (ADR-002, ADR-005).

It only judges; it never rewrites the SQL or adds a user filter. Isolation is Postgres RLS, so this is
a layer that keeps the model on the semantic views and away from dangerous statements, not the
guarantee.
"""

from typing import Protocol

from safe_spending.pipeline.validation.schemas import ValidationResult


class SQLValidator(Protocol):
    def validate(
            self,
            sql: str
    ) -> ValidationResult: ...
