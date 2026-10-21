"""semantic views: v_movimientos, v_gastos, v_ingresos

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06
"""

from safe_spending.db.sqlfile import run_sql_file

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0002_semantic_views.sql")


def downgrade() -> None:
    run_sql_file("0002_semantic_views.down.sql")
