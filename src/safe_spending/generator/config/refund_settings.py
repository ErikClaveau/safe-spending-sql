from pydantic import BaseModel, ConfigDict


class RefundSettings(BaseModel):
    """How often a card purchase is refunded and what the refund looks like (design 5.4)."""

    model_config = ConfigDict(frozen=True)

    # Probability that a purchase is refunded, by category name; the rest use the default.
    probability_by_category: dict[str, float]
    default_probability: float
    total_share: float  # share of refunds that return the whole purchase
    partial_fraction: tuple[float, float]  # a partial refund returns a fraction in this range
    delay_days: tuple[int, int]  # inclusive days between the purchase and its refund
