from pydantic import BaseModel, ConfigDict, Field, computed_field


class NumericVerification(BaseModel):
    """Which numbers of an answer were found in what the query produced, and which were not (plan section 7)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    checked: tuple[str, ...] = Field(description="Every number found in the answer, as written there.")
    untraced: tuple[str, ...] = Field(description="Those with no match in the result, the question or the SQL.")

    @computed_field
    @property
    def ok(self) -> bool:
        return not self.untraced
