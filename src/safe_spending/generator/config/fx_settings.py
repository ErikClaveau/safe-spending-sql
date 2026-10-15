from pydantic import BaseModel, ConfigDict, Field


class CurrencyRate(BaseModel):
    """How the synthetic daily rate of one currency behaves (design 5.3)."""

    model_config = ConfigDict(frozen=True)

    base: float = Field(description="Units of this currency per 1 EUR the series reverts to.")
    daily_sigma: float = Field(description="Standard deviation of the daily log change.")
    reversion: float = Field(
        description="Share of the gap to `base` closed each day (0 = pure random walk)."
    )


class FxSettings(BaseModel):
    """Exchange rates and the bank's fee for a card payment in a foreign currency."""

    model_config = ConfigDict(frozen=True)

    currencies: dict[str, CurrencyRate] = Field(description="Rate behavior of each currency, by ISO code.")
    fee_rate: float = Field(description="Share of the euro amount charged as a separate FEE movement.")
    fee_min_eur: float = Field(description="A fee is never below this amount.")
