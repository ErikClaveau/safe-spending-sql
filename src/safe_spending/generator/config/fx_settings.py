from pydantic import BaseModel, ConfigDict


class CurrencyRate(BaseModel):
    """How the synthetic daily rate of one currency behaves (design 5.3)."""

    model_config = ConfigDict(frozen=True)

    base: float  # units of this currency per 1 EUR the series reverts to
    daily_sigma: float  # standard deviation of the daily log change
    reversion: float  # share of the gap to `base` closed each day (0 = pure random walk)


class FxSettings(BaseModel):
    """Exchange rates and the bank's fee for a card payment in a foreign currency."""

    model_config = ConfigDict(frozen=True)

    currencies: dict[str, CurrencyRate]
    fee_rate: float  # share of the euro amount charged as a separate FEE movement
    fee_min_eur: float  # a fee is never below this amount
