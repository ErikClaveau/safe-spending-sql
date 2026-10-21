from pydantic import BaseModel, ConfigDict, Field


class CategoryRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    category_id: int = Field(description="Category identifier.")
    name: str = Field(description="Category name.")
    group_name: str = Field(description="Broader group the category belongs to.")
