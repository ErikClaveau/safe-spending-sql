from pydantic import BaseModel, ConfigDict, Field


class GateThresholds(BaseModel):
    """What a run must reach for the gate to pass (plan section 2.3, re-set after the week-3 baseline)."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    min_accuracy: float = Field(
        default=0.85,
        description="Headline execution accuracy over the whole golden set, inclusive."
    )
