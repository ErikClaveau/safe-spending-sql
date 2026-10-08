"""Amounts are integer cents everywhere inside the generator; never float (design 3.3)."""

from decimal import Decimal

CENTS_PER_EUR = 100


def to_cents(euros: Decimal) -> int:
    return int(round(euros * CENTS_PER_EUR))


def to_decimal(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)
