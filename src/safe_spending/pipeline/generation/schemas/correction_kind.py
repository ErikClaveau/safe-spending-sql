from enum import StrEnum


class CorrectionKind(StrEnum):
    """Why the SQL the model wrote had to be written again."""

    REJECTED = "rejected"  # the validator refused it before it ran
    EXECUTION_ERROR = "execution_error"  # the database refused it when it ran
