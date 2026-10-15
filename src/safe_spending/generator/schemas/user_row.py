from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class UserRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int = Field(description="User identifier.")
    name: str = Field(description="Synthetic name of the user.")
    city: str = Field(description="City where the user lives.")
    signup_date: date = Field(description="Date the user became a customer.")
