from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UserLabelRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int
    archetype: str
    monthly_income: Decimal
    split: str
