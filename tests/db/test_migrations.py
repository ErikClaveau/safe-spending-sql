from alembic import command
from alembic.script import ScriptDirectory

from conftest import alembic_config

TABLES = {"accounts", "categories", "merchants", "transactions", "users"}
VIEWS = {"v_gastos", "v_ingresos", "v_movimientos"}


def schema_objects(connect, catalog, extra=""):
    with connect("app_owner") as conn:
        return {
            name
            for (name,) in conn.execute(
                f"SELECT table_name FROM information_schema.{catalog} WHERE table_schema = 'app' {extra}"
            )
            if name != "alembic_version"
        }


def schema_tables(connect):
    return schema_objects(connect, "tables", "AND table_type = 'BASE TABLE'")


def schema_views(connect):
    return schema_objects(connect, "views")


def test_database_is_at_head_revision(connect):
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with connect("app_owner") as conn:
        assert conn.execute("SELECT version_num FROM app.alembic_version").fetchone() == (head,)


def test_upgrade_creates_the_base_tables_and_semantic_views(connect):
    assert schema_tables(connect) == TABLES
    assert schema_views(connect) == VIEWS


def test_downgrade_and_upgrade_round_trip(connect):
    config = alembic_config()
    command.downgrade(config, "base")
    assert schema_tables(connect) == set()
    assert schema_views(connect) == set()
    command.upgrade(config, "head")
    assert schema_tables(connect) == TABLES
    assert schema_views(connect) == VIEWS


def test_downgrade_one_step_removes_only_the_semantic_layer(connect):
    config = alembic_config()
    command.downgrade(config, "0001")
    assert schema_tables(connect) == TABLES
    assert schema_views(connect) == set()
    command.upgrade(config, "head")
    assert schema_views(connect) == VIEWS


def test_there_is_a_single_head():
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1
