from pydantic import BaseModel, ConfigDict


class CategoryDoc(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    name: str
    group_name: str
