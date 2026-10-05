"""Alembic environment: online only, as app_owner, raw SQL (no SQLAlchemy models).

Target database: `-x dbname=<name>` on the command line, `Config.attributes["dbname"]`
when called from code (tests), or DB_NAME / the default in safe_spending/db/settings.py.
"""

from alembic import context
from sqlalchemy import create_engine, pool

from safe_spending.db import settings

config = context.config

if context.is_offline_mode():
    raise RuntimeError("Offline mode is not supported: migrations run raw SQL as app_owner.")

dbname = (
    config.attributes.get("dbname")
    or context.get_x_argument(as_dictionary=True).get("dbname")
    or settings.NAME
)

engine = create_engine(settings.sqlalchemy_url(settings.APP_OWNER, dbname), poolclass=pool.NullPool)

with engine.connect() as connection:
    # Be explicit instead of relying only on the per-database role setting.
    connection.exec_driver_sql(f"SET search_path TO {settings.SCHEMA}")
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=None,
        version_table_schema=settings.SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()
