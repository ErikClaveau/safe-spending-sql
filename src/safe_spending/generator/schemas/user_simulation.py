from pydantic import BaseModel, ConfigDict

from safe_spending.generator.schemas.account_row import AccountRow
from safe_spending.generator.schemas.transaction_row import TransactionRow
from safe_spending.generator.schemas.tx_label_row import TxLabelRow
from safe_spending.generator.schemas.user_label_row import UserLabelRow
from safe_spending.generator.schemas.user_row import UserRow


class UserSimulation(BaseModel):
    """Everything one user owns, as produced by `simulate_user`."""

    model_config = ConfigDict(frozen=True)

    user: UserRow
    account: AccountRow
    transactions: list[TransactionRow]
    tx_labels: list[TxLabelRow]
    user_label: UserLabelRow
