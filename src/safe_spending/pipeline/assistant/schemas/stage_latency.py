from pydantic import BaseModel, ConfigDict, Field, computed_field


class StageLatency(BaseModel):
    """Seconds spent in each stage, over every try (plan section 10).

    Validation is not here: sqlglot takes well under a millisecond and is not measured. The numeric check
    runs inside the synthesis and counts there.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    generation_s: float = Field(description="Model calls that write the SQL, including the tries that were corrected.")
    execution_s: float = Field(description="Database time, including the tries that were corrected.")
    synthesis_s: float = Field(description="Model calls that write the answer, and the check of its numbers.")

    @computed_field
    @property
    def total_s(self) -> float:
        return self.generation_s + self.execution_s + self.synthesis_s
