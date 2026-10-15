from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ForeignAmount(BaseModel):
    """The original amount of an operation made in another currency.

    `amount_cents` is in the minor units of `currency`, signed like the euro amount. The euro
    amount lives in `Event.amount_cents`; `rate` is units of `currency` per 1 EUR.
    """

    model_config = ConfigDict(frozen=True)

    currency: str
    amount_cents: int
    rate: Decimal
