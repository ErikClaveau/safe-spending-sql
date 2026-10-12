from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ElectronicsPurchase(BaseModel):
    merchant: str
    date: date
    amount_eur: Decimal


class AnomalousMonthParams(BaseModel):
    month: str  # YYYY-MM
    electronics: ElectronicsPurchase
    extra_by_category_eur: dict[str, Decimal]
    extra_total_eur: Decimal
