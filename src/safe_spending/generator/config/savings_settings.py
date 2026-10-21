from pydantic import BaseModel, ConfigDict, Field


class SavingsSettings(BaseModel):
    """The optional savings account and the transfers between a user's own accounts (design 5.4)."""

    model_config = ConfigDict(frozen=True)

    account_probability: float = Field(description="Probability of a savings account among users who can afford to save.")
    min_capacity_eur: float = Field(description="A user must be able to save at least this much a month.")
    share_of_capacity: tuple[float, float] = Field(
        description="The monthly transfer is a share of what the user can save, in this range."
    )
    rounding_eur: int = Field(description="Transfers are multiples of this amount.")
    min_transfer_eur: int = Field(description="Smallest monthly transfer, in euros.")
    delay_days: tuple[int, int] = Field(
        description="Days after the pay that the monthly transfer is made."
    )
    return_probability: float = Field(
        description="Per month: probability of a transfer back from savings to the current account."
    )
    return_share: tuple[float, float] = Field(
        description="Share of the savings balance that comes back, in this range."
    )
    min_return_eur: int = Field(description="Nothing is returned from a balance below this.")
