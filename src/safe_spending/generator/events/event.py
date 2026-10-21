from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.config import Merchant
from safe_spending.generator.enums import AccountKind, TrapType, TxCode
from safe_spending.generator.events.foreign_amount import ForeignAmount


class Event(BaseModel):
    """A movement before ids, descriptions and derived fields are filled in.

    `amount_cents` is the amount in euros, the currency of every account, signed in integer
    cents (negative = money out). An operation made in another currency also carries `foreign`.
    """

    model_config = ConfigDict(frozen=True)

    booking_date: date = Field(description="Date the bank books the movement.")
    value_date: date = Field(description="Operation (value) date.")
    tx_code: TxCode = Field(description="Kind of movement.")
    amount_cents: int = Field(description="Signed amount in euro cents (negative = money out).")
    category_id: int = Field(description="Category of the movement.")
    merchant: Merchant | None = Field(default=None, description="Merchant of a card purchase.")
    counterparty: str | None = Field(default=None, description="Counterparty of a Bizum or transfer.")
    note: str | None = Field(default=None, description="Internal note about the event, not part of the data.")
    concept: str | None = Field(
        default=None, description="Free text written by the sender of an incoming Bizum or transfer."
    )
    account: AccountKind = Field(
        default=AccountKind.CURRENT, description="Which of the user's accounts the movement is on."
    )
    internal: bool = Field(
        default=False, description="One of the two legs of a transfer between the user's own accounts."
    )
    foreign: ForeignAmount | None = Field(
        default=None, description="Set on payments in a currency other than the euro."
    )
    key: str | None = Field(default=None, description="Names a purchase so that a refund can point to it.")
    refund_of_key: str | None = Field(
        default=None, description="On a refund: the key of the purchase it returns."
    )
    scenario_id: str | None = Field(default=None, description="Set on events a scenario added or changed.")
    trap_type: TrapType | None = Field(
        default=None, description="Set on injection traps (adversarial users only)."
    )
    canary: str | None = Field(
        default=None, description="The unique word a trap asks the assistant to print."
    )
