from enum import StrEnum


class Channel(StrEnum):
    """How a merchant charges the user; the values are the `channel` field of merchants.yaml."""

    CARD_PRESENT = "card_present"
    CARD_ONLINE = "card_online"
    SUBSCRIPTION = "subscription"
    DIRECT_DEBIT = "direct_debit"
