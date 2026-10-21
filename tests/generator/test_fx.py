"""Foreign currency (generator design 5.3): the exchange-rate series, the euro conversion and the fee."""

from datetime import date
from decimal import Decimal

import pytest

from gen_helpers import REFERENCE, build
from safe_spending.generator.config import FxSettings
from safe_spending.generator.dates import daterange
from safe_spending.generator.events import foreign_purchase
from safe_spending.generator.fx import build_fx_series, exchange_fee_cents
from safe_spending.generator.money import convert_to_eur_cents

CURRENCIES = {"CHF", "GBP", "USD"}


@pytest.fixture(scope="module")
def built():
    return build(9)


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
def fx(config):
    return build_fx_series(config, REFERENCE)


# ---------------------------------------------------------------------------
# The rate series
# ---------------------------------------------------------------------------


def test_there_is_a_rate_for_every_day_of_the_period(fx, config):
    days = daterange(config.period_start, REFERENCE)
    assert set(fx.rates) == CURRENCIES
    for currency, series in fx.rates.items():
        assert list(series) == days, currency


def test_rates_are_positive_with_the_precision_of_the_column(fx):
    for series in fx.rates.values():
        for rate in series.values():
            assert rate > 0
            assert rate == rate.quantize(Decimal("0.000001"))  # NUMERIC(12,6)


def test_each_series_moves_around_its_base_value(fx, config):
    for currency, series in fx.rates.items():
        base = config.fx.currencies[currency].base
        rates = [float(r) for r in series.values()]
        assert len(set(rates)) > 100  # it moves
        assert all(0.85 * base < r < 1.15 * base for r in rates)  # and stays realistic
        assert abs(sum(rates) / len(rates) - base) < 0.05 * base  # mean reversion keeps it centred


def test_the_series_is_the_same_for_every_run_and_every_population(config):
    assert build_fx_series(config, REFERENCE) == build_fx_series(config, REFERENCE)
    _, _, _ = build(2)  # a different population size cannot matter: the series has no users
    assert build_fx_series(config.model_copy(update={"n_users": 100}), REFERENCE) == build_fx_series(config, REFERENCE)


def test_a_different_seed_gives_a_different_series(config):
    other = build_fx_series(config.model_copy(update={"seed": 1}), REFERENCE)
    assert other != build_fx_series(config, REFERENCE)


def test_the_order_of_the_currencies_in_the_config_does_not_matter(config):
    reversed_currencies = dict(reversed(list(config.fx.currencies.items())))
    reordered = config.model_copy(update={"fx": config.fx.model_copy(update={"currencies": reversed_currencies})})
    assert build_fx_series(reordered, REFERENCE) == build_fx_series(config, REFERENCE)


def test_the_series_stops_at_the_reference_date(config):
    earlier = build_fx_series(config, date(2025, 6, 30))
    assert max(earlier.rates["GBP"]) == date(2025, 6, 30)
    # A shorter run is a prefix of the full one: the walk does not depend on where it ends.
    full = build_fx_series(config, REFERENCE)
    assert all(full.rate("GBP", day) == rate for day, rate in earlier.rates["GBP"].items())


# ---------------------------------------------------------------------------
# Conversion to euros
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "foreign_cents, rate, expected",
    [
        (-3000, "0.85", -3529),  # GBP 30.00 at 0.85 per EUR is EUR 35.29
        (3000, "0.85", 3529),
        (1000, "1", 1000),
        (5, "2", 2),  # 2.5 rounds half to even
        (7, "2", 4),  # 3.5 rounds half to even
        (-5, "2", -2),
        (0, "0.9", 0),
    ],
)
def test_the_euro_amount_is_the_foreign_amount_divided_by_the_rate(foreign_cents, rate, expected):
    assert convert_to_eur_cents(foreign_cents, Decimal(rate)) == expected


def test_a_foreign_purchase_uses_the_rate_of_the_operation_day(fx, catalog):
    merchant = catalog.merchants_in("Restaurantes y bares", currency="GBP")[0]
    operation, booking = date(2025, 5, 10), date(2025, 5, 12)
    event = foreign_purchase(
        fx=fx, merchant=merchant, category_id=1, operation_date=operation, booking_date=booking, local_cents=4500
    )
    assert event.foreign.rate == fx.rate("GBP", operation) != fx.rate("GBP", booking)
    assert event.foreign.currency == "GBP" and event.foreign.amount_cents == -4500
    assert event.amount_cents == -convert_to_eur_cents(4500, event.foreign.rate)
    assert (event.value_date, event.booking_date) == (operation, booking)


# ---------------------------------------------------------------------------
# The exchange fee
# ---------------------------------------------------------------------------

FEE = FxSettings(currencies={}, fee_rate=0.0175, fee_min_eur=0.50)


@pytest.mark.parametrize(
    "eur_cents, expected",
    [
        (-500, 50),  # 1.75% would be 9 cents: the minimum applies
        (-2857, 50),  # 1.75% is 50 cents
        (-10000, 175),
        (-123456, 2160),
        (10000, 175),  # the sign is ignored
    ],
)
def test_the_fee_is_a_share_of_the_amount_with_a_minimum(eur_cents, expected):
    assert exchange_fee_cents(FEE, eur_cents) == expected


# ---------------------------------------------------------------------------
# Foreign merchants stay out of everyone's everyday life
# ---------------------------------------------------------------------------


def test_foreign_merchants_come_after_every_euro_merchant(dataset, catalog):
    ids_by_currency = {}
    for merchant in catalog.merchants:
        ids_by_currency.setdefault(merchant.currency, []).append(merchant.merchant_id)
    assert set(ids_by_currency) == {"EUR", "GBP"}
    assert min(ids_by_currency["GBP"]) > max(ids_by_currency["EUR"])  # no existing merchant id moved
    assert {m.normalized_name for m in dataset.merchants} >= {"MERCADONA", "PREMIER INN LONDON"}


def test_a_category_lists_only_its_euro_merchants_unless_asked_otherwise(catalog):
    assert all(m.currency == "EUR" for m in catalog.merchants_in("Restaurantes y bares"))
    assert {m.currency for m in catalog.merchants_in("Restaurantes y bares", currency="GBP")} == {"GBP"}
    assert catalog.merchants_in("Supermercados", currency="GBP") == []


def test_only_the_london_user_ever_pays_in_pounds(dataset):
    foreign = [t for t in dataset.transactions if t.currency != "EUR"]
    assert foreign and {t.user_id for t in foreign} == {6}
    assert {t.currency for t in foreign} == {"GBP"}
