"""documentation round 1: comments the assistant was missing (merchants, fees, savings, purchases)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26
"""

from safe_spending.db.sqlfile import run_sql_file

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0003_comments_round1.sql")


def downgrade() -> None:
    run_sql_file("0003_comments_round1.down.sql")
