from datetime import date

from pydantic import BaseModel


class RecentSignupParams(BaseModel):
    signup_date: date
    history_days: int
