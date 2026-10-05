"""Acceptance criteria of ADR-002 (section "Criterios de aceptación") plus its tests 1-3.

Data (see sql/03_data.sql): user 1 has 3 movements, user 2 has 2, user 3 has 2.
Tests connect only as app_owner / app_reader, never as the superuser.
"""

import psycopg
import pytest

from lab_db import connect

TOTAL = 7
PER_USER = {1: 3, 2: 2, 3: 2}


def rows(role, user_id, sql, *, setting_local=True):
    """Run `sql` in one transaction as `role`, with app.user_id set when given.

    `user_id` may be an int, a string (to try odd values) or None (not set at all).
    """
    with connect(role) as conn:
        if user_id is not None:
            conn.execute(
                "SELECT set_config('app.user_id', %s, %s)", (str(user_id), setting_local)
            )
        return conn.execute(sql).fetchall()


def count(role, user_id, relation):
    return len(rows(role, user_id, f"SELECT * FROM {relation}"))


# ---------------------------------------------------------------------------
# ADR tests 1 and 2: direct RLS, no LLM involved
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user_id", [1, 2, 3])
def test_direct_rls_returns_only_own_rows(user_id):
    result = rows("app_reader", user_id, "SELECT DISTINCT user_id FROM transactions")
    assert result == [(user_id,)]
    assert count("app_reader", user_id, "transactions") == PER_USER[user_id]


@pytest.mark.parametrize("table", ["users", "accounts", "transactions"])
def test_every_user_table_is_isolated(table):
    for user_id in PER_USER:
        found = rows("app_reader", user_id, f"SELECT DISTINCT user_id FROM {table}")
        assert found == [(user_id,)]


def test_nonexistent_user_sees_nothing():
    assert count("app_reader", 999, "transactions") == 0


def test_fail_closed_without_variable():
    assert count("app_reader", None, "transactions") == 0


# ---------------------------------------------------------------------------
# Criterion 1: FORCE stops the owner from reading rows without the variable
# ---------------------------------------------------------------------------


def test_c1_force_blocks_owner_even_with_variable_set():
    # The policy is TO app_reader, so no policy applies to the owner: default deny.
    assert count("app_owner", None, "transactions") == 0
    assert count("app_owner", 1, "transactions") == 0


def test_c1_control_without_force_owner_sees_everything(fresh_lab):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("ALTER TABLE transactions NO FORCE ROW LEVEL SECURITY")
    assert count("app_owner", None, "transactions") == TOTAL


# ---------------------------------------------------------------------------
# Criterion 2: views with and without security_invoker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user_id", [1, 2, 3])
def test_c2_security_invoker_view_respects_rls(user_id):
    assert count("app_reader", user_id, "v_movimientos") == PER_USER[user_id]
    assert count("app_reader", None, "v_movimientos") == 0


def test_c2_view_without_invoker_is_safe_only_thanks_to_force():
    # The view runs as its owner (app_owner). FORCE subjects the owner to RLS and no
    # policy covers it, so the insecure view returns nothing instead of leaking.
    assert count("app_reader", 1, "v_movimientos_inseguro") == 0


def test_c2_view_without_invoker_leaks_when_force_is_removed(fresh_lab):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("ALTER TABLE transactions NO FORCE ROW LEVEL SECURITY")
    # The owner now bypasses RLS and the view runs with the owner's rights.
    assert count("app_reader", 1, "v_movimientos_inseguro") == TOTAL
    # The security_invoker view still filters, with or without FORCE.
    assert count("app_reader", 1, "v_movimientos") == PER_USER[1]


# ---------------------------------------------------------------------------
# Criterion 3 (and ADR test 3): set_config(..., true) does not outlive the transaction
# ---------------------------------------------------------------------------


def test_c3_local_setting_does_not_persist_on_reused_connection():
    with connect("app_reader") as conn:
        conn.execute("SELECT set_config('app.user_id', '1', true)")
        assert len(conn.execute("SELECT * FROM transactions").fetchall()) == PER_USER[1]
        conn.commit()

        # Same connection, new transaction, variable not set again.
        assert conn.execute("SELECT current_setting('app.user_id', true)").fetchone()[0] in (
            None,
            "",
        )
        assert conn.execute("SELECT * FROM transactions").fetchall() == []


def test_c3_control_session_setting_leaks_to_next_transaction():
    with connect("app_reader") as conn:
        conn.execute("SELECT set_config('app.user_id', '1', false)")
        conn.commit()

        # is_local = false survives COMMIT: this is the pool contamination the ADR avoids.
        leaked = conn.execute("SELECT * FROM transactions").fetchall()
        assert len(leaked) == PER_USER[1]


# ---------------------------------------------------------------------------
# Criterion 4: empty, absent or invalid variable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "0", "-1"])
def test_c4_missing_empty_or_unmatched_value_gives_zero_rows(value):
    assert count("app_reader", value, "transactions") == 0


def test_c4_non_numeric_value_fails_with_cast_error():
    # Still fails closed (no rows leak), but as an exception rather than an empty result.
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        rows("app_reader", "abc", "SELECT * FROM transactions")


# ---------------------------------------------------------------------------
# Criterion 5: app_reader cannot write, even trying to leave read-only mode
# ---------------------------------------------------------------------------

INSERT = "INSERT INTO transactions VALUES (99, 10, 1, '2026-09-09', 1, 'x')"


def attempt(statements, *, begin="BEGIN"):
    """Run statements in a transaction as app_reader; return the first error class or None."""
    with connect("app_reader", autocommit=True) as conn:
        conn.execute(begin)
        try:
            for statement in statements:
                conn.execute(statement)
        except psycopg.Error as error:
            return type(error)
        finally:
            conn.execute("ROLLBACK")
    return None


@pytest.mark.parametrize(
    "statement",
    [INSERT, "UPDATE transactions SET amount = 0", "DELETE FROM transactions"],
)
def test_c5_writes_fail_in_default_read_only_mode(statement):
    assert attempt([statement]) is psycopg.errors.ReadOnlySqlTransaction


@pytest.mark.parametrize(
    "switch, begin",
    [
        ("SET transaction_read_only = off", "BEGIN"),
        ("SET TRANSACTION READ WRITE", "BEGIN READ ONLY"),
    ],
)
def test_c5_read_only_mode_can_be_left_before_first_query_but_grants_block_writes(
    switch, begin
):
    # Documented finding: the mode switch itself succeeds before any query, so in that
    # window the only barrier is the missing INSERT privilege (GRANTs), not read-only mode.
    assert attempt([switch, INSERT], begin=begin) is psycopg.errors.InsufficientPrivilege


@pytest.mark.parametrize(
    "switch",
    [
        "SET TRANSACTION READ WRITE",
        "SELECT set_config('transaction_read_only', 'off', true)",
    ],
)
def test_c5_read_only_mode_is_locked_after_first_query(switch):
    # The executor's first statement is set_config(app.user_id), so this is the real flow.
    error = attempt(
        ["SELECT set_config('app.user_id', '1', true)", switch, INSERT], begin="BEGIN READ ONLY"
    )
    assert error is psycopg.errors.ActiveSqlTransaction


def test_c5_session_default_can_be_turned_off_but_grants_still_block_writes():
    # Documented finding: app_reader may reset default_transaction_read_only for its
    # session, which would persist on a pooled connection. Writes still fail on GRANTs.
    with connect("app_reader", autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = off")
        conn.execute("BEGIN")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(INSERT)
        conn.execute("ROLLBACK")


def test_c5_reader_cannot_assume_another_role():
    assert attempt(["SET ROLE app_owner"]) is psycopg.errors.InsufficientPrivilege
