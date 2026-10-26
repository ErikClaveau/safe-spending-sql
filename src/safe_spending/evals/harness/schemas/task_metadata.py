from pydantic import BaseModel, ConfigDict, Field


class TaskMetadata(BaseModel):
    """The configuration of one run, written to the eval log so results can be compared."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    model: str = Field(description="The model under test (ours, not Inspect's).")
    effort: str
    refusal_fallback: bool
    max_attempts: int
    prompt_version: str
    schema_version: str
    dataset_version: str
