"""The loader: generated Parquet -> Postgres as app_loader, with the manifest verified first.

The loaded data is then checked through the real semantic views, which is the first time
the generator and the schema meet.
"""

import json
import shutil
from datetime import date
from decimal import Decimal

import psycopg
import pyarrow.parquet as pq
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
        # Not `income > spending`: the recent-sign-up user has a few weeks of history, without
        # the extra pays, so they can legitimately spend more than they earn in that window.
        assert income > Decimal(0) and spending > Decimal(0)


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


# ---------------------------------------------------------------------------
# Injection traps reach the database as ordinary incoming movements (design 5.6)
# ---------------------------------------------------------------------------

TRAP_USERS = range(16, 21)
N_USERS_WITH_TRAPS = 20


@pytest.fixture(scope="module")
def trap_data_dir(tmp_path_factory):
    config = load_config().model_copy(update={"n_users": N_USERS_WITH_TRAPS})
    clock = FixedClock(date(2026, 9, 15))
    path = tmp_path_factory.mktemp("dataset_with_traps")
    write_dataset(generate(config, load_catalog(), clock), path, config, clock.today(), configuration_hash())
    return path


@pytest.fixture
def trap_canaries(trap_data_dir, clean_database):
    """{user_id: [canary, ...]} read from the labels, after loading the dataset."""
    loader.load(trap_data_dir, dbname=TEST_DB, reset_first=True)
    canaries = {}
    for label in pq.read_table(trap_data_dir / "labels" / "tx_labels.parquet").to_pylist():
        if label["is_trap"]:
            canaries.setdefault(label["tx_id"] // 1_000_000, []).append((label["tx_id"], label["canary"]))
    return canaries


def test_the_traps_were_generated_for_the_adversarial_users_only(trap_canaries):
    assert set(trap_canaries) == set(TRAP_USERS)


def test_every_trap_is_in_its_owners_income_and_nowhere_in_spending(trap_canaries):
    for user_id, traps in trap_canaries.items():
        income = dict(reader_rows(user_id, "SELECT id_movimiento, concepto FROM v_ingresos"))
        spending = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_gastos")}
        for tx_id, canary in traps:
            assert canary in income[tx_id]
            assert tx_id not in spending


def test_a_trap_counts_as_income_for_its_owner(trap_canaries):
    for user_id, traps in trap_canaries.items():
        amounts = dict(reader_rows(user_id, "SELECT id_movimiento, ingreso_eur FROM v_ingresos"))
        assert all(Decimal(1) <= amounts[tx_id] <= Decimal(20) for tx_id, _ in traps)


def test_no_user_can_read_another_users_canary(trap_canaries):
    for user_id, traps in trap_canaries.items():
        functional_user = 1
        other_adversarial_user = 16 if user_id != 16 else 17
        for other in (functional_user, other_adversarial_user):
            visible = " ".join(r[0] for r in reader_rows(other, "SELECT concepto FROM v_movimientos"))
            assert not any(canary in visible for _, canary in traps)


def test_a_user_without_traps_sees_no_canary_at_all(trap_canaries):
    for user_id in (1, 8, 15):
        concepts = [r[0] for r in reader_rows(user_id, "SELECT concepto FROM v_movimientos")]
        assert not any("CNR" in c for c in concepts)


# ---------------------------------------------------------------------------
# Foreign currency, exchange fees and refunds through the semantic views
# ---------------------------------------------------------------------------

N_USERS_WITH_SCENARIOS = 7  # user 6 is the London trip and user 7 the Amazon refunds


@pytest.fixture(scope="module")
def scenario_data_dir(tmp_path_factory):
    config = load_config().model_copy(update={"n_users": N_USERS_WITH_SCENARIOS})
    clock = FixedClock(date(2026, 9, 15))
    path = tmp_path_factory.mktemp("dataset_with_scenarios")
    write_dataset(generate(config, load_catalog(), clock), path, config, clock.today(), configuration_hash())
    return path


@pytest.fixture
def scenarios_loaded(scenario_data_dir, clean_database):
    loader.load(scenario_data_dir, dbname=TEST_DB, reset_first=True)
    params = {
        row["type"]: json.loads(row["params"])
        for row in pq.read_table(scenario_data_dir / "labels" / "scenarios.parquet").to_pylist()
    }
    labels = pq.read_table(scenario_data_dir / "labels" / "tx_labels.parquet").to_pylist()
    return params, labels


def test_pounds_and_their_exchange_rate_load_and_show_in_the_views(scenarios_loaded):
    london = scenarios_loaded[0]["london_trip"]
    with admin() as conn:  # the CHECK constraints accepted every foreign-currency row
        assert conn.execute(
            "SELECT count(*) FROM app.transactions WHERE currency = 'GBP' AND exchange_rate > 0 AND user_id = 6"
        ).fetchone()[0] == london["n_purchases"]
    rows = reader_rows(6, "SELECT divisa_original, importe_original, importe_eur FROM v_movimientos WHERE divisa_original <> 'EUR'")
    assert len(rows) == london["n_purchases"] and {r[0] for r in rows} == {"GBP"}
    assert all(original < 0 and euros < 0 for _, original, euros in rows)


def test_the_trip_totals_in_the_views_match_the_scenario_truth(scenarios_loaded):
    london = scenarios_loaded[0]["london_trip"]
    spent, in_pounds = reader_rows(6, "SELECT SUM(gasto_eur), SUM(gasto_original) FROM v_gastos WHERE divisa_original = 'GBP'")[0]
    fees, = reader_rows(6, "SELECT SUM(gasto_eur) FROM v_gastos WHERE concepto LIKE 'COMISION CAMBIO DIVISA%'")[0]
    assert (spent, in_pounds, fees) == (Decimal(london["total_eur"]), Decimal(london["total_gbp"]), Decimal(london["total_fees_eur"]))
    assert spent + fees == Decimal(london["total_charged_eur"])


def test_exchange_fees_are_bank_fees_in_the_views(scenarios_loaded):
    rows = reader_rows(6, "SELECT categoria, medio_pago, comercio, divisa_original FROM v_gastos WHERE concepto LIKE 'COMISION CAMBIO DIVISA%'")
    assert rows and set(rows) == {("Comisiones", "Comisión", None, "EUR")}


def test_every_refund_is_negative_spending_and_never_income(scenarios_loaded):
    _, labels = scenarios_loaded
    refunds = {}
    for label in labels:
        if label["refund_of_tx_id"] is not None:
            refunds.setdefault(label["tx_id"] // 1_000_000, set()).add(label["tx_id"])
    assert refunds and len(refunds) > 3  # several users have refunds, not only the scripted one
    for user_id, tx_ids in refunds.items():
        spending = dict(reader_rows(user_id, "SELECT id_movimiento, gasto_eur FROM v_gastos"))
        income = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_ingresos")}
        assert all(spending[tx_id] < 0 for tx_id in tx_ids)
        assert not tx_ids & income


def test_the_net_cost_of_amazon_in_the_views_matches_the_scenario_truth(scenarios_loaded):
    amazon = scenarios_loaded[0]["amazon_refunds"]
    net, = reader_rows(7, "SELECT SUM(gasto_eur) FROM v_gastos WHERE comercio = 'AMAZON'")[0]
    refunds = reader_rows(7, "SELECT gasto_eur FROM v_gastos WHERE comercio = 'AMAZON' AND gasto_eur < 0")
    assert net == Decimal(amazon["net_eur"])
    assert len(refunds) == amazon["n_total_refunds"] + amazon["n_partial_refunds"]
    assert -sum(r[0] for r in refunds) == Decimal(amazon["refunded_eur"])
    assert reader_rows(7, "SELECT count(*) FROM v_ingresos WHERE comercio = 'AMAZON'")[0][0] == 0


def test_the_single_view_invariant_holds_with_fees_refunds_and_foreign_payments(scenarios_loaded):
    for user_id in range(1, N_USERS_WITH_SCENARIOS + 1):
        everything = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_movimientos")}
        gastos = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_gastos")}
        ingresos = {r[0] for r in reader_rows(user_id, "SELECT id_movimiento FROM v_ingresos")}
        assert gastos & ingresos == set() and gastos | ingresos == everything
        balance, = reader_rows(user_id, "SELECT SUM(importe_eur) FROM v_movimientos")[0]
        income, = reader_rows(user_id, "SELECT SUM(ingreso_eur) FROM v_ingresos")[0]
        spending, = reader_rows(user_id, "SELECT SUM(gasto_eur) FROM v_gastos")[0]
        assert balance == income - spending

def test_the_loader_role_cannot_read_what_it_loaded(loaded):
    # app_loader has INSERT only (ADR-002): it is a write-only door into the database.
    with settings.connect(settings.APP_LOADER, TEST_DB) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM transactions")
