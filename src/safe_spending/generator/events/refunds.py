"""Refunds of card purchases (design 5.4).

Each refundable purchase is refunded with a probability that depends on its category (high in
clothes and online shopping, almost nil in supermarkets). Most refunds return the whole purchase,
some only part of it. A refund arrives days after the purchase, from the same merchant, and never
after the reference date. It points to its purchase through a key, which the pipeline later turns
into `tx_labels.refund_of_tx_id`.
"""

from datetime import date, timedelta

import numpy as np

from safe_spending.generator.config import Catalog, GeneratorConfig, RefundSettings
from safe_spending.generator.enums import Channel, TxCode
from safe_spending.generator.events.event import Event

REFUNDABLE_CHANNELS = (Channel.CARD_PRESENT, Channel.CARD_ONLINE)  # subscriptions are not refunded
KEY_PREFIX = "p"


def refund_events(
        config: GeneratorConfig,
        catalog: Catalog,
        events: list[Event],
        rng: np.random.Generator,
        end: date
) -> list[Event]:
    """`events` with the refunded purchases keyed, plus the refunds, at the end of the list."""
    settings = config.refunds
    category_names = {c.category_id: c.name for c in catalog.categories}
    result = list(events)
    refunds = []

    for index, event in enumerate(events):
        if not _is_refundable(event):
            continue

        # Four draws per refundable purchase, whatever the outcome, so one purchase's result
        # never shifts the draws of the next ones.
        decision, kind, fraction, delay = _draw(rng, settings)
        probability = settings.probability_by_category.get(
            category_names[event.category_id],
            settings.default_probability
        )
        refund_date = event.booking_date + timedelta(days=delay)

        if decision >= probability or refund_date > end:
            continue

        key = f"{KEY_PREFIX}{index}"
        result[index] = event.model_copy(update={"key": key})
        refunds.append(_refund(event, key, refund_date, kind < settings.total_share, fraction))

    return result + refunds


def drop_orphan_refunds(events: tuple[Event, ...]) -> tuple[Event, ...]:
    """Removes refunds whose purchase is gone (a scenario may have dropped it)."""
    keys = {e.key for e in events if e.key is not None}

    return tuple(e for e in events if e.refund_of_key is None or e.refund_of_key in keys)


def _is_refundable(event: Event) -> bool:
    return (
        event.tx_code == TxCode.CARD_PURCHASE
        and event.merchant is not None
        and event.merchant.channel in REFUNDABLE_CHANNELS
        and event.foreign is None
    )


def _draw(
        rng: np.random.Generator,
        settings: RefundSettings
) -> tuple[float, float, float, int]:
    decision = float(rng.random())
    kind = float(rng.random())
    fraction = float(rng.uniform(*settings.partial_fraction))
    delay = int(rng.integers(settings.delay_days[0], settings.delay_days[1] + 1))

    return decision, kind, fraction, delay


def _refund(
        purchase: Event,
        key: str,
        refund_date: date,
        total: bool,
        fraction: float
) -> Event:
    spent = -purchase.amount_cents
    returned = spent if total or spent < 2 else max(1, min(spent - 1, round(spent * fraction)))

    return Event(
        booking_date=refund_date,
        value_date=refund_date,
        tx_code=TxCode.CARD_REFUND,
        amount_cents=returned,
        category_id=purchase.category_id,
        merchant=purchase.merchant,
        refund_of_key=key,
    )
