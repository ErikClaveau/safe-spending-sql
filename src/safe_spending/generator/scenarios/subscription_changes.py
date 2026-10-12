"""Subscription changes (design 5.5): one subscription starts, one raises its price, one is cancelled.

The three use merchants the user does not already subscribe to, so the ground truth is not
mixed with the baseline subscriptions. Every charge they produce is tagged with the scenario.
"""

from safe_spending.generator.config import Merchant
from safe_spending.generator.dates import day_in_month
from safe_spending.generator.enums import Channel, ScenarioType
from safe_spending.generator.events import Event
from safe_spending.generator.money import to_decimal
from safe_spending.generator.profile.builder import FIRST_BILLING_DAY, LAST_BILLING_DAY
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row, card_purchase, subscription_price_cents
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome
from safe_spending.generator.scenarios.subscription_changes_params import (
    CancelledSubscription,
    PriceIncrease,
    StartedSubscription,
    SubscriptionChangesParams,
)

# Position in the month timeline (0 = first month). Margins keep every change away from the
# edges of the period, so each one has data before and after it.
START_FIRST_MONTH = 8
START_LAST_MARGIN = 5  # the new subscription has at least this many months to charge
CHANGE_FIRST_MONTH = 6
CHANGE_LAST_MARGIN = 6  # price increase and cancellation leave at least this many months after

PRICE_INCREASE_CENTS = (100, 300)  # inclusive range of the monthly increase


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    rng = ctx.rng
    started, raised, cancelled = _pick_merchants(ctx)
    n_months = len(ctx.timeline)

    start_index = int(rng.integers(START_FIRST_MONTH, n_months - START_LAST_MARGIN + 1))
    raise_index = int(rng.integers(CHANGE_FIRST_MONTH, n_months - CHANGE_LAST_MARGIN + 1))
    cancel_index = int(rng.integers(CHANGE_FIRST_MONTH, n_months - CHANGE_LAST_MARGIN + 1))
    increase_cents = int(rng.integers(PRICE_INCREASE_CENTS[0], PRICE_INCREASE_CENTS[1] + 1))

    started_day, raised_day, cancelled_day = (_billing_day(ctx) for _ in range(3))
    old_cents = subscription_price_cents(raised)
    new_cents = old_cents + increase_cents

    started_charges = _charges(ctx, started, started_day, first_index=start_index, last_index=n_months - 1)
    cancelled_charges = _charges(ctx, cancelled, cancelled_day, first_index=0, last_index=cancel_index)
    raised_charges = (
        _charges(ctx, raised, raised_day, first_index=0, last_index=raise_index - 1)
        + _charges(ctx, raised, raised_day, first_index=raise_index, last_index=n_months - 1, price_cents=new_cents)
    )

    params = SubscriptionChangesParams(
        started=StartedSubscription(
            merchant=started.name,
            first_charge=started_charges[0].booking_date,
            monthly_eur=to_decimal(subscription_price_cents(started)),
        ),
        price_increase=PriceIncrease(
            merchant=raised.name,
            first_charge_at_new_price=next(e.booking_date for e in raised_charges if e.amount_cents == -new_cents),
            old_eur=to_decimal(old_cents),
            new_eur=to_decimal(new_cents),
        ),
        cancelled=CancelledSubscription(
            merchant=cancelled.name,
            last_charge=cancelled_charges[-1].booking_date,
            monthly_eur=to_decimal(subscription_price_cents(cancelled)),
        ),
    )

    return ScenarioOutcome(
        events=ctx.events + tuple(started_charges + raised_charges + cancelled_charges),
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.SUBSCRIPTION_CHANGES,
            params=params,
            description="One subscription starts, another raises its price and a third is cancelled.",
        ),
    )


def _pick_merchants(ctx: ScenarioContext) -> list[Merchant]:
    subscribed = {s.merchant.merchant_id for s in ctx.profile.subscriptions}
    available = [
        m
        for m in ctx.catalog.merchants
        if m.channel == Channel.SUBSCRIPTION and m.merchant_id not in subscribed
    ]
    indexes = ctx.rng.choice(len(available), size=3, replace=False)

    return [available[int(i)] for i in indexes]


def _billing_day(ctx: ScenarioContext) -> int:
    return int(ctx.rng.integers(FIRST_BILLING_DAY, LAST_BILLING_DAY + 1))


def _charges(
        ctx: ScenarioContext,
        merchant: Merchant,
        day: int,
        first_index: int,
        last_index: int,
        price_cents: int | None = None
) -> list[Event]:
    """Monthly charges from the first to the last month index, both included, on a fixed day."""
    cents = price_cents if price_cents is not None else subscription_price_cents(merchant)
    events = []

    for year, month in ctx.timeline[first_index:last_index + 1]:
        charge_date = day_in_month(year=year, month=month, day=day)
        if ctx.config.period_start <= charge_date <= ctx.end:
            events.append(card_purchase(ctx=ctx, day=charge_date, merchant=merchant, amount_cents=cents))

    return events
