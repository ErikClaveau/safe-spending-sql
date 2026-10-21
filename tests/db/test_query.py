"""`run_as_user`: the read-only, RLS-only way every query reaches the database (ADR-002)."""

import psycopg
import pytest

from conftest import TEST_DB
from safe_spending.db import settings
from safe_spending.db.exceptions import IdentityNotSetError
from safe_spending.db.query import run_as_user
from seed import add_tx, seed_base


@pytest.fixture(scope="module", autouse=True)
def two_users_with_movements(connect_module):
    with connect_module("app_loader") as conn:
        seed_base(conn)
        add_tx(conn, tx_id=1, account_id=10, user_id=1)
        add_tx(conn, tx_id=2, account_id=11, user_id=1, amount=-10, amount_eur=-10)
        add_tx(conn, tx_id=3, account_id=20, user_id=2, amount=-5, amount_eur=-5)
    yield
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute("TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories")


@pytest.fixture(scope="module")
def connect_module():
    def _connect(role):
        return settings.connect(role, TEST_DB)

    return _connect


def run(user_id, sql, **kwargs):
    return run_as_user(user_id, sql, dbname=TEST_DB, **kwargs)


# ---------------------------------------------------------------------------
# Isolation: only RLS, the SQL is run as it is
# ---------------------------------------------------------------------------


def test_each_user_gets_only_their_own_rows():
    assert {r[0] for r in run(1, "SELECT id_movimiento FROM v_movimientos").rows} == {1, 2}
    assert {r[0] for r in run(2, "SELECT id_movimiento FROM v_movimientos").rows} == {3}


def test_a_query_that_asks_for_everything_still_only_gets_the_users_rows():
    # No filter by user anywhere: this is what a prompt-injected query would look like.
    assert len(run(2, "SELECT * FROM v_movimientos ORDER BY id_movimiento LIMIT 1000").rows) == 1


def test_an_unknown_user_gets_nothing():
    assert run(999, "SELECT * FROM v_movimientos").rows == ()


def test_columns_and_rows_come_back_together():
    result = run(1, "SELECT id_movimiento, importe_eur FROM v_movimientos ORDER BY id_movimiento")
    assert result.columns == ("id_movimiento", "importe_eur")
    assert [row[0] for row in result.rows] == [1, 2] and not result.truncated


def test_the_identity_does_not_survive_the_call():
    run(1, "SELECT 1")
    with settings.connect(settings.APP_READER, TEST_DB) as conn:  # a fresh connection, nothing set
        assert conn.execute("SELECT count(*) FROM transactions").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# The user id is not text from anywhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user_id", ["1", "1 OR 1=1", None, 1.5, True, "1'; DROP TABLE users; --"])
def test_anything_but_an_integer_is_refused_before_the_database(user_id):
    with pytest.raises(TypeError, match="authentication layer"):
        run(user_id, "SELECT 1")


class ForgetfulConnection:
    """A connection on which `set_config` has no effect: the identity never reaches the session."""

    read_only = False

    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):  # same parameter names as psycopg's Connection.execute
        self.executed.append(query)

        class Row:
            def fetchone(self):
                return ("",)  # current_setting('app.user_id', true) is empty

        return Row()


def test_the_query_is_not_run_if_the_identity_did_not_take(monkeypatch):
    connection = ForgetfulConnection()
    monkeypatch.setattr(settings, "connect", lambda *args, **kwargs: connection)
    with pytest.raises(IdentityNotSetError, match="expected app.user_id = 1"):
        run_as_user(1, "SELECT * FROM v_movimientos")
    assert not any("v_movimientos" in sql for sql in connection.executed)  # the user's SQL never ran


# ---------------------------------------------------------------------------
# Read-only, locked by the identity statement that goes first
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO transactions VALUES (99, 10, 1, '2026-09-09', '2026-09-09', 1, 'EUR', NULL, 1, 'x', NULL, 'CARD_PURCHASE', 1, 1, NULL)",
        "UPDATE transactions SET amount = 0",
        "DELETE FROM transactions",
        "CREATE TABLE x (a int)",
    ],
)
def test_writes_fail(statement):
    with pytest.raises(psycopg.errors.Error):
        run(1, statement)


@pytest.mark.parametrize(
    "statement",
    ["SET TRANSACTION READ WRITE", "SELECT set_config('transaction_read_only', 'off', true)"],
)
def test_the_read_only_mode_cannot_be_left_after_the_identity_statement(statement):
    # The lab found that read-only mode can be left before the first query; the identity
    # statement is the first query, so by the time the SQL runs the mode is locked.
    with pytest.raises(psycopg.errors.ActiveSqlTransaction):
        run(1, statement)


def test_a_failed_query_leaves_nothing_behind():
    with pytest.raises(psycopg.errors.Error):
        run(1, "DELETE FROM transactions")
    assert len(run(1, "SELECT * FROM v_movimientos").rows) == 2


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------


def test_a_result_larger_than_the_cap_is_cut_and_flagged():
    result = run(1, "SELECT generate_series(1, 5000)", max_rows=10)
    assert len(result.rows) == 10 and result.truncated


def test_a_result_at_the_cap_is_not_flagged():
    result = run(1, "SELECT generate_series(1, 10)", max_rows=10)
    assert len(result.rows) == 10 and not result.truncated


def test_a_slow_query_is_cut_by_the_statement_timeout_of_the_role():
    with pytest.raises(psycopg.errors.QueryCanceled):
        run(1, "SELECT pg_sleep(30)")
