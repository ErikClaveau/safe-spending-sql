from pydantic import BaseModel, ConfigDict, Field


class RunSummary(BaseModel):
    """What the CI gate needs to know about one eval log, read from its header (no samples)."""

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
    accuracy: float = Field(description="Headline execution accuracy over every question.")
    dev_accuracy: float | None = Field(default=None, description="None in logs made before the dev/test split.")
    test_accuracy: float | None = None
    strict_accuracy: float

    @property
    def complete(self) -> bool:
        return self.status == "success" and self.completed_samples == self.samples
