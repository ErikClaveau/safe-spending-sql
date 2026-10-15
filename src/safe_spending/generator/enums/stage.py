from enum import StrEnum


class Stage(StrEnum):
    """Generation stages; each (user, stage) pair has its own random stream (see `rng.stream`)."""

    # Order matters: the index is part of the stream key. Append new stages, never reorder.
    PROFILE = "profile"
    RECURRING = "recurring"
    PURCHASES = "purchases"
    SPECIAL = "special"
    SCENARIOS = "scenarios"
    TRAPS = "traps"
    TEXT = "text"
    FX = "fx"  # the shared exchange-rate series, drawn from the GLOBAL stream
    SAVINGS = "savings"  # the savings account and its transfers
