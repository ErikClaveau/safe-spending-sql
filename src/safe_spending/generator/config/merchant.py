import math

from pydantic import BaseModel, ConfigDict


class Merchant(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant_id: int
    name: str
    mcc: str
    category: str
    channel: str  # card_present | card_online | subscription | direct_debit
    weight: float
    variants: tuple[str, ...]
    median_eur: float | None = None
    sigma: float | None = None
    price_eur: float | None = None
    monthly_eur: tuple[float, float] | None = None
    kind: str | None = None
    legal_name: str | None = None

    @property
    def mean_eur(self) -> float:
        """Mean of the lognormal ticket, used to turn a budget into an event rate."""
        return self.median_eur * math.exp(self.sigma**2 / 2)
