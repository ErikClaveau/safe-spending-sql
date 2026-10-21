from enum import StrEnum


class GeneratorAction(StrEnum):
    """What the model decided to do with a question (ADR-006).

    Same words as the golden set's `behavior`, minus `no_data`: whether there is data is only
    known after the query runs, so the model never decides it.
    """

    QUERY = "query"
    CLARIFY = "clarify"
    REFUSE = "refuse"
