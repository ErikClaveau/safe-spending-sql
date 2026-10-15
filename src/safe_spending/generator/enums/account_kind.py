from enum import StrEnum


class AccountKind(StrEnum):
    """Which of a user's accounts a movement belongs to (design 5.1: one or two accounts)."""

    CURRENT = "current"
    SAVINGS = "savings"
