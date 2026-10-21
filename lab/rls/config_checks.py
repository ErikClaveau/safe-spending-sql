"""Catalog checks that verify the RLS configuration stays in place (ADR-002, "Verificación continua").

Each check returns a list of human-readable violations; an empty list means it passes.
They only read the Postgres catalog, so any role can run them. Discovery is by
structure, not by a hand-kept list, so a new table with a `user_id` column or a new
view in the schema is checked automatically.
"""

import psycopg

SCHEMA = "app"
APP_READER = "app_reader"
USER_COLUMN = "user_id"
TRUE_VALUES = {"true", "on", "yes", "1", "t"}


def user_data_tables(conn: psycopg.Connection) -> list[str]:
    """Tables in the schema that carry a user_id column (i.e. user data)."""
    return [
        name
        for (name,) in conn.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
              AND a.attname = %s AND NOT a.attisdropped
            ORDER BY c.relname
            """,
            (SCHEMA, USER_COLUMN),
        )
    ]


def semantic_views(conn: psycopg.Connection) -> list[str]:
    """Every view in the schema: all of them are reachable by app_reader."""
    return [
        name
        for (name,) in conn.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relkind IN ('v', 'm')
            ORDER BY c.relname
            """,
            (SCHEMA,),
        )
    ]


def check_rls_enabled_and_forced(conn: psycopg.Connection) -> list[str]:
    violations = []
    for table, enabled, forced in conn.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relname = ANY(%s)
        ORDER BY c.relname
        """,
        (SCHEMA, user_data_tables(conn)),
    ):
        if not enabled:
            violations.append(f"{table}: row level security is not enabled")
        if not forced:
            violations.append(f"{table}: row level security is not forced")
    return violations


def check_policy_for_reader(conn: psycopg.Connection) -> list[str]:
    covered = {
        table
        for (table,) in conn.execute(
            """
            SELECT tablename
            FROM pg_policies
            WHERE schemaname = %s AND %s = ANY(roles) AND cmd IN ('SELECT', 'ALL')
            """,
            (SCHEMA, APP_READER),
        )
    }
    return [
        f"{table}: no SELECT policy for {APP_READER}"
        for table in user_data_tables(conn)
        if table not in covered
    ]


def check_views_security_invoker(conn: psycopg.Connection) -> list[str]:
    violations = []
    for view, options in conn.execute(
        """
        SELECT c.relname, c.reloptions
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind = 'v'
        ORDER BY c.relname
        """,
        (SCHEMA,),
    ):
        settings = dict(option.split("=", 1) for option in (options or []))
        if settings.get("security_invoker", "").lower() not in TRUE_VALUES:
            violations.append(f"{view}: view without security_invoker")
    return violations


def check_reader_role(conn: psycopg.Connection) -> list[str]:
    row = conn.execute(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = %s", (APP_READER,)
    ).fetchone()
    if row is None:
        return [f"{APP_READER}: role does not exist"]
    violations = []
    if row[0]:
        violations.append(f"{APP_READER}: is a superuser")
    if row[1]:
        violations.append(f"{APP_READER}: has BYPASSRLS")
    return violations


CHECKS = {
    "rls_enabled_and_forced": check_rls_enabled_and_forced,
    "policy_for_reader": check_policy_for_reader,
    "views_security_invoker": check_views_security_invoker,
    "reader_role": check_reader_role,
}


def run_all(conn: psycopg.Connection) -> dict[str, list[str]]:
    return {name: check(conn) for name, check in CHECKS.items()}
