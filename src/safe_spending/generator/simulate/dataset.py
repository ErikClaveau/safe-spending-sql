from pydantic import BaseModel

from safe_spending.generator.schemas import (
    AccountRow,
    CategoryRow,
    MerchantRow,
    ScenarioRow,
    TransactionRow,
    TxLabelRow,
    UserLabelRow,
    UserRow,
)


class Dataset(BaseModel):
    # Operational tables: what a real bank would have, loaded into Postgres.
    categories: list[CategoryRow] = []
    merchants: list[MerchantRow] = []
    users: list[UserRow] = []
    accounts: list[AccountRow] = []
    transactions: list[TransactionRow] = []
    # Ground-truth labels: never loaded into the application database.
    tx_labels: list[TxLabelRow] = []
    user_labels: list[UserLabelRow] = []
    scenarios: list[ScenarioRow] = []
