"""The loader: generated Parquet -> Postgres as app_loader, with the manifest verified first.

The loaded data is then checked through the real semantic views, which is the first time
the generator and the schema meet.
"""

import shutil
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from conftest import TEST_DB
from safe_spending.clock import FixedClock
from safe_spending.db import loader, settings
from safe_spending.db.exceptions import ManifestError
from safe_spending.generator.config import configuration_hash, load_catalog, load_config
from safe_spending.generator.export import write_dataset
from safe_spending.generator.simulate import generate

N_USERS = 4
OPERATIONAL = ("categories", "merchants", "users", "accounts", "transactions")


def admin():
    return settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True)


def wipe():
    with admin() as conn:
        conn.execute("TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories")


def count_rows(table):
    with admin() as conn:  # the superuser bypasses RLS: it sees every row
        return conn.execute(f"SELECT count(*) FROM app.{table}").fetchone()[0]


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    config = load_config().model_copy(update={"n_users": N_USERS})
    clock = FixedClock(date(2026, 9, 15))
    path = tmp_path_factory.mktemp("dataset")
    write_dataset(generate(config, load_catalog(), clock), path, config, clock.today(), configuration_hash())
    return path


@pytest.fixture
def clean_database():
    wipe()
    yield
    wipe()


@pytest.fixture
def loaded(data_dir, clean_database):
    return loader.load(data_dir, dbname=TEST_DB, reset_first=True)


def reader_rows(user_id, sql):
    with settings.connect(settings.APP_READER, TEST_DB) as conn:
        conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        return conn.execute(sql).fetchall()


def test_loads_every_operational_table(loaded):
    assert set(loaded) == set(OPERATIONAL)
    assert loaded["users"] == N_USERS
    for table, rows in loaded.items():
        assert count_rows(table) == rows > 0


def test_labels_never_reach_the_application_database(loaded):
    with admin() as conn:
        tables = {r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'app'")}
    assert not {"tx_labels", "user_labels", "scenarios"} & tables
    # The loader only knows the five operational tables, whatever else is in the folder.
    assert set(loader.OPERATIONAL) == set(OPERATIONAL)


def test_each_user_sees_only_their_own_movements(loaded):
    for user_id in range(1, N_USERS + 1):
        ids = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_movimientos")}
        assert ids and {i // 1_000_000 for i in ids} == {user_id}


def test_generated_data_satisfies_the_single_view_invariant(loaded):
    for user_id in range(1, N_USERS + 1):
        everything = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_movimientos")}
        gastos = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_gastos")}
        ingresos = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_ingresos")}
        assert gastos & ingresos == set()
        assert gastos | ingresos == everything  # slice 1 has no internal transfers yet


def test_income_minus_spending_equals_the_balance_change_on_generated_data(loaded):
    for user_id in range(1, N_USERS + 1):
        balance, = reader_rows(user_id, "SELECT SUM(importe_eur) FROM v_movimientos")[0]
        income, = reader_rows(user_id, "SELECT SUM(ingreso_eur) FROM v_ingresos")[0]
        spending, = reader_rows(user_id, "SELECT SUM(gasto_eur) FROM v_gastos")[0]
        assert balance == income - spending
        assert income > spending > Decimal(0)


def test_people_are_not_in_the_shared_merchant_catalog(loaded):
    with admin() as conn:
        landlords = {r[0] for r in conn.execute("SELECT DISTINCT counterparty FROM app.transactions WHERE tx_code = 'TRANSFER_OUT'")}
        merchants = {r[0] for r in conn.execute("SELECT normalized_name FROM app.merchants")}
    assert landlords and landlords.isdisjoint(merchants)


def test_loading_twice_without_reset_fails_and_leaves_the_data_untouched(loaded, data_dir):
    before = {t: count_rows(t) for t in OPERATIONAL}
    with pytest.raises(psycopg.errors.UniqueViolation):
        loader.load(data_dir, dbname=TEST_DB)
    assert {t: count_rows(t) for t in OPERATIONAL} == before


def test_reset_allows_reloading(loaded, data_dir):
    again = loader.load(data_dir, dbname=TEST_DB, reset_first=True)
    assert again == loaded


# ---------------------------------------------------------------------------
# Manifest verification: a corrupted or incomplete dataset never reaches the database
# ---------------------------------------------------------------------------


@pytest.fixture
def copy_of_dataset(data_dir, tmp_path):
    target = tmp_path / "copy"
    shutil.copytree(data_dir, target)
    return target


def test_a_modified_file_is_rejected_before_loading(copy_of_dataset, clean_database):
    path = copy_of_dataset / "operational" / "users.parquet"
    path.write_bytes(path.read_bytes() + b"\x00")
    with pytest.raises(ManifestError, match="users.parquet does not match"):
        loader.load(copy_of_dataset, dbname=TEST_DB, reset_first=True)
    assert count_rows("users") == 0


def test_a_missing_file_is_rejected(copy_of_dataset, clean_database):
    (copy_of_dataset / "operational" / "merchants.parquet").unlink()
    with pytest.raises(ManifestError, match="merchants.parquet is missing"):
        loader.load(copy_of_dataset, dbname=TEST_DB)


def test_a_missing_manifest_is_rejected(copy_of_dataset, clean_database):
    (copy_of_dataset / "manifest.json").unlink()
    with pytest.raises(ManifestError, match="no manifest.json"):
        loader.load(copy_of_dataset, dbname=TEST_DB)


def test_a_malformed_manifest_is_rejected(copy_of_dataset, clean_database):
    (copy_of_dataset / "manifest.json").write_text('{"seed": "not a number"}', encoding="utf-8")
    with pytest.raises(ManifestError, match="manifest.json is not valid"):
        loader.load(copy_of_dataset, dbname=TEST_DB)


def test_the_loader_role_cannot_read_what_it_loaded(loaded):
    # app_loader has INSERT only (ADR-002): it is a write-only door into the database.
    with settings.connect(settings.APP_LOADER, TEST_DB) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM transactions")
