"""The validator's function allowlist and the direct attacks it exists for (week 4, ADR-005).

A blocklist let through `query_to_xml('SELECT ...')`, which runs text as SQL, and `dblink_exec`, because it
only knew `dblink`. These tests are the attacks that got through, so the rule cannot go back to a blocklist.
"""

import pytest

from safe_spending.pipeline.validation import ALLOWED_FUNCTIONS, adapters

validator = adapters.SqlglotSQLValidator()
LIMIT = " LIMIT 1"

# One expression per allowed function, written the way Postgres spells it.
SNIPPETS = {
    "sum": "SUM(gasto_eur)",
    "count": "COUNT(*)",
    "avg": "AVG(gasto_eur)",
    "min": "MIN(gasto_eur)",
    "max": "MAX(gasto_eur)",
    "stddev": "STDDEV(gasto_eur)",
    "stddev_pop": "STDDEV_POP(gasto_eur)",
    "stddev_samp": "STDDEV_SAMP(gasto_eur)",
    "variance": "VARIANCE(gasto_eur)",
    "variance_pop": "VAR_POP(gasto_eur)",
    "logical_and": "BOOL_AND(gasto_eur > 0)",
    "logical_or": "BOOL_OR(gasto_eur > 0)",
    "array_agg": "ARRAY_AGG(comercio)",
    "group_concat": "STRING_AGG(comercio, ',')",
    "percentile_cont": "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gasto_eur)",
    "percentile_disc": "PERCENTILE_DISC(0.5) WITHIN GROUP (ORDER BY gasto_eur)",
    "mode": "MODE() WITHIN GROUP (ORDER BY comercio)",
    "coalesce": "COALESCE(gasto_eur, 0)",
    "nullif": "NULLIF(gasto_eur, 0)",
    "greatest": "GREATEST(gasto_eur, 1)",
    "least": "LEAST(gasto_eur, 1)",
    "abs": "ABS(gasto_eur)",
    "round": "ROUND(gasto_eur, 2)",
    "ceil": "CEIL(gasto_eur)",
    "floor": "FLOOR(gasto_eur)",
    "trunc": "TRUNC(gasto_eur)",
    "sign": "SIGN(gasto_eur)",
    "power": "POWER(gasto_eur, 2)",
    "sqrt": "SQRT(gasto_eur)",
    "ln": "LN(gasto_eur)",
    "exp": "EXP(gasto_eur)",
    "length": "LENGTH(comercio)",
    "lower": "LOWER(comercio)",
    "upper": "UPPER(comercio)",
    "initcap": "INITCAP(comercio)",
    "trim": "TRIM(comercio)",
    "substring": "SUBSTRING(comercio, 1, 3)",
    "replace": "REPLACE(comercio, 'a', 'b')",
    "concat": "CONCAT(comercio, 'x')",
    "concat_ws": "CONCAT_WS(',', comercio, 'x')",
    "left": "LEFT(comercio, 2)",
    "right": "RIGHT(comercio, 2)",
    "split_part": "SPLIT_PART(comercio, ' ', 1)",
    "timestamp_trunc": "DATE_TRUNC('month', fecha)",
    "time_to_str": "TO_CHAR(fecha, 'YYYY-MM')",
    "extract": "EXTRACT(MONTH FROM fecha)",
    "str_to_date": "TO_DATE('2026-01-01', 'YYYY-MM-DD')",
    "make_date": "MAKE_DATE(2026, 1, 1)",
    "age": "AGE(fecha, fecha)",
    "cast": "fecha::date",
    "exploding_generate_series": "GENERATE_SERIES(1, 3)",
    "row_number": "ROW_NUMBER() OVER (ORDER BY fecha)",
    "rank": "RANK() OVER (ORDER BY fecha)",
    "dense_rank": "DENSE_RANK() OVER (ORDER BY fecha)",
    "lag": "LAG(gasto_eur) OVER (ORDER BY fecha)",
    "lead": "LEAD(gasto_eur) OVER (ORDER BY fecha)",
    "first_value": "FIRST_VALUE(gasto_eur) OVER (ORDER BY fecha)",
    "last_value": "LAST_VALUE(gasto_eur) OVER (ORDER BY fecha)",
    "ntile": "NTILE(4) OVER (ORDER BY fecha)",
    "case": "CASE WHEN gasto_eur > 0 THEN 1 ELSE 0 END",
    "if": "CASE WHEN gasto_eur > 0 THEN 1 ELSE 0 END",  # sqlglot builds a CASE from IFs
    "exists": "EXISTS (SELECT 1 FROM v_ingresos)",
    "and": "gasto_eur > 0 AND gasto_eur < 5",
    "or": "gasto_eur > 0 OR gasto_eur < 5",
    "regexp_like": "comercio ~ 'a'",
    "regexp_i_like": "comercio ~* 'a'",
}


def select(expression):
    return f"SELECT {expression} FROM v_gastos{LIMIT}"


def violations(sql):
    return validator.validate(sql).violations


def test_there_is_a_snippet_for_every_allowed_function_and_no_other():
    assert set(SNIPPETS) == ALLOWED_FUNCTIONS


@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_every_allowed_function_passes(name):
    assert violations(select(SNIPPETS[name])) == ()


@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_every_snippet_depends_on_its_entry(name, monkeypatch):
    """Take the name off the list and the snippet must fail: so the entry is spelled as sqlglot names it."""
    monkeypatch.setattr(
        adapters.sqlglot_sql_validator,
        "ALLOWED_FUNCTIONS",
        ALLOWED_FUNCTIONS - {name}
    )

    assert any(f"function {name} is not allowed" in v for v in violations(select(SNIPPETS[name])))


# Each of these got through the blocklist. The name is how sqlglot calls it.
FUNCTION_ATTACKS = {
    "query_to_xml('SELECT * FROM transactions', true, false, '')": "query_to_xml",  # SQL as text: skips the views
    "table_to_xml('transactions', true, false, '')": "table_to_xml",
    "cursor_to_xml('c', 1, true, false, '')": "cursor_to_xml",
    "dblink_exec('host=x', 'DROP TABLE a')": "dblink_exec",
    "dblink_connect('host=x')": "dblink_connect",
    "pg_read_binary_file('/etc/passwd')": "pg_read_binary_file",
    "pg_stat_file('/etc/passwd')": "pg_stat_file",
    "lo_get(1)": "lo_get",
    "pg_sleep(10)": "pg_sleep",
    "PG_SLEEP(10)": "pg_sleep",
    '"pg_sleep"(10)': "pg_sleep",
    "pg_catalog.pg_sleep(10)": "pg_sleep",
    "pg_advisory_lock(1)": "pg_advisory_lock",  # a session lock that outlives the query
    "txid_current()": "txid_current",
    "nextval('s')": "nextval",
    "setval('s', 1)": "setval",
    "set_config('app.user_id', '2', true)": "set_config",
    "current_setting('app.user_id')": "current_setting",
    "version()": "current_version",  # what the server is
    "current_user": "current_user",  # which role runs the query
    "session_user": "session_user",
    "current_database()": "current_database",
    "current_schema()": "current_schema",
    "inet_server_addr()": "inet_server_addr",
    "pg_backend_pid()": "pg_backend_pid",
    "has_table_privilege('transactions', 'select')": "has_table_privilege",
    "pg_get_userbyid(10)": "pg_get_userbyid",
    "now()": "current_timestamp",  # the date is the one the assistant is told, not the clock's
    "current_date": "current_date",
}


@pytest.mark.parametrize("expression, name", FUNCTION_ATTACKS.items())
def test_a_function_outside_the_allowlist_is_rejected_by_name(expression, name):
    assert f"function {name} is not allowed" in violations(select(expression))


@pytest.mark.parametrize("sql, expected", [
    ("SELECT * INTO newtab FROM v_gastos" + LIMIT, "SELECT INTO"),
    ("SELECT * FROM v_gastos FOR UPDATE" + LIMIT, "row locks"),
    ("SELECT * FROM v_gastos FOR SHARE" + LIMIT, "row locks"),
    ("WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT n FROM r" + LIMIT, "recursive"),
    ("SELECT * FROM pg_sleep(5)" + LIMIT, "pg_sleep is not allowed"),
    ("SELECT * FROM generate_series(1, 100000000)" + LIMIT, "is not a semantic view"),
    ("SELECT * FROM unnest(ARRAY[1, 2, 3])" + LIMIT, "is not allowed"),
    ("SELECT * FROM v_gastos, LATERAL (SELECT pg_sleep(1)) t" + LIMIT, "pg_sleep is not allowed"),
    ("WITH d AS (DELETE FROM transactions RETURNING *) SELECT * FROM d" + LIMIT, "not a semantic view"),
    ("EXPLAIN SELECT * FROM v_gastos" + LIMIT, "must be a SELECT"),
    ("COPY (SELECT * FROM v_gastos) TO '/tmp/x'", "must be a SELECT"),
    ("DO $$ BEGIN PERFORM 1; END $$", "must be a SELECT"),
    ("CALL p()", "must be a SELECT"),
    ("SHOW ALL", "must be a SELECT"),
    ("VALUES (1)", "must be a SELECT"),
])
def test_clauses_and_statements_that_do_more_than_read_are_rejected(sql, expected):
    assert any(expected in v for v in violations(sql)), violations(sql)


@pytest.mark.parametrize("sql", [
    "SELECT 1 FROM v_gastos LIMIT 1;",  # a trailing semicolon is one statement
    "SELECT $$user_id$$ FROM v_gastos LIMIT 1",  # a quoted string is text, not a column
    "SELECT * FROM v_gastos WHERE comercio = 'user_id' LIMIT 5",
    "SELECT * FROM (VALUES (1), (2)) t(a) JOIN v_gastos ON true LIMIT 5",
    "WITH transactions AS (SELECT 1 AS a) SELECT * FROM transactions LIMIT 5",  # a CTE of that name is not the table
    "SELECT generate_series(date '2025-01-01', date '2025-12-01', interval '1 month')::date AS mes LIMIT 12",
])
def test_harmless_sql_that_looks_odd_is_not_rejected(sql):
    assert violations(sql) == ()


def test_the_reference_sql_of_both_adversarial_and_golden_sets_still_passes():
    """The assistant's own rules are the golden set's: a stricter validator must not break its references."""
    from safe_spending.evals.adversarial import load_isolation_set
    from safe_spending.evals.golden import load_golden_set

    sql = [q.reference_sql for q in load_golden_set().questions if q.reference_sql]
    sql += [q.reference_sql for q in load_isolation_set().questions]

    assert len(sql) > 100
    assert [s for s in sql if violations(s)] == []
