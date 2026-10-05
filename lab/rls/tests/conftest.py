import sys
from pathlib import Path

import pytest

# lab_db.py lives one level above tests/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lab_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def lab_database():
    """Build the schema and data once per test session."""
    lab_db.build()


@pytest.fixture
def fresh_lab():
    """For tests that break the configuration on purpose: rebuild before and after."""
    lab_db.build()
    yield
    lab_db.build()
