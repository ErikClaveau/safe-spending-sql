from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class LondonTripParams(BaseModel):
    """Ground truth of the trip. Euro totals are the sum of each payment converted at its own day's rate."""

    currency: str
    first_day: date
    last_day: date
    n_days: int
    n_purchases: int  # one exchange fee goes with each of them
    total_gbp: Decimal
    total_eur: Decimal  # the purchases alone
    total_fees_eur: Decimal  # the exchange fees alone
    total_charged_eur: Decimal  # purchases plus fees: what left the account
    by_category_eur: dict[str, Decimal]  # purchases alone, by category
