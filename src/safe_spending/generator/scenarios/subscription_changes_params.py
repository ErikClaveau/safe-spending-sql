from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StartedSubscription(BaseModel):
    merchant: str
    first_charge: date
    monthly_eur: Decimal


class PriceIncrease(BaseModel):
    merchant: str
    first_charge_at_new_price: date
    old_eur: Decimal
    new_eur: Decimal


class CancelledSubscription(BaseModel):
    merchant: str
    last_charge: date
    monthly_eur: Decimal


class SubscriptionChangesParams(BaseModel):
    started: StartedSubscription
    price_increase: PriceIncrease
    cancelled: CancelledSubscription
