from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FxSeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    rates: dict[str, dict[date, Decimal]]

    def rate(
            self,
            currency: str,
            day: date
    ) -> Decimal:
        return self.rates[currency][day]
