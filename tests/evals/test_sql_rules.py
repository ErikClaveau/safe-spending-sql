"""The golden set obeys the assistant's own validator. The rules and their negative controls are
tested where they live, in tests/pipeline/test_sqlglot_sql_validator.py."""

from safe_spending.evals.golden import ALLOWED_VIEWS, check_reference_sql


def test_the_reference_sql_of_every_question_follows_the_rules(golden):
    for q in golden.answerable:
        assert check_reference_sql(q.reference_sql) == [], q.id


def test_the_golden_set_uses_the_validators_view_list():
    assert ALLOWED_VIEWS == {"v_movimientos", "v_gastos", "v_ingresos"}


def test_a_broken_reference_sql_is_reported_as_a_list_of_violations():
    assert any("must have a LIMIT" in v for v in check_reference_sql("SELECT 1 FROM v_gastos"))
