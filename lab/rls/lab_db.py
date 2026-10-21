"""Helpers to build and connect to the lab database.

Run `uv run python lab/rls/lab_db.py` to (re)build the schema and data.
Tests must connect only through `connect()` with a non-superuser role.
"""

from pathlib import Path

import psycopg

HOST = "127.0.0.1"
PORT = 5433
DBNAME = "lab_rls"
SQL_DIR = Path(__file__).parent / "sql"

# Each script runs as the role that would own that step in the real project.
# Only the first one needs the superuser (creating roles); tests never do.
SCRIPTS = [
    ("01_roles.sql", "postgres"),
    ("02_schema.sql", "app_owner"),
    ("03_data.sql", "app_loader"),
]

# Lab-only passwords: every role's password equals its name.
PASSWORDS = {"postgres": "postgres"}


def connect(role: str, *, autocommit: bool = False) -> psycopg.Connection:
    """Open a connection as `role`. Tests must never ask for the superuser."""
    password = PASSWORDS.get(role, role)
    return psycopg.connect(
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        user=role,
        password=password,
        autocommit=autocommit,
    )


def build() -> None:
    """Drop and recreate schema, roles' settings and data from the sql/ scripts."""
    for filename, role in SCRIPTS:
        sql = (SQL_DIR / filename).read_text(encoding="utf-8")
        with connect(role, autocommit=True) as conn:
            conn.execute(sql)
        print(f"ok  {filename} as {role}")


if __name__ == "__main__":
    build()
