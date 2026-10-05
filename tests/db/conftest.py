from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from safe_spending.db import settings
from safe_spending.db.bootstrap import bootstrap

TEST_DB = "safe_spending_test"
REPO_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "src" / "safe_spending" / "db" / "alembic"))
    config.attributes["dbname"] = TEST_DB
    return config


def reset_database() -> None:
    """Drop the whole schema (also objects outside migrations) and migrate to head.

    A downgrade only removes what migrations created, so objects that a test adds on
    purpose (extra tables, views) would survive it.
    """
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute(f"DROP SCHEMA IF EXISTS {settings.SCHEMA} CASCADE")
    bootstrap(TEST_DB)
    command.upgrade(alembic_config(), "head")


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """A clean test database at the latest revision (the dev database is never touched)."""
    reset_database()


@pytest.fixture
def connect():
    """connect(role) -> psycopg connection to the test database."""

    def _connect(role: str, *, autocommit: bool = False):
        return settings.connect(role, TEST_DB, autocommit=autocommit)

    return _connect


@pytest.fixture
def remigrate():
    """For tests that break the configuration on purpose: restore it afterwards."""
    yield
    reset_database()
