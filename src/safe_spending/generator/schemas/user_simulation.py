from pydantic import BaseModel, ConfigDict, Field

from safe_spending.generator.schemas.account_row import AccountRow
from safe_spending.generator.schemas.scenario_row import ScenarioRow
from safe_spending.generator.schemas.transaction_row import TransactionRow
from safe_spending.generator.schemas.tx_label_row import TxLabelRow
from safe_spending.generator.schemas.user_label_row import UserLabelRow
from safe_spending.generator.schemas.user_row import UserRow


class UserSimulation(BaseModel):
    """Everything one user owns, as produced by `simulate_user`."""

    model_config = ConfigDict(frozen=True)

    user: UserRow = Field(description="The user.")
    accounts: list[AccountRow] = Field(description="The accounts of the user.")
    transactions: list[TransactionRow] = Field(description="All movements of the user.")
    tx_labels: list[TxLabelRow] = Field(description="Ground-truth label of each movement.")
    user_label: UserLabelRow = Field(description="Ground-truth label of the user.")
    scenarios: list[ScenarioRow] = Field(default=[], description="Scenarios applied to the user.")
