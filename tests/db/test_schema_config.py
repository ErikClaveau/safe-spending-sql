"""ADR-002 configuration checks against the real schema, with a few negative controls.

The detection logic is exercised exhaustively in the RLS lab; here the point is that
the checks pass on the real migrations and still fail when the configuration breaks.
"""

import pytest

from safe_spending.db import config_checks


def violations(connect, check_name):
    with connect("app_owner") as conn:
        return config_checks.CHECKS[check_name](conn)


def test_discovery_finds_the_user_data_tables(connect):
    with connect("app_owner") as conn:
        assert config_checks.user_data_tables(conn) == ["accounts", "transactions", "users"]


@pytest.mark.parametrize("check_name", list(config_checks.CHECKS))
def test_real_schema_has_no_violations(connect, check_name):
    assert violations(connect, check_name) == []


def test_shared_catalogs_have_no_rls(connect):
    with connect("app_owner") as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relnamespace = 'app'::regnamespace AND relname IN ('categories', 'merchants')"
        ).fetchall()
    assert sorted(rows) == [("categories", False), ("merchants", False)]


def test_detects_force_removed(connect, remigrate):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("ALTER TABLE transactions NO FORCE ROW LEVEL SECURITY")
    assert violations(connect, "rls_enabled_and_forced") == [
        "transactions: row level security is not forced"
    ]


def test_detects_missing_policy(connect, remigrate):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("DROP POLICY aislamiento_usuario ON accounts")
    assert violations(connect, "policy_for_reader") == [
        "accounts: no SELECT policy for app_reader"
    ]


def test_detects_new_user_table_without_rls(connect, remigrate):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("CREATE TABLE budgets (budget_id integer PRIMARY KEY, user_id integer)")
    assert "budgets: row level security is not enabled" in violations(
        connect, "rls_enabled_and_forced"
    )


def test_detects_view_without_security_invoker(connect, remigrate):
    with connect("app_owner", autocommit=True) as conn:
        conn.execute("CREATE VIEW v_prueba AS SELECT tx_id FROM transactions")
    assert violations(connect, "views_security_invoker") == [
        "v_prueba: view without security_invoker"
    ]
