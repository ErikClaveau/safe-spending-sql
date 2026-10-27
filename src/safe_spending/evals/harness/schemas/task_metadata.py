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
    max_corrections: int
    prompt_version: str
    schema_version: str
    dataset_version: str
    synthesis_prompt_version: str | None = Field(
        default=None,
        description="The answer-writing prompt, for tasks that synthesize an answer."
    )
