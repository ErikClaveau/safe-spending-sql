"""London trip (design 5.5): a few days of hotel, transport and restaurants paid in pounds.

Every payment is converted at the rate of its day and comes with its own exchange fee, so the
trip's cost in euros, the fees and the original amount in pounds are all known exactly.
"""

from datetime import date
from decimal import Decimal

import numpy as np

from safe_spending.generator.config import Merchant
from safe_spending.generator.dates import day_in_month
from safe_spending.generator.enums import ScenarioType
from safe_spending.generator.events import Event, exchange_fee_event, foreign_purchase
from safe_spending.generator.money import CENTS_PER_EUR, to_decimal
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import booking_delay_days, build_row
from safe_spending.generator.scenarios.london_trip_params import LondonTripParams
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

CURRENCY = "GBP"

HOTEL_CATEGORY = "Viajes y alojamiento"
TRANSIT_CATEGORY = "Transporte público"
TAXI_CATEGORY = "Taxi y VTC"
DINING_CATEGORY = "Restaurantes y bares"
FEE_CATEGORY = "Comisiones"

TRIP_DAYS = (4, 6)  # inclusive range of days
FIRST_MONTH = 8  # position in the month timeline: the trip has history before and after it
LAST_MARGIN = 4
FIRST_DAY_OF_TRIP = (3, 20)  # the whole trip stays inside one month

# Amounts in pounds, in pence.
HOTEL_NIGHT_GBP = (85, 150)
TRANSIT_PENCE = (250, 1500)
TRANSIT_PER_DAY = (1, 2)
TAXI_PENCE = (1200, 3500)
TAXI_PROBABILITY = 0.4  # per day
DINING_PENCE = (800, 4500)
DINING_PER_DAY = (2, 3)


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    rng = ctx.rng
    n_days = int(rng.integers(TRIP_DAYS[0], TRIP_DAYS[1] + 1))
    year, month = ctx.timeline[int(rng.integers(FIRST_MONTH, len(ctx.timeline) - LAST_MARGIN + 1))]
    first = day_in_month(year=year, month=month, day=int(rng.integers(FIRST_DAY_OF_TRIP[0], FIRST_DAY_OF_TRIP[1] + 1)))
    days = [date.fromordinal(first.toordinal() + i) for i in range(n_days)]

    purchases = _hotel(ctx, days) + _transit(ctx, days) + _taxis(ctx, days) + _dining(ctx, days)
    fees = [
        exchange_fee_event(
            settings=ctx.config.fx,
            purchase=purchase,
            category_id=ctx.catalog.category(FEE_CATEGORY).category_id,
            scenario_id=ctx.scenario_id
        )
        for purchase in purchases
    ]

    return ScenarioOutcome(
        events=ctx.events + tuple(purchases + fees),
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.LONDON_TRIP,
            params=_params(ctx, days, purchases, fees),
            description="A few days in London paid in pounds, each payment with its own exchange fee.",
        ),
    )


def _pick(
        ctx: ScenarioContext,
        category: str
) -> Merchant:
    options = ctx.catalog.merchants_in(category, currency=CURRENCY)

    return options[int(ctx.rng.integers(len(options)))]


def _purchase(
        ctx: ScenarioContext,
        merchant: Merchant,
        day: date,
        pence: int
) -> Event:
    return foreign_purchase(
        fx=ctx.fx,
        merchant=merchant,
        category_id=ctx.catalog.category(merchant.category).category_id,
        operation_date=day,
        booking_date=date.fromordinal(day.toordinal() + booking_delay_days(ctx)),
        local_cents=pence,
        scenario_id=ctx.scenario_id
    )


def _hotel(
        ctx: ScenarioContext,
        days: list[date]
) -> list[Event]:
    """One charge for the whole stay, made on the arrival day."""
    nights = len(days) - 1
    per_night = int(ctx.rng.integers(HOTEL_NIGHT_GBP[0], HOTEL_NIGHT_GBP[1] + 1))

    return [_purchase(ctx, _pick(ctx, HOTEL_CATEGORY), days[0], nights * per_night * CENTS_PER_EUR)]


def _transit(
        ctx: ScenarioContext,
        days: list[date]
) -> list[Event]:
    merchant = _pick(ctx, TRANSIT_CATEGORY)

    return [
        _purchase(ctx, merchant, day, int(ctx.rng.integers(TRANSIT_PENCE[0], TRANSIT_PENCE[1] + 1)))
        for day in days
        for _ in range(int(ctx.rng.integers(TRANSIT_PER_DAY[0], TRANSIT_PER_DAY[1] + 1)))
    ]


def _taxis(
        ctx: ScenarioContext,
        days: list[date]
) -> list[Event]:
    merchant = _pick(ctx, TAXI_CATEGORY)

    return [
        _purchase(ctx, merchant, day, int(ctx.rng.integers(TAXI_PENCE[0], TAXI_PENCE[1] + 1)))
        for day in days
        if ctx.rng.random() < TAXI_PROBABILITY
    ]


def _dining(
        ctx: ScenarioContext,
        days: list[date]
) -> list[Event]:
    return [
        _purchase(ctx, _pick(ctx, DINING_CATEGORY), day, int(ctx.rng.integers(DINING_PENCE[0], DINING_PENCE[1] + 1)))
        for day in days
        for _ in range(int(ctx.rng.integers(DINING_PER_DAY[0], DINING_PER_DAY[1] + 1)))
    ]


def _params(
        ctx: ScenarioContext,
        days: list[date],
        purchases: list[Event],
        fees: list[Event]
) -> LondonTripParams:
    names = {c.category_id: c.name for c in ctx.catalog.categories}
    by_category: dict[str, int] = {}
    for purchase in purchases:
        name = names[purchase.category_id]
        by_category[name] = by_category.get(name, 0) - purchase.amount_cents

    total_eur = -sum(p.amount_cents for p in purchases)
    total_fees = -sum(f.amount_cents for f in fees)

    return LondonTripParams(
        currency=CURRENCY,
        first_day=days[0],
        last_day=days[-1],
        n_days=len(days),
        n_purchases=len(purchases),
        total_gbp=to_decimal(-sum(p.foreign.amount_cents for p in purchases)),
        total_eur=to_decimal(total_eur),
        total_fees_eur=to_decimal(total_fees),
        total_charged_eur=to_decimal(total_eur + total_fees),
        by_category_eur={name: to_decimal(cents) for name, cents in sorted(by_category.items())},
    )
