from pydantic import BaseModel, ConfigDict

from safe_spending.generator.enums import ScenarioType


class ScenarioAssignment(BaseModel):
    """Which scripted scenario a functional user gets. The map is fixed in the config (not
    drawn), because the golden set must know which user has what."""

    model_config = ConfigDict(frozen=True)

    user_id: int
    type: ScenarioType
