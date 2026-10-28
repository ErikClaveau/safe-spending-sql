"""documentation round 2: a trip abroad is the payments in another currency

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28
"""

from safe_spending.db.sqlfile import run_sql_file

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0004_comments_round2.sql")


def downgrade() -> None:
    run_sql_file("0004_comments_round2.down.sql")
