from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant


class Utility(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant: Merchant
    day: int
    base_cents: int
