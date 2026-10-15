import math

from pydantic import BaseModel, ConfigDict

from safe_spending.generator.enums import Channel, UtilityKind
from safe_spending.generator.money import BASE_CURRENCY


class Merchant(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant_id: int
    name: str
    mcc: str
    category: str
    channel: Channel
    weight: float
    variants: tuple[str, ...]
    currency: str = BASE_CURRENCY  # what the merchant charges in; only scenarios use foreign ones
    median_eur: float | None = None
    sigma: float | None = None
    price_eur: float | None = None
    monthly_eur: tuple[float, float] | None = None
    kind: UtilityKind | None = None
    legal_name: str | None = None

    @property
    def mean_eur(self) -> float:
        """Mean of the lognormal ticket, used to turn a budget into an event rate."""
        return self.median_eur * math.exp(self.sigma**2 / 2)
