from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.enums import TxCode


class TransactionRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    tx_id: int = Field(description="Transaction identifier.")
    account_id: int = Field(description="Account the movement is on.")
    user_id: int = Field(description="Owner of the account.")
    booking_date: date = Field(description="Date the bank booked the movement.")
    value_date: date = Field(description="Operation (value) date; foreign rates apply on it.")
    amount: Decimal = Field(description="Signed amount in the movement's currency.")
    currency: str = Field(description="ISO 4217 currency code of `amount`.")
    exchange_rate: Decimal | None = Field(
        description="Units of `currency` per 1 EUR on the value date; None for euro movements."
    )
    amount_eur: Decimal = Field(description="Signed amount in euros; its sign is fixed by `tx_code`.")
    description_raw: str = Field(description="Original statement description, untrusted third-party text.")
    counterparty: str | None = Field(description="Counterparty name for Bizum and transfers; None otherwise.")
    tx_code: TxCode = Field(description="Kind of movement; fixes the sign of `amount_eur`.")
    merchant_id: int | None = Field(description="Merchant of a card purchase; None when there is none.")
    category_id: int = Field(description="Category assigned to the movement.")
    counterparty_account_id: int | None = Field(
        description="Other account of the same user on an internal transfer; None otherwise."
    )
