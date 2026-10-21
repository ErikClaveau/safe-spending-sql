from pydantic import BaseModel, Field


class ZeroCategoryParams(BaseModel):
    category: str = Field(description="Category left at zero.")
    group: str = Field(description="Group the category belongs to.")
    purchases_removed: int = Field(description="Proof that the zero is not just a lack of data.")
