"""Statement descriptions in the style of a Spanish bank (design 4.4).

Upper case, ASCII (accents stripped), truncated to the statement's maximum length.
Descriptions use their own random stream so changing a template never alters amounts or dates.
"""

import unicodedata

import numpy as np

from safe_spending.generator.config import Merchant


def statement(text: str, max_length: int) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.upper().split())[:max_length].rstrip()


def pick_variant(merchant: Merchant, rng: np.random.Generator) -> str:
    """One of the names the merchant appears under: the first one most of the time."""
    variants = merchant.variants
    if len(variants) == 1 or rng.random() < 0.7:
        variant = variants[0]
    else:
        variant = variants[1 + int(rng.integers(len(variants) - 1))]
    if "{n4}" in variant:
        variant = variant.replace("{n4}", f"{int(rng.integers(0, 10000)):04d}")
    return variant


def card_purchase(merchant: Merchant, card_prefix: str, city: str, rng: np.random.Generator) -> str:
    variant = pick_variant(merchant, rng)
    if merchant.channel == "card_present":
        return f"COMPRA TARJ. {card_prefix}XXXX {variant} {city}"
    return f"COMPRA TARJ. {card_prefix}XXXX {variant}"


def direct_debit(merchant: Merchant, rng: np.random.Generator) -> str:
    return f"RECIBO {merchant.legal_name} {int(rng.integers(10**8, 10**9))}"


def salary(employer: str, extra: bool) -> str:
    return f"NOMINA {employer}" + (" PAGA EXTRA" if extra else "")


def rent_transfer(landlord: str, month: int, year: int) -> str:
    return f"TRANSFERENCIA A FAVOR DE {landlord} CONCEPTO ALQUILER {month:02d}/{year}"
