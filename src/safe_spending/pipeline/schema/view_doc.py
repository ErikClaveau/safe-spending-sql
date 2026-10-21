from pydantic import BaseModel, ConfigDict, Field

from safe_spending.pipeline.schema.column_doc import ColumnDoc


class ViewDoc(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    name: str
    description: str = Field(description="The view's `COMMENT ON`, written in Spanish for the LLM.")
    columns: tuple[ColumnDoc, ...] = Field(description="In the order the view declares them.")
