from datetime import date

from pydantic import BaseModel, ConfigDict


class UserRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: int
    name: str
    city: str
    signup_date: date
