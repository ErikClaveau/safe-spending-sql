"""Amazon purchases and refunds (design 5.5): total refunds, partial refunds and one that crosses months.

The user's baseline Amazon activity (purchases and their random refunds) is removed first, so the
six scripted purchases are the only Amazon movements and the net amount is known exactly.
Everything is booked on the day it happens, which keeps "which month" unambiguous.
"""

from datetime import date, timedelta

from safe_spending.generator.dates import day_in_month
from safe_spending.generator.enums import ScenarioType, TxCode
from safe_spending.generator.events import Event
from safe_spending.generator.money import to_decimal
from safe_spending.generator.scenarios.amazon_refunds_params import (
    AmazonPurchase,
    AmazonRefundsParams,
    RefundKind,
)
from safe_spending.generator.scenarios.context import ScenarioContext
from safe_spending.generator.scenarios.helpers import build_row, card_purchase
from safe_spending.generator.scenarios.scenario_outcome import ScenarioOutcome

MERCHANT = "AMAZON"
FIRST_MONTH = 6  # position in the month timeline
LAST_MARGIN = 6  # every refund has arrived well before the reference date

PURCHASE_CENTS = (2000, 25000)
EARLY_DAYS = (3, 12)  # purchase day for refunds that stay inside the month
REFUND_DELAY = (3, 12)  # days from purchase to refund when it stays inside the month
LATE_DAYS = (24, 28)  # purchase day for the refund that crosses the month
NEXT_MONTH_REFUND_DAYS = (3, 8)  # refund day of the following month
UNREFUNDED_DAYS = (15, 25)
PARTIAL_FRACTION = (0.3, 0.7)

# (month offset from the first scripted month, kind of refund, refund crosses the month)
PLAN = (
    (0, RefundKind.TOTAL, False),
    (1, RefundKind.TOTAL, True),
    (2, RefundKind.PARTIAL, False),
    (3, RefundKind.PARTIAL, False),
    (0, RefundKind.NONE, False),
    (2, RefundKind.NONE, False),
)


def inject(ctx: ScenarioContext) -> ScenarioOutcome:
    merchant = next(m for m in ctx.catalog.merchants if m.name == MERCHANT)
    base_index = int(ctx.rng.integers(FIRST_MONTH, len(ctx.timeline) - LAST_MARGIN + 1))
    kept = tuple(e for e in ctx.events if e.merchant is None or e.merchant.name != MERCHANT)

    added: list[Event] = []
    purchases: list[AmazonPurchase] = []
    for number, (offset, kind, crosses) in enumerate(PLAN, start=1):
        year, month = ctx.timeline[base_index + offset]
        purchase_day = _purchase_day(ctx, year, month, kind, crosses)
        cents = int(ctx.rng.integers(PURCHASE_CENTS[0], PURCHASE_CENTS[1] + 1))
        key = f"{ctx.scenario_id}-{number}"
        purchase = card_purchase(ctx=ctx, day=purchase_day, merchant=merchant, amount_cents=cents)
        added.append(purchase.model_copy(update={"key": key}))

        refund = _refund(ctx, purchase, key, year, month, kind, crosses)
        if refund is not None:
            added.append(refund)

        purchases.append(AmazonPurchase(
            date=purchase_day,
            amount_eur=to_decimal(cents),
            kind=kind,
            refund_date=refund.booking_date if refund else None,
            refund_eur=to_decimal(refund.amount_cents) if refund else None,
            crosses_month=refund is not None and refund.booking_date.month != purchase_day.month,
        ))

    return ScenarioOutcome(
        events=kept + tuple(added),
        row=build_row(
            ctx=ctx,
            scenario_type=ScenarioType.AMAZON_REFUNDS,
            params=_params(purchases),
            description="Six Amazon purchases: two refunded in full (one in the next month), two in part, two never.",
        ),
    )


def _purchase_day(
        ctx: ScenarioContext,
        year: int,
        month: int,
        kind: RefundKind,
        crosses: bool
) -> date:
    low, high = LATE_DAYS if crosses else UNREFUNDED_DAYS if kind == RefundKind.NONE else EARLY_DAYS

    return day_in_month(year=year, month=month, day=int(ctx.rng.integers(low, high + 1)))


def _refund(
        ctx: ScenarioContext,
        purchase: Event,
        key: str,
        year: int,
        month: int,
        kind: RefundKind,
        crosses: bool
) -> Event | None:
    if kind == RefundKind.NONE:
        return None

    spent = -purchase.amount_cents
    if crosses:
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        low, high = NEXT_MONTH_REFUND_DAYS
        day = day_in_month(year=next_year, month=next_month, day=int(ctx.rng.integers(low, high + 1)))
    else:
        day = purchase.booking_date + timedelta(days=int(ctx.rng.integers(REFUND_DELAY[0], REFUND_DELAY[1] + 1)))
    returned = spent if kind == RefundKind.TOTAL else max(1, min(spent - 1, round(spent * float(ctx.rng.uniform(*PARTIAL_FRACTION)))))

    return Event(
        booking_date=day,
        value_date=day,
        tx_code=TxCode.CARD_REFUND,
        amount_cents=returned,
        category_id=purchase.category_id,
        merchant=purchase.merchant,
        refund_of_key=key,
        scenario_id=ctx.scenario_id,
    )


def _params(purchases: list[AmazonPurchase]) -> AmazonRefundsParams:
    refunded = sum((p.refund_eur for p in purchases if p.refund_eur is not None), start=to_decimal(0))
    purchased = sum((p.amount_eur for p in purchases), start=to_decimal(0))

    return AmazonRefundsParams(
        merchant=MERCHANT,
        purchases=purchases,
        purchased_eur=purchased,
        refunded_eur=refunded,
        net_eur=purchased - refunded,
        n_total_refunds=sum(1 for p in purchases if p.kind == RefundKind.TOTAL),
        n_partial_refunds=sum(1 for p in purchases if p.kind == RefundKind.PARTIAL),
    )
