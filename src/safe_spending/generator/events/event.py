from datetime import date

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant
from safe_spending.generator.enums import TrapType, TxCode
from safe_spending.generator.events.foreign_amount import ForeignAmount


class Event(BaseModel):
    """A movement before ids, descriptions and derived fields are filled in.

    `amount_cents` is the amount in euros, the currency of every account, signed in integer
    cents (negative = money out). An operation made in another currency also carries `foreign`.
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
    foreign: ForeignAmount | None = None  # set on payments in a currency other than the euro
    key: str | None = None  # names a purchase so that a refund can point to it
    refund_of_key: str | None = None  # on a refund: the key of the purchase it returns
    scenario_id: str | None = None  # set on events a scenario added or changed
    trap_type: TrapType | None = None  # set on injection traps (adversarial users only)
    canary: str | None = None  # the unique word a trap asks the assistant to print
