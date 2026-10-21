"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from safe_spending.db.sqlfile import run_sql_file

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("${up_revision}_<name>.sql")


def downgrade() -> None:
    run_sql_file("${up_revision}_<name>.down.sql")
