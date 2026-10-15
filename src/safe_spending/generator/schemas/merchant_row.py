from pydantic import BaseModel, ConfigDict, Field


class MerchantRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    merchant_id: int = Field(description="Merchant identifier.")
    normalized_name: str = Field(description="Clean merchant name, as the bank would normalize it.")
    mcc: str = Field(description="Merchant category code (ISO 18245).")
