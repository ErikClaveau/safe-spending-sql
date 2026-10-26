"""`PostgresSchemaProvider`: the prompt's view of the semantic layer comes from the database."""

import pytest

from conftest import TEST_DB
from safe_spending.db import settings
from safe_spending.db.exceptions import SchemaDocumentationError
from safe_spending.pipeline.schema import PostgresSchemaProvider
from seed import seed_base

VIEWS = {"v_gastos", "v_ingresos", "v_movimientos"}


@pytest.fixture(scope="module", autouse=True)
def categories():
    with settings.connect(settings.APP_LOADER, TEST_DB) as conn:
        seed_base(conn)
    yield
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute("TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories")


def get_schema():
    return PostgresSchemaProvider(dbname=TEST_DB).get_schema()


def view(name):
    return next(v for v in get_schema().views if v.name == name)


def test_exposes_exactly_the_three_semantic_views():
    assert {v.name for v in get_schema().views} == VIEWS


def test_every_view_and_column_carries_its_comment():
    with settings.connect(settings.APP_OWNER, TEST_DB) as conn:
        comment = conn.execute("SELECT obj_description('app.v_gastos'::regclass, 'pg_class')").fetchone()[0]
        column = conn.execute("SELECT col_description('app.v_gastos'::regclass, 4)").fetchone()[0]

    gastos = view("v_gastos")

    assert gastos.description == comment
    assert gastos.columns[3].description == column
    assert all(c.description and c.data_type for v in get_schema().views for c in v.columns)


def test_columns_keep_the_declared_order_and_never_expose_user_id():
    names = [c.name for c in view("v_gastos").columns]

    assert names[:3] == ["id_movimiento", "fecha", "gasto_eur"]
    assert all("user_id" not in c.name for v in get_schema().views for c in v.columns)


def test_categories_come_from_the_closed_catalog():
    assert [(c.name, c.group_name) for c in get_schema().categories] == [("Supermercados", "Alimentación")]


def test_version_is_stable_between_calls():
    assert get_schema().version == get_schema().version


def test_version_changes_when_a_comment_changes(remigrate):
    before = get_schema().version

    with settings.connect(settings.APP_OWNER, TEST_DB, autocommit=True) as conn:
        conn.execute("COMMENT ON VIEW app.v_gastos IS 'otra descripción'")

    assert get_schema().version != before


def test_a_column_without_comment_is_refused(remigrate):
    with settings.connect(settings.APP_OWNER, TEST_DB, autocommit=True) as conn:
        conn.execute("COMMENT ON COLUMN app.v_gastos.fecha IS NULL")

    with pytest.raises(SchemaDocumentationError, match="v_gastos.fecha"):
        get_schema()
