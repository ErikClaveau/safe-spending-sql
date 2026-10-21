"""Synthetic but structurally valid Spanish IBANs (ISO 13616 mod-97 check digits)."""

import numpy as np


SYNTHETIC_BANK_CODE = "9999"  # not assigned to any real bank
ES_NUMERIC = "1428"  # E=14, S=28


def check_digits(bban: str) -> str:
    return f"{98 - int(bban + ES_NUMERIC + '00') % 97:02d}"


def generate(rng: np.random.Generator) -> str:
    branch = f"{int(rng.integers(0, 10**4)):04d}"
    control = f"{int(rng.integers(0, 100)):02d}"
    account = f"{int(rng.integers(0, 10**10)):010d}"
    bban = SYNTHETIC_BANK_CODE + branch + control + account
    return f"ES{check_digits(bban)}{bban}"


def is_valid(iban: str) -> bool:
    return len(iban) == 24 and iban.startswith("ES") and int(iban[4:] + ES_NUMERIC + iban[2:4]) % 97 == 1
