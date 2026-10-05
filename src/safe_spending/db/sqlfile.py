"""Run raw SQL files from migration revisions.

Autogenerate cannot express RLS, policies, `security_invoker` views or `COMMENT ON`,
so migrations are hand-written SQL kept in safe_spending/db/alembic/sql/ and read by each revision.
"""

from pathlib import Path

from alembic import op

SQL_DIR = Path(__file__).parent / "alembic" / "sql"


def run_sql_file(name: str) -> None:
    op.get_bind().exec_driver_sql((SQL_DIR / name).read_text(encoding="utf-8"))
