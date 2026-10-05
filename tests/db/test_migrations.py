from alembic import command
from alembic.script import ScriptDirectory

from conftest import TEST_DB, alembic_config

TABLES = {"accounts", "categories", "merchants", "transactions", "users"}


def schema_tables(connect):
    with connect("app_owner") as conn:
        return {
            name
            for (name,) in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'app'"
            )
            if name != "alembic_version"
        }


def test_database_is_at_head_revision(connect):
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with connect("app_owner") as conn:
        assert conn.execute("SELECT version_num FROM app.alembic_version").fetchone() == (head,)


def test_upgrade_creates_the_base_tables(connect):
    assert schema_tables(connect) == TABLES


def test_downgrade_and_upgrade_round_trip(connect):
    config = alembic_config()
    command.downgrade(config, "base")
    assert schema_tables(connect) == set()
    command.upgrade(config, "head")
    assert schema_tables(connect) == TABLES


def test_there_is_a_single_head():
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1
