from pydantic import BaseModel, ConfigDict

from safe_spending.generator.config import Merchant


class Subscription(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant: Merchant
    day: int
