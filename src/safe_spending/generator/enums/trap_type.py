from enum import StrEnum


class TrapType(StrEnum):
    """Kinds of prompt injection planted in a movement's concept (design 5.6); the values are
    the `trap_type` column of `tx_labels` and the keys of traps.yaml."""

    DIRECT_INSTRUCTION = "direct_instruction"
    SYSTEM_IMPERSONATION = "system_impersonation"
    RESPONSE_MANIPULATION = "response_manipulation"
    SQL_LOOKALIKE = "sql_lookalike"
    RECATEGORIZATION = "recategorization"
