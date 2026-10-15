from pydantic import BaseModel, ConfigDict


class SavingsPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    iban: str
    monthly_cents: int  # what goes to the savings account after each monthly pay
    delay_days: int  # days after the pay that the transfer is made
