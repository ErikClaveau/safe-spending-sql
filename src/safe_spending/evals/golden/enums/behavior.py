from enum import StrEnum


class Behavior(StrEnum):
    """What the assistant is expected to do with the question."""

    ANSWER = "answer"  # SQL and a figure, even when the figure is 0
    CLARIFY = "clarify"  # ask, or state the assumption it makes
    NO_DATA = "no_data"  # say there is no data for the period, without inventing it
    REFUSE = "refuse"  # a polite refusal: not a banking-spending question
