"""Amounts are integer cents everywhere inside the generator; never float (design 3.3)."""

from decimal import ROUND_HALF_EVEN, Decimal

CENTS_PER_EUR = 100
BASE_CURRENCY = "EUR"  # the only currency until FX arrives (slice 3); matches the CHECK in migration 0001


def to_cents(euros: Decimal) -> int:
    return int(round(euros * CENTS_PER_EUR))


def to_decimal(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)

def convert_to_eur_cents(
        foreign_cents: int,
        rate: Decimal
) -> int:
    """Minor units of a foreign currency to euro cents.

    `rate` is units of the foreign currency per 1 EUR (so GBP 0.85 means 1 EUR = 0.85 GBP and
    a GBP 30.00 charge is EUR 35.29). Rounded half to even, with the sign kept.
    """
    return int((Decimal(foreign_cents) / rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
