"""Invariants of the generated data (generator design 6.2) that block the build."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

import pytest

from gen_helpers import REFERENCE, build
from safe_spending.generator import iban
from safe_spending.generator.config import load_config

PERIOD_START = date(2024, 9, 16)
OUTFLOWS = {"CARD_PURCHASE", "DIRECT_DEBIT", "TRANSFER_OUT", "BIZUM_OUT", "FEE", "ATM_WITHDRAWAL"}
INFLOWS = {"CARD_REFUND", "TRANSFER_IN", "BIZUM_IN", "SALARY"}


@pytest.fixture(scope="module")
def built():
    return build(8)


@pytest.fixture(scope="module")
def dataset(built):
    return built[2]


def test_no_date_outside_the_period(dataset):
    for t in dataset.transactions:
        assert PERIOD_START <= t.booking_date <= REFERENCE
        assert PERIOD_START <= t.value_date <= t.booking_date


def test_sign_of_the_amount_matches_the_operation_type(dataset):
    # Mirrors the CHECK constraint transactions_sign_matches_tx_code.
    for t in dataset.transactions:
        assert t.tx_code in OUTFLOWS | INFLOWS
        assert (t.amount_eur < 0) == (t.tx_code in OUTFLOWS)
        assert t.amount_eur != 0


def test_euro_amounts_are_consistent(dataset):
    for t in dataset.transactions:
        assert t.currency == "EUR"
        assert t.exchange_rate is None
        assert t.amount == t.amount_eur
        assert t.amount_eur == t.amount_eur.quantize(Decimal("0.01"))  # whole cents


def test_ids_are_unique_and_follow_booking_order_within_each_user(dataset):
    ids = [t.tx_id for t in dataset.transactions]
    assert len(ids) == len(set(ids))
    by_user = defaultdict(list)
    for t in dataset.transactions:
        by_user[t.user_id].append(t)
    for user_id, rows in by_user.items():
        assert [r.tx_id for r in rows] == sorted(r.tx_id for r in rows)
        assert all(r.tx_id // 1_000_000 == user_id for r in rows)
        dates = [r.booking_date for r in rows]
        assert dates == sorted(dates)


def test_every_transaction_belongs_to_an_account_of_the_same_user(dataset):
    owner = {a.account_id: a.user_id for a in dataset.accounts}
    for t in dataset.transactions:
        assert owner[t.account_id] == t.user_id


def test_ibans_are_structurally_valid_and_unique(dataset):
    ibans = [a.iban for a in dataset.accounts]
    assert all(iban.is_valid(i) for i in ibans)
    assert len(set(ibans)) == len(ibans)


def test_merchants_are_companies_and_people_stay_in_counterparty(dataset):
    merchant_names = {m.normalized_name for m in dataset.merchants}
    people = {t.counterparty for t in dataset.transactions if t.tx_code == "TRANSFER_OUT"}
    assert people and people.isdisjoint(merchant_names)
    for t in dataset.transactions:
        if t.tx_code in ("TRANSFER_OUT", "SALARY"):
            assert t.merchant_id is None
        if t.tx_code == "CARD_PURCHASE":
            assert t.merchant_id is not None


def test_card_purchases_never_carry_a_counterparty_but_receipts_do(dataset):
    for t in dataset.transactions:
        if t.tx_code == "CARD_PURCHASE":
            assert t.counterparty is None
        if t.tx_code in ("DIRECT_DEBIT", "SALARY", "TRANSFER_OUT"):
            assert t.counterparty


def test_categories_and_merchants_are_referenced_consistently(dataset):
    category_ids = {c.category_id for c in dataset.categories}
    merchant_ids = {m.merchant_id for m in dataset.merchants}
    for t in dataset.transactions:
        assert t.category_id in category_ids
        assert t.merchant_id is None or t.merchant_id in merchant_ids


def test_every_user_gets_the_expected_recurring_payments(dataset):
    counts = defaultdict(Counter)
    for t in dataset.transactions:
        counts[t.user_id][t.tx_code] += 1
    for user_id, c in counts.items():
        assert c["SALARY"] == 28, user_id  # 24 monthly pays + 4 extra (Dec-24, Jun-25, Dec-25, Jun-26)
        assert c["TRANSFER_OUT"] == 24, user_id  # rent, Oct-2024 to Sep-2026


def test_descriptions_look_like_a_bank_statement(built):
    config, _, dataset = built
    for t in dataset.transactions:
        description = t.description_raw
        assert description == description.upper()
        assert description.isascii()
        assert len(description) <= config.statement_max_length
        assert description == " ".join(description.split())


def test_labels_match_the_operational_data(built):
    config, _, dataset = built
    assert [l.tx_id for l in dataset.tx_labels] == [t.tx_id for t in dataset.transactions]
    for t, label in zip(dataset.transactions, dataset.tx_labels):
        assert label.true_category_id == t.category_id
        assert not label.is_trap and label.canary is None
    for label in dataset.user_labels:
        assert label.split == config.split_of(label.user_id)


def test_split_ranges_follow_the_design():
    config = load_config()
    assert config.split_of(1) == config.split_of(15) == "eval_functional"
    assert config.split_of(16) == config.split_of(20) == "eval_adversarial"
    assert config.split_of(21) == config.split_of(100) == "population"


def test_no_user_saves_an_absurd_share_of_their_income(dataset):
    # Loose sanity check; the calibrated statistical report arrives with slice 4.
    income, net = defaultdict(Decimal), defaultdict(Decimal)
    for t in dataset.transactions:
        net[t.user_id] += t.amount_eur
        if t.amount_eur > 0:
            income[t.user_id] += t.amount_eur
    for user_id in income:
        rate = net[user_id] / income[user_id]
        assert Decimal("-0.15") < rate < Decimal("0.60"), (user_id, rate)


def test_spending_is_seasonal(dataset):
    # December (Compras and Ocio y viajes peak) should outspend February on card purchases.
    by_month = Counter()
    for t in dataset.transactions:
        if t.tx_code == "CARD_PURCHASE" and t.booking_date.year == 2025:
            by_month[t.booking_date.month] -= t.amount_eur
    assert by_month[12] > by_month[2]
