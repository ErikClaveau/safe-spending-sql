"""Phase 3: catalog configuration checks, each with a negative control.

A check that has never failed proves nothing, so every check is also run against a
configuration broken on purpose and must report the violation.
"""

import pytest

import config_checks
from lab_db import connect


def violations(check_name):
    with connect("app_owner") as conn:
        return config_checks.CHECKS[check_name](conn)


def as_owner(sql):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute(sql)


def as_superuser(sql):
    # Only to break role attributes on purpose; never used to assert anything.
    with connect("postgres", autocommit=True) as conn:
        conn.execute(sql)


# ---------------------------------------------------------------------------
# Baseline: the real configuration passes, and discovery is not vacuous
# ---------------------------------------------------------------------------


def test_discovery_finds_the_expected_objects():
    with connect("app_owner") as conn:
        assert config_checks.user_data_tables(conn) == ["accounts", "transactions", "users"]
        assert config_checks.semantic_views(conn) == ["v_movimientos"]


@pytest.mark.parametrize("check_name", list(config_checks.CHECKS))
def test_baseline_configuration_has_no_violations(check_name):
    assert violations(check_name) == []


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------


def test_detects_row_level_security_not_forced(fresh_lab):
    as_owner("ALTER TABLE transactions NO FORCE ROW LEVEL SECURITY")
    assert violations("rls_enabled_and_forced") == [
        "transactions: row level security is not forced"
    ]


def test_detects_row_level_security_disabled(fresh_lab):
    as_owner("ALTER TABLE accounts DISABLE ROW LEVEL SECURITY")
    assert "accounts: row level security is not enabled" in violations(
        "rls_enabled_and_forced"
    )


def test_detects_new_user_table_without_rls(fresh_lab):
    # ADR consequence: every new table with user data needs user_id, forced RLS and a policy.
    as_owner("CREATE TABLE budgets (budget_id integer PRIMARY KEY, user_id integer NOT NULL)")
    assert "budgets: row level security is not enabled" in violations("rls_enabled_and_forced")
    assert "budgets: no SELECT policy for app_reader" in violations("policy_for_reader")


def test_detects_missing_policy(fresh_lab):
    as_owner("DROP POLICY aislamiento_usuario ON transactions")
    assert violations("policy_for_reader") == ["transactions: no SELECT policy for app_reader"]


def test_detects_policy_for_another_role(fresh_lab):
    as_owner("DROP POLICY aislamiento_usuario ON users")
    as_owner(
        "CREATE POLICY aislamiento_usuario ON users FOR SELECT TO app_owner USING (true)"
    )
    assert violations("policy_for_reader") == ["users: no SELECT policy for app_reader"]


def test_detects_view_created_without_security_invoker(fresh_lab):
    as_owner("CREATE VIEW v_gastos AS SELECT tx_id, amount FROM transactions")
    assert violations("views_security_invoker") == ["v_gastos: view without security_invoker"]


def test_detects_security_invoker_removed_from_existing_view(fresh_lab):
    as_owner("ALTER VIEW v_movimientos RESET (security_invoker)")
    assert violations("views_security_invoker") == [
        "v_movimientos: view without security_invoker"
    ]


def test_detects_security_invoker_explicitly_off(fresh_lab):
    as_owner("ALTER VIEW v_movimientos SET (security_invoker = false)")
    assert violations("views_security_invoker") == [
        "v_movimientos: view without security_invoker"
    ]


def test_detects_reader_with_bypassrls(fresh_lab):
    as_superuser("ALTER ROLE app_reader BYPASSRLS")
    assert violations("reader_role") == ["app_reader: has BYPASSRLS"]


def test_detects_reader_superuser(fresh_lab):
    as_superuser("ALTER ROLE app_reader SUPERUSER")
    assert violations("reader_role") == ["app_reader: is a superuser"]


def test_detects_missing_reader_role(fresh_lab):
    as_superuser("DROP OWNED BY app_reader")
    as_superuser("DROP ROLE app_reader")
    assert violations("reader_role") == ["app_reader: role does not exist"]
