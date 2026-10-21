"""The static rules of the reference SQL (the seed of the week-4 validator), with negative controls:
a rule that has never rejected anything proves nothing."""

import pytest

from safe_spending.evals.golden import ALLOWED_VIEWS, check_reference_sql

GOOD = "SELECT SUM(gasto_eur) AS total FROM v_gastos WHERE fecha >= '2026-01-01' LIMIT 1"


def test_the_reference_sql_of_every_question_follows_the_rules(golden):
    for q in golden.answerable:
        assert check_reference_sql(q.reference_sql) == [], q.id


def test_the_views_are_exactly_the_semantic_layer():
    assert ALLOWED_VIEWS == {"v_movimientos", "v_gastos", "v_ingresos"}


@pytest.mark.parametrize(
    "sql",
    [
        GOOD,
        "SELECT a.fecha FROM v_gastos a JOIN v_gastos b ON a.comercio = b.comercio LIMIT 5",
        "WITH m AS (SELECT fecha, gasto_eur FROM v_gastos) SELECT SUM(gasto_eur) FROM m LIMIT 1",
        "SELECT mes FROM (SELECT to_char(fecha, 'YYYY-MM') AS mes FROM v_ingresos) t GROUP BY mes LIMIT 12",
        "SELECT 1 FROM v_movimientos UNION ALL SELECT 2 FROM v_gastos LIMIT 3",
    ],
)
def test_valid_sql_passes(sql):
    assert check_reference_sql(sql) == []


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT * FROM transactions LIMIT 5", "not a semantic view"),
        ("SELECT * FROM users LIMIT 5", "not a semantic view"),
        ("SELECT * FROM pg_catalog.pg_roles LIMIT 5", "schema-qualified"),
        ("SELECT * FROM app.v_gastos LIMIT 5", "schema-qualified"),
        ("SELECT * FROM information_schema.tables LIMIT 5", "schema-qualified"),
        ("SELECT SUM(gasto_eur) FROM v_gastos", "must have a LIMIT"),
        ("SELECT a FROM v_gastos UNION ALL SELECT a FROM v_ingresos", "must have a LIMIT"),
        ("SELECT * FROM v_gastos WHERE user_id = 1 LIMIT 5", "must not mention user_id"),
        ("SELECT user_id FROM v_gastos LIMIT 5", "must not mention user_id"),
        ("SELECT pg_sleep(10) FROM v_gastos LIMIT 1", "pg_sleep is forbidden"),
        ("SELECT set_config('app.user_id', '2', true) FROM v_gastos LIMIT 1", "set_config is forbidden"),
        ("SELECT current_setting('app.user_id') FROM v_gastos LIMIT 1", "current_setting is forbidden"),
        ("DELETE FROM v_gastos", "must be a SELECT"),
        ("INSERT INTO v_gastos SELECT * FROM v_gastos", "must be a SELECT"),
        ("UPDATE v_gastos SET gasto_eur = 0", "must be a SELECT"),
        ("DROP TABLE transactions", "must be a SELECT"),
        ("SET app.user_id = 2", "must be a SELECT"),
        ("SELECT 1 FROM v_gastos LIMIT 1; DROP TABLE users", "exactly one statement"),
        ("SELECT 1 FROM v_gastos LIMIT 1; SELECT 2 FROM v_ingresos LIMIT 1", "exactly one statement"),
        ("SELEC nothing FROM", "does not parse"),
    ],
)
def test_sql_that_breaks_a_rule_is_rejected_for_the_right_reason(sql, expected):
    violations = check_reference_sql(sql)
    assert any(expected in v for v in violations), violations


def test_a_comment_cannot_hide_a_forbidden_table():
    assert check_reference_sql("SELECT 1 FROM v_gastos /* harmless */, transactions LIMIT 1")


def test_several_violations_are_all_reported():
    violations = check_reference_sql("SELECT * FROM transactions WHERE user_id = 1")
    assert len(violations) >= 3  # no LIMIT, not a view, user_id
