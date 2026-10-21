from enum import StrEnum


class TxCode(StrEnum):
    """Mirrors the `transactions.tx_code` CHECK constraint of migration 0001."""

    CARD_PURCHASE = "CARD_PURCHASE"
    CARD_REFUND = "CARD_REFUND"
    DIRECT_DEBIT = "DIRECT_DEBIT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    BIZUM_IN = "BIZUM_IN"
    BIZUM_OUT = "BIZUM_OUT"
    SALARY = "SALARY"
    FEE = "FEE"
    ATM_WITHDRAWAL = "ATM_WITHDRAWAL"
