from pydantic import BaseModel, ConfigDict


class SavingsSettings(BaseModel):
    """The optional savings account and the transfers between a user's own accounts (design 5.4)."""

    model_config = ConfigDict(frozen=True)

    account_probability: float  # among users who can afford to save
    min_capacity_eur: float  # a user must be able to save at least this much a month
    share_of_capacity: tuple[float, float]  # the monthly transfer is this share of what the user can save
    rounding_eur: int  # transfers are multiples of this amount
    min_transfer_eur: int
    delay_days: tuple[int, int]  # days after the pay that the monthly transfer is made
    return_probability: float  # per month: a transfer back from savings to the current account
    return_share: tuple[float, float]  # share of the savings balance that comes back
    min_return_eur: int  # nothing is returned from a balance below this
