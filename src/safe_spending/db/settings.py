"""Connection settings for the assistant's database.

Everything comes from environment variables with development defaults, so the same
code runs locally and in CI. Role passwords default to the role name: development
only, localhost only.
"""

import os

import psycopg
from psycopg import Connection
from sqlalchemy.engine import URL

HOST = os.environ.get("DB_HOST", "127.0.0.1")
PORT = int(os.environ.get("DB_PORT", "5434"))
NAME = os.environ.get("DB_NAME", "safe_spending")
SCHEMA = "app"

ADMIN_USER = os.environ.get("DB_ADMIN_USER", "postgres")
ADMIN_PASSWORD = os.environ.get("DB_ADMIN_PASSWORD", "postgres")

APP_OWNER = "app_owner"
APP_LOADER = "app_loader"
APP_READER = "app_reader"
ROLES = (APP_OWNER, APP_LOADER, APP_READER)


def role_password(role: str) -> str:
    if role == ADMIN_USER:
        return ADMIN_PASSWORD
    return os.environ.get(f"DB_{role.upper()}_PASSWORD", role)


def connect(
        role: str,
        dbname: str | None = None,
        *,
        autocommit: bool = False
) -> Connection:
    """Open a psycopg connection as `role`."""
    return psycopg.connect(
        host=HOST,
        port=PORT,
        dbname=dbname or NAME,
        user=role,
        password=role_password(role),
        autocommit=autocommit,
    )


def sqlalchemy_url(
        role: str,
        dbname: str | None = None
) -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=role,
        password=role_password(role),
        host=HOST,
        port=PORT,
        database=dbname or NAME,
    )
