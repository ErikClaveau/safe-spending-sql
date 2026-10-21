from pydantic import BaseModel, ConfigDict, Field


class ColumnDoc(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    name: str
    data_type: str = Field(description="Postgres type as `format_type` prints it, e.g. `numeric(12,2)`.")
    description: str = Field(description="The column's `COMMENT ON`, written in Spanish for the LLM.")
