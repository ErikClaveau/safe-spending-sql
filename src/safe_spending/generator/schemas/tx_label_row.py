from pydantic import BaseModel, ConfigDict, Field


class TxLabelRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    tx_id: int = Field(description="Transaction this label belongs to.")
    true_category_id: int = Field(description="Correct category, by construction.")
    scenario_id: str | None = Field(default=None, description="Scenario that added or changed the movement.")
    is_trap: bool = Field(default=False, description="Whether the movement is an injection trap.")
    trap_type: str | None = Field(default=None, description="Type of trap; only set on traps.")
    canary: str | None = Field(default=None, description="Unique word the trap asks the assistant to print.")
    refund_of_tx_id: int | None = Field(default=None, description="Purchase this refund returns.")
