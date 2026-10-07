from pydantic import BaseModel, ConfigDict


class TxLabelRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    tx_id: int
    true_category_id: int
    scenario_id: str | None = None
    is_trap: bool = False
    trap_type: str | None = None
    canary: str | None = None
    refund_of_tx_id: int | None = None
