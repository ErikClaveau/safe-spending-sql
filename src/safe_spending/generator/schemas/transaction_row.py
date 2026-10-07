from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.enums import TxCode


class TransactionRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    tx_id: int
    account_id: int
    user_id: int
    booking_date: date
    value_date: date
    amount: Decimal
    currency: str
    exchange_rate: Decimal | None
    amount_eur: Decimal
    description_raw: str
    counterparty: str | None
    tx_code: TxCode
    merchant_id: int | None
    category_id: int
    counterparty_account_id: int | None
