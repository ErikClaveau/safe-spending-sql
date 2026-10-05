"""One-off setup that migrations cannot do: database, roles and the empty schema.

Roles are cluster-level objects and need a superuser, while migrations run as
`app_owner` (ADR-002). Idempotent: running it again repairs role attributes.

    uv run safe-spending-bootstrap
"""

from psycopg import sql

from safe_spending.db import settings


def ensure_database(dbname: str) -> None:
    with settings.connect(
            role=settings.ADMIN_USER,
            dbname="postgres",
            autocommit=True
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))


def ensure_roles() -> None:
    with settings.connect(
            role=settings.ADMIN_USER,
            dbname="postgres",
            autocommit=True
    ) as conn:
        for role in settings.ROLES:
            password = sql.Literal(settings.role_password(role))
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(
                sql.SQL(f"{verb} ROLE {{}} LOGIN PASSWORD {{}}").format(sql.Identifier(role), password)
            )

        # Explicit attributes, so a re-run also repairs a role that was tampered with.
        conn.execute("ALTER ROLE app_owner  NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB")
        conn.execute("ALTER ROLE app_loader NOSUPERUSER BYPASSRLS   NOCREATEROLE NOCREATEDB")
        conn.execute("ALTER ROLE app_reader NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB")

        # app_reader is read-only by default and bounded in time, set on the role (ADR-002).
        conn.execute("ALTER ROLE app_reader SET default_transaction_read_only = on")
        conn.execute("ALTER ROLE app_reader SET statement_timeout = '5s'")


def ensure_schema(dbname: str) -> None:
    schema = sql.Identifier(settings.SCHEMA)
    with settings.connect(settings.ADMIN_USER, dbname, autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION app_owner").format(schema)
        )
        for role in settings.ROLES:
            conn.execute(
                sql.SQL("ALTER ROLE {} IN DATABASE {} SET search_path = {}").format(
                    sql.Identifier(role), sql.Identifier(dbname), schema
                )
            )


def bootstrap(dbname: str | None = None) -> None:
    dbname = dbname or settings.NAME
    ensure_database(dbname)
    ensure_roles()
    ensure_schema(dbname)


def main() -> None:
    bootstrap()
    print(f"ok  database {settings.NAME}, roles and schema {settings.SCHEMA}")


if __name__ == "__main__":
    main()
