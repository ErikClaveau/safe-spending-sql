from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LondonTripParams(BaseModel):
    """Ground truth of the trip. Euro totals are the sum of each payment converted at its own day's rate."""

    currency: str = Field(description="Currency of the trip.")
    first_day: date = Field(description="First day of the trip.")
    last_day: date = Field(description="Last day of the trip.")
    n_days: int = Field(description="Length of the trip in days.")
    n_purchases: int = Field(description="Number of purchases; one exchange fee goes with each of them.")
    total_gbp: Decimal = Field(description="Total of the purchases in pounds.")
    total_eur: Decimal = Field(description="The purchases alone, in euros.")
    total_fees_eur: Decimal = Field(description="The exchange fees alone, in euros.")
    total_charged_eur: Decimal = Field(description="Purchases plus fees: what left the account, in euros.")
    by_category_eur: dict[str, Decimal] = Field(description="Purchases alone, by category, in euros.")
