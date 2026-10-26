from enum import StrEnum


class Split(StrEnum):
    """Which part of the golden set a question belongs to (see `splits.py`)."""

    DEV = "dev"  # the questions prompts and documentation are tuned on
    TEST = "test"  # held out: reported every round, never used to decide what to change
