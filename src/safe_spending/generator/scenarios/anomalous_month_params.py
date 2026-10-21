from datetime import date as Day
from decimal import Decimal

from pydantic import BaseModel, Field


class ElectronicsPurchase(BaseModel):
    merchant: str = Field(description="Merchant of the purchase.")
    date: Day = Field(description="Date of the purchase.")
    amount_eur: Decimal = Field(description="Amount of the purchase in euros.")


class AnomalousMonthParams(BaseModel):
    month: str = Field(description="Anomalous month, as YYYY-MM.")
    electronics: ElectronicsPurchase = Field(description="The large electronics purchase.")
    extra_by_category_eur: dict[str, Decimal] = Field(description="Extra spending by category, in euros.")
    extra_total_eur: Decimal = Field(description="Total extra spending in euros.")
