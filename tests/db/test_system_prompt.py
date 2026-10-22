"""The system prompt rendered from the real semantic layer, not from a hand-made schema."""

from datetime import date

import pytest

from conftest import TEST_DB
from safe_spending.db import settings
from safe_spending.pipeline.generation import render_system_prompt
from safe_spending.pipeline.schema import PostgresSchemaProvider
from seed import seed_base


@pytest.fixture(scope="module", autouse=True)
def categories():
    with settings.connect(settings.APP_LOADER, TEST_DB) as conn:
        seed_base(conn)
    yield
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute("TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories")


def test_every_view_and_column_of_the_database_reaches_the_prompt():
    schema = PostgresSchemaProvider(dbname=TEST_DB).get_schema()

    prompt = render_system_prompt(schema, date(2026, 9, 15))

    for view in schema.views:
        assert f"### {view.name}" in prompt
        assert view.description in prompt
        for column in view.columns:
            assert f"`{column.name}`" in prompt
            assert column.description in prompt
    assert "- Alimentación: Supermercados" in prompt
    assert "user_id" not in prompt
