from pydantic import BaseModel, ConfigDict


class MerchantRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant_id: int
    normalized_name: str
    mcc: str
