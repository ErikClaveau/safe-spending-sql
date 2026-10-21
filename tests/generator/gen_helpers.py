"""Shared helpers for the generator tests: small, fast datasets built in memory or on disk."""

from datetime import date
from pathlib import Path

from safe_spending.clock import FixedClock
from safe_spending.generator.config import configuration_hash, load_catalog, load_config
from safe_spending.generator.export import write_dataset
from safe_spending.generator.simulate import Dataset, generate
from safe_spending.schemas import Manifest

REFERENCE = date(2026, 9, 15)


def build(n_users: int = 6, *, seed: int | None = None, today: date = REFERENCE) -> tuple:
    """(config, catalog, dataset) for a small population, using a fixed clock."""
    config = load_config().model_copy(update={"n_users": n_users})
    if seed is not None:
        config = config.model_copy(update={"seed": seed})
    catalog = load_catalog()
    return config, catalog, generate(config, catalog, FixedClock(today))


def write(out_dir: Path, n_users: int = 6) -> Manifest:
    config, _, dataset = build(n_users)
    return write_dataset(dataset, out_dir, config, REFERENCE, configuration_hash())
