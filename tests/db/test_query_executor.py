"""`PostgresQueryExecutor`: model-written SQL that fails comes back as data; real bugs still raise."""

import pytest
from pydantic import ValidationError

from conftest import TEST_DB
from safe_spending.db import settings
from safe_spending.db.exceptions import IdentityNotSetError
from safe_spending.pipeline.execution import ExecutionErrorKind, ExecutionResult, PostgresQueryExecutor
from seed import add_tx, seed_base


@pytest.fixture(scope="module", autouse=True)
def two_users_with_movements():
    with settings.connect(settings.APP_LOADER, TEST_DB) as conn:
        seed_base(conn)
        add_tx(conn, tx_id=1, account_id=10, user_id=1)
        add_tx(conn, tx_id=2, account_id=11, user_id=1, amount=-10, amount_eur=-10)
        add_tx(conn, tx_id=3, account_id=20, user_id=2, amount=-5, amount_eur=-5)
    yield
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute("TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories")


def executor(**kwargs):
    return PostgresQueryExecutor(dbname=TEST_DB, **kwargs)


def test_a_query_runs_as_the_given_user_and_reports_its_latency():
    outcome = executor().execute(1, "SELECT id_movimiento FROM v_movimientos ORDER BY 1 LIMIT 10")

    assert outcome.ok
    assert [row[0] for row in outcome.result.rows] == [1, 2]
    assert outcome.error is None and outcome.error_kind is None
    assert outcome.latency_s >= 0


def test_the_user_only_sees_their_own_rows_without_any_filter():
    outcome = executor().execute(2, "SELECT id_movimiento FROM v_movimientos LIMIT 10")

    assert [row[0] for row in outcome.result.rows] == [3]


def test_the_row_cap_is_passed_down():
    outcome = executor(max_rows=1).execute(1, "SELECT id_movimiento FROM v_movimientos LIMIT 10")

    assert len(outcome.result.rows) == 1 and outcome.result.truncated


def test_sql_the_database_rejects_comes_back_as_a_database_error():
    outcome = executor().execute(1, "SELECT columna_que_no_existe FROM v_movimientos LIMIT 1")

    assert not outcome.ok
    assert outcome.error_kind is ExecutionErrorKind.DATABASE_ERROR
    assert "columna_que_no_existe" in outcome.error


def test_a_table_the_role_cannot_read_is_a_database_error_not_an_exception():
    outcome = executor().execute(1, "SELECT * FROM pg_authid LIMIT 1")

    assert outcome.error_kind is ExecutionErrorKind.DATABASE_ERROR


def test_a_slow_query_comes_back_as_a_timeout():
    outcome = executor().execute(1, "SELECT pg_sleep(30)")

    assert outcome.error_kind is ExecutionErrorKind.TIMEOUT
    assert outcome.latency_s < 15


def test_a_bad_user_id_is_a_bug_and_still_raises():
    with pytest.raises(TypeError):
        executor().execute("1", "SELECT 1")  # type: ignore[arg-type]


def test_an_execution_has_either_rows_or_an_error():
    with pytest.raises(ValidationError):
        ExecutionResult(latency_s=0.1)

    with pytest.raises(ValidationError):
        ExecutionResult(error="x", latency_s=0.1)  # an error needs its kind
