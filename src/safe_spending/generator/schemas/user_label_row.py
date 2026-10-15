from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserLabelRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int = Field(description="User this label belongs to.")
    archetype: str = Field(description="Behavior archetype the user was generated from.")
    monthly_income: Decimal = Field(description="Regular monthly income in euros.")
    split: str = Field(description="Dataset split of the user (functional, adversarial or population).")
