import pytest

from safe_spending.clock import FixedClock
from safe_spending.db.query import run_as_user
from safe_spending.evals.golden import load_golden_set, to_table
from safe_spending.evals.golden.dataset import build_reference_database
from safe_spending.generator.config import configuration_hash, load_catalog, load_config
from safe_spending.generator.simulate import generate

REFERENCE_TEST_DB = "safe_spending_golden_test"  # its own database: no clash with the other test modules


@pytest.fixture(scope="session")
def golden():
    return load_golden_set()


@pytest.fixture(scope="session")
def reference_db():
    """The official dataset, built from scratch, in a database of its own."""
    build_reference_database(REFERENCE_TEST_DB)
    return REFERENCE_TEST_DB


@pytest.fixture(scope="session")
def config_hash():
    return configuration_hash()


@pytest.fixture(scope="session")
def dataset():
    """The same dataset in memory, to compute the truth by a route that does not use the views."""
    config = load_config()
    return generate(config, load_catalog(), FixedClock(config.reference_date))


@pytest.fixture(scope="session")
def run(reference_db):
    def _run(question, as_user=None):
        return to_table(run_as_user(as_user or question.user_id, question.reference_sql, dbname=reference_db))

    return _run


@pytest.fixture(scope="session")
def results(golden, run):
    """{question id: ResultTable} for every question that has a reference SQL."""
    return {question.id: run(question) for question in golden.answerable}
