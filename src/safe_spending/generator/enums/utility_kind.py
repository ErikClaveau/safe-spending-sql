from enum import StrEnum


class UtilityKind(StrEnum):
    """Kind of direct-debit utility; the values are the `kind` field of merchants.yaml."""

    ELECTRICITY = "electricity"
    INTERNET = "internet"
    MOBILE = "mobile"
