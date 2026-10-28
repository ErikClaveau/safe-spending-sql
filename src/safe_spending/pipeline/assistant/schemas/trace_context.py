from pydantic import BaseModel, ConfigDict, Field


class TraceContext(BaseModel):
    """What the assistant cannot know by itself and the process that builds it does."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    commit_sha: str
    user_salt: str = Field(
        min_length=1,
        description="Secret for the user pseudonym; from configuration."
    )
