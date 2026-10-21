"""The London trip and the Amazon refunds (generator design 5.5): the ground truth in `scenarios.params`
must match the generated movements, and neither scenario may touch anything it does not claim."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import pytest

from gen_helpers import REFERENCE, build
from safe_spending.clock import FixedClock
from safe_spending.generator.dates import daterange
from safe_spending.generator.enums import TxCode
from safe_spending.generator.fx import build_fx_series, exchange_fee_cents
from safe_spending.generator.money import convert_to_eur_cents
from safe_spending.generator.scenarios.amazon_refunds_params import AmazonRefundsParams, RefundKind
from safe_spending.generator.scenarios.london_trip_params import LondonTripParams
from safe_spending.generator.simulate import generate

N_USERS = 9


@pytest.fixture(scope="module")
def built():
    return build(N_USERS)


@pytest.fixture(scope="module")
def config(built):
    return built[0]


@pytest.fixture(scope="module")
def catalog(built):
    return built[1]


@pytest.fixture(scope="module")
def dataset(built):
    return built[2]


@pytest.fixture(scope="module")
def baseline(config, catalog):
    """The same population without any scenario."""
    return generate(config.model_copy(update={"scenarios": ()}), catalog, FixedClock(REFERENCE))


@pytest.fixture(scope="module")
def fx(config):
    return build_fx_series(config, REFERENCE)


def params_of(dataset, user_id, model):
    row = next(s for s in dataset.scenarios if s.user_id == user_id)
    return model.model_validate_json(row.params)


def transactions_of(dataset, user_id, *, tagged=None):
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    return [
        t for t in dataset.transactions
        if t.user_id == user_id and (tagged is None or (scenario_by_tx[t.tx_id] is not None) == tagged)
    ]


def fingerprints(transactions):
    return Counter((t.booking_date, t.tx_code, t.amount_eur, t.merchant_id, t.category_id) for t in transactions)


def merchant_names(dataset):
    return {m.merchant_id: m.normalized_name for m in dataset.merchants}


def category_names(dataset):
    return {c.category_id: c.name for c in dataset.categories}


# ---------------------------------------------------------------------------
# London trip (user 6)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trip(dataset):
    params = params_of(dataset, 6, LondonTripParams)
    tagged = transactions_of(dataset, 6, tagged=True)
    purchases = [t for t in tagged if t.tx_code == TxCode.CARD_PURCHASE]
    fees = [t for t in tagged if t.tx_code == TxCode.FEE]
    return params, purchases, fees


def test_every_london_payment_is_in_pounds_at_the_rate_of_its_day(trip, fx):
    _, purchases, _ = trip
    for t in purchases:
        assert t.currency == "GBP" and t.amount < 0 and t.amount_eur < 0
        assert t.exchange_rate == fx.rate("GBP", t.value_date)
        assert -t.amount_eur == Decimal(convert_to_eur_cents(int(-t.amount * 100), t.exchange_rate)).scaleb(-2)
        assert t.description_raw.endswith(f"{-t.amount:.2f} GBP")


def test_the_trip_params_match_the_movements(trip, dataset):
    params, purchases, fees = trip
    names = category_names(dataset)
    assert params.currency == "GBP"
    assert params.n_purchases == len(purchases) == len(fees)
    assert params.total_gbp == -sum(t.amount for t in purchases)
    assert params.total_eur == -sum(t.amount_eur for t in purchases)
    assert params.total_fees_eur == -sum(t.amount_eur for t in fees)
    assert params.total_charged_eur == params.total_eur + params.total_fees_eur
    by_category = Counter()
    for t in purchases:
        by_category[names[t.category_id]] -= t.amount_eur
    assert dict(sorted(by_category.items())) == params.by_category_eur
    # A taxi is only taken some days, so that category may be absent; the other three always appear.
    assert {"Viajes y alojamiento", "Transporte público", "Restaurantes y bares"} <= set(by_category)
    assert set(by_category) <= {"Viajes y alojamiento", "Transporte público", "Taxi y VTC", "Restaurantes y bares"}


def test_the_trip_lasts_four_to_six_days_inside_one_month_with_history_around_it(trip, config):
    params, purchases, _ = trip
    assert 4 <= params.n_days <= 6 and params.n_days == (params.last_day - params.first_day).days + 1
    assert {(t.value_date.year, t.value_date.month) for t in purchases} == {(params.first_day.year, params.first_day.month)}
    assert min(t.value_date for t in purchases) == params.first_day
    assert max(t.value_date for t in purchases) == params.last_day
    assert params.first_day - config.period_start > timedelta(days=90)
    assert REFERENCE - params.last_day > timedelta(days=90)


def test_every_trip_day_has_hotel_free_spending(trip):
    params, purchases, _ = trip
    per_day = Counter(t.value_date for t in purchases)
    assert set(per_day) == set(daterange(params.first_day, params.last_day))
    assert all(count >= 3 for count in per_day.values())  # transit and dining, at least


def test_the_hotel_is_one_charge_for_the_whole_stay_on_arrival(trip, dataset):
    params, purchases, _ = trip
    names = category_names(dataset)
    hotel = [t for t in purchases if names[t.category_id] == "Viajes y alojamiento"]
    assert len(hotel) == 1 and hotel[0].value_date == params.first_day
    nights = params.n_days - 1
    assert (-hotel[0].amount) % nights == 0  # whole pounds per night times the nights


def test_booking_follows_the_operation_by_a_few_days(trip):
    _, purchases, _ = trip
    for t in purchases:
        assert timedelta(0) <= t.booking_date - t.value_date <= timedelta(days=3)


def test_each_purchase_has_its_exchange_fee_booked_with_it(trip, config):
    _, purchases, fees = trip
    expected = Counter(
        (t.booking_date, -exchange_fee_cents(config.fx, int(t.amount_eur * 100)) / 100) for t in purchases
    )
    assert Counter((f.booking_date, f.amount_eur) for f in fees) == Counter(
        (date_, Decimal(str(amount))) for (date_, amount), n in expected.items() for _ in range(n)
    )
    for f in fees:
        assert f.tx_code == TxCode.FEE and f.currency == "EUR" and f.exchange_rate is None
        assert f.merchant_id is None and f.counterparty is None
        assert f.description_raw.startswith("COMISION CAMBIO DIVISA ")


def test_the_fee_respects_the_minimum_and_the_rate(trip, config):
    _, purchases, fees = trip
    minimum = Decimal(str(config.fx.fee_min_eur))
    assert all(-f.amount_eur >= minimum for f in fees)
    biggest = max(purchases, key=lambda t: -t.amount_eur)
    fee_of_biggest = next(f for f in fees if f.booking_date == biggest.booking_date and -f.amount_eur > minimum)
    assert abs(-fee_of_biggest.amount_eur - -biggest.amount_eur * Decimal(str(config.fx.fee_rate))) < Decimal("0.01")


def test_the_trip_uses_london_merchants_only(trip, dataset, catalog):
    _, purchases, _ = trip
    london = {m.merchant_id for m in catalog.merchants if m.currency == "GBP"}
    assert {t.merchant_id for t in purchases} <= london


def test_a_london_trip_only_adds_movements(dataset, baseline):
    assert fingerprints(transactions_of(dataset, 6, tagged=False)) == fingerprints(transactions_of(baseline, 6))


def test_the_fees_are_filed_as_bank_fees(trip, dataset):
    _, _, fees = trip
    names = category_names(dataset)
    assert {names[f.category_id] for f in fees} == {"Comisiones"}


# ---------------------------------------------------------------------------
# Amazon refunds (user 7)
# ---------------------------------------------------------------------------

AMAZON = "AMAZON"


@pytest.fixture(scope="module")
def amazon(dataset):
    params = params_of(dataset, 7, AmazonRefundsParams)
    names = merchant_names(dataset)
    by_id = {t.tx_id: t for t in dataset.transactions}
    rows = [t for t in transactions_of(dataset, 7) if names.get(t.merchant_id) == AMAZON]
    labels = {l.tx_id: l for l in dataset.tx_labels}
    return params, rows, by_id, labels


def test_the_baseline_really_had_amazon_activity_to_remove(baseline):
    names = merchant_names(baseline)
    assert any(names.get(t.merchant_id) == AMAZON for t in transactions_of(baseline, 7))


def test_the_scripted_purchases_are_the_only_amazon_movements(amazon):
    params, rows, _, labels = amazon
    assert all(labels[t.tx_id].scenario_id == "007-amazon_refunds" for t in rows)
    purchases = [t for t in rows if t.tx_code == TxCode.CARD_PURCHASE]
    refunds = [t for t in rows if t.tx_code == TxCode.CARD_REFUND]
    assert len(purchases) == len(params.purchases) == 6
    assert len(refunds) == params.n_total_refunds + params.n_partial_refunds == 4


def test_two_total_two_partial_and_two_missing_refunds(amazon):
    params, *_ = amazon
    assert Counter(p.kind for p in params.purchases) == {RefundKind.TOTAL: 2, RefundKind.PARTIAL: 2, RefundKind.NONE: 2}


def test_every_scripted_purchase_and_refund_is_in_the_data(amazon):
    params, rows, by_id, labels = amazon
    purchases = {(t.booking_date, -t.amount_eur): t for t in rows if t.tx_code == TxCode.CARD_PURCHASE}
    for scripted in params.purchases:
        purchase = purchases[(scripted.date, scripted.amount_eur)]
        refunds = [t for t in rows if t.tx_code == TxCode.CARD_REFUND and labels[t.tx_id].refund_of_tx_id == purchase.tx_id]
        if scripted.kind == RefundKind.NONE:
            assert refunds == [] and scripted.refund_date is None and scripted.refund_eur is None
            continue
        assert len(refunds) == 1
        assert (refunds[0].booking_date, refunds[0].amount_eur) == (scripted.refund_date, scripted.refund_eur)
        assert refunds[0].booking_date > purchase.booking_date


def test_total_refunds_return_everything_and_partial_ones_a_share(amazon):
    params, *_ = amazon
    for p in params.purchases:
        if p.kind == RefundKind.TOTAL:
            assert p.refund_eur == p.amount_eur
        elif p.kind == RefundKind.PARTIAL:
            assert Decimal("0.29") * p.amount_eur < p.refund_eur < Decimal("0.71") * p.amount_eur
            assert 0 < p.refund_eur < p.amount_eur


def test_exactly_one_refund_crosses_into_the_next_month_and_it_is_a_total_one(amazon):
    params, *_ = amazon
    crossing = [p for p in params.purchases if p.crosses_month]
    assert len(crossing) == 1 and crossing[0].kind == RefundKind.TOTAL
    assert crossing[0].refund_date.month == (crossing[0].date.month % 12) + 1
    for p in params.purchases:
        if p.refund_date and not p.crosses_month:
            assert p.refund_date.month == p.date.month


def test_the_net_cost_of_amazon_is_known_exactly(amazon):
    params, rows, *_ = amazon
    assert params.net_eur == params.purchased_eur - params.refunded_eur
    assert -sum(t.amount_eur for t in rows) == params.net_eur  # nothing else is Amazon
    assert params.refunded_eur == sum(t.amount_eur for t in rows if t.tx_code == TxCode.CARD_REFUND)
    assert params.net_eur > 0


def test_everything_has_settled_well_before_the_reference_date(amazon):
    params, *_ = amazon
    assert all(p.refund_date is None or REFERENCE - p.refund_date > timedelta(days=90) for p in params.purchases)


def test_other_users_keep_their_amazon_activity(dataset):
    names = merchant_names(dataset)
    others = [t for t in dataset.transactions if t.user_id != 7 and names.get(t.merchant_id) == AMAZON]
    assert others


def test_the_user_keeps_everything_that_is_not_amazon(dataset, baseline):
    non_amazon = lambda ds: fingerprints(t for t in transactions_of(ds, 7) if merchant_names(ds).get(t.merchant_id) != AMAZON)
    assert non_amazon(dataset) == non_amazon(baseline)  # Amazon Prime, a different merchant, stays


def test_no_refund_in_the_whole_dataset_is_left_without_its_purchase(dataset):
    by_id = {t.tx_id for t in dataset.transactions}
    for label in dataset.tx_labels:
        assert label.refund_of_tx_id is None or label.refund_of_tx_id in by_id
