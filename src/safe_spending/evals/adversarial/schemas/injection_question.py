import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.evals.adversarial.enums import Exposure

ID_PATTERN = re.compile(r"^AD-\d{3}$")


class InjectionQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable identifier, AD-001 and up. Never reused.")
    question: str = Field(description="An innocent question, as the user writes it, in Spanish.")
    user_id: int = Field(description="The user who asks: one of the adversarial split, whose data holds the traps.")
    exposure: Exposure = Field(description="How the question brings the planted concepts to the assistant.")
    notes: str | None = Field(
        default=None,
        description="What the question checks."
    )

    @model_validator(mode="after")
    def _is_coherent(self) -> "InjectionQuestion":
        if not ID_PATTERN.match(self.id):
            raise ValueError(f"{self.id}: the id must look like AD-001")
        return self
