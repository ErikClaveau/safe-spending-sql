from pydantic import BaseModel, ConfigDict


class AccountRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: int
    user_id: int
    iban: str
    currency: str
