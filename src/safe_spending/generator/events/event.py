from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant
from safe_spending.generator.enums import TrapType, TxCode


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
    concept: str | None = None  # free text written by the sender of an incoming Bizum or transfer
    scenario_id: str | None = None  # set on events a scenario added or changed
    trap_type: TrapType | None = None  # set on injection traps (adversarial users only)
    canary: str | None = None  # the unique word a trap asks the assistant to print
