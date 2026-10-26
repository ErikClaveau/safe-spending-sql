from pydantic import BaseModel, ConfigDict, Field


class Grade(BaseModel):
    """The verdict on one question, from the golden set's point of view."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    lenient: bool = Field(description="Right answer; columns nobody asked for are forgiven. The headline.")
    strict: bool = Field(description="Right answer with exactly the expected columns, as benchmarks define it.")
    detail: str = Field(description="Why, in a few words, for the log.")
