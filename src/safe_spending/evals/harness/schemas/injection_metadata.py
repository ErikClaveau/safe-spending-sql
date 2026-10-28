from pydantic import BaseModel, ConfigDict, Field

from safe_spending.evals.adversarial import Exposure


class InjectionMetadata(BaseModel):
    """What an injection sample carries: who asks and how the question brings the traps to the model.

    The canaries are not here: the scorer reads them from the generated data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid"
    )

    user_id: int = Field(description="The user the question is asked as; the traps are in this user's data.")
    exposure: Exposure
