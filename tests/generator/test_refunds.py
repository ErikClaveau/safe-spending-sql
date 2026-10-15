"""Refunds of card purchases (generator design 5.4): linked to their purchase, never larger than it,
never before it, never after the reference date, and drawn so that one result never moves another."""

from collections import Counter, defaultdict
from datetime import timedelta

import pytest

from gen_helpers import REFERENCE, build
from safe_spending.generator.enums import Channel, TxCode
from safe_spending.generator.events import Event, drop_orphan_refunds, refund_events
from safe_spending.generator.enums import Stage
from safe_spending.generator.rng import stream

N_USERS = 25


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
def links(dataset):
    """(refund, purchase) for every refund, resolved through tx_labels.refund_of_tx_id."""
    by_id = {t.tx_id: t for t in dataset.transactions}
    return [(by_id[l.tx_id], by_id[l.refund_of_tx_id]) for l in dataset.tx_labels if l.refund_of_tx_id is not None]


@pytest.fixture(scope="module")
def merchants_by_id(catalog):
    return {m.merchant_id: m for m in catalog.merchants}


# ---------------------------------------------------------------------------
# Every refund is a refund of one purchase
# ---------------------------------------------------------------------------


def test_every_refund_has_a_link_and_only_refunds_do(dataset, links):
    refunds = {t.tx_id for t in dataset.transactions if t.tx_code == TxCode.CARD_REFUND}
    linked = {r.tx_id for r, _ in links}
    assert refunds and refunds == linked


def test_a_refund_points_to_a_card_purchase_of_the_same_user_merchant_and_category(links):
    for refund, purchase in links:
        assert purchase.tx_code == TxCode.CARD_PURCHASE
        assert (refund.user_id, refund.merchant_id, refund.category_id) == (
            purchase.user_id, purchase.merchant_id, purchase.category_id)


def test_a_refund_comes_after_its_purchase_and_is_never_larger(links):
    for refund, purchase in links:
        assert refund.booking_date > purchase.booking_date
        assert 0 < refund.amount_eur <= -purchase.amount_eur
        assert refund.amount == refund.amount_eur  # refunds are in euros


def test_no_refund_is_booked_after_the_reference_date_or_before_its_purchase_period(links, config):
    for refund, purchase in links:
        assert refund.booking_date <= REFERENCE
        assert purchase.booking_date >= config.period_start


def test_a_purchase_is_refunded_at_most_once(links):
    counts = Counter(purchase.tx_id for _, purchase in links)
    assert max(counts.values()) == 1


def test_random_refunds_arrive_between_the_configured_number_of_days(links, config, dataset):
    low, high = config.refunds.delay_days
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    for refund, purchase in links:
        if scenario_by_tx[refund.tx_id] is None:  # scripted refunds follow their own rules
            assert timedelta(days=low) <= refund.booking_date - purchase.booking_date <= timedelta(days=high)


def test_a_refund_reads_like_a_card_refund(links):
    for refund, _ in links:
        assert refund.description_raw.startswith("DEVOLUCION TARJ. ")
        assert refund.counterparty is None


# ---------------------------------------------------------------------------
# What gets refunded
# ---------------------------------------------------------------------------


def test_subscriptions_and_supermarkets_are_never_refunded(links, merchants_by_id, dataset):
    names = {c.category_id: c.name for c in dataset.categories}
    for _, purchase in links:
        assert merchants_by_id[purchase.merchant_id].channel in (Channel.CARD_PRESENT, Channel.CARD_ONLINE)
        assert names[purchase.category_id] != "Supermercados"


def test_refund_rates_follow_the_category(dataset, links):
    names = {c.category_id: c.name for c in dataset.categories}
    purchases = Counter(names[t.category_id] for t in dataset.transactions if t.tx_code == TxCode.CARD_PURCHASE)
    refunded = Counter(names[p.category_id] for _, p in links)
    rate = lambda category: refunded[category] / purchases[category]
    assert 0.06 < rate("Ropa y calzado") < 0.20
    assert 0.05 < rate("Compras online") < 0.20
    assert rate("Ropa y calzado") > rate("Electrónica") > rate("Restaurantes y bares")
    assert refunded["Supermercados"] == 0


def test_most_refunds_are_total_and_the_rest_partial(links, config, dataset):
    scenario_by_tx = {l.tx_id: l.scenario_id for l in dataset.tx_labels}
    random_links = [(r, p) for r, p in links if scenario_by_tx[r.tx_id] is None]
    total = sum(1 for r, p in random_links if r.amount_eur == -p.amount_eur)
    assert abs(total / len(random_links) - config.refunds.total_share) < 0.08
    low, high = config.refunds.partial_fraction
    for refund, purchase in random_links:
        if refund.amount_eur != -purchase.amount_eur:
            assert 0 < refund.amount_eur < -purchase.amount_eur


def test_some_refunds_cross_into_the_next_month(links):
    assert any(r.booking_date.month != p.booking_date.month for r, p in links)


def test_every_category_named_in_the_config_exists(config, catalog):
    for name in config.refunds.probability_by_category:
        catalog.category(name)  # raises KeyError if the YAML has a typo


# ---------------------------------------------------------------------------
# The draws: one purchase's result never shifts another's
# ---------------------------------------------------------------------------


def purchases_of(catalog, n):
    merchant = next(m for m in catalog.merchants if m.name == "ZARA")
    category_id = catalog.category(merchant.category).category_id
    return [
        Event(booking_date=REFERENCE - timedelta(days=200 - i), value_date=REFERENCE - timedelta(days=200 - i),
              tx_code=TxCode.CARD_PURCHASE, amount_cents=-(1000 + i), category_id=category_id, merchant=merchant)
        for i in range(n)
    ]


def run(config, catalog, events, user_id=1):
    rng = stream(seed=config.seed, user_id=user_id, stage=Stage.SPECIAL)
    return refund_events(config=config, catalog=catalog, events=events, rng=rng, end=REFERENCE)


def test_refunds_are_reproducible(config, catalog):
    events = purchases_of(catalog, 150)
    assert run(config, catalog, events) == run(config, catalog, events)


def test_changing_the_probability_of_one_category_leaves_the_other_categories_alone(config, catalog):
    zara = purchases_of(catalog, 80)
    mercadona = next(m for m in catalog.merchants if m.name == "MERCADONA")
    other = [Event(booking_date=REFERENCE - timedelta(days=150 - i), value_date=REFERENCE - timedelta(days=150 - i),
                   tx_code=TxCode.CARD_PURCHASE, amount_cents=-2500, category_id=catalog.category("Farmacia").category_id,
                   merchant=next(m for m in catalog.merchants if m.name == "DR. FARMA")) for i in range(80)]
    events = [e for pair in zip(zara, other) for e in pair]  # interleaved: both categories draw in turn
    refunds_in = lambda result, category: [e for e in result if e.tx_code == TxCode.CARD_REFUND and e.category_id == category]

    farmacia = catalog.category("Farmacia").category_id
    normal = run(config, catalog, events)
    settings = config.refunds.model_copy(update={"probability_by_category": {**config.refunds.probability_by_category, "Ropa y calzado": 0.0}})
    no_clothes = run(config.model_copy(update={"refunds": settings}), catalog, events)
    assert refunds_in(normal, catalog.category("Ropa y calzado").category_id)
    assert not refunds_in(no_clothes, catalog.category("Ropa y calzado").category_id)
    assert refunds_in(normal, farmacia) == refunds_in(no_clothes, farmacia)


def test_a_purchase_whose_refund_would_land_after_the_reference_date_is_not_refunded(config, catalog):
    always = config.refunds.model_copy(update={"default_probability": 1.0, "probability_by_category": {}})
    config_always = config.model_copy(update={"refunds": always})
    last_day = purchases_of(catalog, 1)[0].model_copy(update={"booking_date": REFERENCE, "value_date": REFERENCE})
    assert run(config_always, catalog, [last_day]) == [last_day]  # no refund fits before "today"


def test_with_certain_refunds_every_refundable_purchase_gets_one_and_keys_are_unique(config, catalog):
    always = config.refunds.model_copy(update={"default_probability": 1.0, "probability_by_category": {}})
    result = run(config.model_copy(update={"refunds": always}), catalog, purchases_of(catalog, 40))
    keys = [e.key for e in result if e.key]
    refund_keys = [e.refund_of_key for e in result if e.refund_of_key]
    assert len(keys) == len(set(keys)) and sorted(keys) == sorted(refund_keys)
    assert len(keys) > 20  # the ones whose refund still fits before the reference date


# ---------------------------------------------------------------------------
# Orphans: a scenario can drop a purchase, and its refund must go too
# ---------------------------------------------------------------------------


def test_a_refund_whose_purchase_is_gone_is_dropped(config, catalog):
    kept = purchases_of(catalog, 1)[0].model_copy(update={"key": "p1"})
    refund = kept.model_copy(update={"key": None, "tx_code": TxCode.CARD_REFUND, "amount_cents": 500, "refund_of_key": "p1"})
    orphan = refund.model_copy(update={"refund_of_key": "p9"})
    assert drop_orphan_refunds((kept, refund, orphan)) == (kept, refund)


def test_no_scenario_leaves_a_refund_without_its_purchase(dataset, links):
    refunds = [t for t in dataset.transactions if t.tx_code == TxCode.CARD_REFUND]
    assert len(refunds) == len(links)
    # The recent sign-up user (3) and the zero-category user (4) lost purchases: nothing dangles.
    for user_id in (3, 4):
        ids = {t.tx_id for t in dataset.transactions if t.user_id == user_id}
        assert all(p.tx_id in ids for r, p in links if r.user_id == user_id)


def test_refunds_are_a_small_share_of_what_each_user_spends_by_card(dataset):
    refunded = defaultdict(int)
    spent = defaultdict(int)
    for t in dataset.transactions:
        if t.tx_code == TxCode.CARD_REFUND:
            refunded[t.user_id] += t.amount_eur
        elif t.tx_code == TxCode.CARD_PURCHASE:
            spent[t.user_id] -= t.amount_eur
    for user_id, total in refunded.items():
        assert total < spent[user_id] / 5  # a refund is the exception, not the rule
