"""Payments in a foreign currency and the bank's exchange fee (design 5.3)."""

from datetime import date

from safe_spending.generator.config import FxSettings, Merchant
from safe_spending.generator.enums import TxCode
from safe_spending.generator.events.event import Event
from safe_spending.generator.events.foreign_amount import ForeignAmount
from safe_spending.generator.fx import FxSeries, exchange_fee_cents
from safe_spending.generator.money import convert_to_eur_cents


def foreign_purchase(
        fx: FxSeries,
        merchant: Merchant,
        category_id: int,
        operation_date: date,
        booking_date: date,
        local_cents: int,
        scenario_id: str | None = None
) -> Event:
    """A card purchase of `local_cents` (positive, minor units of the merchant's currency).

    The rate is the one of the operation date; the euro amount is that charge converted at it.
    """
    rate = fx.rate(merchant.currency, operation_date)

    return Event(
        booking_date=booking_date,
        value_date=operation_date,
        tx_code=TxCode.CARD_PURCHASE,
        amount_cents=-convert_to_eur_cents(local_cents, rate),
        category_id=category_id,
        merchant=merchant,
        foreign=ForeignAmount(
            currency=merchant.currency,
            amount_cents=-local_cents,
            rate=rate
        ),
        scenario_id=scenario_id,
    )


def exchange_fee_event(
        settings: FxSettings,
        purchase: Event,
        category_id: int,
        scenario_id: str | None = None
) -> Event:
    """The separate FEE movement that goes with a foreign-currency purchase, booked the same day.

    It is not attributed to the merchant (the bank charges it), so it has none; `note` names the
    payment it belongs to, for the statement text.
    """
    return Event(
        booking_date=purchase.booking_date,
        value_date=purchase.booking_date,
        tx_code=TxCode.FEE,
        amount_cents=-exchange_fee_cents(settings, purchase.amount_cents),
        category_id=category_id,
        note=purchase.merchant.name,
        scenario_id=scenario_id,
    )
