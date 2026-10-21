"""The reference database: the official dataset, built from scratch in a database of its own.

Expected answers must not depend on whatever happens to be loaded in someone's development
database, so they are computed here: bootstrap, migrations, the dataset generated from the
committed configuration and its seed, loaded as `app_loader`. The same function serves the
command line and the tests (each with its own database name).
"""

import tempfile
from pathlib import Path

from safe_spending.clock import FixedClock
from safe_spending.db import loader
from safe_spending.db.bootstrap import bootstrap
from safe_spending.db.migrate import upgrade_to_head
from safe_spending.generator.config import configuration_hash, load_catalog, load_config
from safe_spending.generator.export import write_dataset
from safe_spending.generator.simulate import generate

GOLDEN_DATABASE = "safe_spending_golden"


def build_reference_database(dbname: str = GOLDEN_DATABASE) -> str:
    """Create `dbname`, migrate it and load the official dataset. Returns the configuration hash."""
    config = load_config()
    clock = FixedClock(today=config.reference_date)

    bootstrap(dbname=dbname)
    upgrade_to_head(dbname=dbname)

    with tempfile.TemporaryDirectory() as tmp:
        write_dataset(
            dataset=generate(
                config,
                load_catalog(),
                clock
            ),
            out_dir=Path(tmp),
            config=config,
            end=clock.today(),
            config_hash=configuration_hash()
        )
        loader.load(
            data_dir=Path(tmp),
            dbname=dbname,
            reset_first=True
        )

    return configuration_hash()
