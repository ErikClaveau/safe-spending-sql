"""Amounts are integer cents everywhere inside the generator; never float (design 3.3)."""

from decimal import Decimal


def to_cents(euros: Decimal) -> int:
    return int(round(euros * 100))


def to_decimal(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)
