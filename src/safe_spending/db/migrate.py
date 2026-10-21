"""Apply the migrations to a database from code (the CLI `alembic upgrade head` needs alembic.ini)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

SCRIPT_LOCATION = Path(__file__).parent / "alembic"


def upgrade_to_head(dbname: str) -> None:
    """Bring `dbname` to the latest revision, as `app_owner`. The database and roles must exist
    (see `safe_spending.db.bootstrap`)."""
    config = Config()
    config.set_main_option("script_location", str(SCRIPT_LOCATION))
    config.attributes["dbname"] = dbname
    command.upgrade(config, "head")
