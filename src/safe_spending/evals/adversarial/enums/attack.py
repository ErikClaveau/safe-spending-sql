from enum import StrEnum


class Attack(StrEnum):
    """How an isolation question tries to reach another user's data; the values are the YAML ones."""

    NAMED_USER = "named_user"  # asks for a user by id or by name
    IMPERSONATION = "impersonation"  # claims to be the victim, an administrator or the bank
    BYPASS = "bypass"  # asks to switch off the filter, RLS or the session user
    SCHEMA_PROBE = "schema_probe"  # asks for base tables, `user_id` or other schemas
    ENUMERATION = "enumeration"  # asks for everybody's rows, or for the "other" customers
    INDIRECT = "indirect"  # reaches the victim through a fact only the victim's data holds
