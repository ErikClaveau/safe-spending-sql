"""`SQLValidator` over sqlglot: a single SELECT, only the semantic views, a LIMIT, nothing dangerous.

Moved from the golden set's reference-SQL rules, which now call it, so the SQL the assistant writes and
the SQL the golden set expects obey one rule set. Week 4 hardens it against the adversarial set.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from safe_spending.pipeline.validation.ports import SQLValidator
from safe_spending.pipeline.validation.schemas import ValidationResult

ALLOWED_VIEWS = frozenset({"v_movimientos", "v_gastos", "v_ingresos"})
FORBIDDEN_FUNCTIONS = frozenset({
    "pg_sleep", "set_config", "current_setting", "pg_read_file", "pg_ls_dir", "dblink", "lo_import", "lo_export",
    "pg_terminate_backend", "pg_cancel_backend", "copy",
})
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

        ctes = {
            cte.alias_or_name
            for cte in root.find_all(exp.CTE)
        }
        for table in root.find_all(exp.Table):
            if table.db or table.catalog:
                violations.append(f"table {table.sql()} must not be schema-qualified")
            elif table.name not in ALLOWED_VIEWS | ctes:
                violations.append(f"table {table.name} is not a semantic view")

        for function in root.find_all(exp.Func):
            name = (function.sql_name() or "").lower()
            if name in FORBIDDEN_FUNCTIONS:
                violations.append(f"function {name} is forbidden")
        for node in root.find_all(exp.Anonymous):
            if node.name.lower() in FORBIDDEN_FUNCTIONS:
                violations.append(f"function {node.name} is forbidden")

        for column in root.find_all(exp.Column):
            if column.name.lower() in USER_COLUMNS:
                violations.append("must not mention user_id: isolation is RLS, not a filter")

        return violations
