"""Canary words: one unique, hard-to-guess token per trap.

A canary is the prefix, the 3-digit user id and a few random characters, all upper case and
ASCII so it survives the statement formatting. The user id inside makes a clash between two
users impossible by construction; within a user, a clash is redrawn.
"""

import numpy as np

# No 0/O or 1/I: a canary must be unambiguous when read in a log.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USER_ID_DIGITS = 3


def new_canary(
        rng: np.random.Generator,
        user_id: int,
        prefix: str,
        random_length: int,
        used: set[str]
) -> str:
    """A canary not in `used`, which it joins."""
    while True:
        suffix = "".join(ALPHABET[int(i)] for i in rng.integers(len(ALPHABET), size=random_length))
        canary = f"{prefix}{user_id:0{USER_ID_DIGITS}d}{suffix}"
        if canary not in used:
            used.add(canary)
            return canary
