from pydantic import BaseModel, ConfigDict, Field


class RunSummary(BaseModel):
    """What the CI gate needs to know about any eval log, read from its header (no samples)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    path: str
    status: str
    samples: int = Field(description="How many questions were in the run.")
    completed_samples: int
    model: str
    prompt_version: str
    dataset_version: str
    refusal_fallback: bool

    @property
    def complete(self) -> bool:
        return self.status == "success" and self.completed_samples == self.samples
