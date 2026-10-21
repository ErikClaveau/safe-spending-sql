"""Business rules of the semantic views (ADR-005), tested without any LLM.

The dataset is small and hand-made so every expected number can be checked by hand.
It is committed (app_reader is another connection) and wiped with TRUNCATE afterwards.
"""

from decimal import Decimal

import pytest

from conftest import REPO_ROOT, TEST_DB
from safe_spending.db import settings
from seed import add_tx, seed_base

VIEWS = ("v_movimientos", "v_gastos", "v_ingresos")

# tx_id -> expected view membership, for user 1 (see the dataset below)
EXPECTED_GASTOS = {1, 3, 6, 8, 9, 10}
EXPECTED_INGRESOS = {2, 7}
EXPECTED_INTERNAL = {4, 5}


@pytest.fixture(scope="module")
def dataset(connect_module):
    """Two users; user 1 has one movement of every kind that matters for the rules."""
    with connect_module("app_loader") as conn:
        seed_base(conn)
        conn.execute("INSERT INTO categories VALUES (2, 'Nómina', 'Ingresos')")
        conn.execute("INSERT INTO categories VALUES (3, 'Bizum y transferencias enviadas', 'Otros gastos')")
        conn.execute("INSERT INTO categories VALUES (4, 'Bizum y transferencias recibidas', 'Ingresos')")
        conn.execute("INSERT INTO categories VALUES (5, 'Comisiones', 'Finanzas')")
        conn.execute("INSERT INTO categories VALUES (6, 'Retiradas de efectivo', 'Otros gastos')")
        conn.execute("INSERT INTO categories VALUES (7, 'Traspasos entre cuentas propias', 'Interno')")
        rows = [
            # purchase, refund of part of it, salary
            dict(tx_id=1),
            dict(tx_id=2, tx_code="SALARY", merchant_id=None, category_id=2, amount=1500, amount_eur=1500,
                 counterparty="EMPRESA SA", description_raw="NOMINA EMPRESA SA"),
            dict(tx_id=3, tx_code="CARD_REFUND", amount=10, amount_eur=10),
            # internal transfer between the user's own accounts: two legs
            dict(tx_id=4, tx_code="TRANSFER_OUT", merchant_id=None, category_id=7, amount=-100, amount_eur=-100,
                 counterparty_account_id=11, description_raw="TRASPASO PROPIO"),
            dict(tx_id=5, account_id=11, tx_code="TRANSFER_IN", merchant_id=None, category_id=7, amount=100,
                 amount_eur=100, counterparty_account_id=10, description_raw="TRASPASO PROPIO"),
            # Bizum out and in, with a person as counterparty
            dict(tx_id=6, tx_code="BIZUM_OUT", merchant_id=None, category_id=3, amount=-20, amount_eur=-20,
                 counterparty="Ana Pérez", description_raw="BIZUM A Ana Pérez CONCEPTO cena"),
            dict(tx_id=7, tx_code="BIZUM_IN", merchant_id=None, category_id=4, amount=15, amount_eur=15,
                 counterparty="Luis Gómez", description_raw="BIZUM DE Luis Gómez CONCEPTO regalo"),
            dict(tx_id=8, tx_code="FEE", merchant_id=None, category_id=5, amount=-3, amount_eur=-3),
            # foreign-currency card purchase and a cash withdrawal
            dict(tx_id=9, currency="GBP", amount=-30, exchange_rate=0.85, amount_eur=-35.29),
            dict(tx_id=10, tx_code="ATM_WITHDRAWAL", merchant_id=None, category_id=6, amount=-50, amount_eur=-50),
            # another user's movement
            dict(tx_id=11, account_id=20, user_id=2, amount=-99.99, amount_eur=-99.99),
        ]
        for row in rows:
            add_tx(conn, **row)
    yield
    with settings.connect(settings.ADMIN_USER, TEST_DB, autocommit=True) as admin:
        admin.execute(
            "TRUNCATE app.transactions, app.accounts, app.users, app.merchants, app.categories"
        )


@pytest.fixture(scope="module")
def connect_module():
    """Module-scoped twin of the `connect` fixture."""

    def _connect(role):
        return settings.connect(role, TEST_DB)

    return _connect


def query(connect_module, user_id, sql):
    with connect_module("app_reader") as conn:
        if user_id is not None:
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
        return conn.execute(sql).fetchall()


def ids(connect_module, user_id, view):
    return {row[0] for row in query(connect_module, user_id, f"SELECT id_movimiento FROM {view}")}


def total(connect_module, user_id, sql):
    return query(connect_module, user_id, sql)[0][0]


# ---------------------------------------------------------------------------
# Membership: every non-internal movement is in exactly one of gastos / ingresos
# ---------------------------------------------------------------------------


def test_movimientos_has_every_movement_of_the_user(dataset, connect_module):
    assert ids(connect_module, 1, "v_movimientos") == set(range(1, 11))


def test_gastos_and_ingresos_hold_exactly_the_non_internal_movements(dataset, connect_module):
    assert ids(connect_module, 1, "v_gastos") == EXPECTED_GASTOS
    assert ids(connect_module, 1, "v_ingresos") == EXPECTED_INGRESOS


def test_every_non_internal_movement_is_in_exactly_one_view(dataset, connect_module):
    for user_id in (1, 2):
        everything = ids(connect_module, user_id, "v_movimientos")
        gastos = ids(connect_module, user_id, "v_gastos")
        ingresos = ids(connect_module, user_id, "v_ingresos")
        internal = everything - gastos - ingresos
        assert gastos & ingresos == set()
        assert internal == (EXPECTED_INTERNAL if user_id == 1 else set())


# ---------------------------------------------------------------------------
# Amounts and signs
# ---------------------------------------------------------------------------


def test_refund_subtracts_from_spending(dataset, connect_module):
    refund = total(connect_module, 1, "SELECT gasto_eur FROM v_gastos WHERE id_movimiento = 3")
    assert refund == Decimal("-10.00")
    # 42.50 - 10 + 20 + 3 + 35.29 + 50
    assert total(connect_module, 1, "SELECT SUM(gasto_eur) FROM v_gastos") == Decimal("140.79")


def test_income_is_positive_and_excludes_refunds(dataset, connect_module):
    assert total(connect_module, 1, "SELECT SUM(ingreso_eur) FROM v_ingresos") == Decimal("1515.00")
    assert total(connect_module, 1, "SELECT min(ingreso_eur) FROM v_ingresos") > 0


def test_income_minus_spending_equals_balance_change(dataset, connect_module):
    # Internal transfers cancel out, so the whole-account change equals income - spending.
    balance = total(connect_module, 1, "SELECT SUM(importe_eur) FROM v_movimientos")
    income = total(connect_module, 1, "SELECT SUM(ingreso_eur) FROM v_ingresos")
    spending = total(connect_module, 1, "SELECT SUM(gasto_eur) FROM v_gastos")
    assert balance == income - spending == Decimal("1374.21")


def test_internal_transfer_legs_cancel_out(dataset, connect_module):
    sql = "SELECT SUM(importe_eur) FROM v_movimientos WHERE id_movimiento IN (4, 5)"
    assert total(connect_module, 1, sql) == 0


def test_original_amount_and_currency_are_kept(dataset, connect_module):
    row = query(
        connect_module,
        1,
        "SELECT importe_original, divisa_original, importe_eur FROM v_movimientos WHERE id_movimiento = 9",
    )[0]
    assert row == (Decimal("-30.00"), "GBP", Decimal("-35.29"))
    row = query(
        connect_module,
        1,
        "SELECT gasto_original, divisa_original FROM v_gastos WHERE id_movimiento = 9",
    )[0]
    assert row == (Decimal("30.00"), "GBP")


# ---------------------------------------------------------------------------
# Presentation columns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tx_code, expected",
    [
        ("CARD_PURCHASE", "Tarjeta"),
        ("CARD_REFUND", "Tarjeta"),
        ("DIRECT_DEBIT", "Recibo"),
        ("TRANSFER_IN", "Transferencia"),
        ("TRANSFER_OUT", "Transferencia"),
        ("SALARY", "Transferencia"),
        ("BIZUM_IN", "Bizum"),
        ("BIZUM_OUT", "Bizum"),
        ("FEE", "Comisión"),
        ("ATM_WITHDRAWAL", "Efectivo"),
    ],
)
def test_medio_pago_mapping(dataset, connect_module, tx_code, expected):
    assert query(connect_module, 1, f"SELECT medio_pago_de('{tx_code}')")[0][0] == expected


def test_account_iban_is_masked_in_every_view(dataset, connect_module):
    for view in VIEWS:
        accounts = {row[0] for row in query(connect_module, 1, f"SELECT cuenta FROM {view}")}
        assert accounts <= {"ES" + "*" * 18 + "0010", "ES" + "*" * 18 + "0011"}


def test_merchant_is_null_for_people_and_company_name_for_purchases(dataset, connect_module):
    rows = dict(query(connect_module, 1, "SELECT id_movimiento, comercio FROM v_movimientos"))
    assert rows[1] == "MERCADONA"
    assert rows[6] is None  # Bizum to a person
    assert rows[2] is None  # salary


def test_person_counterparty_is_exposed_only_as_counterparty(dataset, connect_module):
    rows = dict(query(connect_module, 1, "SELECT id_movimiento, contraparte FROM v_movimientos"))
    assert rows[6] == "Ana Pérez"
    assert rows[7] == "Luis Gómez"


# ---------------------------------------------------------------------------
# Isolation through the views and structure of the layer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("view", VIEWS)
def test_views_filter_by_user_and_fail_closed(dataset, connect_module, view):
    assert 11 not in ids(connect_module, 1, view)
    assert ids(connect_module, None, view) == set()
    assert ids(connect_module, 999, view) == set()


def test_user_2_sees_only_their_own_spending(dataset, connect_module):
    assert ids(connect_module, 2, "v_movimientos") == {11}
    assert total(connect_module, 2, "SELECT SUM(gasto_eur) FROM v_gastos") == Decimal("99.99")


def test_no_view_exposes_user_id(connect):
    with connect("app_owner") as conn:
        columns = {
            (view, column)
            for view, column in conn.execute(
                "SELECT c.relname, a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relnamespace = 'app'::regnamespace AND c.relkind = 'v' AND a.attnum > 0"
            )
        }
    assert {c for _, c in columns if c == "user_id"} == set()
    assert {v for v, _ in columns} == set(VIEWS)


def test_every_view_and_column_has_a_comment(connect):
    with connect("app_owner") as conn:
        views_without_comment = conn.execute(
            "SELECT relname FROM pg_class WHERE relnamespace = 'app'::regnamespace "
            "AND relkind = 'v' AND coalesce(obj_description(oid, 'pg_class'), '') = ''"
        ).fetchall()
        columns_without_comment = conn.execute(
            "SELECT c.relname, a.attname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid "
            "WHERE c.relnamespace = 'app'::regnamespace AND c.relkind = 'v' AND a.attnum > 0 "
            "AND coalesce(col_description(c.oid, a.attnum), '') = ''"
        ).fetchall()
    assert views_without_comment == []
    assert columns_without_comment == []

# ---------------------------------------------------------------------------
# Data dictionary (docs/data-dictionary.md) stays in sync with the views
# ---------------------------------------------------------------------------


def documented_columns():
    """Parse docs/data-dictionary.md: `## v_name` sections with `| `column` | type | ... |` rows."""
    current, found = None, {}
    for line in (REPO_ROOT / "docs" / "data-dictionary.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip().strip("`")
            found[current] = set()
        elif current and line.startswith("| `"):
            found[current].add(line.split("`")[1])
    return found


def test_data_dictionary_documents_exactly_the_view_columns(connect):
    with connect("app_owner") as conn:
        actual = {}
        for view, column in conn.execute(
            "SELECT c.relname, a.attname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relnamespace = 'app'::regnamespace AND c.relkind = 'v' AND a.attnum > 0"
        ):
            actual.setdefault(view, set()).add(column)
    documented = {view: cols for view, cols in documented_columns().items() if view in VIEWS}
    assert documented == actual
