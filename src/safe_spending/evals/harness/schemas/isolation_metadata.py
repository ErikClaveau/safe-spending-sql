from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.adversarial import Attack


class IsolationMetadata(BaseModel):
    """What an isolation sample carries: who asks, who is targeted, and what a leak would look like."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    user_id: int = Field(description="The user the question is asked as.")
    victim_user_id: int = Field(description="The user whose data the question tries to reach.")
    attack: Attack
    victim: dict = Field(description="ResultTable JSON: what the reference SQL gives for the victim.")
    own: dict = Field(description="ResultTable JSON: what the same SQL gives for the asker.")
