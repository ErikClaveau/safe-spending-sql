"""Static rules every reference SQL must follow: the assistant's own validator.

The golden set is the specification of what the assistant should be able to write, so its SQL
obeys the constraints the assistant is under (ADR-002, ADR-005): a single SELECT, only the
semantic views, a LIMIT, no filter by user and nothing dangerous. The rules live in the
pipeline's `SqlglotSQLValidator`; this module only adapts them to the golden set's use.
"""

from safe_spending.pipeline.validation import ALLOWED_VIEWS, SqlglotSQLValidator

__all__ = ["ALLOWED_VIEWS", "check_reference_sql"]

_VALIDATOR = SqlglotSQLValidator()


def check_reference_sql(sql: str) -> list[str]:
    """The rules the SQL breaks; empty when it is fine."""
    return list(_VALIDATOR.validate(sql).violations)
