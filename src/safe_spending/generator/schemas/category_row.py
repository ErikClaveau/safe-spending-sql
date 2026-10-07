from pydantic import BaseModel, ConfigDict


class CategoryRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    category_id: int
    name: str
    group_name: str
