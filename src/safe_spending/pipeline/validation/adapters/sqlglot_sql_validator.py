"""`SQLValidator` over sqlglot: a single SELECT, only the semantic views, a LIMIT, only allowed functions.

Moved from the golden set's reference-SQL rules, which now call it, so the SQL the assistant writes and
the SQL the golden set expects obey one rule set. Week 4 hardened it against direct attacks: functions are
an allowlist (`allowed_functions.py`), and the clauses that a SELECT can use to do more than read are refused.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from safe_spending.pipeline.validation.adapters.allowed_functions import ALLOWED_FUNCTIONS
from safe_spending.pipeline.validation.ports import SQLValidator
from safe_spending.pipeline.validation.schemas import ValidationResult

ALLOWED_VIEWS = frozenset({"v_movimientos", "v_gastos", "v_ingresos"})
USER_COLUMNS = frozenset({"user_id", "app.user_id"})


class SqlglotSQLValidator(SQLValidator):
    def validate(
            self,
            sql: str
    ) -> ValidationResult:
        return ValidationResult(violations=tuple(self._violations(sql)))

    @staticmethod
    def _violations(sql: str) -> list[str]:
        try:
            statements = [
                s
                for s in sqlglot.parse(
                    sql=sql,
                    read="postgres"
                ) if s is not None
            ]
        except ParseError as error:
            return [f"does not parse: {error}"]

        if len(statements) != 1:
            return [f"must be exactly one statement, found {len(statements)}"]

        root = statements[0]
        violations = []

        if not isinstance(root, exp.Select | exp.Union):
            return [f"must be a SELECT, not {type(root).__name__}"]
        if root.args.get("limit") is None:
            violations.append("must have a LIMIT")

        for select in root.find_all(exp.Select):
            if select.args.get("into") is not None:
                violations.append("SELECT INTO creates a table")
            if select.args.get("locks"):
                violations.append("row locks (FOR UPDATE, FOR SHARE) are not allowed")
        for with_ in root.find_all(exp.With):
            if with_.args.get("recursive"):
                violations.append("recursive queries are not allowed")

        ctes = {
            cte.alias_or_name
            for cte in root.find_all(exp.CTE)
        }
        for table in root.find_all(exp.Table):
            if table.db or table.catalog:
                violations.append(f"table {table.sql()} must not be schema-qualified")
            elif table.name not in ALLOWED_VIEWS | ctes:
                violations.append(f"table {table.name} is not a semantic view")

        for name in sorted({_function_name(function) for function in root.find_all(exp.Func)}):
            if name not in ALLOWED_FUNCTIONS:
                violations.append(f"function {name} is not allowed")

        for column in root.find_all(exp.Column):
            if column.name.lower() in USER_COLUMNS:
                violations.append("must not mention user_id: isolation is RLS, not a filter")

        return violations


def _function_name(function: exp.Func) -> str:
    """The name sqlglot knows it by; for a function it has no type for, the name as written."""
    name = function.name if isinstance(function, exp.Anonymous) else function.sql_name()

    return (name or type(function).__name__).lower()
