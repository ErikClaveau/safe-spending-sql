from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class RefundKind(StrEnum):
    TOTAL = "total"
    PARTIAL = "partial"
    NONE = "none"


class AmazonPurchase(BaseModel):
    date: date
    amount_eur: Decimal
    kind: RefundKind
    refund_date: date | None
    refund_eur: Decimal | None
    crosses_month: bool  # the refund arrives in a later month than the purchase


class AmazonRefundsParams(BaseModel):
    """Ground truth: with the baseline Amazon activity removed, these six purchases are all there is."""

    merchant: str
    purchases: list[AmazonPurchase]
    purchased_eur: Decimal
    refunded_eur: Decimal
    net_eur: Decimal  # purchased minus refunded: what Amazon cost in the end
    n_total_refunds: int
    n_partial_refunds: int
