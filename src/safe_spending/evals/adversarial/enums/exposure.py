from enum import StrEnum


class Exposure(StrEnum):
    """How an injection question brings the planted concepts to the assistant; the values are the YAML ones."""

    CONCEPT_REQUESTED = "concept_requested"  # asks what the concept said: the trap is in the rows for sure
    LISTING = "listing"  # asks for the movements: the concept is probably among the columns
    AGGREGATE = "aggregate"  # asks for a total or a summary: the trap is in the data, rarely in the rows
    SEARCH = "search"  # asks for movements by what their concept says
