from pydantic import BaseModel, ConfigDict, Field, computed_field


class ValidationResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    violations: tuple[str, ...] = Field(
        default=(),
        description="Every rule the SQL breaks, in words fit for the trace and for telling the model."
    )

    @computed_field
    @property
    def valid(self) -> bool:
        return not self.violations
