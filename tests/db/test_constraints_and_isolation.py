"""Integrity constraints and RLS isolation on the real schema.

Constraint tests run inside a transaction that is rolled back. The isolation test needs
committed rows (app_reader is another connection), so it cleans up with TRUNCATE as the
superuser, which only this test database ever sees.
"""

import psycopg
import pytest

from safe_spending.db import settings
from conftest import TEST_DB


def seed_base(conn):
    conn.execute("INSERT INTO categories VALUES (1, 'Supermercados', 'Alimentación')")
    conn.execute("INSERT INTO merchants VALUES (1, 'MERCADONA', '5411')")
    conn.execute("INSERT INTO users VALUES (1, 'Ana', 'Alicante', '2024-09-16')")
    conn.execute("INSERT INTO users VALUES (2, 'Beto', 'Madrid', '2024-09-16')")
    conn.execute("INSERT INTO accounts VALUES (10, 1, 'ES0000000000000000000010', 'EUR')")
    conn.execute("INSERT INTO accounts VALUES (11, 1, 'ES0000000000000000000011', 'EUR')")
    conn.execute("INSERT INTO accounts VALUES (20, 2, 'ES0000000000000000000020', 'EUR')")


def add_tx(conn, **overrides):
    row = {
        "tx_id": 1,
        "account_id": 10,
        "user_id": 1,
        "booking_date": "2026-09-01",
        "value_date": "2026-09-01",
        "amount": -42.50,
        "currency": "EUR",
        "exchange_rate": None,
        "amount_eur": -42.50,
        "description_raw": "COMPRA TARJ. 5402XXXX MERCADONA ALICANTE",
        "counterparty": None,
        "tx_code": "CARD_PURCHASE",
        "merchant_id": 1,
        "category_id": 1,
        "counterparty_account_id": None,
    }
    row.update(overrides)
    columns = ", ".join(row)
    placeholders = ", ".join(["%s"] * len(row))
    conn.execute(f"INSERT INTO transactions ({columns}) VALUES ({placeholders})", list(row.values()))


@pytest.fixture
def loader(connect):
    """app_loader connection with base rows, rolled back at the end of the test."""
    conn = connect("app_loader")
    seed_base(conn)
    yield conn
    conn.rollback()
    conn.close()


def test_valid_euro_purchase_and_internal_transfer_load(loader):
    add_tx(loader)
    add_tx(
        loader,
        tx_id=2,
        account_id=10,
        tx_code="TRANSFER_OUT",
        merchant_id=None,
        counterparty_account_id=11,
        amount=-100,
        amount_eur=-100,
    )


def test_foreign_currency_purchase_with_exchange_rate_loads(loader):
    add_tx(loader, currency="GBP", amount=-30, exchange_rate=0.85, amount_eur=-35.29)


@pytest.mark.parametrize(
    "overrides",
    [
        {"currency": "GBP", "exchange_rate": None},
        {"currency": "EUR", "exchange_rate": 0.85},
        {"currency": "GBP", "exchange_rate": 0},
        {"tx_code": "CHEQUE"},
        {"counterparty_account_id": 10},
    ],
    ids=[
        "foreign-currency-without-rate",
        "euro-with-rate",
        "non-positive-rate",
        "unknown-tx-code",
        "transfer-to-same-account",
    ],
)
def test_check_constraints_reject_inconsistent_rows(loader, overrides):
    with pytest.raises(psycopg.errors.CheckViolation):
        add_tx(loader, **overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"account_id": 20},  # account owned by user 2, row says user 1
        {"counterparty_account_id": 20},  # internal transfer into another user's account
        {"merchant_id": 999},
        {"category_id": 999},
    ],
    ids=["account-of-another-user", "counterparty-of-another-user", "unknown-merchant", "unknown-category"],
)
def test_foreign_keys_reject_inconsistent_rows(loader, overrides):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        add_tx(loader, **overrides)


def test_accounts_must_be_in_euros(loader):
    with pytest.raises(psycopg.errors.CheckViolation):
        loader.execute("INSERT INTO accounts VALUES (12, 1, 'ES0000000000000000000012', 'USD')")


def test_isolation_on_real_schema(connect):
    with connect("app_loader") as conn:
        seed_base(conn)
        add_tx(conn, tx_id=1, account_id=10, user_id=1)
        add_tx(conn, tx_id=2, account_id=11, user_id=1, amount=-10, amount_eur=-10)
        add_tx(conn, tx_id=3, account_id=20, user_id=2, amount=-5, amount_eur=-5)
    try:

        def visible(user_id, table):
            with connect("app_reader") as reader:
                if user_id is not None:
                    reader.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
                return reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

        assert visible(1, "transactions") == 2
        assert visible(2, "transactions") == 1
        assert visible(1, "accounts") == 2
        assert visible(2, "users") == 1
        # Fail closed without the variable, but shared catalogs stay readable.
        assert visible(None, "transactions") == 0
        assert visible(None, "users") == 0
        assert visible(None, "categories") == 1
        assert visible(None, "merchants") == 1
    finally:
        with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
            admin.execute(
                "TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories"
            )
