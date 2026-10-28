import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from safe_spending.evals.adversarial.enums import Attack

ID_PATTERN = re.compile(r"^AI-\d{3}$")


class IsolationQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable identifier, AI-001 and up. Never reused.")
    question: str = Field(description="The attempt, as the user writes it, in Spanish.")
    user_id: int = Field(description="The user who asks: the only one whose data the assistant may touch.")
    victim_user_id: int = Field(description="The user whose data the question tries to reach.")
    attack: Attack = Field(description="How the question tries to reach the victim's data.")
    reference_sql: str = Field(
        description="What the question would return if it worked: run as the victim it gives the data that must not leak."
    )
    notes: str | None = Field(default=None, description="What the question checks.")

    @model_validator(mode="after")
    def _is_coherent(self) -> "IsolationQuestion":
        if not ID_PATTERN.match(self.id):
            raise ValueError(f"{self.id}: the id must look like AI-001")
        if self.user_id == self.victim_user_id:
            raise ValueError(f"{self.id}: the victim must be another user")
        return self
