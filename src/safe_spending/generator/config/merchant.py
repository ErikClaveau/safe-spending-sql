import math

from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.enums import Channel, UtilityKind
from safe_spending.generator.money import BASE_CURRENCY


class Merchant(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant_id: int = Field(description="Merchant identifier.")
    name: str = Field(description="Normalized merchant name.")
    mcc: str = Field(description="Merchant category code.")
    category: str = Field(description="Name of the category its purchases fall in.")
    channel: Channel = Field(description="Where the purchase is made.")
    weight: float = Field(description="Relative weight when a user picks a merchant.")
    variants: tuple[str, ...] = Field(description="Ways the bank writes the merchant in the statement.")
    currency: str = Field(
        default=BASE_CURRENCY,
        description="What the merchant charges in; only scenarios use foreign ones.",
    )
    median_eur: float | None = Field(default=None, description="Median ticket in euros.")
    sigma: float | None = Field(default=None, description="Sigma of the lognormal ticket.")
    price_eur: float | None = Field(default=None, description="Fixed price in euros, for subscriptions.")
    monthly_eur: tuple[float, float] | None = Field(
        default=None, description="Range of the monthly amount in euros, for utilities."
    )
    kind: UtilityKind | None = Field(default=None, description="Kind of utility, for utilities.")
    legal_name: str | None = Field(default=None, description="Legal name of the company, when it differs.")

    @property
    def mean_eur(self) -> float:
        """Mean of the lognormal ticket, used to turn a budget into an event rate."""
        return self.median_eur * math.exp(self.sigma**2 / 2)
