from datetime import date as Day
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class RefundKind(StrEnum):
    TOTAL = "total"
    PARTIAL = "partial"
    NONE = "none"


class AmazonPurchase(BaseModel):
    date: Day = Field(description="Date of the purchase.")
    amount_eur: Decimal = Field(description="Amount of the purchase in euros.")
    kind: RefundKind = Field(description="Whether the purchase is refunded totally, partially or not at all.")
    refund_date: Day | None = Field(description="Date of the refund; None when there is none.")
    refund_eur: Decimal | None = Field(description="Amount refunded in euros; None when there is none.")
    crosses_month: bool = Field(description="The refund arrives in a later month than the purchase.")


class AmazonRefundsParams(BaseModel):
    """Ground truth: with the baseline Amazon activity removed, these six purchases are all there is."""

    merchant: str = Field(description="Merchant name.")
    purchases: list[AmazonPurchase] = Field(description="The scripted purchases.")
    purchased_eur: Decimal = Field(description="Total purchased in euros.")
    refunded_eur: Decimal = Field(description="Total refunded in euros.")
    net_eur: Decimal = Field(description="Purchased minus refunded: what Amazon cost in the end.")
    n_total_refunds: int = Field(description="Number of purchases refunded in full.")
    n_partial_refunds: int = Field(description="Number of purchases refunded in part.")
