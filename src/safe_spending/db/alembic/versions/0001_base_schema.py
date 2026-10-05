"""base schema: tables, row level security and grants

Revision ID: 0001
Revises:
Create Date: 2026-10-05
"""

from safe_spending.db.sqlfile import run_sql_file

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0001_base_schema.sql")


def downgrade() -> None:
    run_sql_file("0001_base_schema.down.sql")
