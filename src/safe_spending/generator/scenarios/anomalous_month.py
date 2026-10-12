"""Anomalous spending month (design 5.5): one big electronics purchase plus a holiday.

Everything it adds happens inside one complete month and is tagged, so the extra spend by
category is known exactly. It feeds the ambiguous and the month-versus-month questions.
"""

from datetime import date
from decimal import Decimal

from safe_spending.generator.config import Merchant
from safe_spending.generator.dates import day_in_month
from safe_spending.generator.enums import Channel, ScenarioType
from safe_spending.generator.events import Event
from safe_spending.generator.money import CENTS_PER_EUR, to_decimal
from safe_spending.generator.scenarios.anomalous_month_params import AnomalousMonthParams, ElectronicsPurchase
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row, card_purchase
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

ELECTRONICS_CATEGORY = "Electrónica"
TRAVEL_CATEGORY = "Viajes y alojamiento"
DINING_CATEGORY = "Restaurantes y bares"

# Candidate months, counted back from the end of the timeline: complete months only
# (the last one is the current, partial month).
MONTHS_BACK = (13, 3)  # from 13 months back to 3 months back, both included

ELECTRONICS_EUR = (900, 1800)
TRAVEL_BOOKINGS_EUR = ((150, 450), (500, 1100))  # transport, then accommodation
DINING_PURCHASES = (4, 6)
DINING_CENTS = (2500, 8000)
TRIP_FIRST_DAY = (6, 14)
TRIP_DAYS = (5, 7)
BOOKING_DAYS = (1, 5)
ELECTRONICS_DAYS = (3, 28)


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    rng = ctx.rng
    n_months = len(ctx.timeline)
    index = int(rng.integers(n_months - MONTHS_BACK[0], n_months - MONTHS_BACK[1] + 1))
    year, month = ctx.timeline[index]

    electronics = _electronics(ctx, year, month)
    travel = _travel(ctx, year, month)
    dining = _dining(ctx, year, month)
    added = [electronics] + travel + dining

    return ScenarioOutcome(
        events=ctx.events + tuple(added),
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.ANOMALOUS_MONTH,
            params=AnomalousMonthParams(
                month=f"{year:04d}-{month:02d}",
                electronics=ElectronicsPurchase(
                    merchant=electronics.merchant.name,
                    date=electronics.booking_date,
                    amount_eur=to_decimal(-electronics.amount_cents),
                ),
                extra_by_category_eur=_by_category(ctx, added),
                extra_total_eur=to_decimal(-sum(e.amount_cents for e in added)),
            ),
            description="A month with a large electronics purchase and a holiday on top of normal spending.",
        ),
    )


def _pick(
        ctx: ScenarioContext,
        category: str,
        exclude: set[int] = frozenset()
) -> Merchant:
    options = [
        m
        for m in ctx.catalog.merchants_in(category)
        if m.channel in (Channel.CARD_PRESENT, Channel.CARD_ONLINE) and m.merchant_id not in exclude
    ]

    return options[int(ctx.rng.integers(len(options)))]


def _day(
        ctx: ScenarioContext,
        year: int,
        month: int,
        low: int,
        high: int
) -> date:
    return day_in_month(year=year, month=month, day=int(ctx.rng.integers(low, high + 1)))


def _electronics(
        ctx: ScenarioContext,
        year: int,
        month: int
) -> Event:
    euros = int(ctx.rng.integers(ELECTRONICS_EUR[0], ELECTRONICS_EUR[1] + 1))

    return card_purchase(
        ctx=ctx,
        day=_day(ctx, year, month, *ELECTRONICS_DAYS),
        merchant=_pick(ctx, ELECTRONICS_CATEGORY),
        amount_cents=euros * CENTS_PER_EUR,
    )


def _travel(
        ctx: ScenarioContext,
        year: int,
        month: int
) -> list[Event]:
    """Two bookings (transport and accommodation) made early in the month."""
    first = _pick(ctx, TRAVEL_CATEGORY)
    second = _pick(ctx, TRAVEL_CATEGORY, exclude={first.merchant_id})
    events = []

    for merchant, (low, high) in zip((first, second), TRAVEL_BOOKINGS_EUR):
        euros = int(ctx.rng.integers(low, high + 1))
        events.append(card_purchase(
            ctx=ctx,
            day=_day(ctx, year, month, *BOOKING_DAYS),
            merchant=merchant,
            amount_cents=euros * CENTS_PER_EUR,
        ))

    return events


def _dining(
        ctx: ScenarioContext,
        year: int,
        month: int
) -> list[Event]:
    """Restaurant purchases spread over the days of the trip."""
    first_day = int(ctx.rng.integers(TRIP_FIRST_DAY[0], TRIP_FIRST_DAY[1] + 1))
    length = int(ctx.rng.integers(TRIP_DAYS[0], TRIP_DAYS[1] + 1))
    count = int(ctx.rng.integers(DINING_PURCHASES[0], DINING_PURCHASES[1] + 1))
    events = []

    for _ in range(count):
        events.append(card_purchase(
            ctx=ctx,
            day=day_in_month(year=year, month=month, day=first_day + int(ctx.rng.integers(length))),
            merchant=_pick(ctx, DINING_CATEGORY),
            amount_cents=int(ctx.rng.integers(DINING_CENTS[0], DINING_CENTS[1] + 1)),
        ))

    return events


def _by_category(
        ctx: ScenarioContext,
        events: list[Event]
) -> dict[str, Decimal]:
    names = {c.category_id: c.name for c in ctx.catalog.categories}
    totals: dict[str, int] = {}

    for event in events:
        name = names[event.category_id]
        totals[name] = totals.get(name, 0) - event.amount_cents

    return {name: to_decimal(cents) for name, cents in sorted(totals.items())}
