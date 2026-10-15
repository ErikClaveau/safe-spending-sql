from pydantic import BaseModel, ConfigDict, Field


class RefundSettings(BaseModel):
    """How often a card purchase is refunded and what the refund looks like (design 5.4)."""

    model_config = ConfigDict(frozen=True)

    probability_by_category: dict[str, float] = Field(
        description="Probability that a purchase is refunded, by category name; the rest use the default."
    )
    default_probability: float = Field(description="Refund probability of categories not listed.")
    total_share: float = Field(description="Share of refunds that return the whole purchase.")
    partial_fraction: tuple[float, float] = Field(
        description="A partial refund returns a fraction in this range."
    )
    delay_days: tuple[int, int] = Field(
        description="Inclusive days between the purchase and its refund."
    )
