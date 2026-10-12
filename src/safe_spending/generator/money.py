"""Amounts are integer cents everywhere inside the generator; never float (design 3.3)."""

from decimal import Decimal

CENTS_PER_EUR = 100
BASE_CURRENCY = "EUR"  # the only currency until FX arrives (slice 3); matches the CHECK in migration 0001


def to_cents(euros: Decimal) -> int:
    return int(round(euros * CENTS_PER_EUR))


def to_decimal(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)
