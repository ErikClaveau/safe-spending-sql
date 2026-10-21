"""Static rules every reference SQL must follow: the same ones the SQL validator will enforce.

The golden set is the specification of what the assistant should be able to write, so its SQL
obeys the constraints the assistant is under (ADR-002, ADR-005): a single SELECT, only the
semantic views, a LIMIT, no filter by user and nothing dangerous. This is the seed of the
validator of week 4; when that exists, this module should call it instead of duplicating it.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWED_VIEWS = frozenset({"v_movimientos", "v_gastos", "v_ingresos"})
FORBIDDEN_FUNCTIONS = frozenset({
    "pg_sleep", "set_config", "current_setting", "pg_read_file", "pg_ls_dir", "dblink", "lo_import", "lo_export",
    "pg_terminate_backend", "pg_cancel_backend", "copy",
})
USER_COLUMNS = frozenset({"user_id", "app.user_id"})


def check_reference_sql(sql: str) -> list[str]:
    """The rules the SQL breaks; empty when it is fine."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError as error:
        return [f"does not parse: {error}"]

    if len(statements) != 1:
        return [f"must be exactly one statement, found {len(statements)}"]

    root = statements[0]
    violations = []

    if not isinstance(root, exp.Select | exp.Union):
        return [f"must be a SELECT, not {type(root).__name__}"]
    if root.args.get("limit") is None and not _union_has_limit(root):
        violations.append("must have a LIMIT")

    ctes = {cte.alias_or_name for cte in root.find_all(exp.CTE)}
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


def _union_has_limit(root: exp.Expression) -> bool:
    return isinstance(root, exp.Union) and root.args.get("limit") is not None
