from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant
from safe_spending.generator.enums import TxCode


class Event(BaseModel):
    """A movement before ids, descriptions and derived fields are filled in.

    Amounts are signed integer cents (negative = money out).
    """

    model_config = ConfigDict(frozen=True)

    booking_date: date
    value_date: date
    tx_code: TxCode
    amount_cents: int
    category_id: int
    merchant: Merchant | None = None
    counterparty: str | None = None
    note: str | None = None
