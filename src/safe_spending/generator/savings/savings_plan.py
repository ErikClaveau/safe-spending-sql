from pydantic import BaseModel, ConfigDict, Field


class SavingsPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    iban: str = Field(description="Synthetic IBAN of the savings account.")
    monthly_cents: int = Field(description="What goes to the savings account after each monthly pay.")
    delay_days: int = Field(description="Days after the pay that the transfer is made.")
