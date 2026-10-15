from pydantic import BaseModel, ConfigDict, Field


class AccountRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_id: int = Field(description="Account identifier: user_id * 10 + 1 (current) or + 2 (savings).")
    user_id: int = Field(description="Owner of the account.")
    iban: str = Field(description="Synthetic IBAN of the account.")
    currency: str = Field(description="ISO 4217 currency code of the account.")
